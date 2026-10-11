"""collector.py — pengumpul data pasar Binance USDT-M Futures dan jam mesin paper.

Satu proses panjang (`run`) mengambil kline 1 menit (harga terakhir + mark price),
funding, snapshot premiumIndex, dan peringkat volume, lalu memanggil mesin paper
untuk memproses setiap bar yang sudah close. Cursor-driven: setelah laptop tidur,
celah data diisi dari kline historis dan mesin memutar ulang bar dalam urutan waktu.

Penulis tunggal data/pasar.sqlite. Tidak ada API key.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from common import (  # noqa: E402
    MINUTE_MS,
    AlreadyRunning,
    BlockedError,
    NetError,
    connect,
    day_wib,
    floor_minute,
    fmt_wib,
    http_get,
    init_schema,
    meta_get,
    meta_set,
    now_ms,
    tx,
)

SCHEMA_VERSION = "2"   # v2: + kline_1h
FAPI = "https://fapi.binance.com"
BRACKETS_URL = "https://www.binance.com/bapi/futures/v1/friendly/future/common/brackets"


# --------------------------------------------------------------------------- klien
class BinanceFapi:
    """Klien tipis endpoint publik. Semua lewat common.http_get (DoH + pacing + deteksi blokir)."""

    def server_time(self) -> int:
        data, _ = http_get(f"{FAPI}/fapi/v1/time")
        return int(data["serverTime"])

    def exchange_info(self) -> dict:
        data, _ = http_get(f"{FAPI}/fapi/v1/exchangeInfo", timeout=20)
        return data

    def brackets(self) -> list[dict]:
        data, _ = http_get(BRACKETS_URL, timeout=20)
        if not isinstance(data, dict) or not data.get("success"):
            raise NetError(f"brackets: respons tidak sukses: {str(data)[:120]}")
        return data["data"]["brackets"]

    def funding_info(self) -> list[dict]:
        data, _ = http_get(f"{FAPI}/fapi/v1/fundingInfo", timeout=20)
        return data

    def ticker_24h(self) -> list[dict]:
        data, _ = http_get(f"{FAPI}/fapi/v1/ticker/24hr", timeout=20)
        return data

    def premium_index(self) -> list[dict]:
        data, _ = http_get(f"{FAPI}/fapi/v1/premiumIndex", timeout=20)
        return data

    def klines_tf(self, symbol: str, interval: str, start_ms: int, end_ms: Optional[int] = None, limit: int = 1500) -> list:
        p = {"symbol": symbol, "interval": interval, "startTime": int(start_ms), "limit": limit}
        if end_ms is not None:
            p["endTime"] = int(end_ms)
        data, _ = http_get(f"{FAPI}/fapi/v1/klines", p, timeout=20)
        return data

    def klines(self, symbol: str, start_ms: int, end_ms: Optional[int] = None, limit: int = 1500) -> list:
        return self.klines_tf(symbol, "1m", start_ms, end_ms, limit)

    def mark_klines(self, symbol: str, start_ms: int, end_ms: Optional[int] = None, limit: int = 1500) -> list:
        p = {"symbol": symbol, "interval": "1m", "startTime": int(start_ms), "limit": limit}
        if end_ms is not None:
            p["endTime"] = int(end_ms)
        data, _ = http_get(f"{FAPI}/fapi/v1/markPriceKlines", p, timeout=20)
        return data

    def funding_history(self, symbol: str, start_ms: int, end_ms: Optional[int] = None, limit: int = 1000) -> list:
        p = {"symbol": symbol, "startTime": int(start_ms), "limit": limit}
        if end_ms is not None:
            p["endTime"] = int(end_ms)
        data, _ = http_get(f"{FAPI}/fapi/v1/fundingRate", p, timeout=20)
        return data


# --------------------------------------------------------------------------- konfigurasi
@dataclass
class CollectorConfig:
    top_n: int = 20
    interval_s: int = 60
    static_refresh_h: int = 24
    bar_grace_ms: int = 5_000
    initial_history_h: int = 48      # riwayat awal per simbol baru
    max_backfill_days: int = 30      # batas celah yang diisi ulang
    refetch_last_bars: int = 2       # bar terakhir selalu diambil ulang (Binance bisa merevisi)
    ticker_every_min: int = 5        # simpan peringkat volume tiap N menit
    ticker_keep_top: int = 50
    funding_every_min: int = 10
    retention_days: int = 21
    snapshot_days: int = 3
    ticker_days: int = 7
    log_days: int = 30
    klines_1h_history_days: int = 120   # backfill awal per simbol baru
    klines_1h_retention_days: int = 180
    klines_1h_grace_ms: int = 60_000    # ambil bar 1h setelah close + grace
    klines_1h_backfill_per_tick: int = 5
    extra_symbols: tuple = field(default_factory=tuple)


@dataclass
class TickReport:
    ts: int = 0
    symbols: int = 0
    bars: int = 0
    bars_1h: int = 0
    gap_ms: int = 0
    engine: Optional[dict] = None
    duration_ms: int = 0
    weight: Optional[int] = None
    errors: list = field(default_factory=list)


# --------------------------------------------------------------------------- parser
def parse_symbol_info(info: dict, funding_info: Optional[list]) -> dict[str, dict]:
    fi = {}
    for item in funding_info or []:
        fi[item["symbol"]] = item
    out = {}
    for s in info.get("symbols", []):
        f = {x["filterType"]: x for x in s.get("filters", [])}
        extra = fi.get(s["symbol"], {})
        out[s["symbol"]] = {
            "symbol": s["symbol"],
            "status": s.get("status"),
            "contract_type": s.get("contractType"),
            "base_asset": s.get("baseAsset"),
            "quote_asset": s.get("quoteAsset"),
            "onboard_date": s.get("onboardDate"),
            "tick_size": f.get("PRICE_FILTER", {}).get("tickSize"),
            "qty_step": f.get("LOT_SIZE", {}).get("stepSize"),
            "min_qty": f.get("LOT_SIZE", {}).get("minQty"),
            "max_qty": f.get("LOT_SIZE", {}).get("maxQty"),
            "min_notional": f.get("MIN_NOTIONAL", {}).get("notional"),
            "pct_up": _f(f.get("PERCENT_PRICE", {}).get("multiplierUp")),
            "pct_down": _f(f.get("PERCENT_PRICE", {}).get("multiplierDown")),
            "liq_fee": _f(s.get("liquidationFee")),
            "funding_interval_h": int(extra.get("fundingIntervalHours", 8) or 8),
            "funding_cap": _f(extra.get("adjustedFundingRateCap")),
            "funding_floor": _f(extra.get("adjustedFundingRateFloor")),
            "raw_json": json.dumps(s, separators=(",", ":")),
        }
    return out


def parse_brackets(rows: list[dict]) -> list[tuple]:
    out = []
    for r in rows:
        for b in r.get("riskBrackets", []):
            out.append(
                (
                    r["symbol"],
                    int(b["bracketSeq"]),
                    _f(b.get("bracketNotionalFloor")),
                    _f(b.get("bracketNotionalCap")),
                    int(b.get("maxOpenPosLeverage") or 0),
                    int(b.get("minOpenPosLeverage") or 1),
                    _f(b.get("bracketMaintenanceMarginRate")),
                    _f(b.get("cumFastMaintenanceAmount")),
                )
            )
    return out


def parse_kline(symbol: str, k: list) -> tuple:
    return (
        symbol, int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]),
        float(k[5]), float(k[7]), int(k[8]), float(k[10]),
    )


def parse_mark_kline(symbol: str, k: list) -> tuple:
    return (symbol, int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]))


def _f(x) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def kline_limit(start_ms: int, to_ms: int, max_limit: int = 1500, tf_ms: int = MINUTE_MS) -> int:
    """Jumlah bar yang diminta: secukupnya + 2. Weight Binance mengikuti `limit`
    (< 100 → 1, < 500 → 2, ≤ 1000 → 5, > 1000 → 10), jadi tick rutin tidak boleh minta 1500."""
    need = (to_ms - start_ms) // tf_ms + 1
    return max(2, min(max_limit, need + 2))


REVISION_MIN_REL = 1e-4   # revisi bar < 0,01% diabaikan (Binance merapikan mark kline yang baru close)


# --------------------------------------------------------------------------- collector
class Collector:
    def __init__(self, conn, api: BinanceFapi, cfg: CollectorConfig, engine=None, log: Optional[logging.Logger] = None):
        self.conn = conn
        self.api = api
        self.cfg = cfg
        self.engine = engine
        self.log = log or logging.getLogger("collector")
        init_schema(conn, C.SCRIPTS_DIR / "schema_pasar.sql", SCHEMA_VERSION)
        self.offset_ms = int(meta_get(conn, "server_offset_ms", "0") or 0)

    # ---- util
    def server_now(self) -> int:
        return now_ms() + self.offset_ms

    def event(self, level: str, type_: str, msg: str, symbol: Optional[str] = None) -> None:
        self.conn.execute(
            "INSERT INTO events(ts, level, type, symbol, msg) VALUES(?,?,?,?,?)",
            (self.server_now(), level, type_, symbol, msg),
        )
        getattr(self.log, level.lower(), self.log.info)("%s %s %s", type_, symbol or "", msg)

    def last_closed_open(self, server_now: int) -> int:
        """open_time bar 1m terakhir yang sudah close (dengan grace)."""
        return floor_minute(server_now - self.cfg.bar_grace_ms) - MINUTE_MS

    # ---- statis
    def refresh_static(self, force: bool = False) -> bool:
        last = int(meta_get(self.conn, "last_static_refresh", "0") or 0)
        if not force and self.server_now() - last < self.cfg.static_refresh_h * C.HOUR_MS:
            return False
        info = self.api.exchange_info()
        try:
            finfo = self.api.funding_info()
        except NetError as e:
            finfo = None
            self.event("WARNING", "FUNDING_INFO", f"gagal: {e}")
        try:
            brackets = parse_brackets(self.api.brackets())
        except NetError as e:
            brackets = []
            self.event("WARNING", "BRACKETS", f"gagal (leverage/MMR 'tidak tersedia' untuk simbol baru): {e}")
        parsed = parse_symbol_info(info, finfo)
        ts = self.server_now()
        watch = ("status", "tick_size", "qty_step", "min_qty", "min_notional", "funding_interval_h", "contract_type")
        with tx(self.conn):
            old = {r["symbol"]: dict(r) for r in self.conn.execute("SELECT * FROM symbol_info")}
            for sym, row in parsed.items():
                o = old.get(sym)
                if o:
                    for fld in watch:
                        if str(o.get(fld)) != str(row.get(fld)):
                            self.conn.execute(
                                "INSERT INTO symbol_info_hist(symbol, changed_ts, field, old, new) VALUES(?,?,?,?,?)",
                                (sym, ts, fld, str(o.get(fld)), str(row.get(fld))),
                            )
                            if fld == "status":
                                self.event("WARNING", "STATUS_CHANGE", f"{o.get(fld)} → {row.get(fld)}", sym)
                self.conn.execute(
                    """INSERT INTO symbol_info(symbol,status,contract_type,base_asset,quote_asset,onboard_date,
                         tick_size,qty_step,min_qty,max_qty,min_notional,pct_up,pct_down,liq_fee,
                         funding_interval_h,funding_cap,funding_floor,updated_ts,raw_json)
                       VALUES(:symbol,:status,:contract_type,:base_asset,:quote_asset,:onboard_date,
                         :tick_size,:qty_step,:min_qty,:max_qty,:min_notional,:pct_up,:pct_down,:liq_fee,
                         :funding_interval_h,:funding_cap,:funding_floor,:updated_ts,:raw_json)
                       ON CONFLICT(symbol) DO UPDATE SET
                         status=excluded.status, contract_type=excluded.contract_type, base_asset=excluded.base_asset,
                         quote_asset=excluded.quote_asset, onboard_date=excluded.onboard_date, tick_size=excluded.tick_size,
                         qty_step=excluded.qty_step, min_qty=excluded.min_qty, max_qty=excluded.max_qty,
                         min_notional=excluded.min_notional, pct_up=excluded.pct_up, pct_down=excluded.pct_down,
                         liq_fee=excluded.liq_fee, funding_interval_h=excluded.funding_interval_h,
                         funding_cap=excluded.funding_cap, funding_floor=excluded.funding_floor,
                         updated_ts=excluded.updated_ts, raw_json=excluded.raw_json""",
                    {**row, "updated_ts": ts},
                )
            for sym in old:
                if sym not in parsed and old[sym].get("status") == "TRADING":
                    self.conn.execute("UPDATE symbol_info SET status='GONE', updated_ts=? WHERE symbol=?", (ts, sym))
                    self.event("WARNING", "STATUS_CHANGE", "hilang dari exchangeInfo", sym)
            if brackets:
                self.conn.executemany(
                    """INSERT INTO leverage_bracket(symbol,bracket,notional_floor,notional_cap,max_leverage,min_leverage,mmr,cum,updated_ts)
                       VALUES(?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(symbol,bracket) DO UPDATE SET notional_floor=excluded.notional_floor,
                         notional_cap=excluded.notional_cap, max_leverage=excluded.max_leverage,
                         min_leverage=excluded.min_leverage, mmr=excluded.mmr, cum=excluded.cum, updated_ts=excluded.updated_ts""",
                    [b + (ts,) for b in brackets],
                )
            meta_set(self.conn, "last_static_refresh", ts)
        self.log.info("statis diperbarui: %d simbol, %d baris bracket", len(parsed), len(brackets))
        return True

    # ---- universe
    def tradeable(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT symbol FROM symbol_info WHERE status='TRADING' AND contract_type='PERPETUAL' AND quote_asset='USDT'"
        )
        return {r[0] for r in rows}

    def store_ticker(self, tickers: list[dict], ts: int, tradeable: set[str]) -> list[str]:
        rows = [t for t in tickers if t.get("symbol") in tradeable]
        rows.sort(key=lambda t: float(t.get("quoteVolume") or 0), reverse=True)
        minute = (ts // MINUTE_MS) % self.cfg.ticker_every_min == 0
        if minute:
            with tx(self.conn):
                self.conn.executemany(
                    "INSERT OR REPLACE INTO ticker_24h(ts,symbol,rank,last,pct_24h,quote_volume) VALUES(?,?,?,?,?,?)",
                    [
                        (floor_minute(ts), t["symbol"], i + 1, _f(t.get("lastPrice")), _f(t.get("priceChangePercent")), _f(t.get("quoteVolume")))
                        for i, t in enumerate(rows[: self.cfg.ticker_keep_top])
                    ],
                )
        return [t["symbol"] for t in rows[: self.cfg.top_n]]

    def universe(self, top: list[str], tradeable: set[str]) -> list[str]:
        uni = list(top)
        for s in self.cfg.extra_symbols:
            if s in tradeable and s not in uni:
                uni.append(s)
        if self.engine is not None:
            for s in self.engine.active_symbols():
                if s not in uni:
                    uni.append(s)
        return uni

    # ---- bar
    def _last_open(self, table: str, symbol: str) -> Optional[int]:
        r = self.conn.execute(f"SELECT MAX(open_time) FROM {table} WHERE symbol=?", (symbol,)).fetchone()
        return int(r[0]) if r and r[0] is not None else None

    def backfill(self, symbol: str, from_ms: int, to_ms: int) -> int:
        """Mengisi kline_1m dan mark_kline_1m untuk [from_ms, to_ms] (open_time). Mengembalikan jumlah bar last-price."""
        n_total = 0
        for table, fetch, parser in (
            ("kline_1m", self.api.klines, parse_kline),
            ("mark_kline_1m", self.api.mark_klines, parse_mark_kline),
        ):
            start = from_ms
            guard = 0
            while start <= to_ms and guard < 2000:
                guard += 1
                limit = kline_limit(start, to_ms)
                rows = fetch(symbol, start, to_ms, limit)
                if not rows:
                    break
                parsed = [parser(symbol, k) for k in rows if int(k[0]) <= to_ms]
                if not parsed:
                    break
                self._upsert_bars(table, symbol, parsed)
                if table == "kline_1m":
                    n_total += len(parsed)
                last_open = int(rows[-1][0])
                if len(rows) < limit or last_open >= to_ms:
                    break
                start = last_open + MINUTE_MS
        return n_total

    def _upsert_bars(self, table: str, symbol: str, parsed: list[tuple]) -> None:
        if not parsed:
            return
        # Deteksi revisi: bar yang sudah diproses mesin tapi nilainya berubah.
        cursor = self.engine.cursor_for(symbol) if self.engine is not None else None
        if cursor is not None:
            check = [p for p in parsed if p[1] <= cursor]
            if check:
                lo, hi = min(p[1] for p in check), max(p[1] for p in check)
                old = {
                    int(r["open_time"]): r
                    for r in self.conn.execute(
                        f"SELECT * FROM {table} WHERE symbol=? AND open_time BETWEEN ? AND ?", (symbol, lo, hi)
                    )
                }
                exposed = self.engine.has_exposure(symbol)
                for p in check:
                    o = old.get(p[1])
                    if o is None:
                        continue
                    ref = abs(p[5]) or 1.0
                    rel = max(abs(o["high"] - p[3]), abs(o["low"] - p[4]), abs(o["close"] - p[5])) / ref
                    if rel < REVISION_MIN_REL:
                        continue
                    msg = f"{table} {fmt_wib(p[1])} h/l/c {o['high']}/{o['low']}/{o['close']} → {p[3]}/{p[4]}/{p[5]} ({rel:.4%})"
                    if exposed:
                        self.event("WARNING", "BAR_REVISED", msg, symbol)
                    else:
                        self.log.info("BAR_REVISED %s %s", symbol, msg)
        if table == "kline_1m":
            sql = "INSERT OR REPLACE INTO kline_1m(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,?,?,?,?)"
        else:
            sql = "INSERT OR REPLACE INTO mark_kline_1m(symbol,open_time,open,high,low,close) VALUES(?,?,?,?,?,?)"
        with tx(self.conn):
            self.conn.executemany(sql, parsed)

    def update_klines_1h(self, universe: Iterable[str], server_now: int) -> int:
        """Bar 1 jam: sekali per jam setelah close + grace; simbol baru di-backfill 120 hari (maks N simbol per tick)."""
        cfg = self.cfg
        hour = server_now // C.HOUR_MS
        if server_now % C.HOUR_MS < cfg.klines_1h_grace_ms:
            return 0
        if int(meta_get(self.conn, "last_1h_hour", "0") or 0) == hour:
            return 0
        last_closed = hour * C.HOUR_MS - C.HOUR_MS
        n, fresh_budget, pending_new = 0, cfg.klines_1h_backfill_per_tick, False
        for sym in universe:
            cur = self._last_open("kline_1h", sym)
            if cur is None:
                if fresh_budget <= 0:
                    pending_new = True
                    continue
                fresh_budget -= 1
                start = last_closed - cfg.klines_1h_history_days * C.DAY_MS
            elif cur >= last_closed:
                continue      # belum ada bar baru untuk simbol ini
            else:
                start = cur   # refetch bar terakhir (bisa direvisi), lalu bar baru
            if start > last_closed:
                continue
            try:
                n += self._fetch_1h(sym, start, last_closed)
            except BlockedError:
                raise
            except NetError as e:
                self.event("WARNING", "BAR_1H", str(e), sym)
        if not pending_new:
            with tx(self.conn):
                meta_set(self.conn, "last_1h_hour", hour)
        return n

    def _fetch_1h(self, symbol: str, from_ms: int, to_ms: int) -> int:
        n, start, guard = 0, from_ms, 0
        while start <= to_ms and guard < 200:
            guard += 1
            limit = kline_limit(start, to_ms, tf_ms=C.HOUR_MS)
            rows = self.api.klines_tf(symbol, "1h", start, to_ms, limit)
            if not rows:
                break
            parsed = [parse_kline(symbol, k) for k in rows if int(k[0]) <= to_ms]
            if not parsed:
                break
            with tx(self.conn):
                self.conn.executemany(
                    "INSERT OR REPLACE INTO kline_1h(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    parsed,
                )
            n += len(parsed)
            last_open = int(rows[-1][0])
            if len(rows) < limit or last_open >= to_ms:
                break
            start = last_open + C.HOUR_MS
        return n

    def update_funding(self, symbols: Iterable[str], server_now: int) -> int:
        n = 0
        for sym in symbols:
            r = self.conn.execute("SELECT MAX(funding_time) FROM funding_rate WHERE symbol=?", (sym,)).fetchone()
            since = int(r[0]) + 1 if r and r[0] is not None else server_now - 7 * C.DAY_MS
            try:
                rows = self.api.funding_history(sym, since, server_now)
            except NetError as e:
                self.event("WARNING", "FUNDING", f"gagal: {e}", sym)
                continue
            if rows:
                with tx(self.conn):
                    self.conn.executemany(
                        "INSERT OR REPLACE INTO funding_rate(symbol,funding_time,rate,mark_price) VALUES(?,?,?,?)",
                        [(sym, int(x["fundingTime"]), float(x["fundingRate"]), _f(x.get("markPrice"))) for x in rows],
                    )
                n += len(rows)
        return n

    # ---- tick
    def tick(self) -> TickReport:
        rep = TickReport()
        t0 = time.monotonic()
        server_now = self.api.server_time()
        self.offset_ms = server_now - now_ms()
        rep.ts = server_now
        last_tick = int(meta_get(self.conn, "last_tick_ms", "0") or 0)
        if last_tick and server_now - last_tick > 2.5 * self.cfg.interval_s * 1000:
            rep.gap_ms = server_now - last_tick
            self.event("WARNING", "GAP", f"tidak ada tick sejak {fmt_wib(last_tick)} ({rep.gap_ms // 60000} menit); mengisi celah")
        with tx(self.conn):
            meta_set(self.conn, "server_offset_ms", self.offset_ms)
        self.refresh_static()
        tradeable = self.tradeable()
        top = self.store_ticker(self.api.ticker_24h(), server_now, tradeable)
        uni = self.universe(top, tradeable)
        rep.symbols = len(uni)

        # snapshot mark price
        prem = {p["symbol"]: p for p in self.api.premium_index()}
        with tx(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO mark_snapshot(symbol,ts,mark,index_price,last_funding_rate,next_funding_time) VALUES(?,?,?,?,?,?)",
                [
                    (s, server_now, _f(prem[s].get("markPrice")), _f(prem[s].get("indexPrice")), _f(prem[s].get("lastFundingRate")), int(prem[s].get("nextFundingTime") or 0))
                    for s in uni if s in prem
                ],
            )

        # bar
        last_closed = self.last_closed_open(server_now)
        floor_start = last_closed - self.cfg.max_backfill_days * C.DAY_MS
        for sym in uni:
            cur = self._last_open("kline_1m", sym)
            if cur is None:
                start = last_closed - self.cfg.initial_history_h * C.HOUR_MS
            else:
                start = cur - (self.cfg.refetch_last_bars - 1) * MINUTE_MS
            start = max(start, floor_start)
            if start > last_closed:
                continue
            try:
                rep.bars += self.backfill(sym, start, last_closed)
            except BlockedError:
                raise
            except NetError as e:
                rep.errors.append(f"{sym}: {e}")
                self.event("WARNING", "BAR_FETCH", str(e), sym)

        # bar 1 jam (sekali per jam)
        try:
            rep.bars_1h = self.update_klines_1h(uni, server_now)
        except BlockedError:
            raise
        except NetError as e:
            rep.errors.append(f"1h: {e}")
            self.event("WARNING", "BAR_1H", str(e))

        # funding: simbol berposisi tiap tick, lainnya tiap N menit
        need = set(self.engine.active_symbols()) if self.engine is not None else set()
        if (server_now // MINUTE_MS) % self.cfg.funding_every_min == 0:
            need |= set(uni)
        if need:
            self.update_funding(sorted(need), server_now)

        # mesin paper
        if self.engine is not None:
            try:
                rep.engine = self.engine.step(until_ms=server_now)
            except Exception as e:  # noqa: BLE001 - mesin tidak boleh menjatuhkan collector
                rep.errors.append(f"mesin: {e}")
                self.event("ERROR", "ENGINE", f"{type(e).__name__}: {e}")
                self.log.exception("mesin gagal")

        # retensi saat pergantian hari
        today = day_wib(server_now)
        if meta_get(self.conn, "last_retention_day") != today:
            try:
                self.retention()
            except Exception as e:  # noqa: BLE001
                self.event("ERROR", "RETENTION", str(e))
            with tx(self.conn):
                meta_set(self.conn, "last_retention_day", today)

        rep.duration_ms = int((time.monotonic() - t0) * 1000)
        rep.weight = C.PACER.last_weight
        with tx(self.conn):
            meta_set(self.conn, "last_tick_ms", server_now)
            self.conn.execute(
                "INSERT OR REPLACE INTO collector_run(ts,kind,symbols_n,bars_n,ok,err,duration_ms,weight_used) VALUES(?,?,?,?,?,?,?,?)",
                (server_now, "tick", rep.symbols, rep.bars, 0 if rep.errors else 1, "; ".join(rep.errors)[:500] or None, rep.duration_ms, rep.weight),
            )
        return rep

    # ---- retensi
    def retention(self) -> dict:
        now = self.server_now()
        protected = self.engine.protected_ranges() if self.engine is not None else []
        cutoff = now - self.cfg.retention_days * C.DAY_MS
        removed = {}
        with tx(self.conn):
            for table in ("kline_1m", "mark_kline_1m"):
                before = self.conn.total_changes
                if protected:
                    cond = " AND NOT (" + " OR ".join("(symbol=? AND open_time BETWEEN ? AND ?)" for _ in protected) + ")"
                    params: list = [cutoff]
                    for sym, a, b in protected:
                        params += [sym, a - C.HOUR_MS, b + C.HOUR_MS]
                    self.conn.execute(f"DELETE FROM {table} WHERE open_time < ?{cond}", params)
                else:
                    self.conn.execute(f"DELETE FROM {table} WHERE open_time < ?", (cutoff,))
                removed[table] = self.conn.total_changes - before
            before = self.conn.total_changes
            self.conn.execute("DELETE FROM kline_1h WHERE open_time < ?", (now - self.cfg.klines_1h_retention_days * C.DAY_MS,))
            removed["kline_1h"] = self.conn.total_changes - before
            self.conn.execute("DELETE FROM mark_snapshot WHERE ts < ?", (now - self.cfg.snapshot_days * C.DAY_MS,))
            self.conn.execute("DELETE FROM ticker_24h WHERE ts < ?", (now - self.cfg.ticker_days * C.DAY_MS,))
            self.conn.execute("DELETE FROM collector_run WHERE ts < ?", (now - self.cfg.log_days * C.DAY_MS,))
            self.conn.execute("DELETE FROM events WHERE ts < ?", (now - self.cfg.log_days * C.DAY_MS,))
        self.conn.execute("PRAGMA incremental_vacuum")
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.log.info("retensi: %s", removed)
        return removed

    # ---- loop
    def run(self, once: bool = False) -> None:
        with C.single_instance_lock("collector"):
            self.log.info("collector mulai (top %d, interval %ds)", self.cfg.top_n, self.cfg.interval_s)
            while True:
                try:
                    rep = self.tick()
                    self.log.info(
                        "tick %s: %d simbol, %d bar, %d ms, weight %s%s%s%s",
                        fmt_wib(rep.ts), rep.symbols, rep.bars, rep.duration_ms, rep.weight,
                        f", bar1h {rep.bars_1h}" if rep.bars_1h else "",
                        f", mesin {rep.engine}" if rep.engine else "",
                        f", error {len(rep.errors)}" if rep.errors else "",
                    )
                except BlockedError as e:
                    self.event("ERROR", "BLOCKED", str(e))
                except NetError as e:
                    self.event("WARNING", "NET", str(e))
                except KeyboardInterrupt:
                    self.log.info("dihentikan")
                    return
                except Exception as e:  # noqa: BLE001
                    self.event("ERROR", "TICK", f"{type(e).__name__}: {e}")
                    self.log.exception("tick gagal")
                if once:
                    return
                # selaras ke detik :05 menit berikutnya
                sleep_s = self.cfg.interval_s - (time.time() % self.cfg.interval_s) + 5.0
                time.sleep(max(1.0, min(sleep_s, self.cfg.interval_s + 5.0)))


# --------------------------------------------------------------------------- CLI
def build(args, with_engine: bool = True) -> Collector:
    conn = connect(C.PASAR_DB)
    cfg = CollectorConfig(top_n=args.n, interval_s=args.interval)
    engine = None
    if with_engine and not getattr(args, "tanpa_mesin", False):
        from paper_engine import PaperEngine, SqliteMarket  # noqa: WPS433 - impor lokal menghindari siklus

        market = SqliteMarket(conn)
        engine = PaperEngine(connect(C.PAPER_DB), market)
    log = C.setup_logging("collector")
    return Collector(conn, BinanceFapi(), cfg, engine=engine, log=log)


def cmd_status(args) -> None:
    if not C.PASAR_DB.exists():
        print("Belum ada data: pasar.sqlite belum dibuat. Jalankan `collector.py run --once` dulu.")
        return
    conn = connect(C.PASAR_DB, readonly=True)
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meta'").fetchone() is None:
        print("pasar.sqlite ada tapi skema belum dibuat. Jalankan `collector.py run --once`.")
        return
    now = now_ms()
    last = int(meta_get(conn, "last_tick_ms", "0") or 0)
    print(f"Tick terakhir : {fmt_wib(last) if last else 'belum ada'} ({(now - last) // 60000 if last else '-'} menit lalu)")
    print(f"Offset server : {meta_get(conn, 'server_offset_ms', '-')} ms | statis: {fmt_wib(int(meta_get(conn, 'last_static_refresh', '0') or 0))}")
    n_sym = conn.execute("SELECT COUNT(*) FROM symbol_info WHERE status='TRADING'").fetchone()[0]
    n_br = conn.execute("SELECT COUNT(DISTINCT symbol) FROM leverage_bracket").fetchone()[0]
    print(f"Simbol TRADING: {n_sym} | simbol dengan bracket: {n_br}")
    try:
        r1h = conn.execute("SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(open_time), MAX(open_time) FROM kline_1h").fetchone()
        if r1h and r1h[1]:
            print(f"Bar 1h: {r1h[0]} simbol, {r1h[1]} bar, {fmt_wib(int(r1h[2]))} → {fmt_wib(int(r1h[3]))}")
        else:
            print("Bar 1h: belum ada")
    except Exception:  # noqa: BLE001 - skema lama tanpa kline_1h
        print("Bar 1h: tabel belum ada (skema lama)")
    print("\n| simbol | bar 1m | bar terakhir (WIB) | umur | mark bar |")
    print("|---|---|---|---|---|")
    for r in conn.execute(
        "SELECT k.symbol, COUNT(*) n, MAX(k.open_time) mx, (SELECT COUNT(*) FROM mark_kline_1m m WHERE m.symbol=k.symbol) mk "
        "FROM kline_1m k GROUP BY k.symbol ORDER BY n DESC LIMIT 40"
    ):
        age = (now - int(r["mx"])) // 60000
        print(f"| {r['symbol']} | {r['n']} | {fmt_wib(int(r['mx']))} | {age} mnt | {r['mk']} |")
    print("\nEvent terakhir:")
    for r in conn.execute("SELECT ts, level, type, symbol, msg FROM events ORDER BY id DESC LIMIT 10"):
        print(f"  {fmt_wib(int(r['ts']))} {r['level']} {r['type']} {r['symbol'] or ''} {r['msg']}")
    try:
        size = C.PASAR_DB.stat().st_size / 1e6
        print(f"\nUkuran pasar.sqlite: {size:.1f} MB")
    except OSError:
        pass


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Pengumpul data pasar Binance USDT-M Futures (endpoint publik, DoH).")
    ap.add_argument("--n", type=int, default=20, help="jumlah simbol top volume")
    ap.add_argument("--interval", type=int, default=60, help="detik antar tick")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="loop pengumpulan + mesin paper")
    p_run.add_argument("--once", action="store_true")
    p_run.add_argument("--tanpa-mesin", action="store_true", help="hanya data, tanpa mesin paper")
    p_bf = sub.add_parser("backfill", help="isi ulang kline satu simbol")
    p_bf.add_argument("--symbol", required=True)
    p_bf.add_argument("--dari", required=True, help="ISO WIB, mis. 2026-10-10T07:00")
    p_bf.add_argument("--sampai", default=None)
    sub.add_parser("status")
    sub.add_parser("retention")
    sub.add_parser("static", help="segarkan exchangeInfo/brackets/fundingInfo sekarang")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        cmd_status(args)
        return 0
    col = build(args, with_engine=(args.cmd == "run"))
    try:
        if args.cmd == "run":
            col.run(once=args.once)
        elif args.cmd == "backfill":
            to = C.parse_iso_ms(args.sampai) if args.sampai else col.last_closed_open(col.api.server_time())
            n = col.backfill(args.symbol, floor_minute(C.parse_iso_ms(args.dari)), floor_minute(to))
            print(f"{args.symbol}: {n} bar diisi")
        elif args.cmd == "retention":
            print(col.retention())
        elif args.cmd == "static":
            col.refresh_static(force=True)
            print("statis diperbarui")
    except AlreadyRunning as e:
        print(f"Sudah berjalan: {e}", file=sys.stderr)
        return 2
    except BlockedError as e:
        print(f"Diblokir: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
