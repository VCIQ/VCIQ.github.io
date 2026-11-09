"""Pure synthetic transition tests; no real collection, network or Git writes."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import unittest

from tools.company_profile_refresh_queue import build_queue, mark_processed_events
from tools.company_profile_writer_transition_gate import TransitionError, check_transition
from tests.test_company_profile_refresh_queue import article


NOW = datetime(2026, 11, 8, 10, tzinfo=UTC)
NAMES = {"openai": "OpenAI", "anthropic": "Anthropic"}
QUEUE_ARTICLE = article("synthetic-funding", "openai", "融资",
                        published_at="2026-11-08", importance=95)
ARTICLES = {"generatedAt": NOW.isoformat(), "articles": [QUEUE_ARTICLE]}


def profiles(*, openai_at="2026-11-07T10:00:00Z", anthropic_at="2026-11-07T10:00:00Z"):
    return {
        "schemaVersion": 2,
        "generatedAt": NOW.isoformat(),
        "companies": {
            "openai": {"updatedAt": openai_at, "name": "OpenAI"},
            "anthropic": {"updatedAt": anthropic_at, "name": "Anthropic"},
        },
        "qualityGate": {},
        "sourceStatus": {},
        "institutions": {},
        "researchModelVersion": 1,
    }


def sample():
    original = profiles()
    base = build_queue({"generatedAt": NOW.isoformat(), "articles": []},
                       original, NAMES, now=NOW)
    intent = build_queue(ARTICLES, original, NAMES, base, now=NOW,
                         select_limit=1)
    next_profiles = profiles(openai_at="2026-11-08T10:01:00Z")
    processed = mark_processed_events(intent, ["openai"], now=NOW)
    final = build_queue(ARTICLES, next_profiles, NAMES, intent,
                        now=NOW + timedelta(minutes=1),
                        processed_events=processed)
    return base, intent, final, original, next_profiles


class CompanyProfileTransitionTests(unittest.TestCase):
    def test_real_queue_build_and_mark_processed_flow_passes(self):
        base, intent, final, before, after = sample()
        self.assertEqual(intent["selectedSlugs"], ["openai"])
        self.assertEqual(final["selectedSlugs"], [])
        result = check_transition(base, intent, final, before, after)
        self.assertTrue(result["ok"])
        self.assertEqual(result["newProcessedEvents"], 1)
        self.assertEqual(result["changedCompanies"], 1)
        self.assertFalse(result["mergeAuthorized"])
        self.assertFalse(result["publicationAuthorized"])

    def test_retrying_processed_event_is_rejected(self):
        base, intent, final, before, after = sample()
        key, row = next(iter(final["processedEvents"].items()))
        base["processedEvents"][key] = deepcopy(row)
        with self.assertRaisesRegex(TransitionError, "DUPLICATE_EVENT"):
            check_transition(base, intent, final, before, after)

    def test_missing_processed_event_rejected(self):
        base, intent, final, before, after = sample()
        final["processedEvents"] = {}
        with self.assertRaisesRegex(TransitionError, "PROCESSED_MISMATCH"):
            check_transition(base, intent, final, before, after)

    def test_extra_processed_event_rejected(self):
        base, intent, final, before, after = sample()
        final["processedEvents"]["anthropic:" + "0" * 40] = {
            "companySlug": "anthropic", "articleId": "synthetic",
            "processedAt": NOW.isoformat(),
        }
        with self.assertRaisesRegex(TransitionError, "PROCESSED_MISMATCH"):
            check_transition(base, intent, final, before, after)

    def test_unselected_company_profile_change_rejected(self):
        base, intent, final, before, after = sample()
        after["companies"]["anthropic"]["name"] = "Unexpected"
        with self.assertRaisesRegex(TransitionError, "UNRELATED_COMPANY"):
            check_transition(base, intent, final, before, after)

    def test_separately_attested_coverage_company_allowed(self):
        base, intent, final, before, after = sample()
        after["companies"]["anthropic"]["name"] = "Coverage Updated"
        result = check_transition(base, intent, final, before, after,
                                  coverage_slugs=["anthropic"])
        self.assertEqual(result["coverageCompanies"], 1)
        self.assertEqual(result["changedCompanies"], 2)

    def test_new_or_removed_profile_root_fails_closed(self):
        base, intent, final, before, after = sample()
        after["otherField"] = 3
        with self.assertRaisesRegex(TransitionError, "PROFILE_SHAPE_CHANGED"):
            check_transition(base, intent, final, before, after)

    def test_unexpected_profile_metadata_change_rejected(self):
        base, intent, final, before, after = sample()
        after["researchModelVersion"] = 2
        with self.assertRaisesRegex(TransitionError, "PROFILE_METADATA_UNEXPECTED"):
            check_transition(base, intent, final, before, after)

    def test_future_processed_timestamp_rejected(self):
        base, intent, final, before, after = sample()
        next(iter(final["processedEvents"].values()))["processedAt"] = (
            NOW + timedelta(hours=2)).isoformat()
        with self.assertRaisesRegex(TransitionError, "NEW_EVENT_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_pre_crawl_selection_must_not_mark_processed(self):
        base, intent, final, before, after = sample()
        intent["processedEvents"] = deepcopy(final["processedEvents"])
        with self.assertRaisesRegex(TransitionError, "INTENT_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_missing_intent_fingerprint_rejected(self):
        base, intent, final, before, after = sample()
        intent["entries"][0]["eventFingerprints"] = []
        with self.assertRaisesRegex(TransitionError, "INTENT_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_selection_count_must_match_slugs(self):
        base, intent, final, before, after = sample()
        intent["selectedCount"] = 0
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_recent_history_cannot_disappear(self):
        base, intent, final, before, after = sample()
        old_key = "anthropic:" + "a" * 40
        event = {"companySlug": "anthropic", "articleId": "old",
                 "processedAt": (NOW - timedelta(days=1)).isoformat()}
        base["processedEvents"][old_key] = event
        intent["processedEvents"][old_key] = event
        with self.assertRaisesRegex(TransitionError, "RECENT_HISTORY_LOST"):
            check_transition(base, intent, final, before, after)

    def test_expired_90_day_history_can_be_pruned(self):
        base, intent, final, before, after = sample()
        old_key = "anthropic:" + "a" * 40
        base["processedEvents"][old_key] = {
            "companySlug": "anthropic", "articleId": "expired",
            "processedAt": (NOW - timedelta(days=100)).isoformat(),
        }
        self.assertTrue(check_transition(base, intent, final, before, after)["ok"])

    def test_prior_history_cannot_be_rewritten(self):
        base, intent, final, before, after = sample()
        old_key = "anthropic:" + "a" * 40
        event = {"companySlug": "anthropic", "articleId": "stable",
                 "processedAt": (NOW - timedelta(days=1)).isoformat()}
        base["processedEvents"][old_key] = deepcopy(event)
        intent["processedEvents"][old_key] = deepcopy(event)
        final["processedEvents"][old_key] = {**event, "articleId": "altered"}
        with self.assertRaisesRegex(TransitionError, "HISTORY_REWRITTEN"):
            check_transition(base, intent, final, before, after)

    def test_company_deleted_rejected(self):
        base, intent, final, before, after = sample()
        after["companies"].pop("anthropic")
        with self.assertRaisesRegex(TransitionError, "COMPANY_DELETED"):
            check_transition(base, intent, final, before, after)


if __name__ == "__main__":
    unittest.main()
