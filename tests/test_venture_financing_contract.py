from __future__ import annotations

import copy
import re
import unittest
from typing import Any

from tools import enforce_venture_entity_semantics as entity_semantics
from tools import finalize_venture_profiles as finalizer
from tools import guard_venture_cross_field_noise as cross_field_noise_guard
from tools import normalize_venture_profiles as base_normalization
from tools import refine_venture_research_evidence as research_evidence
from tools import sanitize_venture_profiles as low_level_sanitization
from tools.stabilize_venture_publication_pipeline import align_capital_event_patterns


PRODUCT_COPY = (
    "Series C autonomous platform",
    "The Series C platform is designed for industrial deployment.",
    "Series C2 platform for factory automation",
    "Series 7 industrial controller",
    "Series B+ autonomous platform",
    "Our series c platform supports enterprise deployment.",
)
FINANCING_EVIDENCE = (
    "Example raises $500 million in Series C",
    "Example raised $500 million in a Series C funding round.",
    "Example Series B financing",
    "Example Series B+ financing",
    "Example Series C2 funding",
    "Example Series D round",
    "Example completes first close of $1 billion financing",
    "Example secured $20 million in funding",
    "Example completes strategic financing",
    "Example 完成 C 轮融资",
)


class SharedFinancingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        # Alignment intentionally mutates production modules. Restore every
        # overridden attribute so these tests do not leak state to other suites.
        overrides = (
            (research_evidence, ("FINANCING_RE", "CAPITAL_MARKET_RE")),
            (base_normalization, ("FINANCING_ACTION_PATTERN", "CAPITAL_MARKET_ACTION_PATTERN")),
            (low_level_sanitization, ("FINANCING_ACTION_RE", "CAPITAL_ACTION_RE")),
            (finalizer, ("STRONG_FINANCING_RE", "CAPITAL_EVIDENCE_RE")),
            (entity_semantics, ("FINANCING_ACTION_RE", "CAPITAL_ACTION_RE", "_capital_summary")),
            (cross_field_noise_guard, ("_capital_summary",)),
        )
        for module, names in overrides:
            for name in names:
                self.addCleanup(setattr, module, name, getattr(module, name))
        align_capital_event_patterns()

    @staticmethod
    def _patterns() -> dict[str, re.Pattern[str]]:
        return {
            "research": research_evidence.FINANCING_RE,
            "normalization": base_normalization.FINANCING_ACTION_PATTERN,
            "sanitization": low_level_sanitization.FINANCING_ACTION_RE,
            "finalization": finalizer.STRONG_FINANCING_RE,
            "entity_semantics": entity_semantics.FINANCING_ACTION_RE,
        }

    @staticmethod
    def _event(title: str, **fields: Any) -> dict[str, Any]:
        return {
            "date": "2026-01-02",
            "type": "融资",
            "title": title,
            "summary": title,
            "sourceUrl": "https://example.com/disclosure",
            **fields,
        }

    def test_aligned_patterns_reject_round_like_product_copy(self) -> None:
        for text in PRODUCT_COPY:
            for gate, pattern in self._patterns().items():
                with self.subTest(gate=gate, text=text):
                    self.assertIsNone(pattern.search(text))

    def test_round_and_amount_fields_do_not_turn_products_into_financing(self) -> None:
        for text in PRODUCT_COPY:
            with self.subTest(text=text):
                rows = finalizer.finalize_financing([
                    self._event(text, round="Series C", amount="$500 million"),
                ])
                self.assertEqual(rows, [])

    def test_aligned_patterns_keep_explicit_financing_evidence(self) -> None:
        for text in FINANCING_EVIDENCE:
            for gate, pattern in self._patterns().items():
                with self.subTest(gate=gate, text=text):
                    self.assertIsNotNone(pattern.search(text))
            with self.subTest(finalizer=text):
                rows = finalizer.finalize_financing([self._event(text)])
                self.assertEqual([row["title"] for row in rows], [text])

    def test_product_mentions_do_not_hide_actual_funding(self) -> None:
        title = "Example raises $20M to scale its Series C industrial platform"
        rows = finalizer.finalize_financing([self._event(title)])
        self.assertEqual([row["title"] for row in rows], [title])

    def test_guidance_is_not_financing_after_alignment(self) -> None:
        for text in (
            "Example raises full-year guidance for its Series C platform",
            "Example raises guidance following Series 7 controller sales",
        ):
            for gate, pattern in self._patterns().items():
                with self.subTest(gate=gate, text=text):
                    self.assertIsNone(pattern.search(text))
            with self.subTest(finalizer=text):
                self.assertEqual(finalizer.finalize_financing([
                    self._event(text, round="Series C"),
                ]), [])

    def test_mixed_batch_finalization_is_idempotent_and_non_mutating(self) -> None:
        financing_title = "Example raises $500 million in a Series C funding round"
        values = [
            self._event(PRODUCT_COPY[0], round="Series C"),
            self._event(financing_title, round="Series C", amount="$500 million"),
        ]
        original = copy.deepcopy(values)
        rows = finalizer.finalize_financing(values)
        self.assertEqual([row["title"] for row in rows], [financing_title])
        self.assertEqual(values, original)
        self.assertEqual(finalizer.finalize_financing(rows), rows)

    def test_repeated_alignment_preserves_the_shared_contract(self) -> None:
        for _ in range(2):
            align_capital_event_patterns()
            shared = finalizer.STRONG_FINANCING_RE
            for gate, pattern in self._patterns().items():
                with self.subTest(gate=gate):
                    self.assertIs(pattern, shared)
                    self.assertIsNone(pattern.search(PRODUCT_COPY[0]))
                    self.assertIsNotNone(pattern.search(FINANCING_EVIDENCE[0]))


if __name__ == "__main__":
    unittest.main()
