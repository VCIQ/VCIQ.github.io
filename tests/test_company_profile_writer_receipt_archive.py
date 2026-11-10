"""Offline fault injection for shared GitHub reservations and S3 receipt versions."""
from __future__ import annotations

import hashlib
import io
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from tests.test_company_profile_writer_crawl_observer import Fixture, SHA, TIMES
from tests.test_company_profile_writer_crawl_runner import OfflineRepo
from tools.company_profile_writer_crawl_observer import (
    ObservedCrawlError, observe_selected_company_crawls,
)
from tools.company_profile_writer_pr_gate import SMOKE_BASE_BRANCH
from tools.company_profile_writer_pr_handoff import GitHubCli, RESERVATION, SMOKE_RESERVATION
from tools.company_profile_writer_receipt_archive import (
    CrossJobReceiptArchive, S3ReceiptStore, inspect_archived_run,
)
from tools.company_profile_writer_receipt_journal import JournalError, RunReceiptJournal


class ObjectMissing(Exception):
    response = {
        "ResponseMetadata": {"HTTPStatusCode": 404},
        "Error": {"Code": "NoSuchKey"},
    }


class FakeS3:
    def __init__(self):
        self.lock = threading.Lock()
        self.objects = {}
        self.puts = []
        self.gets = []
        self.lose_ack = None
        self.fail_before_put = None
        self.ignore_lock = False
        self.missing_version = False
        self.on_put = None

    def put_object(self, **request):
        key = request["Key"]
        name = key.rsplit("/", 1)[-1]
        with self.lock:
            self.puts.append(request)
            if request["IfNoneMatch"] != "*" or key in self.objects:
                raise RuntimeError("conditional write rejected")
            if name == self.fail_before_put:
                raise TimeoutError("synthetic request failure")
            version = str(len(self.objects) + 1)
            self.objects[key] = (version, request)
        if self.on_put is not None:
            self.on_put(name)
        if name == self.lose_ack:
            raise TimeoutError("synthetic response lost after commit")
        return {"VersionId": None if self.missing_version else version}

    def get_object(self, **request):
        self.gets.append(request)
        if request["Key"] not in self.objects:
            raise ObjectMissing()
        version, stored = self.objects[request["Key"]]
        if request.get("VersionId", version) != version:
            raise ObjectMissing()
        return {
            "VersionId": version,
            "Body": io.BytesIO(stored["Body"]),
            "ChecksumSHA256": stored["ChecksumSHA256"],
            "ObjectLockMode": "GOVERNANCE" if self.ignore_lock else stored["ObjectLockMode"],
            "ObjectLockRetainUntilDate": stored["ObjectLockRetainUntilDate"],
        }


class SharedGitHub:
    def __init__(self, *, base=SHA, smoke=False):
        self.base = base
        self.base_branch = SMOKE_BASE_BRANCH if smoke else "main"
        self.reservation_ref = SMOKE_RESERVATION if smoke else RESERVATION
        self.anchor = None
        self.lock = threading.Lock()
        self.race = None
        self.creates = 0
        self.lose_ack = False

    def base_sha(self):
        return self.base

    def open_proposals(self):
        return []

    def candidate_branches(self):
        return [self.reservation_ref] if self.anchor else []

    def create_reservation_commit(self, base, manifest_digest):
        return hashlib.sha1(f"{base}:{manifest_digest}".encode()).hexdigest()

    def create_ref(self, ref, sha):
        if self.race:
            self.race.wait(timeout=5)
        with self.lock:
            self.creates += 1
            if ref != self.reservation_ref or self.anchor:
                raise RuntimeError("ref conflict")
            self.anchor = sha
        if self.lose_ack:
            raise TimeoutError("synthetic ref created but response lost")

    def reservation_sha(self):
        return self.anchor


class ReceiptArchiveTests(unittest.TestCase):
    def setUp(self):
        self.s3 = FakeS3()
        self.store = S3ReceiptStore(self.s3, bucket="review-fixture", owner="000000000000")
        self.github = SharedGitHub()

    def journal(self, folder, github=None):
        archive = CrossJobReceiptArchive(github or self.github, self.store, authorized=True)
        return RunReceiptJournal(Path(folder), authorized=True, archive=archive)

    def observe(self, folder, run_id="fixture-run", *, slugs=("alpha",), github=None, **kwargs):
        fixture = Fixture(slugs)
        self.addCleanup(fixture.close)
        fixture.ticks = ([TIMES[0], TIMES[1], TIMES[1], TIMES[2], TIMES[-1]]
                         if len(slugs) == 1 else [
                             TIMES[0], TIMES[1], TIMES[1], TIMES[2],
                             TIMES[3], TIMES[3], TIMES[4], TIMES[5],
                         ])
        result = fixture.observe(run_id=run_id, journal=self.journal(folder, github), **kwargs)
        return fixture, result

    def inspect(self, run_id="fixture-run", scope="production"):
        return inspect_archived_run(self.store, run_id=run_id, scope=scope)

    def test_remote_records_survive_loss_of_local_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            _, result = self.observe(folder)
        outcome = self.inspect()
        self.assertTrue(result["externalArchiveRecorded"])
        self.assertEqual(outcome["state"], "recorded")
        self.assertEqual(outcome["companies"], {"alpha": "verified_receipt"})
        self.assertEqual(outcome["reservation"]["anchorSha"], self.github.anchor)
        self.assertFalse(outcome["automaticResumeAuthorized"])
        self.assertFalse(outcome["markProcessedAuthorized"])
        self.assertFalse(outcome["mergeAuthorized"])
        self.assertFalse(outcome["publicationAuthorized"])
        self.assertEqual(len(outcome["archiveVersions"]), 5)
        self.assertEqual(len([request for request in self.s3.gets if "VersionId" in request]), 5)
        for put in self.s3.puts:
            self.assertEqual(put["ObjectLockMode"], "COMPLIANCE")
            self.assertEqual(put["ExpectedBucketOwner"], "000000000000")
            self.assertGreater(put["ObjectLockRetainUntilDate"], datetime.now(UTC) + timedelta(days=364))
            self.assertNotIn(b"alpha.example", put["Body"])

    def test_concurrent_independent_jobs_allow_only_one_dispatch(self):
        self.github.race = threading.Barrier(2)
        commands = []

        def job(run_id):
            with tempfile.TemporaryDirectory() as folder:
                try:
                    fixture, _ = self.observe(folder, run_id)
                    commands.extend(fixture.commands)
                    return "ran"
                except ObservedCrawlError as exc:
                    return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            states = list(pool.map(job, ["job-one", "job-two"]))
        self.assertCountEqual(states, ["ran", "CRAWL_OBSERVER_JOURNAL_FAILED"])
        self.assertEqual(self.github.creates, 2)
        self.assertEqual(len(commands), 1)
        states = [self.inspect(run_id) for run_id in ("job-one", "job-two")]
        self.assertCountEqual([item["state"] for item in states], ["incomplete", "recorded"])
        loser = next(item for item in states if item["state"] == "incomplete")
        self.assertIsNone(loser["reservation"])
        self.assertEqual(loser["companies"], {"alpha": "no_dispatch_record"})

    def test_different_job_id_is_blocked_after_ambiguous_github_create(self):
        self.github.lose_ack = True
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(first, run_command=self.unexpected_command)
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(second, "different", run_command=self.unexpected_command)
        self.assertIsNotNone(self.github.anchor)
        self.assertEqual(self.github.creates, 1)
        self.assertIsNone(self.inspect()["reservation"])
        self.assertEqual(self.inspect("different")["state"], "manifest_missing")

    def test_archived_run_id_cannot_reserve_again_after_external_release(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.observe(first)
            self.github.anchor = None  # Simulate separate operator reconciliation.
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(second, run_command=self.unexpected_command)
        self.assertEqual(self.github.creates, 1)
        self.assertIsNone(self.github.anchor)
        self.assertEqual(self.inspect()["state"], "recorded")

    def test_lost_dispatch_ack_preserves_intent_without_starting_command(self):
        self.s3.lose_ack = "start-00.json"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(folder, run_command=self.unexpected_command)
        self.assertEqual(self.inspect()["companies"], {"alpha": "possibly_dispatched"})
        self.assertTrue(self.github.anchor)

    def test_receipt_write_failure_blocks_next_company(self):
        self.s3.fail_before_put = "receipt-00.json"
        fixture = Fixture(("alpha", "beta"))
        self.addCleanup(fixture.close)
        fixture.ticks = [TIMES[0], TIMES[1], TIMES[1], TIMES[2]]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                fixture.observe(run_id="fixture-run", journal=self.journal(folder))
        self.assertEqual(len(fixture.commands), 1)
        self.assertEqual(self.inspect()["companies"], {
            "alpha": "possibly_dispatched", "beta": "no_dispatch_record",
        })

    def test_lost_receipt_ack_recovers_verified_prefix_without_next_dispatch(self):
        self.s3.lose_ack = "receipt-00.json"
        fixture = Fixture(("alpha", "beta"))
        self.addCleanup(fixture.close)
        fixture.ticks = [TIMES[0], TIMES[1], TIMES[1], TIMES[2]]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                fixture.observe(run_id="fixture-run", journal=self.journal(folder))
        self.assertEqual(len(fixture.commands), 1)
        self.assertEqual(self.inspect()["companies"], {
            "alpha": "verified_receipt", "beta": "no_dispatch_record",
        })

    def test_two_company_success_recovers_ordered_chain(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture, _ = self.observe(folder, slugs=("alpha", "beta"))
        self.assertEqual(len(fixture.commands), 2)
        outcome = self.inspect()
        self.assertEqual(outcome["recordedCompanies"], 2)
        self.assertEqual(outcome["companies"], {
            "alpha": "verified_receipt", "beta": "verified_receipt",
        })

    def test_archive_round_trip_counts_against_command_budget(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        fixture.ticks = [TIMES[0], TIMES[1], "2026-11-08T14:30:00+00:00"]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "RUN_WINDOW_INVALID"):
                fixture.observe(run_id="fixture-run", journal=self.journal(folder),
                                run_command=self.unexpected_command)
        self.assertEqual(self.inspect()["companies"], {"alpha": "possibly_dispatched"})

    def test_lost_completion_ack_is_recoverable_remotely(self):
        self.s3.lose_ack = "complete.json"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(folder)
            self.assertFalse((Path(folder) / "run-fixture-run/complete.json").exists())
        self.assertEqual(self.inspect()["state"], "recorded")

    def test_anchor_change_between_intent_and_dispatch_blocks_execution(self):
        def replace_anchor(name):
            if name == "start-00.json":
                self.github.anchor = "b" * 40

        self.s3.on_put = replace_anchor
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(folder, run_command=self.unexpected_command)
        self.assertEqual(self.inspect()["companies"], {"alpha": "possibly_dispatched"})

    def test_drift_before_reservation_keeps_remote_state_clean(self):
        self.github.base = "b" * 40
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                self.observe(folder, run_command=self.unexpected_command)
        self.assertEqual(self.github.creates, 0)
        self.assertEqual(self.s3.puts, [])

    def test_missing_version_or_wrong_retention_mode_prevents_dispatch(self):
        for missing_version, wrong_mode in ((True, False), (False, True)):
            with self.subTest(missing_version=missing_version):
                self.s3.missing_version = missing_version
                self.s3.ignore_lock = wrong_mode
                with tempfile.TemporaryDirectory() as folder:
                    with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
                        self.observe(folder, f"fixture-{missing_version}",
                                     run_command=self.unexpected_command)
        self.assertEqual(self.github.creates, 0)

    def test_smoke_scope_cannot_occupy_production_reservation(self):
        smoke = SharedGitHub(smoke=True)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.observe(first, github=smoke)
            self.observe(second)
        self.assertEqual(self.inspect(scope="smoke")["reservation"]["ref"], SMOKE_RESERVATION)
        self.assertEqual(self.inspect()["reservation"]["ref"], RESERVATION)

    def test_recovery_rejects_missing_intent_with_existing_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            self.observe(folder)
        key = next(key for key in self.s3.objects if key.endswith("start-00.json"))
        del self.s3.objects[key]  # Deliberate simulation of corrupt archive state.
        with self.assertRaisesRegex(JournalError, "COMMAND_SEQUENCE_INVALID"):
            self.inspect()

    def test_read_denial_is_not_reported_as_missing(self):
        with patch.object(self.s3, "get_object", side_effect=PermissionError("synthetic credential")):
            with self.assertRaisesRegex(JournalError, "^ARCHIVE_READ_UNCONFIRMED$"):
                self.inspect()

    def test_github_anchor_has_same_tree_and_binds_manifest_digest(self):
        github = GitHubCli.__new__(GitHubCli)
        github.reservation_ref = RESERVATION
        github.branch_prefix = RESERVATION.removesuffix("reservation")
        tree, anchor, digest = "b" * 40, "c" * 40, "d" * 64
        with patch.object(github, "_api", side_effect=[
            {"sha": SHA, "tree": {"sha": tree}}, {"sha": anchor},
            {"ref": "refs/heads/" + RESERVATION, "object": {"type": "commit", "sha": anchor}},
        ]) as api:
            self.assertEqual(github.create_reservation_commit(SHA, digest), anchor)
            self.assertEqual(github.reservation_sha(), anchor)
        self.assertEqual(api.call_args_list[1].args[1], {
            "tree": tree, "parents": [SHA], "message": f"writer reservation manifest sha256 {digest}",
        })

    @unittest.skipUnless(os.name == "posix", "POSIX process group contract")
    def test_real_offline_subprocess_with_external_archive(self):
        repo = OfflineRepo()
        self.addCleanup(repo.close)
        self.github.base = repo.sha
        started = (datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds")
        with tempfile.TemporaryDirectory() as folder:
            result = observe_selected_company_crawls(
                checkout_root=repo.root,
                pre_crawl_selection={"generatedAt": started, "selectedCount": 1,
                                     "selectedSlugs": ["alpha"]},
                pinned_official_urls={"alpha": "https://alpha.example/"},
                base_sha=repo.sha, run_id="fixture-run", run_started_at=started,
                run_command=repo.runner(), clock=lambda: datetime.now(UTC),
                authorized=True, journal=self.journal(folder),
            )
        self.assertTrue(result["externalArchiveRecorded"])
        self.assertEqual(self.inspect()["companies"], {"alpha": "verified_receipt"})

    def unexpected_command(self, *args, **kwargs):
        self.fail("the company command must not run")
