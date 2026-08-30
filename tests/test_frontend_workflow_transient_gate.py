from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_TEST = ROOT / ".github" / "workflows" / "web-test.yml"
PAGES = ROOT / ".github" / "workflows" / "pages.yml"


class FrontendWorkflowTransientGateTests(unittest.TestCase):
    def setUp(self):
        self.web_test = WEB_TEST.read_text(encoding="utf-8")
        self.pages = PAGES.read_text(encoding="utf-8")

    def test_main_only_transient_tracking_snapshot_failure_is_deferred(self):
        self.assertIn('EVENT_NAME: ${{ github.event_name }}', self.web_test)
        self.assertIn('if [ "$EVENT_NAME" = "push" ]; then', self.web_test)
        self.assertIn(
            "tracking configuration is newer than the article snapshot",
            self.web_test,
        )
        self.assertIn("missing crawler coverage record", self.web_test)
        self.assertIn("Frontend build deferred", self.web_test)

    def test_pull_requests_and_non_transient_build_failures_stay_strict(self):
        self.assertIn("build_status=${PIPESTATUS[0]}", self.web_test)
        self.assertIn("unexpected_tracking_errors", self.web_test)
        self.assertIn('exit "$build_status"', self.web_test)
        self.assertNotIn("continue-on-error", self.web_test)
        self.assertLess(
            self.web_test.index("npm run lint"),
            self.web_test.index("Build Pages candidate or defer a main-only tracking refresh"),
        )
        self.assertLess(
            self.web_test.index("npm run test:unit"),
            self.web_test.index("Build Pages candidate or defer a main-only tracking refresh"),
        )
        self.assertLess(
            self.web_test.index("npm run test:crawler"),
            self.web_test.index("Build Pages candidate or defer a main-only tracking refresh"),
        )

    def test_pull_requests_require_the_committed_source_registry_to_be_normalized(self):
        command = "python tools/tracking_source_governance.py --check"
        self.assertIn(command, self.web_test)
        self.assertLess(self.web_test.index(command), self.web_test.index("npm ci"))

    def test_frontend_and_pages_use_the_same_pending_refresh_signature(self):
        signature = "tracking configuration is newer than the article snapshot"
        companion = "missing crawler coverage record"
        self.assertIn(signature, self.web_test)
        self.assertIn(signature, self.pages)
        self.assertIn(companion, self.web_test)
        self.assertIn(companion, self.pages)


if __name__ == "__main__":
    unittest.main()
