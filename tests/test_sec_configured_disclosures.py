from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import sec_configured_disclosures as configured
from tools import sec_structured_disclosures as sec


class SecConfiguredDisclosuresTest(unittest.TestCase):
    def test_all_current_us_listings_have_configured_ciks(self) -> None:
        listings = sec.load_us_listings()
        config = base.load_config()
        resolved, missing = configured.configured_ticker_ciks(listings, config)
        self.assertEqual(missing, [])
        self.assertEqual(len(resolved), len(listings))
        self.assertEqual(resolved["IONQ"], "0001824920")
        self.assertEqual(resolved["RKLB"], "0001819994")
        self.assertTrue(all(len(cik) == 10 and cik.isdigit() for cik in resolved.values()))

    def test_complete_registry_skips_blocked_sec_ticker_index(self) -> None:
        listings = [sec.USListing("ionq", "IonQ", "IONQ", "量子计算")]
        config = {
            "settings": {"requestTimeout": 18, "requestAttempts": 2},
            "secCiks": {"ionq": "1824920"},
        }

        def blocked_fetcher(*args, **kwargs):
            raise AssertionError("dynamic SEC ticker index must not be requested")

        resolved, metadata = configured.resolve_ticker_ciks(
            listings,
            config,
            index_fetcher=blocked_fetcher,
        )
        self.assertEqual(resolved, {"IONQ": "0001824920"})
        self.assertEqual(metadata["configuredListingCount"], 1)
        self.assertEqual(metadata["configuredTickers"], ["IONQ"])
        self.assertFalse(metadata["dynamicLookupAttempted"])
        self.assertEqual(metadata["dynamicLookupErrors"], [])

    def test_missing_future_listing_can_use_dynamic_lookup(self) -> None:
        listings = [sec.USListing("future-company", "Future Company", "FUTR", "AI / AGI")]
        config = {
            "settings": {"requestTimeout": 18, "requestAttempts": 2},
            "secCiks": {},
        }

        def index_fetcher(url, timeout, attempts):
            self.assertEqual(url, sec.TICKER_INDEX_URL)
            return {
                "0": {
                    "cik_str": 1234567,
                    "ticker": "FUTR",
                    "title": "Future Company",
                }
            }

        resolved, metadata = configured.resolve_ticker_ciks(
            listings,
            config,
            index_fetcher=index_fetcher,
        )
        self.assertEqual(resolved, {"FUTR": "0001234567"})
        self.assertTrue(metadata["dynamicLookupAttempted"])
        self.assertEqual(metadata["dynamicResolvedCount"], 1)
        self.assertEqual(metadata["dynamicResolvedTickers"], ["FUTR"])

    def test_submission_identity_must_match_cik_and_ticker(self) -> None:
        configured.verify_submission_identity(
            {"cik": "1824920", "tickers": ["IONQ"]},
            expected_ticker="IONQ",
            expected_cik="0001824920",
        )
        with self.assertRaises(RuntimeError):
            configured.verify_submission_identity(
                {"cik": "1824920", "tickers": ["OTHER"]},
                expected_ticker="IONQ",
                expected_cik="0001824920",
            )
        with self.assertRaises(RuntimeError):
            configured.verify_submission_identity(
                {"cik": "1234567", "tickers": ["IONQ"]},
                expected_ticker="IONQ",
                expected_cik="0001824920",
            )

    def test_registry_metadata_marks_configured_cik_source(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        snapshot = {
            "sourceStatus": [
                {
                    "id": listing.source_id,
                    "accepted": 1,
                    "cikResolved": True,
                }
            ],
            "secStructured": {
                "schemaVersion": 1,
                "provider": sec.PROVIDER,
                "attemptedListingCount": 1,
                "acceptedEventCount": 1,
            },
        }
        result = configured.apply_registry_metadata(
            snapshot,
            [listing],
            {
                "configuredListingCount": 1,
                "configuredTickers": ["IONQ"],
                "dynamicLookupAttempted": False,
                "dynamicResolvedCount": 0,
                "dynamicResolvedTickers": [],
                "dynamicLookupErrors": [],
            },
        )
        self.assertEqual(
            result["sourceStatus"][0]["cikSource"],
            "configured-official-registry",
        )
        self.assertEqual(
            result["secStructured"]["cikRegistry"]["configuredListingCount"],
            1,
        )

    def test_observation_only_failure_is_not_promoted_by_existing_ir_content(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        previous = {
            "generatedAt": "2026-09-01T00:00:00+00:00",
            "companyCount": 1,
            "eventCount": 1,
            "companies": {
                "ionq": {
                    "slug": "ionq",
                    "events": [{"id": "existing-ir-event"}],
                }
            },
            "sourceStatus": [
                {
                    "id": "us-ir-disclosure-ionq-ionq",
                    "provider": "official-company-ir-sec-filings",
                    "status": "ok",
                    "accepted": 1,
                },
                {
                    "id": listing.source_id,
                    "provider": sec.PROVIDER,
                    "status": "ok",
                    "accepted": 99,
                },
            ],
        }
        config = {
            "settings": {
                "requestTimeout": 1,
                "requestAttempts": 1,
                "maxAgeDays": 1095,
                "maxItemsPerListing": 18,
            },
            "secCiks": {"ionq": "1824920"},
        }

        def blocked_submission(url, timeout, attempts):
            raise RuntimeError("shared CI blocked by SEC")

        result = configured.build_observation_snapshot(
            previous,
            [listing],
            config,
            submissions_fetcher=blocked_submission,
        )
        self.assertEqual(result["companies"], previous["companies"])
        self.assertEqual(result["companyCount"], 1)
        self.assertEqual(result["eventCount"], 1)
        status = next(
            row for row in result["sourceStatus"] if row.get("id") == listing.source_id
        )
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["scanned"], 0)
        self.assertEqual(status["accepted"], 0)
        self.assertIn("RuntimeError:shared CI blocked by SEC", status["errors"])
        self.assertTrue(status["observedAt"])
        self.assertEqual(status["cikSource"], "configured-official-registry")
        self.assertEqual(result["secStructured"]["acceptedEventCount"], 0)
        self.assertTrue(result["secStructured"]["observationOnly"])
        self.assertEqual(
            configured.validate_observation_snapshot(result, [listing]),
            [],
        )

    def test_observation_only_success_keeps_direct_sec_counters(self) -> None:
        listing = sec.USListing("ionq", "IonQ", "IONQ", "量子计算")
        config = {
            "settings": {
                "requestTimeout": 1,
                "requestAttempts": 1,
                "maxAgeDays": 1095,
                "maxItemsPerListing": 18,
            },
            "secCiks": {"ionq": "1824920"},
        }
        payload = {
            "cik": "1824920",
            "tickers": ["IONQ"],
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "4"],
                    "accessionNumber": [
                        "0001193125-26-000001",
                        "0001193125-26-000002",
                        "0001193125-26-000003",
                    ],
                    "filingDate": ["2026-08-01", "2026-07-20", "2026-07-10"],
                    "reportDate": ["2026-06-30", "2026-07-20", ""],
                    "primaryDocument": ["ionq-10q.htm", "ionq-8k.htm", "form4.xml"],
                    "primaryDocDescription": [
                        "Quarterly Report",
                        "Current Report",
                        "Ownership Form",
                    ],
                }
            },
        }

        def submissions_fetcher(url, timeout, attempts):
            self.assertIn("CIK0001824920.json", url)
            return payload

        result = configured.build_observation_snapshot(
            {"companies": {}, "sourceStatus": []},
            [listing],
            config,
            submissions_fetcher=submissions_fetcher,
        )
        status = next(
            row for row in result["sourceStatus"] if row.get("id") == listing.source_id
        )
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["scanned"], 3)
        self.assertEqual(status["accepted"], 2)
        self.assertEqual(result["secStructured"]["acceptedEventCount"], 2)
        self.assertEqual(result.get("companies"), {})
        self.assertEqual(
            configured.validate_observation_snapshot(result, [listing]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
