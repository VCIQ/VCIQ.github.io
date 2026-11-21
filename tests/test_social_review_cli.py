"""Exercise real offline review CLI + SQLite; prohibit live I/O and subprocesses."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.social_review_fixtures import add, request, rows
from tests.test_social_contracts import fixture
from tools.social import review_cli
from tools.social.guard import protected_snapshot
from tools.social.review import ReviewStore
from tools.social.signal_store import SignalStore


class ReviewCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        self.runtime = fixture("runtime_config")
        self.runtime.update(stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        self.save("runtime.json", self.runtime)
        self.save("companies.json", {"companies": []})
        with SignalStore(self.root) as source: add(source)
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("live I/O forbidden")))

    def save(self, name, payload):
        path = self.root / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8"); path.chmod(0o600)
        return path

    def invoke(self, command, *more):
        argv = [command, "--state-dir", str(self.root), "--runtime-config", str(self.root / "runtime.json")]
        if command != "list": argv += ["--companies", "companies.json"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = review_cli.main(argv + list(more))
        payload = json.loads(stdout.getvalue() if code == 0 else stderr.getvalue())
        self.assertFalse(payload["liveExecuted"]); self.assertFalse(payload["publish"])
        return code, payload

    def sync(self):
        code, value = self.invoke("sync", "--apply"); self.assertEqual(code, 0)
        return value

    def item(self):
        return self.invoke("list")[1]["items"][0]["item"]

    def test_preview_does_not_create_review_database_or_pins(self):
        before = (self.root / "signals.sqlite3").read_bytes()
        code, result = self.invoke("sync")
        self.assertEqual(code, 0); self.assertEqual(result["candidateCount"], 1)
        self.assertFalse(result["applied"]); self.assertFalse((self.root / "reviews.sqlite3").exists())
        self.assertEqual(before, (self.root / "signals.sqlite3").read_bytes())

    def test_disabled_runtime_permits_only_explicit_offline_sync(self):
        self.assertFalse(self.runtime["enabled"]); self.sync()
        self.assertEqual(self.item()["status"], "pending")
        with SignalStore(self.root, readonly=True) as source: self.assertEqual(source.counts()["evidence_pins"], 1)

    def test_sync_list_decide_and_replay_end_to_end(self):
        self.sync(); command = request(self.item()); self.save("decision.json", command)
        self.assertEqual(self.invoke("decide", "--request", "decision.json")[0], 0)
        self.assertEqual(self.item()["status"], "pending")
        code, value = self.invoke("decide", "--request", "decision.json", "--apply")
        self.assertEqual(code, 0); self.assertTrue(value["applied"]); self.assertFalse(value["factVerified"])
        self.assertEqual(self.item()["promotionStatus"], "awaiting-primary-evidence")
        self.assertFalse(self.invoke("decide", "--request", "decision.json", "--apply")[1]["changed"])

    def test_decision_preview_does_not_change_either_database(self):
        self.sync(); self.save("decision.json", request(self.item()))
        before = {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}
        self.assertFalse(self.invoke("decide", "--request", "decision.json")[1]["applied"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")})

    def test_final_rejection_cannot_be_changed(self):
        self.sync(); self.save("decision.json", request(self.item(), "rejected"))
        self.assertEqual(self.invoke("decide", "--request", "decision.json", "--apply")[0], 0)
        self.save("opposite.json", request(self.item(), "accepted"))
        code, value = self.invoke("decide", "--request", "opposite.json", "--apply")
        self.assertEqual(code, 2); self.assertEqual(value["error"], "review_final_decision_conflict")

    def test_stale_source_refused_without_queue_rebuild(self):
        self.sync(); self.save("decision.json", request(self.item()))
        with SignalStore(self.root) as source: add(source, rows(at="2026-10-25T12:00:00Z", excerpt="新的测试证据"))
        code, value = self.invoke("decide", "--request", "decision.json", "--apply")
        self.assertEqual(code, 2); self.assertEqual(value["error"], "review_evidence_changed")

    def test_stale_queue_and_wrong_fingerprint_rejected(self):
        self.sync()
        for key, expected in (("seenQueueVersion", "review_queue_stale"), ("candidateFingerprint", "review_evidence_changed")):
            command = request(self.item()); command[key] = "f" * 64; self.save("decision.json", command)
            code, value = self.invoke("decide", "--request", "decision.json", "--apply")
            self.assertEqual(code, 2); self.assertEqual(value["error"], expected)

    def test_listing_bridge_does_not_modify_formal_queue(self):
        with SignalStore(self.root) as source: add(source, rows(at="2026-10-25T12:00:00Z", title="合成测试机器人尚未上市 IPO"))
        before = protected_snapshot(review_cli.ROOT)
        self.sync(); self.assertEqual(self.item()["leadType"], "listing")
        self.save("decision.json", request(self.item()))
        self.assertEqual(self.invoke("decide", "--request", "decision.json", "--apply")[0], 0)
        self.assertEqual(before, protected_snapshot(review_cli.ROOT))
        self.assertEqual(self.item()["promotionStatus"], "awaiting-primary-evidence")

    def test_history_retains_previous_decision(self):
        self.sync(); self.save("decision.json", request(self.item()))
        self.invoke("decide", "--request", "decision.json", "--apply")
        with SignalStore(self.root) as source: add(source, rows(at="2026-10-25T12:00:00Z", excerpt="新版"))
        self.sync()
        self.assertEqual(self.item()["status"], "pending")
        self.assertEqual(self.invoke("list", "--history")[1]["items"][0]["item"]["status"], "accepted")

    def test_missing_content_database_does_not_create_any_store(self):
        (self.root / "signals.sqlite3").unlink()
        code, _ = self.invoke("sync", "--apply")
        self.assertEqual(code, 2); self.assertFalse(list(self.root.glob("*.sqlite3")))

    def test_missing_review_database_is_not_created_by_list_or_decide(self):
        self.assertEqual(self.invoke("list")[0], 2)
        self.save("decision.json", fixture("decision_request"))
        self.assertEqual(self.invoke("decide", "--request", "decision.json", "--apply")[0], 2)
        self.assertFalse((self.root / "reviews.sqlite3").exists())

    def test_bad_request_and_sensitive_note_do_not_echo_input(self):
        self.sync()
        for value in ({}, {**request(self.item()), "note": "Cookie=PRIVATE_SECRET"}):
            self.save("decision.json", value)
            code, report = self.invoke("decide", "--request", "decision.json", "--apply")
            self.assertEqual(code, 2); self.assertNotIn("PRIVATE_SECRET", repr(report))
            self.assertEqual(self.item()["status"], "pending")

    def test_external_input_and_symlink_are_refused(self):
        self.sync(); real = self.save("decision.json", request(self.item()))
        (self.root / "link.json").symlink_to(real)
        for value in ("link.json", "../PRIVATE_PATH.json", "/PRIVATE_PATH.json"):
            code, report = self.invoke("decide", "--request", value, "--apply")
            self.assertEqual(code, 2); self.assertNotIn("PRIVATE_PATH", repr(report))

    def test_runtime_directory_mismatch_and_public_permissions(self):
        self.runtime["stateDir"] = str(self.root / "other"); self.save("runtime.json", self.runtime)
        self.assertEqual(self.invoke("sync")[0], 2)
        self.runtime["stateDir"] = str(self.root); self.save("runtime.json", self.runtime).chmod(0o644)
        self.assertEqual(self.invoke("sync")[0], 2)

    def test_real_company_registry_shape_is_supported_readonly(self):
        index = review_cli.registry_input(self.root, (review_cli.ROOT,))
        self.assertIsInstance(index, list); self.assertGreater(len(index), 0)
        self.assertEqual(set(index[0]), {"slug", "name", "aliases"})

    def test_custom_same_name_registry_does_not_bind_company(self):
        self.save("companies.json", {"companies": [{"slug": "one", "name": "合成测试机器人"}, {"slug": "two", "name": "合成测试机器人"}]})
        self.sync(); item = self.item()
        self.assertEqual(item["subject"]["resolution"], "ambiguous")
        self.assertIsNone(item["subject"]["companyId"])

    def test_list_invalid_pagination_rejected(self):
        self.sync()
        self.assertEqual(self.invoke("list", "--limit", "101")[0], 2)
        self.assertEqual(self.invoke("list", "--offset", "-1")[0], 2)

    def test_no_scheduler_or_public_output_created(self):
        self.sync(); self.save("decision.json", request(self.item()))
        self.invoke("decide", "--request", "decision.json", "--apply")
        self.assertFalse((self.root / "state.sqlite3").exists()); self.assertFalse((self.root / "public").exists())


if __name__ == "__main__": unittest.main()
