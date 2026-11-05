"""Explicit local-only HTTP smoke test, separate from network-denied offline CI.

Creates synthetic evidence and an ephemeral 127.0.0.1 server, then shuts it down.
No platform request, real account, browser profile or production data is used.
"""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
from pathlib import Path

from tests.social_review_fixtures import add, registry
from tools.social.batch import ROOT
from tools.social.review import ReviewStore
from tools.social.signal_store import SignalStore
from tools.social.review_web import create_server


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve() / "private"; root.mkdir(mode=0o700)
        with SignalStore(root) as source, ReviewStore(root) as store:
            add(source); store.materialize(source, registry())
        before = {path.name: path.read_bytes() for path in root.glob("*.sqlite3")}
        with create_server(root, (ROOT,), port=0) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval":0.02}, daemon=True); thread.start()
            cases = [("GET", "/", None, 200), ("GET", "/api/queue", None, 200),
                     ("GET", "/app.js", None, 200), ("POST", "/api/queue", None, 405),
                     ("GET", "/api/queue", {"Host":"evil.invalid"}, 403),
                     ("GET", "/runtime.json", None, 404), ("HEAD", "/", None, 200)]
            try:
                for method, path, headers, expected in cases:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    try:
                        connection.request(method, path, headers=headers or {})
                        response = connection.getresponse(); body = response.read()
                        assert response.status == expected, (method,path,response.status)
                        assert response.getheader("Cache-Control") == "no-store"
                        assert response.getheader("X-Content-Type-Options") == "nosniff"
                        if method == "HEAD": assert body == b""
                        if path == "/api/queue" and expected == 200: assert json.loads(body)["total"] == 1
                    finally: connection.close()
            finally:
                server.shutdown(); thread.join(timeout=5)
                assert not thread.is_alive()
        assert before == {path.name: path.read_bytes() for path in root.glob("*.sqlite3")}
    print(json.dumps({"ok":True,"localHttpCases":len(cases),"externalRequests":0,"realDecisions":0,"productionChanged":False}))


if __name__ == "__main__": main()
