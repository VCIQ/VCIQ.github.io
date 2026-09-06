from __future__ import annotations

import copy
import unittest

from tools import manual_tracking_remove as removal


class ManualTrackingRemovalTests(unittest.TestCase):
    def setUp(self):
        self.tracking = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "robotics",
                    "name": "机器人",
                    "enabled": True,
                    "keywords": ["具身智能", "C++"],
                    "people": ["王兴兴"],
                    "sampleCompanies": ["宇树科技"],
                }
            ],
        }
        self.intents = {
            "schemaVersion": 1,
            "entities": [
                {"id": "technology:embodied", "kind": "technology", "name": "具身智能", "aliases": []},
                {"id": "technology:cpp", "kind": "technology", "name": "C++", "aliases": []},
                {"id": "person:wang", "kind": "person", "name": "王兴兴", "aliases": []},
                {"id": "company:unitree", "kind": "company", "name": "宇树科技", "aliases": ["Unitree"]},
            ],
            "memberships": [
                {
                    "id": "membership:technology:embodied",
                    "entityId": "technology:embodied",
                    "trackSlug": "robotics",
                    "state": "active",
                    "origins": [],
                },
                {
                    "id": "membership:technology:cpp",
                    "entityId": "technology:cpp",
                    "trackSlug": "robotics",
                    "state": "active",
                    "origins": [],
                },
                {
                    "id": "membership:person:wang",
                    "entityId": "person:wang",
                    "trackSlug": "robotics",
                    "state": "active",
                    "origins": [],
                },
                {
                    "id": "membership:company:unitree",
                    "entityId": "company:unitree",
                    "trackSlug": "robotics",
                    "state": "active",
                    "origins": [],
                },
            ],
        }

    def apply(self, kind: str, name: str):
        tracking = copy.deepcopy(self.tracking)
        intents = copy.deepcopy(self.intents)
        report = removal.apply_removal(
            tracking,
            intents,
            kind=kind,
            name=name,
            track_name="robotics",
            actor="owner",
            triggering_actor="owner",
            reasons=["个人研究兴趣"],
            note="remove from fixed watch",
            now="2026-09-05T12:00:00+00:00",
        )
        return tracking, intents, report

    def test_technology_removal_updates_runtime_and_rejects_membership(self):
        tracking, intents, report = self.apply("technology", "具身智能")
        self.assertNotIn("具身智能", tracking["tracks"][0]["keywords"])
        membership = next(row for row in intents["memberships"] if row["entityId"] == "technology:embodied")
        self.assertEqual(membership["state"], "rejected")
        self.assertEqual(membership["origins"][-1]["decision"], "remove-fixed-watch")
        self.assertTrue(report["configChanged"])
        self.assertTrue(report["intentsChanged"])
        self.assertEqual(report["state"], "rejected")

    def test_canonical_track_id_membership_is_rejected(self):
        tracking = copy.deepcopy(self.tracking)
        intents = copy.deepcopy(self.intents)
        for membership in intents["memberships"]:
            membership["trackId"] = f"track:{membership.pop('trackSlug')}"

        report = removal.apply_removal(
            tracking,
            intents,
            kind="technology",
            name="具身智能",
            track_name="robotics",
            actor="owner",
            triggering_actor="owner",
            reasons=["个人研究兴趣"],
            note="canonical membership cleanup",
            now="2026-09-05T12:00:00+00:00",
        )

        membership = next(row for row in intents["memberships"] if row["entityId"] == "technology:embodied")
        self.assertEqual(membership["trackId"], "track:robotics")
        self.assertEqual(membership["state"], "rejected")
        self.assertEqual(membership["origins"][-1]["decision"], "remove-fixed-watch")
        self.assertTrue(report["intentsChanged"])
        self.assertEqual(report["membershipCount"], 1)
        self.assertEqual(report["state"], "rejected")

    def test_track_id_is_authoritative_when_legacy_track_slug_disagrees(self):
        membership = {
            "trackId": "track:robotics",
            "trackSlug": "wrong-legacy-value",
        }
        self.assertEqual(removal.membership_track_slug(membership), "robotics")

    def test_symbolic_technology_identity_is_not_collapsed(self):
        tracking, intents, _ = self.apply("technology", "C++")
        self.assertNotIn("C++", tracking["tracks"][0]["keywords"])
        membership = next(row for row in intents["memberships"] if row["entityId"] == "technology:cpp")
        self.assertEqual(membership["state"], "rejected")

    def test_company_removal_needs_no_new_evidence_url(self):
        tracking, intents, report = self.apply("company", "宇树科技")
        self.assertNotIn("宇树科技", tracking["tracks"][0]["sampleCompanies"])
        membership = next(row for row in intents["memberships"] if row["entityId"] == "company:unitree")
        self.assertEqual(membership["state"], "rejected")
        self.assertEqual(report["field"], "sampleCompanies")

    def test_removal_is_scoped_to_exactly_one_track(self):
        with self.assertRaises(removal.ManualTrackingRemovalError):
            removal.apply_removal(
                copy.deepcopy(self.tracking),
                copy.deepcopy(self.intents),
                kind="source",
                name="Example",
                track_name="robotics",
                actor="owner",
                triggering_actor="owner",
                reasons=["个人研究兴趣"],
                note="",
            )

    def test_runtime_only_legacy_value_can_still_be_removed(self):
        tracking = copy.deepcopy(self.tracking)
        intents = {"schemaVersion": 1, "entities": [], "memberships": []}
        report = removal.apply_removal(
            tracking,
            intents,
            kind="person",
            name="王兴兴",
            track_name="机器人",
            actor="owner",
            triggering_actor="owner",
            reasons=["个人研究兴趣"],
            note="legacy cleanup",
            now="2026-09-05T12:00:00+00:00",
        )
        self.assertNotIn("王兴兴", tracking["tracks"][0]["people"])
        self.assertEqual(report["state"], "runtime-only-removed")
        self.assertFalse(report["intentsChanged"])


if __name__ == "__main__":
    unittest.main()
