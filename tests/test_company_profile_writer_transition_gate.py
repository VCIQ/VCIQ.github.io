"""Pure synthetic transition tests; no real collection, network or Git writes."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import unittest

from tools.company_profile_refresh_queue import build_queue, mark_processed_events
from tools.company_profile_writer_transition_gate import (
    TransitionError, _selection, check_transition as validate_transition,
)
from tests.test_company_profile_refresh_queue import article


NOW = datetime(2026, 11, 8, 10, tzinfo=UTC)
NAMES = {"openai": "OpenAI", "anthropic": "Anthropic"}
QUEUE_ARTICLE = article("synthetic-funding", "openai", "融资",
                        published_at="2026-11-08", importance=95)
ARTICLES = {"generatedAt": NOW.isoformat(), "articles": [QUEUE_ARTICLE]}

def check_transition(*args, **kwargs):
    """Use a separately attested, synthetic runtime window for all cases."""
    kwargs.setdefault("run_started_at", (NOW - timedelta(minutes=1)).isoformat())
    kwargs.setdefault("run_completed_at", (NOW + timedelta(minutes=3)).isoformat())
    return validate_transition(*args, **kwargs)


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
    def test_run_window_must_be_explicit_and_bounded(self):
        base, intent, final, before, after = sample()
        with self.assertRaisesRegex(TransitionError, "RUN_WINDOW_REQUIRED"):
            validate_transition(base, intent, final, before, after)
        with self.assertRaisesRegex(TransitionError, "RUN_WINDOW_INVALID"):
            validate_transition(
                base, intent, final, before, after,
                run_started_at=NOW.isoformat(),
                run_completed_at=(NOW + timedelta(hours=3)).isoformat(),
            )

    def test_stale_source_snapshot_does_not_invalidate_real_processing_time(self):
        source_time = NOW - timedelta(days=5)
        original = profiles()
        original["companies"]["openai"]["updatedAt"] = (
            source_time - timedelta(days=1)).isoformat()
        base = build_queue({"generatedAt": source_time.isoformat(), "articles": []},
                           original, NAMES, now=source_time)
        article_payload = {
            "generatedAt": source_time.isoformat(),
            "articles": [article("synthetic-old-source", "openai", "融资",
                                 published_at=source_time.date().isoformat())],
        }
        intent = build_queue(article_payload, original, NAMES, base, now=source_time)
        processed = mark_processed_events(intent, ["openai"], now=NOW)
        updated = deepcopy(original)
        updated["companies"]["openai"]["updatedAt"] = NOW.isoformat()
        final = build_queue(article_payload, updated, NAMES, intent,
                            now=source_time, processed_events=processed)
        self.assertLess(final["generatedAt"], next(
            iter(final["processedEvents"].values()))["processedAt"])
        self.assertEqual(check_transition(
            base, intent, final, original, updated)["newProcessedEvents"], 1)

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

    def test_selection_must_match_ordered_first_entries(self):
        base, intent, final, before, after = sample()
        intent["selectedSlugs"] = ["anthropic"]
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_unselected_entry_cannot_claim_selected_status(self):
        base, intent, final, before, after = sample()
        intent["entries"][0]["status"] = "pending"
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_final_queue_selected_count_must_match_slugs(self):
        base, intent, final, before, after = sample()
        final["selectedCount"] = 1
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_pending_count_cannot_undershoot_entries(self):
        base, intent, final, before, after = sample()
        intent["pendingCount"] = 0
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_pending_count_cannot_hide_missing_entries(self):
        base, intent, final, before, after = sample()
        intent["pendingCount"] = 101
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_entries_must_follow_builder_priority_order(self):
        payload = build_queue({
            "generatedAt": NOW.isoformat(),
            "articles": [
                article("synthetic-product", "openai", "产品发布",
                        published_at="2026-11-08", importance=95),
                article("synthetic-ipo", "anthropic", "IPO",
                        published_at="2026-11-08", importance=95),
            ],
        }, profiles(), NAMES, now=NOW, select_limit=2)
        _selection(payload)
        payload["entries"].reverse()
        payload["selectedSlugs"].reverse()
        with self.assertRaisesRegex(TransitionError, "SELECTION_INVALID"):
            _selection(payload)

    def test_candidate_generation_must_not_predate_selection(self):
        base, intent, final, before, after = sample()
        final["generatedAt"] = (NOW - timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(TransitionError, "CHRONOLOGY_INVALID"):
            check_transition(base, intent, final, before, after)

    def test_candidate_selected_slug_rejects_non_catalog_style(self):
        base, intent, final, before, after = sample()
        final["selectedSlugs"] = ["../../unexpected"]
        final["selectedCount"] = 1
        with self.assertRaisesRegex(TransitionError, "SLUGS_INVALID"):
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
