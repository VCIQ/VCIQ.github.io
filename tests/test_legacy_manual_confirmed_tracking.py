from __future__ import annotations

import unittest

from tools import manual_tracking as manual
from tools import reconcile_legacy_manual_confirmed_tracking as legacy


class LegacyManualConfirmedTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracking = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "venture-capital",
                    "name": "风险投资",
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": [],
                }
            ],
            "sources": [],
        }
        self.intents = {"schemaVersion": 1, "entities": [], "memberships": []}
        self.admins = {"schemaVersion": 1, "actors": ["VCIQ"]}

    def capture(self, name: str) -> dict:
        return {
            "id": "legacy-" + name,
            "entityType": "company",
            "canonicalName": name,
            "rawSelection": name,
            "aliases": [],
            "trackSlugs": ["venture-capital"],
            "trackNames": ["风险投资"],
            "source": {
                "articleId": "",
                "title": name,
                "url": "https://vciq.github.io/companies/",
                "summary": "赛道关注对象管理器:批量确认自动扩展为持续关注(风险投资)",
                "sourceName": "GitHub Actions · 内部手动追踪",
                "channel": "manual-tracking",
                "channelLabel": "内部管理",
                "eventType": "人工追踪",
            },
            "capturedAt": "2026-09-18T07:28:39+00:00",
            "capturedBy": "VCIQ",
            "status": "queued",
            "appliedTo": [],
            "reasons": ["个人研究兴趣"],
            "note": "赛道关注对象管理器:批量确认自动扩展为持续关注(风险投资)",
            "resolution": {
                "status": "review",
                "requestedType": "company",
                "entityType": "company",
                "canonicalName": name,
                "targetId": "",
                "confidence": "low",
                "source": "unresolved",
                "reason": "legacy state",
                "decisionKey": name,
                "reclassified": False,
            },
        }

    def review_intents(self, name: str, *, source: str = "source-context") -> dict:
        provisional_id = manual.stable_id("company", name)
        return {
            "schemaVersion": 1,
            "entities": [
                {
                    "id": provisional_id,
                    "kind": "company",
                    "name": name,
                    "aliases": [],
                    "keywords": [],
                    "state": "review",
                    "resolutionSource": source,
                    "resolutionStatus": "resolved" if source != "unresolved" else "review",
                    "createdAt": "2026-09-18T07:28:39+00:00",
                    "createdBy": "VCIQ",
                }
            ],
            "memberships": [
                {
                    "id": manual.stable_id(
                        "membership", "track:venture-capital", provisional_id, "actor"
                    ),
                    "trackId": "track:venture-capital",
                    "entityId": provisional_id,
                    "role": "actor",
                    "state": "review",
                    "pinned": True,
                    "confidence": "medium" if source != "unresolved" else "low",
                    "origins": [],
                }
            ],
        }

    def test_resolved_legacy_confirmation_becomes_active_and_pinned(self) -> None:
        inbox = {"schemaVersion": 1, "records": [self.capture("九合创投")]}
        tracking, inbox, intents, report = legacy.reconcile_legacy_manual_confirmed_tracking(
            self.tracking,
            inbox,
            self.review_intents("九合创投"),
            self.admins,
            now="2026-09-18T09:00:00+00:00",
        )

        self.assertEqual(report["promotedNames"], ["九合创投"])
        self.assertEqual(report["heldCount"], 0)
        self.assertIn("九合创投", tracking["tracks"][0]["sampleCompanies"])
        self.assertEqual(intents["entities"][0]["state"], "active")
        self.assertEqual(intents["entities"][0]["resolutionSource"], "human-decision")
        self.assertTrue(intents["memberships"][0]["pinned"])
        self.assertEqual(intents["memberships"][0]["state"], "active")
        self.assertEqual(inbox["records"][0]["status"], "applied")

    def test_existing_review_intent_is_migrated_without_duplicate_rows(self) -> None:
        name = "九合创投"
        intents = self.review_intents(name)
        inbox = {"schemaVersion": 1, "records": [self.capture(name)]}

        _, _, next_intents, report = legacy.reconcile_legacy_manual_confirmed_tracking(
            self.tracking,
            inbox,
            intents,
            self.admins,
            now="2026-09-18T09:00:00+00:00",
        )

        self.assertEqual(report["promotedNames"], [name])
        self.assertEqual(len(next_intents["entities"]), 1)
        self.assertEqual(len(next_intents["memberships"]), 1)
        self.assertEqual(next_intents["entities"][0]["state"], "active")
        self.assertEqual(
            next_intents["entities"][0]["id"], "company-candidate:九合创投"
        )
        self.assertEqual(next_intents["memberships"][0]["state"], "active")
        self.assertEqual(
            next_intents["memberships"][0]["entityId"],
            "company-candidate:九合创投",
        )

    def test_unresolved_legacy_confirmation_remains_review_gated(self) -> None:
        inbox = {"schemaVersion": 1, "records": [self.capture("美团龙珠")]}
        tracking, inbox, intents, report = legacy.reconcile_legacy_manual_confirmed_tracking(
            self.tracking,
            inbox,
            self.review_intents("美团龙珠", source="unresolved"),
            self.admins,
            now="2026-09-18T09:00:00+00:00",
        )

        self.assertEqual(report["promotedCount"], 0)
        self.assertEqual(report["heldNames"], ["美团龙珠"])
        self.assertNotIn("美团龙珠", tracking["tracks"][0]["sampleCompanies"])
        self.assertEqual(intents["entities"][0]["state"], "review")
        self.assertEqual(intents["memberships"][0]["state"], "review")
        self.assertTrue(intents["memberships"][0]["pinned"])
        self.assertEqual(inbox["records"][0]["status"], "queued")

    def test_rejected_pin_is_never_revived_by_legacy_capture(self) -> None:
        intents = self.review_intents("九合创投")
        intents["entities"][0]["state"] = "rejected"
        intents["memberships"][0]["state"] = "rejected"
        inbox = {"schemaVersion": 1, "records": [self.capture("九合创投")]}

        tracking, _, next_intents, report = legacy.reconcile_legacy_manual_confirmed_tracking(
            self.tracking,
            inbox,
            intents,
            self.admins,
            now="2026-09-18T09:00:00+00:00",
        )

        self.assertEqual(report["eligibleCount"], 0)
        self.assertEqual(tracking, self.tracking)
        self.assertEqual(next_intents, intents)

    def test_non_allowlisted_capture_is_not_replayed(self) -> None:
        row = self.capture("九合创投")
        row["capturedBy"] = "github-actions[bot]"
        tracking, inbox, intents, report = legacy.reconcile_legacy_manual_confirmed_tracking(
            self.tracking,
            {"schemaVersion": 1, "records": [row]},
            self.intents,
            self.admins,
            now="2026-09-18T09:00:00+00:00",
        )

        self.assertEqual(report["eligibleCount"], 0)
        self.assertEqual(tracking, self.tracking)
        self.assertEqual(intents, self.intents)
        self.assertEqual(inbox["records"][0]["status"], "queued")

    def test_replay_is_idempotent(self) -> None:
        inbox = {"schemaVersion": 1, "records": [self.capture("九合创投")]}
        first = legacy.reconcile_legacy_manual_confirmed_tracking(
            self.tracking,
            inbox,
            self.review_intents("九合创投"),
            self.admins,
            now="2026-09-18T09:00:00+00:00",
        )
        second = legacy.reconcile_legacy_manual_confirmed_tracking(
            first[0],
            first[1],
            first[2],
            self.admins,
            now="2026-09-18T10:00:00+00:00",
        )

        self.assertEqual(first[:3], second[:3])


if __name__ == "__main__":
    unittest.main()
