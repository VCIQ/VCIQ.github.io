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

HARD_GATE = "npm run validate:tracking-entities"
DELTA_GATE = "node --import tsx scripts/validate-new-tracking-entities.ts --base-ref HEAD"


class TrackingCleanStateWorkflowTests(unittest.TestCase):
    def test_pages_build_enforces_zero_compound_state_before_taxonomy(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        scripts = package["scripts"]
        self.assertEqual(
            scripts["validate:tracking-entities"],
            "node --import tsx scripts/validate-zero-tracking-compounds.ts",
        )
        build = scripts["build:pages"]
        self.assertIn("npm run validate:tracking", build)
        self.assertIn(HARD_GATE, build)
        self.assertIn("npm run validate:taxonomy", build)
        self.assertLess(build.index("npm run validate:tracking"), build.index(HARD_GATE))
        self.assertLess(build.index(HARD_GATE), build.index("npm run validate:taxonomy"))

    def test_clean_state_validator_reads_raw_config_without_runtime_normalization(self) -> None:
        text = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn('const TRACKING_CONFIG_PATH = "config/user_tracking.json"', text)
        self.assertIn('argumentValue("--worktree", ".")', text)
        self.assertIn("splitCompoundTrackingEntityName", text)
        self.assertNotIn("normalizeTrackingConfig", text)

    def test_discovery_commit_helper_hard_gates_every_commit(self) -> None:
        text = DISCOVERY.read_text(encoding="utf-8")
        self.assertEqual(text.count(DELTA_GATE), 2)
        self.assertEqual(text.count(HARD_GATE), 1)
        helper = text.split("commit_current_config() {", 1)[1].split(
            "regenerate_from_latest_main()", 1
        )[0]
        self.assertIn(HARD_GATE, helper)
        self.assertLess(helper.index(HARD_GATE), helper.index("git add"))
        self.assertGreaterEqual(text.count("commit_current_config"), 3)

    def _assert_manual_writer_hard_gate(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        validation = text.split("- name: Validate changed tracking configuration", 1)[1].split(
            "- name: Commit and push only approved configuration files", 1
        )[0]
        commit = text.split("- name: Commit and push only approved configuration files", 1)[1].split(
            "- name: Summarize the public audit record", 1
        )[0]

        self.assertIn(HARD_GATE, validation)
        self.assertLess(validation.index(HARD_GATE), validation.index("npm run validate:taxonomy"))
        self.assertIn(HARD_GATE, commit)
        self.assertLess(commit.index(HARD_GATE), commit.index("git add --"))
        self.assertEqual(text.count(HARD_GATE), 2)

    def test_single_manual_writer_hard_gates_validation_and_commit(self) -> None:
        self._assert_manual_writer_hard_gate(MANUAL)

    def test_batch_manual_writer_hard_gates_validation_and_commit(self) -> None:
        self._assert_manual_writer_hard_gate(BATCH)

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
