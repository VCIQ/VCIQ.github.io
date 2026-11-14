"""Read-only HTTP dispatch tests with actual SQLite, but no listening socket."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.social_review_fixtures import add, registry
from tools.social.batch import ROOT
from tools.social.review import ReviewStore
from tools.social.signal_store import SignalStore
from tools.social import review_web as web


class ReviewWebTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        with SignalStore(self.root) as source, ReviewStore(self.root) as review:
            add(source); review.materialize(source, registry())
        self.headers = {"Host": "127.0.0.1:8767"}
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("no external I/O")))

    def fetch(self, target="/api/queue", method="GET", headers=None):
        return web.response(method, target, self.headers if headers is None else headers, root=self.root, roots=(ROOT,), port=8767)

    def test_queue_read_is_paginated_and_readonly(self):
        before = {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}
        status, media_type, body = self.fetch()
        value = json.loads(body)
        self.assertEqual(status, 200); self.assertIn("application/json", media_type)
        self.assertEqual(value["total"], 1); self.assertFalse(value["publish"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")})

    def test_assets_are_exact_local_files(self):
        for target, expected in (("/", "text/html"), ("/app.js", "text/javascript"), ("/style.css", "text/css")):
            status, media_type, body = self.fetch(target)
            self.assertEqual(status, 200); self.assertIn(expected, media_type); self.assertTrue(body)

    def test_all_mutation_methods_are_refused(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method): self.assertEqual(self.fetch(method=method)[0], 405)

    def test_no_arbitrary_file_or_database_route(self):
        for target in ("/reviews.sqlite3", "/signals.sqlite3", "/runtime.json", "/../runtime.json", "/%2e%2e/runtime.json", "/api/decide", "/api/queue/extra", "/favicon.ico"):
            with self.subTest(target=target): self.assertIn(self.fetch(target)[0], (400, 404))

    def test_dns_rebinding_hosts_and_ports_denied(self):
        for host in ("localhost:8767", "evil.invalid:8767", "127.0.0.1", "127.0.0.1:9999", "127.0.0.1.evil.invalid:8767", "[::1]:8767"):
            self.assertEqual(self.fetch(headers={"Host": host})[0], 403)
        self.assertEqual(self.fetch(headers={})[0], 403)

    def test_origin_fetch_site_and_null_origin_denied(self):
        for extra in ({"Origin": "http://evil.invalid"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"}):
            self.assertEqual(self.fetch(headers={**self.headers, **extra})[0], 403)
        self.assertEqual(self.fetch(headers={**self.headers, "Origin": "http://127.0.0.1:8767", "Sec-Fetch-Site": "same-origin"})[0], 200)

    def test_bad_query_and_duplicate_parameters_denied(self):
        for query in ("offset=-1", "offset=1e3", "limit=101", "limit=0", "offset=0&offset=1", "history=1", "q=PRIVATE", "offset", "offset=9999999999999999"):
            self.assertIn(self.fetch("/api/queue?" + query)[0], (400, 409))

    def test_request_body_transfer_encoding_and_absolute_targets_denied(self):
        for extra in ({"Content-Length": "1"}, {"Transfer-Encoding": "chunked"}):
            self.assertEqual(self.fetch(headers={**self.headers, **extra})[0], 400)
        for target in ("https://evil.invalid/api/queue", "//evil.invalid/api/queue", "/api/queue#x", "/" + "x" * 4097):
            self.assertEqual(self.fetch(target)[0], 400)

    def test_missing_database_not_created_by_http_read(self):
        (self.root / "reviews.sqlite3").unlink()
        self.assertEqual(self.fetch()[0], 409)
        self.assertFalse((self.root / "reviews.sqlite3").exists())

    def test_error_does_not_echo_exception_or_private_path(self):
        with patch.object(web, "ReviewStore", side_effect=RuntimeError("Cookie=PRIVATE_SECRET /private/path")):
            result = self.fetch()
        self.assertEqual(result[0], 503); self.assertNotIn(b"PRIVATE_SECRET", result[2]); self.assertNotIn(b"/private/path", result[2])

    def test_history_and_page_bounds(self):
        result = json.loads(self.fetch("/api/queue?offset=0&limit=10&history=true")[2])
        self.assertTrue(result["history"]); self.assertEqual(result["items"], [])
        self.assertEqual(json.loads(self.fetch("/api/queue?offset=999&limit=1")[2])["items"], [])

    def test_security_headers_have_no_remote_or_inline_permissions(self):
        csp = web.SECURITY_HEADERS["Content-Security-Policy"]
        for directive in ("default-src 'none'", "script-src 'self'", "frame-ancestors 'none'", "form-action 'none'"):
            self.assertIn(directive, csp)
        self.assertNotIn("unsafe-inline", csp); self.assertNotIn("unsafe-eval", csp)
        self.assertNotIn("Access-Control-Allow-Origin", web.SECURITY_HEADERS)
        self.assertEqual(web.SECURITY_HEADERS["Cache-Control"], "no-store")
        self.assertEqual(web.SECURITY_HEADERS["Referrer-Policy"], "no-referrer")

    def test_ui_uses_text_nodes_and_has_no_write_api(self):
        js = (web.ASSETS / "app.js").read_text()
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "localStorage", "method: 'POST'", "fetch('http"):
            self.assertNotIn(forbidden, js)
        self.assertIn("textContent", js); self.assertIn("makeDecision", js)
        html = (web.ASSETS / "index.html").read_text()
        self.assertIn('lang="zh-CN"', html); self.assertIn('role="alert"', html)
        self.assertNotIn('https://', html); self.assertNotIn('<form', html)

    def test_oversized_response_and_asset_query_refused(self):
        with patch.object(web, "MAX_RESPONSE", 10): self.assertEqual(self.fetch()[0], 413)
        self.assertEqual(self.fetch("/app.js?source=external")[0], 404)

    def test_head_dispatch_body_matches_get_for_handler_to_omit(self):
        self.assertEqual(self.fetch(method="HEAD"), self.fetch(method="GET"))

    def test_server_bind_is_fixed_loopback(self):
        import http.server
        captured = []
        with patch.object(http.server.HTTPServer, "__init__", lambda self, address, handler: captured.append(address)):
            web.create_server(self.root, (ROOT,), port=8767)
        self.assertEqual(captured, [("127.0.0.1", 8767)])


class ReviewJavaScriptTests(unittest.TestCase):
    def test_node_ui_contracts(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required for the UI contract tests")
        result = subprocess.run([node, "--test", "tests/social-review-ui.test.cjs"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__": unittest.main()
