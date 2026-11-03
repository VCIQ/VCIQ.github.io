"""PR-05 aid/BVID and description-only fixture acceptance."""
import asyncio
import unittest
from pathlib import Path

from tests.test_social_contracts import fixture
from tools.social.adapters.bilibili import normalize_record
from tools.social.contracts import ContractError
from tools.social.worker import normalize_execution
from workers.mediacrawler import observer as om
from workers.mediacrawler.runtime_bilibili import search

TIME = "2026-10-23T12:00:00+00:00"


def raw(aid="12345"):
    return {"video_id": aid, "video_type": "video", "title": "合成机器人演示", "desc": "视频简介不是转录。", "create_time": 1700000000}


class BilibiliTests(unittest.TestCase):
    def setUp(self):
        self.job = fixture("crawl_job", "bili")

    def test_B01_aid_produces_av_identity(self):
        row = normalize_record(raw(), self.job, observed_at=TIME)
        self.assertEqual(row["signalId"], "bili:video:12345")
        self.assertTrue(row["canonicalUrl"].endswith("av12345"))
        with self.assertRaises(ContractError):
            normalize_record(raw("BV1d54y1g7db"), self.job, observed_at=TIME)

    def test_B02_alias_only_with_response_mapping(self):
        value = raw()
        self.assertEqual(normalize_record(value, self.job, observed_at=TIME)["nativeAliases"], [])
        value["observed_video_identity"] = {"aid": "12345", "bvid": "BV1d54y1g7db"}
        row = normalize_record(value, self.job, observed_at=TIME)
        self.assertEqual(row["nativeAliases"], ["bili:bvid:BV1d54y1g7db"])
        value["observed_video_identity"]["aid"] = "999"
        with self.assertRaises(ContractError):
            normalize_record(value, self.job, observed_at=TIME)

    def test_B03_equal_titles_do_not_merge_distinct_aids(self):
        first = normalize_record(raw("1"), self.job, observed_at=TIME)
        second = normalize_record(raw("2"), self.job, observed_at=TIME)
        self.assertEqual(first["title"], second["title"])
        self.assertNotEqual(first["signalId"], second["signalId"])

    def test_B04_description_never_becomes_transcript(self):
        row = normalize_record(raw(), self.job, observed_at=TIME)
        self.assertEqual(row["textScope"], "video_description")
        self.assertNotIn("transcript", row)
        self.assertEqual(row["evidence"]["grade"], "D")

    def run_pages(self, pages):
        observer = om.Observer(self.job, clock=lambda: TIME)
        class Client:
            async def search_video_by_keyword(self, **kwargs):
                assert kwargs["pubtime_begin_s"] == kwargs["pubtime_end_s"] == 0
                return pages[kwargs["page"] - 1]
            async def get_video_info(self, aid):
                return {"View": {"aid": aid, "bvid": "BV1d54y1g7db", "title": "test", "desc": "test", "owner": {}, "stat": {}}}
        class Store:
            async def update_bilibili_video(self, value):
                observer.capture(raw(str(value["View"]["aid"])))
        async def no_sleep(_): pass
        try:
            asyncio.run(search(Client(), Store(), om, observer, sleep=no_sleep))
        except om.Halt as exc:
            observer.fail(exc.status, exc.code)
        return normalize_execution(observer.payload(), self.job)

    def test_B05_empty_and_unknown_shapes_differ(self):
        self.assertEqual(self.run_pages([{"result": []}])["receipt"]["status"], "empty")
        self.assertEqual(self.run_pages([{}])["receipt"]["status"], "schema_error")

    def test_B05_normal_mode_bounded_and_explicit_final_page(self):
        first = self.run_pages([{"result": [{"aid": 12345}]}])
        self.assertEqual(first["receipt"]["completeness"], "bounded")
        final = self.run_pages([{"result": [{"aid": 12345}], "numPages": 1}])
        self.assertEqual(final["receipt"]["completeness"], "exhausted")
        self.assertEqual(final["observations"][0]["nativeAliases"], ["bili:bvid:BV1d54y1g7db"])

    def test_B03_duplicate_page_items_emit_one_record(self):
        value = self.run_pages([{"result": [{"aid": 12345}, {"aid": 12345}]}])
        self.assertEqual(len(value["observations"]), 1)
        self.assertEqual(value["receipt"]["counts"]["searchItems"], 2)

    def test_B06_legacy_person_discovery_not_called(self):
        source = Path(__file__).resolve().parents[1] / "workers/mediacrawler/runtime_bilibili.py"
        content = source.read_text()
        for forbidden in ("download_media(", "get_video_comments(", "update_up_info(", "person_video_discovery"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
