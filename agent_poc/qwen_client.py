"""Safe OpenAI-compatible DashScope/Qwen client.

The API key is read only from ``DASHSCOPE_API_KEY`` or an explicit runtime
argument. It is never written to a file, included in results, or logged.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-flash"


class QwenConfigurationError(RuntimeError):
    pass


class QwenRequestError(RuntimeError):
    pass


def _default_transport(url: str, headers: Mapping[str, str], body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(url, method="POST", headers=dict(headers), data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise QwenRequestError("Qwen 请求失败，请检查权限、模型和网络，不记录原始密钥或响应正文。") from exc
    if not isinstance(payload, dict):
        raise QwenRequestError("Qwen 返回内容不是 JSON 对象。")
    return payload


class QwenClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        transport: Callable[[str, Mapping[str, str], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DASHSCOPE_API_KEY", "")
        self.base_url = (base_url or os.getenv("DASHSCOPE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.getenv("DASHSCOPE_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self._transport = transport

    def configuration_status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.api_key),
            "base_url": self.base_url,
            "model": self.model,
            "api_key_present": bool(self.api_key),
        }

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise QwenConfigurationError("DASHSCOPE_API_KEY 未配置；请在本机环境变量中设置轮换后的 Key。")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        payload = self._transport(url, headers, body) if self._transport is not None else _default_transport(url, headers, body, self.timeout)
        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = message.get("content", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenRequestError("Qwen 返回结构缺少 choices.message.content。") from exc
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        return {
            "content": content,
            "model": payload.get("model", self.model),
            "usage": payload.get("usage"),
            "response_id": payload.get("id"),
        }

    def build_cross_market_messages(
        self,
        customer_context: dict[str, Any],
        source_record: dict[str, Any],
        compact_memory: dict[str, Any],
    ) -> list[dict[str, str]]:
        system = (
            "你是面向拟在美股上市的海外企业的跨市场情报分析助手。"
            "只根据给定来源和压缩上下文判断，不补造事实。"
            "输出 JSON：materiality、cross_market_difference、affected_business_areas、"
            "us_listing_relevance、evidence、uncertainties、follow_up_questions。"
            "每个事实都要绑定 source_record_id；不把可能性写成确定结论。"
        )
        user_payload = {
            "customer_context": customer_context,
            "source_record": source_record,
            "compact_memory": compact_memory,
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]


__all__ = ["QwenClient", "QwenConfigurationError", "QwenRequestError"]
