"""budget_proxy.py — proxy lokal antara Hermes Agent dan api.anthropic.com yang menegakkan cap biaya.

Hermes diarahkan ke http://127.0.0.1:8585 (provider custom, api_mode anthropic_messages) dengan key dummy.
Proxy ini:
- membuang key dummy dan menyuntikkan key asli dari env var ANTHROPIC_API_KEY (tidak pernah ada di konfigurasi Hermes),
- memeriksa BudgetGuard.allow() sebelum meneruskan (cap $10/hari, $190/bulan, $1/panggilan, kill file data/STOP_AGENT),
- meneruskan respons apa adanya (termasuk stream SSE) sambil membaca `usage`, lalu mencatatnya lewat BudgetGuard.record(),
- menolak dengan HTTP 429 berformat error Anthropic bila budget habis.

Penulis tunggal data/budget.sqlite tetap budget_guard.py (dipanggil dari sini).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from budget_guard import BudgetGuard, Decision  # noqa: E402

GUARDED_PATH = "/v1/messages"
PASS_POST_PATHS = {"/v1/messages/count_tokens"}
PASS_GET_PREFIXES = ("/v1/models",)
HOP_HEADERS = {
    "host", "content-length", "connection", "transfer-encoding", "accept-encoding", "x-api-key", "authorization",
    "keep-alive", "proxy-connection", "te", "trailer", "upgrade", "expect",
}
DROP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "content-encoding", "connection", "keep-alive"}


@dataclass
class ProxyConfig:
    host: str = "127.0.0.1"
    port: int = 8585
    upstream: str = "https://api.anthropic.com"
    key_env: str = "ANTHROPIC_API_KEY"
    daily_cap: float = 10.0
    monthly_cap: float = 190.0
    per_call: float = 1.0
    est_chars_per_token: float = 3.5
    est_out_cap: int = 8192
    allowed_models: Optional[set] = None
    connect_timeout: float = 10.0
    read_timeout: float = 600.0
    db_path: Optional[Path] = None
    kill_file: Optional[Path] = None
    clock: Optional[Callable[[], int]] = None
    purpose: str = "hermes"


# --------------------------------------------------------------------------- fungsi murni
def estimate_tokens(body: Optional[dict], raw_len: int, cfg: ProxyConfig) -> tuple[int, int]:
    """Perkiraan kasar token masuk/keluar untuk pre-check: byte/3,5 dan max_tokens (dibatasi)."""
    est_in = int(raw_len / cfg.est_chars_per_token) + 1
    max_tokens = 4096
    if isinstance(body, dict):
        try:
            max_tokens = int(body.get("max_tokens") or 4096)
        except (TypeError, ValueError):
            max_tokens = 4096
    return est_in, max(1, min(max_tokens, cfg.est_out_cap))


def filter_request_headers(headers) -> dict:
    out = {}
    for k, v in headers.items():
        if k.lower() in HOP_HEADERS:
            continue
        out[k] = v
    return out


def anthropic_error(type_: str, message: str) -> bytes:
    return json.dumps({"type": "error", "error": {"type": type_, "message": message}}, ensure_ascii=False).encode("utf-8")


def parse_sse_event(block: str) -> tuple[Optional[str], Optional[dict]]:
    """Satu blok SSE (tanpa baris kosong penutup) → (event, data_json|None). Komentar `: ping` diabaikan."""
    event = None
    data_lines: list[str] = []
    for line in block.splitlines():
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return event, None
    try:
        return event, json.loads("\n".join(data_lines))
    except ValueError:
        return event, None


class UsageAccumulator:
    """Menyusun `usage` dari stream SSE Anthropic: message_start (input/cache) + message_delta (output, kumulatif)."""

    def __init__(self):
        self._buf = b""
        self.started = False
        self.model: Optional[str] = None
        self.request_id: Optional[str] = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read = 0
        self.cache_creation = 0
        self.cache_5m = 0
        self.cache_1h = 0
        self.speed: Optional[str] = None
        self.events = 0

    def feed(self, chunk: bytes) -> None:
        self._buf += chunk
        while True:
            idx = self._buf.find(b"\n\n")
            if idx < 0:
                break
            block = self._buf[:idx]
            self._buf = self._buf[idx + 2:]
            self._handle(block.decode("utf-8", "replace"))

    def finish(self) -> None:
        if self._buf.strip():
            self._handle(self._buf.decode("utf-8", "replace"))
            self._buf = b""

    def _handle(self, block: str) -> None:
        event, data = parse_sse_event(block)
        if data is None:
            return
        self.events += 1
        etype = event or data.get("type")
        if etype == "message_start":
            msg = data.get("message") or {}
            u = msg.get("usage") or {}
            self.started = True
            self.model = msg.get("model")
            self.request_id = msg.get("id")
            self.input_tokens = int(u.get("input_tokens") or 0)
            self.output_tokens = int(u.get("output_tokens") or 0)
            self.cache_read = int(u.get("cache_read_input_tokens") or 0)
            self.cache_creation = int(u.get("cache_creation_input_tokens") or 0)
            cc = u.get("cache_creation") or {}
            self.cache_5m = int(cc.get("ephemeral_5m_input_tokens") or 0)
            self.cache_1h = int(cc.get("ephemeral_1h_input_tokens") or 0)
            self.speed = u.get("speed")
        elif etype == "message_delta":
            u = data.get("usage") or {}
            if u.get("output_tokens") is not None:
                self.output_tokens = int(u["output_tokens"])
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                if u.get(k) is not None:
                    setattr(self, {"input_tokens": "input_tokens", "cache_read_input_tokens": "cache_read",
                                   "cache_creation_input_tokens": "cache_creation"}[k], int(u[k]))

    def usage(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read,
            "cache_creation_input_tokens": self.cache_creation,
            "cache_creation": {"ephemeral_5m_input_tokens": self.cache_5m, "ephemeral_1h_input_tokens": self.cache_1h},
            "speed": self.speed,
        }


# --------------------------------------------------------------------------- server
class ProxyState:
    def __init__(self, cfg: ProxyConfig, log):
        self.cfg = cfg
        self.log = log
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.started_ms = C.now_ms()
        self.n_ok = 0
        self.n_blocked = 0
        self.n_err = 0
        self.api_key = os.environ.get(cfg.key_env, "")

    def guard(self) -> BudgetGuard:
        # Satu koneksi sqlite per thread permintaan; murah (skema idempoten).
        return BudgetGuard(self.cfg.db_path, daily_cap=self.cfg.daily_cap, monthly_cap=self.cfg.monthly_cap,
                           max_single_call=self.cfg.per_call, clock=self.cfg.clock, kill_file=self.cfg.kill_file)


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "crypto-analyst-budget-proxy/0.1"
    state: ProxyState  # diisi oleh make_server

    # ---- util
    def log_message(self, fmt, *args):  # noqa: D401 - diarahkan ke logger, tanpa body/header
        self.state.log.debug("http %s", fmt % args)

    def _send(self, status: int, body: bytes, ctype: str = "application/json", extra: Optional[dict] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n > 0 else b""

    def _upstream(self, method: str, raw: bytes, stream: bool):
        st = self.state
        headers = filter_request_headers(self.headers)
        headers["x-api-key"] = st.api_key
        headers["Accept-Encoding"] = "identity"
        url = st.cfg.upstream.rstrip("/") + self.path
        return st.session.request(method, url, headers=headers, data=raw if raw else None, stream=stream,
                                  timeout=(st.cfg.connect_timeout, st.cfg.read_timeout), allow_redirects=False)

    def _relay_plain(self, resp, body: Optional[bytes] = None) -> bytes:
        body = resp.content if body is None else body
        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() not in DROP_RESPONSE_HEADERS:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return body

    # ---- GET
    def do_GET(self):  # noqa: N802
        st = self.state
        if self.path == "/healthz":
            try:
                g = st.guard()
                s = g.status()
                g.conn.close()
                info = {"ok": True, "uptime_s": (C.now_ms() - st.started_ms) // 1000, "spent_today": s["spent_today"],
                        "daily_cap": s["daily_cap"], "spent_month": s["spent_month"], "monthly_cap": s["monthly_cap"],
                        "blocked_until": s["blocked_until"], "kill_switch": s["kill_switch"], "key_set": bool(st.api_key),
                        "ok_n": st.n_ok, "blocked_n": st.n_blocked, "err_n": st.n_err}
            except Exception as e:  # noqa: BLE001
                info = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            self._send(200, json.dumps(info, ensure_ascii=False).encode("utf-8"))
            return
        if self.path.startswith(PASS_GET_PREFIXES):
            try:
                resp = self._upstream("GET", b"", stream=False)
                self._relay_plain(resp)
            except requests.RequestException as e:
                st.n_err += 1
                self._send(502, anthropic_error("api_error", f"proxy: upstream tidak terjangkau: {e.__class__.__name__}"))
            return
        self._send(404, anthropic_error("not_found_error", f"proxy: path {self.path} tidak dilayani"))

    # ---- POST
    def do_POST(self):  # noqa: N802
        st = self.state
        raw = self._read_body()
        if self.path in PASS_POST_PATHS:
            try:
                resp = self._upstream("POST", raw, stream=False)
                self._relay_plain(resp)
            except requests.RequestException as e:
                st.n_err += 1
                self._send(502, anthropic_error("api_error", f"proxy: upstream tidak terjangkau: {e.__class__.__name__}"))
            return
        if self.path != GUARDED_PATH:
            self._send(404, anthropic_error("not_found_error", f"proxy: path {self.path} tidak dilayani"))
            return
        if not st.api_key:
            self._send(500, anthropic_error("api_error", f"proxy: env {st.cfg.key_env} tidak diset"))
            return
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            body = {}
        model = str(body.get("model") or "?") if isinstance(body, dict) else "?"
        stream = bool(body.get("stream")) if isinstance(body, dict) else False
        if st.cfg.allowed_models and model not in st.cfg.allowed_models:
            self._send(400, anthropic_error("invalid_request_error", f"proxy: model {model} tidak diizinkan"))
            return
        est_in, est_out = estimate_tokens(body if isinstance(body, dict) else None, len(raw), st.cfg)
        t0 = time.monotonic()
        with st.lock:
            g = st.guard()
            try:
                d: Decision = g.allow(model, est_in, est_out, st.cfg.purpose)
            finally:
                g.conn.close()
        if not d.ok:
            st.n_blocked += 1
            retry = 60
            if d.blocked_until:
                retry = max(1, int((d.blocked_until - (st.cfg.clock or C.now_ms)()) / 1000))
            st.log.warning("TOLAK model=%s est_in=%d est_out=%d: %s", model, est_in, est_out, d.reason)
            self._send(429, anthropic_error("rate_limit_error", f"budget_guard: {d.reason}"), extra={"Retry-After": str(retry)})
            return
        try:
            resp = self._upstream("POST", raw, stream=stream)
        except requests.RequestException as e:
            st.n_err += 1
            st.log.error("upstream gagal model=%s: %s", model, e.__class__.__name__)
            self._send(502, anthropic_error("api_error", f"proxy: upstream tidak terjangkau: {e.__class__.__name__}"))
            return
        if not stream:
            body_out = resp.content
            if resp.status_code == 200:
                # catat dulu, baru kirim: biaya pasti tercatat sebelum klien melihat jawaban
                try:
                    j = json.loads(body_out.decode("utf-8"))
                    cost = self._record(model, j.get("usage") or {}, j.get("id"), j.get("model"))
                    self._log_line(model, False, resp.status_code, j.get("usage") or {}, cost, time.monotonic() - t0)
                except ValueError:
                    st.log.warning("respons 200 bukan JSON; tidak dicatat")
            else:
                st.log.info("upstream %s model=%s (tidak dicatat)", resp.status_code, model)
            self._relay_plain(resp, body_out)
            return
        # streaming
        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() not in DROP_RESPONSE_HEADERS:
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        acc = UsageAccumulator()
        ok_status = resp.status_code == 200
        stream_ok = False
        try:
            for chunk in resp.iter_content(chunk_size=None):
                if not chunk:
                    continue
                self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii") + chunk + b"\r\n")
                self.wfile.flush()
                if ok_status:
                    acc.feed(chunk)
            stream_ok = True
        except (ConnectionError, BrokenPipeError, OSError) as e:
            st.log.warning("stream terputus model=%s: %s", model, e.__class__.__name__)
        finally:
            resp.close()
            if ok_status:
                acc.finish()
                if acc.started:
                    try:
                        cost = self._record(model, acc.usage(), acc.request_id, acc.model)
                        self._log_line(model, True, resp.status_code, acc.usage(), cost, time.monotonic() - t0)
                    except Exception as e:  # noqa: BLE001 - pencatatan gagal tidak boleh menggantung klien
                        st.log.error("pencatatan stream gagal: %s", e)
                else:
                    st.log.warning("stream tanpa message_start; tidak dicatat (model=%s)", model)
            # penutup chunked dikirim SETELAH pencatatan, jadi klien melihat akhir stream saat biaya sudah tercatat
            if stream_ok:
                try:
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except OSError:
                    pass

    def _record(self, model: str, usage: dict, request_id: Optional[str], served: Optional[str]) -> float:
        st = self.state
        with st.lock:
            g = st.guard()
            try:
                cost = g.record(model, usage, purpose=st.cfg.purpose, ref=None, request_id=request_id, served_model=served)
            finally:
                g.conn.close()
        st.n_ok += 1
        return cost

    def _log_line(self, model: str, stream: bool, status: int, usage: dict, cost: float, secs: float) -> None:
        cc = usage.get("cache_creation") or {}
        cw = (cc.get("ephemeral_5m_input_tokens") or 0) + (cc.get("ephemeral_1h_input_tokens") or 0) or usage.get("cache_creation_input_tokens") or 0
        self.state.log.info(
            "OK model=%s stream=%s status=%s in=%s out=%s cache_r=%s cache_w=%s biaya=$%.4f %.1fs",
            model, int(stream), status, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
            usage.get("cache_read_input_tokens", 0), cw, cost, secs,
        )


def make_server(cfg: ProxyConfig, log=None) -> ThreadingHTTPServer:
    log = log or C.setup_logging("budget_proxy")
    state = ProxyState(cfg, log)
    handler = type("BoundProxyHandler", (ProxyHandler,), {"state": state})
    srv = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    srv.daemon_threads = True
    srv.state = state  # type: ignore[attr-defined]
    return srv


def serve(cfg: ProxyConfig) -> int:
    log = C.setup_logging("budget_proxy")
    if not os.environ.get(cfg.key_env):
        log.error("env %s tidak diset; proxy tidak dijalankan. Set lewat `setx %s <key>` di terminal Anda sendiri.", cfg.key_env, cfg.key_env)
        return 2
    try:
        with C.single_instance_lock("budget_proxy"):
            srv = make_server(cfg, log)
            log.info("budget proxy di http://%s:%d → %s (cap $%.2f/hari, $%.2f/bulan, $%.2f/panggilan)",
                     cfg.host, srv.server_address[1], cfg.upstream, cfg.daily_cap, cfg.monthly_cap, cfg.per_call)
            try:
                srv.serve_forever(poll_interval=0.5)
            except KeyboardInterrupt:
                log.info("dihentikan")
            finally:
                srv.server_close()
    except C.AlreadyRunning as e:
        log.error("%s", e)
        return 2
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Proxy budget lokal untuk Hermes → Anthropic.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8585)
    ap.add_argument("--upstream", default="https://api.anthropic.com")
    ap.add_argument("--daily", type=float, default=10.0)
    ap.add_argument("--monthly", type=float, default=190.0)
    ap.add_argument("--per-call", type=float, default=1.0)
    ap.add_argument("--allow-model", action="append", default=None, help="batasi model (bisa diulang)")
    ap.add_argument("--db", default=None, help="path budget.sqlite (default data/budget.sqlite)")
    args = ap.parse_args(argv)
    cfg = ProxyConfig(host=args.host, port=args.port, upstream=args.upstream, daily_cap=args.daily, monthly_cap=args.monthly,
                      per_call=args.per_call, allowed_models=set(args.allow_model) if args.allow_model else None,
                      db_path=Path(args.db) if args.db else None)
    return serve(cfg)


if __name__ == "__main__":
    sys.exit(main())
