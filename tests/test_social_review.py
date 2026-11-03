"""PR-08 immutable, fingerprint-bound review with zero production writes."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from tests.test_social_ingest import synthetic
from tools.social.batch import seal_batch
from tools.social.contracts import ContractError, content_hash
from tools.social.ingest import ingest_batch
from tools.social.lead_builder import build_leads
from tools.social.review import apply_shadow_decision, build_review_queue, current_queue
from tools.social.review_web import request_allowed
from tools.social.signal_store import SignalStore

ROOT = Path(__file__).resolve().parents[1]


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.state = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.store = self.enterContext(SignalStore(self.state, repo_roots=(ROOT,)))

    def add(self, triple):
        job, row, receipt = triple
        path = seal_batch(self.state, [job], [row], [receipt], roots=(ROOT,))
        ingest_batch(path, self.store)

    def pending(self, *, body="合成企业拟启动IPO上市辅导，尚待核验"):
        self.add(synthetic(body=body))
        queue = build_review_queue(self.store)
        item = next(item for item in queue["candidates"] if item["leadType"] == "listing")
        return queue, item

    def request(self, item, decision="accepted"):
        return {"schemaVersion": 1, "kind": "decision_request", "requestId": str(uuid4()),
            "candidateKey": item["candidateKey"], "candidateFingerprint": item["candidateFingerprint"],
            "decision": decision, "reviewedBy": "local-reviewer", "note": "合成测试决定", "seenQueueVersion": item["queueVersion"]}

    def test_L01_name_collision_is_not_identity_match(self):
        row = synthetic()[1]
        row["entityCandidates"] = [{"kind": "company", "label": "同名科技", "entityId": None, "status": "ambiguous", "basis": "name-only"}]
        leads, _ = build_leads([row])
        self.assertTrue(leads)
        for item in leads:
            self.assertIsNone(item["subject"]["companyId"])
            self.assertEqual(item["subject"]["resolution"], "ambiguous")

    def test_L02_existing_project_is_update_not_new_candidate(self):
        row = synthetic()[1]
        row["entityCandidates"] = [{"kind": "company", "label": "已核验公司", "entityId": "company-1", "status": "matched", "basis": "reviewed-registry"}]
        leads, updates = build_leads([row], {"projects": [{"id": "company-1"}]})
        self.assertEqual(leads, [])
        self.assertEqual(updates[0]["action"], "existing-project-evidence-only")

    def test_L03_acceptance_is_not_promotion(self):
        _, item = self.pending()
        with patch("tools.innovation_listing_candidate_review.write_json", side_effect=AssertionError("production write")):
            result = apply_shadow_decision(self.store, self.request(item))
        self.assertTrue(result["changed"])
        self.assertEqual(result["promotionStatus"], "awaiting-primary-evidence")
        self.assertFalse(result["productionModified"])
        accepted = next(row for row in current_queue(self.store)["candidates"] if row["candidateKey"] == item["candidateKey"])
        self.assertEqual(accepted["evidenceClass"], "discovery-only")

    def test_L04_duplicate_request_idempotent_and_mutated_request_rejected(self):
        _, item = self.pending()
        request = self.request(item)
        apply_shadow_decision(self.store, request)
        self.assertFalse(apply_shadow_decision(self.store, request)["changed"])
        request["note"] = "changed payload"
        with self.assertRaisesRegex(ContractError, "review_request_conflict"):
            apply_shadow_decision(self.store, request)

    def test_L04_opposite_terminal_decision_is_forbidden(self):
        _, item = self.pending()
        apply_shadow_decision(self.store, self.request(item, "rejected"))
        with self.assertRaisesRegex(ContractError, "review_final_decision_immutable"):
            apply_shadow_decision(self.store, self.request(item, "accepted"))

    def test_L05_changed_evidence_gets_new_revision_old_decision_preserved(self):
        _, item = self.pending()
        request = self.request(item)
        apply_shadow_decision(self.store, request)
        self.add(synthetic(observed="2026-10-24T12:00:00Z", body="合成企业IPO辅导计划发生变化"))
        queue = build_review_queue(self.store)
        updated = next(row for row in queue["candidates"] if row["leadType"] == "listing")
        self.assertNotEqual(updated["candidateKey"], item["candidateKey"])
        self.assertEqual(updated["status"], "pending")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM social_review_decisions").fetchone()[0], 1)
        with self.assertRaisesRegex(ContractError, "review_candidate_stale"):
            apply_shadow_decision(self.store, self.request(item))

    def test_L05_current_content_change_invalidates_even_without_queue_rebuild(self):
        _, item = self.pending()
        self.add(synthetic(observed="2026-10-24T12:00:00Z", body="新的IPO材料"))
        with self.assertRaisesRegex(ContractError, "review_evidence_changed"):
            apply_shadow_decision(self.store, self.request(item))

    def test_L06_engagement_changes_do_not_change_fingerprint(self):
        body = "合成IPO辅导事项"
        _, item = self.pending(body=body)
        triple = synthetic(observed="2026-10-24T12:00:00Z", body=body)
        triple[1]["metrics"]["likes"] = {"value": 2000, "approximate": False}
        self.add(triple)
        queue = build_review_queue(self.store)
        updated = next(row for row in queue["candidates"] if row["leadType"] == "listing")
        self.assertEqual(updated["candidateFingerprint"], item["candidateFingerprint"])

    def test_L06_unrelated_queue_version_not_stale(self):
        _, item = self.pending()
        request = self.request(item)
        request["seenQueueVersion"] = "a" * 64
        self.assertTrue(apply_shadow_decision(self.store, request)["changed"])

    def test_L07_listing_bridge_never_returns_ready_for_promotion(self):
        from tools.social.innovation_bridge import check_listing_decision
        _, item = self.pending()
        result = check_listing_decision(item, self.request(item))
        self.assertEqual(result["promotionStatus"], "awaiting-primary-evidence")

    def test_L08_loopback_host_origin_and_read_only_assets(self):
        self.assertTrue(request_allowed("127.0.0.1:8765", None, 8765))
        self.assertFalse(request_allowed("evil.example:8765", None, 8765))
        self.assertFalse(request_allowed("127.0.0.1:8765", "https://evil.example", 8765))
        self.assertFalse(request_allowed("127.0.0.1:8765", None, 8765, "cross-site"))
        js = (ROOT / "tools/social/review_ui/app.js").read_text()
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("method:'POST'", js)
        self.assertIn("textContent", js)
        self.assertIn("createObjectURL", js)

    def test_L09_same_post_different_searches_not_duplicate_lead(self):
        triple = synthetic(body="IPO辅导")
        self.add(triple)
        first = build_review_queue(self.store)
        other = synthetic(observed="2026-10-24T12:00:00Z", body="IPO辅导")
        self.add(other)
        second = build_review_queue(self.store)
        self.assertEqual([row["candidateKey"] for row in first["candidates"]], [row["candidateKey"] for row in second["candidates"]])


if __name__ == "__main__":
    unittest.main()
