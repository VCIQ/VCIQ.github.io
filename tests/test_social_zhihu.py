"""PR-06 typed identity and raw-response observation regression tests."""
import asyncio
import unittest
from types import SimpleNamespace

from tests.test_social_contracts import fixture
from tools.social.adapters.zhihu import normalize_record
from tools.social.contracts import ContractError
from tools.social.worker import normalize_execution
from workers.mediacrawler import observer as om
from workers.mediacrawler.runtime_zhihu import search

TIME = "2026-10-23T12:00:00+00:00"


def raw(kind="answer", identifier="11"):
    return {"content_type": kind, "content_id": identifier, "question_id": "100", "title": "合成机器人",
            "content_text": "技术讨论", "desc": "简介", "created_time": 1700000000, "updated_time": 1700000100,
            "user_nickname": "测***"}


class ZhihuTests(unittest.TestCase):
    def setUp(self):
        self.job = fixture("crawl_job", "zhihu")

    def test_Z01_question_does_not_identify_answer(self):
        a = normalize_record(raw(identifier="11"), self.job, observed_at=TIME)
        b = normalize_record(raw(identifier="12"), self.job, observed_at=TIME)
        c = normalize_record(raw("article", "11"), self.job, observed_at=TIME)
        self.assertEqual(len({a["signalId"], b["signalId"], c["signalId"]}), 3)
        self.assertIn("/question/100/answer/11", a["canonicalUrl"])

    def test_Z02_creation_and_update_are_separate(self):
        row = normalize_record(raw(), self.job, observed_at=TIME)
        self.assertNotEqual(row["publishedAt"], row["updatedAt"])
        value = raw()
        value["created_time"] = 0
        self.assertIsNone(normalize_record(value, self.job, observed_at=TIME)["publishedAt"])

    def test_Z02_update_before_creation_is_rejected(self):
        value = raw()
        value["updated_time"] = 1600000000
        with self.assertRaises(ContractError):
            normalize_record(value, self.job, observed_at=TIME)

    def test_Z03_html_is_not_executable_text(self):
        value = raw()
        value["content_text"] = '<p>讨论<script>bad()</script><img src=x onerror=bad()>内容</p>'
        row = normalize_record(value, self.job, observed_at=TIME)
        self.assertNotIn("bad", row["excerpt"])
        self.assertNotIn("<", row["excerpt"])

    def test_Z04_empty_video_is_title_only(self):
        value = raw("zvideo")
        value.update(content_text="", desc="")
        row = normalize_record(value, self.job, observed_at=TIME)
        self.assertEqual(row["textScope"], "title_only")
        self.assertEqual(row["excerpt"], "")

    def test_Z05_unknown_type_rejected(self):
        with self.assertRaisesRegex(ContractError, "zhihu_record_type"):
            normalize_record(raw("unknown"), self.job, observed_at=TIME)

    def run_response(self, response, *, drop=False):
        observer = om.Observer(self.job, clock=lambda: TIME)
        class Client:
            async def get(self, uri, params=None, **kwargs): return response
            async def get_note_by_keyword(self, **kwargs):
                value = await self.get("/api/v4/search_v3", {"q": kwargs["keyword"]})
                return [] if drop else [SimpleNamespace(**raw(row["object"]["type"], str(row["object"]["id"]))) for row in value["data"] if row.get("object")]
        class Store:
            async def update_zhihu_content(self, value): observer.capture(vars(value))
        async def no_sleep(_): pass
        try:
            asyncio.run(search(Client(), Store(), om, observer, sleep=no_sleep))
        except om.Halt as exc:
            observer.fail(exc.status, exc.code)
        return normalize_execution(observer.payload(), self.job)

    def test_Z05_raw_shape_not_hidden_by_empty_extractor(self):
        self.assertEqual(self.run_response({})["receipt"]["status"], "schema_error")
        value = {"data": [{"type": "search_result", "object": {"type": "answer", "id": 11}}], "paging": {"is_end": True}}
        self.assertEqual(self.run_response(value, drop=True)["receipt"]["status"], "schema_error")

    def test_Z05_empty_only_with_observed_end(self):
        self.assertEqual(self.run_response({"data": [], "paging": {"is_end": True}})["receipt"]["status"], "empty")
        self.assertEqual(self.run_response({"data": []})["receipt"]["status"], "schema_error")

    def test_three_types_and_unknown_pagination_are_bounded(self):
        value = {"data": [{"type": "search_result", "object": {"type": kind, "id": n}} for n, kind in enumerate(("answer", "article", "zvideo"), 1)]}
        result = self.run_response(value)
        self.assertEqual({row["contentType"] for row in result["observations"]}, {"answer", "article", "zvideo"})
        self.assertEqual(result["receipt"]["completeness"], "bounded")


if __name__ == "__main__":
    unittest.main()
