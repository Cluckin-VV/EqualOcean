"""Dry-run-first retention policy for session JSONL logs."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _record_id(record: dict[str, Any], line_number: int) -> str:
    return str(record.get("message_id") or record.get("event_id") or record.get("run_id") or record.get("record_id") or f"line-{line_number}")


def plan_jsonl_cleanup(
    path: str | Path,
    now: datetime | None = None,
    retention_days: int = 15,
) -> dict[str, Any]:
    """Create a deletion plan without changing the file."""

    target = Path(path)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(days=retention_days)
    delete_ids: list[str] = []
    keep_ids: list[str] = []
    held_ids: list[str] = []
    unknown_timestamp_ids: list[str] = []
    invalid_line_numbers: list[int] = []
    rows = target.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(rows, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            invalid_line_numbers.append(line_number)
            continue
        if not isinstance(record, dict):
            invalid_line_numbers.append(line_number)
            continue
        item_id = _record_id(record, line_number)
        retention_class = str(record.get("retention_class") or "").lower()
        if record.get("legal_hold") is True or retention_class in {"audit", "legal_hold", "source_snapshot"}:
            held_ids.append(item_id)
            keep_ids.append(item_id)
            continue
        timestamp = next((_parse_timestamp(record.get(field)) for field in ("logged_at", "created_at", "timestamp", "updated_at") if record.get(field)), None)
        if timestamp is None:
            unknown_timestamp_ids.append(item_id)
            keep_ids.append(item_id)
        elif timestamp < cutoff:
            delete_ids.append(item_id)
        else:
            keep_ids.append(item_id)
    return {
        "path": str(target),
        "retention_days": retention_days,
        "cutoff": cutoff.isoformat(),
        "record_count": len(rows),
        "delete_ids": delete_ids,
        "keep_ids": keep_ids,
        "held_ids": held_ids,
        "unknown_timestamp_ids": unknown_timestamp_ids,
        "invalid_line_numbers": invalid_line_numbers,
        "dry_run": True,
    }


def apply_jsonl_cleanup(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply a previously generated plan atomically.

    Only IDs explicitly listed in ``delete_ids`` are removed. Invalid JSON and
    records without timestamps stay in the file.
    """

    target = Path(str(plan["path"]))
    delete_ids = set(plan.get("delete_ids") or [])
    if not delete_ids:
        return {"applied": True, "deleted_count": 0, "path": str(target)}
    kept_lines: list[str] = []
    deleted_count = 0
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            kept_lines.append(line)
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            kept_lines.append(line)
            continue
        if not isinstance(record, dict):
            kept_lines.append(line)
            continue
        item_id = _record_id(record, line_number)
        if item_id in delete_ids:
            deleted_count += 1
        else:
            kept_lines.append(line)
    fd, temp_name = tempfile.mkstemp(prefix=f"{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(kept_lines))
            if kept_lines:
                handle.write("\n")
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return {"applied": True, "deleted_count": deleted_count, "path": str(target)}


__all__ = ["apply_jsonl_cleanup", "plan_jsonl_cleanup"]
