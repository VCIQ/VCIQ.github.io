from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "manual-tracking.yml"
ADMINS = ROOT / "config" / "tracking_admins.json"
INTENTS = ROOT / "config" / "tracking_intents.json"
DOC = ROOT / "docs" / "manual-tracking-admin.md"


class ManualTrackingWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_entry_is_manual_only_and_covers_all_five_object_types(self) -> None:
        trigger = self.text.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("  push:", trigger)
        self.assertNotIn("  schedule:", trigger)
        self.assertIn("options: [validate, apply]", trigger)
        self.assertIn(
            "options: [technology, track, company, person, source]",
            trigger,
        )

    def test_validate_is_read_only_and_apply_alone_gets_write_permissions(self) -> None:
        self.assertIn("permissions: {}", self.text)
        validate = self.text.split("  validate:\n", 1)[1].split("\n  apply:\n", 1)[0]
        apply = self.text.split("  apply:\n", 1)[1]
        self.assertIn("permissions:\n      contents: read", validate)
        self.assertNotIn("contents: write", validate)
        apply_job = apply.split("\n  handoff:\n", 1)[0]
        handoff = apply.split("\n  handoff:\n", 1)[1]
        self.assertIn("permissions:\n      contents: write", apply_job)
        self.assertNotIn("actions: write", apply_job)
        self.assertIn("permissions:\n      actions: write", handoff)
        self.assertNotIn("contents: write", handoff)
        self.assertIn("--mode validate", validate)
        self.assertNotIn("git push", validate)

    def test_repository_branch_event_and_both_actors_are_guarded(self) -> None:
        self.assertIn("EXPECTED_REPOSITORY: VCIQ/VCIQ.github.io", self.text)
        self.assertIn('test "$ACTUAL_REPOSITORY" = "$EXPECTED_REPOSITORY"', self.text)
        self.assertIn('test "$ACTUAL_REF" = "refs/heads/main"', self.text)
        self.assertIn('test "$ACTUAL_EVENT" = "workflow_dispatch"', self.text)
        self.assertIn("github.actor", self.text)
        self.assertIn("github.triggering_actor", self.text)
        self.assertIn('Path("config/tracking_admins.json")', self.text)
        self.assertGreaterEqual(self.text.count("environment: tracking-admin"), 2)

    def test_inputs_are_passed_through_environment_not_interpolated_in_shell(self) -> None:
        for expression in (
            "${{ inputs.object_type }}",
            "${{ inputs.name }}",
            "${{ inputs.target_tracks }}",
            "${{ inputs.keywords }}",
            "${{ inputs.source_url }}",
            "${{ inputs.note }}",
        ):
            self.assertIn(expression, self.text)

        for run_block in self.text.split("run: |")[1:]:
            shell = run_block.split("\n      - ", 1)[0].split("\n  handoff:", 1)[0]
            self.assertNotIn("${{ inputs.", shell)

        self.assertIn('--kind "$OBJECT_TYPE"', self.text)
        self.assertIn('--note "$NOTE"', self.text)
        self.assertIn('--actor "$ACTOR"', self.text)
        self.assertIn('--triggering-actor "$TRIGGERING_ACTOR"', self.text)

    def test_apply_uses_shared_fifo_writer_queue_and_main_checkout(self) -> None:
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", self.text)
        self.assertIn("queue: max", self.text)
        self.assertNotIn("cancel-in-progress:", self.text)
        apply = self.text.split("  apply:\n", 1)[1]
        validate = self.text.split("  validate:\n", 1)[1].split("\n  apply:\n", 1)[0]
        self.assertNotIn("concurrency:", validate)
        checkout = apply.split("- uses: actions/checkout@v4", 1)[1].split("- uses:", 1)[0]
        self.assertIn("ref: main", checkout)
        self.assertIn("fetch-depth: 0", checkout)
        self.assertIn("persist-credentials: false", checkout)

    def test_apply_stages_only_the_three_approved_config_files(self) -> None:
        commit = self.text.split(
            "- name: Commit and push only approved configuration files", 1
        )[1].split("- name:", 1)[0]
        allowed = (
            "config/tracking_intents.json",
            "config/user_tracking.json",
            "config/tracking_capture_inbox.json",
        )
        for path in allowed:
            self.assertIn(path, commit)
        self.assertNotIn("git add -A", commit)
        self.assertNotIn("git add .", commit)
        self.assertNotIn("git commit -a", commit)

    def test_apply_validates_manual_and_automatic_feedback_paths(self) -> None:
        apply = self.text.split("  apply:\n", 1)[1].split("\n  handoff:\n", 1)[0]
        for suite in (
            "tests.test_manual_tracking",
            "tests.test_manual_tracking_workflow",
            "tests.test_tracking_manual_feedback",
            "tests.test_expand_tracking_entities",
        ):
            self.assertIn(suite, apply)
        self.assertIn("tools/expand_tracking_entities.py", apply)
        self.assertIn("tools/strict_tracking_config.py", apply)

    def test_apply_reads_the_single_top_level_cli_report(self) -> None:
        apply_step = self.text.split("- name: Apply the authorized request", 1)[1].split(
            "- name: Validate changed tracking configuration", 1
        )[0]
        self.assertIn("report = json.loads(", apply_step)
        self.assertIn('"changed" not in report', apply_step)
        self.assertNotIn("raw_decode", apply_step)
        self.assertNotIn("reports[-1]", apply_step)

    def test_apply_fails_closed_when_remote_main_advances(self) -> None:
        commit = self.text.split(
            "- name: Commit and push only approved configuration files", 1
        )[1].split("- name:", 1)[0]
        self.assertEqual(commit.count("git fetch origin main"), 2)
        self.assertEqual(
            commit.count('test "$(git rev-parse origin/main)" = "$BASE_SHA"'),
            2,
        )
        self.assertIn("git push origin HEAD:main", commit)
        for unsafe in ("--force", "pull --rebase", "rebase origin", "reset --hard"):
            self.assertNotIn(unsafe, commit)

    def test_robot_push_has_explicit_downstream_handoffs(self) -> None:
        self.assertIn("actions: write", self.text)
        self.assertIn("GH_REPO: ${{ github.repository }}", self.text)
        self.assertIn("gh workflow run scheduled-sync.yml --ref main", self.text)
        self.assertIn(
            "gh workflow run company-candidate-discovery.yml --ref main",
            self.text,
        )
        self.assertIn(
            "gh workflow run tracking-discovery.yml --ref main -f mode=full",
            self.text,
        )

    def test_public_repository_confidentiality_warning_is_prominent(self) -> None:
        self.assertIn("repository is public", self.text)
        self.assertIn("never", self.text)
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("本仓库是公开仓库", doc)
        self.assertIn("不要填写密钥", doc)
        self.assertIn("公开页面继续只保留“收藏”和“分享”", doc)

    def test_admin_and_intent_registries_start_with_explicit_schemas(self) -> None:
        admins = json.loads(ADMINS.read_text(encoding="utf-8"))
        intents = json.loads(INTENTS.read_text(encoding="utf-8"))
        self.assertEqual(admins["schemaVersion"], 1)
        self.assertIn("IamVC", admins["actors"])
        self.assertEqual(intents, {
            "schemaVersion": 1,
            "updatedAt": "",
            "entities": [],
            "memberships": [],
        })


if __name__ == "__main__":
    unittest.main()
