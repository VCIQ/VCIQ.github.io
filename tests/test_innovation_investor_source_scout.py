import unittest
from tools.innovation_investor_source_scout import ScoutError, extract_candidates, validate_url


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


if __name__ == "__main__":
    unittest.main()
