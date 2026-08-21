from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DISCOVERY = WORKFLOWS / "company-candidate-discovery.yml"
ONBOARDING = WORKFLOWS / "company-candidate-onboarding.yml"
REFRESH = WORKFLOWS / "scheduled-sync.yml"
MANUAL = WORKFLOWS / "manual-tracking.yml"
MANUAL_BATCH = WORKFLOWS / "manual-tracking-batch.yml"

WRITER_GROUP = "group: vciq-repository-writer-${{ github.ref }}"


class WriterQueueCompactionTests(unittest.TestCase):
    def test_candidate_discovery_preserves_push_delta_and_publication_intent(self) -> None:
        text = DISCOVERY.read_text(encoding="utf-8")
        top = text.split("\njobs:\n", 1)[0]
        discover = text.split("  discover:\n", 1)[1]

        self.assertIn(
            "group: vciq-candidate-discovery-${{ github.ref }}-${{ github.event_name }}-${{ github.event_name == 'push' && github.sha || inputs.publish_after_reconciliation || 'false' }}",
            top,
        )
        self.assertIn("queue: single", top)
        self.assertNotIn(WRITER_GROUP, top)
        self.assertIn(WRITER_GROUP, discover)
        self.assertIn("queue: max", discover.split("steps:", 1)[0])

        # Push handling later relies on this exact event's before→sha delta to decide
        # whether a public tracking refresh is required. Therefore distinct push SHAs
        # must never collapse into one pending run.
        self.assertIn("github.event_name == 'push' && github.sha", top)
        self.assertIn("BEFORE_SHA: ${{ github.event.before }}", text)
        self.assertIn("AFTER_SHA: ${{ github.sha }}", text)
        self.assertIn("PUSH_TRACKING_INPUTS_CHANGED", text)

        self.assertIn("publish_after_reconciliation:", text)
        self.assertIn("-f post_onboarding_handoff=refresh", text)
        self.assertIn("-f post_onboarding_handoff=publish-with-research", text)

    def test_candidate_onboarding_keeps_each_handoff_in_a_distinct_coalescing_key(self) -> None:
        text = ONBOARDING.read_text(encoding="utf-8")
        top = text.split("\njobs:\n", 1)[0]
        onboard = text.split("  onboard:\n", 1)[1]

        self.assertIn(
            "group: vciq-candidate-onboarding-${{ github.ref }}-${{ inputs.post_onboarding_handoff || 'none' }}",
            top,
        )
        self.assertIn("queue: single", top)
        self.assertNotIn(WRITER_GROUP, top)
        self.assertIn(WRITER_GROUP, onboard)
        self.assertIn("queue: max", onboard.split("steps:", 1)[0])
        for handoff in ("none", "refresh", "publish-with-research"):
            self.assertIn(f"          - {handoff}", text)
        self.assertIn('handoff="${POST_ONBOARDING_HANDOFF:-none}"', text)

    def test_full_refresh_checks_currentness_before_waiting_for_writer_lock(self) -> None:
        text = REFRESH.read_text(encoding="utf-8")
        top = text.split("\njobs:\n", 1)[0]
        preflight = text.split("  preflight:\n", 1)[1].split("\n  crawl:\n", 1)[0]
        crawl = text.split("  crawl:\n", 1)[1]

        self.assertIn("group: vciq-public-refresh-${{ github.ref }}", top)
        self.assertIn("queue: single", top)
        self.assertNotIn(WRITER_GROUP, top)
        self.assertIn("python tools/full_refresh_input_guard.py", preflight)
        self.assertNotIn(WRITER_GROUP, preflight)
        self.assertIn("needs: preflight", crawl)
        self.assertIn("if: needs.preflight.outputs.current == 'true'", crawl)
        self.assertIn(WRITER_GROUP, crawl)
        self.assertIn("queue: max", crawl.split("steps:", 1)[0])

    def test_manual_writes_remain_fifo_and_are_never_coalesced(self) -> None:
        for workflow in (MANUAL, MANUAL_BATCH):
            text = workflow.read_text(encoding="utf-8")
            apply = text.split("  apply:\n", 1)[1].split("\n  handoff:\n", 1)[0]
            with self.subTest(workflow=workflow.name):
                self.assertNotIn("queue: single", text)
                self.assertIn(WRITER_GROUP, apply)
                self.assertIn("queue: max", apply)


if __name__ == "__main__":
    unittest.main()
