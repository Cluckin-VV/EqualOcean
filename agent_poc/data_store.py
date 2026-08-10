"""Small local SQLite store for official-source records and compact memory."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_records (
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    official_source TEXT NOT NULL DEFAULT '',
    attributes_json TEXT NOT NULL DEFAULT '{}',
    raw_fields_json TEXT NOT NULL DEFAULT '{}',
    retrieved_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (record_type, record_id)
);
CREATE INDEX IF NOT EXISTS idx_source_records_published ON source_records (record_type, published_at DESC);
CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT '',
    utility_score INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
CREATE TABLE IF NOT EXISTS conversation_memory (
    customer_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    memory_version TEXT NOT NULL,
    memory_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (customer_id, conversation_id)
);
"""


class SQLiteDataStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    def upsert_customer(self, customer_id: str, company_name: str, role: str = "", status: str = "active") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO customers (customer_id, company_name, role, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(customer_id) DO UPDATE SET company_name=excluded.company_name,
                   role=excluded.role, status=excluded.status, updated_at=excluded.updated_at""",
                (customer_id, company_name, role, status, now, now),
            )

    def upsert_source_records(self, records: Iterable[dict[str, Any]], retrieved_at: str | None = None) -> int:
        now = retrieved_at or datetime.now(timezone.utc).isoformat()
        count = 0
        with self._connection() as connection:
            for record in records:
                record_type = str(record.get("record_type") or "unknown")
                record_id = str(record.get("record_id") or "")
                if not record_id:
                    continue
                connection.execute(
                    """INSERT INTO source_records
                       (record_type, record_id, title, summary, published_at, source, source_url,
                        official_source, attributes_json, raw_fields_json, retrieved_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(record_type, record_id) DO UPDATE SET
                       title=excluded.title, summary=excluded.summary, published_at=excluded.published_at,
                       source=excluded.source, source_url=excluded.source_url, official_source=excluded.official_source,
                       attributes_json=excluded.attributes_json, raw_fields_json=excluded.raw_fields_json,
                       retrieved_at=excluded.retrieved_at, updated_at=excluded.updated_at""",
                    (
                        record_type,
                        record_id,
                        str(record.get("title") or ""),
                        str(record.get("summary") or ""),
                        str(record.get("published_at") or ""),
                        str(record.get("source") or ""),
                        str(record.get("source_url") or ""),
                        str(record.get("official_source") or ""),
                        json.dumps(record.get("attributes") or {}, ensure_ascii=False),
                        json.dumps(record.get("raw_fields") or {}, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                count += 1
        return count

    def list_source_records(self, record_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM source_records"
        params: list[Any] = []
        if record_type:
            query += " WHERE record_type = ?"
            params.append(record_type)
        query += " ORDER BY published_at DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["attributes"] = json.loads(item.pop("attributes_json") or "{}")
            item["raw_fields"] = json.loads(item.pop("raw_fields_json") or "{}")
            result.append(item)
        return result

    def count_source_records(self, record_type: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM source_records"
        params: list[Any] = []
        if record_type:
            query += " WHERE record_type = ?"
            params.append(record_type)
        with self._connection() as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def save_memory(self, customer_id: str, conversation_id: str, memory: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO conversation_memory (customer_id, conversation_id, memory_version, memory_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(customer_id, conversation_id) DO UPDATE SET memory_version=excluded.memory_version,
                   memory_json=excluded.memory_json, updated_at=excluded.updated_at""",
                (customer_id, conversation_id, str(memory.get("memory_version") or "unknown"), json.dumps(memory, ensure_ascii=False), now),
            )


__all__ = ["SQLiteDataStore"]
