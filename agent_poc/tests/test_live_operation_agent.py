import json
import tempfile
import unittest
from pathlib import Path

from agent_poc.iyiou_data_agent import normalize_records
from agent_poc.live_operation_agent import (
    build_live_help_messages,
    render_live_answer_markdown,
    run_live_consultation,
)
from agent_poc.run_demo import load_news_input


class OfficialLinkTests(unittest.TestCase):
    def test_investment_without_source_link_uses_openable_company_detail_page(self):
        payload = {
            "code": 200,
            "data": {
                "dataList": {
                    "records": [
                        {
                            "investId": "invest-1",
                            "comId": "company-1",
                            "briefName": "AI基础设施企业",
                            "briefIntro": "提供AI算力基础设施",
                            "investTime": "2026-08-10",
                            "investRoundDesc": "A轮",
                            "sourceLink": "",
                        }
                    ]
                }
            },
        }

        item = normalize_records("investment", payload, limit=1)[0]

        self.assertEqual(
            item["source_url"],
            "https://data.iyiou.com/company/details/company-1/profile?source=iyiou.trz",
        )
        self.assertEqual(item["link_origin"], "official_company_profile")

    def test_demo_can_run_without_private_excel_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(load_news_input(Path(temp_dir)), [])

    def test_demo_uses_public_snapshot_when_private_excel_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "agent_poc" / "data"
            data_dir.mkdir(parents=True)
            sample = [{"report_id": "news-1", "title": "公开样例"}]
            (data_dir / "news_snapshot_poc.json").write_text(
                json.dumps(sample, ensure_ascii=False), encoding="utf-8"
            )

            self.assertEqual(load_news_input(root), sample)


class LiveOperationAgentTests(unittest.TestCase):
    def setUp(self):
        self.partner = {
            "partner_id": "partner_demo_nasdaq",
            "company_name": "Nasdaq",
            "role": "投资研究与战略团队",
        }
        self.behavior = {"stage": "评估", "score": 22, "evidence_ids": ["evt-1"]}
        self.item = {
            "record_type": "investment",
            "record_id": "invest-1",
            "title": "AI基础设施企业",
            "summary": "完成A轮融资",
            "published_at": "2026-08-10",
            "source": "亿欧数据",
            "source_url": "https://data.iyiou.com/company/details/company-1/profile?source=iyiou.trz",
            "official_source": "data.iyiou.com",
            "link_origin": "official_company_profile",
            "attributes": {"round": "A轮", "amount": "1亿元", "industry": "人工智能"},
        }

    def test_prompt_asks_what_help_and_contains_only_supplied_source_evidence(self):
        messages = build_live_help_messages(
            customer=self.partner,
            behavior_context=self.behavior,
            question="最新融资事件对拟在美股上市的海外企业有什么帮助",
            source_records=[self.item],
        )

        self.assertIn("有什么帮助", messages[0]["content"])
        self.assertIn("不得补造", messages[0]["content"])
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["source_records"][0]["record_id"], "invest-1")
        self.assertEqual(payload["source_records"][0]["source_url"], self.item["source_url"])

    def test_live_consultation_keeps_sources_outside_model_answer(self):
        class FakeDataClient:
            def consult(inner_self, question, limit):
                return {
                    "query": question,
                    "query_type": "investment",
                    "status": "ok",
                    "items": [self.item],
                    "retrieved_at": "2026-08-10T08:00:00+00:00",
                    "source": {"site": "data.iyiou.com", "official_read_only": True},
                }

        class FakeQwenClient:
            model = "qwen-flash"

            def complete(inner_self, messages, **kwargs):
                self.assertIn(self.item["source_url"], messages[1]["content"])
                return {
                    "content": "这条融资记录可帮助客户观察资本偏好，但仍需进一步核验。",
                    "model": "qwen-flash",
                    "usage": {"total_tokens": 100},
                    "response_id": "response-1",
                }

        result = run_live_consultation(
            question="最新融资事件对拟在美股上市的海外企业有什么帮助",
            customer=self.partner,
            behavior_context=self.behavior,
            limit=5,
            data_client=FakeDataClient(),
            qwen_client=FakeQwenClient(),
        )
        markdown = render_live_answer_markdown(result)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["sources"][0]["source_url"], self.item["source_url"])
        self.assertIn(self.item["source_url"], markdown)
        self.assertIn("人工审核", markdown)


if __name__ == "__main__":
    unittest.main()
