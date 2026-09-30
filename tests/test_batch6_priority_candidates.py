from datetime import datetime, timezone, timedelta
import unittest

from tools.batch6_priority_candidates import finalize, validate_incoming, PUBLIC_LIMIT

NOW = datetime(2026, 9, 30, 3, tzinfo=timezone.utc)


def item(index=0, publisher="证券时报"):
    return {
        "id": f"batch6-rss-{index:024x}",
        "sourceId": "batch6-google-alerts",
        "title": f"硬科技公司完成Pre-IPO融资 {index}",
        "summary": "公司披露新一轮融资进展。",
        "publishedAt": (NOW - timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
        "type": "融资",
        "region": "全球",
        "sector": "科创资本",
        "company": "",
        "importance": 92,
        "source": {
            "name": publisher,
            "url": f"https://www.stcn.com/article/detail/{index}.html",
            "level": "待交叉验证",
            "platform": "Google Alerts RSS",
        },
        "radarQuery": "Pre-IPO 融资",
        "radarPriority": "P0",
    }


def payload(rows=None):
    return {
        "schemaVersion": 1,
        "policyVersion": "batch6-priority-v1",
        "generatedAt": NOW.isoformat().replace("+00:00", "Z"),
        "items": rows if rows is not None else [item()],
        "sourceSummary": {
            "configuredQueries": 10,
            "rssSources": 10,
            "healthySources": 10,
            "failedSources": 0,
            "observedItems": 1,
        },
    }


class Batch6PriorityCandidatesTests(unittest.TestCase):
    def test_valid_payload_publishes_bounded_public_snapshot(self):
        value = finalize({}, payload(), NOW)
        self.assertEqual(len(value["items"]), 1)
        self.assertEqual(value["sourceState"], "healthy")
        self.assertLess(len(str(value).encode()), PUBLIC_LIMIT)
        self.assertEqual(value["items"][0]["firstSeenAt"], payload()["generatedAt"])

    def test_previous_first_seen_is_stable(self):
        first = finalize({}, payload(), NOW)
        later = payload()
        later["generatedAt"] = (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        second = finalize(first, later, NOW + timedelta(minutes=5))
        self.assertEqual(first["items"][0]["firstSeenAt"], second["items"][0]["firstSeenAt"])

    def test_private_hosts_and_wrong_coverage_fail_closed(self):
        bad = payload()
        bad["items"][0]["source"]["url"] = "https://127.0.0.1/private"
        with self.assertRaises(ValueError):
            validate_incoming(bad, NOW)
        bad = payload()
        bad["sourceSummary"]["rssSources"] = 9
        with self.assertRaises(ValueError):
            validate_incoming(bad, NOW)

    def test_input_cap_and_stale_payload_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_incoming(payload([item(i) for i in range(25)]), NOW)
        stale = payload()
        stale["generatedAt"] = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaises(ValueError):
            validate_incoming(stale, NOW)

    def test_public_contract_contains_no_private_rss_metadata(self):
        raw = str(finalize({}, payload(), NOW)).lower()
        for forbidden in ("feedurl", "google.com/alerts/feeds", "authorization", "gmail.com"):
            self.assertNotIn(forbidden, raw)


if __name__ == "__main__":
    unittest.main()
