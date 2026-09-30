from datetime import datetime, timezone
from pathlib import Path
import json
import unittest

from tools.priority_intelligence import SOURCES, SOURCE_POLICY, collect, source_specs, LIMIT, SCAN_ARTIFACT_LIMIT
from tools.priority_incremental import collect_source

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 30, 2, tzinfo=timezone.utc)


class ApprovedPrioritySourceTests(unittest.TestCase):
    def test_only_the_six_confirmed_sources_are_added(self):
        expected = {"amd-newsroom", "mittrchina-public-news", "deepmind-blog", "google-ai-blog",
                    "openai-newsroom", "leiphone", "tmtpost", "techcrunch-venture"}
        self.assertEqual(set(SOURCES), expected)
        self.assertEqual({s["id"] for s in source_specs()}, expected)
        self.assertFalse(SOURCE_POLICY["autoPromoteCore"])
        self.assertEqual(SOURCE_POLICY["requestedIntervalMinutes"], 5)
        self.assertEqual(LIMIT, 300_000)
        self.assertEqual(SCAN_ARTIFACT_LIMIT, 1_000_000)
        workflow = (ROOT / ".github/workflows/priority-intelligence-refresh.yml").read_text()
        self.assertIn('cron: "*/5 * * * *"', workflow)
        self.assertNotIn('cron: "3-58/5 * * * *"', workflow)

    def test_source_types_and_canonical_google_endpoint_remain_explicit(self):
        specs = {s["id"]: s for s in source_specs()}
        self.assertIn("/innovation-and-ai/", specs["google-ai-blog"]["url"])
        for name in ("leiphone", "tmtpost", "techcrunch-venture"):
            self.assertEqual(SOURCES[name][2], "媒体报道")
        self.assertEqual(SOURCES["openai-newsroom"][2], "官方披露")

    def test_malformed_xml_isolated_to_one_source(self):
        specs = source_specs()
        def fetch(url):
            if "mittrchina" in url: return json.dumps({"code":10000,"data":{"items":[]}})
            if "openai" in url: return "<html>not RSS"
            return "<rss><channel /></rss>"
        result = collect(specs, NOW, fetcher=fetch)
        rows = {r["sourceId"]: r for r in result["sources"]}
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows["openai-newsroom"]["status"], "error")
        self.assertEqual(rows["amd-newsroom"]["status"], "empty")

    def test_ancient_tail_does_not_create_false_recent_gap(self):
        spec = next(s for s in source_specs() if s["id"] == "openai-newsroom")
        def feed(tail_date):
            return '<rss><channel>' + ''.join(
                f'<item><title>AI launch {i}</title><link>https://openai.com/index/item-{i}/</link>'
                f'<pubDate>{"Tue, 29 Sep 2026 12:00:00 GMT" if i < 2 else tail_date}</pubDate></item>'
                for i in range(70)) + '</channel></rss>'
        old = collect_source(spec, NOW, lambda _: feed("Tue, 01 Sep 2026 12:00:00 GMT"))
        self.assertFalse(old["historyGap"])
        recent = collect_source(spec, NOW, lambda _: feed("Tue, 29 Sep 2026 12:00:00 GMT"))
        self.assertTrue(recent["historyGap"])

    def test_candidates_are_not_rss_observations_or_runtime_approvals(self):
        data = json.loads((ROOT / "config/priority_media_candidates.json").read_text())
        self.assertTrue(data["runtimeEnabled"])
        self.assertTrue(data["approvalRequiredForPriorityPolling"])
        self.assertFalse(data["autoPromoteCore"])
        self.assertEqual(len(data["observationScope"]["topicFamilies"]), 10)
        self.assertEqual(len({r["id"] for r in data["candidates"]}), len(data["candidates"]))
        self.assertEqual(len(data["candidates"]), 6)
        self.assertTrue(all(r["status"] == "approved-direct-focus" for r in data["candidates"]))
        self.assertEqual({r["id"] for r in data["deferredByOwner"]}, {"eet-china", "c114", "xhby"})
        self.assertTrue(set(r["id"] for r in data["candidates"]).isdisjoint(SOURCES))
        raw = json.dumps(data).lower()
        for private_value in ("google.com/alerts/feeds", "gmail.com", "access_client_secret", "authorization", "google.com/url"):
            self.assertNotIn(private_value, raw)


if __name__ == "__main__": unittest.main()
