"""Compact conversation history into a small, useful working memory.

This is a deterministic first pass. It keeps goals, constraints, decisions,
corrections, open questions, evidence references, and a short recent window.
It does not pretend that deletion is summarization: the caller decides when
raw logs can be removed under the retention policy.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable


IMPORTANT_TYPES = {
    "goal",
    "constraint",
    "decision",
    "correction",
    "open_question",
    "evidence",
    "tool_result",
}

_IMPORTANT_PATTERNS = (
    "目标",
    "服务对象",
    "约束",
    "必须",
    "决定",
    "修正",
    "纠正",
    "不要",
    "待确认",
    "未解决",
    "证据",
    "上市",
    "来源",
)


def _parse_datetime(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _content(message: dict[str, Any]) -> str:
    return str(message.get("content") or message.get("text") or "").strip()


def _canonical(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def score_message_utility(message: dict[str, Any]) -> int:
    """Score whether a message should survive context compaction."""

    content = _content(message)
    message_type = str(message.get("message_type") or "").strip()
    score = int(message.get("importance") or 0)
    if message_type in IMPORTANT_TYPES:
        score += 10
    if message.get("role") == "user":
        score += 1
    if len(content) >= 20:
        score += 1
    score += sum(2 for pattern in _IMPORTANT_PATTERNS if pattern in content)
    if message.get("evidence_ids") or message.get("source_refs"):
        score += 5
    return score


def _bucket(messages: Iterable[dict[str, Any]], keywords: tuple[str, ...], message_types: set[str]) -> list[str]:
    values: list[str] = []
    for message in messages:
        content = _content(message)
        if str(message.get("message_type") or "") in message_types or any(keyword in content for keyword in keywords):
            if content and content not in values:
                values.append(content[:500])
    return values[:10]


def compact_conversation(
    messages: list[dict[str, Any]],
    recent_limit: int = 6,
    max_items: int = 20,
) -> dict[str, Any]:
    """Return compact working memory and the IDs selected from raw history."""

    ordered = sorted(messages, key=lambda item: _parse_datetime(item.get("created_at")))
    recent = ordered[-max(0, recent_limit):] if recent_limit else []
    candidates = sorted(
        ordered,
        key=lambda item: (score_message_utility(item), _parse_datetime(item.get("created_at"))),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_content: set[str] = set()
    important_candidates = [
        message for message in candidates
        if score_message_utility(message) >= 3 or str(message.get("message_type") or "") in IMPORTANT_TYPES
    ]
    recent_candidates = sorted(
        recent,
        key=lambda item: (
            score_message_utility(item),
            1 if item.get("role") == "user" else 0,
            _parse_datetime(item.get("created_at")),
        ),
        reverse=True,
    )
    for message in important_candidates + recent_candidates:
        message_id = str(message.get("message_id") or message.get("event_id") or "")
        canonical = _canonical(_content(message))
        if not message_id or not canonical or canonical in seen_content:
            continue
        if len(selected) >= max_items:
            break
        seen_content.add(canonical)
        selected.append(message)

    selected.sort(key=lambda item: _parse_datetime(item.get("created_at")))
    compact_recent = [
        {
            "message_id": str(item.get("message_id") or item.get("event_id") or ""),
            "role": item.get("role"),
            "content": _content(item)[:500],
            "created_at": item.get("created_at"),
            "message_type": item.get("message_type"),
        }
        for item in selected[-max(1, recent_limit):]
    ]
    source_ids = [str(item.get("message_id") or item.get("event_id") or "") for item in selected]
    all_ids = {str(item.get("message_id") or item.get("event_id") or "") for item in messages}
    return {
        "memory_version": "conversation-memory-v0.1",
        "customer_id": next((item.get("customer_id") for item in messages if item.get("customer_id")), None),
        "conversation_id": next((item.get("conversation_id") for item in messages if item.get("conversation_id")), None),
        "active_goals": _bucket(selected, ("目标", "服务对象", "要做"), {"goal"}),
        "constraints": _bucket(selected, ("必须", "不能", "限制", "权限"), {"constraint"}),
        "decisions": _bucket(selected, ("决定", "采用", "先用"), {"decision"}),
        "corrections": _bucket(selected, ("修正", "纠正", "不要再"), {"correction"}),
        "open_questions": _bucket(selected, ("待确认", "未解决", "怎么", "是否", "？"), {"open_question"}),
        "evidence_refs": [
            {"message_id": str(item.get("message_id") or item.get("event_id") or ""), "evidence_ids": item.get("evidence_ids", []), "source_refs": item.get("source_refs", [])}
            for item in selected
            if item.get("evidence_ids") or item.get("source_refs")
        ][:10],
        "recent_messages": compact_recent,
        "source_message_ids": source_ids,
        "dropped_message_count": max(0, len(all_ids - set(source_ids))),
        "selection_policy": "utility-ranked goals/constraints/decisions/corrections/evidence + recent window; duplicate content removed",
    }


__all__ = ["compact_conversation", "score_message_utility"]
