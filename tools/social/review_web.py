"""Loopback-only, read-only review UI. No HTTP endpoint can submit a decision."""
from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .batch import ROOT
from .contracts import ContractError, canonical_bytes
from .guard import GuardError, assert_unchanged, protected_snapshot
from .review import ReviewStore
from .review_cli import settings, require_database

ASSETS = Path(__file__).parent / "review_ui"
ROUTES = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
MAX_RESPONSE = 2 * 1024 * 1024
SECURITY_HEADERS = {
    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    "Cross-Origin-Resource-Policy": "same-origin", "Connection": "close",
}


def error_response(status, code):
    return status, "application/json; charset=utf-8", canonical_bytes({"ok": False, "error": code})


def response(method, target, headers, *, root, roots, port):
    """Pure dispatch seam; exact routes only, never a filesystem path resolver."""
    lower = {key.lower(): value for key, value in headers.items()}
    authority = "127.0.0.1:" + str(port)
    if lower.get("host") != authority:
        return error_response(403, "loopback_host_required")
    if lower.get("origin") not in (None, "http://" + authority):
        return error_response(403, "cross_origin_forbidden")
    if lower.get("sec-fetch-site") not in (None, "same-origin", "none"):
        return error_response(403, "cross_site_forbidden")
    if method not in {"GET", "HEAD"}:
        return error_response(405, "read_only_service")
    if lower.get("transfer-encoding") or lower.get("content-length", "0") != "0":
        return error_response(400, "request_body_forbidden")
    if not isinstance(target, str) or len(target) > 4096 or not target.startswith("/") or target.startswith("//"):
        return error_response(400, "invalid_request_target")
    try:
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or parts.fragment or "\\" in target or "%" in parts.path:
            raise ValueError
        if parts.path in ROUTES and not parts.query:
            filename, media_type = ROUTES[parts.path]
            path = ASSETS / filename
            if path.is_symlink() or ASSETS.is_symlink(): raise ValueError
            data = path.read_bytes()
        elif parts.path == "/api/queue":
            pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
            args = dict(pairs)
            if len(args) != len(pairs) or set(args) - {"offset", "limit", "history"}:
                raise ValueError
            for key in ("offset", "limit"):
                if key in args and not re.fullmatch(r"[0-9]{1,7}", args[key]): raise ValueError
            if args.get("history", "false") not in {"true", "false"}: raise ValueError
            with ReviewStore(root, repo_roots=roots, readonly=True) as store:
                value = store.view(offset=int(args.get("offset", 0)), limit=int(args.get("limit", 50)), history=args.get("history") == "true")
            data, media_type = canonical_bytes(value), "application/json; charset=utf-8"
        else:
            return error_response(404, "route_not_found")
        if len(data) > MAX_RESPONSE:
            return error_response(413, "review_response_limit")
        return 200, media_type, data
    except (ValueError, TypeError) as exc:
        if isinstance(exc, (ContractError, GuardError)):
            return error_response(409, "review_snapshot_unavailable")
        return error_response(400, "invalid_request")
    except Exception:
        return error_response(503, "review_service_unavailable")


def create_server(root, roots, *, port=8767):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ContractError("review_port")
    require_database(root, roots, "reviews.sqlite3")
    # Validate read-only before binding. A missing or incompatible DB cannot be
    # initialized by visiting the UI.
    with ReviewStore(root, repo_roots=roots, readonly=True): pass

    class Handler(BaseHTTPRequestHandler):
        server_version = "VCIQ-ShadowReview"
        sys_version = ""
        def log_message(self, *_): pass
        def _dispatch(self):
            if len(self.headers.get_all("Host", [])) != 1 or any(len(self.headers.get_all(key, [])) > 1 for key in ("Origin", "Content-Length", "Transfer-Encoding", "Sec-Fetch-Site")):
                result = error_response(400, "duplicate_security_header")
            else:
                result = response(self.command, self.path, dict(self.headers), root=root, roots=roots, port=self.server.server_port)
            status, media_type, body = result
            self.send_response(status)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in SECURITY_HEADERS.items(): self.send_header(key, value)
            self.end_headers()
            self.close_connection = True
            if self.command != "HEAD": self.wfile.write(body)
        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = _dispatch
        def send_error(self, code, message=None, explain=None):
            body = canonical_bytes({"ok": False, "error": "invalid_http_request"})
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for key, value in SECURITY_HEADERS.items(): self.send_header(key, value)
            self.end_headers()
            self.close_connection = True
            if getattr(self, "command", None) != "HEAD": self.wfile.write(body)

    class LoopbackServer(HTTPServer):
        allow_reuse_address = False
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(5)
            return connection, address
    return LoopbackServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--runtime-config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)
    before = None
    try:
        root, roots = settings(args.state_dir, args.runtime_config)
        before = protected_snapshot(ROOT)
        with create_server(root, roots, port=args.port) as server:
            print(json.dumps({"url": "http://127.0.0.1:" + str(server.server_port), "readOnly": True,
                "mode": "shadow", "publish": False, "liveExecuted": False}), flush=True)
            try: server.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt: pass
        assert_unchanged(before, repo_root=ROOT)
        return 0
    except (ContractError, GuardError) as exc:
        code = exc.code
    except Exception:
        code = "review_service_start_failed"
    if before is not None:
        try: assert_unchanged(before, repo_root=ROOT)
        except GuardError: code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": False}), file=sys.stderr)
    return 2


if __name__ == "__main__": raise SystemExit(main())
