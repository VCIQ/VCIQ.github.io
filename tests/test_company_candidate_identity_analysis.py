import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "analyze_company_candidate_identity.py"
SPEC = importlib.util.spec_from_file_location("candidate_identity_analysis", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CompanyCandidateIdentityAnalysisTests(unittest.TestCase):
    def test_atomizer_splits_compound_names_without_breaking_legal_suffix(self):
        self.assertEqual(
            MODULE.atomize_name("Smallest.ai、ElevenLabs、Cartesia、Sarvam"),
            ["Smallest.ai", "ElevenLabs", "Cartesia", "Sarvam"],
        )
        self.assertEqual(MODULE.atomize_name("字节跳动、闪迪"), ["字节跳动", "闪迪"])
        self.assertEqual(MODULE.atomize_name("Disruptive,Infinitum"), ["Disruptive", "Infinitum"])
        self.assertEqual(MODULE.atomize_name("OpenAI, Inc."), ["OpenAI, Inc."])

    def test_exact_alias_is_resolved_but_core_match_stays_possible(self):
        company_registry = {
            "companies": [
                {"slug": "bytedance", "name": "字节跳动", "englishName": "ByteDance", "aliases": []},
                {"slug": "demo", "name": "合肥示例芯片技术有限公司", "englishName": "", "aliases": []},
            ]
        }
        entities = MODULE.registry_entities(company_registry, {"companies": []})
        exact, cores = MODULE.build_indexes(entities)
        exact_result = MODULE.classify_atom("ByteDance", exact, cores)
        possible_result = MODULE.classify_atom("合肥示例芯片技术", exact, cores)
        self.assertEqual(exact_result["category"], "resolved_existing")
        self.assertEqual(exact_result["match"]["slug"], "bytedance")
        self.assertEqual(possible_result["category"], "possible_existing")
        self.assertEqual(possible_result["match"]["slug"], "demo")

    def test_structural_noise_is_only_a_dry_run_classification(self):
        result = MODULE.analyze(
            {
                "candidates": [
                    {"id": "a", "name": "Benchmarks", "score": 75, "status": "pending"},
                    {"id": "b", "name": "字节跳动、NewCo", "score": 75, "status": "pending"},
                    {"id": "c", "name": "Already", "score": 55, "status": "accepted"},
                ]
            },
            {"companies": [{"slug": "bytedance", "name": "字节跳动", "englishName": "ByteDance", "aliases": []}]},
            {"companies": []},
        )
        summary = result["summary"]
        self.assertEqual(summary["pendingBefore"], 2)
        self.assertEqual(summary["compoundCandidateRows"], 1)
        self.assertEqual(summary["atomizedEntities"], 3)
        self.assertEqual(summary["registryResolved"], 1)
        self.assertEqual(summary["structuralNoise"], 1)
        self.assertEqual(summary["ambiguousStillNeedsReview"], 1)
        self.assertFalse(result["safety"]["writesQueue"])
        self.assertFalse(result["safety"]["changesCandidateStatus"])

    def test_repository_dry_run_is_accounted_and_prints_ci_summary(self):
        queue = MODULE.load_json(ROOT / "config" / "company_candidate_review_queue.json")
        report = MODULE.analyze(
            queue,
            MODULE.load_json(ROOT / "config" / "company_registry.json"),
            MODULE.load_json(ROOT / "config" / "official_company_sources.json"),
        )
        summary = report["summary"]
        self.assertEqual(summary["pendingBefore"], int(queue.get("pendingCount", 0)))
        self.assertGreaterEqual(summary["compoundCandidateRows"], 1)
        self.assertEqual(
            summary["registryResolved"]
            + summary["possibleExisting"]
            + summary["structuralNoise"]
            + summary["ambiguousStillNeedsReview"],
            summary["atomizedEntities"],
        )
        self.assertEqual(report["mode"], "read-only-dry-run")
        print("COMPANY_CANDIDATE_IDENTITY_DRY_RUN=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
