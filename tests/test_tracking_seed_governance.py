from __future__ import annotations

import unittest
from datetime import datetime, timezone

from tools import tracking_seed_governance as governance


class TrackingSeedGovernanceTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI / AGI",
                    "enabled": True,
                    "keywords": ["大模型", "Here", "能力", "2026-07-27", "人物材料"],
                    "people": ["Sam Altman", "The Washington Post @washingtonpost"],
                    "sampleCompanies": ["OpenAI"],
                }
            ],
            "sources": [],
        }

    def test_low_signal_and_blocked_people_are_removed_and_tombstoned(self) -> None:
        config = self._config()
        ledger = {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [
                {
                    "track": "ai",
                    "kind": "keywords",
                    "value": "Here",
                    "addedAt": "2026-07-26T00:00:00+00:00",
                    "evidence": ["corpus-term"],
                }
            ],
            "removed": [],
        }
        report = governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
        track = config["tracks"][0]
        self.assertEqual(track["keywords"], ["大模型"])
        self.assertEqual(track["people"], ["Sam Altman"])
        self.assertGreaterEqual(report["tombstonesAdded"], 5)
        removed = {
            (row["kind"], row["value"])
            for row in ledger["removed"]
        }
        self.assertIn(("keywords", "Here"), removed)
        self.assertIn(("people", "The Washington Post @washingtonpost"), removed)

    def test_automatic_entries_receive_provenance_confidence_and_expiry(self) -> None:
        config = self._config()
        config["tracks"][0]["keywords"] = ["大模型", "agentic ai"]
        config["tracks"][0]["people"] = ["Sam Altman"]
        ledger = {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [
                {
                    "track": "ai",
                    "kind": "keywords",
                    "value": "agentic ai",
                    "addedAt": "2026-08-01T00:00:00+00:00",
                    "evidence": ["google-suggest", "news-confirmed"],
                }
            ],
            "removed": [],
        }
        report = governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(report["metadataBackfilled"], 1)
        row = ledger["added"][0]
        self.assertEqual(row["termProvenance"], "auto:news-confirmed")
        self.assertGreaterEqual(row["confidence"], 0.8)
        self.assertEqual(row["expiresAt"], "2026-10-30T00:00:00+00:00")

    def test_verified_team_entries_get_high_confidence_but_still_expire(self) -> None:
        config = self._config()
        config["tracks"][0]["keywords"] = ["大模型"]
        config["tracks"][0]["people"] = ["Sam Altman", "Research Lead"]
        ledger = {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [
                {
                    "track": "ai",
                    "kind": "people",
                    "value": "Research Lead",
                    "addedAt": "2026-08-01T00:00:00+00:00",
                    "evidence": ["sample-company-core-team", "verified-company-profile"],
                }
            ],
            "removed": [],
        }
        governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
        row = ledger["added"][0]
        self.assertEqual(row["termProvenance"], "auto:verified-directory")
        self.assertEqual(row["confidence"], 0.97)
        self.assertEqual(row["expiresAt"], "2027-08-01T00:00:00+00:00")

    def test_malformed_automatic_people_are_removed_and_tombstoned(self) -> None:
        config = self._config()
        config["tracks"][0]["keywords"] = ["大模型"]
        config["tracks"][0]["people"] = [
            "Sam Altman",
            "Class Presiden Thomas Sonderman",
            "Massachusetts Governo Chris Ballance",
            "Manual Class Example",
        ]
        ledger = {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [
                {
                    "track": "ai",
                    "kind": "people",
                    "value": "Class Presiden Thomas Sonderman",
                    "addedAt": "2026-08-01T00:00:00+00:00",
                    "evidence": ["sample-company-core-team", "verified-company-profile"],
                },
                {
                    "track": "ai",
                    "kind": "people",
                    "value": "Massachusetts Governo Chris Ballance",
                    "addedAt": "2026-08-01T00:00:00+00:00",
                    "evidence": ["sample-company-core-team", "verified-company-profile"],
                },
            ],
            "removed": [],
        }

        report = governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )

        self.assertEqual(
            config["tracks"][0]["people"],
            ["Sam Altman", "Manual Class Example"],
        )
        self.assertEqual(len(report["invalidAutomaticPeopleRemoved"]), 2)
        self.assertEqual(ledger["added"], [])
        removed = {(row["kind"], row["value"]) for row in ledger["removed"]}
        self.assertIn(("people", "Class Presiden Thomas Sonderman"), removed)
        self.assertIn(("people", "Massachusetts Governo Chris Ballance"), removed)

    def test_invalid_person_tombstone_prunes_stale_reintroduction(self) -> None:
        config = self._config()
        config["tracks"][0]["keywords"] = ["大模型"]
        config["tracks"][0]["people"] = [
            "Sam Altman",
            "Massachusetts Governo Chris Ballance",
            "Manual Class Example",
        ]
        ledger = {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [],
            "removed": [
                {
                    "track": "ai",
                    "kind": "people",
                    "value": "Massachusetts Governo Chris Ballance",
                    "removedAt": "2026-08-07T00:00:00+00:00",
                    "reason": "seed-governance-invalid-person",
                }
            ],
        }

        report = governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )

        self.assertEqual(
            config["tracks"][0]["people"],
            ["Sam Altman", "Manual Class Example"],
        )
        self.assertEqual(
            report["invalidAutomaticPeopleRemoved"],
            [{"track": "ai", "value": "Massachusetts Governo Chris Ballance"}],
        )
        self.assertEqual(report["tombstonesAdded"], 0)
        self.assertEqual(len(ledger["removed"]), 1)

        second = governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
        self.assertFalse(second["changed"])

    def test_expired_entries_are_removed_without_permanent_tombstone(self) -> None:
        config = self._config()
        config["tracks"][0]["keywords"] = ["大模型", "agentic ai"]
        config["tracks"][0]["people"] = ["Sam Altman"]
        ledger = {
            "schemaVersion": 1,
            "updatedAt": "",
            "tracks": {},
            "added": [
                {
                    "track": "ai",
                    "kind": "keywords",
                    "value": "agentic ai",
                    "addedAt": "2026-01-01T00:00:00+00:00",
                    "evidence": ["corpus-term"],
                }
            ],
            "removed": [],
        }
        report = governance.govern(
            config,
            ledger,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(config["tracks"][0]["keywords"], ["大模型"])
        self.assertEqual(ledger["added"], [])
        self.assertEqual(ledger["removed"], [])
        self.assertEqual(len(report["expiredRemoved"]), 1)


if __name__ == "__main__":
    unittest.main()
