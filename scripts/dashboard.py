"""dashboard.py — dashboard lokal baca-saja (http://127.0.0.1:8586): chart trading + posisi/order/riwayat/statistik/psikologi/jurnal.

Tidak menulis ke DB mana pun (semua koneksi readonly, singkat per permintaan) dan tidak memegang rahasia.
Jalankan: .venv/Scripts/python.exe scripts/dashboard.py  (autostart lewat run_dashboard.cmd + Startup vbs).
Frontend statis di folder dashboard/ (Lightweight Charts dari CDN).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisis as A  # noqa: E402
import common as C  # noqa: E402
import evaluasi as E  # noqa: E402
import hipotesis as H  # noqa: E402
import psikologi as PSI  # noqa: E402
from paper_engine import ACAK, LONG, SWING, TIKET, EngineConfig, SqliteMarket, budget_harian  # noqa: E402

STATIC_DIR = C.ROOT / "dashboard"
KANDIDAT_DB = C.DATA_DIR / "kandidat.sqlite"
HERMES_EXEC_DB = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "cron" / "executions.db"
TF_1M = {"1m": 1, "5m": 5, "15m": 15}
TF_1H = {"1h": 1, "4h": 4, "1d": 24}


class Data:
    """Akses baca ke semua sumber; path bisa diganti untuk tes."""

    def __init__(self, root: Path = C.ROOT, pasar: Path = C.PASAR_DB, paper: Path = C.PAPER_DB, budget: Path = C.BUDGET_DB,
                 kandidat: Path = KANDIDAT_DB, psikologi: Path = PSI.PSIKOLOGI_DB, hermes_exec: Path = HERMES_EXEC_DB,
                 clock=None, cfg: Optional[EngineConfig] = None):
        self.root, self.pasar_p, self.paper_p, self.budget_p = Path(root), Path(pasar), Path(paper), Path(budget)
        self.kandidat_p, self.psikologi_p, self.hermes_exec_p = Path(kandidat), Path(psikologi), Path(hermes_exec)
        self.clock = clock or C.now_ms
        self.cfg = cfg or EngineConfig()

    def _ro(self, p: Path) -> Optional[sqlite3.Connection]:
        return C.connect(p, readonly=True) if p.exists() else None

    # ---- ringkasan
    def tick(self, pasar) -> dict:
        v = C.meta_get(pasar, "last_tick_ms") if pasar else None
        if not v:
            return {"ts": None, "umur_s": None, "status": "tidak tersedia"}
        ts = int(v)
        umur = (self.clock() - ts) // 1000
        return {"ts": ts, "wib": C.fmt_wib(ts), "umur_s": umur, "status": "OK" if umur <= 90 else "BASI"}

    def budget(self, paper, account: str, day: str) -> dict:
        if paper is None:
            return {"account": account, "status": "tidak tersedia"}
        if account in (TIKET, ACAK):
            total = self.cfg.tiket_budget if account == TIKET else self.cfg.acak_budget
            return budget_harian(paper, account, day, total, self.cfg.tiket_min_saldo, self.cfg.tiket_max_per_order)
        n_open = paper.execute("SELECT COUNT(*) FROM positions WHERE account='swing' AND status='OPEN'").fetchone()[0]
        n_pend = paper.execute("SELECT COUNT(*) FROM orders WHERE account='swing' AND reduce_only=0 AND status IN ('NEW','ACTIVE')").fetchone()[0]
        return {"account": SWING, "margin_per_trade": self.cfg.swing_margin, "open": n_open, "pending": n_pend, "max_open": self.cfg.swing_max_open}

    def positions(self, paper, market) -> list[dict]:
        if paper is None:
            return []
        out = []
        for r in paper.execute("SELECT * FROM positions WHERE status='OPEN' ORDER BY id"):
            d = dict(r)
            lm = market.last_mark(d["symbol"]) if market else None
            if lm:
                mark, ts = lm
                sign = 1 if d["side"] == LONG else -1
                d["mark"], d["mark_ts"] = mark, ts
                d["unrealized"] = (mark - d["entry_price"]) * d["qty"] * sign
                d["liq_dist_pct"] = (mark - d["liq_price"]) / mark * 100 * sign
            out.append(d)
        return out

    def orders(self, paper) -> list[dict]:
        if paper is None:
            return []
        return [dict(r) for r in paper.execute("SELECT * FROM orders WHERE status IN ('NEW','ACTIVE') AND reduce_only=0 ORDER BY id")]

    def pemindai(self) -> dict:
        k = self._ro(self.kandidat_p)
        if k is None:
            return {"status": "tidak tersedia"}
        try:
            day = C.day_wib(self.clock())
            rr = k.execute("SELECT * FROM pemindai_run ORDER BY ts DESC LIMIT 1").fetchone()
            wake = k.execute("SELECT COUNT(*) FROM pemindai_run WHERE day_wib=? AND wake=1", (day,)).fetchone()[0]
            return {"run_terakhir": dict(rr) if rr else None, "wake_hari_ini": wake}
        finally:
            k.close()

    def biaya(self) -> dict:
        b = self._ro(self.budget_p)
        if b is None:
            return {"status": "tidak tersedia"}
        try:
            day = C.day_wib(self.clock())
            month = C.month_wib(self.clock())
            hari = b.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM api_calls WHERE day_wib=?", (day,)).fetchone()
            bulan = b.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM api_calls WHERE substr(day_wib,1,7)=?", (month,)).fetchone()
            last = [dict(r) for r in b.execute("SELECT ts, model_served, purpose, cost_usd, input_tokens, output_tokens FROM api_calls ORDER BY ts DESC LIMIT 10")]
            return {"hari": day, "calls_hari": hari[0], "cost_hari": float(hari[1]), "calls_bulan": bulan[0], "cost_bulan": float(bulan[1]),
                    "cap_hari": 10.0, "cap_bulan": 190.0, "terakhir": last}
        finally:
            b.close()

    def cron(self) -> list[dict]:
        if not self.hermes_exec_p.exists():
            return []
        try:
            c = sqlite3.connect(f"file:{self.hermes_exec_p.as_posix()}?mode=ro", uri=True, timeout=1)
            c.row_factory = sqlite3.Row
            jobs = {}
            jp = self.hermes_exec_p.parent / "jobs.json"
            if jp.exists():
                try:
                    data = json.loads(jp.read_text(encoding="utf-8"))
                    for j in (data.get("jobs", []) if isinstance(data, dict) else data):
                        jobs[j.get("id")] = j.get("name")
                except ValueError:
                    pass
            rows = [dict(r) for r in c.execute("SELECT job_id, source, status, delivery_outcome, started_at FROM executions ORDER BY started_at DESC LIMIT 12")]
            for r in rows:
                r["name"] = jobs.get(r["job_id"], r["job_id"])
            c.close()
            return rows
        except sqlite3.Error:
            return []

    def ringkasan(self) -> dict:
        pasar, paper = self._ro(self.pasar_p), self._ro(self.paper_p)
        try:
            market = SqliteMarket(pasar) if pasar else None
            day = C.day_wib(self.clock())
            return {
                "sekarang": self.clock(), "sekarang_wib": C.fmt_wib(self.clock()), "hari": day,
                "collector": self.tick(pasar),
                "budget": {a: self.budget(paper, a, day) for a in (TIKET, SWING, ACAK)},
                "posisi": self.positions(paper, market), "order": self.orders(paper),
                "pemindai": self.pemindai(), "biaya": self.biaya(), "cron": self.cron(),
                "kill_switch": (self.root / "data" / "STOP_AGENT").exists(),
            }
        finally:
            for c in (pasar, paper):
                if c:
                    c.close()

    # ---- chart
    def simbol(self) -> dict:
        pasar, paper = self._ro(self.pasar_p), self._ro(self.paper_p)
        try:
            aktif = []
            if paper:
                aktif = [r[0] for r in paper.execute("SELECT symbol FROM positions WHERE status='OPEN' UNION SELECT symbol FROM orders WHERE status IN ('NEW','ACTIVE') ORDER BY 1")]
            top = []
            if pasar:
                r = pasar.execute("SELECT MAX(ts) FROM ticker_24h").fetchone()
                if r and r[0]:
                    top = [x[0] for x in pasar.execute("SELECT symbol FROM ticker_24h WHERE ts=? ORDER BY rank LIMIT 30", (int(r[0]),))]
            riwayat = [r[0] for r in paper.execute("SELECT DISTINCT symbol FROM positions ORDER BY 1")] if paper else []
            return {"aktif": aktif, "top": top, "riwayat": riwayat}
        finally:
            for c in (pasar, paper):
                if c:
                    c.close()

    def candles(self, symbol: str, tf: str, n: int = 500) -> list[dict]:
        pasar = self._ro(self.pasar_p)
        if pasar is None:
            return []
        try:
            market = SqliteMarket(pasar)
            now = self.clock()
            if tf in TF_1M:
                hours = min(48, n * TF_1M[tf] / 60 + 1)
                raw = A.load_bars(market, symbol, hours, now)
                bars = raw if tf == "1m" else A.resample(raw, A.TF_MS[tf], 1 << 62)   # bucket terakhir ikut walau belum lengkap (live)
                tf_ms = A.TF_MS[tf]
            elif tf in TF_1H:
                h = A.load_bars_1h(market, symbol, n * TF_1H[tf] / 24 + 2, now)
                bars = h if tf == "1h" else A.resample(h, A.TF_MS[tf], 1 << 62)
                tf_ms = A.TF_MS[tf]
            else:
                return []
            bars = bars[-n:]
            return [{"time": b.open_time // 1000, "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.quote_volume, "tf_ms": tf_ms}
                    for b in bars]
        finally:
            pasar.close()

    def marker(self, symbol: str) -> dict:
        paper = self._ro(self.paper_p)
        if paper is None:
            return {"marker": [], "garis": []}
        try:
            marker, garis = [], []
            rows = paper.execute(
                "SELECT f.ts, f.price, f.role, f.rule, p.side, p.account, p.id AS pid, p.net_result, p.plan_id FROM fills f JOIN positions p ON p.id=f.position_id "
                "WHERE p.symbol=? ORDER BY f.ts", (symbol,)).fetchall()
            for r in rows:
                d = dict(r)
                acak = d["account"] == ACAK
                if d["role"] == "ENTRY":
                    marker.append({"time": d["ts"] // 1000, "jenis": "ENTRY", "side": d["side"], "account": d["account"],
                                   "text": f"#{d['pid']} {d['side']} {'(acak)' if acak else ''}".strip(), "price": d["price"]})
                else:
                    marker.append({"time": d["ts"] // 1000, "jenis": d["role"], "side": d["side"], "account": d["account"],
                                   "text": f"#{d['pid']} {d['role']} {d['net_result']:+.4f}" if d["net_result"] is not None else f"#{d['pid']} {d['role']}",
                                   "price": d["price"]})
            for r in paper.execute("SELECT id, side, price, account, done_ts, status FROM orders WHERE symbol=? AND reduce_only=0 AND status IN ('EXPIRED','CANCELED') AND done_ts IS NOT NULL", (symbol,)):
                marker.append({"time": int(r["done_ts"]) // 1000, "jenis": r["status"], "side": r["side"], "account": r["account"],
                               "text": f"order #{r['id']} {r['status'].lower()}", "price": r["price"]})
            for r in paper.execute("SELECT * FROM positions WHERE symbol=? AND status='OPEN'", (symbol,)):
                d = dict(r)
                garis.append({"price": d["entry_price"], "label": f"entry #{d['id']} {d['side']}", "jenis": "entry", "account": d["account"]})
                garis.append({"price": d["liq_price"], "label": f"liq #{d['id']}", "jenis": "liq", "account": d["account"]})
                if d["tp_price"]:
                    garis.append({"price": d["tp_price"], "label": f"TP #{d['id']}", "jenis": "tp", "account": d["account"]})
                if d["sl_price"]:
                    garis.append({"price": d["sl_price"], "label": f"SL #{d['id']}", "jenis": "sl", "account": d["account"]})
            for r in paper.execute("SELECT id, side, price, account, type FROM orders WHERE symbol=? AND reduce_only=0 AND status IN ('NEW','ACTIVE')", (symbol,)):
                if r["price"]:
                    garis.append({"price": r["price"], "label": f"order #{r['id']} {r['side']} {r['type']}", "jenis": "order", "account": r["account"]})
            marker.sort(key=lambda m: m["time"])
            return {"marker": marker, "garis": garis}
        finally:
            paper.close()

    # ---- riwayat & statistik
    def riwayat(self, akun: Optional[str], hari: Optional[str], symbol: Optional[str], limit: int = 200) -> dict:
        paper = self._ro(self.paper_p)
        if paper is None:
            return {"posisi": [], "order": [], "harian": []}
        try:
            q, p = "SELECT * FROM positions WHERE status='CLOSED'", []
            qo, po = "SELECT * FROM orders WHERE reduce_only=0 AND status IN ('EXPIRED','CANCELED','REJECTED')", []
            for col, val in (("account", akun), ("day_wib", hari), ("symbol", symbol)):
                if val:
                    q += f" AND {col}=?"; p.append(val)
                    qo += f" AND {col}=?"; po.append(val)
            pos = [dict(r) for r in paper.execute(q + " ORDER BY closed_ts DESC LIMIT ?", p + [int(limit)])]
            ords = [dict(r) for r in paper.execute(qo + " ORDER BY id DESC LIMIT ?", po + [int(limit)])]
            harian = [dict(r) for r in paper.execute("SELECT * FROM daily_summary ORDER BY day_wib DESC, account LIMIT 90")]
            return {"posisi": pos, "order": ords, "harian": harian}
        finally:
            paper.close()

    def ekuitas(self) -> dict:
        paper = self._ro(self.paper_p)
        if paper is None:
            return {}
        try:
            out: dict[str, dict] = {}
            for acc in (TIKET, SWING, ACAK):
                out[acc] = ekuitas_drawdown([(int(r[0]), float(r[1])) for r in paper.execute(
                    "SELECT closed_ts, net_result FROM positions WHERE account=? AND status='CLOSED' AND net_result IS NOT NULL ORDER BY closed_ts, id", (acc,))])
            return out
        finally:
            paper.close()

    def statistik(self) -> dict:
        paper = self._ro(self.paper_p)
        if paper is None:
            return {"status": "tidak tersedia"}
        try:
            return E.compute(paper, self.clock())
        finally:
            paper.close()

    def psikologi(self, symbol: str) -> dict:
        p = self._ro(self.psikologi_p)
        if p is None:
            return {"symbol": symbol, "status": "tidak tersedia", "alasan": "psikologi.sqlite belum ada"}
        try:
            return PSI.panel_untuk(p, symbol, self.clock())
        finally:
            p.close()

    def kandidat(self) -> dict:
        k = self._ro(self.kandidat_p)
        if k is None:
            return {"run": None, "kandidat": [], "runs": []}
        try:
            run = k.execute("SELECT * FROM pemindai_run WHERE wake=1 ORDER BY ts DESC LIMIT 1").fetchone()
            rows = [dict(r) for r in k.execute("SELECT * FROM kandidat WHERE run_ts=? ORDER BY score DESC", (run["ts"] if run else 0,))]
            for d in rows:
                for f in ("lev_layak", "flags"):
                    try:
                        d[f] = json.loads(d[f]) if isinstance(d[f], str) else d[f]
                    except ValueError:
                        pass
            runs = [dict(r) for r in k.execute("SELECT ts, wake, alasan, n_symbols, duration_ms FROM pemindai_run ORDER BY ts DESC LIMIT 24")]
            return {"run": dict(run) if run else None, "kandidat": rows, "runs": runs}
        finally:
            k.close()

    def teks(self, jenis: str, hari: Optional[str]) -> dict:
        day = hari or C.day_wib(self.clock())
        if jenis == "hipotesis":
            recs = H.load_jsonl(self.root / "pasar" / "hipotesis.jsonl")
            hasil = {h["id"]: h for h in H.load_jsonl(self.root / "pasar" / "hipotesis-hasil.jsonl")}
            return {"jenis": jenis, "isi": H.render_hipotesis_md(recs, hasil) if recs else ""}
        rel = {"jurnal": f"jurnal/agent/{day}.md", "harian": f"pasar/harian/{day}.md", "pelajaran": "pasar/pelajaran.md",
               "pelajaran-usulan": "pasar/pelajaran-usulan.md", "playbook": "referensi/playbook.md", "indeks": "referensi/indeks.md"}.get(jenis)
        if rel is None:
            return {"jenis": jenis, "isi": "", "error": "jenis tidak dikenal"}
        p = self.root / rel
        return {"jenis": jenis, "path": rel, "isi": p.read_text(encoding="utf-8") if p.exists() else ""}


def ekuitas_drawdown(closes: list[tuple[int, float]]) -> dict:
    """Kurva ekuitas kumulatif + trailing drawdown (jarak dari puncak tertinggi sejauh ini), semua dalam USD.
    closes: [(closed_ts_ms, net_result)] urut waktu."""
    cum, peak, max_dd, max_dd_ts = 0.0, 0.0, 0.0, None
    ek, dd = [], []
    for ts, net in closes:
        cum += net
        peak = max(peak, cum)
        d = cum - peak
        if d < max_dd:
            max_dd, max_dd_ts = d, ts
        ek.append({"time": ts // 1000, "value": round(cum, 6)})
        dd.append({"time": ts // 1000, "value": round(d, 6)})
    return {"ekuitas": ek, "drawdown": dd, "ekuitas_akhir": round(cum, 6), "puncak": round(peak, 6),
            "drawdown_sekarang": round(cum - peak, 6), "drawdown_maks": round(max_dd, 6), "drawdown_maks_ts": max_dd_ts, "n": len(closes)}


# --------------------------------------------------------------------------- app
def _json(obj: Any):
    from starlette.responses import Response
    return Response(json.dumps(obj, ensure_ascii=False, default=str), media_type="application/json; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


def make_app(data: Optional[Data] = None, static_dir: Path = STATIC_DIR):
    from starlette.applications import Starlette
    from starlette.responses import FileResponse, PlainTextResponse
    from starlette.routing import Route

    d = data or Data()
    log = logging.getLogger("dashboard")

    def guard(fn):
        async def handler(request):
            try:
                return _json(fn(request))
            except Exception as e:  # noqa: BLE001
                log.exception("endpoint gagal")
                return _json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        return handler

    def qp(request, k, default=None):
        v = request.query_params.get(k)
        return v if v not in (None, "") else default

    async def index(request):
        f = static_dir / "index.html"
        return FileResponse(str(f)) if f.exists() else PlainTextResponse("dashboard/index.html tidak ada", status_code=404)

    async def static(request):
        name = request.path_params["name"]
        if "/" in name or "\\" in name or name.startswith(".") or ".." in name:
            return PlainTextResponse("ditolak", status_code=400)
        f = static_dir / name
        return FileResponse(str(f)) if f.is_file() else PlainTextResponse("tidak ada", status_code=404)

    routes = [
        Route("/", index),
        Route("/static/{name}", static),
        Route("/api/ringkasan", guard(lambda r: d.ringkasan())),
        Route("/api/simbol", guard(lambda r: d.simbol())),
        Route("/api/candles", guard(lambda r: d.candles(qp(r, "symbol", "BTCUSDT"), qp(r, "tf", "5m"), int(qp(r, "n", 500))))),
        Route("/api/marker", guard(lambda r: d.marker(qp(r, "symbol", "BTCUSDT")))),
        Route("/api/riwayat", guard(lambda r: d.riwayat(qp(r, "akun"), qp(r, "hari"), qp(r, "symbol"), int(qp(r, "limit", 200))))),
        Route("/api/ekuitas", guard(lambda r: d.ekuitas())),
        Route("/api/statistik", guard(lambda r: d.statistik())),
        Route("/api/psikologi", guard(lambda r: d.psikologi(qp(r, "symbol", "BTCUSDT")))),
        Route("/api/kandidat", guard(lambda r: d.kandidat())),
        Route("/api/teks", guard(lambda r: d.teks(qp(r, "jenis", "jurnal"), qp(r, "hari")))),
    ]
    return Starlette(routes=routes)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Dashboard lokal baca-saja crypto-analyst")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8586)
    args = ap.parse_args(argv)
    log = C.setup_logging("dashboard", to_stderr=False)
    import uvicorn
    try:
        with C.single_instance_lock("dashboard"):
            log.info("dashboard http://%s:%d", args.host, args.port)
            uvicorn.run(make_app(), host=args.host, port=args.port, log_level="warning")
    except C.AlreadyRunning:
        log.info("dashboard sudah berjalan")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
