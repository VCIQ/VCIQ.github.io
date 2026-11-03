"""PR-04 Weibo fixture acceptance; live acceptance is separate."""
import asyncio
import unittest
from types import SimpleNamespace

from tests.test_social_contracts import fixture
from tools.social.adapters.weibo import normalize_record
from tools.social.contracts import ContractError
from tools.social.worker import normalize_execution
from workers.mediacrawler import observer as om
from workers.mediacrawler.runtime_weibo import search

TIME = "2026-10-23T12:00:00+00:00"
IDENTIFIER = "90071992547409931234"


def raw():
    return {"note_id": IDENTIFIER, "content": "合成测试机器人发布产品", "create_time": 1700000000,
            "create_date_time": "2023-11-15 06:13:20", "nickname": "测***"}


class WeiboTests(unittest.TestCase):
    def setUp(self):
        self.job = fixture("crawl_job", "wb")

    def test_WB01_large_id_never_passes_through_float(self):
        value = raw()
        value["note_id"] = int(IDENTIFIER)
        row = normalize_record(value, self.job, observed_at=TIME)
        self.assertEqual(row["nativeId"], IDENTIFIER)

    def test_WB02_html_scripts_emoji_and_derived_title(self):
        value = raw()
        value["content"] = '<div>机器人 🚀<script>alert(1)</script><br>新品 &amp; 演示</div>'
        row = normalize_record(value, self.job, observed_at=TIME)
        self.assertNotIn("alert", row["excerpt"])
        self.assertIn("🚀", row["excerpt"])
        self.assertEqual(row["titleOrigin"], "derived")

    def test_WB03_no_fabricated_parent_or_real_author(self):
        row = normalize_record(raw(), self.job, observed_at=TIME)
        self.assertEqual(row["entityCandidates"], [])
        self.assertEqual(row["nativeAliases"], [])
        self.assertNotIn("originId", row)
        self.assertEqual(row["author"]["maskStatus"], "masked")

    def test_WB04_timezone_equivalence_and_conflict(self):
        row = normalize_record(raw(), self.job, observed_at=TIME)
        self.assertEqual(row["publishedAt"], "2023-11-14T22:13:20+00:00")
        value = raw()
        value["create_date_time"] = "2023-11-15 07:13:20"
        with self.assertRaisesRegex(ContractError, "weibo_time_conflict"):
            normalize_record(value, self.job, observed_at=TIME)

    def test_WB04_unknown_date_stays_null(self):
        value = raw()
        value.update(create_time=0, create_date_time=None, last_modify_ts=1700000000)
        self.assertIsNone(normalize_record(value, self.job, observed_at=TIME)["publishedAt"])

    def run_pages(self, responses):
        observer = om.Observer(self.job, clock=lambda: TIME)
        class Client:
            async def get_note_by_keyword(self, **kwargs):
                response = responses[kwargs["page"] - 1]
                if isinstance(response, Exception):
                    raise response
                return response
        class Store:
            async def update_weibo_note(self, note):
                observer.capture({**raw(), "content": note["mblog"]["text"]})
        async def no_sleep(_):
            pass
        try:
            asyncio.run(search(Client(), Store(), om, observer, sleep=no_sleep))
        except om.Halt as exc:
            observer.fail(exc.status, exc.code)
        return normalize_execution(observer.payload(), self.job)

    def test_WB05_page_one_then_verification_retains_partial(self):
        self.job["limits"]["maxSearchPages"] = 2
        first = {"cards": [{"card_type": 9, "mblog": {"id": IDENTIFIER, "text": "合成测试机器人"}}]}
        result = self.run_pages([first, om.Halt("verification_required", "HTTP_VERIFICATION")])
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)

    def test_WB05_unknown_shape_is_not_empty(self):
        self.assertEqual(self.run_pages([{}])["receipt"]["status"], "schema_error")

    def test_WB05_explicit_empty_cards(self):
        self.assertEqual(self.run_pages([{"cards": []}])["receipt"]["status"], "empty")

    def test_nested_cards_and_noncontent_cards(self):
        response = {"cards": [{"card_type": 11, "card_group": [{"card_type": 9, "mblog": {"id": IDENTIFIER, "text": "合成测试机器人"}}]}]}
        result = self.run_pages([response])
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["receipt"]["completeness"], "bounded")


if __name__ == "__main__":
    unittest.main()
