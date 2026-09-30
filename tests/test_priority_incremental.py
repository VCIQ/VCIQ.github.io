from datetime import datetime, timezone
import json
from urllib.parse import urlsplit, parse_qs
import unittest

from tools.priority_incremental import collect_source
from tools.priority_entity_linking import link_priority_entities
from tools.priority_intelligence import source_specs, finalize, config_hash

NOW = datetime(2026, 9, 30, 2, tzinfo=timezone.utc)


def publisher_row(i):
    return {"id": i, "name": "AMD World Labs 发布进展", "summary": "AMD and World Labs; Fei-Fei Li", "start_time": 1790715600}


class PriorityIncrementTests(unittest.TestCase):
    def test_title_and_summary_link_companies_and_person_without_approving_profiles(self):
        row = link_priority_entities({"sourceId": "amd-newsroom", "company": "科技产业", "title": "AMD to acquire World Labs", "summary": "World Labs was co-founded by Fei-Fei Li"})
        self.assertEqual(row["company"], "AMD")
        self.assertIn("World Labs", row["mentionedCompanies"])
        self.assertIn("李飞飞", row["mentionedPeople"])
        self.assertNotIn("companySlug", row)
        self.assertNotIn("personSlug", row)

    def test_ambiguous_names_and_substrings_do_not_get_forced_attribution(self):
        entities = [{"id": "a", "name": "Company A", "kind": "company", "aliases": ["ABC"]},
                    {"id": "b", "name": "Company B", "kind": "company", "aliases": ["ABC"]}]
        row = link_priority_entities({"title": "ABC launches", "summary": "", "company": "科技产业"}, entities)
        self.assertEqual(row["entityResolutionStatus"], "ambiguous")
        self.assertEqual(row["mentionedCompanies"], [])
        self.assertEqual(link_priority_entities({"title": "ABCD launches", "summary": ""}, entities)["entityResolutionStatus"], "unresolved")

    def test_multiple_company_mentions_never_create_a_compound_capture_entity(self):
        row = link_priority_entities({"sourceId": "mittrchina-public-news", "company": "科技产业",
                                     "title": "World Labs被收购，李飞飞成为AMD第一位首席科学家", "summary": "AMD / World Labs"})
        self.assertEqual(row["company"], "World Labs")
        self.assertEqual(set(row["mentionedCompanies"]), {"AMD", "World Labs"})
        self.assertEqual(row["mentionedPeople"], ["李飞飞"])

    def test_catchup_resumes_after_budget_instead_of_repeating_first_three_pages(self):
        spec = next(s for s in source_specs() if s["id"] == "mittrchina-public-news")
        ids = list(range(160, 19, -1)); calls = []
        def fetch(url):
            page = int(parse_qs(urlsplit(url).query)["page"][0]); calls.append(page)
            return json.dumps({"code": 10000, "data": {"items": [publisher_row(i) for i in ids[(page-1)*20:page*20]]}})
        cursor = {"anchorIds": ["30"], "pendingHeadIds": [], "resumePage": 2}
        visited = set(); complete = False
        for _ in range(10):
            calls.clear(); row = collect_source(spec, NOW, fetch, cursor); cursor = row["cursor"]
            self.assertLessEqual(len(calls), 3); self.assertEqual(calls[0], 1)
            visited.update(calls)
            if not row["pending"]: complete = True; break
        self.assertTrue(complete); self.assertIn(7, visited)
        self.assertIn("160", cursor["anchorIds"])

    def test_partial_page_failure_does_not_advance_the_cursor(self):
        spec = next(s for s in source_specs() if s["id"] == "mittrchina-public-news")
        cursor = {"anchorIds": ["30"], "pendingHeadIds": [], "resumePage": 2}
        def fetch(url):
            if "page=1&" not in url: raise OSError("network")
            return json.dumps({"code": 10000, "data": {"items": [publisher_row(i) for i in range(100, 80, -1)]}})
        row = collect_source(spec, NOW, fetch, cursor)
        self.assertEqual(row["status"], "partial"); self.assertEqual(row["cursor"], cursor)
        self.assertGreater(len(row["items"]), 0)

    def test_epoch_precision_is_retained_and_diagnostics_explain_invalid_date(self):
        spec = next(s for s in source_specs() if s["id"] == "mittrchina-public-news")
        invalid = {**publisher_row(2), "start_time": None}
        result = collect_source(spec, NOW, lambda _: json.dumps({"code": 10000, "data": {"items": [publisher_row(1), invalid]}}))
        self.assertIn("T", result["items"][0]["publishedAt"])
        self.assertEqual(result["items"][0]["publicationTimePrecision"], "second")
        self.assertTrue(any(t["reason"] == "invalid-publication-date" for t in result["trace"]))

    def test_empty_head_never_erases_the_last_known_checkpoint(self):
        spec = next(s for s in source_specs() if s["id"] == "mittrchina-public-news")
        cursor = {"anchorIds": ["30"], "pendingHeadIds": [], "resumePage": 2}
        row = collect_source(spec, NOW, lambda _: json.dumps({"code": 10000, "data": {"items": []}}), cursor)
        self.assertEqual(row["cursor"]["anchorIds"], ["30"])

    def test_capacity_overflow_is_reported_and_failed_sources_cannot_smuggle_items(self):
        from tests.test_priority_intelligence import item
        specs = source_specs()
        sources = []
        for spec in specs:
            rows = []
            for index in range(50):
                value = item(spec["id"]); value["id"] = spec["id"] + f"-{index}"
                value["source"] = {**value["source"], "url": value["source"]["url"] + str(index)}
                rows.append(value)
            sources.append({"sourceId": spec["id"], "status": "ok", "items": rows})
        scan = {"schemaVersion": 1, "policyVersion": "priority-publisher-v1", "configHash": config_hash(specs), "checkedAt": NOW.isoformat(), "sources": sources}
        result = finalize({}, scan, specs, NOW)
        self.assertEqual(len(result["items"]), 72)
        self.assertEqual(result["collectionSummary"]["capacityHeld"], 28)
        self.assertEqual(sum(x["reason"] == "snapshot-capacity" for x in result["collectionTrace"]), 28)
        sources[0]["status"] = "error"
        with self.assertRaises(ValueError): finalize({}, scan, specs, NOW)

    def test_snapshot_cap_is_explicit_and_first_observation_is_stable(self):
        specs = source_specs(); sources = []
        for spec in specs:
            if spec["id"] == "mittrchina-public-news":
                row = collect_source(spec, NOW, lambda _: json.dumps({"code": 10000, "data": {"items": [publisher_row(i) for i in range(20)]}}))
            else:
                row = {"sourceId": spec["id"], "status": "empty", "items": []}
            sources.append(row)
        scan = {"schemaVersion": 1, "policyVersion": "priority-publisher-v1", "configHash": config_hash(specs), "checkedAt": NOW.isoformat(), "sources": sources}
        first = finalize({}, scan, specs, NOW)
        second = finalize(first, scan, specs, NOW)
        self.assertEqual(first["items"][0]["firstSeenAt"], second["items"][0]["firstSeenAt"])
        self.assertIn("collectionTrace", second)
        self.assertEqual(second["collectionSummary"]["capacityHeld"], 0)

    def test_rss_gap_is_not_disguised_as_complete_catchup(self):
        spec = next(s for s in source_specs() if s["id"] == "amd-newsroom")
        feed = '<rss><channel><item><title>AMD AI update</title><link>https://newsroom.amd.com/news/new</link><pubDate>Tue, 29 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>'
        row = collect_source(spec, NOW, lambda _: feed, {"anchorIds": ["missing"], "pendingHeadIds": [], "resumePage": 2})
        self.assertTrue(row["historyGap"]); self.assertEqual(row["status"], "partial")


if __name__ == "__main__": unittest.main()
