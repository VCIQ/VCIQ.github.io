import tempfile
import unittest
from pathlib import Path

from tools import company_registry


class CompanyRegistryTests(unittest.TestCase):
    def test_parse_catalog_company_preserves_profile_fields(self):
        text = '''
export const companies: Company[] = [
  { slug:"sample", name:"示例公司", englishName:"Sample", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2024", headquarters:"北京", summary:"这是一家提供人工智能基础设施和企业软件服务的示例公司。", product:"模型平台与企业软件。", source:official("示例公司","https://example.com/"), confidence:0.96 },
];

export type Institution = {
'''
        rows = company_registry.parse_catalog_companies(text)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["slug"], "sample")
        self.assertEqual(row["englishName"], "Sample")
        self.assertEqual(row["founded"], "2024")
        self.assertEqual(row["source"]["url"], "https://example.com/")
        self.assertEqual(row["confidence"], 0.96)

    def test_registry_validation_rejects_duplicate_slugs(self):
        company = {
            "slug": "sample",
            "name": "示例公司",
            "region": "中国",
            "sector": "AI / AGI",
            "stage": "成长期",
            "status": "运营中",
            "summary": "这是一家拥有足够长度简介的示例科技公司。",
            "product": "企业软件平台",
            "source": {"name": "示例公司", "url": "https://example.com/"},
            "confidence": 0.9,
        }
        payload = company_registry.normalize_registry({"companies": [company, company]})
        errors = company_registry.validate_registry(payload)
        self.assertTrue(any("duplicate slug" in error for error in errors))

    def test_committed_registry_passes_onboarding_preflight(self):
        """Catch invalid shipped company profiles before the publish workflow."""
        registry = company_registry.load_json(company_registry.REGISTRY_PATH, {})
        self.assertGreater(len(registry.get("companies", [])), 0)
        payload = company_registry.normalize_registry(registry)
        errors = company_registry.validate_registry(payload)
        self.assertEqual(errors, [], f"Invalid committed company registry: {errors}")

    def test_migration_replaces_only_company_block(self):
        catalog = '''import type { Source } from "./intelligence-data";
export type Company = {
  region: "中国" | "美国";
};
const official = (name: string, url: string): Source => ({ name, url, level: "官方披露" });
export const companies: Company[] = [
  { slug:"sample", name:"示例公司", region:"中国", sector:"AI", stage:"成长期", status:"运营中", summary:"这是一家拥有足够长度简介的示例科技公司。", product:"企业软件平台", source:official("示例公司","https://example.com/"), confidence:0.9 },
];

export type Institution = { slug: string };
export const institutionCatalog = [];
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "catalog-data.ts"
            registry_path = root / "company_registry.json"
            catalog_path.write_text(catalog, encoding="utf-8")
            result = company_registry.migrate_catalog(catalog_path, registry_path)
            migrated = catalog_path.read_text(encoding="utf-8")
            self.assertTrue(result["catalogChanged"])
            self.assertIn('export { companies } from "./company-registry";', migrated)
            self.assertIn("export type Institution", migrated)
            self.assertIn("region: string", migrated)
            payload = company_registry.load_json(registry_path, {})
            self.assertEqual(payload["companies"][0]["slug"], "sample")


if __name__ == "__main__":
    unittest.main()
