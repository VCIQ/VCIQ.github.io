"""Regressions for the AMD / World Labs missed-news investigation.

Fixtures describe a publisher announcement, not a completed acquisition.
No live requests, publication writes, or synthetic source-health records.
"""
import json
from pathlib import Path
import unittest

from tools.crawl_articles import normalize_url, parse_feed_items, parse_mittrchina_items

ROOT = Path(__file__).resolve().parents[1]


class PrioritySourcePublicationTests(unittest.TestCase):
    def test_mittrchina_public_api_restores_the_reported_article(self):
        config = json.loads((ROOT / "config/intelligence_sources.json").read_text())
        spec = next(x for x in config["feeds"] if x["id"] == "mittrchina-public-news")
        self.assertEqual(spec["adapter"], "mittrchina_json")
        self.assertEqual(spec["sourceUrl"], "https://www.mittrchina.com/")
        row = {"id": 17028, "name": "World Labs被收购，李飞飞成为AMD第一位首席科学家",
               "summary": "媒体报道 AMD 与 World Labs 签署收购协议。", "start_time": 1790645454,
               "url": "https://untrusted.example/ignored"}
        body = json.dumps({"code": 10000, "data": {"items": [row, row, {**row, "id": "../x"}]}})
        items = parse_mittrchina_items(body, spec)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"]["url"], "https://www.mittrchina.com/news/detail/17028")
        self.assertEqual(items[0]["source"]["level"], "媒体报道")
        self.assertEqual(items[0]["publishedAt"], normalize_date_for_fixture())

    def test_mittrchina_error_is_not_misreported_as_an_empty_feed(self):
        for payload in [{"code": 403}, {"code": 10000, "data": {}}, []]:
            with self.assertRaises(ValueError):
                parse_mittrchina_items(json.dumps(payload), {"maxItems": 12})
        empty = json.dumps({"code": 10000, "data": {"items": []}})
        self.assertEqual(parse_mittrchina_items(empty, {}), [])

    def test_mittrchina_invalid_dates_ids_and_disabled_budget(self):
        base = {"id": 17028, "name": "AI research", "summary": "News", "start_time": 1790645454}
        invalid = [{**base, "id": True}, {**base, "start_time": False},
                   {**base, "start_time": -1}, {**base, "start_time": "yesterday"},
                   {**base, "start_time": 253402214400000}, {**base, "name": []}]
        self.assertEqual(parse_mittrchina_items(json.dumps({"code": 10000, "data": {"items": invalid}}), {}), [])
        self.assertEqual(parse_mittrchina_items(json.dumps({"code": 10000, "data": {"items": [base]}}), {"maxItems": 0}), [])

    def test_official_feed_accepts_world_labs_announcement(self):
        config = json.loads((ROOT / "config/intelligence_sources.json").read_text())
        specs = [x for x in config["feeds"] if x["id"] == "amd-newsroom"]
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec["adapter"], "rss")
        self.assertEqual(spec["sourceLevel"], "官方披露")
        self.assertEqual(spec["allowedHosts"], ["newsroom.amd.com"])
        feed = """<rss version="2.0"><channel><item>
        <title>AMD to Acquire World Labs to Advance the Future of AI Compute</title>
        <link>https://newsroom.amd.com/news/amd-acquire-world-labs/</link>
        <pubDate>Mon, 28 Sep 2026 00:00:00 GMT</pubDate>
        <description>Definitive agreement; subject to regulatory approvals.</description>
        </item></channel></rss>"""
        items = parse_feed_items(feed, spec)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"]["url"],
                         normalize_url("https://newsroom.amd.com/news/amd-acquire-world-labs/"))
        self.assertIn("subject to regulatory approvals", items[0]["summary"])

    def test_official_feed_rejects_external_host(self):
        config = json.loads((ROOT / "config/intelligence_sources.json").read_text())
        spec = next(x for x in config["feeds"] if x["id"] == "amd-newsroom")
        feed = """<rss><channel><item><title>AMD AI acquisition</title>
        <link>https://untrusted.example/news/</link>
        <pubDate>Mon, 28 Sep 2026 00:00:00 GMT</pubDate>
        </item></channel></rss>"""
        self.assertEqual(parse_feed_items(feed, spec), [])

    def test_projection_writer_has_a_guarded_pages_handoff(self):
        listener = (ROOT / ".github/workflows/publish-validated-data.yml").read_text()
        writer = (ROOT / ".github/workflows/publish-ranked-intelligence.yml").read_text()
        listener_header = listener.split("permissions:", 1)[0]
        self.assertIn("- Publish ranked intelligence homepage projection", listener_header)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", listener)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", listener)
        self.assertEqual(listener.count("gh workflow run pages.yml --ref main"), 1)
        # The observer owns this edge: avoid a competing second dispatch here.
        self.assertNotIn("gh workflow run pages.yml", writer)
        self.assertNotIn("- Build and deploy GitHub Pages", listener_header)


def normalize_date_for_fixture():
    from datetime import datetime, timezone
    return datetime.fromtimestamp(1790645454, tz=timezone.utc).date().isoformat()


if __name__ == "__main__":
    unittest.main()
