import unittest

from agent_poc.behavior_agent import analyze_partner, judge_intent, propose_profile_changes, read_json
from agent_poc.iyiou_data_agent import IYIOUClient, classify_consultation


class BehaviorAgentTests(unittest.TestCase):
    def test_explicit_material_request_reaches_evaluating(self):
        events = [
            {
                "event_id": "evt-1",
                "partner_id": "partner-1",
                "event_type": "article_view",
                "object_type": "news",
                "object_id": "news-1",
                "created_at": "2026-08-01T10:00:00+08:00",
                "topic": "AI硬件",
                "simulated": True,
            },
            {
                "event_id": "evt-2",
                "partner_id": "partner-1",
                "event_type": "material_request",
                "object_type": "topic",
                "object_id": "ai-hardware",
                "created_at": "2026-08-02T10:00:00+08:00",
                "topic": "AI硬件",
                "simulated": True,
            },
        ]

        result = judge_intent(events)

        self.assertEqual(result["stage"], "评估")
        self.assertIn("evt-2", result["evidence_ids"])
        self.assertGreaterEqual(result["confidence"], 0.7)

    def test_one_view_does_not_create_stable_profile(self):
        events = [
            {
                "event_id": "evt-1",
                "partner_id": "partner-1",
                "event_type": "article_view",
                "object_type": "news",
                "object_id": "news-1",
                "created_at": "2026-08-01T10:00:00+08:00",
                "topic": "AI硬件",
                "simulated": True,
            }
        ]

        proposals = propose_profile_changes(events)

        self.assertEqual(proposals, [])

    def test_analysis_keeps_source_warning_and_never_auto_writes_profile(self):
        partner = {
            "partner_id": "partner-1",
            "company_name": "Nasdaq",
            "role": "投资研究与战略团队",
            "tags": ["投资方", "资本市场"],
            "profile_confidence": 0.95,
            "profile_status": "initial_simulated",
        }
        events = [
            {
                "event_id": "evt-1",
                "partner_id": "partner-1",
                "event_type": "report_download",
                "object_type": "news",
                "object_id": "news-1",
                "created_at": "2026-08-01T10:00:00+08:00",
                "topic": "AI硬件",
                "simulated": True,
            },
            {
                "event_id": "evt-2",
                "partner_id": "partner-1",
                "event_type": "subscription_request",
                "object_type": "topic",
                "object_id": "ai-hardware",
                "created_at": "2026-08-02T10:00:00+08:00",
                "topic": "AI硬件",
                "simulated": True,
            },
        ]
        news = [
            {
                "report_id": "news-1",
                "title": "��乱码标题",
                "published_at": "2026-07-01 17:20:10",
                "source_url": "https://example.com/news-1",
                "source": "真实新闻快照",
                "verification_status": "blocked",
                "semantic_matching_status": "blocked_pending_clean_source",
                "data_quality_flags": ["replacement_character_detected"],
            }
        ]

        result = analyze_partner(partner, events, news)

        self.assertTrue(result["needs_human_review"])
        self.assertIn("replacement_character_detected", result["data_quality_flags"])
        self.assertEqual(result["profile_write_action"], "proposal_only")
        self.assertEqual(result["intent"]["stage"], "评估")
        self.assertIn("evt-2", result["intent"]["evidence_ids"])

    def test_context_limits_source_references_and_empty_input_is_not_simulated(self):
        partner = {
            "partner_id": "partner-1",
            "company_name": "Demo",
            "profile_status": "initial_simulated",
        }
        events = [
            {
                "event_id": f"evt-{index}",
                "partner_id": "partner-1",
                "event_type": "article_view",
                "object_type": "news",
                "object_id": f"news-{index}",
                "created_at": f"2026-08-0{index}T10:00:00+08:00",
                "simulated": True,
            }
            for index in range(1, 7)
        ]
        news = [
            {
                "report_id": f"news-{index}",
                "source_url": f"https://example.com/{index}",
                "source": "test",
                "verification_status": "pending",
                "semantic_matching_status": "ready_for_review",
                "data_quality_flags": [],
            }
            for index in range(1, 7)
        ]

        result = analyze_partner(partner, events, news)

        self.assertEqual(len(result["source_refs"]), 5)
        self.assertTrue(result["audit"]["simulated_input"])

        empty_result = analyze_partner(partner, [], [])
        self.assertFalse(empty_result["audit"]["simulated_input"])

    def test_data_agent_handoff_blocks_stale_translation_and_returns_feedback(self):
        partner = {
            "partner_id": "partner-1",
            "company_name": "Nasdaq",
            "role": "投资研究与战略团队",
            "profile_status": "initial_simulated",
        }
        events = [
            {
                "event_id": "evt-download",
                "partner_id": "partner-1",
                "event_type": "report_download",
                "object_type": "news",
                "object_id": "news-stale",
                "created_at": "2026-08-02T10:00:00+08:00",
                "topic": "中国AI硬件投资",
                "simulated": True,
            }
        ]
        news = [
            {
                "report_id": "news-stale",
                "source_url": "https://example.com/news-stale",
                "source": "test",
                "verification_status": "pending",
                "semantic_matching_status": "ready_for_review",
                "data_quality_flags": [],
            }
        ]
        handoff = [
            {
                "content_id": "news-stale",
                "source_url": "https://example.com/news-stale",
                "company_ids": ["company-demo"],
                "company_match_status": "matched",
                "change_type": "event_update",
                "quality_status": "passed",
                "translation_status": "pending",
                "dedup_status": "unique",
                "publish_status": "candidate",
                "data_version": "data-v2",
                "content_version": "content-v2",
                "quality_flags": ["original_updated_translation_pending"],
            }
        ]

        result = analyze_partner(partner, events, news, data_agent_records=handoff)

        self.assertEqual(result["source_refs"], [])
        self.assertEqual(result["data_handoff"]["blocked_content_refs"][0]["content_id"], "news-stale")
        self.assertIn("translation_not_ready", result["data_quality_flags"])
        self.assertEqual(result["data_handoff"]["feedback_items"][0]["action"], "reprocess_content")

    def test_data_agent_handoff_allows_ready_content_and_keeps_versions(self):
        partner = {
            "partner_id": "partner-1",
            "company_name": "Nasdaq",
            "role": "投资研究与战略团队",
            "profile_status": "initial_simulated",
        }
        events = [
            {
                "event_id": "evt-ready",
                "partner_id": "partner-1",
                "event_type": "article_view",
                "object_type": "news",
                "object_id": "news-ready",
                "created_at": "2026-08-02T10:00:00+08:00",
                "topic": "中国AI硬件投资",
                "simulated": True,
            }
        ]
        news = [
            {
                "report_id": "news-ready",
                "source_url": "https://legacy.example.com/news-ready",
                "source": "test",
                "verification_status": "pending",
                "semantic_matching_status": "ready_for_review",
                "data_quality_flags": [],
            }
        ]
        handoff = [
            {
                "content_id": "news-ready",
                "source_url": "https://example.com/news-ready",
                "company_ids": ["company-demo"],
                "company_match_status": "matched",
                "change_type": "new",
                "quality_status": "passed",
                "translation_status": "passed",
                "dedup_status": "unique",
                "publish_status": "candidate",
                "data_version": "data-v3",
                "content_version": "content-v1",
                "quality_flags": [],
            }
        ]

        result = analyze_partner(partner, events, news, data_agent_records=handoff)

        self.assertEqual(len(result["source_refs"]), 1)
        self.assertEqual(result["source_refs"][0]["source_url"], "https://example.com/news-ready")
        self.assertEqual(result["source_refs"][0]["data_version"], "data-v3")
        self.assertEqual(result["source_refs"][0]["content_version"], "content-v1")
        self.assertEqual(result["data_handoff"]["blocked_content_refs"], [])

    def test_consultation_classifier_routes_investment_and_news_questions(self):
        self.assertEqual(classify_consultation("请查一下今天有哪些融资事件"), "investment")
        self.assertEqual(classify_consultation("纳斯达克最近关注哪些行业资讯"), "news")
        self.assertEqual(classify_consultation("看一下人工智能行业指标"), "industry")

    def test_live_data_client_normalizes_official_news_and_investment_records(self):
        payloads = {
            "/spa/news/defaultList": {
                "code": 200,
                "data": {
                    "dataList": {
                        "records": [
                            {
                                "reportId": "news-1",
                                "title": "AI芯片企业完成融资",
                                "summary": "完成新一轮融资。",
                                "pubTime": "2026-08-06 10:00:00",
                                "source": "亿欧数据",
                                "sourceUrl": "https://data.iyiou.com/intelligence/details/news-1",
                                "reportTypeStr": "融资",
                            }
                        ],
                        "total": 1,
                    }
                },
            },
            "/spa/invest/defaultList": {
                "code": 200,
                "data": {
                    "dataList": {
                        "records": [
                            {
                                "investId": "invest-1",
                                "briefName": "AI芯片企业",
                                "investTime": "2026-08-06",
                                "investRoundDesc": "A轮",
                                "investAmount": "1亿",
                                "investCurrencyDesc": "人民币",
                                "industryName": "人工智能",
                            }
                        ],
                        "total": 1,
                    }
                },
            },
        }

        def fake_transport(url, headers):
            path = url.split("https://apidata.iyiou.com", 1)[1].split("?", 1)[0]
            return payloads[path]

        client = IYIOUClient(transport=fake_transport)

        news = client.consult("AI资讯", limit=5)
        investments = client.consult("最新融资事件", limit=5)

        self.assertEqual(news["status"], "ok")
        self.assertEqual(news["query_type"], "news")
        self.assertEqual(news["items"][0]["record_id"], "news-1")
        self.assertEqual(news["items"][0]["record_type"], "news")
        self.assertEqual(investments["items"][0]["record_id"], "invest-1")
        self.assertEqual(investments["items"][0]["record_type"], "investment")
        self.assertEqual(investments["items"][0]["attributes"]["industry"], "人工智能")

    def test_live_data_client_reports_login_boundary_instead_of_faking_search(self):
        def fake_transport(url, headers):
            return {"code": 401, "message": "请登录", "success": False}

        client = IYIOUClient(transport=fake_transport)

        result = client.consult("搜索人工智能行业研究报告")

        self.assertEqual(result["status"], "needs_auth")
        self.assertTrue(result["needs_login"])
        self.assertEqual(result["items"], [])

    def test_live_data_client_uses_official_home_fallback_for_login_gated_bidding(self):
        def fake_transport(url, headers):
            path = url.split("https://apidata.iyiou.com", 1)[1].split("?", 1)[0]
            if path == "/spa/bidding/getBiddingDefaultList":
                return {"code": 401, "message": "请登录", "success": False}
            if path == "/spa/home/data":
                return {
                    "code": 200,
                    "data": {
                        "biddingList": [
                            {
                                "biddingId": "bid-1",
                                "title": "AI设备采购公告",
                                "publishDate": "2026-08-06",
                                "source": "亿欧数据",
                                "bidUrl": "https://data.iyiou.com/intelligence/biddetails/bid-1",
                            }
                        ]
                    },
                }
            raise AssertionError(path)

        result = IYIOUClient(transport=fake_transport).consult("最新招投标", limit=5)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["items"][0]["record_type"], "bidding")
        self.assertEqual(result["source"]["api_endpoint"], "/spa/home/data")

    def test_customer_registry_keeps_nasdaq_target_and_empty_primary_slot(self):
        partners = read_json("agent_poc/data/partners.json")
        by_id = {partner["partner_id"]: partner for partner in partners}

        self.assertEqual(by_id["partner_demo_nasdaq"]["company_name"], "Nasdaq")
        self.assertEqual(by_id["partner_demo_nasdaq"]["profile_status"], "target_customer")
        self.assertEqual(by_id["partner_primary_cheng_shaokai"]["company_name"], "程少楷")
        self.assertEqual(by_id["partner_primary_cheng_shaokai"]["profile_status"], "reserved_empty")
        self.assertEqual(by_id["partner_primary_cheng_shaokai"]["confirmed_interests"], [])


if __name__ == "__main__":
    unittest.main()
