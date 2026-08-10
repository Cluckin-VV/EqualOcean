"""Run the local behavior-analysis POC against the supplied real news export."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Support both `python -m agent_poc.run_demo` and `python agent_poc/run_demo.py`.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_poc.behavior_agent import analyze_partner, read_json, read_jsonl, read_xlsx_news, write_json


def load_news_input(root: Path) -> list[dict]:
    """Use the private Excel snapshot when present; keep the public POC runnable without it."""

    news_path = root / "intelligence_export_100.xlsx"
    if news_path.exists():
        return read_xlsx_news(news_path, limit=100)
    public_snapshot = root / "agent_poc" / "data" / "news_snapshot_poc.json"
    return read_json(public_snapshot) if public_snapshot.exists() else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the EqualOcean subscription operations-agent POC")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--partner-id", default="partner_demo_nasdaq")
    args = parser.parse_args()

    root = args.root.resolve()
    partners = read_json(root / "agent_poc" / "data" / "partners.json")
    events = read_jsonl(root / "agent_poc" / "data" / "simulated_behavior.jsonl")
    data_agent_records = read_json(root / "agent_poc" / "data" / "data_agent_handoff.json")
    news = load_news_input(root)
    partner = next(item for item in partners if item.get("partner_id") == args.partner_id)
    partner_events = [event for event in events if event.get("partner_id") == args.partner_id]
    result = analyze_partner(partner, events, news, data_agent_records=data_agent_records)

    output_dir = root / "agent_poc" / "output"
    write_json(output_dir / "news_snapshot_100.json", news)
    write_json(output_dir / "behavior_analysis_run.json", result)
    log_entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "run_id": result["run_id"],
        "partner_id": result["partner_id"],
        "rule_version": result["audit"]["rule_version"],
        "event_count": len(partner_events),
        "news_count": len(news),
        "needs_human_review": result["needs_human_review"],
        "data_quality_flags": result["data_quality_flags"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "agent_run_log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(json.dumps({
        "run_id": result["run_id"],
        "customer": result["partner_snapshot"],
        "simulated_event_count": len(partner_events),
        "behavior_score": result["lead_proposal"]["rule_score"],
        "behavior_stage": result["intent"]["stage"],
        "judgment_confidence": result["intent"]["confidence"],
        "evidence_ids": result["intent"]["evidence_ids"],
        "ready_content_count": result["data_handoff"]["ready_content_count"],
        "blocked_content_count": len(result["data_handoff"]["blocked_content_refs"]),
        "data_quality_flags": result["data_quality_flags"],
        "needs_human_review": result["needs_human_review"],
        "output_dir": str(output_dir),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
