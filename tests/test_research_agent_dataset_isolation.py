from __future__ import annotations

import unittest

from tools import research_agent as agent


class ResearchAgentDatasetIsolationTest(unittest.TestCase):
    def _observation(self, dataset: str) -> dict[str, object]:
        return {
            "dataset": dataset,
            "normalizedTitle": "示例人物发布重大更新",
            "publishedDate": "2026-09-13",
            "publishedDates": ["2026-09-13"],
            "entityKeys": ["entity:example"],
            "numericCues": [],
            "typeKeys": ["type:update"],
            "aliases": ["src-example"],
            "sourceAlias": "src-example",
            "sourceAliasNeedsTitleMatch": False,
            "fuzzyMatchThreshold": 0.86,
            "scalarClaims": {"role": "cto"},
        }

    def _entry(self, dataset: str) -> dict[str, object]:
        return {
            "dataset": dataset,
            "titleAliases": ["示例人物发布重大更新"],
            "publishedDate": "2026-09-13",
            "publishedDates": ["2026-09-13"],
            "entityKeys": ["entity:example"],
            "numericCues": [],
            "typeKeys": ["type:update"],
            "sourceAliases": ["src-example"],
            "scalarClaims": {"role": "cto"},
        }

    def test_regular_match_rejects_cross_dataset_event(self) -> None:
        observation = self._observation("intelligenceEvent")
        entry = self._entry("person")
        self.assertIsNone(agent._observation_matches_entry(observation, entry))

    def test_regular_match_preserves_same_dataset_behavior(self) -> None:
        observation = self._observation("person")
        entry = self._entry("person")
        self.assertIsNotNone(agent._observation_matches_entry(observation, entry))

    def test_seed_reuse_cannot_bypass_dataset_gate(self) -> None:
        observation = self._observation("intelligenceEvent")
        seeded_id = agent._new_event_id(observation)
        events = {seeded_id: self._entry("person")}
        matched_id, kind, ambiguous = agent._match_event_entry(observation, events)
        self.assertIsNone(matched_id)
        self.assertEqual(kind, "new")
        self.assertEqual(ambiguous, [])

    def test_correction_target_rejects_cross_dataset_event(self) -> None:
        observation = self._observation("intelligenceEvent")
        observation["correctionCue"] = True
        observation["correctionStrength"] = 4
        events = {"evt-old": self._entry("person")}
        target, ambiguous = agent._event_correction_target(observation, events)
        self.assertIsNone(target)
        self.assertEqual(ambiguous, [])

    def test_missing_legacy_dataset_remains_compatible(self) -> None:
        observation = self._observation("person")
        entry = self._entry("")
        self.assertTrue(agent._event_datasets_compatible(observation, entry))


if __name__ == "__main__":
    unittest.main()
