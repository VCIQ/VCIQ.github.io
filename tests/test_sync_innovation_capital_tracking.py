import copy
import unittest

from tools import sync_innovation_capital_tracking as syncer


class InnovationCapitalTrackingSyncTests(unittest.TestCase):
    def seeds(self):
        return {
            "schemaVersion": 1,
            "trackingKeywords": ["科创板", "Pre-IPO", "具身智能"],
            "projects": [
                {"name": "甲硬科技股份有限公司"},
            ],
            "brokers": [
                {"name": "中金公司", "aliases": ["中金公司", "CICC"]},
            ],
            "institutions": [
                {
                    "name": "红杉中国",
                    "aliases": ["红杉", "红杉中国", "HongShan红杉中国"],
                    "institutionTypes": ["PE/VC"],
                },
                {
                    "name": "启明创投",
                    "aliases": ["启明创投"],
                    "institutionTypes": ["PE/VC"],
                },
            ],
        }

    def ledger(self):
        return {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [],
            "removed": [],
        }

    def registry(self):
        return {
            "companies": [
                {
                    "slug": "galbot",
                    "name": "银河通用",
                    "region": "中国",
                    "sector": "机器人",
                    "stage": "成长期",
                    "status": "运营中",
                    "source": {
                        "url": "https://example.com/galbot",
                        "level": "官方披露",
                    },
                },
                {
                    "slug": "listed",
                    "name": "已上市样本",
                    "region": "中国",
                    "sector": "半导体",
                    "stage": "已上市",
                    "status": "已上市",
                    "source": {
                        "url": "https://example.com/listed",
                        "level": "官方披露",
                    },
                },
            ]
        }

    def venture(self):
        return {
            "companies": [
                {
                    "slug": "galbot",
                    "evidenceScore": 85,
                    "capitalSummary": {
                        "rounds": ["D轮"],
                        "latestRound": "D轮",
                        "latestDate": "2026-09-01",
                    },
                    "financing": [],
                    "capitalMarkets": [],
                }
            ],
            "institutions": [
                {
                    "name": "启明创投",
                    "portfolio": [
                        {
                            "name": "银河通用",
                            "companySlug": "galbot",
                            "round": "D轮",
                            "date": "2026-09-01",
                        }
                    ],
                }
            ],
        }

    def test_sync_creates_lane_and_merges_known_aliases(self):
        config = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "innovation-capital",
                    "name": "科创资本",
                    "enabled": True,
                    "custom": True,
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": ["红杉", "HongShan红杉中国"],
                }
            ],
            "sources": [],
        }
        result = syncer.sync(
            config,
            self.ledger(),
            self.seeds(),
            self.registry(),
            self.venture(),
        )
        track = config["tracks"][0]
        self.assertEqual(track["sampleCompanies"].count("红杉中国"), 1)
        self.assertNotIn("红杉", track["sampleCompanies"])
        self.assertIn("甲硬科技股份有限公司", track["sampleCompanies"])
        self.assertIn("中金公司", track["sampleCompanies"])
        self.assertIn("启明创投", track["sampleCompanies"])
        self.assertIn("银河通用", track["sampleCompanies"])
        self.assertGreaterEqual(len(result["mergedAliases"]), 1)

    def test_researched_mature_candidate_overrides_weaker_registry_row(self):
        mature = {
            "candidates": [
                {
                    "id": "galbot-mature",
                    "name": "银河通用",
                    "aliases": ["银河通用", "Galbot"],
                    "sector": "机器人",
                    "policyThemes": ["智能机器人", "具身智能"],
                    "financingRound": "D+轮",
                    "financingAmount": "25亿元人民币",
                    "financingDate": "2026-03-02",
                    "maturityClass": "late-stage",
                    "institutionBackers": ["启明创投"],
                    "source": {
                        "url": "https://example.com/galbot-dplus",
                        "level": "投资机构官方",
                    },
                }
            ]
        }
        rows = syncer.opportunity_rows(
            self.registry(),
            self.venture(),
            self.seeds(),
            mature,
        )
        galbot = next(row for row in rows if row["name"] == "银河通用")
        self.assertEqual(galbot["latestRound"], "D+轮")
        self.assertEqual(galbot["financingAmount"], "25亿元人民币")
        self.assertEqual(galbot["institutionBackers"], ["启明创投"])
        self.assertGreaterEqual(galbot["readinessScore"], 65)
        self.assertEqual(
            len([row for row in rows if row["name"] == "银河通用"]),
            1,
        )

    def test_opportunity_pool_prioritizes_late_stage_institution_backed_hard_tech(self):
        rows = syncer.opportunity_rows(
            self.registry(),
            self.venture(),
            self.seeds(),
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["name"], "银河通用")
        self.assertEqual(row["lateStageRounds"], ["D轮"])
        self.assertEqual(row["institutionBackers"], ["启明创投"])
        self.assertIn("具身智能", row["policyThemes"])
        self.assertGreaterEqual(row["readinessScore"], 80)

    def test_opportunity_projects_are_first_in_tracking_runtime_window(self):
        config = {"schemaVersion": 1, "tracks": [], "sources": []}
        syncer.sync(
            config,
            self.ledger(),
            self.seeds(),
            self.registry(),
            self.venture(),
        )
        track = next(row for row in config["tracks"] if row["slug"] == "innovation-capital")
        self.assertEqual(track["sampleCompanies"][0], "银河通用")
        self.assertIn("甲硬科技股份有限公司", track["sampleCompanies"])
        self.assertIn("中金公司", track["sampleCompanies"])
        self.assertIn("启明创投", track["sampleCompanies"])

    def test_removed_seed_is_not_silently_restored(self):
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [],
        }
        ledger = self.ledger()
        ledger["removed"].append(
            {
                "track": "innovation-capital",
                "kind": "sampleCompanies",
                "value": "中金公司",
                "reason": "owner-removed",
            }
        )
        syncer.sync(
            config,
            ledger,
            self.seeds(),
            self.registry(),
            self.venture(),
        )
        track = next(row for row in config["tracks"] if row["slug"] == "innovation-capital")
        self.assertNotIn("中金公司", track["sampleCompanies"])

    def test_second_sync_is_idempotent(self):
        config = {"schemaVersion": 1, "tracks": [], "sources": []}
        ledger = self.ledger()
        syncer.sync(
            config,
            ledger,
            self.seeds(),
            self.registry(),
            self.venture(),
        )
        config_once = copy.deepcopy(config)
        ledger_once = copy.deepcopy(ledger)
        result = syncer.sync(
            config,
            ledger,
            self.seeds(),
            self.registry(),
            self.venture(),
        )
        self.assertEqual(config, config_once)
        self.assertEqual(ledger, ledger_once)
        self.assertFalse(result["changed"])


if __name__ == "__main__":
    unittest.main()
