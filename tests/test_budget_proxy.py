"""Tes proxy budget (P1–P9) dengan upstream palsu di localhost. Tanpa jaringan luar."""
from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from budget_guard import BudgetGuard  # noqa: E402
from budget_proxy import ProxyConfig, UsageAccumulator, estimate_tokens, make_server, parse_sse_event  # noqa: E402
from fixtures import Usage, t  # noqa: E402

OPUS = "claude-opus-5-5"
SSE = (
    b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_s1","model":"claude-opus-5-5",'
    b'"usage":{"input_tokens":1000,"cache_read_input_tokens":500,"cache_creation_input_tokens":200,'
    b'"cache_creation":{"ephemeral_5m_input_tokens":200,"ephemeral_1h_input_tokens":0}}}}\n\n'
    b': ping\n\n'
    b'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Ha"}}\n\n'
    b'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}}\n\n'
    b'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":120}}\n\n'
    b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
)
NONSTREAM = {"id": "msg_n1", "type": "message", "model": "claude-opus-5-5", "content": [{"type": "text", "text": "halo"}],
             "usage": {"input_tokens": 1000, "output_tokens": 200, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}


class FakeUpstream(BaseHTTPRequestHandler):
    received: list = []
    mode = "ok"

    def log_message(self, *a):  # senyap
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):  # noqa: N802
        FakeUpstream.received.append(("GET", self.path, dict(self.headers), b""))
        body = json.dumps({"data": [{"id": OPUS}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        raw = self._body()
        FakeUpstream.received.append(("POST", self.path, dict(self.headers), raw))
        if self.path == "/v1/messages/count_tokens":
            body = b'{"input_tokens": 42}'
            status, ctype = 200, "application/json"
        elif FakeUpstream.mode == "400":
            body = b'{"type":"error","error":{"type":"invalid_request_error","message":"salah"}}'
            status, ctype = 400, "application/json"
        else:
            req = json.loads(raw.decode())
            if req.get("stream"):
                body, status, ctype = SSE, 200, "text/event-stream"
            else:
                body, status, ctype = json.dumps(NONSTREAM).encode(), 200, "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("request-id", "req_abc")
        self.end_headers()
        self.wfile.write(body)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up = HTTPServer(("127.0.0.1", 0), FakeUpstream)
        cls.up_thread = threading.Thread(target=cls.up.serve_forever, daemon=True)
        cls.up_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.up.shutdown()
        cls.up.server_close()

    def setUp(self):
        FakeUpstream.received = []
        FakeUpstream.mode = "ok"
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "budget.sqlite"
        self.kill = Path(self.tmp.name) / "STOP_AGENT"
        self.clock = [t("10:00")]
        os.environ["ANTHROPIC_API_KEY"] = "sk-real-test"
        self.cfg = ProxyConfig(port=0, upstream=f"http://127.0.0.1:{self.up.server_address[1]}", db_path=self.db,
                               kill_file=self.kill, clock=lambda: self.clock[0])
        self.srv = make_server(self.cfg, log=C.setup_logging("budget_proxy_test", to_stderr=False))
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Content-Type": "application/json", "x-api-key": "sk-dummy", "anthropic-version": "2023-06-01",
             "Authorization": "Bearer bocor"}
        h.update(headers or {})
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        out = (r.status, dict(r.getheaders()), r.read())
        conn.close()
        return out

    def guard(self):
        return BudgetGuard(self.db, clock=lambda: self.clock[0], kill_file=self.kill)

    def rows(self):
        g = self.guard()
        r = g.conn.execute("SELECT * FROM api_calls ORDER BY id").fetchall()
        g.conn.close()
        return [dict(x) for x in r]


class TestProxy(Base):
    def test_p1_nonstream_passthrough_and_key_swap(self):
        status, headers, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 100, "messages": []})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), NONSTREAM)
        self.assertEqual(headers.get("request-id"), "req_abc")
        m, path, h, raw = FakeUpstream.received[-1]
        self.assertEqual(h.get("x-api-key"), "sk-real-test")
        self.assertIsNone(h.get("Authorization"))
        self.assertEqual(h.get("anthropic-version"), "2023-06-01")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["cost_usd"], (1000 * 4 + 200 * 20) / 1e6, places=9)
        self.assertEqual(rows[0]["request_id"], "msg_n1")
        self.assertEqual(rows[0]["model_served"], OPUS)

    def test_p2_stream_passthrough_and_usage(self):
        status, headers, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 100, "stream": True, "messages": []})
        self.assertEqual(status, 200)
        self.assertEqual(body, SSE)
        self.assertIn("text/event-stream", headers.get("Content-Type", ""))
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["input_tokens"], rows[0]["output_tokens"], rows[0]["cache_read_tokens"], rows[0]["cache_write_5m_tokens"]), (1000, 120, 500, 200))
        self.assertAlmostEqual(rows[0]["cost_usd"], (1000 * 4 + 120 * 20 + 500 * 4 * 0.05 + 200 * 4 * 1.25) / 1e6, places=9)
        # ulang dengan id sama → idempoten
        self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 100, "stream": True, "messages": []})
        self.assertEqual(len(self.rows()), 1)

    def test_p3_blocked_no_upstream(self):
        g = self.guard()
        g.record(OPUS, Usage(2_000_000, 100_000))   # $10
        g.conn.close()
        status, headers, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 10, "messages": []})
        self.assertEqual(status, 403)   # bukan 429: SDK tidak mengulang 403
        j = json.loads(body)
        self.assertEqual(j["type"], "error")
        self.assertEqual(j["error"]["type"], "permission_error")
        self.assertIn("budget_guard", j["error"]["message"])
        self.assertIn("Retry-After", headers)
        self.assertEqual(FakeUpstream.received, [])
        self.assertEqual(len(self.rows()), 1)

    def test_p4_count_tokens_and_models_pass_unrecorded(self):
        status, _, body = self.call("POST", "/v1/messages/count_tokens", {"model": OPUS, "messages": []})
        self.assertEqual((status, json.loads(body)), (200, {"input_tokens": 42}))
        status, _, body = self.call("GET", "/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["data"][0]["id"], OPUS)
        self.assertEqual(self.rows(), [])
        self.assertEqual(FakeUpstream.received[-1][2].get("x-api-key"), "sk-real-test")

    def test_p5_upstream_400_passthrough_unrecorded(self):
        FakeUpstream.mode = "400"
        status, _, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 10, "messages": []})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["message"], "salah")
        self.assertEqual(self.rows(), [])

    def test_p6_upstream_down(self):
        self.srv.state.cfg.upstream = "http://127.0.0.1:1"  # type: ignore[attr-defined]
        status, _, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 10, "messages": []})
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["error"]["type"], "api_error")

    def test_p7_unknown_path(self):
        status, _, body = self.call("POST", "/v1/complete", {"model": OPUS})
        self.assertEqual(status, 404)
        status, _, _ = self.call("GET", "/admin")
        self.assertEqual(status, 404)

    def test_p8_per_call_cap_and_estimate(self):
        est_in, est_out = estimate_tokens({"max_tokens": 50_000}, 350_000, self.cfg)
        self.assertEqual((est_in, est_out), (100_001, 8192))
        self.srv.state.cfg.per_call = 0.001  # type: ignore[attr-defined]
        status, _, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 4096, "messages": []})
        self.assertEqual(status, 403)
        self.assertIn("per panggilan", json.loads(body)["error"]["message"])
        self.assertEqual(FakeUpstream.received, [])

    def test_p8b_kill_switch_and_healthz(self):
        self.kill.write_text("stop", encoding="utf-8")
        status, _, body = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 10, "messages": []})
        self.assertEqual(status, 403)
        self.assertIn("kill switch", json.loads(body)["error"]["message"])
        status, _, body = self.call("GET", "/healthz")
        j = json.loads(body)
        self.assertEqual((status, j["ok"], j["kill_switch"], j["key_set"]), (200, True, True, True))
        self.kill.unlink()
        status, _, _ = self.call("POST", "/v1/messages", {"model": OPUS, "max_tokens": 10, "messages": []})
        self.assertEqual(status, 200)


class TestSse(unittest.TestCase):
    def test_p9_parse_sse_event(self):
        self.assertEqual(parse_sse_event(": ping"), (None, None))
        ev, data = parse_sse_event("event: message_delta\ndata: {\"type\": \"message_delta\",\ndata: \"usage\": {\"output_tokens\": 7}}")
        self.assertEqual(ev, "message_delta")
        self.assertEqual(data["usage"]["output_tokens"], 7)
        acc = UsageAccumulator()
        for i in range(0, len(SSE), 7):   # potongan sembarang, termasuk di tengah byte
            acc.feed(SSE[i:i + 7])
        acc.finish()
        self.assertTrue(acc.started)
        self.assertEqual((acc.model, acc.request_id, acc.input_tokens, acc.output_tokens, acc.cache_read, acc.cache_5m), (OPUS, "msg_s1", 1000, 120, 500, 200))


if __name__ == "__main__":
    unittest.main()
