import unittest

from tools import reconcile_innovation_listing_lifecycle as reconciler


class InnovationListingLifecycleReconcilerTests(unittest.TestCase):
    def watchlist(self):
        return {
            "asOf": "2026-09-20",
            "brokers": ["中信证券", "中信建投", "中金公司", "国泰海通", "华泰联合", "广发证券"],
            "projects": [
                {
                    "id": "citic-chip",
                    "company": "创新芯片股份有限公司",
                    "aliases": ["创新芯片"],
                    "broker": "中信证券",
                    "sector": "集成电路",
                    "subsector": "AI芯片",
                    "route": "A-share-TBD",
                    "routeConfidence": "official-a-share-only",
                    "capitalMarketPath": "A",
                    "hkStatus": "none",
                    "pool": "observation",
                    "stage": "辅导中",
                    "firstGuidanceDate": "2026-08-01",
                    "latestEventDate": "2026-09-20",
                    "latestEvent": "辅导持续推进",
                    "everFiledBefore": False,
                    "priorFilingSummary": "",
                    "fifteenthTags": ["集成电路", "人工智能"],
                    "source": {
                        "title": "中信证券辅导公告",
                        "url": "https://www.citics.com/example/old",
                        "kind": "broker-official",
                    },
                }
            ],
        }

    def lifecycle(self):
        return {
            "schemaVersion": 1,
            "asOf": "2026-09-20",
            "projects": [
                {
                    "id": "citic-fatedi-lifecycle",
                    "company": "广东法特迪精密科技股份有限公司",
                    "aliases": ["法特迪", "法特迪精密"],
                    "broker": "中信证券",
                    "sector": "集成电路",
                    "subsector": "半导体测试硬件",
                    "route": "ChiNext",
                    "capitalMarketPath": "A",
                    "lifecycleStatus": "exchange-review",
                    "stage": "已问询",
                    "firstGuidanceDate": "2025-01-01",
                    "latestEventDate": "2026-09-20",
                    "latestEvent": "创业板IPO处于问询阶段",
                    "stockCode": "",
                    "fifteenthTags": ["集成电路"],
                    "sources": [
                        {
                            "title": "首次问询",
                            "url": "https://reportdocs.static.szse.cn/old.pdf",
                            "kind": "exchange-official",
                            "level": "regulatory",
                        }
                    ],
                }
            ],
            "governance": {"rule": "一级证据"},
        }

    def article(self, **overrides):
        row = {
            "id": "primary-1",
            "sourceId": "innovation-listing-primary-projects-01",
            "title": "广东法特迪精密科技股份有限公司关于首次公开发行股票并在创业板上市审核问询函的回复",
            "summary": "公司回复审核问询，中信证券为保荐机构。",
            "company": "广东法特迪精密科技股份有限公司",
            "publishedAt": "2026-09-23",
            "source": {
                "name": "深圳证券交易所",
                "url": "https://reportdocs.static.szse.cn/reply.pdf",
                "level": "监管文件",
            },
        }
        row.update(overrides)
        return row

    def test_primary_exchange_reply_updates_existing_lifecycle(self):
        watchlist, lifecycle, report = reconciler.reconcile(
            {"articles": [self.article()]},
            self.watchlist(),
            self.lifecycle(),
            {"candidates": []},
        )
        self.assertEqual(len(watchlist["projects"]), 1)
        row = lifecycle["projects"][0]
        self.assertEqual(row["stage"], "问询回复")
        self.assertEqual(row["latestEventDate"], "2026-09-23")
        self.assertEqual(row["route"], "ChiNext")
        self.assertEqual(row["lifecycleStatus"], "exchange-review")
        self.assertEqual(row["sources"][0]["url"], "https://reportdocs.static.szse.cn/reply.pdf")
        self.assertEqual(report["appliedCount"], 1)

    def test_discovery_only_or_non_official_url_never_mutates_canonical_state(self):
        article = self.article(
            sourceId="innovation-listing-projects-01",
            source={
                "name": "媒体",
                "url": "https://example.com/reply",
                "level": "待交叉验证",
            },
        )
        watchlist, lifecycle, report = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            self.lifecycle(),
            {"candidates": []},
        )
        self.assertEqual(lifecycle["projects"][0]["stage"], "已问询")
        self.assertEqual(report["appliedCount"], 0)
        self.assertFalse(report["changed"])
        self.assertEqual(len(watchlist["projects"]), 1)

    def test_official_acceptance_migrates_reserve_project_to_lifecycle(self):
        article = {
            "id": "primary-accept",
            "sourceId": "innovation-listing-primary-projects-01",
            "title": "创新芯片股份有限公司首次公开发行股票并在科创板上市申请获受理",
            "summary": "上交所受理，公司保荐机构为中信证券。",
            "company": "创新芯片股份有限公司",
            "publishedAt": "2026-09-24",
            "source": {
                "name": "上海证券交易所",
                "url": "https://www.sse.com.cn/example/accept",
                "level": "交易所公告",
            },
        }
        watchlist, lifecycle, report = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            self.lifecycle(),
            {"candidates": []},
        )
        self.assertEqual(watchlist["projects"], [])
        migrated = next(
            row for row in lifecycle["projects"] if row["company"] == "创新芯片股份有限公司"
        )
        self.assertEqual(migrated["stage"], "交易所受理")
        self.assertEqual(migrated["route"], "STAR")
        self.assertEqual(migrated["lifecycleStatus"], "exchange-review")
        self.assertTrue(any(row["action"] == "migrate-to-lifecycle" for row in report["applied"]))

    def test_primary_hard_tech_counselling_candidate_auto_promotes_without_board_inference(self):
        queue = {
            "candidates": [
                {
                    "id": "innovation-listing-newchip",
                    "status": "pending",
                    "candidateClass": "listing-candidate",
                    "company": "新芯半导体股份有限公司",
                    "aliases": ["新芯半导体股份有限公司"],
                    "broker": "中信证券",
                    "sector": "集成电路",
                    "route": "A-share-TBD",
                    "capitalMarketPath": "A",
                    "stage": "辅导备案",
                    "firstSeenAt": "2026-09-24",
                    "latestEvent": "完成IPO辅导备案",
                    "fifteenthTags": ["集成电路"],
                    "evidenceClass": "primary-backed",
                    "evidence": [
                        {
                            "articleId": "reg-newchip",
                            "sourceId": "innovation-listing-primary-regulatory-01-01",
                            "title": "新芯半导体股份有限公司完成IPO辅导备案",
                            "summary": "中信证券为辅导机构，公司聚焦集成电路。",
                            "url": "https://eid.csrc.gov.cn/example/newchip",
                            "sourceName": "证监会辅导公示",
                            "level": "监管文件",
                            "publishedAt": "2026-09-24",
                        }
                    ],
                }
            ]
        }
        watchlist, lifecycle, report = reconciler.reconcile(
            {"articles": []},
            self.watchlist(),
            self.lifecycle(),
            queue,
        )
        promoted = next(
            row for row in watchlist["projects"] if row["company"] == "新芯半导体股份有限公司"
        )
        self.assertEqual(promoted["route"], "A-share-TBD")
        self.assertEqual(promoted["routeConfidence"], "official-a-share-only")
        self.assertEqual(promoted["pool"], "observation")
        self.assertEqual(len(lifecycle["projects"]), 1)
        self.assertTrue(any(row["action"] == "auto-promote-watchlist" for row in report["applied"]))

    def test_exchange_candidate_requires_explicit_board_route(self):
        queue = {
            "candidates": [
                {
                    "id": "innovation-listing-unknown-board",
                    "status": "pending",
                    "candidateClass": "listing-candidate",
                    "company": "未定板块科技股份有限公司",
                    "aliases": ["未定板块科技股份有限公司"],
                    "broker": "中信证券",
                    "sector": "集成电路",
                    "route": "A-share-TBD",
                    "capitalMarketPath": "A",
                    "stage": "待核验",
                    "firstSeenAt": "2026-09-24",
                    "latestEvent": "审核问询回复",
                    "fifteenthTags": ["集成电路"],
                    "evidenceClass": "primary-backed",
                    "evidence": [
                        {
                            "articleId": "exchange-unknown",
                            "sourceId": "innovation-listing-primary-market-broker-01",
                            "title": "未定板块科技股份有限公司审核问询回复",
                            "url": "https://reportdocs.static.szse.cn/unknown.pdf",
                            "sourceName": "深圳证券交易所",
                            "level": "监管文件",
                            "publishedAt": "2026-09-24",
                        }
                    ],
                }
            ]
        }
        watchlist, lifecycle, report = reconciler.reconcile(
            {"articles": []},
            self.watchlist(),
            self.lifecycle(),
            queue,
        )
        self.assertFalse(
            any(row["company"] == "未定板块科技股份有限公司" for row in watchlist["projects"])
        )
        self.assertFalse(
            any(row["company"] == "未定板块科技股份有限公司" for row in lifecycle["projects"])
        )
        self.assertEqual(report["appliedCount"], 0)

    def test_regressive_event_does_not_overwrite_registration_stage(self):
        lifecycle = self.lifecycle()
        lifecycle["projects"][0]["stage"] = "提交注册"
        lifecycle["projects"][0]["lifecycleStatus"] = "registration-review"
        lifecycle["projects"][0]["latestEventDate"] = "2026-09-23"
        article = self.article(
            title="广东法特迪精密科技股份有限公司创业板审核问询函",
            summary="交易所发出新问询。",
            publishedAt="2026-09-24",
            source={
                "name": "深圳证券交易所",
                "url": "https://reportdocs.static.szse.cn/new-question.pdf",
                "level": "监管文件",
            },
        )
        _watchlist, updated, report = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            lifecycle,
            {"candidates": []},
        )
        self.assertEqual(updated["projects"][0]["stage"], "提交注册")
        self.assertEqual(updated["projects"][0]["latestEventDate"], "2026-09-23")
        self.assertEqual(report["appliedCount"], 0)

    def test_reconcile_is_idempotent_for_same_primary_evidence(self):
        first_watchlist, first_lifecycle, first_report = reconciler.reconcile(
            {"articles": [self.article()]},
            self.watchlist(),
            self.lifecycle(),
            {"candidates": []},
        )
        second_watchlist, second_lifecycle, second_report = reconciler.reconcile(
            {"articles": [self.article()]},
            first_watchlist,
            first_lifecycle,
            {"candidates": []},
        )
        self.assertEqual(first_report["appliedCount"], 1)
        self.assertEqual(second_report["appliedCount"], 0)
        self.assertFalse(second_report["changed"])
        self.assertEqual(first_watchlist, second_watchlist)
        self.assertEqual(first_lifecycle, second_lifecycle)


    def test_primary_candidate_does_not_auto_promote_when_official_evidence_omits_broker(self):
        queue = {
            "candidates": [
                {
                    "id": "innovation-listing-no-broker-proof",
                    "status": "pending",
                    "candidateClass": "listing-candidate",
                    "company": "谨慎芯片股份有限公司",
                    "aliases": ["谨慎芯片股份有限公司"],
                    "broker": "中信证券",
                    "sector": "集成电路",
                    "route": "A-share-TBD",
                    "capitalMarketPath": "A",
                    "stage": "辅导备案",
                    "firstSeenAt": "2026-09-24",
                    "latestEvent": "完成IPO辅导备案",
                    "fifteenthTags": ["集成电路"],
                    "evidenceClass": "primary-backed",
                    "evidence": [
                        {
                            "articleId": "reg-no-broker",
                            "sourceId": "innovation-listing-primary-regulatory-01-01",
                            "title": "谨慎芯片股份有限公司完成IPO辅导备案",
                            "summary": "公司聚焦集成电路。",
                            "url": "https://eid.csrc.gov.cn/example/no-broker",
                            "sourceName": "证监会辅导公示",
                            "level": "监管文件",
                            "publishedAt": "2026-09-24",
                        }
                    ],
                }
            ]
        }
        watchlist, lifecycle, report = reconciler.reconcile(
            {"articles": []},
            self.watchlist(),
            self.lifecycle(),
            queue,
        )
        self.assertFalse(
            any(row["company"] == "谨慎芯片股份有限公司" for row in watchlist["projects"])
        )
        self.assertEqual(len(lifecycle["projects"]), 1)
        self.assertEqual(report["appliedCount"], 0)

    def test_newer_explicit_other_market_route_can_update_parallel_ah_path(self):
        lifecycle = self.lifecycle()
        row = lifecycle["projects"][0]
        row["route"] = "HK"
        row["capitalMarketPath"] = "A+H"
        row["stage"] = "已上市"
        row["lifecycleStatus"] = "listed"
        row["latestEventDate"] = "2026-09-20"
        article = self.article(
            title="广东法特迪精密科技股份有限公司首次公开发行股票并在创业板上市审核问询函",
            summary="中信证券保荐，创业板项目进入新一轮问询。",
            publishedAt="2026-09-24",
            source={
                "name": "深圳证券交易所",
                "url": "https://reportdocs.static.szse.cn/parallel-a.pdf",
                "level": "监管文件",
            },
        )
        _watchlist, updated, report = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            lifecycle,
            {"candidates": []},
        )
        current = updated["projects"][0]
        self.assertEqual(current["route"], "ChiNext")
        self.assertEqual(current["stage"], "新一轮问询")
        self.assertEqual(current["capitalMarketPath"], "A+H")
        self.assertEqual(report["appliedCount"], 1)

    def test_newer_primary_restart_can_follow_terminal_state(self):
        lifecycle = self.lifecycle()
        row = lifecycle["projects"][0]
        row["stage"] = "终止审核"
        row["lifecycleStatus"] = "terminated"
        row["latestEventDate"] = "2026-09-20"
        article = self.article(
            title="广东法特迪精密科技股份有限公司重新启动IPO辅导备案",
            summary="中信证券继续担任辅导机构。",
            publishedAt="2026-09-24",
            source={
                "name": "证监会辅导公示",
                "url": "https://eid.csrc.gov.cn/example/restart",
                "level": "监管文件",
            },
        )
        _watchlist, updated, report = reconciler.reconcile(
            {"articles": [article]},
            self.watchlist(),
            lifecycle,
            {"candidates": []},
        )
        current = updated["projects"][0]
        self.assertEqual(current["stage"], "辅导备案")
        self.assertEqual(current["lifecycleStatus"], "counselling")
        self.assertEqual(current["latestEventDate"], "2026-09-24")
        self.assertEqual(report["appliedCount"], 1)


if __name__ == "__main__":
    unittest.main()
