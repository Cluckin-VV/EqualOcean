"""Ask an arbitrary customer question using current official 亿欧 evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typing import Any

from agent_poc.iyiou_data_agent import IYIOUClient
from agent_poc.live_operation_agent import render_live_answer_markdown, run_live_consultation
from agent_poc.qwen_client import QwenClient


def answer_grounded_question(
    question: str,
    *,
    limit: int = 5,
    data_client: Any | None = None,
    qwen_client: Any | None = None,
) -> dict[str, Any]:
    """Fetch the matching official category and answer only from those records."""

    clean_question = str(question or "").strip()
    if not clean_question:
        raise ValueError("问题不能为空")
    return run_live_consultation(
        question=clean_question,
        customer={
            "partner_id": "partner_primary_cheng_shaokai",
            "company_name": "程少楷（真实客户提问入口）",
            "role": "企业客户代表",
            "profile_status": "real_question_input",
        },
        behavior_context={
            "simulated": False,
            "source": "current_cli_question",
            "note": "本轮问题作为真实客户咨询记录；不据此自动确认长期画像。",
        },
        limit=max(1, min(int(limit), 10)),
        data_client=data_client or IYIOUClient(),
        qwen_client=qwen_client or QwenClient(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="使用亿欧官网最新证据回答任意企业客户问题")
    parser.add_argument("question", nargs="+", help="客户问题，可自由替换，不限于融资事件")
    parser.add_argument("--limit", type=int, default=5, help="最多使用多少条官网来源，默认 5")
    args = parser.parse_args()
    result = answer_grounded_question(" ".join(args.question), limit=args.limit)
    print(render_live_answer_markdown(result))
    print(json.dumps({
        "status": result["status"],
        "query_type": result.get("query_type"),
        "query_applied": result.get("query_applied"),
        "source_count": result["source_count"],
        "model": result.get("model"),
    }, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "sources_ready_model_not_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
