from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer
from tools import stabilize_venture_profiles as stabilizer


CATALOG = '''
export type Company = {};
export const companies: Company[] = [
  { slug:"anduril", name:"Anduril Industries", englishName:"Anduril Industries", region:"美国", sector:"智能制造", stage:"成长期", status:"运营中", founded:"2017", headquarters:"California", summary:"开发自主系统、传感器和国防软件平台。", product:"Lattice 平台与多类自主飞行器。", source:official("Anduril","https://www.anduril.com/"), confidence:0.96 },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [];
export type IpoCompany = {};
'''


class VentureProfileStabilizerTests(unittest.TestCase):
    def test_current_snapshot_and_catalog_share_fixed_point(self) -> None:
        catalog_text = stabilizer.CATALOG_PATH.read_text(encoding="utf-8")
        payload = json.loads(stabilizer.SNAPSHOT_PATH.read_text(encoding="utf-8"))
        companies, _ = semantics.parse_catalog(catalog_text)
        specs = {company.slug: company for company in companies}

        self.assertIn("anduril", specs)
        self.assertEqual(
            specs["anduril"].summary,
            "开发自主系统、传感器和国防软件平台。",
        )

        stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, catalog_text)
        structural_check, _ = finalizer.finalize_snapshot(stabilized, catalog_text)
        semantic_check, _ = semantics.enforce_snapshot(stabilized, catalog_text)

        self.assertTrue(diagnostics["converged"])
        self.assertEqual(
            stabilized["companies"]["anduril"]["background"],
            "开发自主系统、传感器和国防软件平台。",
        )
        self.assertEqual(
            stabilized["companies"]["anduril"]["projectBackground"]["summary"],
            "开发自主系统、传感器和国防软件平台。",
        )
        self.assertEqual(structural_check, stabilized)
        self.assertEqual(semantic_check, stabilized)

    def test_real_gates_share_one_terminal_fixed_point(self) -> None:
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T17:44:03+00:00",
            "companies": {
                "anduril": {
                    "slug": "anduril",
                    "name": "Anduril Industries",
                    "updatedAt": "2026-07-25T17:43:00+00:00",
                    "status": "partial",
                    "background": "",
                    "technology": "Lattice 平台与多类自主飞行器。",
                    "researchTechnology": "Anduril Industries develops Lattice autonomous systems.",
                    "products": [
                        "Anduril Industries",
                        "英特尔深化智能生态合作",
                        "Lattice 平台与多类自主飞行器",
                    ],
                    "technologyProducts": [],
                    "team": [
                        {"name": "Chris Lyons. The Next", "role": "Partner"},
                    ],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [],
                    "projectBackground": {
                        "summary": "",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }

        stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, CATALOG)
        company = stabilized["companies"]["anduril"]
        structural_check, _ = finalizer.finalize_snapshot(stabilized, CATALOG)
        semantic_check, _ = semantics.enforce_snapshot(stabilized, CATALOG)

        self.assertTrue(diagnostics["converged"])
        self.assertEqual(company["background"], "开发自主系统、传感器和国防软件平台。")
        self.assertEqual(company["products"], ["Lattice 平台", "多类自主飞行器"])
        self.assertEqual(company["team"], [])
        self.assertEqual(structural_check, stabilized)
        self.assertEqual(semantic_check, stabilized)

    def test_short_generated_technology_is_a_shared_fixed_point(self) -> None:
        catalog = """
        export type Company = {};
        export const companies: Company[] = [
          { slug:"form-energy", name:"Form Energy", englishName:"Form Energy", region:"美国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2017", headquarters:"Massachusetts", summary:"开发多日储能系统。", product:"多日储能系统", source:official("Form Energy","https://formenergy.com/"), confidence:0.96 },
        ];
        export type Institution = {};
        export const institutionCatalog: Institution[] = [];
        export type IpoCompany = {};
        """
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T17:44:03+00:00",
            "companies": {
                "form-energy": {
                    "slug": "form-energy",
                    "name": "Form Energy",
                    "background": "开发多日储能系统。",
                    "technology": "核心技术与产品包括多日储能系统。",
                    "researchTechnology": "核心技术与产品包括多日储能系统。",
                    "products": ["多日储能系统"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [],
                    "projectBackground": {
                        "summary": "开发多日储能系统。",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, catalog)
        company = stabilized["companies"]["form-energy"]
        self.assertTrue(diagnostics["converged"])
        self.assertEqual(company["technology"], "核心技术与产品包括多日储能系统。")
        self.assertEqual(company["researchTechnology"], company["technology"])
        structural_check, _ = finalizer.finalize_snapshot(stabilized, catalog)
        semantic_check, _ = semantics.enforce_snapshot(stabilized, catalog)
        self.assertEqual(structural_check, stabilized)
        self.assertEqual(semantic_check, stabilized)

    def test_converges_when_gates_need_multiple_passes(self) -> None:
        payload = {"value": 0}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["value"] = max(1, int(result.get("value", 0)))
            return result, {"changedCompanies": int(result != value)}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["value"] = max(2, int(result.get("value", 0)))
            return result, {"changedCompanies": int(result != value)}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, "catalog")

        self.assertEqual(stabilized, {"value": 2})
        self.assertTrue(diagnostics["converged"])
        self.assertGreaterEqual(diagnostics["passes"], 1)

    def test_rejects_a_cross_gate_cycle(self) -> None:
        payload = {"state": "a"}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "b"
            return result, {}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "a"
            return result, {}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            with self.assertRaisesRegex(RuntimeError, "cycle"):
                stabilizer.stabilize_snapshot(payload, "catalog", max_passes=4)

    def test_cycle_error_reports_changed_paths(self) -> None:
        payload = {"state": "a"}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "b"
            return result, {}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "a"
            return result, {}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            with self.assertRaises(RuntimeError) as caught:
                stabilizer.stabilize_snapshot(payload, "catalog", max_passes=4)

        message = str(caught.exception)
        prefix = "venture terminal gates entered a cycle before reaching a shared fixed point: "
        self.assertTrue(message.startswith(prefix))
        details = json.loads(message[len(prefix):])
        self.assertFalse(details["structuralStable"])
        self.assertTrue(details["semanticStable"])
        self.assertEqual(details["finalizeStepDiff"][0]["path"], "$.state")
        self.assertEqual(details["finalizeStepDiff"][0]["before"], '"a"')
        self.assertEqual(details["finalizeStepDiff"][0]["after"], '"b"')
        self.assertEqual(details["semanticStepDiff"][0]["path"], "$.state")
        self.assertEqual(details["semanticStepDiff"][0]["before"], '"b"')
        self.assertEqual(details["semanticStepDiff"][0]["after"], '"a"')

    def test_rejects_non_positive_pass_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            stabilizer.stabilize_snapshot({}, "catalog", max_passes=0)


if __name__ == "__main__":
    unittest.main()
