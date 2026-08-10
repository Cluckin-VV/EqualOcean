"""Run the minimal simulated-customer + live-data + Qwen operations Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_poc.behavior_agent import EVENT_WEIGHTS, judge_intent, read_json, read_jsonl, write_json
from agent_poc.iyiou_data_agent import IYIOUClient
from agent_poc.live_operation_agent import render_live_answer_markdown, run_live_consultation
from agent_poc.qwen_client import QwenClient


DEFAULT_QUESTION = "最新融资事件对拟在美股上市的海外企业有什么帮助"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the minimal live EqualOcean operations Agent")
    parser.add_argument("question", nargs="*", help="咨询问题；默认询问最新融资事件有什么帮助")
    parser.add_argument("--limit", type=int, default=5, help="最多使用多少条官网来源，默认 5")
    parser.add_argument("--partner-id", default="partner_demo_nasdaq")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    root = args.root.resolve()
    question = " ".join(args.question).strip() or DEFAULT_QUESTION
    partners = read_json(root / "agent_poc" / "data" / "partners.json")
    events = read_jsonl(root / "agent_poc" / "data" / "simulated_behavior.jsonl")
    customer = next(item for item in partners if item.get("partner_id") == args.partner_id)
    customer_events = [event for event in events if event.get("partner_id") == args.partner_id]
    intent = judge_intent(customer_events)
    behavior_context = {
        "simulated": True,
        "event_count": len(customer_events),
        "score": sum(EVENT_WEIGHTS.get(str(event.get("event_type") or ""), 0) for event in customer_events),
        "stage": intent["stage"],
        "confidence": intent["confidence"],
        "evidence_ids": intent["evidence_ids"],
    }
    result = run_live_consultation(
        question=question,
        customer=customer,
        behavior_context=behavior_context,
        limit=max(1, min(args.limit, 10)),
        data_client=IYIOUClient(),
        qwen_client=QwenClient(),
    )
    output_dir = root / "agent_poc" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "live_operation_answer.json"
    markdown_path = output_dir / "live_operation_answer.md"
    write_json(json_path, result)
    markdown = render_live_answer_markdown(result)
    markdown_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(json.dumps({
        "status": result["status"],
        "model": result.get("model"),
        "source_count": result["source_count"],
        "json_output": str(json_path),
        "markdown_output": str(markdown_path),
    }, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "sources_ready_model_not_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
