"""Run one read-only consultation against the official 亿欧数据 API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_poc.behavior_agent import write_json
from agent_poc.iyiou_data_agent import IYIOUClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a read-only 亿欧数据 consultation")
    parser.add_argument("question", nargs="+", help="中文咨询，例如：今天有哪些融资事件")
    parser.add_argument("--limit", type=int, default=10, help="最多返回多少条证据，默认 10")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    question = " ".join(args.question).strip()
    result = IYIOUClient().consult(question, limit=max(1, min(args.limit, 50)))
    output_path = args.root.resolve() / "agent_poc" / "output" / "live_consultation.json"
    write_json(output_path, result)
    print(json.dumps({
        "query": result["query"],
        "query_type": result["query_type"],
        "status": result["status"],
        "needs_login": result["needs_login"],
        "item_count": len(result["items"]),
        "source": result["source"],
        "output_path": str(output_path),
    }, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "ok_empty", "needs_auth"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
