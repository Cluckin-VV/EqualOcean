"""Optional Qwen smoke test; requires a locally configured, rotated API key."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_poc.qwen_client import QwenClient, QwenConfigurationError, QwenRequestError


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Qwen smoke test without persisting the API key")
    parser.add_argument("question", nargs="+", help="要交给 Qwen 的问题")
    args = parser.parse_args()
    client = QwenClient()
    try:
        result = client.complete([
            {"role": "system", "content": "你是海外企业上市信息差研究助手，只回答给定问题，不虚构来源。"},
            {"role": "user", "content": " ".join(args.question)},
        ])
    except (QwenConfigurationError, QwenRequestError) as exc:
        print(json.dumps({"status": "not_run", "message": str(exc), "configuration": client.configuration_status()}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"status": "ok", "model": result["model"], "content": result["content"], "usage": result["usage"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
