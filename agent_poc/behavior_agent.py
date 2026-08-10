"""Deterministic, local-first behavior analysis for the first operations-agent slice.

The module deliberately does not call an LLM. It proves the data contract, evidence
chain, review boundary, and context budget before semantic work is delegated to Qwen.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


RULE_VERSION = "behavior-rule-v0.1"
MAX_RECENT_EVENTS = 10
MAX_HISTORY_EVIDENCE = 5
HANDOFF_REQUIRED_FIELDS = (
    "content_id",
    "source_url",
    "company_ids",
    "company_match_status",
    "change_type",
    "quality_status",
    "translation_status",
    "dedup_status",
    "publish_status",
    "data_version",
    "content_version",
)
READY_DEDUP_STATUSES = {"unique", "merged"}

EVENT_WEIGHTS = {
    "article_view": 1,
    "repeat_view": 2,
    "search": 2,
    "company_query": 3,
    "favorite": 2,
    "report_download": 4,
    "subscription_request": 4,
    "material_request": 5,
    "cooperation_request": 6,
    "meeting_request": 6,
}

EVALUATING_EVENTS = {"report_download", "subscription_request", "material_request"}
PROGRESSING_EVENTS = {"cooperation_request", "meeting_request"}

XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _parse_datetime(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref or "")
    if not letters:
        return 0
    index = 0
    for char in letters.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _xlsx_cell_value(cell: ET.Element) -> Any:
    inline = cell.find(f"{{{XLSX_NS}}}is")
    if inline is not None:
        return "".join(node.text or "" for node in inline.iter(f"{{{XLSX_NS}}}t"))
    value = cell.find(f"{{{XLSX_NS}}}v")
    return value.text if value is not None else ""


def read_xlsx_news(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Read the simple inline-string export without requiring a spreadsheet package."""

    with zipfile.ZipFile(path) as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet_xml)
    rows: list[list[Any]] = []
    for row in root.findall(f".//{{{XLSX_NS}}}row"):
        values: list[Any] = []
        for cell in row.findall(f"{{{XLSX_NS}}}c"):
            index = _column_index(cell.attrib.get("r", ""))
            while len(values) <= index:
                values.append("")
            values[index] = _xlsx_cell_value(cell)
        rows.append(values)

    if not rows:
        return []
    headers = [str(value or "").strip() for value in rows[0]]
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        record = {header: (row[index] if index < len(row) else "") for index, header in enumerate(headers) if header}
        if not any(str(value or "").strip() for value in record.values()):
            continue
        records.append(prepare_news_record(record))
        if limit is not None and len(records) >= limit:
            break
    return records


def prepare_news_record(record: dict[str, Any]) -> dict[str, Any]:
    """Attach conservative quality metadata without rewriting the source values."""

    text_values = [str(record.get(key) or "") for key in ("title", "summary", "ai_summary", "content")]
    flags: list[str] = []
    if any("\ufffd" in value for value in text_values):
        flags.append("replacement_character_detected")
    if not str(record.get("source_url") or "").startswith(("http://", "https://")):
        flags.append("source_url_missing_or_invalid")
    title_usable = bool(str(record.get("title") or "").strip()) and "\ufffd" not in str(record.get("title") or "")
    if not title_usable:
        flags.append("title_not_semantically_usable")
    result = dict(record)
    result["verification_status"] = "blocked" if flags else "pending"
    result["semantic_matching_status"] = "blocked_pending_clean_source" if flags else "ready_for_review"
    result["data_quality_flags"] = sorted(set(flags))
    result["processing_version"] = "news-snapshot-v0.1"
    return result


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"JSONL record must be an object at {path}:{line_number}")
            records.append(value)
    return records


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _event_score(event: dict[str, Any]) -> int:
    return EVENT_WEIGHTS.get(str(event.get("event_type") or ""), 0)


def _event_id(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or "")


def _recent_events(events: Iterable[dict[str, Any]], limit: int = MAX_RECENT_EVENTS) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: _parse_datetime(item.get("created_at")), reverse=True)[:limit]


def _supporting_events(events: Iterable[dict[str, Any]], allowed: set[str]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("event_type") in allowed]


def judge_intent(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Map recent behavior to a current, explainable four-level intent stage."""

    recent = _recent_events(events)
    event_types = {event.get("event_type") for event in recent}
    topic_counts = Counter(str(event.get("topic") or "未分类") for event in recent)
    evidence: list[dict[str, Any]]
    if event_types & PROGRESSING_EVENTS:
        stage = "推进"
        evidence = _supporting_events(recent, PROGRESSING_EVENTS)
        reason = "出现明确的合作或会议请求，当前意向进入人工跟进候选。"
    elif event_types & EVALUATING_EVENTS:
        stage = "评估"
        evidence = _supporting_events(recent, EVALUATING_EVENTS)
        reason = "出现资料、下载或订阅动作，说明用户已从了解进入评估候选。"
    elif len([event for event in recent if _event_score(event) >= 2]) >= 2 or max(topic_counts.values(), default=0) >= 2:
        stage = "了解"
        evidence = [event for event in recent if _event_score(event) >= 2]
        reason = "存在至少两次有主题的主动互动或重复关注，但尚无明确资料/合作请求。"
    elif recent:
        stage = "关注"
        evidence = recent[:3]
        reason = "目前只有浏览或低强度互动，不能推出高意向。"
    else:
        stage = "关注"
        evidence = []
        reason = "没有可用行为证据。"

    support_count = len(evidence)
    confidence = 0.35 + min(0.45, support_count * 0.10)
    if stage in {"评估", "推进"}:
        # Explicit requests are stronger evidence than passive views.
        confidence += 0.25
    confidence = round(min(0.95, confidence), 2)
    return {
        "stage": stage,
        "confidence": confidence,
        "confidence_semantics": "规则判断置信度，不是客户购买概率",
        "reason": reason,
        "evidence_ids": [_event_id(event) for event in evidence],
    }


def propose_profile_changes(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate reviewable profile candidates; never write a stable profile."""

    topic_events: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        topic = str(event.get("topic") or "").strip()
        if topic:
            topic_events.setdefault(topic, []).append(event)

    proposals: list[dict[str, Any]] = []
    for topic, topic_records in sorted(topic_events.items()):
        explicit = any(event.get("event_type") in {"subscription_request", "material_request"} for event in topic_records)
        if len(topic_records) < 2 and not explicit:
            continue
        confidence = 0.55 + min(0.25, len(topic_records) * 0.08) + (0.08 if explicit else 0)
        proposals.append(
            {
                "candidate_type": "interest_candidate",
                "field": "confirmed_interests",
                "value": topic,
                "status": "needs_review",
                "confidence": round(min(0.90, confidence), 2),
                "confidence_semantics": "规则候选置信度，不是已确认画像",
                "evidence_ids": [_event_id(event) for event in topic_records],
                "reason": "重复主动行为或明确订阅/资料请求支持该候选；单次浏览不会写入画像。",
            }
        )
    return proposals


def _recommended_action(stage: str) -> str:
    return {
        "关注": "继续观察，不主动打扰；可在下次简报中提供相关主题试读。",
        "了解": "生成相关主题的已核验内容候选，交人工审核后推荐。",
        "评估": "准备已审核的资料/报告草稿，由运营人员确认需求后发送。",
        "推进": "进入人工商务跟进队列，先核对需求和授权，不自动联系。",
    }[stage]


def _stable_id(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _collect_source_refs(
    events: Iterable[dict[str, Any]],
    news_by_id: dict[str, dict[str, Any]],
    data_agent_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    source_refs: list[dict[str, Any]] = []
    quality_flags: set[str] = set()
    blocked_content_refs: list[dict[str, Any]] = []
    feedback_items: list[dict[str, Any]] = []
    for event in events:
        if event.get("object_type") != "news":
            continue
        report_id = str(event.get("object_id") or "")
        item = news_by_id.get(report_id)
        if not item:
            quality_flags.add("news_reference_not_found")
            continue
        quality_flags.update(item.get("data_quality_flags") or [])
        if item.get("semantic_matching_status") == "blocked_pending_clean_source":
            quality_flags.add("semantic_matching_blocked_pending_clean_source")
        handoff = data_agent_by_id.get(report_id) if data_agent_by_id is not None else None
        if data_agent_by_id is not None and handoff is None:
            reasons = ["data_agent_handoff_not_found"]
            quality_flags.update(reasons)
            blocked_content_refs.append({"content_id": report_id, "reasons": reasons})
            feedback_items.append(
                {
                    "action": "request_handoff_record",
                    "content_id": report_id,
                    "event_id": _event_id(event),
                    "reasons": reasons,
                }
            )
            continue
        if handoff is not None:
            quality_flags.update(handoff.get("quality_flags") or [])
            ready, reasons = _handoff_readiness(handoff)
            if not ready:
                quality_flags.update(reasons)
                blocked_content_refs.append(
                    {
                        "content_id": report_id,
                        "change_type": handoff.get("change_type"),
                        "content_version": handoff.get("content_version"),
                        "reasons": reasons,
                    }
                )
                feedback_items.append(
                    {
                        "action": "reprocess_content",
                        "content_id": report_id,
                        "event_id": _event_id(event),
                        "reasons": reasons,
                    }
                )
                continue
        source_ref = {
            "report_id": report_id,
            "content_id": report_id,
            "source_url": handoff.get("source_url") if handoff is not None else item.get("source_url"),
            "source": item.get("source"),
            "verification_status": item.get("verification_status"),
            "semantic_matching_status": item.get("semantic_matching_status"),
        }
        if handoff is not None:
            for field in (
                "company_ids",
                "company_match_status",
                "change_type",
                "quality_status",
                "translation_status",
                "dedup_status",
                "publish_status",
                "data_version",
                "content_version",
            ):
                source_ref[field] = handoff.get(field)
        source_refs.append(source_ref)
    return (
        source_refs[:MAX_HISTORY_EVIDENCE],
        quality_flags,
        blocked_content_refs[:MAX_HISTORY_EVIDENCE],
        feedback_items[:MAX_HISTORY_EVIDENCE],
    )


def _handoff_readiness(record: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check whether a data-agent record is safe for operations-agent evidence."""

    reasons: list[str] = []
    for field in HANDOFF_REQUIRED_FIELDS:
        if field not in record or record.get(field) in (None, ""):
            reasons.append(f"handoff_missing_{field}")
    if record.get("company_match_status") != "matched":
        reasons.append("company_match_not_ready")
    if record.get("quality_status") != "passed":
        reasons.append("quality_not_ready")
    if record.get("translation_status") != "passed":
        reasons.append("translation_not_ready")
    if record.get("dedup_status") not in READY_DEDUP_STATUSES:
        reasons.append("dedup_not_ready")
    if record.get("publish_status") != "candidate":
        reasons.append("publish_not_ready")
    if record.get("change_type") == "full_overlap":
        reasons.append("full_overlap")
    if not str(record.get("source_url") or "").startswith(("http://", "https://")):
        reasons.append("source_url_missing_or_invalid")
    return not reasons, sorted(set(reasons))


def analyze_partner(
    partner: dict[str, Any],
    events: list[dict[str, Any]],
    news: list[dict[str, Any]],
    data_agent_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Produce the minimal operations-agent result for one partner."""

    partner_id = str(partner.get("partner_id") or "")
    partner_events = [event for event in events if str(event.get("partner_id")) == partner_id]
    recent = _recent_events(partner_events)
    news_by_id = {str(item.get("report_id")): item for item in news}
    data_agent_by_id = (
        {str(item.get("content_id")): item for item in data_agent_records}
        if data_agent_records is not None
        else None
    )
    source_refs, quality_flags, blocked_content_refs, feedback_items = _collect_source_refs(
        recent,
        news_by_id,
        data_agent_by_id,
    )

    intent = judge_intent(recent)
    profile_proposals = propose_profile_changes(recent)
    rule_score = sum(_event_score(event) for event in recent)
    input_snapshot = {
        "partner": partner,
        "recent_events": recent,
        "source_refs": source_refs,
        "data_agent_handoff": [
            data_agent_by_id.get(str(event.get("object_id")))
            for event in recent
            if data_agent_by_id is not None and event.get("object_type") == "news" and data_agent_by_id.get(str(event.get("object_id")))
        ],
        "context_policy": {
            "recent_event_limit": MAX_RECENT_EVENTS,
            "history_evidence_limit": MAX_HISTORY_EVIDENCE,
        },
    }
    run_id = f"run_{_stable_id(input_snapshot)}"
    return {
        "run_id": run_id,
        "partner_id": partner_id,
        "partner_snapshot": {
            "company_name": partner.get("company_name"),
            "role": partner.get("role"),
            "tags": partner.get("tags", []),
            "profile_status": partner.get("profile_status"),
        },
        "intent": intent,
        "profile_proposals": profile_proposals,
        "profile_write_action": "proposal_only",
        "lead_proposal": {
            "rule_score": rule_score,
            "recommended_action": _recommended_action(intent["stage"]),
            "evidence_ids": [_event_id(event) for event in recent if _event_score(event) > 0],
        },
        "source_refs": source_refs,
        "data_handoff": {
            "mode": "data_agent_contract_v0.1" if data_agent_records is not None else "legacy_news_snapshot",
            "ready_content_count": len(source_refs),
            "blocked_content_refs": blocked_content_refs,
            "feedback_items": feedback_items,
        },
        "data_quality_flags": sorted(quality_flags),
        "needs_human_review": True,
        "audit": {
            "input_snapshot_id": _stable_id(input_snapshot),
            "rule_version": RULE_VERSION,
            "model": "none",
            "tool_calls": [
                "read_partner_snapshot",
                "read_recent_behavior",
                "read_news_snapshot",
                *(["read_data_agent_handoff"] if data_agent_records is not None else []),
            ],
            "token_usage": None,
            "context_policy": "recent 10 events + profile summary + max 5 source refs; no full history",
            "simulated_input": bool(recent) and all(bool(event.get("simulated")) for event in recent),
        },
    }


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
