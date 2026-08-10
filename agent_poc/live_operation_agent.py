"""Minimal live operations-agent flow grounded in official 亿欧 records."""

from __future__ import annotations

import json
from typing import Any

from agent_poc.qwen_client import QwenConfigurationError, QwenRequestError


def _source_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(record.get("record_id") or ""),
        "record_type": str(record.get("record_type") or ""),
        "title": str(record.get("title") or ""),
        "summary": str(record.get("summary") or ""),
        "published_at": str(record.get("published_at") or ""),
        "source": str(record.get("source") or "亿欧数据"),
        "source_url": str(record.get("source_url") or ""),
        "link_origin": str(record.get("link_origin") or ""),
        "attributes": record.get("attributes") or {},
    }


def build_live_help_messages(
    customer: dict[str, Any],
    behavior_context: dict[str, Any],
    question: str,
    source_records: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build a source-locked prompt for the live help consultation."""

    system = (
        "你是亿欧出海运营 Agent，服务计划在美国资本市场上市的海外企业。"
        "回答重点是：这些最新真实资讯对客户有什么帮助，而不是泛泛描述有什么影响。"
        "你只能使用用户消息中提供的 source_records；不得补造公司、数字、案例、监管事实或链接。"
        "先按发布时间列出资讯，再分析其对业务判断、融资准备、合规准备、投资者沟通和上市节奏的帮助。"
        "每项判断必须引用对应 record_id，并原样保留 source_url。"
        "资料不足时明确写‘现有来源不足以判断’，所有结论均为待人工审核的决策辅助。"
    )
    payload = {
        "question": question,
        "customer": customer,
        "simulated_behavior_context": behavior_context,
        "source_records": [_source_view(record) for record in source_records],
        "required_answer_sections": ["最新真实资讯", "对客户有什么帮助", "依据与不确定性"],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _trusted_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for item in items:
        source = _source_view(item)
        if source["record_id"] and source["source_url"].startswith(("https://", "http://")):
            sources.append(source)
    return sources


def run_live_consultation(
    question: str,
    customer: dict[str, Any],
    behavior_context: dict[str, Any],
    limit: int,
    data_client: Any,
    qwen_client: Any,
) -> dict[str, Any]:
    """Fetch current official records and ask Qwen using only those records."""

    data_result = data_client.consult(question, limit=limit)
    sources = _trusted_sources(data_result.get("items") or [])
    base_result: dict[str, Any] = {
        "question": question,
        "customer": customer,
        "behavior_context": behavior_context,
        "retrieved_at": data_result.get("retrieved_at"),
        "query_type": data_result.get("query_type"),
        "query_applied": data_result.get("query_applied"),
        "data_status": data_result.get("status"),
        "data_source": data_result.get("source"),
        "source_count": len(sources),
        "sources": sources,
        "model": getattr(qwen_client, "model", None),
        "human_review_required": True,
    }
    if data_result.get("status") not in {"ok", "ok_empty"}:
        return {
            **base_result,
            "status": "source_unavailable",
            "answer": data_result.get("message") or "官网数据暂时不可用。",
            "usage": None,
        }
    if not sources:
        return {
            **base_result,
            "status": "blocked_no_source_links",
            "answer": "官网返回了记录，但没有可追溯链接，本次不调用模型。",
            "usage": None,
        }

    messages = build_live_help_messages(customer, behavior_context, question, sources)
    try:
        model_result = qwen_client.complete(messages, temperature=0.1, max_tokens=1800)
    except QwenConfigurationError as exc:
        return {
            **base_result,
            "status": "sources_ready_model_not_run",
            "answer": str(exc),
            "usage": None,
        }
    except QwenRequestError as exc:
        return {
            **base_result,
            "status": "model_error",
            "answer": str(exc),
            "usage": None,
        }

    return {
        **base_result,
        "status": "ok",
        "answer": model_result["content"],
        "model": model_result["model"],
        "usage": model_result.get("usage"),
        "response_id": model_result.get("response_id"),
    }


def render_live_answer_markdown(result: dict[str, Any]) -> str:
    """Render trusted sources independently from model-generated prose."""

    customer_name = str((result.get("customer") or {}).get("company_name") or "模拟客户")
    lines = [
        "# 亿欧出海运营 Agent 实时咨询",
        "",
        f"客户：{customer_name}",
        f"官网读取时间：{result.get('retrieved_at') or '未知'}",
        f"运行状态：{result.get('status') or 'unknown'}",
        "",
        "## 最新真实资讯与官网链接",
        "",
    ]
    sources = result.get("sources") or []
    if not sources:
        lines.append("本次没有取得带可追溯链接的官网记录。")
    for index, source in enumerate(sources, start=1):
        title = source.get("title") or source.get("record_id") or f"来源 {index}"
        url = source.get("source_url") or ""
        published_at = source.get("published_at") or "时间未知"
        summary = source.get("summary") or ""
        lines.extend(
            [
                f"{index}. [{title}]({url})",
                f"   - 时间：{published_at}",
                f"   - 来源编号：{source.get('record_id') or '未知'}",
                f"   - 摘要：{summary or '官网默认列表未提供摘要'}",
            ]
        )
    lines.extend(
        [
            "",
            "## 对客户有什么帮助",
            "",
            str(result.get("answer") or "未生成分析。"),
            "",
            "> 以上分析仅基于列出的亿欧官网记录，是待人工审核的决策辅助，不构成投资、法律或上市结论。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "build_live_help_messages",
    "render_live_answer_markdown",
    "run_live_consultation",
]
