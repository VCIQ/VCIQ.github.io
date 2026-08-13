from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pages.yml"
CONTROL_PLANE_PATH = ROOT / "tools" / "run_pipeline.py"
REFRESH_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "scheduled-sync.yml"
TRACKING_VALIDATOR_PATH = ROOT / "scripts" / "validate-tracking-snapshot.mjs"


class PagesWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.refresh_workflow = REFRESH_WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.tracking_validator = TRACKING_VALIDATOR_PATH.read_text(encoding="utf-8")
        cls.control_plane = CONTROL_PLANE_PATH.read_text(encoding="utf-8")
        cls.lines = [line.strip() for line in cls.workflow.splitlines()]
        cls.runtime_workflow = cls.workflow.split("permissions:", 1)[1]

    def test_pages_build_only_observes_and_validates_public_build_inputs(self):
        python_commands = [
            line for line in self.lines if line.startswith("python tools/")
        ]
        self.assertEqual(
            python_commands,
            [
                "python tools/run_pipeline.py check",
                "python tools/reconcile_entity_resolution.py --check",
                "python tools/company_profile_refresh_queue.py --check",
                "python tools/crawl_articles.py --validate-only",
                "python tools/validate_eastmoney_snapshot.py",
                "python tools/run_pipeline.py refresh \\",
                "python tools/run_pipeline.py build-provenance \\",
            ],
        )
        self.assertNotIn("company_candidate_review_queue.json", self.runtime_workflow)
        self.assertNotIn("company_candidate_onboarding_state.json", self.runtime_workflow)
        self.assertNotIn("apply_manual_company_trust.py", self.runtime_workflow)
        self.assertNotIn("build_resolved_company_candidates.py", self.runtime_workflow)
        self.assertNotIn("public/data/company_candidates.json", self.runtime_workflow)
        self.assertNotIn("Reconcile derived public data", self.runtime_workflow)
        self.assertNotIn("tools/run_pipeline.py finalize", self.runtime_workflow)

    def test_control_plane_only_pushes_do_not_start_pages(self):
        ignored = (
            "config/user_tracking.json",
            "config/company_candidate_review_queue.json",
            "config/company_candidate_onboarding_state.json",
            "config/company_candidate_decisions.json",
            "config/tracking_capture_inbox.json",
            "config/entity_resolution_decisions.json",
        )
        self.assertIn("paths-ignore:", self.workflow)
        for path in ignored:
            with self.subTest(path=path):
                self.assertIn(f"      - {path}", self.workflow)

    def test_transient_fixed_point_states_defer_pages_without_weakening_validation(self):
        self.assertIn("name: Assess publication readiness", self.workflow)
        self.assertIn("id: publication_readiness", self.workflow)
        self.assertIn("ready: ${{ steps.publication_readiness.outputs.ready }}", self.workflow)
        self.assertIn(
            "entity resolution reconciliation is not at a fixed point",
            self.workflow,
        )
        self.assertIn(
            "tracking configuration is newer than the article snapshot",
            self.workflow,
        )
        self.assertIn("missing crawler coverage record", self.workflow)
        self.assertIn("ready=false", self.workflow)
        self.assertIn("::notice title=Pages deferred::", self.workflow)
        self.assertIn(
            "::error title=Pages readiness check failed::",
            self.workflow,
        )
        self.assertIn("if: needs.build.outputs.ready == 'true'", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("if: steps.publication_readiness.outputs.ready == 'true'"),
            9,
        )

    def test_tracking_config_is_refreshed_before_pages_can_publish_it(self):
        self.assertIn("      - config/user_tracking.json", self.refresh_workflow)
        self.assertIn("      - config/user_tracking.json", self.workflow)
        self.assertIn(
            "Pages must wait for that workflow to commit the matching public snapshot",
            self.workflow,
        )
        self.assertIn("-f publish_after_reconciliation=true", self.refresh_workflow)
        self.assertIn("run: npm run build:pages", self.workflow)
        self.assertNotIn("ALLOW_INCOMPLETE_TRACKING_COVERAGE", self.workflow)

    def test_terminal_deploy_can_handoff_to_research_without_creating_a_refresh_race(self):
        self.assertIn("run_research_after_deploy:", self.workflow)
        self.assertIn("type: boolean", self.workflow)
        self.assertIn("default: false", self.workflow)
        self.assertIn("actions: write", self.workflow)
        deploy = self.workflow.split("  deploy:", 1)[1]
        deployment = deploy.index("uses: actions/deploy-pages@v4")
        research_command = (
            'gh workflow run research-agent-v1.yml --ref main --repo "$GITHUB_REPOSITORY"'
        )
        research = deploy.index(research_command)
        self.assertLess(deployment, research)
        self.assertIn("inputs.run_research_after_deploy == true", deploy)
        self.assertIn(research_command, deploy)
        self.assertNotIn("uses: actions/checkout@", deploy)

    def test_tracking_hash_mismatch_exposes_only_safe_short_hashes(self):
        self.assertIn("expected=${expectedHash.slice(0, 12)}", self.tracking_validator)
        self.assertIn("actual=${actualHash.slice(0, 12)}", self.tracking_validator)
        self.assertNotIn("JSON.stringify(config)", self.tracking_validator)

    def test_pages_build_is_pinned_to_the_event_commit(self):
        self.assertIn("ref: ${{ github.sha }}", self.workflow)
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "${GITHUB_SHA}"', self.workflow)
        self.assertEqual(
            self.workflow.count("git diff --exit-code -- config public/data"),
            2,
        )

    def test_tracking_coverage_cannot_be_bypassed(self):
        self.assertNotIn("ALLOW_INCOMPLETE_TRACKING_COVERAGE", self.workflow)
        self.assertIn("run: npm run build:pages", self.workflow)
        self.assertIn("node scripts/validate-tracking-snapshot.mjs", self.workflow)

    def test_deployed_artifact_records_source_sha_and_control_plane_hashes(self):
        self.assertIn('"sourceSha": git_head(root)', self.control_plane)
        self.assertIn("--output out/build-provenance.json", self.workflow)
        self.assertIn("--lineage out/data/data_lineage.json", self.workflow)
        self.assertIn("--health out/data/pipeline_health.json", self.workflow)
        self.assertIn("uses: actions/upload-pages-artifact@v3", self.workflow)


if __name__ == "__main__":
    unittest.main()
