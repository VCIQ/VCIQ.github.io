import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import native_event_research as research
from tools.validate_native_research_reports import validate

EVENT = "official-xtalpi-test-event"
REQUEST = "00000000-0000-4000-8000-000000000001"


def model_result(prompt):
    package = json.loads(prompt)
    ref = package["evidence"][0]["id"]
    return {
        "executiveSummary": {"text": "The provided source describes this event; commercial impact remains unverified.", "kind": "inference", "evidenceIds": [ref]},
        "sections": {name: [{"text": f"Bounded {name} analysis", "kind": "source_statement" if name == "facts" else "unknown", "evidenceIds": [ref]}] for name in research.SECTIONS},
    }


class NativeResearchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "public/data"
        self.data.mkdir(parents=True)
        self.event = {"id": EVENT, "title": "Company event", "summary": "Company announces a research collaboration.", "company": "ExampleCo", "sector": "生物科技", "source": {"url": "https://example.com/event", "name": "ExampleCo", "level": "官方"}}
        self.write("articles.json", {"articles": [self.event]})
        self.write("ranked-intelligence.json", {"items": []})
        self.write("research_agent_daily.json", {"analysis": {"executiveSummary": "UNRELATED DAILY SUMMARY"}, "evidence": [
            {"id": "E001", "entityName": "ExampleCo", "url": "https://example.com/unrelated", "claim": "UNRELATED SAME COMPANY CLAIM"},
            {"id": "E002", "entityName": "Other", "url": "https://example.com/event", "claim": "Same event source"},
        ]})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        (self.data / name).write_text(json.dumps(value), encoding="utf-8")

    def test_real_event_creates_request_bound_draft_not_generic_digest(self):
        result = research.generate(self.root, EVENT, REQUEST, model_result)
        self.assertEqual(result["status"], "completed-draft")
        self.assertTrue(result["modelUsed"])
        self.assertEqual(result["requestId"], REQUEST)
        self.assertEqual(result["reviewStatus"], "automated_unreviewed")
        self.assertNotIn("UNRELATED", json.dumps(result))
        validate(research.merge_result({}, result))

    def test_same_company_is_not_an_event_binding(self):
        material = research.evidence_package(self.root, self.event)
        self.assertEqual(len(material), 1)
        self.assertEqual(material[0]["url"], "https://example.com/event")
        self.assertEqual(material[0]["verificationStatus"], "source-statement-unverified")

    def test_unknown_event_never_calls_model(self):
        def forbidden(_):
            self.fail("unexpected model call")
        result = research.generate(self.root, "missing-event", REQUEST, forbidden)
        self.assertEqual(result["status"], "event-unavailable")
        self.assertIsNone(result["analysis"])

    def test_title_only_does_not_become_substantive_evidence(self):
        self.event["summary"] = ""
        self.write("articles.json", {"articles": [self.event]})
        self.write("research_agent_daily.json", {})
        result = research.generate(self.root, EVENT, REQUEST, lambda _: self.fail("model must not run"))
        self.assertEqual(result["status"], "evidence-insufficient")

    def test_model_failure_is_not_completion_or_raw_error_leak(self):
        def failed(_):
            raise RuntimeError("PRIVATE_TOKEN_MUST_NOT_LEAK")
        result = research.generate(self.root, EVENT, REQUEST, failed)
        self.assertEqual(result["status"], "model-unavailable")
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(result))
        self.assertIsNone(result["analysis"])

    def test_unknown_citations_and_verified_fact_labels_are_rejected(self):
        def bad(prompt):
            data = model_result(prompt)
            data["executiveSummary"]["evidenceIds"] = ["FAKE"]
            return data
        self.assertEqual(research.generate(self.root, EVENT, REQUEST, bad)["status"], "model-unavailable")
        def false_fact(prompt):
            data = model_result(prompt)
            data["sections"]["facts"][0]["kind"] = "verified_fact"
            return data
        self.assertEqual(research.generate(self.root, EVENT, REQUEST, false_fact)["status"], "model-unavailable")

    def test_invalid_identity_is_rejected_before_model(self):
        with self.assertRaises(ValueError):
            research.generate(self.root, 'event;$(touch injected)', REQUEST, model_result)
        with self.assertRaises(ValueError):
            research.generate(self.root, EVENT, "not-a-request-id", model_result)

    def test_missing_credentials_are_reported_without_fabrication(self):
        with patch.dict("os.environ", {"SILICONFLOW_API_KEY": ""}):
            result = research.generate(self.root, EVENT, REQUEST)
        self.assertEqual(result["status"], "model-unavailable")

    def test_failed_retry_does_not_remove_previous_success(self):
        success = research.generate(self.root, EVENT, REQUEST, model_result)
        failed = copy.deepcopy(success)
        failed.update(requestId="00000000-0000-4000-8000-000000000002", status="model-unavailable", modelUsed=False, analysis=None)
        merged = research.merge_result({"results": [success]}, failed)
        self.assertEqual(len(merged["results"]), 2)
        self.assertEqual(merged["results"][1]["status"], "completed-draft")
        validate(merged)

    def test_unsafe_source_and_rejected_event_do_not_trigger_model(self):
        self.event["source"]["url"] = "javascript:alert(1)"
        self.write("articles.json", {"articles": [self.event]})
        result = research.generate(self.root, EVENT, REQUEST, lambda _: self.fail("model must not run"))
        self.assertEqual(result["status"], "event-unavailable")

    def test_publication_gate_rejects_self_approval_and_duplicate_request(self):
        report = research.generate(self.root, EVENT, REQUEST, model_result)
        invalid = copy.deepcopy(report)
        invalid["reviewStatus"] = "approved"
        with self.assertRaises(ValueError):
            validate({"schemaVersion": 2, "results": [invalid]})
        with self.assertRaises(ValueError):
            validate({"schemaVersion": 2, "results": [report, report]})


if __name__ == "__main__":
    unittest.main()
