from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
TRACKING_CONFIG = "config/user_tracking.json"
COMPOSED_GATE = "npm run validate:tracking"

EXPECTED_DIRECT_WRITERS = {
    "manual-tracking.yml",
    "manual-tracking-batch.yml",
    "scheduled-sync.yml",
    "tracking-discovery.yml",
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

    def test_entity_mutating_writers_reach_the_composed_clean_state_gate(self) -> None:
        for name in EXPECTED_DIRECT_WRITERS - {"scheduled-sync.yml"}:
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertIn(COMPOSED_GATE, text, name)

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


if __name__ == "__main__":
    unittest.main()
