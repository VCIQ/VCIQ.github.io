from __future__ import annotations

import unittest

from tools.entity_resolution import resolve_entity
from tools.reconcile_entity_resolution import reconcile_payloads
from tools.tracking_entity_integrity import find_compound_tracking_entities


EMPTY_DECISIONS = {"decisions": {}}


class CompoundCaptureReconciliationTests(unittest.TestCase):
    def test_person_and_company_compounds_are_reviewed_before_any_resolution_source(self) -> None:
        reviewed_decision = {
            "decisions": {
                "alicebob": {
                    "status": "resolved",
                    "requestedType": "person",
                    "entityType": "person",
                    "canonicalName": "Alice Bob",
                    "targetId": "person:alice-bob",
                    "confidence": "verified",
                    "aliases": [],
                    "note": "legacy decision must not collapse multiple people",
                }
            }
        }
        person = resolve_entity(
            "person",
            "Alice、Bob",
            decisions_payload=reviewed_decision,
            company_registry_payload={"companies": []},
            people_payload={"people": [{"slug": "alicebob", "name": "Alice、Bob"}]},
            tracking_payload={"tracks": []},
        )
        company = resolve_entity(
            "company",
            "Alpha / Beta",
            {"title": "Alpha / Beta companies"},
            decisions_payload=EMPTY_DECISIONS,
            company_registry_payload={
                "companies": [{"slug": "alpha-beta", "name": "Alpha / Beta"}]
            },
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )

        for resolution in (person, company):
            self.assertEqual(resolution.status, "review")
            self.assertEqual(resolution.source, "compound-entity-guard")
            self.assertEqual(resolution.targetId, "")
            self.assertIn("拆分", resolution.reason)

    def test_legal_single_entity_punctuation_and_topic_lists_are_not_blocked(self) -> None:
        companies = {
            "companies": [
                {"slug": "openai", "name": "OpenAI, Inc."},
                {"slug": "ab-test-labs", "name": "A/B Test Labs"},
                {"slug": "pg", "name": "Procter & Gamble"},
            ]
        }
        for name in ("OpenAI, Inc.", "A/B Test Labs", "Procter & Gamble"):
            with self.subTest(name=name):
                resolution = resolve_entity(
                    "company",
                    name,
                    decisions_payload=EMPTY_DECISIONS,
                    company_registry_payload=companies,
                    people_payload={"people": []},
                    tracking_payload={"tracks": []},
                )
                self.assertEqual(resolution.status, "resolved")
                self.assertNotEqual(resolution.source, "compound-entity-guard")

        topic = resolve_entity(
            "topic",
            "NAS、Transformer",
            decisions_payload=EMPTY_DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
            tracking_payload={"tracks": []},
        )
        self.assertEqual(topic.status, "resolved")
        self.assertEqual(topic.entityType, "topic")
        self.assertNotEqual(topic.source, "compound-entity-guard")

    def test_historical_replay_removes_all_ten_compound_occurrences_without_losing_atomic_values(self) -> None:
        google = "Quoc Le、Jeff Dean、Sanjay Ghemawat、Quoc Le、Oriol Vinyals"
        research = "Jeff Dean、陶哲轩、李飞飞、Dawn Song、Oriol Vinyals"
        wang = "王慧文、陈天桥、"
        investors = (
            "Aliya Capital Partners、Atreides Management、Artisan Partners、"
            "Battery Ventures、Diagonal Capital、Intel Capital、Key1 Capital"
        )
        google_atoms = ["Quoc Le", "Jeff Dean", "Sanjay Ghemawat", "Oriol Vinyals"]
        research_atoms = ["Jeff Dean", "陶哲轩", "李飞飞", "Dawn Song", "Oriol Vinyals"]
        investor_atoms = [
            "Aliya Capital Partners",
            "Atreides Management",
            "Artisan Partners",
            "Battery Ventures",
            "Diagonal Capital",
            "Intel Capital",
            "Key1 Capital",
        ]

        def track(slug: str, name: str, *, people=None, companies=None):
            return {
                "slug": slug,
                "name": name,
                "enabled": True,
                "custom": False,
                "keywords": [],
                "people": list(people or []),
                "sampleCompanies": list(companies or []),
            }

        config = {
            "schemaVersion": 1,
            "tracks": [
                track(
                    "ai",
                    "AI / AGI",
                    people=["王慧文", "陈天桥", *google_atoms, *research_atoms, wang, google, research],
                ),
                track("robotics", "机器人", people=[*google_atoms, *research_atoms, google, research]),
                track("ai-2", "AI安全", people=[*google_atoms, *research_atoms, google, research]),
                track("semiconductor", "半导体", companies=[*investor_atoms, investors]),
                track(
                    "track-1ccjq49",
                    "风险投资",
                    people=["王慧文", "陈天桥", wang],
                    companies=[*investor_atoms, investors],
                ),
            ],
            "listedCompanies": [],
            "sources": [],
        }
        self.assertEqual(len(find_compound_tracking_entities(config)), 10)

        def capture(capture_id: str, kind: str, value: str, slugs: list[str], field: str):
            return {
                "id": capture_id,
                "entityType": kind,
                "canonicalName": value,
                "rawSelection": value,
                "aliases": [],
                "trackSlugs": slugs,
                "trackNames": slugs,
                "source": {"title": "historical capture"},
                "capturedAt": "2026-08-09T00:00:00Z",
                "capturedBy": "VCIQ",
                "status": "applied",
                "appliedTo": [f"{slug}:{field}" for slug in slugs],
                "reasons": ["个人研究兴趣"],
                "note": "",
            }

        inbox = {
            "schemaVersion": 1,
            "generatedAt": "",
            "records": [
                capture("capture-wang", "person", wang, ["ai", "track-1ccjq49"], "people"),
                capture("capture-google", "person", google, ["ai", "robotics", "ai-2"], "people"),
                capture("capture-research", "person", research, ["ai", "robotics", "ai-2"], "people"),
                capture(
                    "capture-investors",
                    "company",
                    investors,
                    ["semiconductor", "track-1ccjq49"],
                    "sampleCompanies",
                ),
            ],
        }

        next_config, next_inbox, stats = reconcile_payloads(
            config,
            inbox,
            decisions_payload=EMPTY_DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
        )

        self.assertEqual(find_compound_tracking_entities(next_config), [])
        self.assertEqual(stats["review"], 4)
        for record in next_inbox["records"]:
            self.assertEqual(record["status"], "queued")
            self.assertEqual(record["appliedTo"], [])
            self.assertEqual(record["resolution"]["source"], "compound-entity-guard")

        by_slug = {row["slug"]: row for row in next_config["tracks"]}
        self.assertTrue({"王慧文", "陈天桥"}.issubset(by_slug["ai"]["people"]))
        self.assertTrue({"王慧文", "陈天桥"}.issubset(by_slug["track-1ccjq49"]["people"]))
        for slug in ("ai", "robotics", "ai-2"):
            self.assertTrue(set(google_atoms).issubset(by_slug[slug]["people"]))
            self.assertTrue(set(research_atoms).issubset(by_slug[slug]["people"]))
        for slug in ("semiconductor", "track-1ccjq49"):
            self.assertTrue(set(investor_atoms).issubset(by_slug[slug]["sampleCompanies"]))

        fixed_config, fixed_inbox, fixed_stats = reconcile_payloads(
            next_config,
            next_inbox,
            decisions_payload=EMPTY_DECISIONS,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
        )
        self.assertEqual(fixed_config, next_config)
        self.assertEqual(fixed_inbox, next_inbox)
        self.assertEqual(fixed_stats["review"], 4)


if __name__ == "__main__":
    unittest.main()
