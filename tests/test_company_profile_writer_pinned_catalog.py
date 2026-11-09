"""No-network provenance tests for the re-exported company registry."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.company_profile_writer_pinned_catalog import (
    PinnedCatalogError, pinned_catalog,
)
from tools.venture_profile_extraction import parse_catalog


REGISTRY_TS = (
    'import rawRegistry from "@/config/company_registry.json";\n'
    'export const companies = rawRegistry.companies;\n'
)
CATALOG = (
    'export { companies } from "./company-registry";\n'
    'export type Institution = {};\n'
    'export const institutionCatalog: Institution[] = [];\n'
    'export type IpoCompany = {};\n'
)
REGISTRY = {
    "schemaVersion": 1,
    "companies": [
        {"slug": "alpha", "name": "Alpha", "source": {"name": "Alpha",
         "url": "https://alpha.example/"}},
        {"slug": "beta", "name": "Beta", "source": {"name": "Beta",
         "url": "https://beta.example/"}},
    ],
}


class PinnedCatalogTests(unittest.TestCase):
    def test_synthetic_registry_is_parsed_without_ambient_files(self):
        companies, institutions = pinned_catalog(CATALOG, REGISTRY_TS, REGISTRY)
        self.assertEqual([c.slug for c in companies], ["alpha", "beta"])
        self.assertEqual(institutions, [])

    def test_missing_or_invalid_registry_fails_closed(self):
        for ts, value in ((None, REGISTRY), (REGISTRY_TS, None),
                          ("import rawRegistry from './elsewhere.json'", REGISTRY),
                          (REGISTRY_TS, {"schemaVersion": 1, "companies": []})):
            with self.subTest(ts=ts, value=value), self.assertRaises(PinnedCatalogError):
                pinned_catalog(CATALOG, ts, value)

    def test_duplicate_company_identity_is_rejected(self):
        value = copy.deepcopy(REGISTRY)
        value["companies"].append(copy.deepcopy(value["companies"][0]))
        with self.assertRaisesRegex(PinnedCatalogError, "DUPLICATE"):
            pinned_catalog(CATALOG, REGISTRY_TS, value)

    def test_invalid_official_url_is_rejected(self):
        value = copy.deepcopy(REGISTRY)
        value["companies"][0]["source"]["url"] = "javascript:alert(1)"
        with self.assertRaisesRegex(PinnedCatalogError, "REGISTRY_INVALID"):
            pinned_catalog(CATALOG, REGISTRY_TS, value)

    def test_inline_catalog_does_not_consult_registry(self):
        inline = (
            'export const companies: Company[] = [\n'
            '  { slug:"alpha", name:"Alpha", source:official("Alpha","https://alpha.example/") },\n'
            '];\nexport type Institution = {};\n'
        )
        company, _ = pinned_catalog(inline)
        self.assertEqual([c.slug for c in company], ["alpha"])
        with self.assertRaisesRegex(PinnedCatalogError, "AMBIGUOUS"):
            pinned_catalog(inline, REGISTRY_TS, REGISTRY)

    def test_real_public_git_worktree_catalog_matches_existing_parser(self):
        root = Path(__file__).resolve().parents[1]
        catalog = (root / "lib/catalog-data.ts").read_text(encoding="utf-8")
        ts = (root / "lib/company-registry.ts").read_text(encoding="utf-8")
        data = json.loads((root / "config/company_registry.json").read_text(encoding="utf-8"))
        companies, institutions = pinned_catalog(catalog, ts, data)
        existing_companies, existing_institutions = parse_catalog(catalog)
        self.assertEqual(companies, existing_companies)
        self.assertEqual(institutions, existing_institutions)
        self.assertEqual(len(companies), 100)
        self.assertEqual(len(institutions), 20)


if __name__ == "__main__":
    unittest.main()
