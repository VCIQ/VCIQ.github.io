from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tools import crawl_listed_company_disclosures as base
from tools import publish_us_ir_baselines as publisher
from tools import sec_structured_disclosures as sec
from tools import us_ir_baseline_disclosures as baselines
from tools import us_ir_sec_disclosures as ir


class UsIrBaselineDisclosuresTest(unittest.TestCase):
    def test_every_us_listing_has_one_verified_official_baseline(self) -> None:
        listings = sec.load_us_listings()
        config = base.load_config()
        registry = baselines.load_baselines(listings, config)
        sources = ir.load_ir_sources(listings, config)
        self.assertEqual(set(registry), {listing.catalog_slug for listing in listings})
        self.assertEqual(len(registry), 10)
        for listing in listings:
            row = registry[listing.catalog_slug]
            source = sources[listing.catalog_slug]
            self.assertIn(row["form"], sec.FORM_TYPES)
            self.assertEqual(ir.normalized_host(row["url"]), source.host)
            self.assertRegex(row["filingDate"], r"^20\d{2}-\d{2}-\d{2}$")

    def test_baseline_event_keeps_original_official_ir_url(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        source = ir.IRSource(
            "ionq",
            "IonQ Investor Relations",
            "https://investors.ionq.com/financials/sec-filings/",
            "investors.ionq.com",
            "q4",
        )
        row = {
            "form": "10-Q",
            "filingDate": "2026-05-07",
            "documentDate": "2026-03-31",
            "description": "Quarterly Report",
            "url": "https://investors.ionq.com/financials/sec-filings/sec-filings-details/default.aspx?FilingId=19421418",
        }
        event = baselines.baseline_event(listing, source, row)
        self.assertEqual(event["documentType"], "定期报告与业绩")
        self.assertEqual(event["source"]["url"], row["url"])
        self.assertEqual(event["source"]["name"], source.name)
        self.assertTrue(event["verifiedBaseline"])
        self.assertFalse(event["fallback"])

    def test_baseline_merge_survives_live_discovery_failure(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        source = ir.IRSource(
            "ionq",
            "IonQ Investor Relations",
            "https://investors.ionq.com/financials/sec-filings/",
            "investors.ionq.com",
            "q4",
        )
        original = baselines._ORIGINAL_CRAWL_SOURCE
        baseline_registry = baselines._BASELINES
        try:
            baselines._BASELINES = {
                "ionq": {
                    "form": "10-Q",
                    "filingDate": "2026-05-07",
                    "documentDate": "2026-03-31",
                    "description": "Quarterly Report",
                    "url": "https://investors.ionq.com/financials/sec-filings/sec-filings-details/default.aspx?FilingId=19421418",
                }
            }
            baselines._ORIGINAL_CRAWL_SOURCE = lambda listing, source, settings: (
                [],
                {
                    "id": "us-ir-disclosure-ionq-ionq",
                    "companySlug": "ionq",
                    "accepted": 0,
                    "status": "error",
                    "errors": ["timeout"],
                },
            )
            rows, status = baselines.crawl_source(
                listing,
                source,
                {"maxItemsPerListing": 18},
            )
        finally:
            baselines._ORIGINAL_CRAWL_SOURCE = original
            baselines._BASELINES = baseline_registry
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["verifiedBaseline"])
        self.assertEqual(status["accepted"], 1)
        self.assertEqual(status["baselineAccepted"], 1)
        self.assertEqual(status["status"], "ok")

    def test_publisher_observes_direct_sec_before_building_ir_baseline(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        previous = {"sourceStatus": []}
        observed = {
            "sourceStatus": [
                {
                    "id": listing.source_id,
                    "provider": sec.PROVIDER,
                    "status": "error",
                    "attempted": True,
                    "cikResolved": True,
                    "scanned": 0,
                    "accepted": 0,
                    "errors": ["HTTPError:403"],
                }
            ],
            "secStructured": {"provider": sec.PROVIDER, "acceptedEventCount": 0},
        }
        final_snapshot = {
            "companyCount": 1,
            "eventCount": 1,
            "sourceStatus": observed["sourceStatus"],
            "secStructured": observed["secStructured"],
            "usIrStructured": {"verifiedBaselineCount": 1},
        }
        order: list[str] = []

        def observe(snapshot, rows):
            self.assertIs(snapshot, previous)
            self.assertEqual(rows, [listing])
            order.append("observe")
            return observed

        def validate(snapshot, rows):
            self.assertIs(snapshot, observed)
            self.assertEqual(rows, [listing])
            order.append("validate-observation")
            return []

        def build(snapshot):
            self.assertIs(snapshot, observed)
            order.append("build-baseline")
            return final_snapshot

        def write(snapshot, path):
            self.assertIs(snapshot, final_snapshot)
            self.assertEqual(path, publisher.OUTPUT_PATH)
            order.append("write")
            return True

        with (
            patch.object(publisher.base, "load_previous", return_value=previous),
            patch.object(publisher.sec, "load_us_listings", return_value=[listing]),
            patch.object(
                publisher.configured_sec,
                "build_observation_snapshot",
                side_effect=observe,
            ),
            patch.object(
                publisher.configured_sec,
                "validate_observation_snapshot",
                side_effect=validate,
            ),
            patch.object(publisher, "build_snapshot", side_effect=build),
            patch.object(publisher, "write_snapshot", side_effect=write),
        ):
            self.assertEqual(publisher.main(), 0)

        self.assertEqual(
            order,
            ["observe", "validate-observation", "build-baseline", "write"],
        )

    def test_baseline_publisher_preserves_direct_sec_observation(self) -> None:
        previous = json.loads(
            json.dumps(base.load_previous(publisher.OUTPUT_PATH), ensure_ascii=False)
        )
        direct_status = {
            "id": "sec-disclosure-ionq-ionq",
            "companySlug": "ionq",
            "provider": sec.PROVIDER,
            "status": "error",
            "attempted": True,
            "cikResolved": True,
            "cik": "0001824920",
            "cikSource": "configured-official-registry",
            "scanned": 0,
            "accepted": 0,
            "errors": ["HTTPError:403"],
            "observedAt": "2026-09-04T00:00:00+00:00",
        }
        previous["sourceStatus"] = [
            row
            for row in previous.get("sourceStatus", [])
            if not (
                isinstance(row, dict)
                and row.get("id") == direct_status["id"]
            )
        ] + [direct_status]
        direct_metadata = {
            "schemaVersion": 1,
            "provider": sec.PROVIDER,
            "attemptedListingCount": 10,
            "acceptedEventCount": 0,
            "observationOnly": True,
            "observedAt": "2026-09-04T00:00:00+00:00",
        }
        previous["secStructured"] = direct_metadata

        result = publisher.build_snapshot(previous)
        restored = next(
            row
            for row in result["sourceStatus"]
            if row.get("id") == direct_status["id"]
        )
        self.assertEqual(restored, direct_status)
        self.assertEqual(result["secStructured"], direct_metadata)
        self.assertEqual(
            result["usIrStructured"]["directSecAccess"],
            "see-secStructured",
        )

    def test_live_ir_refresh_restores_direct_sec_observation_unchanged(self) -> None:
        direct_status = {
            "id": "sec-disclosure-ionq-ionq",
            "companySlug": "ionq",
            "provider": sec.PROVIDER,
            "status": "error",
            "attempted": True,
            "cikResolved": True,
            "cik": "0001824920",
            "cikSource": "configured-official-registry",
            "scanned": 0,
            "accepted": 0,
            "errors": ["HTTPError:403"],
            "observedAt": "2026-09-04T00:00:00+00:00",
        }
        direct_metadata = {
            "schemaVersion": 1,
            "provider": sec.PROVIDER,
            "attemptedListingCount": 1,
            "acceptedEventCount": 0,
            "observationOnly": True,
            "observedAt": "2026-09-04T00:00:00+00:00",
        }
        previous = {
            "sourceStatus": [
                direct_status,
                {"id": "us-ir-disclosure-ionq-ionq", "accepted": 1},
            ],
            "secStructured": direct_metadata,
        }
        rebuilt = {
            "sourceStatus": [
                {
                    "id": "us-ir-disclosure-ionq-ionq",
                    "provider": "official-company-ir-sec-filings",
                    "accepted": 7,
                }
            ],
            "usIrStructured": {"acceptedEventCount": 7},
        }
        result = baselines._restore_direct_sec_observations(rebuilt, previous)
        restored = next(
            row
            for row in result["sourceStatus"]
            if row.get("id") == "sec-disclosure-ionq-ionq"
        )
        self.assertEqual(restored, direct_status)
        self.assertEqual(result["secStructured"], direct_metadata)
        self.assertEqual(result["usIrStructured"]["acceptedEventCount"], 7)
        self.assertEqual(restored["accepted"], 0)

    def test_ir_metadata_points_to_separate_direct_sec_ledger(self) -> None:
        result = baselines._apply_metadata(
            {"usIrStructured": {"acceptedEventCount": 3}},
            [sec.USListing("ionq", "IonQ", "IONQ", "量子计算")],
        )
        self.assertEqual(result["usIrStructured"]["directSecAccess"], "see-secStructured")
        self.assertEqual(result["usIrStructured"]["acceptedEventCount"], 3)


if __name__ == "__main__":
    unittest.main()
