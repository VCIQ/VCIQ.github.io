from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools.crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH, ROOT, load_snapshot
from tools.ensure_venture_profile_coverage import (
    ensure_catalog_coverage,
    repair_snapshot,
)
from tools.venture_profile_extraction import parse_catalog


CATALOG = '''
export const companies: Company[] = [
  { slug:"alpha", name:"Alpha", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", summary:"Alpha summary", product:"Alpha product", source:official("Alpha","https://alpha.example/") },
  { slug:"beta", name:"Beta", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", summary:"Beta summary", product:"Beta product", source:official("Beta","https://beta.example/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"sample-capital", name:"Sample Capital", region:"美国", type:"风险投资", stages:"种子至成长期", sectors:["AI"], source:official("Sample Capital","https://capital.example/") },
];
export type IpoCompany = {};
'''


class EnsureVentureProfileCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.companies, self.institutions = parse_catalog(CATALOG)

    def test_missing_catalog_entities_receive_traceable_fallback_skeletons(self) -> None:
        snapshot = {
            "companies": {
                "alpha": {
                    "slug": "alpha",
                    "name": "Alpha",
                    "updatedAt": "2026-08-01T00:00:00Z",
                    "status": "ok",
                    "background": "Existing evidence.",
                    "technology": "Existing technology.",
                    "products": ["Alpha product"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [{"url": "https://alpha.example/"}],
                }
            },
            "institutions": {},
            "sourceStatus": [
                {
                    "kind": "company",
                    "slug": "alpha",
                    "name": "Alpha",
                    "status": "ok",
                }
            ],
        }
        companies, institutions, statuses, quality, report = ensure_catalog_coverage(
            snapshot,
            self.companies,
            self.institutions,
            updated_at="2026-08-03T15:45:00+00:00",
        )
        self.assertEqual(set(companies), {"alpha", "beta"})
        self.assertEqual(set(institutions), {"sample-capital"})
        self.assertEqual(companies["alpha"]["background"], "Existing evidence.")
        self.assertEqual(companies["beta"]["status"], "fallback")
        self.assertEqual(institutions["sample-capital"]["status"], "fallback")
        self.assertEqual(report["addedCompanies"], ["beta"])
        self.assertEqual(report["addedInstitutions"], ["sample-capital"])
        self.assertEqual(len(statuses), 3)
        self.assertTrue(quality["passed"])

    def test_missing_company_fallback_uses_the_same_product_sanitizer_as_crawl(self) -> None:
        noisy_catalog = '''
export const companies: Company[] = [
  { slug:"noisy", name:"Noisy", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", summary:"Noisy summary", product:"product, products", source:official("Noisy","https://noisy.example/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"sample-capital", name:"Sample Capital", region:"美国", type:"风险投资", stages:"种子至成长期", sectors:["AI"], source:official("Sample Capital","https://capital.example/") },
];
export type IpoCompany = {};
'''
        companies, institutions = parse_catalog(noisy_catalog)
        company_profiles, _, _, quality, report = ensure_catalog_coverage(
            {"companies": {}, "institutions": {}, "sourceStatus": []},
            companies,
            institutions,
            updated_at="2026-08-03T15:45:00+00:00",
        )

        self.assertEqual(company_profiles["noisy"]["products"], [])
        self.assertTrue(quality["passed"])
        self.assertTrue(report["qualityPassed"])

    def test_repair_is_idempotent_when_coverage_is_complete(self) -> None:
        empty = {"companies": {}, "institutions": {}, "sourceStatus": []}
        companies, institutions, statuses, quality, _ = ensure_catalog_coverage(
            empty,
            self.companies,
            self.institutions,
            updated_at="2026-08-03T15:45:00+00:00",
        )
        complete = {
            "companies": companies,
            "institutions": institutions,
            "sourceStatus": statuses,
        }
        _, _, second_statuses, second_quality, report = ensure_catalog_coverage(
            complete,
            self.companies,
            self.institutions,
            updated_at="2026-08-03T16:00:00+00:00",
        )
        self.assertEqual(report["addedCompanies"], [])
        self.assertEqual(report["addedInstitutions"], [])
        self.assertEqual(report["addedStatuses"], [])
        self.assertEqual(len(second_statuses), 3)
        self.assertTrue(quality["passed"])
        self.assertTrue(second_quality["passed"])

    def test_repair_snapshot_writes_standard_payload_and_is_idempotent(self) -> None:
        initial = {
            "schemaVersion": 1,
            "researchModelVersion": 3,
            "generatedAt": "2026-08-01T00:00:00Z",
            "companies": {},
            "institutions": {},
            "sourceStatus": [],
            "qualityGate": {"passed": False},
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            base = Path(directory)
            catalog_path = base / "catalog-data.ts"
            snapshot_path = base / "venture_profiles.json"
            catalog_path.write_text(CATALOG, encoding="utf-8")
            snapshot_path.write_text(
                json.dumps(initial, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            first = repair_snapshot(
                catalog_path=catalog_path,
                snapshot_path=snapshot_path,
                now=datetime(2026, 8, 3, 16, 0, tzinfo=UTC),
            )
            persisted = json.loads(snapshot_path.read_text(encoding="utf-8"))

            self.assertTrue(first["changed"])
            self.assertTrue(first["qualityPassed"])
            self.assertEqual(set(persisted["companies"]), {"alpha", "beta"})
            self.assertEqual(set(persisted["institutions"]), {"sample-capital"})
            self.assertEqual(len(persisted["sourceStatus"]), 3)
            self.assertTrue(persisted["qualityGate"]["passed"])
            self.assertEqual(persisted["researchModelVersion"], 3)
            self.assertEqual(persisted["generatedAt"], "2026-08-03T16:00:00+00:00")

            second = repair_snapshot(
                catalog_path=catalog_path,
                snapshot_path=snapshot_path,
                now=datetime(2026, 8, 3, 16, 5, tzinfo=UTC),
            )
            self.assertFalse(second["changed"])
            self.assertEqual(
                json.loads(snapshot_path.read_text(encoding="utf-8")),
                persisted,
            )

    def test_production_snapshot_repairs_to_complete_catalog_coverage(self) -> None:
        companies, institutions = parse_catalog(CATALOG_PATH.read_text(encoding="utf-8"))
        company_profiles, institution_profiles, statuses, quality, report = ensure_catalog_coverage(
            load_snapshot(OUTPUT_PATH),
            companies,
            institutions,
            updated_at="2026-08-03T16:00:00+00:00",
        )
        self.assertEqual(len(company_profiles), len(companies))
        self.assertEqual(len(institution_profiles), len(institutions))
        self.assertEqual(report["companyCoverage"], len(companies))
        self.assertEqual(report["institutionCoverage"], len(institutions))
        self.assertEqual(report["runtimeStatusCoverage"], len(statuses))
        self.assertTrue(quality["passed"])


if __name__ == "__main__":
    unittest.main()
