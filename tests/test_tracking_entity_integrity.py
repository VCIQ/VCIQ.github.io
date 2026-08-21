from __future__ import annotations

import unittest

from tools.tracking_entity_integrity import (
    assert_no_compound_tracking_entities,
    split_compound_tracking_entity_name,
)


def config(people: list[object], companies: list[object]) -> dict:
    return {
        "schemaVersion": 1,
        "tracks": [
            {
                "slug": "ai",
                "name": "AI / AGI",
                "people": people,
                "sampleCompanies": companies,
            }
        ],
    }


class TrackingEntityIntegrityTests(unittest.TestCase):
    def test_python_splitter_matches_reviewed_high_confidence_semantics(self) -> None:
        self.assertEqual(split_compound_tracking_entity_name("Alice、Bob"), ["Alice", "Bob"])
        self.assertEqual(split_compound_tracking_entity_name("Alpha / Beta"), ["Alpha", "Beta"])
        self.assertEqual(split_compound_tracking_entity_name("甲；乙"), ["甲", "乙"])
        self.assertEqual(split_compound_tracking_entity_name("甲 | 乙"), ["甲", "乙"])
        self.assertEqual(split_compound_tracking_entity_name("甲 和 乙"), ["甲", "乙"])

    def test_python_gate_catches_compounds_beyond_runtime_caps(self) -> None:
        people: list[object] = [
            *[f"Person {index + 1}" for index in range(40)],
            "Alice、Bob",
        ]
        companies: list[object] = [
            *[f"Company {index + 1}" for index in range(80)],
            "Alpha / Beta",
        ]
        with self.assertRaisesRegex(ValueError, "Alice、Bob") as ctx:
            assert_no_compound_tracking_entities(config(people, companies))
        self.assertIn("Alpha / Beta", str(ctx.exception))

    def test_python_gate_allows_legal_single_entity_punctuation(self) -> None:
        assert_no_compound_tracking_entities(
            config(
                ["Alice Smith"],
                ["OpenAI, Inc.", "Pony.ai, Inc.", "Procter & Gamble", "A/B Test Labs"],
            )
        )

    def test_python_gate_fails_closed_on_malformed_entity_arrays(self) -> None:
        with self.assertRaisesRegex(ValueError, "is not a string"):
            assert_no_compound_tracking_entities(
                config(["Alice", {"name": "Bob"}], ["OpenAI"])
            )


if __name__ == "__main__":
    unittest.main()
