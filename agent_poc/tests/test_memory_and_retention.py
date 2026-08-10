import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_poc.conversation_memory import compact_conversation, score_message_utility
from agent_poc.retention_policy import plan_jsonl_cleanup


class ConversationMemoryTests(unittest.TestCase):
    def test_compaction_keeps_goal_decision_correction_and_recent_context(self):
        messages = [
            {
                "message_id": "m-old-chat",
                "role": "user",
                "content": "你好，今天心情不错。",
                "created_at": "2026-07-01T09:00:00+08:00",
            },
            {
                "message_id": "m-goal",
                "role": "user",
                "content": "我们的目标客户是计划在美股上市的海外企业。",
                "created_at": "2026-07-01T09:01:00+08:00",
                "message_type": "goal",
            },
            {
                "message_id": "m-decision",
                "role": "assistant",
                "content": "决定先使用官网只读数据，不绕过登录权限。",
                "created_at": "2026-07-02T09:00:00+08:00",
                "message_type": "decision",
            },
            {
                "message_id": "m-correction",
                "role": "user",
                "content": "修正：Nasdaq 是目标客户，不要再写成普通模拟用户。",
                "created_at": "2026-07-03T09:00:00+08:00",
                "message_type": "correction",
            },
            {
                "message_id": "m-recent",
                "role": "user",
                "content": "请查今天的融资事件。",
                "created_at": "2026-08-06T09:00:00+08:00",
            },
            {
                "message_id": "m-duplicate",
                "role": "assistant",
                "content": "请查今天的融资事件。",
                "created_at": "2026-08-06T09:01:00+08:00",
            },
        ]

        result = compact_conversation(messages, recent_limit=2)

        kept_ids = result["source_message_ids"]
        self.assertIn("m-goal", kept_ids)
        self.assertIn("m-decision", kept_ids)
        self.assertIn("m-correction", kept_ids)
        self.assertIn("m-recent", kept_ids)
        self.assertNotIn("m-old-chat", kept_ids)
        self.assertGreaterEqual(result["dropped_message_count"], 1)
        self.assertGreater(score_message_utility(messages[1]), score_message_utility(messages[0]))


class RetentionPolicyTests(unittest.TestCase):
    def test_cleanup_plan_deletes_only_expired_non_held_records(self):
        now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.jsonl"
            rows = [
                {"message_id": "recent", "created_at": "2026-08-01T12:00:00+00:00"},
                {"message_id": "expired", "created_at": "2026-07-01T12:00:00+00:00"},
                {"message_id": "held", "created_at": "2026-07-01T12:00:00+00:00", "legal_hold": True},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            plan = plan_jsonl_cleanup(path, now=now, retention_days=15)

            self.assertEqual(plan["delete_ids"], ["expired"])
            self.assertEqual(plan["keep_ids"], ["recent", "held"])
            self.assertEqual(plan["held_ids"], ["held"])
        self.assertFalse(path.exists())
