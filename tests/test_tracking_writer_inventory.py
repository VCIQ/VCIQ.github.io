from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
TRACKING_CONFIG = "config/user_tracking.json"
COMPOSED_GATE = "npm run validate:tracking"
PYTHON_GATE = "python tools/tracking_entity_integrity.py"

EXPECTED_DIRECT_WRITERS = {
    "company-candidate-discovery.yml",
    "manual-tracking.yml",
    "manual-tracking-batch.yml",
    "register-semiconductor-media-sources.yml",
    "scheduled-sync.yml",
    "tracking-discovery.yml",
}
NPM_GATED_ENTITY_WRITERS = {
    "manual-tracking.yml",
    "manual-tracking-batch.yml",
    "tracking-discovery.yml",
}
PYTHON_GATED_ENTITY_WRITERS = {"company-candidate-discovery.yml"}
SOURCE_ONLY_WRITERS = {
    "register-semiconductor-media-sources.yml",
    "scheduled-sync.yml",
}


def _is_direct_tracking_config_writer(text: str) -> bool:
    if TRACKING_CONFIG not in text:
        return False

    # Explicit staging of user_tracking.json, including multiline `git add \\` blocks.
    for match in re.finditer(r"\bgit\s+add\b", text):
        window = text[match.start() : match.start() + 1800]
        if TRACKING_CONFIG in window:
            return True

    # Full refresh stages a named governance array after defining user_tracking.json
    # in that array; the definition and staging are intentionally far apart.
    if (
        "GOVERNANCE_PATHS=(" in text
        and TRACKING_CONFIG in text
        and '"${GOVERNANCE_PATHS[@]}"' in text
    ):
        return True

    # Broad staging/commit forms are dangerous when a workflow also references the
    # tracking config; treat them as writers so they cannot silently bypass review.
    broad_write_markers = ("git add -A", "git add .", "git commit -a")
    return any(marker in text for marker in broad_write_markers)


class TrackingWriterInventoryTests(unittest.TestCase):
    def test_all_direct_user_tracking_workflow_writers_are_reviewed(self) -> None:
        writers = {
            path.name
            for path in WORKFLOWS.glob("*.yml")
            if _is_direct_tracking_config_writer(path.read_text(encoding="utf-8"))
        }
        self.assertEqual(writers, EXPECTED_DIRECT_WRITERS)
        self.assertEqual(
            NPM_GATED_ENTITY_WRITERS | PYTHON_GATED_ENTITY_WRITERS | SOURCE_ONLY_WRITERS,
            EXPECTED_DIRECT_WRITERS,
        )

    def test_node_entity_mutating_writers_reach_composed_clean_state_gate(self) -> None:
        for name in NPM_GATED_ENTITY_WRITERS:
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertIn(COMPOSED_GATE, text, name)

    def test_company_reconciliation_hard_gates_initial_and_replay_states(self) -> None:
        text = (WORKFLOWS / "company-candidate-discovery.yml").read_text(encoding="utf-8")
        self.assertIn("tools/tracking_entity_integrity.py", text)
        self.assertGreaterEqual(text.count(PYTHON_GATE), 3)

        commit_block = text.split("- name: Commit resolved tracking and private candidate evidence", 1)[1]
        first_add = commit_block.index('git add "${changed_paths[@]}"')
        self.assertLess(commit_block.index(PYTHON_GATE), first_add)

        replay = commit_block.split("for attempt in 1 2 3; do", 1)[1]
        self.assertLess(replay.index("python tools/reconcile_entity_resolution.py --check"), replay.index(PYTHON_GATE))
        self.assertLess(replay.index(PYTHON_GATE), replay.index('git add "${changed_paths[@]}"'))

    def test_scheduled_sync_is_source_governance_only_before_staging_config(self) -> None:
        text = (WORKFLOWS / "scheduled-sync.yml").read_text(encoding="utf-8")
        self.assertIn(TRACKING_CONFIG, text)
        self.assertIn("python tools/tracking_source_governance.py", text)
        self.assertIn("python tools/tracking_source_governance.py --check", text)
        self.assertIn('"${GOVERNANCE_PATHS[@]}"', text)

        stage = text.index('git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}" "${GOVERNANCE_PATHS[@]}"')
        before_stage = text[:stage]
        self.assertGreater(before_stage.rfind("python tools/tracking_source_governance.py\n"), -1)
        self.assertGreater(before_stage.rfind("python tools/tracking_source_governance.py --check"), -1)

    def test_semiconductor_registration_is_explicitly_source_only(self) -> None:
        text = (WORKFLOWS / "register-semiconductor-media-sources.yml").read_text(encoding="utf-8")
        self.assertIn("python tools/add_semiconductor_media_sources.py", text)
        self.assertIn("git add config/user_tracking.json", text)
        self.assertNotIn("reconcile_entity_resolution.py", text)


if __name__ == "__main__":
    unittest.main()
