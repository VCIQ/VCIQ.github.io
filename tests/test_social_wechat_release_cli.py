"""Exercise the saved HTML, SQLite review and public snapshot boundary offline."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.social_review_fixtures import request
from tests.test_social_wechat import NOW, ORIGINAL, fixture
from tools.social import wechat_release_cli as release
from tools.social.batch import build_batch
from tools.social.review import ReviewStore
from tools.social.review_cli import registry_input
from tools.social.signal_store import SignalStore
from tools.social.wechat_html_cli import import_html, records


class WechatReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.html = fixture("article.html")
        self.keyword = "人形机器人"
        for name in ("socket.create_connection", "socket.getaddrinfo", "urllib.request.urlopen"):
            self.enterContext(patch(name, side_effect=AssertionError("offline release must not access the network")))
        clock = self.enterContext(patch("tools.social.wechat_html_cli.datetime"))
        clock.now.return_value = NOW
        self.enterContext(patch("tools.social.wechat_html_cli.revision", return_value="a" * 40))
        import_html(self.root, (release.ROOT,), self.html.encode(), ORIGINAL, self.keyword, apply=True)
        with ReviewStore(self.root, readonly=True) as review:
            self.item = review.view()["items"][0]["item"]
        snapshot = self.root / "preview-baseline.json"
        snapshot.write_text("[]", encoding="utf-8")
        self.enterContext(patch.object(release, "SNAPSHOT", snapshot))

    def decide(self, decision):
        with SignalStore(self.root) as source, ReviewStore(self.root) as review:
            return review.decide(source, registry_input(self.root, (release.ROOT,)), request(self.item, decision), apply=True)

    def export(self, *, url=ORIGINAL, fingerprint=None):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = release.main(["--state-dir", str(self.root), "--candidate-key", self.item["candidateKey"],
                                   "--candidate-fingerprint", fingerprint or self.item["candidateFingerprint"],
                                   "--confirmed-source-url", url])
        if status:
            self.assertEqual(out.getvalue(), "")
        return status, json.loads(err.getvalue() if status else out.getvalue())

    def test_public_projection_is_allowlisted_readonly_and_deduplicated(self):
        self.assertFalse(self.decide("accepted")["factVerified"])
        before = {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}
        status, output = self.export()
        self.assertEqual(status, 0)
        (article,) = output
        self.assertEqual(set(article), {"url", "publisher", "title", "publishedAt"})
        self.assertEqual(article["url"], ORIGINAL)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}, before)
        release.SNAPSHOT.write_text(json.dumps(output), encoding="utf-8")
        self.assertEqual(self.export(), (0, output))

    def test_pending_and_rejected_cannot_be_exported(self):
        expected = (2, {"ok": False, "error": "wechat_release_accepted_revision_required"})
        self.assertEqual(self.export(), expected)
        self.decide("rejected")
        self.assertEqual(self.export(), expected)

    def test_confirmation_and_fingerprint_bind_the_exact_revision(self):
        self.decide("accepted")
        self.assertEqual(self.export(url=ORIGINAL + "_OTHER")[1]["error"], "wechat_release_source_confirmation_mismatch")
        self.assertEqual(self.export(fingerprint="f" * 64)[1]["error"], "wechat_release_accepted_revision_required")

    def test_changed_source_cannot_be_exported_before_queue_rebuild(self):
        self.decide("accepted")
        changed = self.html.replace("</p>", " 更新材料</p>", 1)
        jobs, receipts, observations = records(ORIGINAL, self.keyword, changed, "b" * 64, "a" * 40,
                                               NOW + timedelta(hours=1))
        with SignalStore(self.root) as source:
            source.import_batch(build_batch(jobs, receipts, observations, created_at=receipts[0]["completedAt"]))
        self.assertEqual(self.export()[1]["error"], "review_evidence_changed")

    def test_snapshot_rejects_extra_fields_and_duplicate_links(self):
        self.decide("accepted")
        row = self.export()[1][0]
        for invalid, error in (([{**row, "reviewer": "private"}], "wechat_release_fields"),
                               ([row, row], "wechat_release_duplicate_url")):
            release.SNAPSHOT.write_text(json.dumps(invalid), encoding="utf-8")
            self.assertEqual(self.export()[1]["error"], error)
