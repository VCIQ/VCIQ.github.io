import unittest

from tools import reconcile_innovation_listing_lifecycle as reconciler


class InnovationListingLifecycleReconcileTests(unittest.TestCase):
    def watchlist(self):
        return {
            "projects": [
                {
                    "company": "示例科技股份有限公司",
                    "aliases": ["示例科技"],
                    "broker": "中信证券",
                    "sector": "集成电路",
                    "subsector": "AI芯片",
                    "route": "ChiNext",
                    "capitalMarketPath": "A",
                    "firstGuidanceDate": "2026-01-01",
                    "latestEventDate": "2026-08-01",
                    "latestEvent": "辅导中",
                    "fifteenthTags": ["集成电路", "人工智能"],
                }
            ]
        }

    def lifecycle(self):
        return {
            "schemaVersion": 1,
            "asOf": "2026-08-01",
            "projects": [],
            "governance": {},
        }

    def article(self, **overrides):
        row = {
            "id": "official-1",
            "sourceId": "innovation-listing-primary-project-02-01",
            "title": "示例科技股份有限公司首次公开发行股票并在创业板上市审核问询回复",
            "summary": "深圳证券交易所披露审核问询回复文件。",
            "company": "示例科技股份有限公司",
            "publishedAt": "2026-09-24",
            "source": {
                "name": "深圳证券交易所",
                "url": "https://reportdocs.static.szse.cn/example.pdf",
                "level": "交易所公告",
            },
        }
        row.update(overrides)
        return row

    def test_primary_official_event_promotes_reviewed_project(self):
        result, stats = reconciler.reconcile(
            {"articles": [self.article()]},
            self.watchlist(),
            self.lifecycle(),
        )
        self.assertEqual(stats["promotedProjects"], 1)
        self.assertEqual(stats["updatedProjects"], 1)
        project = result["projects"][0]
        self.assertEqual(project["stage"], "问询回复")
        self.assertEqual(project["lifecycleStatus"], "exchange-review")
        self.assertEqual(project["route"], "ChiNext")
        self.assertEqual(project["latestEventDate"], "2026-09-24")
        self.assertEqual(len(project["sources"]), 1)

    def test_discovery_only_source_cannot_mutate_lifecycle(self):
        article = self.article(
            sourceId="innovation-listing-projects-01",
            source={
                "name": "媒体",
                "url": "https://example.com/story",
                "level": "待交叉验证",
            },
        )
        result, stats = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            self.lifecycle(),
        )
        self.assertEqual(result["projects"], [])
        self.assertEqual(stats["eligiblePrimaryEvents"], 0)

    def test_unknown_company_is_not_auto_promoted(self):
        article = self.article(
            company="未知科技股份有限公司",
            title="未知科技股份有限公司创业板上市申请获受理",
        )
        result, stats = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            self.lifecycle(),
        )
        self.assertEqual(result["projects"], [])
        self.assertEqual(stats["matchedEvents"], 0)

    def test_board_is_not_inferred_when_official_text_does_not_name_it(self):
        article = self.article(
            title="示例科技股份有限公司首次公开发行股票审核问询回复",
            summary="交易所披露审核问询回复。",
        )
        result, _ = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            self.lifecycle(),
        )
        self.assertEqual(result["projects"][0]["route"], "ChiNext")

    def test_stale_or_regressive_event_is_rejected(self):
        lifecycle = self.lifecycle()
        lifecycle["projects"] = [
            {
                "id": "example",
                "company": "示例科技股份有限公司",
                "aliases": ["示例科技"],
                "broker": "中信证券",
                "sector": "集成电路",
                "subsector": "AI芯片",
                "route": "ChiNext",
                "capitalMarketPath": "A",
                "lifecycleStatus": "registration-review",
                "stage": "提交注册",
                "firstGuidanceDate": "2026-01-01",
                "latestEventDate": "2026-09-23",
                "latestEvent": "提交注册",
                "stockCode": "",
                "fifteenthTags": ["集成电路"],
                "sources": [],
            }
        ]
        result, stats = reconciler.reconcile(
            {"articles": [self.article(publishedAt="2026-09-24")]},
            self.watchlist(),
            lifecycle,
        )
        self.assertEqual(result["projects"][0]["stage"], "提交注册")
        self.assertEqual(stats["ignoredTransitions"], 1)

    def test_duplicate_source_url_is_idempotent(self):
        lifecycle = self.lifecycle()
        lifecycle["projects"] = [
            {
                "id": "example",
                "company": "示例科技股份有限公司",
                "aliases": ["示例科技"],
                "broker": "中信证券",
                "sector": "集成电路",
                "subsector": "AI芯片",
                "route": "ChiNext",
                "capitalMarketPath": "A",
                "lifecycleStatus": "exchange-review",
                "stage": "已问询",
                "firstGuidanceDate": "2026-01-01",
                "latestEventDate": "2026-09-20",
                "latestEvent": "已问询",
                "stockCode": "",
                "fifteenthTags": ["集成电路"],
                "sources": [
                    {
                        "title": "旧记录",
                        "url": "https://reportdocs.static.szse.cn/example.pdf",
                        "kind": "exchange-official",
                        "level": "regulatory",
                    }
                ],
            }
        ]
        result, stats = reconciler.reconcile(
            {"articles": [self.article()]},
            self.watchlist(),
            lifecycle,
        )
        self.assertEqual(len(result["projects"][0]["sources"]), 1)
        self.assertEqual(stats["dedupedEvents"], 1)


if __name__ == "__main__":
    unittest.main()
