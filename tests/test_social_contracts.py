"""PR-01 C01-C03/G03: synthetic contracts; no platform traffic or credentials."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.social import contracts as c
from tools.social.cli import validate_fixtures

FIXTURES = Path(__file__).parent / "fixtures/social/contracts"


def records():
    return [json.loads(line) for line in (FIXTURES / "valid.jsonl").read_text(encoding="utf-8").splitlines()]


def fixture(kind, platform=None):
    return copy.deepcopy(next(row for row in records() if row["kind"] == kind and (platform is None or row.get("platform") == platform)))


class SocialContractsTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("offline test attempted external work")))

    def assertCode(self, doc, code):
        with self.assertRaises(c.ContractError) as caught:
            c.validate(doc)
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def test_C01_all_nine_kinds_and_five_platforms(self):
        values = records()
        self.assertEqual(set(c.KINDS), {d["kind"] for d in values})
        for kind in ("crawl_job", "query_receipt", "signal_observation"):
            self.assertEqual(set(c.PLATFORMS), {d["platform"] for d in values if d["kind"] == kind})
        for document in values:
            original = copy.deepcopy(document)
            with self.subTest(kind=document["kind"], platform=document.get("platform")):
                self.assertEqual(document, c.validate(document))
                self.assertEqual(original, document)

    def test_C01_negative_corpus_precise_codes(self):
        result = validate_fixtures(FIXTURES)
        self.assertEqual(result["validRecords"], 21)
        self.assertEqual(result["rejectedNegativeCases"], 10)
        self.assertFalse(result["liveExecuted"])
        self.assertFalse(result["batchIntegrityChecked"])

    def test_C02_unknown_publication_remains_null(self):
        doc = fixture("signal_observation", "xhs")
        c.validate(doc)
        self.assertIsNone(doc["publishedAt"])
        doc["publishedAt"] = doc["observedAt"]
        doc["contentHash"] = c.content_hash(doc)
        self.assertCode(doc, "publication_precision")

    def test_C02_known_date_time_and_invalid_calendar(self):
        for value, precision in (("2026-10-22", "day"), ("2026-10-22T12:00:00+08:00", "second")):
            doc = fixture("signal_observation", "xhs")
            doc.update(publishedAt=value, publishedPrecision=precision)
            doc["contentHash"] = c.content_hash(doc)
            c.validate(doc)
        doc["publishedAt"] = "2026-02-30"
        self.assertCode(doc, "any_of")

    def test_C02_no_timezone_and_future_dates_rejected(self):
        doc = fixture("signal_observation", "xhs")
        doc["observedAt"] = "2026-10-23T12:00:00"
        self.assertCode(doc, "format")
        doc = fixture("signal_observation", "xhs")
        doc.update(publishedAt="2036-01-01T00:00:00Z", publishedPrecision="second")
        self.assertCode(doc, "future_publication")

    def test_C03_sensitive_keys_variants_and_no_echo(self):
        for key in ("Cookie", "authorization", "xsec_token", "accessToken", "password", "storageState", "COOKIE", "ｃｏｏｋｉｅ", "coo%6bie"):
            doc = fixture("crawl_job", "xhs")
            doc[key] = "SYNTHETIC_SECRET_ONLY"
            error = self.assertCode(doc, "sensitive_field")
            self.assertNotIn("SYNTHETIC_SECRET_ONLY", str(error))

    def test_C03_secret_assignments_in_logs_and_nested_text(self):
        for text in ('Cookie: SYNTHETIC_SECRET_ONLY', 'Authorization: Bearer SYNTHETIC_SECRET_ONLY', '{"xsec_token":"SYNTHETIC_SECRET_ONLY"}', 'https://example.org/?access_token=SYNTHETIC_SECRET_ONLY', 'https://user:pass@example.org/path', 'https://example.org/?sn=SYNTHETIC_SECRET_ONLY', 'xsec%255ftoken%253DSYNTHETIC_SECRET_ONLY'):
            with self.subTest(text=text.split(":", 1)[0]):
                with self.assertRaises(c.ContractError) as error:
                    c.assert_safe({"note": text})
                self.assertNotIn("SYNTHETIC_SECRET_ONLY", str(error.exception))
        c.assert_safe("Cookie handling is discussed here, without a credential assignment.")

    def test_C03_safe_url_exact_host_path_and_no_remote_resolver(self):
        doc = fixture("signal_observation", "xhs")
        for url in ("https://www.xiaohongshu.com.evil.invalid/explore/a", "https://127.0.0.1/explore/a", "https://www.xiaohongshu.com:443/explore/a", "https://www.xiaohongshu.com/login", "https://www.xiaohongshu.com/explore/%2e%2e", "https://www.xiaohongshu.com/explore/a?redirect=private"):
            doc["canonicalUrl"] = url
            self.assertCode(doc, "canonical_url")

    def test_G03_unknown_fields_and_bounds_are_not_silently_dropped(self):
        doc = fixture("crawl_job", "xhs")
        doc["query"]["extra"] = "unrecognized"
        self.assertCode(doc, "additional_properties")
        doc = fixture("crawl_job", "xhs")
        doc["query"]["text"] = "x" * 513
        self.assertCode(doc, "string_length")
        doc = fixture("crawl_job", "xhs")
        doc["limits"]["maxRecords"] = 201
        self.assertCode(doc, "number_range")

    def test_G03_boolean_not_integer_or_version(self):
        for path in ("schemaVersion", "limits"):
            doc = fixture("crawl_job", "xhs")
            if path == "schemaVersion":
                doc[path] = True
                self.assertCode(doc, "const")
            else:
                doc["limits"]["maxSearchPages"] = True
                self.assertCode(doc, "type")

    def test_G03_nonfinite_nesting_duplicate_keys(self):
        for value in (math.nan, math.inf, -math.inf):
            doc = fixture("signal_observation", "xhs")
            doc["metrics"]["likes"]["value"] = value
            self.assertCode(doc, "non_finite_number")
        value = {}
        for _ in range(34):
            value = {"child": value}
        self.assertCode(value, "nesting_limit")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for raw, code in (('{"kind":1,"kind":2}', "duplicate_key"), ('{"x":NaN}', "non_finite_number")):
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(c.ContractError) as caught:
                    c.load_json(path)
                self.assertEqual(code, caught.exception.code)

    def test_schema_has_no_silent_new_keyword_or_remote_ref(self):
        schema = c.load_schema()
        for modification in ({"unevaluatedProperties": False}, {"$ref": "https://example.org/schema"}, {"format": "unknown"}):
            node = {"type": "object", **modification}
            with self.assertRaises(c.ContractError):
                c._audit_schema(node, schema)

    def test_query_hash_stable_when_budget_window_tracks_change(self):
        doc = fixture("crawl_job", "xhs")
        original = doc["queryId"]
        doc["limits"]["maxRecords"] = 5
        doc["trackRefs"].append("other-track")
        doc["window"].update({"from": "2026-10-01", "filterMode": "post_filter"})
        self.assertEqual(original, c.query_id(doc))
        c.validate(doc)
        doc["query"]["text"] += "new meaning"
        self.assertCode(doc, "identity_hash")

    def test_scope_and_engine_cannot_be_misrepresented(self):
        doc = fixture("crawl_job", "wechat")
        doc["query"]["scope"] = "account"
        self.assertCode(doc, "query_scope")
        doc = fixture("crawl_job", "xhs")
        doc["engine"] = "wechat-public"
        self.assertCode(doc, "const")

    def test_content_hash_excludes_observation_time_and_engagement(self):
        doc = fixture("signal_observation", "xhs")
        expected = doc["contentHash"]
        doc["metrics"]["likes"]["value"] = 12000
        doc["metrics"]["likes"]["approximate"] = True
        doc["observedAt"] = "2026-10-24T00:00:00Z"
        self.assertEqual(expected, c.content_hash(doc))
        c.validate(doc)
        doc["excerpt"] += "material change"
        self.assertCode(doc, "content_hash")

    def test_empty_receipt_requires_processed_successful_zero_page(self):
        doc = fixture("query_receipt", "xhs")
        doc.update(status="empty", completeness="exhausted", stopReason="exhausted")
        doc["counts"] = {key: 0 for key in doc["counts"]}
        doc["pageReceipts"] = [{"pageIndex": 1, "schemaValid": True, "contentItems": 0, "processed": True, "hasMore": False}]
        c.validate(doc)
        doc["pageReceipts"] = []
        self.assertCode(doc, "success_evidence")

    def test_exhausted_is_not_inferred_from_null_has_more(self):
        doc = fixture("query_receipt", "xhs")
        doc.update(completeness="exhausted", stopReason="exhausted")
        self.assertCode(doc, "exhaustion_unproven")
        doc["pageReceipts"][-1]["hasMore"] = False
        c.validate(doc)

    def test_receipt_row_conservation_and_time_order(self):
        doc = fixture("query_receipt", "xhs")
        doc["counts"]["rawRows"] += 1
        self.assertCode(doc, "receipt_counts")
        doc = fixture("query_receipt", "xhs")
        doc["completedAt"] = "2026-10-22T00:00:00Z"
        self.assertCode(doc, "receipt_time_order")

    def test_failure_and_partial_cannot_become_success(self):
        doc = fixture("query_receipt", "xhs")
        doc.update(status="partial", completeness="incomplete", stopReason="network", errorCode="DETAIL_FAILED")
        c.validate(doc)
        doc["status"] = "ok"
        self.assertCode(doc, "success_evidence")
        doc = fixture("query_receipt", "xhs")
        doc.update(status="auth_required", completeness="unknown", stopReason="auth", errorCode="LOGIN_REQUIRED")
        doc["counts"] = {key: 0 for key in doc["counts"]}
        doc["pageReceipts"] = []
        c.validate(doc)

    def test_manifest_requires_unique_filenames_and_correct_totals(self):
        doc = fixture("run_manifest")
        doc["files"][1] = copy.deepcopy(doc["files"][0])
        self.assertCode(doc, "manifest_paths")
        doc = fixture("run_manifest")
        doc["counts"]["jobs"] += 1
        self.assertCode(doc, "manifest_counts")

    def test_plan_count_conservation(self):
        doc = fixture("job_plan")
        doc["stats"]["deferredQueries"] += 1
        self.assertCode(doc, "plan_counts")

    def test_accepting_review_is_not_production_promotion(self):
        doc = fixture("review_item")
        doc.update(status="accepted", promotionStatus="awaiting-primary-evidence")
        c.validate(doc)
        doc["promotionStatus"] = "not-reviewed"
        self.assertCode(doc, "promotion_status")
        doc["promotionStatus"] = "ready-for-mechanical-promotion"
        self.assertCode(doc, "enum")

    def test_frozen_upstream_lock_uses_commit_not_mutable_ref(self):
        root = Path(__file__).resolve().parents[1]
        lock = c.load_json(root / "workers/mediacrawler/upstream.lock.json")
        self.assertRegex(lock["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(lock["repository"], "NanmiCoder/MediaCrawler")
        self.assertEqual(lock["patches"], [])
        self.assertEqual(lock["patchsetHash"], c.digest(lock["patches"]))

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional reference-validator dependency is not installed")
    def test_optional_reference_schema_parity(self):
        import jsonschema
        schema = c.load_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        for doc in records():
            with self.subTest(kind=doc["kind"], platform=doc.get("platform")):
                validator.validate(doc)
                c.validate(doc)
        for key, value in (("schemaVersion", 2), ("platform", "unknown"), ("unexpected", 0)):
            doc = fixture("crawl_job", "xhs")
            doc[key] = value
            self.assertFalse(validator.is_valid(doc))
            with self.assertRaises(c.ContractError):
                c.validate(doc)


if __name__ == "__main__":
    unittest.main()
