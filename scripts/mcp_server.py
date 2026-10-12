"""mcp_server.py — server MCP (stdio) untuk Hermes Agent: satu-satunya pintu agent ke mesin paper dan data pasar.

Dijalankan oleh Hermes sebagai subprocess (`mcp_servers.paper` di config.yaml) dengan interpreter venv proyek.
Stdout adalah kanal protokol MCP: TIDAK ADA print(). Log hanya ke logs/mcp_server.log.

Tool hanya membungkus API publik: PaperEngine (order/posisi/laporan), SqliteMarket (data pasar, baca saja),
analisis.py (indikator/level/jejak/tabel leverage), BudgetGuard.status (biaya API).
File yang ditulis server ini hanya catatan agent: jurnal/agent/, pasar/harian/, pasar/hipotesis.jsonl (append; dinilai
uji_hipotesis.py), pasar/pelajaran-usulan.md. Nama file berasal dari jam, bukan dari input agent.
"""
from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import sys
import threading
from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisis as A  # noqa: E402
import common as C  # noqa: E402
import evaluasi as E  # noqa: E402
import hipotesis as H  # noqa: E402
import psikologi as PSI  # noqa: E402
import referensi as RF  # noqa: E402
from budget_guard import BudgetGuard  # noqa: E402
from paper_engine import LONG, SHORT, SWING, TIKET, OrderRequest, PaperEngine, SqliteMarket  # noqa: E402

KANDIDAT_DB = C.DATA_DIR / "kandidat.sqlite"
PROXY_HEALTH = "http://127.0.0.1:8585/healthz"
FRESH_OK_S = 90
MAX_HIPOTESIS_PER_HARI = 3
MAX_READ_CHARS = 20_000
POLA = H.POLA
MS_FIELDS = {"ts", "open_time", "funding_time", "opened_ts", "closed_ts", "created_ts", "activate_ts", "expire_ts",
             "done_ts", "mark_ts", "opened_bar", "closed_bar", "bar_open_time", "run_ts", "next_funding_time", "onboard_date",
             "bar_terakhir", "bar_1m_ts", "tick_ts", "data_tick_ts", "last_ts"}
TOOL_NAMES = (
    "waktu_sekarang", "harga", "simbol_info", "top_volume", "tabel_tiket", "ohlcv", "kandidat_terbaru", "status_sistem",
    "pasang_order", "batal_order", "tutup_posisi", "posisi", "order_menunggu", "riwayat", "budget_tiket", "laporan_paper",
    "biaya_api", "tulis_jurnal", "baca_memori", "tulis_catatan_harian", "tulis_hipotesis", "usul_pelajaran", "statistik_lulus", "panel_psikologi", "cari_referensi", "baca_referensi",
)


# --------------------------------------------------------------------------- util
def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            out[k] = _jsonable(v)
            if k in MS_FIELDS and isinstance(v, (int, float)) and v and v > 1e11:
                out[f"{k}_wib"] = C.fmt_wib(int(v))
        return out
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, sqlite3.Row):
        return _jsonable(dict(x))
    if is_dataclass(x) and not isinstance(x, type):
        return _jsonable(asdict(x))
    if isinstance(x, Decimal):
        return C.fmt_dec(x)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def _err(e: Exception) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@dataclass
class Ctx:
    engine: PaperEngine
    market: Any
    pasar: sqlite3.Connection
    root: Path
    clock: Callable[[], int]
    guard_factory: Optional[Callable[[], BudgetGuard]] = None
    kandidat_path: Optional[Path] = None
    psikologi_path: Optional[Path] = None
    proxy_health: Optional[str] = PROXY_HEALTH
    log: logging.Logger = logging.getLogger("mcp_server")


def build_ctx() -> Ctx:
    log = C.setup_logging("mcp_server", to_stderr=False)
    if not C.PASAR_DB.exists():
        raise RuntimeError("pasar.sqlite belum ada: collector belum pernah jalan")
    pasar = C.connect(C.PASAR_DB, readonly=True)
    market = SqliteMarket(pasar)
    engine = PaperEngine(C.connect(C.PAPER_DB), market, log=log)
    return Ctx(engine=engine, market=market, pasar=pasar, root=C.ROOT, clock=C.now_ms,
               guard_factory=lambda: BudgetGuard(), kandidat_path=KANDIDAT_DB, psikologi_path=PSI.PSIKOLOGI_DB, log=log)


# --------------------------------------------------------------------------- tools
class Tools:
    """Implementasi tool. Setiap metode publik = satu tool MCP; mengembalikan dict JSON-able."""

    def __init__(self, ctx: Optional[Ctx] = None, ctx_factory: Callable[[], Ctx] = build_ctx):
        self._ctx = ctx
        self._factory = ctx_factory
        self._lock = threading.Lock()

    @property
    def ctx(self) -> Ctx:
        if self._ctx is None:
            self._ctx = self._factory()
        return self._ctx

    def _call(self, name: str, fn: Callable[[], Any]) -> Any:
        with self._lock:
            t0 = C.now_ms()
            try:
                out = _jsonable(fn())
                self.ctx.log.info("%s ok %d ms", name, C.now_ms() - t0)
                return out
            except Exception as e:  # noqa: BLE001
                try:
                    self.ctx.log.warning("%s gagal: %s", name, e)
                except Exception:  # noqa: BLE001
                    pass
                return _err(e)

    # ---- waktu & data pasar
    def _tick(self) -> tuple[Optional[int], Optional[int], str]:
        now = self.ctx.clock()
        v = C.meta_get(self.ctx.pasar, "last_tick_ms")
        if not v:
            return None, None, "tidak tersedia"
        tick = int(v)
        umur = (now - tick) // 1000
        return tick, umur, ("OK" if umur <= FRESH_OK_S else "BASI")

    def waktu_sekarang(self) -> dict:
        """Jam sekarang (WIB & UTC), umur tick collector, status kesegaran data, dan sisa menit ke jam tutup tiket 23:50 WIB."""
        def run():
            now = self.ctx.clock()
            tick, umur, status = self._tick()
            eod = self.ctx.engine.eod_ms(now)
            return {"ms": now, "wib": C.fmt_wib(now), "utc": C.to_utc(now).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "hari_wib": C.day_wib(now), "tick_collector_wib": C.fmt_wib(tick) if tick else "tidak tersedia",
                    "umur_tick_detik": umur, "status_data": status, "eod_tiket_wib": self.ctx.engine.cfg.tiket_eod_wib,
                    "menit_ke_eod": max(0, (eod - now) // C.MINUTE_MS)}
        return self._call("waktu_sekarang", run)

    def harga(self, symbol: str) -> dict:
        """Mark price terakhir, close 1m terakhir, funding terakhir & berikutnya, tier, dan kesegaran untuk satu simbol (mis. BTCUSDT)."""
        def run():
            sym = symbol.strip()
            f = self.ctx.market.filters(sym)
            if f is None:
                return {"symbol": sym, "status": "tidak tersedia", "alasan": "simbol tidak ada di symbol_info"}
            now = self.ctx.clock()
            lm = self.ctx.market.last_mark(sym)
            bars = self.ctx.market.bars(sym, now - 5 * C.MINUTE_MS, now)
            last = bars[-1][0] if bars else None
            snap = self.ctx.pasar.execute(
                "SELECT last_funding_rate, next_funding_time, index_price FROM mark_snapshot WHERE symbol=? ORDER BY ts DESC LIMIT 1", (sym,)
            ).fetchone()
            umur = (now - lm[1]) // 1000 if lm else None
            return {"symbol": sym, "status_simbol": f.status, "mark": lm[0] if lm else None, "mark_ts": lm[1] if lm else None,
                    "umur_detik": umur, "status": ("OK" if umur is not None and umur <= FRESH_OK_S else "BASI") if lm else "tidak tersedia",
                    "index": snap["index_price"] if snap else None, "close_1m": last.close if last else None,
                    "bar_1m_ts": last.open_time if last else None, "funding_terakhir": snap["last_funding_rate"] if snap else None,
                    "next_funding_time": snap["next_funding_time"] if snap else None, "interval_funding_h": f.funding_interval_h,
                    "tier": self.ctx.market.tier(sym)}
        return self._call("harga", run)

    def simbol_info(self, symbol: str) -> dict:
        """Filter order (tick, step, qty & notional minimum), status, umur listing, dan bracket leverage/MMR simbol."""
        def run():
            sym = symbol.strip()
            f = self.ctx.market.filters(sym)
            if f is None:
                return {"symbol": sym, "status": "tidak tersedia"}
            row = self.ctx.pasar.execute("SELECT onboard_date, liq_fee, pct_up, pct_down FROM symbol_info WHERE symbol=?", (sym,)).fetchone()
            now = self.ctx.clock()
            onboard = int(row["onboard_date"]) if row and row["onboard_date"] else None
            return {"symbol": sym, "status": f.status, "tick_size": f.tick_size, "qty_step": f.qty_step, "min_qty": f.min_qty,
                    "min_notional": f.min_notional, "pct_up": f.pct_up, "pct_down": f.pct_down, "interval_funding_h": f.funding_interval_h,
                    "liq_fee": row["liq_fee"] if row else None, "onboard_date": onboard,
                    "umur_listing_hari": (now - onboard) // C.DAY_MS if onboard else None,
                    "bracket": self.ctx.market.brackets(sym), "tier": self.ctx.market.tier(sym)}
        return self._call("simbol_info", run)

    def top_volume(self, n: int = 20) -> dict:
        """Watchlist dinamis: n pair USDT-M perpetual dengan volume 24 jam terbesar, beserta leverage maks, funding, umur listing, dan flag (SUDAH_LARI, BARU, FUNDING_EKSTREM)."""
        return self._call("top_volume", lambda: A.top_volume(self.ctx.pasar, int(n), self.ctx.clock()))

    def _atr_map(self, sym: str, now: int) -> tuple[dict, list]:
        bars = A.load_bars(self.ctx.market, sym, 48, now)
        closed_1m = [b for b in bars if b.open_time + C.MINUTE_MS <= now]
        atr_map = {"1m": A.atr(closed_1m[-200:]) if len(closed_1m) > 15 else None}
        for tf in ("5m", "15m", "1h"):
            rb = A.resample(bars, A.TF_MS[tf], now)
            atr_map[tf] = A.atr(rb) if len(rb) > 15 else None
        return atr_map, bars

    def tabel_tiket(self, symbol: str, sisi: str, entry: Optional[float] = None, leverage: Optional[int] = None,
                    target_pct: Optional[float] = None) -> dict:
        """Tabel leverage untuk tiket $1: qty yang muat budget, likuidasi & jaraknya dalam ATR 1m/5m/15m/1h, fee, dan win rate minimum per target. sisi = LONG|SHORT."""
        def run():
            sym = symbol.strip()
            side = sisi.strip().upper()
            if side not in (LONG, SHORT):
                raise ValueError("sisi harus LONG atau SHORT")
            f = self.ctx.market.filters(sym)
            if f is None:
                return {"symbol": sym, "status": "tidak tersedia"}
            now = self.ctx.clock()
            lm = self.ctx.market.last_mark(sym)
            px = float(entry) if entry else (lm[0] if lm else None)
            if not px:
                return {"symbol": sym, "status": "tidak tersedia", "alasan": "tidak ada harga"}
            atr_map, _ = self._atr_map(sym, now)
            bs = self.ctx.engine.budget_status(TIKET, C.day_wib(now))
            tab = A.tabel_leverage(side, px, f, self.ctx.market.brackets(sym), atr_map, bs["remaining"], self.ctx.engine.cfg,
                                   [int(leverage)] if leverage else None, [float(target_pct)] if target_pct else (0.5, 1.0, 2.0))
            tab.update({"symbol": sym, "sumber_entry": "input" if entry else "mark terakhir", "budget": bs})
            return tab
        return self._call("tabel_tiket", run)

    def ohlcv(self, symbol: str, tf: str = "5m", n: int = 60) -> dict:
        """Candle yang sudah close (tf: 1m|5m|15m|1h|4h|1d) + EMA20/50, RSI14, ATR14, tren, swing, level kunci terdekat, dan jejak psikologi (WICK, VOL, BREAKOUT_GAGAL, IMPULS, KOMPRESI). 1h/4h/1d dari kline_1h (120 hari)."""
        def run():
            sym = symbol.strip()
            if tf not in A.TF_MS:
                raise ValueError("tf harus salah satu dari 1m, 5m, 15m, 1h, 4h, 1d")
            now = self.ctx.clock()
            sumber = "resample_1m"
            if tf in ("1h", "4h", "1d"):
                h = A.load_bars_1h(self.ctx.market, sym, 180 if tf != "1h" else 30, now)
                if tf == "1h" and len(h) >= 20:
                    bars, sumber = h, "kline_1h"
                elif tf in ("4h", "1d"):
                    bars = A.resample(h, A.TF_MS[tf], now) if h else []
                    sumber = "kline_1h"
                    if len(bars) < 20:
                        return {"symbol": sym, "tf": tf, "status": "tidak tersedia", "alasan": f"hanya {len(bars)} bar {tf} close (butuh ≥ 20)",
                                "catatan": "kline_1h belum cukup; collector mengisi 120 hari saat pertama jalan (±4 tick)"}
                else:
                    raw = A.load_bars(self.ctx.market, sym, 48, now)
                    bars = A.resample(raw, A.TF_MS[tf], now) if raw else []
            else:
                raw = A.load_bars(self.ctx.market, sym, 48, now)
                if not raw:
                    return {"symbol": sym, "tf": tf, "status": "tidak tersedia", "alasan": "belum ada bar untuk simbol ini"}
                bars = [b for b in raw if b.open_time + C.MINUTE_MS <= now] if tf == "1m" else A.resample(raw, A.TF_MS[tf], now)
            if len(bars) < 20:
                return {"symbol": sym, "tf": tf, "status": "tidak tersedia", "alasan": f"hanya {len(bars)} bar close (butuh ≥ 20)", "sumber": sumber}
            closes = [b.close for b in bars]
            atr_v = A.atr(bars)
            sw = A.swings(bars)
            levels = A.cluster_levels(sw, 0.5 * atr_v) if atr_v else []
            above, below = A.nearest(levels, bars[-1].close)
            out_bars = [{"open_time": b.open_time, "o": b.open, "h": b.high, "l": b.low, "c": b.close, "qv": round(b.quote_volume, 2)} for b in bars[-int(n):]]
            return {"symbol": sym, "tf": tf, "sumber": sumber, "n_bar": len(bars), "bar_terakhir": bars[-1].open_time, "close": bars[-1].close,
                    "ema20": A.ema_last(closes, 20), "ema50": A.ema_last(closes, 50), "rsi14": A.rsi(closes), "atr14": atr_v,
                    "atr14_pct": (atr_v / bars[-1].close * 100) if atr_v else None, "tren": A.tren(bars),
                    "swing_terakhir": sw[-6:], "level_atas": above, "level_bawah": below,
                    "jejak": A.jejak(bars, levels, atr_v), "bars": out_bars,
                    "catatan": "hanya candle yang sudah close; swing baru terkonfirmasi 3 bar kemudian; EMA/RSI None = warm-up belum cukup"}
        return self._call("ohlcv", run)

    def kandidat_terbaru(self, limit: int = 5, hari: Optional[str] = None) -> dict:
        """Kandidat tiket dari pemindai mekanis (run terakhir, atau hari tertentu YYYY-MM-DD)."""
        def run():
            p = self.ctx.kandidat_path
            if not p or not Path(p).exists():
                return {"kandidat": [], "catatan": "pemindai belum pernah jalan (kandidat.sqlite tidak ada)"}
            k = C.connect(p, readonly=True)
            try:
                if hari:
                    rows = k.execute("SELECT * FROM kandidat WHERE day_wib=? ORDER BY score DESC, id DESC LIMIT ?", (hari, int(limit))).fetchall()
                    run_row = k.execute("SELECT * FROM pemindai_run WHERE day_wib=? ORDER BY ts DESC LIMIT 1", (hari,)).fetchone()
                else:
                    # run terakhir yang MEMBANGUNKAN agent; run tanpa kandidat sesudahnya tidak mengosongkan daftar
                    run_row = k.execute("SELECT * FROM pemindai_run WHERE wake=1 ORDER BY ts DESC LIMIT 1").fetchone()
                    rows = k.execute("SELECT * FROM kandidat WHERE run_ts=? ORDER BY score DESC, id DESC LIMIT ?",
                                     (run_row["ts"] if run_row else 0, int(limit))).fetchall()
                out = []
                for r in rows:
                    d = dict(r)
                    d["plan_id"] = f"K{d['id']}"
                    for fld in ("lev_layak", "flags"):
                        if isinstance(d.get(fld), str):
                            try:
                                d[fld] = json.loads(d[fld])
                            except ValueError:
                                pass
                    out.append(d)
                last = k.execute("SELECT ts, wake, alasan FROM pemindai_run ORDER BY ts DESC LIMIT 1").fetchone()
                return {"run": dict(run_row) if run_row else None, "run_terakhir": dict(last) if last else None, "kandidat": out,
                        "catatan": "plan_id untuk pasang_order = field plan_id (K<id>); jangan mengarang ID"}
            finally:
                k.close()
        return self._call("kandidat_terbaru", run)

    def status_sistem(self) -> dict:
        """Kesehatan sistem: umur tick collector, proxy budget (/healthz), run pemindai terakhir, kill switch."""
        def run():
            now = self.ctx.clock()
            tick, umur, status = self._tick()
            out: dict[str, Any] = {"collector": {"tick_ts": tick, "umur_detik": umur, "status": status},
                                   "kill_switch": (self.ctx.root / "data" / "STOP_AGENT").exists()}
            if self.ctx.proxy_health:
                try:
                    import requests
                    r = requests.get(self.ctx.proxy_health, timeout=1.5)
                    out["proxy"] = r.json()
                except Exception as e:  # noqa: BLE001
                    out["proxy"] = {"ok": False, "status": "tidak tersedia", "alasan": type(e).__name__}
            p = self.ctx.kandidat_path
            if p and Path(p).exists():
                k = C.connect(p, readonly=True)
                try:
                    rr = k.execute("SELECT * FROM pemindai_run ORDER BY ts DESC LIMIT 1").fetchone()
                    day = C.day_wib(now)
                    wake = k.execute("SELECT COUNT(*) FROM pemindai_run WHERE day_wib=? AND wake=1", (day,)).fetchone()[0]
                    gagal = k.execute("SELECT COUNT(*) FROM pemindai_run WHERE day_wib=? AND ok=0", (day,)).fetchone()[0]
                    out["pemindai"] = {"run_terakhir": dict(rr) if rr else None, "wake_hari_ini": wake, "gagal_hari_ini": gagal}
                finally:
                    k.close()
            else:
                out["pemindai"] = "tidak tersedia"
            return out
        return self._call("status_sistem", run)

    # ---- order & posisi
    def pasang_order(self, akun: str, symbol: str, sisi: str, qty: float, leverage: int, harga: Optional[float] = None,
                     market: bool = False, tp: Optional[float] = None, sl: Optional[float] = None, plan_id: Optional[str] = None,
                     pola: Optional[str] = None, catatan: Optional[str] = None) -> dict:
        """Pasang order PAPER. akun=tiket|swing, sisi=LONG|SHORT. Limit (harga) post-only = fee maker; market=true = taker di open bar berikutnya. Swing wajib tp & sl. Mesin memvalidasi budget, leverage, tick/step, dan mengembalikan kode penolakan."""
        def run():
            req = OrderRequest(account=akun.strip().lower(), symbol=symbol.strip(), side=sisi.strip().upper(), qty=float(qty),
                               leverage=int(leverage), type="MARKET" if market else "LIMIT", price=float(harga) if harga else None,
                               tp_price=float(tp) if tp else None, sl_price=float(sl) if sl else None, post_only=not market,
                               plan_id=plan_id, pattern=pola, note=catatan, created_by="hermes")
            res = self.ctx.engine.place_order(req)
            d = asdict(res)
            d["pesan"] = str(res)
            return d
        return self._call("pasang_order", run)

    def batal_order(self, order_id: int) -> dict:
        """Batalkan order entry yang masih NEW/ACTIVE."""
        def run():
            ok = self.ctx.engine.cancel_order(int(order_id), who="hermes")
            return {"ok": ok, "order_id": int(order_id), "pesan": "dibatalkan" if ok else "tidak bisa dibatalkan (tidak ada / sudah selesai / reduce-only)"}
        return self._call("batal_order", run)

    def tutup_posisi(self, position_id: int) -> dict:
        """Minta tutup posisi terbuka: dieksekusi market (taker + slippage) di open bar berikutnya."""
        def run():
            ok = self.ctx.engine.close_position_request(int(position_id), who="hermes")
            return {"ok": ok, "position_id": int(position_id), "pesan": "permintaan tutup dicatat; eksekusi di bar berikutnya" if ok else "posisi tidak ditemukan / tidak terbuka"}
        return self._call("tutup_posisi", run)

    def posisi(self, akun: Optional[str] = None) -> dict:
        """Posisi paper yang terbuka (+ unrealized di mark terakhir dan jarak ke likuidasi)."""
        def run():
            rows = self.ctx.engine.positions(akun.strip().lower() if akun else None)
            return {"n": len(rows), "posisi": rows}
        return self._call("posisi", run)

    def order_menunggu(self, akun: Optional[str] = None, termasuk_reduce_only: bool = False) -> dict:
        """Order yang masih NEW/ACTIVE (entry; TP/SL otomatis hanya jika termasuk_reduce_only=true)."""
        def run():
            rows = self.ctx.engine.orders(akun.strip().lower() if akun else None)
            if not termasuk_reduce_only:
                rows = [r for r in rows if not r.get("reduce_only")]
            return {"n": len(rows), "order": rows}
        return self._call("order_menunggu", run)

    def riwayat(self, hari: Optional[str] = None, akun: Optional[str] = None, limit: int = 50) -> dict:
        """Posisi yang sudah ditutup dan order yang kedaluwarsa/ditolak/dibatalkan pada hari WIB (default hari ini)."""
        def run():
            rows = self.ctx.engine.history(hari, akun.strip().lower() if akun else None, int(limit))
            return {"hari": hari or C.day_wib(self.ctx.clock()), "n": len(rows), "riwayat": rows}
        return self._call("riwayat", run)

    def budget_tiket(self) -> dict:
        """Sisa budget tiket hari ini (margin + fee masuk ≤ $1) dan status akun swing."""
        return self._call("budget_tiket", lambda: {"tiket": self.ctx.engine.budget_status(TIKET), "swing": self.ctx.engine.budget_status(SWING)})

    def laporan_paper(self, hari: Optional[str] = None) -> dict:
        """Laporan paper harian (markdown): budget, posisi terbuka, posisi ditutup, order menunggu, hasil ambigu, event."""
        return self._call("laporan_paper", lambda: {"hari": hari or C.day_wib(self.ctx.clock()), "markdown": self.ctx.engine.report(hari)})

    def biaya_api(self, hari: Optional[str] = None) -> dict:
        """Biaya API Anthropic yang tercatat proxy: hari ini vs cap, bulan ini vs cap, per model dan tujuan."""
        def run():
            if not self.ctx.guard_factory:
                return {"status": "tidak tersedia"}
            g = self.ctx.guard_factory()
            try:
                return g.status(hari)
            finally:
                g.conn.close()
        return self._call("biaya_api", run)

    def _panel(self, symbol: str) -> dict:
        p = self.ctx.psikologi_path
        if not p or not Path(p).exists():
            return {"symbol": symbol, "status": "tidak tersedia", "alasan": "psikologi.sqlite belum ada (cron psikologi belum jalan)"}
        conn = C.connect(p, readonly=True)
        try:
            return PSI.panel_untuk(conn, symbol.strip(), self.ctx.clock())
        finally:
            conn.close()

    def panel_psikologi(self, symbol: str = "BTCUSDT") -> dict:
        """Panel psikologi pasar (§16.2) snapshot terakhir (cron tiap jam): Fear & Greed, funding, Δ OI 24j + Δ harga 24j (kapitulasi/penumpukan), L/S akun vs top trader, taker buy/sell, likuidasi OKX (sampel terbatas), premium Coinbase & IDR, suplai stablecoin 7 hari — masing-masing dengan zona takut_ekstrem|netral|serakah_ekstrem, hitungan ekstrem, divergensi, perubahan 24 jam. Tidak ada skor gabungan; 'tidak tersedia' = sumber gagal/diblokir."""
        return self._call("panel_psikologi", lambda: self._panel(symbol))

    def cari_referensi(self, kata_kunci: str, n: int = 5, slug: Optional[str] = None, salah_satu: bool = False) -> dict:
        """Cari kata kunci (bahasa Inggris, 1–3 kata; semua harus muncul kecuali salah_satu=true) di bab buku referensi pemilik; hasil: judul buku, bab, judul bab, halaman, path, skor, cuplikan ≤ 320 karakter. Kutip persis dari cuplikan; jangan mengarang kutipan. Daftar buku ada di field `buku`."""
        def run():
            return {"kata_kunci": kata_kunci, "hasil": RF.cari(self.ctx.root, kata_kunci, int(n), slug=slug, salah_satu=bool(salah_satu)),
                    "buku": RF.daftar(self.ctx.root), "catatan": "isi buku untuk pemakaian pribadi; kutipan langsung ≤ 15 kata"}
        return self._call("cari_referensi", run)

    def baca_referensi(self, slug: str, bab: int, mulai: int = 0) -> dict:
        """Baca satu bab buku referensi (≤ 12.000 karakter per panggilan; lanjutkan dengan mulai=lanjut_dari). slug dari cari_referensi/daftar."""
        return self._call("baca_referensi", lambda: RF.baca(self.ctx.root, slug, bab, mulai=int(mulai)))

    def statistik_lulus(self, sejak: Optional[str] = None) -> dict:
        """Statistik kelulusan §19.7 per akun (tiket, swing, acak = bayangan acak yang dibuat mesin sebagai pembanding): sampel, expectancy/trade setelah fee, per bulan, win rate, stabilitas tanpa 5% trade terbaik, kepatuhan aturan tiket, tiket vs acak (uji permutasi + sign test). Nilai 'tidak tersedia' bila sampel < 10 — laporkan apa adanya, jangan menafsirkan."""
        def run():
            st = E.compute(self.ctx.engine.conn, self.ctx.clock(), C.parse_iso_ms(sejak) if sejak else None)
            st["markdown"] = E.render_markdown(st)
            return st
        return self._call("statistik_lulus", run)

    # ---- catatan agent (file di bawah ROOT, nama dari jam)
    def _append(self, rel: str, text: str) -> Path:
        p = self.ctx.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def tulis_jurnal(self, jenis: str, judul: str, isi: str, symbol: Optional[str] = None, kandidat_id: Optional[int] = None,
                     order_id: Optional[int] = None, position_id: Optional[int] = None, aturan_dilanggar: Optional[str] = None) -> dict:
        """Catat keputusan/catatan agent ke jurnal/agent/YYYY-MM-DD.md. jenis=keputusan|catatan. Selalu dipanggil setelah menilai kandidat, termasuk saat SKIP. aturan_dilanggar: ID playbook (mis. "P-03,P-07") bila rencana melanggar aturan playbook."""
        def run():
            if jenis not in ("keputusan", "catatan"):
                raise ValueError("jenis harus keputusan|catatan")
            now = self.ctx.clock()
            meta = " ".join(f"{k}={v}" for k, v in (("symbol", symbol), ("kandidat", kandidat_id), ("order", order_id), ("posisi", position_id),
                                                 ("aturan_dilanggar", aturan_dilanggar)) if v)
            block = f"\n## {C.to_wib(now).strftime('%H:%M')} WIB — {jenis} — {judul.strip()}\n" + (f"_{meta}_\n\n" if meta else "\n") + isi.strip() + "\n"
            p = self._append(f"jurnal/agent/{C.day_wib(now)}.md", block)
            return {"ok": True, "path": p.relative_to(self.ctx.root).as_posix(), "bytes": len(block.encode('utf-8'))}
        return self._call("tulis_jurnal", run)

    def baca_memori(self, jenis: str, hari: Optional[str] = None) -> dict:
        """Baca pelajaran (pasar/pelajaran.md), hipotesis, catatan harian (pasar/harian/<hari>.md), jurnal agent (jurnal/agent/<hari>.md), pelajaran-usulan, playbook (referensi/playbook.md: aturan trading pemilik, status aktif/uji/pensiun), atau indeks (referensi/indeks.md: peta bab buku + kata kunci)."""
        def run():
            day = hari or C.day_wib(self.ctx.clock())
            rel = {"pelajaran": "pasar/pelajaran.md", "hipotesis": "pasar/hipotesis.md", "harian": f"pasar/harian/{day}.md",
                   "jurnal": f"jurnal/agent/{day}.md", "pelajaran-usulan": "pasar/pelajaran-usulan.md",
                   "playbook": "referensi/playbook.md", "indeks": "referensi/indeks.md"}.get(jenis)
            if rel is None:
                raise ValueError("jenis harus pelajaran|hipotesis|harian|jurnal|pelajaran-usulan|playbook|indeks")
            jl = self.ctx.root / "pasar" / "hipotesis.jsonl"
            if jenis == "hipotesis" and jl.exists():   # tabel dirender dari jsonl + hasil penilaian skrip
                hasil = {h["id"]: h for h in H.load_jsonl(self.ctx.root / "pasar" / "hipotesis-hasil.jsonl")}
                txt = H.render_hipotesis_md(H.load_jsonl(jl), hasil)
                return {"path": "pasar/hipotesis.jsonl", "ada": True, "isi": txt[-MAX_READ_CHARS:], "terpotong": len(txt) > MAX_READ_CHARS}
            p = self.ctx.root / rel
            if not p.exists():
                return {"path": rel, "ada": False, "isi": ""}
            txt = p.read_text(encoding="utf-8")
            return {"path": rel, "ada": True, "isi": txt[-MAX_READ_CHARS:], "terpotong": len(txt) > MAX_READ_CHARS}
        return self._call("baca_memori", run)

    def _panel_frontmatter(self) -> str:
        """Baris frontmatter §16.4 dari panel psikologi terakhir (kosong bila panel belum ada)."""
        try:
            pn = self._panel("BTCUSDT")
        except Exception:  # noqa: BLE001
            return ""
        if pn.get("status") == "tidak tersedia":
            return ""
        nilai = {r["indikator"]: r["nilai"] for r in pn["indikator"]}
        fmt = lambda v: "tidak tersedia" if v is None else f"{v:g}"  # noqa: E731
        return (f"panel_takut_ekstrem: {pn['takut_ekstrem']}\npanel_serakah_ekstrem: {pn['serakah_ekstrem']}\n"
                f"fng: {fmt(nilai.get('fng'))}\nfunding_btc: {fmt(nilai.get('funding'))}\npanel_ts: {pn['waktu']}\n")

    def tulis_catatan_harian(self, ringkasan_psikologi: str, jejak_grafik: str = "", reaksi_berita: str = "",
                             rezim: str = "tidak tersedia", catatan: str = "", hari: Optional[str] = None) -> dict:
        """Tulis catatan pasar harian pasar/harian/YYYY-MM-DD.md (§16.4). Jika sudah ada, ditambahkan sebagai revisi berjam. hari (YYYY-MM-DD, opsional, tidak boleh di masa depan): untuk evaluasi susulan hari sebelumnya."""
        def run():
            now = self.ctx.clock()
            day = C.day_wib(now)
            if hari:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", hari) or hari > day:
                    raise ValueError("hari harus YYYY-MM-DD dan tidak di masa depan")
                day = hari
            p = self.ctx.root / "pasar" / "harian" / f"{day}.md"
            tick, umur, status = self._tick()
            if not p.exists():
                head = f"---\ntanggal: {day}\njam: \"{C.to_wib(now).strftime('%H:%M')}\"\nrezim: {rezim}\nstatus_data: {status}\n"
                head += self._panel_frontmatter() + "---\n\n"
            else:
                head = f"\n## Revisi {C.to_wib(now).strftime('%H:%M')} WIB\n\n"
            body = (f"## Psikologi hari ini\n{ringkasan_psikologi.strip()}\n\n## Jejak di grafik\n{jejak_grafik.strip() or 'tidak tersedia'}\n\n"
                    f"## Reaksi terhadap berita\n{reaksi_berita.strip() or 'tidak tersedia'}\n\n## Catatan\n{catatan.strip() or '-'}\n")
            self._append(f"pasar/harian/{day}.md", head + body)
            return {"ok": True, "path": f"pasar/harian/{day}.md"}
        return self._call("tulis_catatan_harian", run)

    def tulis_hipotesis(self, pola: str, symbol: str, tf: str, jenis: str, arah: str, nilai: Optional[float] = None,
                        batas_hari: int = 3, kondisi: str = "", catatan: str = "") -> dict:
        """Tambah hipotesis TERUKUR ke pasar/hipotesis.jsonl (maks 3/hari); dinilai skrip uji_hipotesis.py saat jatuh tempo, bukan oleh agent. pola: daftar tetap. tf: 1h|4h|1d. jenis: sentuh_harga (nilai = harga target), gerak_atr (nilai = kelipatan ATR14 tf, mis. 2.0), close_arah (nilai diabaikan). arah: atas|bawah. batas_hari 1–7. kondisi: fakta terukur yang memicu hipotesis (angka, simbol, tf)."""
        def run():
            now = self.ctx.clock()
            day = C.day_wib(now)
            path = self.ctx.root / "pasar" / "hipotesis.jsonl"
            recs = H.load_jsonl(path)
            today = [r for r in recs if r.get("hari") == day]
            if len(today) >= MAX_HIPOTESIS_PER_HARI:
                raise ValueError(f"sudah {MAX_HIPOTESIS_PER_HARI} hipotesis hari ini; tidak boleh menambah lagi")
            sym = symbol.strip()
            lm = self.ctx.market.last_mark(sym)
            harga = float(lm[0]) if lm else None
            atr = None
            if jenis == "gerak_atr" and tf in H.TF:
                h1 = A.load_bars_1h(self.ctx.market, sym, 120 if tf == "1d" else 60, now)
                bars = h1 if tf == "1h" else A.resample(h1, A.TF_MS[tf], now)
                atr = A.atr(bars, H.ATR_N) if len(bars) > H.ATR_N + 1 else None
            rec = H.new_record(f"H-{len(recs) + 1:04d}", now, pola, sym, tf, jenis, arah, nilai, int(batas_hari), kondisi, catatan, harga, atr, "hermes")
            H.append_jsonl(path, rec)
            return {"ok": True, "id": rec["id"], "batas": rec["batas"], "harga_awal": harga, "atr_awal": atr,
                    "sisa_hari_ini": MAX_HIPOTESIS_PER_HARI - len(today) - 1,
                    "catatan": "dinilai skrip (uji_hipotesis.py) setelah batas; hasil terlihat lewat baca_memori('hipotesis')"}
        return self._call("tulis_hipotesis", run)

    def usul_pelajaran(self, pola: str, ringkasan: str, bukti: str, sampel: int = 0) -> dict:
        """Usulkan pelajaran/aturan baru ke pasar/pelajaran-usulan.md dengan status `uji`. Tidak aktif sebelum disetujui user dan lolos penilaian skrip."""
        def run():
            if pola not in POLA:
                raise ValueError(f"pola harus salah satu dari: {', '.join(POLA)}")
            now = self.ctx.clock()
            p = self.ctx.root / "pasar" / "pelajaran-usulan.md"
            n = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("| U-")) if p.exists() else 0
            uid = f"U-{n + 1:03d}"
            cell = lambda s: str(s).replace("|", "/").replace("\n", " ").strip()  # noqa: E731
            if not p.exists():
                self._append("pasar/pelajaran-usulan.md", "# Usulan pelajaran (status uji; perlu persetujuan user)\n\n| ID | Tanggal | Pola | Ringkasan | Bukti | Sampel | Status |\n|---|---|---|---|---|---|---|\n")
            self._append("pasar/pelajaran-usulan.md", f"| {uid} | {C.day_wib(now)} | {pola} | {cell(ringkasan)} | {cell(bukti)} | {int(sampel)} | uji |\n")
            return {"ok": True, "id": uid, "status": "uji"}
        return self._call("usul_pelajaran", run)


# --------------------------------------------------------------------------- registrasi & main
def register(mcp, tools: Tools) -> list[str]:
    names = []
    for name in TOOL_NAMES:
        fn = getattr(tools, name)
        mcp.add_tool(fn, name=name, description=(fn.__doc__ or name).strip())
        names.append(name)
    return names


def main() -> int:
    from mcp.server.fastmcp import FastMCP

    log = C.setup_logging("mcp_server", to_stderr=False)
    mcp = FastMCP("paper")
    register(mcp, Tools())
    log.info("mcp_server mulai (stdio), %d tool", len(TOOL_NAMES))
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
