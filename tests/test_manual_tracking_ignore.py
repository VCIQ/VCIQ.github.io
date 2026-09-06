from __future__ import annotations

import copy
import unittest

from tools import manual_tracking_ignore as ignore


class ManualTrackingIgnoreTests(unittest.TestCase):
    def setUp(self):
        self.tracking = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "robotics",
                    "name": "机器人",
                    "enabled": True,
                    "keywords": ["具身智能", "自动候选技术"],
                    "people": ["候选人物"],
                    "sampleCompanies": ["候选公司"],
                    "ignoredRecommendations": {"keywords": ["旧噪声"]},
                }
            ],
        }
        self.intents = {"schemaVersion": 1, "entities": [], "memberships": []}
        self.ledger = {
            "schemaVersion": 1,
            "updatedAt": "2026-09-05T00:00:00+00:00",
            "added": [
                {
                    "track": "robotics",
                    "kind": "keywords",
                    "value": "自动候选技术",
                    "addedAt": "2026-09-05T08:00:00+00:00",
                    "termProvenance": "auto:news-discovery",
                    "confidence": 0.68,
                },
                {
                    "track": "robotics",
                    "kind": "people",
                    "value": "候选人物",
                    "addedAt": "2026-09-05T08:01:00+00:00",
                },
                {
                    "track": "robotics",
                    "kind": "sampleCompanies",
                    "value": "候选公司",
                    "addedAt": "2026-09-05T08:02:00+00:00",
                },
            ],
            "removed": [],
        }

    def apply(self, kind: str, name: str):
        tracking = copy.deepcopy(self.tracking)
        intents = copy.deepcopy(self.intents)
        ledger = copy.deepcopy(self.ledger)
        report = ignore.apply_ignore(
            tracking,
            intents,
            ledger,
            kind=kind,
            name=name,
            track_name="robotics",
            actor="owner",
            triggering_actor="owner",
            reasons=["与本赛道无关"],
            note="not relevant to this track",
            now="2026-09-06T07:00:00+00:00",
        )
        return tracking, intents, ledger, report

    def test_ignore_removes_runtime_adds_tombstone_and_rejected_intent(self):
        tracking, intents, ledger, report = self.apply("technology", "自动候选技术")
        track = tracking["tracks"][0]
        self.assertNotIn("自动候选技术", track["keywords"])
        self.assertIn("自动候选技术", track["ignoredRecommendations"]["keywords"])
        tombstone = ledger["removed"][-1]
        self.assertEqual(tombstone["track"], "robotics")
        self.assertEqual(tombstone["kind"], "keywords")
        self.assertEqual(tombstone["reason"], "manual-ignore-auto-candidate")
        membership = intents["memberships"][0]
        self.assertEqual(membership["trackId"], "track:robotics")
        self.assertEqual(membership["state"], "rejected")
        self.assertTrue(membership["pinned"])
        self.assertEqual(membership["origins"][-1]["decision"], "ignore-auto-candidate")
        self.assertEqual(membership["origins"][-1]["reasons"], ["与本赛道无关"])
        self.assertTrue(report["runtimeRemoved"])
        self.assertTrue(report["tombstoneAdded"])
        self.assertEqual(report["state"], "rejected")

    def test_company_negative_feedback_needs_no_evidence_url(self):
        tracking, intents, ledger, report = self.apply("company", "候选公司")
        track = tracking["tracks"][0]
        self.assertNotIn("候选公司", track["sampleCompanies"])
        self.assertIn("候选公司", track["ignoredRecommendations"]["companies"])
        self.assertEqual(intents["memberships"][0]["role"], "actor")
        self.assertTrue(report["changed"])
        self.assertTrue(any(row["kind"] == "sampleCompanies" for row in ledger["removed"]))

    def test_non_candidate_is_rejected(self):
        with self.assertRaises(ignore.ManualTrackingIgnoreError):
            ignore.apply_ignore(
                copy.deepcopy(self.tracking),
                copy.deepcopy(self.intents),
                copy.deepcopy(self.ledger),
                kind="technology",
                name="任意新对象",
                track_name="robotics",
                actor="owner",
                triggering_actor="owner",
                reasons=["与本赛道无关"],
                note="",
                now="2026-09-06T07:00:00+00:00",
            )

    def test_positive_tracking_reason_is_rejected_for_negative_feedback(self):
        with self.assertRaises(ignore.ManualTrackingIgnoreError) as raised:
            ignore.apply_ignore(
                copy.deepcopy(self.tracking),
                copy.deepcopy(self.intents),
                copy.deepcopy(self.ledger),
                kind="technology",
                name="自动候选技术",
                track_name="robotics",
                actor="owner",
                triggering_actor="owner",
                reasons=["融资机会"],
                note="",
                now="2026-09-06T07:00:00+00:00",
            )
        self.assertIn("受控负反馈枚举", str(raised.exception))

    def test_all_controlled_ignore_reasons_are_accepted(self):
        self.assertEqual(
            ignore.ALLOWED_IGNORE_REASONS,
            {
                "与本赛道无关",
                "实体识别错误",
                "低信号噪声",
                "重复或已覆盖",
                "当前不再关注",
            },
        )

    def test_second_apply_is_idempotent(self):
        tracking, intents, ledger, first = self.apply("person", "候选人物")
        second = ignore.apply_ignore(
            tracking,
            intents,
            ledger,
            kind="person",
            name="候选人物",
            track_name="robotics",
            actor="owner",
            triggering_actor="owner",
            reasons=["与本赛道无关"],
            note="not relevant to this track",
            now="2026-09-06T07:05:00+00:00",
        )
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(len([row for row in ledger["removed"] if row["kind"] == "people"]), 1)
        self.assertEqual(len(intents["memberships"][0]["origins"]), 1)

    def test_stale_ignore_cannot_override_active_manual_membership(self):
        entity_id = ignore.stable_id("technology", ignore.signal_identity("自动候选技术", "keywords"))
        self.intents = {
            "schemaVersion": 1,
            "entities": [
                {
                    "id": entity_id,
                    "kind": "technology",
                    "name": "自动候选技术",
                    "aliases": [],
                    "keywords": ["自动候选技术"],
                    "state": "active",
                }
            ],
            "memberships": [
                {
                    "id": ignore.stable_id("membership", "track:robotics", entity_id, "keyword"),
                    "trackId": "track:robotics",
                    "entityId": entity_id,
                    "role": "keyword",
                    "state": "active",
                    "pinned": True,
                    "confidence": "verified",
                    "origins": [],
                }
            ],
        }
        with self.assertRaises(ignore.ManualTrackingIgnoreError):
            self.apply("technology", "自动候选技术")


if __name__ == "__main__":
    unittest.main()
