from __future__ import annotations

import unittest
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from tools import onboard_company_candidates as onboarding
from tools import prepare_company_candidate_onboarding as auto


class AutomaticCompanyOnboardingTests(unittest.TestCase):
    def candidate(
        self,
        name: str = "Sample AI",
        *,
        sector: str = "AI / AGI",
        region: str = "美国",
    ) -> dict:
        return {
            "id": f"candidate-{auto.identity_key(name)}",
            "decisionKey": onboarding.decision_key(name),
            "name": name,
            "aliases": [name],
            "region": region,
            "sector": sector,
            "score": 75,
            "status": "accepted",
            "articleCount": 2,
            "sourceCount": 2,
            "sourceArticleIds": ["article-a", "article-b"],
            "sourceUrls": ["https://media.example/a", "https://media.example/b"],
            "eventTypes": ["产品发布"],
            "captureCount": 1,
            "captureIds": ["capture-sample"],
        }

    def decisions(self, candidate: dict, *, onboarding_state: dict | None = None) -> dict:
        row = {
            "status": "accepted",
            "note": "人工确认公司实体。",
            "mergedSlug": "",
            "decidedAt": "2026-08-08T00:00:00Z",
            "reviewedBy": "VCIQ",
        }
        if onboarding_state is not None:
            row["onboarding"] = onboarding_state
        return {
            "schemaVersion": 1,
            "decisions": {candidate["decisionKey"]: row},
        }

    def metadata(self, name: str = "Sample AI", homepage: str = "https://sample.ai/") -> dict:
        return {
            "source": "wikidata",
            "sourceId": "Q100",
            "canonicalName": name,
            "englishName": name,
            "homepage": homepage,
            "region": "美国",
            "founded": "2024",
            "headquarters": "旧金山",
            "aliases": [f"{name} Inc."],
            "description": "artificial intelligence company",
        }

    def page(
        self,
        name: str = "Sample AI",
        *,
        text: str | None = None,
        url: str = "https://sample.ai/",
    ) -> dict:
        body = text or (
            f"{name} builds artificial intelligence infrastructure for enterprise teams. "
            "Our AI platform combines model serving, data workflows and developer tools."
        )
        return {
            "url": url,
            "title": f"{name} | Official",
            "description": body,
            "siteName": name,
            "text": body,
            "newsUrls": [f"{url.rstrip('/')}/news"],
        }

    def synthesis(self) -> dict:
        return {
            "summary": "为企业团队提供可审计的人工智能基础设施，并围绕模型服务和数据工作流建设统一平台。",
            "product": "人工智能模型服务、数据工作流与开发者工具平台。",
            "identityConfidence": 0.96,
        }

    def prepare(
        self,
        candidate: dict,
        *,
        decisions: dict | None = None,
        official_sources: dict | None = None,
        registry: dict | None = None,
        resolver=None,
        page_fetcher=None,
        synthesizer=None,
    ):
        return auto.prepare_automatic_onboarding(
            {"schemaVersion": 1, "candidates": [candidate]},
            decisions or self.decisions(candidate),
            official_sources or {"schemaVersion": 1, "companies": []},
            registry or {"schemaVersion": 1, "companies": []},
            {
                "schemaVersion": 1,
                "records": [
                    {
                        "id": "capture-sample",
                        "source": {
                            "title": f"{candidate['name']} releases a new product",
                            "summary": "Candidate context",
                            "url": "https://media.example/a",
                            "eventType": "产品发布",
                        },
                    }
                ],
            },
            resolver=resolver or (lambda _name: (self.metadata(candidate["name"]), "")),
            page_fetcher=page_fetcher or (lambda _url: self.page(candidate["name"])),
            synthesizer=synthesizer
            or (lambda **_kwargs: (self.synthesis(), "")),
            now=datetime(2026, 8, 8, 1, tzinfo=UTC),
        )

    def test_verified_official_page_creates_requested_onboarding(self) -> None:
        candidate = self.candidate()
        next_decisions, report = self.prepare(candidate)

        decision = next_decisions["decisions"][candidate["decisionKey"]]
        request = decision["onboarding"]
        self.assertEqual(request["status"], "requested")
        self.assertEqual(request["requestedBy"], "VCIQ/auto-profile")
        self.assertEqual(request["requestedAt"], "2026-08-08T01:00:00+00:00")
        self.assertEqual(request["profile"]["slug"], "sample-ai")
        self.assertEqual(request["profile"]["homepage"], "https://sample.ai/")
        self.assertEqual(request["profile"]["stage"], "未披露")
        self.assertEqual(
            request["evidenceFingerprint"], onboarding.evidence_fingerprint(candidate)
        )
        self.assertEqual(report["requestedKeys"], [candidate["decisionKey"]])
        self.assertEqual(report["holdCount"], 0)

    def test_existing_official_source_is_preferred_over_wikidata(self) -> None:
        candidate = self.candidate()

        def resolver(_name: str):
            raise AssertionError("Wikidata must not run when an exact official source exists")

        official = {
            "companies": [
                {
                    "slug": "sample-ai",
                    "name": "Sample AI",
                    "region": "美国",
                    "sector": "AI / AGI",
                    "homepage": "https://sample.ai/",
                    "newsUrls": ["https://sample.ai/news"],
                    "aliases": ["Sample AI Inc."],
                }
            ]
        }
        next_decisions, report = self.prepare(
            candidate,
            official_sources=official,
            resolver=resolver,
        )
        profile = next_decisions["decisions"][candidate["decisionKey"]]["onboarding"][
            "profile"
        ]
        self.assertEqual(profile["homepage"], "https://sample.ai/")
        self.assertEqual(report["requestedCount"], 1)

    def test_investment_institution_is_held_before_source_discovery(self) -> None:
        candidate = self.candidate(
            "Expedition Growth Capital",
            sector="风险投资",
            region="全球",
        )

        def resolver(_name: str):
            raise AssertionError("institution-like candidates must not enter company discovery")

        next_decisions, report = self.prepare(candidate, resolver=resolver)
        decision = next_decisions["decisions"][candidate["decisionKey"]]
        self.assertEqual(decision["onboarding"]["status"], "awaiting_profile")
        self.assertEqual(decision["onboarding"]["attemptedAt"], "2026-08-08T01:00:00+00:00")
        self.assertIn("investment institution", decision["onboarding"]["error"])
        self.assertEqual(report["requestedCount"], 0)
        self.assertIn("investment institution", report["holds"][0]["reason"])

    def test_previous_hold_does_not_starve_unattempted_candidate(self) -> None:
        held = self.candidate("Expedition Growth Capital", sector="风险投资")
        fresh = self.candidate("Sample AI")
        decisions = {
            "schemaVersion": 1,
            "decisions": {
                held["decisionKey"]: {
                    "status": "accepted",
                    "note": "人工确认。",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-08T00:00:00Z",
                    "reviewedBy": "VCIQ",
                    "onboarding": {
                        "status": "awaiting_profile",
                        "attemptedAt": "2026-08-08T00:30:00Z",
                        "error": "previous hold",
                    },
                },
                fresh["decisionKey"]: {
                    "status": "accepted",
                    "note": "人工确认。",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-08T00:01:00Z",
                    "reviewedBy": "VCIQ",
                },
            },
        }
        next_decisions, report = auto.prepare_automatic_onboarding(
            {"schemaVersion": 1, "candidates": [held, fresh]},
            decisions,
            {"schemaVersion": 1, "companies": []},
            {"schemaVersion": 1, "companies": []},
            {"schemaVersion": 1, "records": []},
            resolver=lambda name: (self.metadata(name), ""),
            page_fetcher=lambda _url: self.page("Sample AI"),
            synthesizer=lambda **_kwargs: (self.synthesis(), ""),
            now=datetime(2026, 8, 8, 1, tzinfo=UTC),
            limit=1,
        )
        self.assertEqual(report["processedCount"], 1)
        self.assertEqual(report["requestedKeys"], [fresh["decisionKey"]])
        self.assertEqual(report["unattemptedRemainingCount"], 0)
        self.assertEqual(
            next_decisions["decisions"][held["decisionKey"]]["onboarding"]["status"],
            "awaiting_profile",
        )

    def test_first_hold_leaves_later_candidate_as_unattempted_backlog(self) -> None:
        held = self.candidate("Expedition Growth Capital", sector="风险投资")
        fresh = self.candidate("Sample AI")
        decisions = {
            "schemaVersion": 1,
            "decisions": {
                held["decisionKey"]: self.decisions(held)["decisions"][held["decisionKey"]],
                fresh["decisionKey"]: self.decisions(fresh)["decisions"][fresh["decisionKey"]],
            },
        }
        next_decisions, report = auto.prepare_automatic_onboarding(
            {"schemaVersion": 1, "candidates": [held, fresh]},
            decisions,
            {"schemaVersion": 1, "companies": []},
            {"schemaVersion": 1, "companies": []},
            {"schemaVersion": 1, "records": []},
            resolver=lambda name: (self.metadata(name), ""),
            page_fetcher=lambda _url: self.page("Sample AI"),
            synthesizer=lambda **_kwargs: (self.synthesis(), ""),
            now=datetime(2026, 8, 8, 1, tzinfo=UTC),
            limit=1,
        )
        self.assertEqual(report["processedCount"], 1)
        self.assertEqual(report["unattemptedRemainingCount"], 1)
        self.assertEqual(report["unattemptedRemainingKeys"], [fresh["decisionKey"]])
        self.assertEqual(
            next_decisions["decisions"][held["decisionKey"]]["onboarding"]["status"],
            "awaiting_profile",
        )

    def test_same_name_wrong_sector_homepage_is_held(self) -> None:
        candidate = self.candidate("Movida", sector="AI / AGI", region="全球")
        wrong_page = self.page(
            "Movida",
            text=(
                "Movida is a car rental and mobility company. "
                "Reserve vehicles for travel, airports and long-term rentals."
            ),
            url="https://movida.example/",
        )
        synth_calls = []

        def synthesizer(**kwargs):
            synth_calls.append(kwargs)
            return self.synthesis(), ""

        next_decisions, report = self.prepare(
            candidate,
            resolver=lambda _name: (
                self.metadata("Movida", "https://movida.example/"),
                "",
            ),
            page_fetcher=lambda _url: wrong_page,
            synthesizer=synthesizer,
        )
        hold = next_decisions["decisions"][candidate["decisionKey"]]["onboarding"]
        self.assertEqual(hold["status"], "awaiting_profile")
        self.assertIn("does not support the candidate sector", hold["error"])
        self.assertEqual(synth_calls, [])
        self.assertIn("does not support the candidate sector", report["holds"][0]["reason"])

    def test_exact_existing_registry_identity_is_automatically_merged(self) -> None:
        candidate = self.candidate("Sample Brand")
        registry = {
            "companies": [
                {
                    "slug": "sample",
                    "name": "Sample",
                    "englishName": "Sample",
                    "aliases": ["Sample Brand"],
                }
            ]
        }
        next_decisions, report = self.prepare(candidate, registry=registry)
        decision = next_decisions["decisions"][candidate["decisionKey"]]
        self.assertEqual(decision["status"], "merged")
        self.assertEqual(decision["mergedSlug"], "sample")
        self.assertEqual(report["mergedKeys"], [candidate["decisionKey"]])

    def test_generated_slug_collision_is_held_not_sent_to_publisher(self) -> None:
        candidate = self.candidate()
        registry = {
            "companies": [
                {
                    "slug": "sample-ai",
                    "name": "Different Company",
                    "englishName": "Different Company",
                    "aliases": [],
                }
            ]
        }
        next_decisions, report = self.prepare(candidate, registry=registry)
        hold = next_decisions["decisions"][candidate["decisionKey"]]["onboarding"]
        self.assertEqual(hold["status"], "awaiting_profile")
        self.assertIn("already belongs to another company", hold["error"])
        self.assertIn("already belongs to another company", report["holds"][0]["reason"])

    def test_existing_requested_onboarding_is_never_overwritten(self) -> None:
        candidate = self.candidate()
        existing = {
            "status": "requested",
            "mode": "create",
            "profile": {
                "slug": "manual-sample",
                "name": "Sample AI",
                "region": "美国",
                "sector": "AI / AGI",
                "stage": "成长期",
                "summary": "这是管理员已经提交并等待发布的规范公司简介，自动流程不得覆盖。",
                "product": "管理员提交的产品说明。",
                "homepage": "https://manual.example/",
            },
            "evidenceFingerprint": onboarding.evidence_fingerprint(candidate),
            "requestedAt": "2026-08-08T00:30:00Z",
            "requestedBy": "VCIQ",
        }
        decisions = self.decisions(candidate, onboarding_state=existing)
        next_decisions, report = self.prepare(candidate, decisions=decisions)
        request = next_decisions["decisions"][candidate["decisionKey"]]["onboarding"]
        self.assertEqual(request["profile"]["slug"], "manual-sample")
        self.assertEqual(request["requestedBy"], "VCIQ")
        self.assertEqual(report["processedCount"], 0)

    def test_model_support_quotes_must_exist_on_official_page(self) -> None:
        page_text = (
            "Sample AI builds artificial intelligence infrastructure. "
            "The platform provides model serving and data workflows."
        )
        self.assertEqual(
            auto._supported_quotes(
                ["Sample AI builds artificial intelligence infrastructure."],
                page_text,
            ),
            ["Sample AI builds artificial intelligence infrastructure."],
        )
        self.assertEqual(
            auto._supported_quotes(["This sentence was invented by a model."], page_text),
            [],
        )

    def test_wikidata_person_exact_match_is_rejected(self) -> None:
        def fetch_json(url: str):
            query = parse_qs(urlsplit(url).query)
            action = query.get("action", [""])[0]
            if action == "wbsearchentities":
                return {"search": [{"id": "Q1"}]}
            return {
                "entities": {
                    "Q1": {
                        "labels": {"en": {"value": "Sample AI"}},
                        "aliases": {},
                        "descriptions": {},
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {"value": {"id": "Q5"}}
                                    }
                                }
                            ],
                            "P856": [
                                {
                                    "mainsnak": {
                                        "datavalue": {"value": "https://sample.ai/"}
                                    }
                                }
                            ],
                        },
                    }
                }
            }

        resolved, reason = auto.resolve_wikidata_company(
            "Sample AI", fetch_json=fetch_json
        )
        self.assertIsNone(resolved)
        self.assertIn("person", reason)


if __name__ == "__main__":
    unittest.main()
