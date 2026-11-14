"""Real SQLite/CLI checks for gate changes; no real accounts or platform I/O."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.social_review_fixtures import add, rows, registry, request
from tests.test_social_contracts import fixture
from tools.social import review_cli
from tools.social.lead_builder import triage_report
from tools.social.review import ReviewStore
from tools.social.signal_store import SignalStore


class TriageHistoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("live I/O forbidden")))

    def seed(self, title="机器人入门科普"):
        with SignalStore(self.root) as source:
            doc = add(source, rows(title=title))
        return doc

    def old_gate(self):
        return patch("tools.social.lead_builder.classify_material", return_value={"disposition":"reviewable"})

    def test_filtered_pending_remains_in_history_with_pins_and_content(self):
        doc = self.seed()
        with SignalStore(self.root) as source, ReviewStore(self.root) as review:
            with self.old_gate(): review.materialize(source, registry())
            old = review.view()["items"][0]
            before = source.counts()
            result = review.materialize(source, registry())
            self.assertEqual(result["candidateCount"], 0)
            self.assertEqual(review.view()["total"], 0)
            history = review.view(history=True)["items"][0]
            self.assertEqual(history["item"]["candidateKey"], old["item"]["candidateKey"])
            self.assertEqual(history["item"]["status"], "pending")
            self.assertIsNone(history["decision"])
            self.assertEqual(source.counts(), before)
            self.assertEqual(source.get_signal(doc["signalId"])["latest"], doc)

    def test_preexisting_acceptance_is_not_rewritten_as_rejection(self):
        self.seed()
        with SignalStore(self.root) as source, ReviewStore(self.root) as review:
            with self.old_gate():
                review.materialize(source, registry())
                command = request(review.view()["items"][0]["item"])
                review.decide(source, registry(), command, apply=True)
            before = [tuple(row) for row in review.db.execute("SELECT * FROM decisions")]
            review.materialize(source, registry())
            after = [tuple(row) for row in review.db.execute("SELECT * FROM decisions")]
            self.assertEqual(before, after)
            self.assertEqual(review.view(history=True)["items"][0]["item"]["status"], "accepted")

    def test_retained_event_keeps_revision_and_existing_decision(self):
        self.seed("机器人公司完成A轮融资")
        with SignalStore(self.root) as source, ReviewStore(self.root) as review:
            with self.old_gate():
                review.materialize(source, registry())
                command = request(review.view()["items"][0]["item"])
                review.decide(source, registry(), command, apply=True)
            old = review.view()["items"][0]
            review.materialize(source, registry())
            new = review.view()["items"][0]
            self.assertEqual(old, new)
            self.assertEqual(new["item"]["status"], "accepted")

    def test_aggregate_counts_are_readonly_and_conserve_signals(self):
        self.seed()
        path = self.root / "signals.sqlite3"; before = path.read_bytes()
        with SignalStore(self.root, readonly=True) as source:
            result = triage_report(source, registry())
        self.assertEqual(result["backgroundSignals"], 1)
        self.assertEqual(result["totalSignals"], sum(result[k] for k in ("reviewableSignals","backgroundSignals","unrelatedSignals")))
        self.assertEqual(result["candidateCount"], 0)
        self.assertEqual(before, path.read_bytes())
        self.assertFalse((self.root / "reviews.sqlite3").exists())

    def test_cli_triage_is_nonmutating_without_review_store(self):
        self.seed()
        value = fixture("runtime_config")
        value.update(stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        for name, payload in (("runtime.json",value),("companies.json",{"companies":[]})):
            path=self.root/name;path.write_text(json.dumps(payload));path.chmod(0o600)
        before = {p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        stdout,stderr=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            status=review_cli.main(["triage","--state-dir",str(self.root),"--runtime-config",str(self.root/"runtime.json"),"--companies","companies.json"])
        self.assertEqual(status,0,stderr.getvalue())
        result=json.loads(stdout.getvalue())
        self.assertFalse(result["liveExecuted"]);self.assertFalse(result["writesPerformed"])
        self.assertEqual(result["reasonCounts"],{"EXPLAINER_WITHOUT_EVENT_CUE":1})
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()})
        self.assertNotIn("机器人",stdout.getvalue())


if __name__ == "__main__": unittest.main()
