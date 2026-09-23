import unittest

from tools import build_innovation_listing_candidates as builder


class InnovationListingCandidateBuilderTests(unittest.TestCase):
    def watchlist(self):
        return {
            "asOf": "2026-09-21",
            "brokers": ["中信证券", "中金公司"],
            "policyThemes": ["人工智能", "具身智能", "量子科技"],
            "projects": [
                {"company": "已跟踪科技股份有限公司", "broker": "中信证券"},
            ],
        }

    def payload(self):
        return {
            "generatedAt": "2026-09-22T08:00:00+00:00",
            "articles": [
                {
                    "id": "a1",
                    "sourceId": "innovation-listing-broker-01",
                    "title": "新锐量子科技股份有限公司启动科创板IPO辅导",
                    "summary": "中信证券担任辅导机构，项目聚焦量子科技。",
                    "publishedAt": "2026-09-22",
                    "sector": "量子科技",
                    "source": {
                        "name": "公开发现",
                        "url": "https://example.com/a1",
                        "level": "待交叉验证",
                    },
                },
                {
                    "id": "a2",
                    "sourceId": "innovation-listing-policy-01",
                    "title": "中金公司辅导「灵虎机器人」启动A股IPO辅导",
                    "summary": "灵虎机器人聚焦具身智能，上市板块尚未公开锁定。",
                    "publishedAt": "2026-09-21",
                    "sector": "智能机器人",
                    "source": {
                        "name": "监管公告镜像",
                        "url": "https://example.com/a2",
                        "level": "监管文件",
                    },
                },
                {
                    "id": "a3",
                    "sourceId": "innovation-listing-a-plus-h-02",
                    "title": "中金公司推进星海生物科技股份有限公司A+H上市辅导",
                    "summary": "公司同步关注港交所路径与A股IPO。",
                    "publishedAt": "2026-09-20",
                    "sector": "生物医药",
                    "source": {
                        "name": "媒体",
                        "url": "https://example.com/a3",
                        "level": "待交叉验证",
                    },
                },
                {
                    "id": "a4",
                    "sourceId": "innovation-listing-projects-01",
                    "title": "已跟踪科技股份有限公司辅导进展更新",
                    "summary": "中信证券持续辅导。",
                    "publishedAt": "2026-09-22",
                    "sector": "人工智能",
                    "company": "已跟踪科技股份有限公司",
                    "source": {
                        "name": "公开发现",
                        "url": "https://example.com/a4",
                        "level": "待交叉验证",
                    },
                },
                {
                    "id": "a5",
                    "sourceId": "other-source",
                    "title": "噪声公司股份有限公司启动IPO辅导",
                    "summary": "中信证券担任辅导机构。",
                    "publishedAt": "2026-09-22",
                    "sector": "人工智能",
                    "source": {
                        "name": "其他",
                        "url": "https://example.com/a5",
                        "level": "监管文件",
                    },
                },
            ],
        }

    def test_builds_only_new_projects_from_discovery_sources(self):
        snapshot = builder.build_candidate_snapshot(self.payload(), self.watchlist(), {})
        names = {item["company"] for item in snapshot["candidates"]}
        self.assertIn("新锐量子科技股份有限公司", names)
        self.assertIn("灵虎机器人", names)
        self.assertIn("星海生物科技股份有限公司", names)
        self.assertNotIn("已跟踪科技股份有限公司", names)
        self.assertNotIn("噪声公司股份有限公司", names)
        self.assertEqual(snapshot["pendingCount"], 3)

    def test_preserves_broker_route_theme_and_ah_signals(self):
        snapshot = builder.build_candidate_snapshot(self.payload(), self.watchlist(), {})
        by_name = {item["company"]: item for item in snapshot["candidates"]}

        quantum = by_name["新锐量子科技股份有限公司"]
        self.assertEqual(quantum["broker"], "中信证券")
        self.assertEqual(quantum["route"], "STAR")
        self.assertIn("量子科技", quantum["fifteenthTags"])
        self.assertEqual(quantum["evidenceClass"], "discovery-only")

        robot = by_name["灵虎机器人"]
        self.assertEqual(robot["broker"], "中金公司")
        self.assertEqual(robot["route"], "A-share-TBD")
        self.assertIn("具身智能", robot["fifteenthTags"])
        self.assertEqual(robot["evidenceClass"], "primary-backed")
        self.assertGreaterEqual(robot["primaryEvidenceCount"], 1)

        ah = by_name["星海生物科技股份有限公司"]
        self.assertEqual(ah["capitalMarketPath"], "A+H")

    def test_portfolio_mature_source_enters_review_without_inventing_broker(self):
        payload = {
            "generatedAt": "2026-09-22T08:00:00+00:00",
            "articles": [
                {
                    "id": "portfolio-1",
                    "sourceId": "innovation-capital-portfolio-01",
                    "title": "新锐具身智能科技股份有限公司完成D+轮融资",
                    "summary": "项目聚焦具身智能和智能机器人，投资机构继续加码。",
                    "publishedAt": "2026-09-22",
                    "sector": "智能机器人",
                    "company": "新锐具身智能科技股份有限公司",
                    "source": {
                        "name": "投资机构公开动态",
                        "url": "https://example.com/portfolio-1",
                        "level": "待交叉验证",
                    },
                }
            ],
        }
        snapshot = builder.build_candidate_snapshot(payload, self.watchlist(), {})
        self.assertEqual(snapshot["pendingCount"], 1)
        row = snapshot["candidates"][0]
        self.assertEqual(row["company"], "新锐具身智能科技股份有限公司")
        self.assertEqual(row["candidateClass"], "mature-opportunity")
        self.assertEqual(row["broker"], "")
        self.assertEqual(row["brokerEvidenceStatus"], "unassigned")
        self.assertEqual(row["route"], "A-share-TBD")
        self.assertEqual(row["routeConfidence"], "unassigned")
        self.assertEqual(row["capitalMarketPath"], "unassigned")
        self.assertEqual(row["stage"], "成熟期融资候选")
        self.assertIn("具身智能", row["fifteenthTags"])
        self.assertIn("命中硬科技机构组合成熟项目发现源", row["reasons"])
        self.assertIn("出现D/E/Pre-IPO/Growth等成熟期融资信号", row["reasons"])

    def test_reviewed_alias_is_not_rediscovered_from_portfolio_source(self):
        watchlist = self.watchlist()
        watchlist["projects"][0]["aliases"] = ["已跟踪科技"]
        payload = {
            "generatedAt": "2026-09-22T08:00:00+00:00",
            "articles": [
                {
                    "id": "portfolio-known",
                    "sourceId": "innovation-capital-portfolio-01",
                    "title": "已跟踪科技完成D轮融资",
                    "summary": "具身智能项目。",
                    "company": "已跟踪科技",
                    "publishedAt": "2026-09-22",
                    "sector": "智能机器人",
                    "source": {
                        "name": "公开发现",
                        "url": "https://example.com/known",
                        "level": "待交叉验证",
                    },
                }
            ],
        }
        snapshot = builder.build_candidate_snapshot(payload, watchlist, {})
        self.assertEqual(snapshot["candidateCount"], 0)

    def test_primary_regulatory_source_is_primary_backed_and_broker_bound(self):
        payload = {
            "generatedAt": "2026-09-22T08:00:00+00:00",
            "articles": [
                {
                    "id": "reg-1",
                    "sourceId": "innovation-listing-primary-regulatory-01-01",
                    "title": "星核半导体科技股份有限公司完成IPO辅导备案",
                    "summary": "中信证券为辅导机构，公司聚焦人工智能芯片。",
                    "publishedAt": "2026-09-22",
                    "sector": "半导体",
                    "source": {
                        "name": "证监会辅导公示",
                        "url": "https://eid.csrc.gov.cn/example/reg-1",
                        "level": "监管文件",
                    },
                }
            ],
        }
        snapshot = builder.build_candidate_snapshot(payload, self.watchlist(), {})
        self.assertEqual(snapshot["pendingCount"], 1)
        row = snapshot["candidates"][0]
        self.assertEqual(row["company"], "星核半导体科技股份有限公司")
        self.assertEqual(row["broker"], "中信证券")
        self.assertEqual(row["evidenceClass"], "primary-backed")
        self.assertEqual(row["reviewPriority"], "primary-first")
        self.assertEqual(row["primaryEvidenceCount"], 1)
        self.assertIn("命中证监会辅导公示定向源", row["reasons"])

    def test_human_decision_is_sticky_but_does_not_mutate_watchlist(self):
        initial = builder.build_candidate_snapshot(self.payload(), self.watchlist(), {})
        key = next(
            item["decisionKey"]
            for item in initial["candidates"]
            if item["company"] == "新锐量子科技股份有限公司"
        )
        decisions = {
            "decisions": {
                key: {
                    "status": "rejected",
                    "note": "人工确认该条仅为误匹配。",
                    "reviewedBy": "VCIQ",
                    "decidedAt": "2026-09-22T09:00:00+00:00",
                }
            }
        }
        snapshot = builder.build_candidate_snapshot(self.payload(), self.watchlist(), decisions)
        row = next(item for item in snapshot["candidates"] if item["decisionKey"] == key)
        self.assertEqual(row["status"], "rejected")
        self.assertEqual(snapshot["rejectedCount"], 1)
        self.assertEqual(snapshot["pendingCount"], 2)
        self.assertEqual(len(self.watchlist()["projects"]), 1)

    def test_fingerprint_changes_when_evidence_changes(self):
        first = builder.build_candidate_snapshot(self.payload(), self.watchlist(), {})
        row = next(item for item in first["candidates"] if item["company"] == "灵虎机器人")

        changed_payload = self.payload()
        changed_payload["articles"][1]["source"]["url"] = "https://example.com/a2-new"
        second = builder.build_candidate_snapshot(changed_payload, self.watchlist(), {})
        changed = next(item for item in second["candidates"] if item["company"] == "灵虎机器人")
        self.assertNotEqual(row["candidateFingerprint"], changed["candidateFingerprint"])


if __name__ == "__main__":
    unittest.main()
