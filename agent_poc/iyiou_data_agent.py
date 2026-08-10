"""Read-only adapter for the public 亿欧数据 data endpoints.

The adapter deliberately stays small: it classifies a consultation, calls one
official read endpoint, normalizes the returned records, and reports when a
login-gated endpoint cannot be used. It does not submit forms, change follows,
export data, send messages, or write back to the website.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


IYIOU_API_BASE_URL = "https://apidata.iyiou.com"

READ_ENDPOINTS = {
    "home": "/spa/home/data",
    "news": "/spa/news/defaultList",
    "investment": "/spa/invest/defaultList",
    "company": "/spa/company/defaultList",
    "policy": "/spa/policy/getPolicyDefaultList",
    "bidding": "/spa/bidding/getBiddingDefaultList",
    "industry": "/spa/index/contents/search",
    "search": "/spa/search/all",
}


class IYIOUDataError(RuntimeError):
    """Base error for the official data adapter."""


class IYIOUAuthRequired(IYIOUDataError):
    """Raised when an endpoint requires a valid user session."""

    def __init__(self, endpoint: str, message: str = "该官网数据入口需要登录") -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.code = 401


class IYIOURequestError(IYIOUDataError):
    """Raised when the official API returns a non-success response."""

    def __init__(self, endpoint: str, code: Any, message: str) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.code = code


def classify_consultation(question: str) -> str:
    """Route a short user question to the smallest suitable data category."""

    text = str(question or "").strip().lower()
    if any(token in text for token in ("融资事件", "融资", "投资事件", "投资方", "投资机构")):
        return "investment"
    if any(token in text for token in ("招标", "招投标", "中标", "采购公告")):
        return "bidding"
    if any(token in text for token in ("政策", "法规", "行动方案", "通知")):
        return "policy"
    if any(token in text for token in ("资讯", "新闻", "情报", "动态", "消息")):
        return "news"
    if any(token in text for token in ("行业", "指标", "行业研究", "研究报告", "图表", "数据分析")):
        return "industry"
    if any(token in text for token in ("公司", "企业", "工商", "企业分析")):
        return "company"
    return "search"


def _default_transport(url: str, headers: Mapping[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, method="GET", headers=dict(headers))
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise IYIOURequestError(url, exc.code, f"官网请求失败：HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise IYIOURequestError(url, "network_error", "官网数据暂时无法访问") from exc
    except json.JSONDecodeError as exc:
        raise IYIOURequestError(url, "invalid_json", "官网返回内容不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise IYIOURequestError(url, "invalid_payload", "官网返回内容不是对象")
    return payload


def _first_value(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _official_detail_link(record_type: str, record: Mapping[str, Any]) -> tuple[str, str]:
    """Return a record-specific public page when the API omits sourceLink."""

    direct_url = _first_value(record, "sourceUrl", "sourceLink", "bidUrl", "url")
    if direct_url:
        return str(direct_url), "api_source_link"

    company_id = _first_value(record, "comId", "companyId")
    report_id = _first_value(record, "reportId", "id")
    bidding_id = _first_value(record, "biddingId")
    if record_type in {"investment", "company"} and company_id:
        return (
            f"https://data.iyiou.com/company/details/{company_id}/profile?source=iyiou.trz",
            "official_company_profile",
        )
    if record_type in {"news", "report", "briefing"} and report_id:
        return (
            f"https://data.iyiou.com/intelligence/details/{report_id}",
            "official_intelligence_detail",
        )
    if record_type == "bidding" and bidding_id:
        return (
            f"https://data.iyiou.com/intelligence/biddetails/{bidding_id}",
            "official_bidding_detail",
        )
    return "https://data.iyiou.com/home", "official_home_fallback"


def _extract_records(kind: str, payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    data = payload.get("data", payload)
    if not isinstance(data, Mapping):
        return [], None

    if kind == "home":
        records: list[dict[str, Any]] = []
        for category, record_type in (
            ("investStat", "investment"),
            ("biddingList", "bidding"),
            ("policyList", "policy"),
            ("recommendReportList", "report"),
            ("recommendBriefList", "briefing"),
        ):
            value = data.get(category)
            if category == "investStat" and isinstance(value, Mapping):
                value = value.get("investList")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, Mapping):
                        record = dict(item)
                        record["_record_type"] = record_type
                        records.append(record)
        return records, len(records)

    data_list = data.get("dataList", data)
    if isinstance(data_list, Mapping):
        raw_records = data_list.get("records", [])
        total = data_list.get("total")
    elif isinstance(data_list, list):
        raw_records = data_list
        total = len(data_list)
    else:
        raw_records = []
        total = None
    records = [dict(item) for item in raw_records if isinstance(item, Mapping)]
    return records, total if isinstance(total, int) else None


def normalize_records(kind: str, payload: Mapping[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    """Normalize different official data categories to one evidence shape."""

    raw_records, _ = _extract_records(kind, payload)
    normalized: list[dict[str, Any]] = []
    for record in raw_records[:limit]:
        record_type = str(record.pop("_record_type", kind))
        record_id = _first_value(
            record,
            "reportId",
            "investId",
            "comId",
            "biddingId",
            "reportId",
            "id",
        )
        title = _first_value(record, "title", "briefName", "fullName", "name", "scenarioTitle")
        summary = _first_value(record, "summary", "briefIntro", "detailIntro", "content", "intro")
        published_at = _first_value(record, "pubTime", "investTime", "publishDate", "updatedAt")
        source_url, link_origin = _official_detail_link(record_type, record)
        source = _first_value(record, "source", "sourceTitle", "sourceTypeDesc")
        attributes = {
            "industry": _first_value(record, "industryName", "industry"),
            "amount": _first_value(record, "investAmount", "latestInvestAmount"),
            "currency": _first_value(record, "investCurrencyDesc", "latestInvestCurrencyStr"),
            "round": _first_value(record, "investRoundDesc", "latestInvestRoundStr"),
            "investors": [
                item.get("investorName")
                for item in (record.get("investors") or [])
                if isinstance(item, Mapping) and item.get("investorName")
            ],
        }
        normalized.append(
            {
                "record_type": record_type,
                "record_id": str(record_id or ""),
                "title": str(title or ""),
                "summary": str(summary or ""),
                "published_at": str(published_at or ""),
                "source": str(source or "亿欧数据"),
                "source_url": str(source_url or ""),
                "official_source": "data.iyiou.com",
                "link_origin": link_origin,
                "attributes": attributes,
                "raw_fields": record,
            }
        )
    return normalized


class IYIOUClient:
    """Small read-only client for the official 亿欧数据 API."""

    def __init__(
        self,
        base_url: str = IYIOU_API_BASE_URL,
        auth_token: str | None = None,
        timeout: float = 20.0,
        transport: Callable[[str, Mapping[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token if auth_token is not None else os.getenv("IYIOU_DATA_AUTH")
        self.timeout = timeout
        self._transport = transport

    def _request(self, endpoint: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        query = {key: value for key, value in (params or {}).items() if value not in (None, "")}
        url = f"{self.base_url}{endpoint}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"Accept": "application/json"}
        if self.auth_token:
            headers["Auth"] = self.auth_token
        if self._transport is not None:
            payload = self._transport(url, headers)
        else:
            payload = _default_transport(url, headers, self.timeout)
        code = payload.get("code", 200)
        if code == 401:
            raise IYIOUAuthRequired(endpoint, str(payload.get("message") or "该官网数据入口需要登录"))
        if code != 200:
            raise IYIOURequestError(endpoint, code, str(payload.get("message") or "官网数据请求失败"))
        return payload

    def fetch(self, kind: str, question: str = "", limit: int = 20) -> tuple[dict[str, Any], str, bool]:
        if kind not in READ_ENDPOINTS:
            raise ValueError(f"Unsupported 亿欧数据 category: {kind}")
        endpoint = READ_ENDPOINTS[kind]
        params: dict[str, Any] = {}
        query_applied = False
        if kind == "search":
            params["keyword"] = question
            query_applied = True
        elif kind == "industry":
            params["chartTitle"] = question
            params["pageSize"] = limit
            query_applied = bool(question.strip())
        payload = self._request(endpoint, params)
        return payload, endpoint, query_applied

    def consult(self, question: str, limit: int = 10) -> dict[str, Any]:
        question = str(question or "").strip()
        kind = classify_consultation(question)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        try:
            payload, endpoint, query_applied = self.fetch(kind, question, limit)
            items = normalize_records(kind, payload, limit=limit)
            _, total = _extract_records(kind, payload)
            return {
                "query": question,
                "query_type": kind,
                "status": "ok" if items else "ok_empty",
                "needs_login": False,
                "query_applied": query_applied,
                "items": items,
                "total": total if total is not None else len(items),
                "source": {
                    "site": "data.iyiou.com",
                    "api_endpoint": endpoint,
                    "official_read_only": True,
                },
                "retrieved_at": retrieved_at,
                "answer_mode": "structured_first_pass",
                "human_review_required": True,
                "notes": [
                    "当前返回官方数据结构和来源，不自动生成事实之外的结论。",
                    "公开默认列表未必按关键词筛选；query_applied=false 时仅代表读取该类最新列表。",
                ],
            }
        except IYIOUAuthRequired as exc:
            if kind in {"bidding", "policy"}:
                try:
                    fallback_payload, fallback_endpoint, _ = self.fetch("home", question, limit)
                    fallback_items = [
                        item for item in normalize_records("home", fallback_payload, limit=100)
                        if item["record_type"] == kind
                    ]
                    if fallback_items:
                        return {
                            "query": question,
                            "query_type": kind,
                            "status": "ok",
                            "needs_login": False,
                            "query_applied": False,
                            "items": fallback_items[:limit],
                            "total": len(fallback_items),
                            "source": {
                                "site": "data.iyiou.com",
                                "api_endpoint": fallback_endpoint,
                                "official_read_only": True,
                                "fallback_from": exc.endpoint,
                            },
                            "retrieved_at": retrieved_at,
                            "answer_mode": "structured_first_pass",
                            "human_review_required": True,
                            "notes": [
                                "专用入口需要登录，已使用官网首页公开汇总中的同类数据。",
                                "首页汇总不是完整筛选结果，query_applied=false。",
                            ],
                        }
                except IYIOUDataError:
                    pass
            return {
                "query": question,
                "query_type": kind,
                "status": "needs_auth",
                "needs_login": True,
                "query_applied": kind in {"search", "industry"},
                "items": [],
                "total": 0,
                "source": {
                    "site": "data.iyiou.com",
                    "api_endpoint": exc.endpoint,
                    "official_read_only": True,
                },
                "retrieved_at": retrieved_at,
                "answer_mode": "login_required",
                "human_review_required": True,
                "message": "该类官网查询需要登录权限；请配置授权后的 IYIOU_DATA_AUTH，再进行读取。",
            }
        except IYIOUDataError as exc:
            return {
                "query": question,
                "query_type": kind,
                "status": "error",
                "needs_login": False,
                "query_applied": False,
                "items": [],
                "total": 0,
                "source": {"site": "data.iyiou.com", "official_read_only": True},
                "retrieved_at": retrieved_at,
                "answer_mode": "unavailable",
                "human_review_required": True,
                "message": str(exc),
            }


__all__ = [
    "IYIOU_API_BASE_URL",
    "IYIOUAuthRequired",
    "IYIOUClient",
    "IYIOUDataError",
    "IYIOURequestError",
    "classify_consultation",
    "normalize_records",
]
