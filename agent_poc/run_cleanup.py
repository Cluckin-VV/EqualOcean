"""Inspect and optionally apply the 15-day JSONL retention policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_poc.retention_policy import apply_jsonl_cleanup, plan_jsonl_cleanup


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or apply local session-log cleanup")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent / "output")
    parser.add_argument("--days", type=int, default=15)
    parser.add_argument("--apply", action="store_true", help="actually rewrite eligible session JSONL files")
    args = parser.parse_args()

    root = args.root.resolve()
    results = []
    for path in sorted(root.rglob("*.jsonl")) if root.exists() else []:
        if path.name == "agent_run_log.jsonl":
            results.append({"path": str(path), "status": "protected_audit_log", "reason": "审计日志默认不按 15 天原始会话策略删除"})
            continue
        plan = plan_jsonl_cleanup(path, retention_days=max(1, args.days))
        if args.apply:
            result = apply_jsonl_cleanup(plan)
            results.append({**plan, **result, "dry_run": False})
        else:
            results.append(plan)
    print(json.dumps({"root": str(root), "apply": args.apply, "files": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
