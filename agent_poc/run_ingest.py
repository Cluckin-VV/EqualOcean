"""Ingest official 亿欧数据 read-only results into local SQLite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_poc.data_store import SQLiteDataStore
from agent_poc.iyiou_data_agent import IYIOUClient


CATEGORY_QUESTIONS = {
    "news": "最新资讯",
    "investment": "今天有哪些融资事件",
    "company": "最新企业信息",
    "policy": "最新政策",
    "bidding": "最新招投标",
    "industry": "行业指标",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest official 亿欧数据 into SQLite")
    parser.add_argument("--category", action="append", choices=sorted(CATEGORY_QUESTIONS), help="可重复指定；默认同步公开可用类别")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--db", type=Path, default=Path(__file__).resolve().parent / "data" / "iyiou_local.sqlite3")
    args = parser.parse_args()

    categories = args.category or ["news", "investment", "company", "policy", "bidding"]
    store = SQLiteDataStore(args.db.resolve())
    store.initialize()
    client = IYIOUClient()
    results = []
    for category in categories:
        result = client.consult(CATEGORY_QUESTIONS[category], limit=max(1, min(args.limit, 100)))
        inserted = store.upsert_source_records(result.get("items", [])) if result["status"] in {"ok", "ok_empty"} else 0
        results.append({"category": category, "status": result["status"], "needs_login": result["needs_login"], "received": len(result.get("items", [])), "inserted_or_updated": inserted})
    print(json.dumps({"db": str(args.db.resolve()), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
