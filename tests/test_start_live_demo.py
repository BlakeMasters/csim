"""Port reuse and ownership boundary for the local demo supervisor."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import threading
import unittest

from start_live_demo import probe


class _KnownHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = b"<h1>Agent work board</h1><h2>Completed activity</h2>"
        elif self.path == "/api/state":
            body = json.dumps({"status": "ok", "recording_available": True}).encode()
        elif self.path == "/campaign":
            body = b"<html>campaign</html>"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class _ForeignHandler(_KnownHandler):
    def do_GET(self):
        body = b"unrelated process"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LiveDemoLauncherTests(unittest.TestCase):
    def _serve(self, handler, check):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            check(server.server_port)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_matching_services_are_reused_only_with_exact_campaign(self):
        digest = hashlib.sha256(b"<html>campaign</html>").hexdigest()
        def check(port):
            self.assertEqual(probe(port, "board", digest), "reused")
            self.assertEqual(probe(port, "playground", digest), "reused")
            with self.assertRaisesRegex(RuntimeError, "unrecognized or stale"):
                probe(port, "playground", "wrong-campaign-hash")
        self._serve(_KnownHandler, check)

    def test_unrelated_occupied_port_is_rejected_without_stopping_it(self):
        def check(port):
            with self.assertRaisesRegex(RuntimeError, "unrecognized or stale"):
                probe(port, "board", "unused")
            with self.assertRaisesRegex(RuntimeError, "unrecognized or stale"):
                probe(port, "playground", "unused")
        self._serve(_ForeignHandler, check)


if __name__ == "__main__":
    unittest.main()
