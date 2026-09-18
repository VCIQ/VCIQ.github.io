from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import company_official_source_discovery as discovery
from tools import prepare_company_candidate_onboarding_v2 as onboarding_v2


class CompanyOfficialSourceDiscoveryTests(unittest.TestCase):
    def candidate(self, name: str = "Taalas", *, sector: str = "AI / AGI") -> dict:
        return {
            "decisionKey": name.casefold().replace(" ", ""),
            "name": name,
            "aliases": [name],
            "region": "全球",
            "sector": sector,
            "sourceUrls": ["https://news.example/article"],
        }

    def page(
        self,
        url: str,
        *,
        text: str = "Taalas builds AI chip infrastructure",
    ) -> dict:
        return {
            "url": url,
            "title": "Taalas",
            "description": text,
            "text": text,
            "newsUrls": [],
        }

    def decisions(self, key: str) -> dict:
        return {
            "decisions": {
                key: {
                    "status": "accepted",
                    "note": "manual",
                    "reviewedBy": "VCIQ",
                }
            }
        }

    def test_brand_domain_candidates_are_bounded_and_exact(self) -> None:
        urls = discovery.brand_domain_candidates("Taalas")
        self.assertIn("https://taalas.com/", urls)
        self.assertIn("https://taalas.ai/", urls)
        self.assertLessEqual(len(urls), 8)
        self.assertEqual(discovery.brand_domain_candidates("AI"), [])

    def test_source_link_candidates_require_candidate_signal(self) -> None:
        candidate = self.candidate()

        def fetcher(_url: str):
            return [
                {"url": "https://taalas.com/", "anchor": "Taalas official site"},
                {"url": "https://x.com/taalas", "anchor": "Taalas"},
                {"url": "https://news.example/other", "anchor": "Taalas"},
                {"url": "https://unrelated.example/", "anchor": "read more"},
            ]

        self.assertEqual(
            discovery.source_link_candidates(candidate, source_link_fetcher=fetcher),
            ["https://taalas.com/"],
        )

    def test_verified_source_article_link_wins_before_domain_probes(self) -> None:
        candidate = self.candidate()
        fetched: list[str] = []

        def source_fetcher(_url: str):
            return [{"url": "https://taalas.com/", "anchor": "Taalas"}]

        def page_fetcher(url: str):
            fetched.append(url)
            if url == "https://taalas.com/":
                return self.page(url)
            raise AssertionError(
                f"brand probe should not run after verified source link: {url}"
            )

        metadata, reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=page_fetcher,
            identity_checker=lambda page, names: "Taalas" in page["text"]
            and "Taalas" in names,
            sector_checker=lambda page, sector: "AI chip" in page["text"]
            and sector == "AI / AGI",
            source_link_fetcher=source_fetcher,
        )
        self.assertEqual(reason, "")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata["source"], "source-article-link")
        self.assertEqual(metadata["homepage"], "https://taalas.com/")
        self.assertEqual(fetched, ["https://taalas.com/"])

    def test_brand_domain_probe_can_verify_emerging_company_without_wikidata(self) -> None:
        candidate = self.candidate("Firmus")

        def page_fetcher(url: str):
            if url == "https://firmus.ai/":
                return {
                    "url": url,
                    "title": "Firmus",
                    "description": "Firmus builds artificial intelligence infrastructure",
                    "text": "Firmus builds artificial intelligence infrastructure",
                    "newsUrls": [],
                }
            raise OSError("not found")

        metadata, reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=page_fetcher,
            identity_checker=lambda page, names: "Firmus" in page["text"]
            and "Firmus" in names,
            sector_checker=lambda page, _sector: "artificial intelligence"
            in page["text"],
            source_link_fetcher=lambda _url: [],
        )
        self.assertEqual(reason, "")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata["source"], "brand-domain-probe")
        self.assertEqual(metadata["homepage"], "https://firmus.ai/")

    def test_multiple_verified_hosts_fail_closed(self) -> None:
        candidate = self.candidate()

        def source_fetcher(_url: str):
            return [
                {"url": "https://taalas.com/", "anchor": "Taalas"},
                {"url": "https://taalas.ai/", "anchor": "Taalas"},
            ]

        metadata, reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=lambda url: self.page(url),
            identity_checker=lambda _page, _names: True,
            sector_checker=lambda _page, _sector: True,
            source_link_fetcher=source_fetcher,
        )
        self.assertIsNone(metadata)
        self.assertIn("multiple verified official hosts", reason)

    def test_wrong_sector_domain_is_not_promoted(self) -> None:
        candidate = self.candidate("Movida", sector="AI / AGI")

        def page_fetcher(url: str):
            if "movida" not in url:
                raise OSError("not found")
            return {
                "url": url,
                "title": "Movida",
                "description": "Movida car rental and travel mobility",
                "text": "Movida car rental and travel mobility",
                "newsUrls": [],
            }

        metadata, reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=page_fetcher,
            identity_checker=lambda _page, _names: True,
            sector_checker=lambda page, _sector: "artificial intelligence"
            in page["text"],
            source_link_fetcher=lambda _url: [],
        )
        self.assertIsNone(metadata)
        self.assertIn("no verified official site", reason)

    def test_v2_prefers_exact_wikidata_before_domain_discovery(self) -> None:
        candidate = self.candidate("Taalas")
        wikidata = {
            "source": "wikidata",
            "canonicalName": "Taalas",
            "englishName": "Taalas",
            "homepage": "https://verified.example/",
            "region": "美国",
            "aliases": [],
        }
        with patch.object(
            onboarding_v2.preparation,
            "resolve_wikidata_company",
            return_value=(wikidata, ""),
        ) as wikidata_mock, patch.object(
            onboarding_v2.discovery,
            "discover_verified_official_site",
        ) as discover_mock:
            verified, report = onboarding_v2.discover_candidate_identities(
                {"candidates": [candidate]},
                self.decisions("taalas"),
                {"companies": []},
                {"companies": []},
                limit=6,
            )
        self.assertEqual(verified["taalas"]["homepage"], "https://verified.example/")
        self.assertEqual(report["verifiedSources"]["taalas"], "wikidata")
        self.assertEqual(report["attemptedFailureCount"], 0)
        wikidata_mock.assert_called_once_with("Taalas")
        discover_mock.assert_not_called()

    def test_v2_uses_evidence_discovery_after_wikidata_failure(self) -> None:
        candidate = self.candidate("Taalas")
        metadata = {
            "source": "brand-domain-probe",
            "canonicalName": "Taalas",
            "englishName": "Taalas",
            "homepage": "https://taalas.com/",
            "region": "全球",
            "aliases": [],
        }
        with patch.object(
            onboarding_v2.preparation,
            "resolve_wikidata_company",
            return_value=(None, "wikidata has no exact identity"),
        ), patch.object(
            onboarding_v2.discovery,
            "discover_verified_official_site",
            return_value=(metadata, ""),
        ) as discover_mock:
            verified, report = onboarding_v2.discover_candidate_identities(
                {"candidates": [candidate]},
                self.decisions("taalas"),
                {"companies": []},
                {"companies": []},
                limit=6,
            )
        self.assertEqual(verified["taalas"]["homepage"], "https://taalas.com/")
        self.assertEqual(report["verifiedSources"]["taalas"], "brand-domain-probe")
        self.assertEqual(report["attemptedFailureCount"], 0)
        discover_mock.assert_called_once()

    def test_v2_caches_negative_identity_resolution_for_core_preparer(self) -> None:
        candidate = {
            **self.candidate("Unresolved AI"),
            "id": "candidate-unresolvedai",
            "score": 75,
            "status": "accepted",
            "articleCount": 1,
            "sourceCount": 1,
            "sourceArticleIds": ["article-a"],
            "eventTypes": ["产品发布"],
            "captureIds": [],
        }
        with patch.object(
            onboarding_v2.preparation,
            "resolve_wikidata_company",
            return_value=(None, "wikidata has no exact identity"),
        ) as wikidata_mock, patch.object(
            onboarding_v2.discovery,
            "discover_verified_official_site",
            return_value=(None, "no verified official site"),
        ) as discover_mock:
            next_decisions, report = onboarding_v2.run(
                candidates_payload={"candidates": [candidate]},
                decisions_payload=self.decisions("unresolvedai"),
                official_sources_payload={"companies": []},
                registry_payload={"companies": []},
                captures_payload={"records": []},
                limit=6,
            )
        hold = next_decisions["decisions"]["unresolvedai"]["onboarding"]
        self.assertEqual(hold["status"], "awaiting_profile")
        self.assertIn("no verified official site", hold["error"])
        self.assertEqual(report["sourceDiscovery"]["attemptedFailureCount"], 1)
        self.assertIn(
            "wikidata has no exact identity",
            report["sourceDiscovery"]["attemptedReasons"]["unresolvedai"],
        )
        self.assertEqual(wikidata_mock.call_count, 1)
        self.assertEqual(discover_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
