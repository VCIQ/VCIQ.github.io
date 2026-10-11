import unittest
from unittest.mock import patch
from tools.innovation_investor_source_scout import MAX_BYTES, ScoutError, extract_candidates, scout, validate_url


class InvestorSourceScoutTests(unittest.TestCase):
    def test_same_domain_only_and_credentials_rejected(self):
        for url in ["http://example.com/news", "https://x:secret@example.com/news", "https://evil.test/news", "https://127.0.0.1/news"]:
            with self.subTest(url=url), self.assertRaises(ScoutError):
                validate_url(url, "example.com", resolve_dns=False)
        self.assertEqual(validate_url("https://www.example.com/news#part", "example.com", resolve_dns=False), "https://www.example.com/news")

    def test_candidates_are_unreviewed_not_investments(self):
        html = '<a href="/insights/robotics">Robotics investment thesis</a><a href="/team/person">投资人团队</a><a href="https://evil.test/news">External report</a><a href="/login">Login</a>'
        rows = extract_candidates(html, "https://example.com/", "example")
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertFalse(row["investmentRelationConfirmed"])
            self.assertIsNone(row["publishedAt"])
            self.assertEqual(row["claimStatus"], "unreviewed-navigation-candidate")

    def test_duplicate_links_and_navigation_never_inflate_captured_events(self):
        html = '<a href="/news/one">News item</a>' * 20
        rows = extract_candidates(html, "https://example.com/", "example")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], extract_candidates(html, "https://example.com/", "example")[0]["id"])

    def test_sensitive_query_and_script_links_not_exported(self):
        html = '<a href="/news?token=private">News</a><script><a href="/news/bad">Bad</a></script><a href="/portfolio/company">Company investment</a>'
        rows = extract_candidates(html, "https://example.com/", "example")
        self.assertEqual(len(rows), 1)
        self.assertNotIn("token", str(rows))



    def test_same_domain_official_news_entry_point(self):
        firm = {
            "id": "firm",
            "officialUrl": "https://www.example.com/",
            "discoveryUrl": "https://www.example.com/news",
        }
        html = '<a href="/news/robotics-investment">Robotics investment</a>'
        with patch("tools.innovation_investor_source_scout.fetch_page") as mocked:
            mocked.return_value = ("https://www.example.com/news", html, "digest")
            result = scout(firm)
        mocked.assert_called_once_with("https://www.example.com/news", "www.example.com")
        self.assertEqual(result["status"], "candidates-found")
        self.assertEqual(result["sourceUrl"], firm["discoveryUrl"])
        self.assertEqual(result["candidates"][0]["claimStatus"], "unreviewed-navigation-candidate")
        self.assertFalse(result["candidates"][0]["investmentRelationConfirmed"])

    def test_index_news_late_article_links_are_not_displaced_by_old_carousel(self):
        # On the actual Index news page, old generic Read-more carousel links
        # precede the current dated article listing in the HTML.
        old = "".join(f'<a href="/perspectives/old-{i}/">Read more</a>' for i in range(18))
        recent = (
            '<a href="/perspectives/making-quantum-computing-real-our-investment-in-oratomic/">'
            'Making Quantum Computing Real: Our Investment in Oratomic by Martin Mignot '
            'This link opens the post, "Making Quantum Computing Real"</a>'
            '<a href="/perspectives/ai-that-owns-business-outcomes-our-investment-in-hone/">'
            'AI That Owns Business Outcomes: Our Investment in Hone by Shardul Shah, Mark Xu '
            'This link opens the post, "AI That Owns Business Outcomes"</a>'
            '<a href="https://untrusted.example.org/perspectives/investing-in-fake/">'
            'Fake source This link opens the post</a>'
        )
        url = "https://www.indexventures.com/perspectives/news/"
        rows = extract_candidates(old + recent, url, "index")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("This link opens the post" not in row["title"] for row in rows))
        self.assertTrue(any("oratomic" in row["url"] for row in rows))
        self.assertTrue(any("hone" in row["url"] for row in rows))
        self.assertTrue(all(row["publishedAt"] is None for row in rows))
        self.assertTrue(all(row["claimStatus"] == "unreviewed-navigation-candidate"
                            and row["investmentRelationConfirmed"] is False for row in rows))
        self.assertEqual([row["id"] for row in rows],
                         [row["id"] for row in extract_candidates(old + recent, url, "index")])

    def test_index_news_entry_remains_on_registered_official_domain(self):
        index = {"id": "index", "officialUrl": "https://www.indexventures.com/",
                 "discoveryUrl": "https://www.indexventures.com/perspectives/news/"}
        html = ('<a href="/perspectives/making-quantum-computing-real-our-investment-in-oratomic/">'
                'Our Investment in Oratomic This link opens the post</a>')
        with patch("tools.innovation_investor_source_scout.fetch_page") as fetch:
            fetch.return_value = (index["discoveryUrl"], html, "digest")
            result = scout(index)
        fetch.assert_called_once_with(index["discoveryUrl"], "www.indexventures.com")
        self.assertEqual(result["status"], "candidates-found")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["sourceUrl"], index["discoveryUrl"])
        self.assertFalse(result["candidates"][0]["investmentRelationConfirmed"])

    def test_cross_domain_news_entry_is_rejected_before_network(self):
        firm = {
            "id": "firm",
            "officialUrl": "https://www.example.com/",
            "discoveryUrl": "https://not-official.example.org/news",
        }
        with patch("tools.innovation_investor_source_scout.fetch_page") as mocked:
            result = scout(firm)
        mocked.assert_not_called()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "off-domain")

    def test_official_html_limit_is_still_strictly_bounded(self):
        self.assertGreaterEqual(MAX_BYTES, 900_000)
        self.assertLessEqual(MAX_BYTES, 1_048_576)

if __name__ == "__main__":
    unittest.main()
