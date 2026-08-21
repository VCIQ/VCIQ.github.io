from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
DISCOVERY = ROOT / ".github" / "workflows" / "tracking-discovery.yml"
MANUAL = ROOT / ".github" / "workflows" / "manual-tracking.yml"
BATCH = ROOT / ".github" / "workflows" / "manual-tracking-batch.yml"
CAPTURE_GITHUB = ROOT / "lib" / "tracking-capture-github.ts"
VALIDATOR = ROOT / "scripts" / "validate-zero-tracking-compounds.ts"

TRACKING_VALIDATE = "npm run validate:tracking"
DELTA_GATE = "node --import tsx scripts/validate-new-tracking-entities.ts --base-ref HEAD"


class TrackingCleanStateWorkflowTests(unittest.TestCase):
    def test_validate_tracking_composes_the_raw_clean_state_gate(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        scripts = package["scripts"]
        self.assertEqual(
            scripts["validate:tracking-entities"],
            "node --import tsx scripts/validate-zero-tracking-compounds.ts",
        )
        self.assertEqual(
            scripts["validate:tracking"],
            "node scripts/validate-tracking-pages.mjs && npm run validate:tracking-entities",
        )
        build = scripts["build:pages"]
        self.assertIn(TRACKING_VALIDATE, build)
        self.assertIn("npm run validate:taxonomy", build)
        self.assertLess(build.index(TRACKING_VALIDATE), build.index("npm run validate:taxonomy"))

    def test_clean_state_validator_reads_raw_config_without_runtime_normalization(self) -> None:
        text = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn('const TRACKING_CONFIG_PATH = "config/user_tracking.json"', text)
        self.assertIn('argumentValue("--worktree", ".")', text)
        self.assertIn("splitCompoundTrackingEntityName", text)
        self.assertNotIn("normalizeTrackingConfig", text)

    def test_discovery_initial_and_replay_validation_both_use_composed_tracking_gate(self) -> None:
        text = DISCOVERY.read_text(encoding="utf-8")
        self.assertEqual(text.count(DELTA_GATE), 2)
        self.assertEqual(text.count(TRACKING_VALIDATE), 2)

        initial = text.split("- name: Validate the expanded config before committing", 1)[1].split(
            "- name: Commit expanded tracking config", 1
        )[0]
        replay = text.split("regenerate_from_latest_main()", 1)[1].split(
            "if ! commit_current_config", 1
        )[0]
        for block in (initial, replay):
            self.assertIn(TRACKING_VALIDATE, block)
            self.assertIn(DELTA_GATE, block)
            self.assertIn("npm run validate:taxonomy", block)
            self.assertLess(block.index(TRACKING_VALIDATE), block.index(DELTA_GATE))
            self.assertLess(block.index(DELTA_GATE), block.index("npm run validate:taxonomy"))

    def _assert_manual_writer_uses_composed_tracking_gate(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        validation = text.split("- name: Validate changed tracking configuration", 1)[1].split(
            "- name: Commit and push only approved configuration files", 1
        )[0]
        self.assertEqual(text.count(TRACKING_VALIDATE), 1)
        self.assertIn(TRACKING_VALIDATE, validation)
        self.assertIn("npm run validate:taxonomy", validation)
        self.assertLess(validation.index(TRACKING_VALIDATE), validation.index("npm run validate:taxonomy"))

        # The validated worktree flows directly into the fail-closed base-SHA check
        # and commit step; there is no intervening writer step that can mutate it.
        after_validation = text.split("- name: Validate changed tracking configuration", 1)[1]
        self.assertLess(
            after_validation.index("- name: Commit and push only approved configuration files"),
            after_validation.index("- name: Summarize the public audit record"),
        )

    def test_single_manual_writer_uses_composed_clean_state_gate(self) -> None:
        self._assert_manual_writer_uses_composed_tracking_gate(MANUAL)

    def test_batch_manual_writer_uses_composed_clean_state_gate(self) -> None:
        self._assert_manual_writer_uses_composed_tracking_gate(BATCH)

    def test_capture_repository_persistence_checks_full_next_state_before_blobs(self) -> None:
        text = CAPTURE_GITHUB.read_text(encoding="utf-8")
        function = text.split("export async function commitTrackingCaptureRepositoryState", 1)[1]
        delta = "assertNoNewCompoundTrackingEntities(state.config, next.config);"
        full = "assertNoCompoundTrackingEntities(next.config);"
        blob = "const [configBlob, inboxBlob]"
        self.assertIn(delta, function)
        self.assertIn(full, function)
        self.assertIn(blob, function)
        self.assertLess(function.index(delta), function.index(full))
        self.assertLess(function.index(full), function.index(blob))


if __name__ == "__main__":
    unittest.main()
