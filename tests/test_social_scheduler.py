"""PR-02 W01-W04: deterministic synthetic vocabulary, no external services."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools.social.adapters.wechat import error_result
from tools.social.contracts import ContractError, digest, validate
from tools.social.guard import GuardError
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs
from tools.social.scheduler_state import SchedulerStore, read_state

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)
COMMIT = "a" * 40
UPSTREAM = "8f583999006d5b692272c608440e193ca282e73b"


def tracking(words):
    return {"tracks": [{"name": "合成机器人", "slug": "synthetic", "enabled": True,
                        "keywords": list(words), "sampleCompanies": [], "people": []}]}


def successful(job, now=NOW, empty=True):
    result = error_result(job, "schema_error", "UNSTARTED", now, now)
    receipt = result["receipt"]
    receipt.update(status="empty" if empty else "ok", stopReason="exhausted", completeness="exhausted", errorCode=None,
                   pageReceipts=[{"pageIndex": 1, "schemaValid": True, "contentItems": 0 if empty else 1, "processed": True, "hasMore": False}])
    if not empty:
        receipt["counts"].update(searchItems=1, rawRows=1, rejectedRows=1)
    validate(receipt)
    return result


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.state = self.base / "private"
        self.policy = load_policy()
        self.policy["budget"]["jobsPerPlatformPerRun"] = 10
        self.store = SchedulerStore(self.state, repo_roots=(self.repo,))
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.store.close)

    def registry(self, words, **kwargs):
        return build_query_registry(tracking(words), self.policy, **kwargs)

    def plan(self, registry, now=NOW):
        return plan_jobs(registry, self.store.snapshot(), now, self.policy, vciq_commit=COMMIT,
                         config_hash=digest({"synthetic": True}), upstream_commit=UPSTREAM)

    def test_W01_447_terms_covered_in_45_batches(self):
        registry = self.registry([f"合成关键词{i:03}" for i in range(447)])
        self.assertEqual(len(registry.entries), 447)
        self.store.sync(registry)
        covered = set()
        for _ in range(45):
            plan = self.plan(registry)
            self.assertLessEqual(len(plan["jobs"]), 10)
            for job in plan["jobs"]:
                self.assertNotIn(job["queryId"], covered)
                self.assertTrue(self.store.claim(job, NOW))
                self.store.finish(job, successful(job), NOW, cadence_hours=168)
                covered.add(job["queryId"])
        self.assertEqual(len(covered), 447)
        self.assertEqual(self.plan(registry)["stats"]["selectedJobs"], 0)

    def test_W02_no_company_or_person_prefix_limit(self):
        config = tracking([])
        config["tracks"][0].update(sampleCompanies=[f"合成公司{i}" for i in range(65)], people=[f"合成人物{i}" for i in range(67)])
        registry = build_query_registry(config, self.policy)
        self.assertEqual(len(registry.entries), 132)
        texts = {entry["query"]["text"] for entry in registry.entries}
        self.assertIn("合成公司64", texts)
        self.assertIn("合成人物66", texts)

    def test_W03_reorder_add_remove_preserves_identity_and_state(self):
        initial = self.registry(["机器人", "具身智能"])
        self.store.sync(initial)
        job = self.plan(initial)["jobs"][0]
        self.store.claim(job, NOW)
        self.store.finish(job, successful(job), NOW, cadence_hours=24)
        covered = job["query"]["text"]
        changed = self.registry(["新增词", covered])
        self.store.sync(changed)
        self.assertEqual(self.store.snapshot()["queries"][job["queryId"]]["lastCoveredAt"], NOW.isoformat(timespec="seconds"))
        removed = ({e["queryId"] for e in initial.entries} - {e["queryId"] for e in changed.entries}).pop()
        self.assertFalse(self.store.snapshot()["queries"][removed]["active"])
        self.assertEqual(len(self.plan(changed)["jobs"]), 1)

    def test_W03_cross_track_dedup_and_nfkc(self):
        config = tracking(["ＡＩ  Agent"])
        config["tracks"].append({"name": "第二赛道", "slug": "second", "keywords": ["AI Agent"]})
        registry = build_query_registry(config, self.policy)
        self.assertEqual(len(registry.entries), 1)
        self.assertEqual(registry.entries[0]["trackRefs"], ["second", "synthetic"])
        self.assertEqual(len(registry.terms[0]["originals"]), 2)

    def test_explicit_aliases_only(self):
        raw = tracking(["别名甲", "公司甲", "公司甲乙"])
        self.assertEqual(len(build_query_registry(raw, self.policy).entries), 3)
        aliased = build_query_registry(raw, self.policy, aliases={"别名甲": "公司甲"})
        self.assertEqual(len(aliased.entries), 2)
        with self.assertRaises(ContractError):
            build_query_registry(raw, self.policy, aliases={"别名甲": "公司甲", "公司甲": "别名甲"})

    def test_exclusions_not_truncation_or_loss(self):
        config = tracking(["长" * 39, "有,逗号", "可用词"])
        registry = build_query_registry(config, self.policy, platforms=("wechat", "xhs"))
        self.assertEqual(len(registry.entries), 6)
        reasons = {entry["excludedReason"] for entry in registry.entries}
        self.assertIn("sogou_query_too_long", reasons)
        self.assertIn("query_requires_manual_comma", reasons)
        self.assertEqual(sum(entry["excludedReason"] is not None for entry in registry.entries), 2)

    def test_sensitive_term_is_redacted_before_persistence(self):
        registry = self.registry(["cookie=SYNTHETIC_ONLY", "机器人"])
        self.store.sync(registry)
        blob = json.dumps([*registry.entries, *registry.terms], ensure_ascii=False)
        self.assertNotIn("SYNTHETIC_ONLY", blob)
        self.assertEqual(sum(entry["excludedReason"] is not None for entry in registry.entries), 1)

    def test_W04_failure_backoff_does_not_block_others(self):
        registry = self.registry(["甲机器人", "乙机器人", "丙机器人"])
        self.store.sync(registry)
        job = self.plan(registry)["jobs"][0]
        self.store.claim(job, NOW)
        self.store.finish(job, error_result(job, "network_error", "NETWORK_ERROR", NOW, NOW), NOW, cadence_hours=24)
        self.assertEqual(len(self.plan(registry)["jobs"]), 2)
        state = self.store.snapshot()["queries"][job["queryId"]]
        self.assertIsNone(state["lastCoveredAt"])
        self.assertEqual(state["consecutiveFailures"], 1)
        self.assertGreater(state["nextDueAt"], NOW.isoformat())

    def test_W04_crash_lease_expiry_and_fencing(self):
        registry = self.registry(["机器人"])
        self.store.sync(registry)
        old = self.plan(registry)["jobs"][0]
        self.assertTrue(self.store.claim(old, NOW))
        self.assertEqual(len(self.plan(registry)["jobs"]), 0)
        later = NOW + timedelta(seconds=220)
        new = self.plan(registry, later)["jobs"][0]
        self.assertTrue(self.store.claim(new, later))
        with self.assertRaisesRegex(ContractError, "stale_lease"):
            self.store.finish(old, successful(old), later, cadence_hours=24)
        self.store.finish(new, successful(new, later), later, cadence_hours=24)

    def test_platform_lease_prevents_concurrent_queries(self):
        registry = self.registry(["甲机器人", "乙机器人"])
        self.store.sync(registry)
        jobs = self.plan(registry)["jobs"]
        self.store.claim(jobs[0], NOW)
        with SchedulerStore(self.state, repo_roots=(self.repo,)) as second:
            self.assertFalse(second.claim(jobs[1], NOW))
        self.store.finish(jobs[0], successful(jobs[0]), NOW, cadence_hours=24)
        self.assertTrue(self.store.claim(jobs[1], NOW))

    def test_receipt_checkpoint_atomic_idempotent_and_conflict(self):
        registry = self.registry(["机器人"])
        self.store.sync(registry)
        job = self.plan(registry)["jobs"][0]
        self.store.claim(job, NOW)
        result = successful(job)
        self.assertTrue(self.store.finish(job, result, NOW, cadence_hours=24))
        self.assertFalse(self.store.finish(job, result, NOW, cadence_hours=24))
        changed = copy.deepcopy(result)
        changed["diagnostics"]["requests"] = 999
        with self.assertRaisesRegex(ContractError, "attempt_result_conflict"):
            self.store.finish(job, changed, NOW, cadence_hours=24)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM social_query_results").fetchone()[0], 1)

    def test_invalid_receipt_cannot_advance_coverage(self):
        registry = self.registry(["机器人"])
        self.store.sync(registry)
        job = self.plan(registry)["jobs"][0]
        self.store.claim(job, NOW)
        result = successful(job)
        result["receipt"]["runId"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(ContractError):
            self.store.finish(job, result, NOW, cadence_hours=24)
        self.assertIsNone(self.store.snapshot()["queries"][job["queryId"]]["lastCoveredAt"])

    def test_verification_pauses_platform_until_explicit_resume(self):
        registry = self.registry(["甲机器人", "乙机器人"])
        self.store.sync(registry)
        job = self.plan(registry)["jobs"][0]
        self.store.claim(job, NOW)
        self.store.finish(job, error_result(job, "verification_required", "VERIFY", NOW, NOW), NOW, cadence_hours=24)
        self.assertEqual(len(self.plan(registry)["jobs"]), 0)
        self.store.resume("wechat", NOW)
        self.assertEqual(len(self.plan(registry)["jobs"]), 1)

    def test_retry_after_is_not_truncated_or_manually_bypassed(self):
        registry = self.registry(["甲机器人", "乙机器人"])
        self.store.sync(registry)
        job = self.plan(registry)["jobs"][0]
        self.store.claim(job, NOW)
        result = error_result(job, "rate_limited", "RATE", NOW, NOW)
        result["diagnostics"]["retryAfterSeconds"] = 120000
        self.store.finish(job, result, NOW, cadence_hours=24)
        self.assertEqual(len(self.plan(registry, NOW + timedelta(days=1))["jobs"]), 0)
        with self.assertRaisesRegex(ContractError, "retry_after_not_elapsed"):
            self.store.resume("wechat", NOW)

    def test_tail_reservation_with_new_priority_terms(self):
        self.policy["budget"]["jobsPerPlatformPerRun"] = 2
        config = tracking(["尾部关键词"])
        config["tracks"][0]["sampleCompanies"] = [f"合成公司{i}" for i in range(100)]
        registry = build_query_registry(config, self.policy)
        self.store.sync(registry)
        selected = self.plan(registry)["jobs"]
        self.assertIn("尾部关键词", [job["query"]["text"] for job in selected])

    def test_preview_does_not_create_or_lease(self):
        absent = self.base / "not-created"
        before = self.store.snapshot()
        self.plan(self.registry(["机器人"]))
        self.assertEqual(before, self.store.snapshot())
        self.assertEqual(read_state(absent, repo_roots=(self.repo,)), {"queries": {}, "platforms": {}})
        self.assertFalse(absent.exists())

    def test_combined_request_budget_persists_and_cannot_be_reset(self):
        grant = {"windowStart": NOW.isoformat(), "windowEnd": (NOW + timedelta(hours=1)).isoformat(),
                 "combinedMaxRequests": 10, "productionReservedRequests": 8}
        self.store.consume_request(grant, "synthetic-attempt", NOW)
        with SchedulerStore(self.state, repo_roots=(self.repo,)) as second:
            second.consume_request(grant, "synthetic-attempt", NOW)
            with self.assertRaisesRegex(ContractError, "request_budget_exhausted"):
                second.consume_request(grant, "different-attempt", NOW)
        with self.assertRaisesRegex(ContractError, "budget_grant_changed"):
            self.store.consume_request({**grant, "combinedMaxRequests": 20}, "synthetic-attempt", NOW)
        self.assertEqual(self.store.request_count("synthetic-attempt"), 2)

    def test_state_and_database_links_rejected(self):
        with self.assertRaises(GuardError):
            SchedulerStore(self.repo / "state", repo_roots=(self.repo,))
        link = self.base / "linked"
        link.symlink_to(self.state)
        with self.assertRaises(GuardError):
            SchedulerStore(link, repo_roots=(self.repo,))


if __name__ == "__main__":
    unittest.main()
