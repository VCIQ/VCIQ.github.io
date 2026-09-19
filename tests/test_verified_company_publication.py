from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from tools import onboard_company_candidates as onboarding
from tools import publish_verified_company_candidates as publication
from tools.venture_profile_extraction import CatalogInstitution

NOW = datetime(2026, 9, 19, 2, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def inputs(*names: str):
    candidates = []
    decisions = {}
    for name in names:
        key = onboarding.decision_key(name)
        candidate = {
            "id": "candidate-" + key, "decisionKey": key, "name": name,
            "aliases": [name], "score": 70, "articleCount": 3, "sourceCount": 2,
            "sourceArticleIds": ["a1", "a2"],
            "sourceUrls": [f"https://{key}.example/news"], "eventTypes": ["产品发布"],
        }
        candidates.append(candidate)
        decisions[key] = {
            "status": "accepted", "note": "Reviewed official evidence", "reviewedBy": "VCIQ",
            "decidedAt": "2026-09-18T00:00:00Z",
            "onboarding": {
                "status": "requested", "mode": "create",
                "profile": {
                    "slug": key, "name": name, "englishName": name,
                    "region": "美国", "sector": "AI / AGI", "stage": "成长期", "status": "运营中",
                    "summary": "为企业客户提供可审计的人工智能软件和数据基础设施服务。",
                    "product": "企业人工智能平台与数据工具。", "homepage": f"https://{key}.example/",
                    "newsUrls": [f"https://{key}.example/news"], "confidence": 0.95,
                },
                "evidenceFingerprint": onboarding.evidence_fingerprint(candidate),
                "requestedAt": "2026-09-18T00:00:00Z", "requestedBy": "VCIQ",
            },
        }
    return (
        {"candidates": candidates}, {"schemaVersion": 1, "decisions": decisions},
        {"schemaVersion": 1, "companies": []}, {"schemaVersion": 1, "companies": []},
        {"schemaVersion": 1, "companies": {}, "institutions": {}, "sourceStatus": []},
    )


def good_crawl(company, user_agent, max_pages, previous):
    profile = {
        "slug": company.slug, "name": company.name, "status": "ok",
        "updatedAt": NOW.isoformat(), "background": company.summary,
        "technology": "Evidence-backed engineering platform", "products": ["Alpha Engine"],
        "team": [], "financing": [], "capitalMarkets": [],
        "sources": [{"name": company.name, "url": company.source_url}], "evidenceScore": 80,
    }
    status = {
        "kind": "company", "slug": company.slug, "name": company.name, "status": "ok",
        "fetchedPages": 2, "acceptedSections": 5, "retainedPrevious": False, "elapsedSeconds": 1.0,
    }
    return profile, status


def partial_crawl(*args):
    profile, status = good_crawl(*args)
    profile["status"] = status["status"] = "partial"
    return profile, status


class VerifiedCompanyPublicationTests(unittest.TestCase):
    def run_transaction(self, values, crawler=good_crawl):
        return publication.verified_transaction(*values, [], crawler=crawler, now=NOW)

    def test_mixed_batch_publishes_verified_peer_and_holds_partial_without_a_route(self):
        values = inputs("Alpha", "Beta")
        def crawl(company, *args):
            return (partial_crawl if company.slug == "beta" else good_crawl)(company, *args)
        decisions, registry, sources, snapshot, report = self.run_transaction(values, crawl)
        self.assertEqual(report["publishedSlugs"], ["alpha"])
        self.assertEqual(report["verifiedProfileCount"], 1)
        self.assertEqual(report["heldCount"], 1)
        self.assertEqual(report["failedCount"], 0)
        self.assertEqual([row["slug"] for row in registry["companies"]], ["alpha"])
        self.assertEqual([row["slug"] for row in sources["companies"]], ["alpha"])
        self.assertEqual(set(snapshot["companies"]), {"alpha"})
        self.assertTrue(snapshot["qualityGate"]["passed"])
        held = decisions["decisions"]["beta"]
        self.assertEqual(held["status"], "accepted")
        self.assertEqual(held["onboarding"]["status"], "awaiting_profile")
        self.assertEqual(held["onboarding"]["attemptedAt"], NOW.isoformat())
        self.assertEqual(held["onboarding"]["publishedSlug"], "")
        self.assertIn("partial", held["onboarding"]["error"])
        self.assertEqual(held["onboarding"]["evidenceFingerprint"], values[1]["decisions"]["beta"]["onboarding"]["evidenceFingerprint"])
        replay = onboarding.process_onboarding(values[0], decisions, registry, sources, now=NOW)
        self.assertEqual(replay[0], decisions)
        self.assertEqual(replay[1], registry)
        self.assertEqual(replay[3]["failedCount"], 0)

    def test_all_partial_is_a_private_hold_not_a_public_success(self):
        decisions, registry, sources, snapshot, report = self.run_transaction(inputs("Alpha"), partial_crawl)
        self.assertEqual(report["publishedCount"], 0)
        self.assertEqual(report["heldCount"], 1)
        self.assertEqual(registry["companies"], [])
        self.assertEqual(sources["companies"], [])
        self.assertEqual(snapshot["companies"], {})
        self.assertEqual(decisions["decisions"]["alpha"]["status"], "accepted")

    def test_crawl_exception_is_isolated_and_recorded(self):
        def crawl(company, *args):
            if company.slug == "beta":
                raise TimeoutError("official page timed out")
            return good_crawl(company, *args)
        *_, report = self.run_transaction(inputs("Alpha", "Beta"), crawl)
        self.assertEqual(report["publishedSlugs"], ["alpha"])
        self.assertIn("TimeoutError", report["holds"][0]["reason"])

    def test_identity_and_official_source_gates_are_not_relaxed(self):
        for field, value in (("name", "Wrong"), ("slug", "wrong"), ("sources", []),
                             ("sources", [{"url": "https://alpha.example.attacker.example/"}]),
                             ("background", ""), ("status", "partial")):
            with self.subTest(field=field, value=value):
                def crawl(*args):
                    profile, status = good_crawl(*args)
                    profile[field] = value
                    return profile, status
                *_, report = self.run_transaction(inputs("Alpha"), crawl)
                self.assertEqual(report["publishedCount"], 0)
                self.assertEqual(report["heldCount"], 1)

    def test_semantic_noise_still_blocks_a_new_profile(self):
        def crawl(*args):
            profile, status = good_crawl(*args)
            profile["products"] = ["News"]
            return profile, status
        *_, report = self.run_transaction(inputs("Alpha"), crawl)
        self.assertEqual(report["publishedCount"], 0)
        self.assertIn("quality gate", report["holds"][0]["reason"])

    def test_stale_review_evidence_remains_a_fatal_gate(self):
        values = inputs("Alpha")
        values[1]["decisions"]["alpha"]["onboarding"]["evidenceFingerprint"] = "stale"
        crawl = Mock()
        with self.assertRaisesRegex(ValueError, "request validation"):
            self.run_transaction(values, crawl)
        crawl.assert_not_called()

    def test_transaction_does_not_mutate_its_inputs(self):
        values = inputs("Alpha", "Beta")
        original = copy.deepcopy(values)
        self.run_transaction(values, partial_crawl)
        self.assertEqual(values, original)

    def test_committed_state_replay_is_idempotent_and_does_not_recrawl(self):
        values = inputs("Alpha")
        decisions, registry, sources, snapshot, _ = self.run_transaction(values)
        crawl = Mock()
        replay = self.run_transaction((values[0], decisions, registry, sources, snapshot), crawl)
        crawl.assert_not_called()
        self.assertEqual(replay[:4], (decisions, registry, sources, snapshot))
        self.assertEqual(replay[4]["publishedCount"], 0)

    def test_held_candidate_can_be_reprepared_and_verified_later(self):
        values = inputs("Alpha")
        decisions, registry, sources, snapshot, _ = self.run_transaction(values, partial_crawl)
        decisions["decisions"]["alpha"]["onboarding"]["status"] = "requested"
        *_, report = self.run_transaction((values[0], decisions, registry, sources, snapshot))
        self.assertEqual(report["publishedSlugs"], ["alpha"])
        self.assertEqual(report["heldCount"], 0)

    def test_invalid_existing_evidence_prevents_every_cli_write(self):
        values = inputs("Alpha")
        decisions, registry, sources, snapshot, _ = self.run_transaction(values)
        snapshot["companies"]["alpha"]["products"] = ["News"]
        beta = inputs("Beta")
        institution = CatalogInstitution("capital", "Capital", "Capital", "美国", "VC", "seed", ("AI",), "Capital", "https://capital.example/")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            payloads = {"candidates": beta[0], "decisions": beta[1], "registry": registry,
                        "official-sources": sources, "snapshot": snapshot, "report": {"existing": True}}
            paths = {key: base / (key + ".json") for key in payloads}
            for key, path in paths.items():
                path.write_text(json.dumps(payloads[key]), encoding="utf-8")
            catalog = base / "catalog.ts"
            catalog.write_text("test catalog", encoding="utf-8")
            before = {key: path.read_bytes() for key, path in paths.items()}
            argv = ["--catalog", str(catalog)]
            for key, path in paths.items():
                argv.extend(["--" + key, str(path)])
            stdout = io.StringIO()
            with patch.object(publication, "parse_catalog", return_value=([], [institution])), \
                 patch.object(publication, "crawl_company") as crawl, redirect_stdout(stdout):
                code = publication.main(argv)
            self.assertEqual(code, 1)
            self.assertIn("existing profile quality gate", stdout.getvalue())
            crawl.assert_not_called()
            self.assertEqual({key: path.read_bytes() for key, path in paths.items()}, before)

    def test_workflow_uses_verified_transaction_without_a_second_crawl(self):
        text = (ROOT / ".github/workflows/company-candidate-onboarding.yml").read_text()
        apply = text.split("- name: Apply reviewed onboarding and merge decisions", 1)[1].split("- name:", 1)[0]
        self.assertIn("tools/publish_verified_company_candidates.py", apply)
        validation = text.split("- name: Crawl and validate newly published company profiles", 1)[1].split("- name:", 1)[0]
        self.assertNotIn("--max-pages", validation)
        self.assertIn("--validate-only", validation)
        self.assertIn("{'ok', 'retained', 'fallback'}", validation)
        self.assertIn("assert sources", validation)
        self.assertIn("--limit 12", text)
        self.assertIn("vciq-repository-writer-", text)

    def test_fallback_dispatch_identifies_repository_without_checkout(self):
        text = (ROOT / ".github/workflows/company-candidate-onboarding.yml").read_text()
        fallback = text.split("  terminal-publication-fallback:", 1)[1]
        self.assertIn('--repo "$GITHUB_REPOSITORY"', fallback)
        self.assertIn("run_research_after_deploy=true", fallback)
        self.assertNotIn("continue-on-error", fallback)


if __name__ == "__main__":
    unittest.main()
