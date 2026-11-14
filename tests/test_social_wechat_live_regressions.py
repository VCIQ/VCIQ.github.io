"""Offline reproductions of failures found by the first bounded Mac smoke run."""
import socket
import ssl
import unittest
from unittest.mock import patch

from tests.test_social_wechat import FakeTransport, NOW, ORIGINAL, make_job
from tools.social.adapters import wechat
from tools.social.adapters.wechat_transport import FetchError, PublicTransport
from tools.social.batch import build_batch


class WechatRecordBudgetTests(unittest.TestCase):
    def run_rows(self, *, limit=1, article=None, pages=1, rows=10):
        job, context = make_job(pages=pages)
        job["limits"]["maxRecords"] = limit
        transport = FakeTransport(article=article)
        cards = [{"url": ORIGINAL, "title": "合成机器人文章"} for _ in range(rows)]
        with patch.object(wechat, "_search_page", return_value=(cards, True)):
            result = wechat.run_job(job, context, transport, now=lambda: NOW)
        build_batch([job], [result["receipt"]], result["observations"], created_at=NOW.isoformat())
        return job, transport, result

    def test_positive_search_page_larger_than_cap_still_seals(self):
        _, transport, result = self.run_rows()
        self.assertEqual(result["receipt"]["counts"]["searchItems"], 10)
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 1)
        self.assertEqual(result["receipt"]["counts"]["emittedRows"], 1)
        self.assertEqual(result["receipt"]["counts"]["budgetSkipped"], 0)
        self.assertEqual(result["diagnostics"]["detailsNotRequested"], 9)
        self.assertEqual(len(transport.urls), 2)

    def test_failed_detail_consumes_budget_not_replaced_by_extra_attempt(self):
        _, transport, result = self.run_rows(article=FetchError("network_error", "DETAIL_FAILURE"))
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 1)
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)
        self.assertEqual(result["receipt"]["status"], "network_error")
        self.assertEqual(result["observations"], [])
        self.assertEqual(len(transport.urls), 2)

    def test_content_rejection_also_consumes_budget(self):
        _, transport, result = self.run_rows(article=FetchError("schema_error", "IRRELEVANT_ORIGINAL"))
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 1)
        self.assertEqual(result["receipt"]["counts"]["detailFailures"], 0)
        self.assertEqual(result["receipt"]["stopReason"], "item_limit")
        self.assertEqual(len(transport.urls), 2)

    def test_duplicate_details_do_not_allow_unbounded_retry(self):
        _, transport, result = self.run_rows(limit=2)
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 2)
        self.assertEqual(result["receipt"]["counts"]["duplicateRows"], 1)
        self.assertEqual(result["diagnostics"]["detailsNotRequested"], 8)
        self.assertEqual(len(transport.urls), 3)

    def test_budget_does_not_reset_across_search_pages(self):
        _, transport, result = self.run_rows(limit=2, pages=3, rows=1)
        self.assertEqual(len(result["receipt"]["pageReceipts"]), 2)
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 2)
        self.assertEqual(len(transport.urls), 4)

    def test_restriction_stops_immediately_without_consuming_other_records(self):
        _, transport, result = self.run_rows(limit=2, article=FetchError("verification_required", "VERIFICATION_REQUIRED"))
        self.assertEqual(result["receipt"]["stopReason"], "verification")
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 1)
        self.assertEqual(len(transport.urls), 2)


class WechatTLSTests(unittest.TestCase):
    def failure(self, error):
        closed, debits = [], []
        class Connection:
            def request(self, *args, **kwargs): raise error
            def close(self): closed.append(True)
        transport = PublicTransport(before_request=lambda: debits.append(True), deadline=100,
            monotonic=lambda: 0, sleep=lambda _: None, connection_factory=lambda *args, **kwargs: Connection())
        with self.assertRaises(FetchError) as caught:
            transport.get("https://www.bing.com/search?q=synthetic")
        self.assertEqual(closed, [True]); self.assertEqual(debits, [True])
        self.assertNotIn("PRIVATE", str(caught.exception))
        return caught.exception

    def test_certificate_failure_has_specific_fixed_error_code(self):
        error = self.failure(ssl.SSLCertVerificationError(1, "PRIVATE certificate details"))
        self.assertEqual(error.status, "network_error")
        self.assertEqual(error.code, "TLS_CERTIFICATE_VERIFY_FAILED")

    def test_other_tls_failure_not_misreported_as_generic_network(self):
        self.assertEqual(self.failure(ssl.SSLError(1, "PRIVATE handshake")).code, "TLS_HANDSHAKE_FAILED")

    def test_ordinary_network_failure_stays_distinct(self):
        self.assertEqual(self.failure(OSError("PRIVATE connection")).code, "NETWORK_ERROR")

    def test_dns_failure_has_specific_fixed_error_code(self):
        self.assertEqual(self.failure(socket.gaierror("PRIVATE DNS")).code, "DNS_LOOKUP_FAILED")

    def test_timeout_stays_distinct(self):
        self.assertEqual(self.failure(TimeoutError("PRIVATE timeout")).status, "timeout")


if __name__ == "__main__": unittest.main()
