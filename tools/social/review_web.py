"""Loopback read-only review UI. Decisions are exported, never posted here."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .contracts import ContractError, assert_safe, load_json
from .guard import output_path, state_path
from .lead_builder import verify_fingerprint

UI = Path(__file__).with_name("review_ui")


def request_allowed(host, origin, port, fetch_site=None):
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    return host in hosts and (origin is None or origin == "http://" + host) and fetch_site in {None, "none", "same-origin"}


def read_queue(path):
    value = load_json(path)
    if not isinstance(value, dict) or value.get("mode") != "shadow" or value.get("publish") is not False or not isinstance(value.get("candidates"), list):
        raise ContractError("review_snapshot_shape")
    assert_safe(value)
    for item in value["candidates"]:
        verify_fingerprint(item)
    return value


def handler_class(state_dir, *, roots):
    root = state_path(state_dir, repo_roots=roots)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            port = self.server.server_port
            if not request_allowed(self.headers.get("Host"), self.headers.get("Origin"), port, self.headers.get("Sec-Fetch-Site")):
                self.send_body(403, b"Forbidden", "text/plain; charset=utf-8")
                return
            allowed = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                       "/style.css": ("style.css", "text/css; charset=utf-8")}
            try:
                if self.path == "/api/queue":
                    path = output_path(root, "review/queue.json", repo_roots=roots)
                    body = json.dumps(read_queue(path), ensure_ascii=False, allow_nan=False).encode()
                    self.send_body(200, body, "application/json; charset=utf-8")
                elif self.path in allowed:
                    name, content_type = allowed[self.path]
                    self.send_body(200, (UI / name).read_bytes(), content_type)
                else:
                    self.send_body(404, b"Not found", "text/plain; charset=utf-8")
            except Exception:
                self.send_body(503, b"Review snapshot unavailable", "text/plain; charset=utf-8")
        def do_POST(self):
            self.send_body(405, b"Read-only: export a decision and use the local CLI", "text/plain; charset=utf-8")
        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST
    return Handler


def serve(state_dir, port=8765, *, roots):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ContractError("review_port_range")
    server = HTTPServer(("127.0.0.1", port), handler_class(state_dir, roots=roots))
    try:
        print(f"Read-only shadow review: http://127.0.0.1:{port}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
