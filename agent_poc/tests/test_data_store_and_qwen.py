import tempfile
import unittest
from pathlib import Path

from agent_poc.data_store import SQLiteDataStore
from agent_poc.qwen_client import QwenClient, QwenConfigurationError


class SQLiteDataStoreTests(unittest.TestCase):
    def test_source_records_are_idempotent_on_reingest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteDataStore(Path(temp_dir) / "iyiou.sqlite3")
            store.initialize()
            record = {
                "record_type": "investment",
                "record_id": "invest-1",
                "title": "AI芯片企业融资",
                "summary": "完成 A 轮融资",
                "published_at": "2026-08-06",
                "source": "亿欧数据",
                "source_url": "https://data.iyiou.com/example",
                "official_source": "data.iyiou.com",
                "attributes": {"amount": "1亿", "industry": "人工智能"},
                "raw_fields": {"investId": "invest-1"},
            }

            store.upsert_source_records([record])
            store.upsert_source_records([{**record, "summary": "更新后的摘要"}])

            rows = store.list_source_records(record_type="investment")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["summary"], "更新后的摘要")


class QwenClientTests(unittest.TestCase):
    def test_default_model_is_qwen_flash(self):
        client = QwenClient(api_key="unit-test-placeholder")

        self.assertEqual(client.model, "qwen-flash")

    def test_missing_key_is_reported_without_network_call(self):
        client = QwenClient(api_key="")

        with self.assertRaises(QwenConfigurationError):
            client.complete([{"role": "user", "content": "test"}])

    def test_client_reads_openai_compatible_response_without_logging_key(self):
        seen = {}

        def fake_transport(url, headers, body):
            seen["url"] = url
            seen["headers"] = dict(headers)
            seen["body"] = body
            return {
                "id": "completion-1",
                "model": "qwen-plus",
                "choices": [{"message": {"role": "assistant", "content": "{\"ok\":true}"}}],
            }

        client = QwenClient(api_key="unit-test-placeholder", transport=fake_transport)
        result = client.complete([{"role": "user", "content": "test"}])

        self.assertEqual(result["content"], "{\"ok\":true}")
        self.assertIn("/chat/completions", seen["url"])
        self.assertEqual(seen["headers"]["Authorization"], "Bearer unit-test-placeholder")
        self.assertNotIn("unit-test-placeholder", result)
