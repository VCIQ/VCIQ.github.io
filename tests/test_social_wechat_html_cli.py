"""Operator HTML stays offline and carries its own provenance in private state."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.test_social_wechat import NOW, ORIGINAL, fixture
from tools.social.batch import ROOT, BatchError, build_batch, read_batch, write_private
from tools.social.contracts import ContractError, digest, validate
from tools.social.wechat_html_cli import main, records


class WechatHtmlTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.html = fixture("article.html")
        write_private(self.root, "article.html", self.html.encode(), (ROOT,))
        self.args = ["--state-dir", str(self.root), "--html", "article.html",
                     "--url", ORIGINAL, "--keyword", "人形机器人"]
        for target in ("socket.create_connection", "socket.getaddrinfo", "urllib.request.urlopen"):
            guard = patch(target, side_effect=AssertionError("offline import must not access the network"))
            guard.start()
            self.addCleanup(guard.stop)
        clock = patch("tools.social.wechat_html_cli.datetime")
        clock.start().now.return_value = NOW
        self.addCleanup(clock.stop)
        revision = patch("tools.social.wechat_html_cli.revision", return_value="a" * 40)
        revision.start()
        self.addCleanup(revision.stop)

    def call(self, *options, args=None):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([*(self.args if args is None else args), *options])
        return code, json.loads(out.getvalue() if not code else err.getvalue())

    def test_preview_writes_nothing(self):
        code, summary = self.call()
        self.assertEqual(code, 0)
        self.assertEqual(summary["source"], "operator-html")
        self.assertEqual(summary["accessStatus"], "unverified")
        self.assertGreater(summary["candidateCount"], 0)
        self.assertFalse(summary["writesPerformed"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["article.html"])

    def test_apply_seals_provenance_and_is_idempotent(self):
        code, first = self.call("--apply")
        self.assertEqual(code, 0)
        self.assertEqual(first["insertedSignals"], 1)
        self.assertEqual(first["reviewCandidateCount"], first["candidateCount"])
        (folder,) = (self.root / "operator-html").iterdir()
        batch = read_batch(self.root, folder.relative_to(self.root).as_posix())
        (job,) = batch.records("jobs.jsonl")
        (receipt,) = batch.records("query_receipts.jsonl")
        self.assertEqual((job["provider"], job["operation"]), ("operator-html", "import-html"))
        self.assertEqual(receipt["counts"]["searchItems"], 0)
        self.assertEqual(receipt["pageReceipts"], [])
        code, second = self.call("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["insertedSignals"], 0)
        self.assertEqual(second["queueVersion"], first["queueVersion"])

    def test_refuses_scheduler_state_without_creating_a_lock(self):
        write_private(self.root, "state.sqlite3", b"synthetic", (ROOT,))
        code, result = self.call("--apply")
        self.assertEqual((code, result["error"]), (2, "operator_html_separate_state_required"))
        self.assertFalse((self.root / "locks").exists())

    def test_batch_rejects_a_claim_of_verified_online_access(self):
        jobs, receipts, observations = records(ORIGINAL, "人形机器人", self.html, "b" * 64, "a" * 40, NOW)
        observations[0]["accessStatus"] = "verified_public"
        with self.assertRaisesRegex(BatchError, "operator_html_access_status"):
            build_batch(jobs, receipts, observations, created_at=receipts[0]["completedAt"])

    def test_operator_job_cannot_be_scheduled(self):
        (jobs, receipts, _) = records(ORIGINAL, "人形机器人", self.html, "b" * 64, "a" * 40, NOW)
        plan = {"schemaVersion": 1, "kind": "job_plan", "generatedAt": receipts[0]["startedAt"],
                "vciqCommit": "a" * 40, "configHash": "b" * 64,
                "stats": {"registeredQueries": 1, "eligibleQueries": 1, "excludedQueries": 0,
                          "selectedJobs": 1, "deferredQueries": 0}, "jobs": jobs}
        plan["planId"] = digest({k: v for k, v in plan.items() if k != "generatedAt"})
        with self.assertRaisesRegex(ContractError, "plan_requires_search"):
            validate(plan, expected_kind="job_plan")

    def test_rejects_verification_page_without_importing_it(self):
        write_private(self.root, "verification.html", fixture("verification.html").encode(), (ROOT,))
        args = [*self.args, "--html", "verification.html"]
        code, result = self.call(args=args)
        self.assertEqual((code, result["error"]), (2, "VERIFICATION_REQUIRED"))
        self.assertFalse((self.root / "signals.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
