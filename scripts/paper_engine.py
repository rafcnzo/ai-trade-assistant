"""paper_engine.py — mesin simulasi paper trading Binance USDT-M Futures (isolated margin, one-way).

Aturan utama (spesifikasi §17 dan §19.4):
- Limit order terisi hanya jika harga MENEMBUS level (bukan menyentuh); fee maker.
- Market/stop order terisi di open bar berikutnya ± slippage; fee taker.
- Likuidasi dan stop dicek pada MARK PRICE; TP dicek pada harga terakhir.
- Ambiguitas dalam satu bar 1 menit diputuskan pesimis (liq → SL → TP) dan ditandai.
- Tanpa look-ahead: order yang dibuat pada T hanya berlaku dari bar open_time ≥ ceil_minute(T).
- Budget tiket: margin + fee masuk semua tiket per hari WIB ≤ $1. Swing: margin ≤ $10 per posisi.

Penulis tunggal data/paper.sqlite. Hasil trade hanya ditulis mesin.
"""
from __future__ import annotations

import argparse
import random
import csv
import json
import logging
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Optional, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from common import (  # noqa: E402
    MINUTE_MS,
    Bar,
    D,
    MarkBar,
    ceil_minute,
    connect,
    day_wib,
    floor_minute,
    fmt_wib,
    init_schema,
    is_multiple,
    meta_get,
    meta_set,
    now_ms,
    tx,
    wib_clock_ms,
)

SCHEMA_VERSION = "3"   # v2: akun acak, orders.tp_pct/sl_pct; v3: arena (akun persona, account.status)
LONG, SHORT = "LONG", "SHORT"
TIKET, SWING, ACAK = "tiket", "swing", "acak"
DAILY_ACCOUNTS = (TIKET, ACAK)   # kompat; sumber kebenaran = tabel account (kind tiket|acak = harian). Lihat PaperEngine.is_daily
DAILY_KINDS = ("tiket", "acak")
ENTRY_TYPES = ("LIMIT", "MARKET")


# --------------------------------------------------------------------------- konfigurasi
@dataclass
class EngineConfig:
    fee_maker: float = 0.0002
    fee_taker: float = 0.0005
    slippage: dict = field(default_factory=lambda: {"mayor": 0.0002, "large": 0.0005, "small": 0.0010})
    tiket_budget: float = 1.00             # saldo awal tiap hari WIB; TP menambah, hangus mengurangi (bergulir)
    tiket_min_saldo: float = 0.50          # di bawah ini tidak boleh buka tiket baru sampai besok
    tiket_max_per_order: float = 1.00      # satu tiket tidak boleh memakai lebih dari ini walau saldo tumbuh
    tiket_fee_from_budget: bool = True      # margin + fee masuk ≤ budget (wallet $1 nyata tidak bisa buka margin $1)
    tiket_eod_wib: str = "23:50"            # posisi tiket ditutup paksa, order entry tiket kedaluwarsa
    swing_margin: float = 10.00
    swing_max_open: int = 2
    swing_min_rr: float = 2.5
    swing_liq_buffer: float = 0.005
    swing_entry_ttl_h: int = 72
    bar_grace_ms: int = 5_000
    mark_fallback_to_last: bool = True
    acak_enabled: bool = True              # setiap order tiket (bukan dari mesin) dibuatkan bayangan acak di akun `acak`
    acak_seed: str = "acak-v1"             # sisi acak = Random(f"{seed}:{order_id}") → deterministik, bisa diverifikasi
    acak_budget: float = 1.00
    tiket_breakeven_mfe: float = 0.8   # tiket/acak: setelah harga menempuh >= 80% jalan ke TP, SL dipindah ke harga masuk (pengaman; 0 = mati)


# --------------------------------------------------------------------------- budget harian bergulir
def budget_harian(conn, account: str, day: str, budget: float, min_saldo: float, max_per_order: float) -> dict:
    """Saldo tiket/acak hari WIB `day`: mulai `budget`, ditambah hasil bersih posisi yang ditutup hari itu (TP menambah,
    hangus mengurangi), dikurangi yang terkunci (margin+fee posisi terbuka) dan tereservasi (order hidup).
    Boleh buka tiket baru bila saldo ≥ min_saldo; satu order ≤ max_per_order."""
    realisasi = conn.execute("SELECT COALESCE(SUM(net_result),0) FROM positions WHERE account=? AND day_wib=? AND status='CLOSED'", (account, day)).fetchone()[0]
    terkunci = conn.execute(
        "SELECT COALESCE(SUM(margin_initial + COALESCE((SELECT fee_usdt FROM fills f WHERE f.order_id=p.entry_order_id), 0)), 0) "
        "FROM positions p WHERE account=? AND day_wib=? AND status='OPEN'", (account, day)).fetchone()[0]
    reserved = conn.execute(
        "SELECT COALESCE(SUM(margin_usdt + COALESCE(fee_reserved,0)), 0) FROM orders WHERE account=? AND reduce_only=0 AND status IN ('NEW','ACTIVE') AND day_wib=?",
        (account, day)).fetchone()[0]
    saldo = budget + float(realisasi)
    remaining = max(0.0, saldo - float(terkunci) - float(reserved))
    return {"account": account, "day": day, "budget": budget, "realisasi": float(realisasi), "used": float(terkunci), "reserved": float(reserved),
            "saldo": saldo, "remaining": remaining, "min_saldo": min_saldo, "max_per_order": max_per_order,
            "boleh_buka": saldo >= min_saldo, "maks_order_sekarang": min(remaining, max_per_order)}


# --------------------------------------------------------------------------- data pasar
@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    status: str
    tick_size: Decimal
    qty_step: Decimal
    min_qty: Decimal
    min_notional: Decimal
    pct_up: Optional[float] = None
    pct_down: Optional[float] = None
    funding_interval_h: int = 8


@dataclass(frozen=True)
class Bracket:
    bracket: int
    notional_floor: float
    notional_cap: float
    max_leverage: int
    mmr: float
    cum: float


@dataclass(frozen=True)
class FundingEvent:
    symbol: str
    funding_time: int
    rate: float
    mark_price: Optional[float] = None


class MarketData(Protocol):
    def bars(self, symbol: str, after_open_time: int, until_open_time: int) -> list[tuple[Bar, Optional[MarkBar]]]: ...
    def funding_events(self, symbol: str, after_ms: int, until_ms: int) -> list[FundingEvent]: ...
    def filters(self, symbol: str) -> Optional[SymbolFilters]: ...
    def brackets(self, symbol: str) -> list[Bracket]: ...
    def last_mark(self, symbol: str) -> Optional[tuple[float, int]]: ...
    def tier(self, symbol: str) -> str: ...


class SqliteMarket:
    """Implementasi MarketData di atas data/pasar.sqlite (hanya membaca)."""

    def __init__(self, conn):
        self.conn = conn

    def bars(self, symbol, after_open_time, until_open_time):
        rows = self.conn.execute(
            """SELECT k.symbol, k.open_time, k.open, k.high, k.low, k.close, k.volume, k.quote_volume, k.trades, k.taker_buy_quote,
                      m.open AS mo, m.high AS mh, m.low AS ml, m.close AS mc
               FROM kline_1m k LEFT JOIN mark_kline_1m m ON m.symbol=k.symbol AND m.open_time=k.open_time
               WHERE k.symbol=? AND k.open_time>? AND k.open_time<=? ORDER BY k.open_time""",
            (symbol, after_open_time, until_open_time),
        ).fetchall()
        out = []
        for r in rows:
            bar = Bar(r[0], int(r[1]), r[2], r[3], r[4], r[5], r[6] or 0.0, r[7] or 0.0, int(r[8] or 0), r[9] or 0.0)
            mark = MarkBar(r[0], int(r[1]), r[10], r[11], r[12], r[13]) if r[10] is not None else None
            out.append((bar, mark))
        return out

    def bars_1h(self, symbol, after_open_time, until_open_time) -> list[Bar]:
        """Bar 1 jam (kline_1h). Catatan: Bar.close_time mengasumsikan 1m; untuk 1h pakai open_time + HOUR_MS."""
        try:
            rows = self.conn.execute(
                "SELECT symbol, open_time, open, high, low, close, volume, quote_volume, trades, taker_buy_quote FROM kline_1h "
                "WHERE symbol=? AND open_time>? AND open_time<=? ORDER BY open_time",
                (symbol, after_open_time, until_open_time),
            ).fetchall()
        except Exception:  # noqa: BLE001 - skema lama tanpa kline_1h
            return []
        return [Bar(r[0], int(r[1]), r[2], r[3], r[4], r[5], r[6] or 0.0, r[7] or 0.0, int(r[8] or 0), r[9] or 0.0) for r in rows]

    def funding_events(self, symbol, after_ms, until_ms):
        rows = self.conn.execute(
            "SELECT symbol, funding_time, rate, mark_price FROM funding_rate WHERE symbol=? AND funding_time>? AND funding_time<=? ORDER BY funding_time",
            (symbol, after_ms, until_ms),
        ).fetchall()
        return [FundingEvent(r[0], int(r[1]), float(r[2]), r[3]) for r in rows]

    def filters(self, symbol):
        r = self.conn.execute("SELECT * FROM symbol_info WHERE symbol=?", (symbol,)).fetchone()
        if r is None or r["contract_type"] != "PERPETUAL":
            return None
        return SymbolFilters(
            symbol, r["status"], D(r["tick_size"] or "0"), D(r["qty_step"] or "0"), D(r["min_qty"] or "0"),
            D(r["min_notional"] or "0"), r["pct_up"], r["pct_down"], int(r["funding_interval_h"] or 8),
        )

    def brackets(self, symbol):
        rows = self.conn.execute(
            "SELECT bracket, notional_floor, notional_cap, max_leverage, mmr, cum FROM leverage_bracket WHERE symbol=? ORDER BY bracket",
            (symbol,),
        ).fetchall()
        return [Bracket(int(r[0]), r[1] or 0.0, r[2] or 0.0, int(r[3] or 0), float(r[4] or 0), float(r[5] or 0)) for r in rows]

    def last_mark(self, symbol):
        r = self.conn.execute("SELECT mark, ts FROM mark_snapshot WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)).fetchone()
        if r is None or r[0] is None:
            r2 = self.conn.execute("SELECT close, open_time FROM mark_kline_1m WHERE symbol=? ORDER BY open_time DESC LIMIT 1", (symbol,)).fetchone()
            return (float(r2[0]), int(r2[1]) + MINUTE_MS) if r2 else None
        return float(r[0]), int(r[1])

    def tier(self, symbol):
        r = self.conn.execute(
            "SELECT rank FROM ticker_24h WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)
        ).fetchone()
        return C.tier_for(symbol, int(r[0]) if r else None)


# --------------------------------------------------------------------------- fungsi murni
def liq_price(side: str, qty: float, entry: float, margin: float, mmr: float, cum: float = 0.0) -> float:
    """Harga likuidasi isolated (rumus Binance one-way). LONG di bawah entry, SHORT di atas."""
    if qty <= 0:
        return 0.0
    if side == LONG:
        return (qty * entry - margin - cum) / (qty * (1.0 - mmr))
    return (qty * entry + margin + cum) / (qty * (1.0 + mmr))


def pick_bracket(brackets: list[Bracket], notional: float) -> Optional[Bracket]:
    if not brackets:
        return None
    for b in sorted(brackets, key=lambda x: x.bracket):
        if notional <= b.notional_cap or b.notional_cap <= 0:
            return b
    return sorted(brackets, key=lambda x: x.bracket)[-1]


def fee_amount(notional: float, is_maker: bool, cfg: EngineConfig) -> float:
    return abs(notional) * (cfg.fee_maker if is_maker else cfg.fee_taker)


def size_for_margin(price: float, leverage: int, margin_max: float, f: SymbolFilters) -> Optional[Decimal]:
    """Qty terbesar (kelipatan step) yang marginnya ≤ margin_max. None jika di bawah minimum."""
    qty = C.round_step(D(margin_max) * leverage / D(price), f.qty_step, "down")
    if qty < f.min_qty or qty * D(price) < f.min_notional:
        return None
    return qty


def limit_fill(is_buy: bool, price: float, bar: Bar) -> Optional[tuple[float, str]]:
    """Limit terisi hanya jika harga menembus level: GAP_OPEN (di open) atau THROUGH (di level)."""
    if is_buy:
        if bar.open < price:
            return bar.open, "GAP_OPEN"
        if bar.low < price:
            return price, "THROUGH"
        return None
    if bar.open > price:
        return bar.open, "GAP_OPEN"
    if bar.high > price:
        return price, "THROUGH"
    return None


def stop_trigger(pos_side: str, stop: float, mark: MarkBar, bar: Bar, slip: float) -> Optional[tuple[float, str]]:
    """Stop-market keluar: trigger di mark price, isi di harga stop/open ± slippage (taker)."""
    if pos_side == LONG:  # keluar = jual, stop di bawah
        if mark.open <= stop:
            return bar.open * (1 - slip), "STOP_GAP"
        if mark.low <= stop:
            return stop * (1 - slip), "STOP_TRIGGER"
        return None
    if mark.open >= stop:
        return bar.open * (1 + slip), "STOP_GAP"
    if mark.high >= stop:
        return stop * (1 + slip), "STOP_TRIGGER"
    return None


def liq_hit(side: str, liq: float, mark: MarkBar) -> bool:
    return mark.low <= liq if side == LONG else mark.high >= liq


# --------------------------------------------------------------------------- request/result
@dataclass
class OrderRequest:
    account: str
    symbol: str
    side: str                       # LONG | SHORT (arah posisi)
    qty: float
    leverage: int
    type: str = "LIMIT"             # LIMIT | MARKET
    price: Optional[float] = None
    reduce_only: bool = False
    position_id: Optional[int] = None
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    post_only: bool = True
    expire_ts: Optional[int] = None
    plan_id: Optional[str] = None
    pattern: Optional[str] = None
    note: Optional[str] = None
    created_by: str = "cli"
    shadow_of: Optional[int] = None    # order tiket asal (akun acak)
    tp_pct: Optional[float] = None     # jarak TP relatif terhadap entry (akun acak; diresolusi saat terisi)
    sl_pct: Optional[float] = None


@dataclass
class OrderResult:
    ok: bool
    order_id: Optional[int] = None
    status: str = "REJECTED"
    reject_code: Optional[str] = None
    reject_reason: Optional[str] = None
    margin_usdt: Optional[float] = None
    notional: Optional[float] = None
    est_liq_price: Optional[float] = None
    est_fee_in: Optional[float] = None
    leverage_max: Optional[int] = None
    activate_ts: Optional[int] = None
    expire_ts: Optional[int] = None
    shadow_order_id: Optional[int] = None

    def __str__(self) -> str:
        if self.ok:
            return (f"OK order #{self.order_id} ({self.status}); margin ${self.margin_usdt:.4f}, notional ${self.notional:.2f}, "
                    f"fee masuk ≈ ${self.est_fee_in:.4f}, est. likuidasi {self.est_liq_price:.6g}, "
                    f"aktif {fmt_wib(self.activate_ts)}, kedaluwarsa {fmt_wib(self.expire_ts) if self.expire_ts else '-'}")
        return f"DITOLAK [{self.reject_code}] {self.reject_reason}"


class Reject(Exception):
    def __init__(self, code: str, reason: str):
        super().__init__(f"[{code}] {reason}")
        self.code = code
        self.reason = reason


# --------------------------------------------------------------------------- mesin
class PaperEngine:
    def __init__(self, conn, market: MarketData, clock: Optional[Callable[[], int]] = None,
                 cfg: Optional[EngineConfig] = None, log: Optional[logging.Logger] = None):
        self.conn = conn
        self.market = market
        self.clock = clock or now_ms
        self.cfg = cfg or EngineConfig()
        self.log = log or logging.getLogger("paper_engine")
        init_schema(conn, C.SCRIPTS_DIR / "schema_paper.sql", SCHEMA_VERSION)
        self._migrate()
        if meta_get(conn, "created_ts") is None:
            with tx(conn):
                meta_set(conn, "created_ts", self.clock())

    def _migrate(self) -> None:
        """Kolom baru pada DB lama (CREATE TABLE IF NOT EXISTS tidak menambah kolom)."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(orders)")}
        acols = {r[1] for r in self.conn.execute("PRAGMA table_info(account)")}
        with tx(self.conn):
            for col in ("tp_pct", "sl_pct"):
                if col not in cols:
                    self.conn.execute(f"ALTER TABLE orders ADD COLUMN {col} REAL")
            if "status" not in acols:
                self.conn.execute("ALTER TABLE account ADD COLUMN status TEXT DEFAULT 'aktif'")
            self.conn.execute("INSERT OR IGNORE INTO account(name, kind, budget_rule, budget_usdt) VALUES('acak','acak','daily_total',?)", (self.cfg.acak_budget,))
            for nm in ("fade", "breakout", "rentang"):
                self.conn.execute("INSERT OR IGNORE INTO account(name, kind, budget_rule, budget_usdt) VALUES(?, 'tiket', 'daily_total', ?)", (nm, self.cfg.tiket_budget))
        self._accounts: dict = {}
        self._load_accounts()

    def _load_accounts(self) -> None:
        self._accounts = {r[0]: {"kind": r[1], "budget": float(r[2] or 0), "status": r[3] or "aktif"}
                          for r in self.conn.execute("SELECT name, kind, budget_usdt, COALESCE(status,'aktif') FROM account")}

    # ---- akun (arena)
    def accounts(self, kind: Optional[str] = None, aktif_saja: bool = False) -> list[str]:
        out = [n for n, a in self._accounts.items() if (kind is None or a["kind"] == kind) and (not aktif_saja or a["status"] == "aktif")]
        urut = {"tiket": 0, "acak": 1, "swing": 2}
        return sorted(out, key=lambda n: (urut.get(self._accounts[n]["kind"], 9), n != TIKET, n))

    def kind(self, account: str) -> Optional[str]:
        a = self._accounts.get(account)
        return a["kind"] if a else None

    def is_daily(self, account: str) -> bool:
        return self.kind(account) in DAILY_KINDS

    def account_info(self, account: str) -> Optional[dict]:
        a = self._accounts.get(account)
        return dict(a, name=account) if a else None

    def set_account_status(self, account: str, status: str, alasan: str = "") -> bool:
        """Hanya lewat CLI/skrip evaluasi (arena). pensiun = tidak boleh buka order baru; posisi yang ada tetap diproses."""
        if status not in ("aktif", "pensiun") or self.kind(account) != "tiket":
            return False
        with tx(self.conn):
            self.conn.execute("UPDATE account SET status=? WHERE name=?", (status, account))
            self.event("INFO", "AKUN_STATUS", f"{account} → {status}{(' (' + alasan + ')') if alasan else ''}", ts=self.clock())
        self._load_accounts()
        return True

    # ---- util
    def event(self, level: str, type_: str, msg: str, position_id=None, order_id=None, ts=None) -> None:
        self.conn.execute(
            "INSERT INTO events(ts, level, type, position_id, order_id, msg) VALUES(?,?,?,?,?,?)",
            (ts if ts is not None else self.clock(), level, type_, position_id, order_id, msg),
        )
        getattr(self.log, level.lower(), self.log.info)("%s pos=%s ord=%s %s", type_, position_id, order_id, msg)

    def _ledger(self, ts: int, account: str, kind: str, amount: float, ref_table: str, ref_id: int) -> None:
        self.conn.execute(
            "INSERT INTO ledger(ts, day_wib, account, kind, amount, ref_table, ref_id) VALUES(?,?,?,?,?,?,?)",
            (ts, day_wib(ts), account, kind, amount, ref_table, ref_id),
        )

    def slip(self, symbol: str) -> float:
        return self.cfg.slippage.get(self.market.tier(symbol), self.cfg.slippage["small"])

    def eod_ms(self, ms: int) -> int:
        return wib_clock_ms(ms, self.cfg.tiket_eod_wib)

    # ---- query
    def cursor_for(self, symbol: str) -> Optional[int]:
        r = self.conn.execute("SELECT last_open_time FROM cursor WHERE symbol=?", (symbol,)).fetchone()
        return int(r[0]) if r else None

    def has_exposure(self, symbol: str) -> bool:
        """Ada posisi terbuka atau order hidup untuk simbol ini (revisi bar jadi berarti)."""
        return self.conn.execute(
            "SELECT 1 FROM positions WHERE symbol=? AND status='OPEN' "
            "UNION SELECT 1 FROM orders WHERE symbol=? AND status IN ('NEW','ACTIVE') LIMIT 1",
            (symbol, symbol),
        ).fetchone() is not None

    def active_symbols(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT symbol FROM positions WHERE status='OPEN' UNION SELECT symbol FROM orders WHERE status IN ('NEW','ACTIVE')"
        ).fetchall()
        return sorted(r[0] for r in rows)

    def protected_ranges(self) -> list[tuple[str, int, int]]:
        now = self.clock()
        return [
            (r[0], int(r[1]), int(r[2]) if r[2] else now)
            for r in self.conn.execute("SELECT symbol, opened_ts, closed_ts FROM positions")
        ]

    def positions(self, account: Optional[str] = None, status: str = "OPEN") -> list[dict]:
        q = "SELECT * FROM positions WHERE status=?"
        p: list = [status]
        if account:
            q += " AND account=?"
            p.append(account)
        out = []
        for r in self.conn.execute(q + " ORDER BY id", p):
            d = dict(r)
            lm = self.market.last_mark(d["symbol"])
            if status == "OPEN" and lm:
                mark, ts = lm
                sign = 1 if d["side"] == LONG else -1
                d["mark"] = mark
                d["mark_ts"] = ts
                d["unrealized"] = (mark - d["entry_price"]) * d["qty"] * sign
                d["liq_dist_pct"] = (mark - d["liq_price"]) / mark * 100 * sign
            out.append(d)
        return out

    def orders(self, account: Optional[str] = None, status: Iterable[str] = ("NEW", "ACTIVE")) -> list[dict]:
        st = tuple(status)
        q = f"SELECT * FROM orders WHERE status IN ({','.join('?' * len(st))})"
        p: list = list(st)
        if account:
            q += " AND account=?"
            p.append(account)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id", p)]

    def history(self, day: Optional[str] = None, account: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Posisi yang ditutup + order entry yang EXPIRED/REJECTED/CANCELED pada hari WIB tertentu (default hari ini)."""
        day = day or day_wib(self.clock())
        out: list[dict] = []
        q = "SELECT * FROM positions WHERE status='CLOSED' AND day_wib=?"
        p: list = [day]
        if account:
            q += " AND account=?"
            p.append(account)
        for r in self.conn.execute(q + " ORDER BY id DESC LIMIT ?", p + [limit]):
            d = dict(r)
            d["jenis"] = "posisi"
            out.append(d)
        q = "SELECT * FROM orders WHERE reduce_only=0 AND status IN ('EXPIRED','REJECTED','CANCELED') AND day_wib=?"
        p = [day]
        if account:
            q += " AND account=?"
            p.append(account)
        for r in self.conn.execute(q + " ORDER BY id DESC LIMIT ?", p + [limit]):
            d = dict(r)
            d["jenis"] = "order"
            out.append(d)
        return out

    def hangus_beruntun(self, day: Optional[str] = None, account: str = TIKET) -> int:
        """Jumlah posisi akun yang ditutup HANGUS/FUNDING_LIQ berturut-turut di akhir hari WIB `day` (playbook P-09)."""
        day = day or day_wib(self.clock())
        rows = self.conn.execute("SELECT close_reason FROM positions WHERE account=? AND day_wib=? AND status='CLOSED' ORDER BY closed_ts DESC, id DESC",
                                 (account, day)).fetchall()
        n = 0
        for r in rows:
            if r[0] in ("HANGUS", "FUNDING_LIQ"):
                n += 1
            else:
                break
        return n

    def budget_status(self, account: str = TIKET, day: Optional[str] = None) -> dict:
        day = day or day_wib(self.clock())
        if self.is_daily(account):
            info = self._accounts[account]
            total = self.cfg.acak_budget if info["kind"] == "acak" else (info["budget"] or self.cfg.tiket_budget)
            out = budget_harian(self.conn, account, day, total, self.cfg.tiket_min_saldo, self.cfg.tiket_max_per_order)
            out["kind"], out["status"] = info["kind"], info["status"]
            if info["status"] != "aktif":
                out["boleh_buka"] = False
            return out
        n_open = self.conn.execute("SELECT COUNT(*) FROM positions WHERE account='swing' AND status='OPEN'").fetchone()[0]
        n_pending = self.conn.execute(
            "SELECT COUNT(*) FROM orders WHERE account='swing' AND reduce_only=0 AND status IN ('NEW','ACTIVE')"
        ).fetchone()[0]
        return {"account": SWING, "margin_per_trade": self.cfg.swing_margin, "open": n_open, "pending": n_pending,
                "max_open": self.cfg.swing_max_open}

    # ---- validasi
    def _validate(self, req: OrderRequest, now: int) -> dict:
        if req.account not in self._accounts:
            raise Reject("ACCOUNT", f"akun '{req.account}' tidak dikenal; akun tiket: {', '.join(self.accounts('tiket'))}; swing; acak")
        if self._accounts[req.account]["status"] != "aktif" and req.shadow_of is None:
            raise Reject("ACCOUNT_PENSIUN", f"akun '{req.account}' berstatus pensiun (arena); hidupkan lagi lewat `paper_engine.py akun aktif {req.account}`")
        if self.kind(req.account) == "acak":
            if req.shadow_of is None or req.type != "MARKET":
                raise Reject("ACCOUNT", "akun acak hanya untuk bayangan mesin (MARKET, shadow_of)")
            for label, pct in (("tp_pct", req.tp_pct), ("sl_pct", req.sl_pct)):
                if pct is not None and not (0 < pct < 0.5):
                    raise Reject("BAD_PCT", f"{label} {pct} di luar (0, 0.5)")
        if req.side not in (LONG, SHORT):
            raise Reject("SIDE", "sisi harus LONG atau SHORT")
        if req.type not in ENTRY_TYPES:
            raise Reject("TYPE", "tipe order entry harus LIMIT atau MARKET")
        f = self.market.filters(req.symbol)
        if f is None or f.status != "TRADING":
            raise Reject("SYMBOL_UNAVAILABLE", f"{req.symbol} tidak ada / tidak TRADING / bukan perpetual USDT")
        brackets = self.market.brackets(req.symbol)
        if not brackets:
            raise Reject("LEVERAGE_UNKNOWN", f"bracket leverage {req.symbol} tidak tersedia; cek di aplikasi Binance")
        lm = self.market.last_mark(req.symbol)
        ref_price = req.price if req.type == "LIMIT" and req.price else (lm[0] if lm else None)
        if ref_price is None or ref_price <= 0:
            raise Reject("NO_PRICE", "tidak ada harga referensi (mark) untuk simbol ini")
        qty = D(req.qty)
        if qty <= 0 or not is_multiple(qty, f.qty_step):
            raise Reject("QTY_STEP", f"qty {C.fmt_dec(qty)} bukan kelipatan step {C.fmt_dec(f.qty_step)}")
        if qty < f.min_qty:
            raise Reject("MIN_QTY", f"qty {C.fmt_dec(qty)} < minimum {C.fmt_dec(f.min_qty)}")
        notional = float(qty) * float(ref_price)
        if D(notional) < f.min_notional:
            raise Reject("MIN_NOTIONAL", f"notional ${notional:.2f} < minimum ${C.fmt_dec(f.min_notional)}")
        if req.type == "LIMIT":
            if req.price is None or req.price <= 0 or not is_multiple(D(req.price), f.tick_size):
                raise Reject("TICK_SIZE", f"harga limit harus kelipatan tick {C.fmt_dec(f.tick_size)}")
        for label, px in (("TP", req.tp_price), ("SL", req.sl_price)):
            if px is not None and (px <= 0 or not is_multiple(D(px), f.tick_size)):
                raise Reject("TICK_SIZE", f"harga {label} harus kelipatan tick {C.fmt_dec(f.tick_size)}")
        if lm and req.type == "LIMIT" and f.pct_up and f.pct_down:
            if req.price > lm[0] * f.pct_up or req.price < lm[0] * f.pct_down:
                raise Reject("PRICE_BAND", f"harga limit di luar batas {f.pct_down:.0%}–{f.pct_up:.0%} dari mark {lm[0]}")
        if lm and req.type == "LIMIT" and req.post_only:
            if (req.side == LONG and req.price >= lm[0]) or (req.side == SHORT and req.price <= lm[0]):
                raise Reject("LIMIT_CROSSES", f"limit {req.price} memotong mark {lm[0]}; post-only ditolak (pakai --market untuk taker)")
        b = pick_bracket(brackets, notional)
        assert b is not None
        if req.leverage < 1 or req.leverage > b.max_leverage:
            raise Reject("LEVERAGE_CAP", f"leverage {req.leverage}x di luar 1–{b.max_leverage}x untuk notional ${notional:.0f}")
        margin = notional / req.leverage
        is_maker = req.type == "LIMIT"
        fee_in = fee_amount(notional, is_maker, self.cfg)
        est_liq = liq_price(req.side, float(qty), float(ref_price), margin, b.mmr, b.cum)
        # TP/SL arah
        if req.tp_price is not None and ((req.side == LONG and req.tp_price <= ref_price) or (req.side == SHORT and req.tp_price >= ref_price)):
            raise Reject("BAD_TP", "TP harus di arah untung dari entry")
        if req.sl_price is not None:
            if (req.side == LONG and req.sl_price >= ref_price) or (req.side == SHORT and req.sl_price <= ref_price):
                raise Reject("BAD_SL", "SL harus di arah rugi dari entry")
            if (req.side == LONG and est_liq >= req.sl_price) or (req.side == SHORT and est_liq <= req.sl_price):
                raise Reject("LIQ_INSIDE_STOP", f"likuidasi ≈ {est_liq:.6g} tercapai sebelum SL {req.sl_price}")
        # budget per akun
        if self.is_daily(req.account):
            tag = "ACAK" if self.kind(req.account) == "acak" else "TIKET"
            if now >= self.eod_ms(now):
                raise Reject(f"{tag}_EOD", f"sudah lewat jam tutup tiket {self.cfg.tiket_eod_wib} WIB")
            bs = self.budget_status(req.account, day_wib(now))
            need = margin + (fee_in if self.cfg.tiket_fee_from_budget else 0.0)
            if not bs["boleh_buka"]:
                raise Reject(f"BUDGET_{tag}", f"saldo {req.account} hari ini ${bs['saldo']:.4f} < minimum ${bs['min_saldo']:.2f}; tidak ada tiket baru sampai besok")
            if need > bs["max_per_order"] + 1e-9:
                raise Reject(f"BUDGET_{tag}", f"butuh ${need:.4f} > maksimum per tiket ${bs['max_per_order']:.2f}")
            if need > bs["remaining"] + 1e-9:
                raise Reject(f"BUDGET_{tag}", f"butuh ${need:.4f} (margin {margin:.4f} + fee {fee_in:.4f}), sisa saldo {req.account} hari ini ${bs['remaining']:.4f}")
        else:
            if margin > self.cfg.swing_margin + 1e-9:
                raise Reject("BUDGET_SWING", f"margin ${margin:.2f} > ${self.cfg.swing_margin:.2f} per trade")
            bs = self.budget_status(SWING)
            if bs["open"] + bs["pending"] >= self.cfg.swing_max_open:
                raise Reject("SWING_MAX_OPEN", f"sudah {bs['open']} posisi + {bs['pending']} order swing (maks {self.cfg.swing_max_open})")
            if req.sl_price is None or req.tp_price is None:
                raise Reject("SWING_NEEDS_SL_TP", "swing wajib punya --sl dan --tp")
            buf = self.cfg.swing_liq_buffer
            if (req.side == LONG and est_liq > req.sl_price * (1 - buf)) or (req.side == SHORT and est_liq < req.sl_price * (1 + buf)):
                raise Reject("LIQ_INSIDE_STOP", f"likuidasi ≈ {est_liq:.6g} terlalu dekat dengan SL (buffer {buf:.1%})")
            reward = abs(req.tp_price - ref_price) * float(qty) - fee_in - fee_amount(req.tp_price * float(qty), True, self.cfg)
            risk = abs(ref_price - req.sl_price) * float(qty) + fee_in + fee_amount(req.sl_price * float(qty), False, self.cfg)
            rr = reward / risk if risk > 0 else 0.0
            if rr < self.cfg.swing_min_rr:
                raise Reject("RR_TOO_LOW", f"R:R setelah fee {rr:.2f} < {self.cfg.swing_min_rr}")
        return {"filters": f, "bracket": b, "ref_price": float(ref_price), "qty": float(qty), "notional": notional,
                "margin": margin, "fee_in": fee_in, "est_liq": est_liq}

    # ---- perintah
    def place_order(self, req: OrderRequest) -> OrderResult:
        now = self.clock()
        try:
            v = self._validate(req, now)
        except Reject as e:
            with tx(self.conn):
                self.conn.execute(
                    "INSERT INTO orders(account,symbol,side,type,reduce_only,price,qty,leverage,tp_price,sl_price,post_only,status,reject_code,reject_reason,"
                    "plan_id,pattern,note,created_by,created_ts,day_wib,done_ts) VALUES(?,?,?,?,0,?,?,?,?,?,?,'REJECTED',?,?,?,?,?,?,?,?,?)",
                    (req.account, req.symbol, req.side, req.type, req.price, req.qty, req.leverage, req.tp_price, req.sl_price,
                     int(req.post_only), e.code, e.reason, req.plan_id, req.pattern, req.note, req.created_by, now, day_wib(now), now),
                )
            return OrderResult(ok=False, reject_code=e.code, reject_reason=e.reason, est_liq_price=None)
        activate = ceil_minute(now)
        if req.expire_ts is not None:
            expire = req.expire_ts
        elif self.is_daily(req.account):
            expire = self.eod_ms(now)
        else:
            expire = now + self.cfg.swing_entry_ttl_h * C.HOUR_MS
        fee_reserved = v["fee_in"] if (self.is_daily(req.account) and self.cfg.tiket_fee_from_budget) else 0.0
        with tx(self.conn):
            cur = self.conn.execute(
                "INSERT INTO orders(account,symbol,side,type,reduce_only,price,qty,leverage,margin_usdt,notional,fee_reserved,tp_price,sl_price,post_only,"
                "tp_pct,sl_pct,status,plan_id,pattern,note,created_by,created_ts,activate_ts,expire_ts,day_wib) "
                "VALUES(?,?,?,?,0,?,?,?,?,?,?,?,?,?,?,?,'NEW',?,?,?,?,?,?,?,?)",
                (req.account, req.symbol, req.side, req.type, req.price, v["qty"], req.leverage, v["margin"], v["notional"], fee_reserved,
                 req.tp_price, req.sl_price, int(req.post_only), req.tp_pct, req.sl_pct, req.plan_id, req.pattern, req.note, req.created_by, now, activate, expire, day_wib(now)),
            )
            oid = cur.lastrowid
            self._ledger(now, req.account, "MARGIN_LOCK", -(v["margin"] + fee_reserved), "orders", oid)
            self.event("INFO", "ORDER_NEW", f"{req.account} {req.symbol} {req.side} {req.type} qty {v['qty']} @ {req.price or 'MARKET'} lev {req.leverage}x", order_id=oid, ts=now)
        shadow_id = None
        if self.kind(req.account) == "tiket" and req.shadow_of is None and req.created_by != "engine" and self.cfg.acak_enabled:
            shadow_id = self._shadow_acak(req, oid, v, now)
        return OrderResult(ok=True, order_id=oid, status="NEW", margin_usdt=v["margin"], notional=v["notional"],
                           est_liq_price=v["est_liq"], est_fee_in=v["fee_in"], leverage_max=v["bracket"].max_leverage,
                           activate_ts=activate, expire_ts=expire, shadow_order_id=shadow_id)

    def _shadow_acak(self, req: OrderRequest, oid: int, v: dict, now: int) -> Optional[int]:
        """Bayangan acak (§19.7): simbol, leverage, qty, jarak TP/SL sama; sisi acak; entry market di open bar berikutnya.
        Kegagalan apa pun hanya dicatat sebagai event ACAK_SKIP; order asli tidak terpengaruh."""
        side = random.Random(f"{self.cfg.acak_seed}:{oid}").choice((LONG, SHORT))
        ref = v["ref_price"]
        tp_pct = abs(req.tp_price - ref) / ref if req.tp_price else None
        sl_pct = abs(req.sl_price - ref) / ref if req.sl_price else None
        sreq = OrderRequest(account=ACAK, symbol=req.symbol, side=side, qty=req.qty, leverage=req.leverage, type="MARKET", post_only=False,
                            tp_pct=tp_pct, sl_pct=sl_pct, plan_id=f"ACAK:{oid}", pattern=req.pattern,
                            note=f"bayangan acak dari order #{oid}; seed {self.cfg.acak_seed}", created_by="engine", shadow_of=oid)
        try:
            res = self.place_order(sreq)
        except Exception as e:  # noqa: BLE001 - bayangan tidak boleh menggagalkan order asli
            with tx(self.conn):
                self.event("WARNING", "ACAK_SKIP", f"{type(e).__name__}: {e}", order_id=oid, ts=now)
            return None
        with tx(self.conn):
            if res.ok:
                self.event("INFO", "ACAK_SHADOW", f"order #{res.order_id} {side} MARKET {req.symbol} lev {req.leverage}x untuk order #{oid}", order_id=oid, ts=now)
            else:
                self.event("WARNING", "ACAK_SKIP", f"[{res.reject_code}] {res.reject_reason}", order_id=oid, ts=now)
        return res.order_id if res.ok else None

    def cancel_order(self, order_id: int, who: str = "cli") -> bool:
        now = self.clock()
        with tx(self.conn):
            r = self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if r is None or r["status"] not in ("NEW", "ACTIVE") or r["reduce_only"]:
                return False
            self.conn.execute("UPDATE orders SET status='CANCELED', done_ts=?, note=COALESCE(note,'')||? WHERE id=?",
                              (now, f" [dibatalkan oleh {who}]", order_id))
            self._ledger(now, r["account"], "MARGIN_RELEASE", (r["margin_usdt"] or 0) + (r["fee_reserved"] or 0), "orders", order_id)
            self.event("INFO", "ORDER_CANCEL", f"oleh {who}", order_id=order_id, ts=now)
            # bayangan acak yang belum terisi ikut dibatalkan supaya jumlah sampel sebanding
            for s in self.conn.execute("SELECT * FROM orders WHERE plan_id=? AND status IN ('NEW','ACTIVE') AND reduce_only=0", (f"ACAK:{order_id}",)).fetchall():
                self.conn.execute("UPDATE orders SET status='CANCELED', done_ts=?, note=COALESCE(note,'')||' [ikut order asli]' WHERE id=?", (now, s["id"]))
                self._ledger(now, s["account"], "MARGIN_RELEASE", (s["margin_usdt"] or 0) + (s["fee_reserved"] or 0), "orders", s["id"])
                self.event("INFO", "ORDER_CANCEL", f"ikut order asli #{order_id}", order_id=s["id"], ts=now)
        return True

    def close_position_request(self, position_id: int, who: str = "cli") -> bool:
        """Minta tutup manual: dieksekusi market di open bar berikutnya (taker + slippage)."""
        now = self.clock()
        with tx(self.conn):
            p = self.conn.execute("SELECT * FROM positions WHERE id=? AND status='OPEN'", (position_id,)).fetchone()
            if p is None:
                return False
            exists = self.conn.execute(
                "SELECT 1 FROM orders WHERE position_id=? AND type='MARKET' AND reduce_only=1 AND status IN ('NEW','ACTIVE')", (position_id,)
            ).fetchone()
            if exists:
                return True
            self.conn.execute(
                "INSERT INTO orders(account,symbol,side,type,reduce_only,qty,leverage,status,position_id,created_by,created_ts,activate_ts,day_wib) "
                "VALUES(?,?,?,'MARKET',1,?,?,'NEW',?,?,?,?,?)",
                (p["account"], p["symbol"], p["side"], p["qty"], p["leverage"], position_id, who, now, ceil_minute(now), day_wib(now)),
            )
            self.event("INFO", "CLOSE_REQUEST", f"oleh {who}", position_id=position_id, ts=now)
        return True

    # ---- pemrosesan
    def step(self, until_ms: Optional[int] = None) -> dict:
        now = until_ms if until_ms is not None else self.clock()
        last_closed = floor_minute(now - self.cfg.bar_grace_ms) - MINUTE_MS
        symbols = self.active_symbols()
        rep = {"bars": 0, "fills": 0, "closes": 0, "until": last_closed, "symbols": len(symbols)}
        if not symbols:
            return rep
        stream: list[tuple[int, str, Bar, Optional[MarkBar]]] = []
        starts: dict[str, int] = {}
        for sym in symbols:
            cur = self.cursor_for(sym)
            if cur is None:
                # mulai dari bar setelah order/posisi pertama simbol ini dibuat
                r = self.conn.execute(
                    "SELECT MIN(activate_ts) FROM orders WHERE symbol=? AND status IN ('NEW','ACTIVE')", (sym,)
                ).fetchone()
                cur = (int(r[0]) - MINUTE_MS) if r and r[0] is not None else last_closed
            starts[sym] = cur
            for bar, mark in self.market.bars(sym, cur, last_closed):
                stream.append((bar.open_time, sym, bar, mark))
        stream.sort(key=lambda x: (x[0], x[1]))
        i = 0
        while i < len(stream):
            open_time = stream[i][0]
            j = i
            with tx(self.conn):
                while j < len(stream) and stream[j][0] == open_time:
                    _, sym, bar, mark = stream[j]
                    prev = self.cursor_for(sym)
                    prev = prev if prev is not None else starts[sym]
                    r = self._process_bar(bar, mark, prev)
                    rep["bars"] += 1
                    rep["fills"] += r["fills"]
                    rep["closes"] += r["closes"]
                    self.conn.execute(
                        "INSERT INTO cursor(symbol, last_open_time) VALUES(?,?) ON CONFLICT(symbol) DO UPDATE SET last_open_time=excluded.last_open_time",
                        (sym, open_time),
                    )
                    j += 1
                self._maybe_rollover(open_time)
            i = j
        # bersihkan cursor simbol yang sudah tidak aktif
        with tx(self.conn):
            for sym in symbols:
                if sym not in self.active_symbols():
                    self.conn.execute("DELETE FROM cursor WHERE symbol=?", (sym,))
        return rep

    def replay(self, from_ms: int, to_ms: int) -> dict:
        """Memproses ulang rentang bar lewat jalur kode yang sama dengan step() (cursor-driven)."""
        return self.step(until_ms=to_ms + MINUTE_MS + self.cfg.bar_grace_ms)

    def _maybe_rollover(self, open_time: int) -> None:
        d = day_wib(open_time)
        last = meta_get(self.conn, "last_day_rolled")
        if last is None:
            meta_set(self.conn, "last_day_rolled", d)
        elif d > last:
            self.rollover_day(last)
            meta_set(self.conn, "last_day_rolled", d)

    def _process_bar(self, bar: Bar, mark: Optional[MarkBar], prev_open: int) -> dict:
        sym = bar.symbol
        ot = bar.open_time
        rep = {"fills": 0, "closes": 0}
        if mark is None:
            if not self.cfg.mark_fallback_to_last:
                return rep
            mark = MarkBar(sym, ot, bar.open, bar.high, bar.low, bar.close, source="last")
        slip = self.slip(sym)
        eod = self.eod_ms(ot)

        # 1. aktivasi / kedaluwarsa order simbol ini
        self.conn.execute("UPDATE orders SET status='ACTIVE' WHERE symbol=? AND status='NEW' AND activate_ts<=?", (sym, ot))
        for o in self.conn.execute(
            "SELECT * FROM orders WHERE symbol=? AND status IN ('NEW','ACTIVE') AND reduce_only=0 AND expire_ts IS NOT NULL AND expire_ts<=?", (sym, ot)
        ).fetchall():
            self._expire_order(o, ot)

        # 2. funding: event dengan funding_time setelah close bar sebelumnya sampai close bar ini
        for ev in self.market.funding_events(sym, prev_open + MINUTE_MS - 1, ot + MINUTE_MS - 1):
            for p in self._open_positions(sym):
                self._settle_funding(p, ev, mark, bar)
                rep["closes"] += 1 if self._is_closed(p["id"]) else 0

        # 3. posisi yang sudah ada
        for p in self._open_positions(sym):
            if p["opened_bar"] is not None and p["opened_bar"] >= ot:
                continue  # dibuka di bar ini (tidak mungkin di sini, tapi aman)
            # 3a. tutup paksa EOD / permintaan tutup manual: eksekusi di open bar
            manual = self.conn.execute(
                "SELECT * FROM orders WHERE position_id=? AND type='MARKET' AND reduce_only=1 AND status IN ('NEW','ACTIVE') AND activate_ts<=?",
                (p["id"], ot),
            ).fetchone()
            if manual is not None or (self.is_daily(p["account"]) and ot >= eod):
                reason = "MANUAL" if manual is not None else "EOD"
                px = bar.open * (1 - slip) if p["side"] == LONG else bar.open * (1 + slip)
                self._close_position(p, px, reason, False, "MARKET_OPEN", bar, order_id=manual["id"] if manual else None)
                rep["closes"] += 1
                continue
            # 3b0. pengaman breakeven (playbook P-18): tiket/acak dengan TP tanpa SL, setelah >= k x jalan ke TP tercapai
            if self.cfg.tiket_breakeven_mfe and self.is_daily(p["account"]) and p["tp_price"] and not p["sl_price"]:
                # hanya dari bar-bar SEBELUMNYA (best_mark), supaya bar yang menyentuh TP tidak keburu di-STOP oleh SL yang baru dipasang
                best = p["best_mark"]
                jarak_tp = abs(p["tp_price"] - p["entry_price"])
                tempuh = ((best - p["entry_price"]) if p["side"] == LONG else (p["entry_price"] - best)) if best is not None else 0.0
                if jarak_tp > 0 and tempuh / jarak_tp >= self.cfg.tiket_breakeven_mfe:
                    self.conn.execute("UPDATE positions SET sl_price=? WHERE id=?", (p["entry_price"], p["id"]))
                    p["sl_price"] = p["entry_price"]
                    self.event("INFO", "BREAKEVEN", f"{p['symbol']} {p['side']} menempuh {tempuh / jarak_tp:.0%} jalan ke TP {p['tp_price']:.6g}; "
                                                    f"SL dipindah ke harga masuk {p['entry_price']:.6g}", position_id=p["id"], ts=ot)
            # 3b. likuidasi (mark) → SL (mark) → TP (last)
            tp_fill = limit_fill(p["side"] == SHORT, p["tp_price"], bar) if p["tp_price"] else None
            sl_fill = stop_trigger(p["side"], p["sl_price"], mark, bar, slip) if p["sl_price"] else None
            if liq_hit(p["side"], p["liq_price"], mark):
                alt = "TP" if tp_fill else ("STOP" if sl_fill else None)
                self._liquidate(p, bar, mark, ambiguous=alt is not None, alt=alt)
                rep["closes"] += 1
                continue
            if sl_fill:
                px, rule = sl_fill
                self._close_position(p, px, "STOP", False, rule, bar, ambiguous=tp_fill is not None, alt="TP" if tp_fill else None,
                                     order_id=p["sl_order_id"])
                rep["closes"] += 1
                continue
            if tp_fill:
                px, rule = tp_fill
                self._close_position(p, px, "TP", True, rule, bar, order_id=p["tp_order_id"])
                rep["closes"] += 1
                continue
            self.conn.execute(
                "UPDATE positions SET worst_mark=CASE WHEN side='LONG' THEN MIN(COALESCE(worst_mark, ?), ?) ELSE MAX(COALESCE(worst_mark, ?), ?) END,"
                " best_mark=CASE WHEN side='LONG' THEN MAX(COALESCE(best_mark, ?), ?) ELSE MIN(COALESCE(best_mark, ?), ?) END WHERE id=?",
                (mark.low, mark.low, mark.high, mark.high, mark.high, mark.high, mark.low, mark.low, p["id"]),
            )

        # 4. order entry aktif
        for o in self.conn.execute(
            "SELECT * FROM orders WHERE symbol=? AND status='ACTIVE' AND reduce_only=0 ORDER BY id", (sym,)
        ).fetchall():
            if self.is_daily(o["account"]) and ot >= eod:
                self._expire_order(o, ot)
                continue
            fill = None
            if o["type"] == "LIMIT":
                fill = limit_fill(o["side"] == LONG, o["price"], bar)
                is_maker = True
            else:
                px = bar.open * (1 + slip) if o["side"] == LONG else bar.open * (1 - slip)
                fill = (px, "MARKET_OPEN")
                is_maker = False
            if not fill:
                continue
            px, rule = fill
            pos = self._open_position(o, px, is_maker, rule, bar, mark)
            rep["fills"] += 1
            # cek likuidasi / SL di bar yang sama (pesimis), tanpa TP
            if liq_hit(pos["side"], pos["liq_price"], mark):
                self._liquidate(pos, bar, mark, ambiguous=True, alt="OPEN")
                rep["closes"] += 1
            elif pos["sl_price"]:
                sl_fill = stop_trigger(pos["side"], pos["sl_price"], mark, bar, slip)
                if sl_fill:
                    self._close_position(pos, sl_fill[0], "STOP", False, sl_fill[1], bar, ambiguous=True, alt="OPEN", order_id=pos["sl_order_id"])
                    rep["closes"] += 1
        return rep

    # ---- helper posisi
    def _open_positions(self, symbol: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM positions WHERE symbol=? AND status='OPEN' ORDER BY id", (symbol,))]

    def _is_closed(self, position_id: int) -> bool:
        return self.conn.execute("SELECT status FROM positions WHERE id=?", (position_id,)).fetchone()[0] == "CLOSED"

    def _expire_order(self, o, ot: int) -> None:
        self.conn.execute("UPDATE orders SET status='EXPIRED', done_ts=? WHERE id=?", (ot, o["id"]))
        self._ledger(ot, o["account"], "MARGIN_RELEASE", (o["margin_usdt"] or 0) + (o["fee_reserved"] or 0), "orders", o["id"])
        self.event("INFO", "ORDER_EXPIRED", "TIDAK_TERISI", order_id=o["id"], ts=ot)

    def _open_position(self, o, px: float, is_maker: bool, rule: str, bar: Bar, mark: MarkBar) -> dict:
        ot = bar.open_time
        qty = float(o["qty"])
        notional = qty * px
        margin = notional / o["leverage"]
        b = pick_bracket(self.market.brackets(o["symbol"]), notional)
        mmr, cum, bno = (b.mmr, b.cum, b.bracket) if b else (0.0, 0.0, None)
        liq = liq_price(o["side"], qty, px, margin, mmr, cum)
        fee_in = fee_amount(notional, is_maker, self.cfg)
        ts = ot if rule in ("GAP_OPEN", "MARKET_OPEN") else ot + 30_000
        o = dict(o)
        if o.get("tp_pct") or o.get("sl_pct"):   # akun acak: jarak relatif → harga, dibulatkan menjauh dari untung / lebih ketat
            f = self.market.filters(o["symbol"])
            if f is None:
                self.event("WARNING", "ACAK_TANPA_TP", f"filter {o['symbol']} tidak tersedia; posisi tanpa TP/SL (ditutup EOD)", order_id=o["id"], ts=ts)
            else:
                long = o["side"] == LONG
                if o.get("tp_pct") and not o.get("tp_price"):
                    o["tp_price"] = float(C.round_step(D(px) * (1 + D(o["tp_pct"]) if long else 1 - D(o["tp_pct"])), f.tick_size, "down" if long else "up"))
                if o.get("sl_pct") and not o.get("sl_price"):
                    o["sl_price"] = float(C.round_step(D(px) * (1 - D(o["sl_pct"]) if long else 1 + D(o["sl_pct"])), f.tick_size, "up" if long else "down"))
        cur = self.conn.execute(
            "INSERT INTO positions(account,symbol,side,qty,entry_price,leverage,margin_initial,margin_now,notional_entry,mmr,cum,bracket,liq_price,"
            "tp_price,sl_price,entry_order_id,plan_id,pattern,day_wib,opened_ts,opened_bar,fees_total,funding_total,worst_mark,best_mark,status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,'OPEN')",
            (o["account"], o["symbol"], o["side"], qty, px, o["leverage"], margin, margin, notional, mmr, cum, bno, liq,
             o["tp_price"], o["sl_price"], o["id"], o["plan_id"], o["pattern"], o["day_wib"] or day_wib(ts), ts, ot, fee_in,
             mark.low if o["side"] == LONG else mark.high, mark.high if o["side"] == LONG else mark.low),
        )
        pid = cur.lastrowid
        self.conn.execute(
            "INSERT INTO fills(order_id,position_id,ts,bar_open_time,price,qty,notional,fee_usdt,is_maker,role,rule) VALUES(?,?,?,?,?,?,?,?,?,'ENTRY',?)",
            (o["id"], pid, ts, ot, px, qty, notional, fee_in, int(is_maker), rule),
        )
        self.conn.execute("UPDATE orders SET status='FILLED', position_id=?, done_ts=? WHERE id=?", (pid, ts, o["id"]))
        # margin: lepas reservasi order, kunci margin posisi (selisih harga isi vs harga order)
        reserved = (o["margin_usdt"] or 0) + (o["fee_reserved"] or 0)
        self._ledger(ts, o["account"], "MARGIN_RELEASE", reserved, "orders", o["id"])
        self._ledger(ts, o["account"], "MARGIN_LOCK", -margin, "positions", pid)
        self._ledger(ts, o["account"], "FEE", -fee_in, "fills", self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        tp_id = sl_id = None
        if o["tp_price"]:
            tp_id = self.conn.execute(
                "INSERT INTO orders(account,symbol,side,type,reduce_only,price,qty,leverage,post_only,status,position_id,oco_group,created_by,created_ts,activate_ts,day_wib) "
                "VALUES(?,?,?,'LIMIT',1,?,?,?,1,'ACTIVE',?,?,'engine',?,?,?)",
                (o["account"], o["symbol"], o["side"], o["tp_price"], qty, o["leverage"], pid, pid, ts, ot + MINUTE_MS, day_wib(ts)),
            ).lastrowid
        if o["sl_price"]:
            sl_id = self.conn.execute(
                "INSERT INTO orders(account,symbol,side,type,reduce_only,stop_price,qty,leverage,post_only,status,position_id,oco_group,created_by,created_ts,activate_ts,day_wib) "
                "VALUES(?,?,?,'STOP_MARKET',1,?,?,?,0,'ACTIVE',?,?,'engine',?,?,?)",
                (o["account"], o["symbol"], o["side"], o["sl_price"], qty, o["leverage"], pid, pid, ts, ot, day_wib(ts)),
            ).lastrowid
        self.conn.execute("UPDATE positions SET tp_order_id=?, sl_order_id=? WHERE id=?", (tp_id, sl_id, pid))
        self.event("INFO", "OPEN", f"{o['symbol']} {o['side']} qty {qty} @ {px:.6g} ({rule}) lev {o['leverage']}x margin ${margin:.4f} liq {liq:.6g}", position_id=pid, order_id=o["id"], ts=ts)
        return dict(self.conn.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone())

    def _settle_funding(self, p: dict, ev: FundingEvent, mark: MarkBar, bar: Bar) -> None:
        mp = ev.mark_price if ev.mark_price else mark.open
        notional = p["qty"] * mp
        sign = 1 if p["side"] == LONG else -1
        amount = -sign * notional * ev.rate          # long membayar saat rate > 0
        margin_after = p["margin_now"] + amount
        liq_after = liq_price(p["side"], p["qty"], p["entry_price"], margin_after, p["mmr"], p["cum"])
        self.conn.execute(
            "INSERT INTO funding_payments(position_id,funding_time,rate,mark_price,notional,amount_usdt,margin_after,liq_after) VALUES(?,?,?,?,?,?,?,?)",
            (p["id"], ev.funding_time, ev.rate, mp, notional, amount, margin_after, liq_after),
        )
        self.conn.execute("UPDATE positions SET margin_now=?, liq_price=?, funding_total=funding_total+? WHERE id=?",
                          (margin_after, liq_after, amount, p["id"]))
        self._ledger(ev.funding_time, p["account"], "FUNDING", amount, "positions", p["id"])
        p["margin_now"], p["liq_price"], p["funding_total"] = margin_after, liq_after, p["funding_total"] + amount
        maint = notional * p["mmr"] - p["cum"]
        if margin_after <= maint or margin_after <= 0:
            self._liquidate(p, bar, mark, reason="FUNDING_LIQ", note=f"funding {amount:+.4f} membuat margin {margin_after:.4f} ≤ maintenance {maint:.4f}")

    def _liquidate(self, p: dict, bar: Bar, mark: MarkBar, ambiguous: bool = False, alt: Optional[str] = None,
                   reason: str = "HANGUS", note: Optional[str] = None) -> None:
        ot = bar.open_time
        ts = ot if (mark.open <= p["liq_price"] if p["side"] == LONG else mark.open >= p["liq_price"]) else ot + 30_000
        margin_lost = max(p["margin_now"], 0.0)
        self.conn.execute(
            "INSERT INTO liquidations(position_id,ts,bar_open_time,liq_price,mark_extreme,last_extreme,margin_lost,ambiguous,alt_outcome,mark_source,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (p["id"], ts, ot, p["liq_price"], mark.low if p["side"] == LONG else mark.high, bar.low if p["side"] == LONG else bar.high,
             margin_lost, int(ambiguous), alt, mark.source, note),
        )
        self.conn.execute(
            "INSERT INTO fills(order_id,position_id,ts,bar_open_time,price,qty,notional,fee_usdt,is_maker,role,rule) VALUES(NULL,?,?,?,?,?,?,0,0,'LIQUIDATION','LIQUIDATION')",
            (p["id"], ts, ot, p["liq_price"], p["qty"], p["qty"] * p["liq_price"]),
        )
        realized = -margin_lost
        net = realized - p["fees_total"]  # funding sudah tercermin di margin_now
        self.conn.execute(
            "UPDATE positions SET status='CLOSED', closed_ts=?, closed_bar=?, close_reason=?, exit_price=?, realized_pnl=?, net_result=?, "
            "ambiguous=?, alt_outcome=?, worst_mark=?, margin_now=0 WHERE id=?",
            (ts, ot, reason, p["liq_price"], realized, net, int(ambiguous), alt, mark.low if p["side"] == LONG else mark.high, p["id"]),
        )
        self.conn.execute("UPDATE orders SET status='CANCELED', done_ts=? WHERE position_id=? AND reduce_only=1 AND status IN ('NEW','ACTIVE')", (ts, p["id"]))
        self._ledger(ts, p["account"], "LIQ_LOSS", -margin_lost, "positions", p["id"])
        self.event("WARNING" if ambiguous else "INFO", reason,
                   f"{p['symbol']} {p['side']} liq {p['liq_price']:.6g} mark {mark.low if p['side']==LONG else mark.high:.6g} rugi ${margin_lost:.4f}"
                   + (f" [AMBIGU: alternatif {alt}]" if ambiguous else "") + (f" {note}" if note else ""),
                   position_id=p["id"], ts=ts)
        p["status"] = "CLOSED"

    def _close_position(self, p: dict, px: float, reason: str, is_maker: bool, rule: str, bar: Bar,
                        ambiguous: bool = False, alt: Optional[str] = None, order_id: Optional[int] = None) -> None:
        ot = bar.open_time
        ts = ot if rule in ("GAP_OPEN", "MARKET_OPEN", "STOP_GAP") else ot + 30_000
        sign = 1 if p["side"] == LONG else -1
        realized = (px - p["entry_price"]) * p["qty"] * sign
        notional = px * p["qty"]
        fee_out = fee_amount(notional, is_maker, self.cfg)
        fees_total = p["fees_total"] + fee_out
        net = realized - fees_total + p["funding_total"]
        role = {"TP": "TP", "STOP": "SL", "MANUAL": "MARKET_EXIT", "EOD": "EOD", "DELISTED": "DELISTED"}.get(reason, reason)
        fid = self.conn.execute(
            "INSERT INTO fills(order_id,position_id,ts,bar_open_time,price,qty,notional,fee_usdt,is_maker,role,rule) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (order_id, p["id"], ts, ot, px, p["qty"], notional, fee_out, int(is_maker), role, rule),
        ).lastrowid
        self.conn.execute(
            "UPDATE positions SET status='CLOSED', closed_ts=?, closed_bar=?, close_reason=?, exit_price=?, realized_pnl=?, fees_total=?, net_result=?, "
            "ambiguous=?, alt_outcome=?, margin_now=0 WHERE id=?",
            (ts, ot, reason, px, realized, fees_total, net, int(ambiguous), alt, p["id"]),
        )
        if order_id:
            self.conn.execute("UPDATE orders SET status='FILLED', done_ts=? WHERE id=?", (ts, order_id))
        self.conn.execute("UPDATE orders SET status='CANCELED', done_ts=? WHERE position_id=? AND reduce_only=1 AND status IN ('NEW','ACTIVE')", (ts, p["id"]))
        self._ledger(ts, p["account"], "FEE", -fee_out, "fills", fid)
        self._ledger(ts, p["account"], "PNL", realized, "positions", p["id"])
        self._ledger(ts, p["account"], "MARGIN_RELEASE", p["margin_now"], "positions", p["id"])
        self.event("WARNING" if ambiguous else "INFO", reason,
                   f"{p['symbol']} {p['side']} keluar {px:.6g} ({rule}) pnl {realized:+.4f} fee {fees_total:.4f} funding {p['funding_total']:+.4f} net {net:+.4f}"
                   + (f" [AMBIGU: alternatif {alt}]" if ambiguous else ""), position_id=p["id"], ts=ts)
        p["status"] = "CLOSED"

    # ---- autopsi posisi (baca saja)
    def autopsi(self, position_id: int) -> dict:
        """Rekonstruksi mekanis satu posisi: seberapa jauh harga menempuh jalan ke TP (MFE), seberapa dekat ke likuidasi (MAE),
        kapan, berapa lama, dan apa yang terjadi — bahan evaluasi, bukan opini."""
        r = self.conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
        if r is None:
            raise ValueError(f"posisi #{position_id} tidak ada")
        p = dict(r)
        sign = 1 if p["side"] == LONG else -1
        end = p["closed_ts"] or self.clock()
        pairs = self.market.bars(p["symbol"], p["opened_ts"] - MINUTE_MS, end + MINUTE_MS)
        bars = [b for b, _ in pairs]
        marks = [m for _, m in pairs if m is not None]
        out = {"id": p["id"], "account": p["account"], "symbol": p["symbol"], "side": p["side"], "leverage": p["leverage"], "entry": p["entry_price"],
               "tp": p["tp_price"], "sl": p["sl_price"], "liq": p["liq_price"], "dibuka": fmt_wib(p["opened_ts"]),
               "ditutup": fmt_wib(p["closed_ts"]) if p["closed_ts"] else None, "durasi_menit": (end - p["opened_ts"]) // 60000,
               "hasil": p["close_reason"] or "TERBUKA", "net": p["net_result"], "n_bar": len(bars)}
        if not bars:
            out["catatan"] = "tidak ada bar 1m tersimpan untuk rentang ini (retensi / simbol tidak dipantau)"
            return out
        fav = max(bars, key=lambda b: (b.high if sign > 0 else -b.low))
        best_px = fav.high if sign > 0 else fav.low
        adv = max(marks, key=lambda m: (m.high if sign < 0 else -m.low)) if marks else None
        worst_px = (adv.high if sign < 0 else adv.low) if adv else None
        jarak_tp = abs(p["tp_price"] - p["entry_price"]) if p["tp_price"] else None
        jarak_liq = abs(p["liq_price"] - p["entry_price"]) if p["liq_price"] else None
        out["mfe"] = {"harga": best_px, "pada": fmt_wib(fav.open_time), "menit_sejak_buka": (fav.open_time - p["opened_ts"]) // 60000,
                      "persen_jalan_ke_tp": round((best_px - p["entry_price"]) * sign / jarak_tp * 100, 1) if jarak_tp else None,
                      "sisa_ke_tp": round(abs(p["tp_price"] - best_px), 8) if p["tp_price"] else None}
        out["mae"] = {"harga": worst_px, "pada": fmt_wib(adv.open_time) if adv else None,
                      "persen_jalan_ke_liq": round((p["entry_price"] - worst_px) * sign / jarak_liq * 100, 1) if (jarak_liq and worst_px is not None) else None}
        untung = sum(1 for b in bars if (b.close - p["entry_price"]) * sign > 0)
        out["menit_di_sisi_untung"] = untung
        out["menit_di_sisi_rugi"] = len(bars) - untung
        after = [b for b in bars if b.open_time > fav.open_time]
        back = next((b for b in after if (b.close - p["entry_price"]) * sign <= 0), None)
        out["kembali_ke_entry_setelah_mfe"] = fmt_wib(back.open_time) if back else None
        ev = self.conn.execute("SELECT ts, type, msg FROM events WHERE position_id=? ORDER BY id", (position_id,)).fetchall()
        out["kejadian"] = [{"ts": fmt_wib(int(e[0])), "type": e[1], "msg": e[2]} for e in ev]
        pel = []
        m = out["mfe"]["persen_jalan_ke_tp"]
        if m is not None and m >= 80 and p["close_reason"] in ("HANGUS", "FUNDING_LIQ", "EOD", "STOP"):
            pel.append(f"harga sudah menempuh {m:.0f}% jalan ke TP ({out['mfe']['menit_sejak_buka']} menit setelah buka) lalu berbalik: "
                       "TP terlalu rapat untuk dijangkau atau perlu pengaman (breakeven) setelah MFE besar")
        if out["durasi_menit"] > 180 and p["close_reason"] in ("HANGUS", "EOD"):
            pel.append(f"posisi hidup {out['durasi_menit']} menit tanpa mencapai TP: tesis intraday basi; pertimbangkan batas waktu")
        if m is not None and m < 30 and p["close_reason"] in ("HANGUS", "FUNDING_LIQ"):
            pel.append("harga hampir tidak pernah ke arah tesis: level/arah salah sejak awal, bukan soal manajemen")
        if p["close_reason"] == "TP":
            pel.append("rencana berjalan sesuai tesis")
        out["pelajaran_mekanis"] = pel or ["tidak ada pola khusus"]
        return out

    # ---- ringkasan harian / ekspor
    def day_counts(self, account: str, day: str) -> dict:
        pos = self.conn.execute("SELECT * FROM positions WHERE account=? AND day_wib=?", (account, day)).fetchall()
        closed = [p for p in pos if p["status"] == "CLOSED"]
        tt = self.conn.execute("SELECT COUNT(*) FROM orders WHERE account=? AND day_wib=? AND reduce_only=0 AND status='EXPIRED'", (account, day)).fetchone()[0]
        return {"filled_n": len(pos), "tidak_terisi_n": tt,
                "tp_n": sum(1 for p in closed if p["close_reason"] == "TP"),
                "hangus_n": sum(1 for p in closed if p["close_reason"] in ("HANGUS", "FUNDING_LIQ")),
                "other_close_n": sum(1 for p in closed if p["close_reason"] not in ("TP", "HANGUS", "FUNDING_LIQ")),
                "pnl_net": sum(p["net_result"] or 0 for p in closed)}

    def rollover_day(self, day: str) -> list[dict]:
        out = []
        for acc in self.accounts():
            pos = self.conn.execute("SELECT * FROM positions WHERE account=? AND day_wib=?", (acc, day)).fetchall()
            orders_n = self.conn.execute("SELECT COUNT(*) FROM orders WHERE account=? AND day_wib=? AND reduce_only=0 AND status!='REJECTED'", (acc, day)).fetchone()[0]
            tt = self.conn.execute("SELECT COUNT(*) FROM orders WHERE account=? AND day_wib=? AND reduce_only=0 AND status='EXPIRED'", (acc, day)).fetchone()[0]
            closed = [p for p in pos if p["status"] == "CLOSED"]
            row = {
                "day_wib": day, "account": acc, "orders_n": orders_n, "filled_n": len(pos), "tidak_terisi_n": tt,
                "tp_n": sum(1 for p in closed if p["close_reason"] == "TP"),
                "hangus_n": sum(1 for p in closed if p["close_reason"] in ("HANGUS", "FUNDING_LIQ")),
                "other_close_n": sum(1 for p in closed if p["close_reason"] not in ("TP", "HANGUS", "FUNDING_LIQ")),
                "margin_used": sum(p["margin_initial"] or 0 for p in pos),
                "fees": sum(p["fees_total"] or 0 for p in pos),
                "funding": sum(p["funding_total"] or 0 for p in pos),
                "pnl_net": sum(p["net_result"] or 0 for p in closed),
                "ambiguous_n": sum(1 for p in pos if p["ambiguous"]),
            }
            self.conn.execute(
                "INSERT OR REPLACE INTO daily_summary(day_wib,account,orders_n,filled_n,tidak_terisi_n,tp_n,hangus_n,other_close_n,margin_used,fees,funding,pnl_net,ambiguous_n) "
                "VALUES(:day_wib,:account,:orders_n,:filled_n,:tidak_terisi_n,:tp_n,:hangus_n,:other_close_n,:margin_used,:fees,:funding,:pnl_net,:ambiguous_n)",
                row,
            )
            out.append(row)
        return out

    def export_tiket_csv(self, day: str, path) -> int:
        cols = ["tanggal", "pair", "arah", "leverage", "entry", "mark_liq", "target", "exit", "hasil", "pnl_usdt", "fee_usdt",
                "durasi_menit", "rencana", "pola", "aturan_dilanggar", "emosi", "catatan"]
        rows = []
        for p in self.conn.execute("SELECT * FROM positions WHERE account='tiket' AND day_wib=? ORDER BY id", (day,)):
            hasil = {"TP": "TP", "HANGUS": "HANGUS", "FUNDING_LIQ": "HANGUS", "MANUAL": "MANUAL", "EOD": "MANUAL"}.get(p["close_reason"], p["close_reason"] or "TERBUKA")
            dur = ((p["closed_ts"] or self.clock()) - p["opened_ts"]) // 60000
            rows.append([day, p["symbol"], p["side"], p["leverage"], p["entry_price"], round(p["liq_price"], 8), p["tp_price"] or "",
                         p["exit_price"] or "", hasil, round(p["net_result"], 4) if p["net_result"] is not None else "",
                         round(p["fees_total"] or 0, 4), dur, p["plan_id"] or "", p["pattern"] or "", "", "",
                         (f"ambigu: alternatif {p['alt_outcome']}" if p["ambiguous"] else "")])
        for o in self.conn.execute("SELECT * FROM orders WHERE account='tiket' AND day_wib=? AND reduce_only=0 AND status='EXPIRED' ORDER BY id", (day,)):
            rows.append([day, o["symbol"], o["side"], o["leverage"], o["price"], "", o["tp_price"] or "", "", "TIDAK_TERISI", 0, 0, "",
                         o["plan_id"] or "", o["pattern"] or "", "", "", "limit tidak tersentuh"])
        if not rows:
            rows.append([day, "-", "-", "-", "-", "-", "-", "-", "SKIP", 0, 0, "-", "-", "-", "", "", "tidak ada tiket"])
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(cols)
            w.writerows(rows)
        return len(rows)

    def report(self, day: Optional[str] = None) -> str:
        day = day or day_wib(self.clock())
        lines = [f"# Laporan paper {day}", ""]
        bs = self.budget_status(TIKET, day)
        lines.append(f"Saldo tiket (mulai ${bs['budget']:.2f}, hasil hari ini {bs['realisasi']:+.4f}) = ${bs['saldo']:.4f} | terkunci ${bs['used']:.4f} | "
                     f"tereservasi ${bs['reserved']:.4f} | bisa dipakai ${bs['remaining']:.4f}{'' if bs['boleh_buka'] else ' | DI BAWAH MINIMUM, tidak ada tiket baru'}")
        sw = self.budget_status(SWING)
        lines.append(f"Swing: {sw['open']} posisi terbuka, {sw['pending']} order menunggu (maks {sw['max_open']}, margin ${sw['margin_per_trade']:.2f}/trade)")
        ak = self.budget_status(ACAK, day)
        lines.append(f"Acak (bayangan pembanding, dibuat mesin): terpakai ${ak['used']:.4f} | tereservasi ${ak['reserved']:.4f} | sisa ${ak['remaining']:.4f}")
        lines += ["", "## Arena hari ini (persona tiket vs acak)", "", "| akun | status | posisi | TP | HANGUS | lain | TIDAK_TERISI | net |", "|---|---|---|---|---|---|---|---|"]
        for acc in self.accounts("tiket") + [ACAK]:
            st = self._accounts[acc]["status"]
            d = self.day_counts(acc, day)
            lines.append(f"| {acc} | {st} | {d['filled_n']} | {d['tp_n']} | {d['hangus_n']} | {d['other_close_n']} | {d['tidak_terisi_n']} | {d['pnl_net']:+.4f} |")
        lines += ["", "## Posisi terbuka", "", "| id | akun | pair | sisi | qty | entry | lev | liq | jarak liq | TP | SL | unrealized | sejak |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in self.positions():
            lines.append(f"| {p['id']} | {p['account']} | {p['symbol']} | {p['side']} | {p['qty']} | {p['entry_price']:.6g} | {p['leverage']}x | {p['liq_price']:.6g} | "
                         f"{p.get('liq_dist_pct', float('nan')):.2f}% | {p['tp_price'] or '-'} | {p['sl_price'] or '-'} | {p.get('unrealized', 0):+.4f} | {fmt_wib(p['opened_ts'])} |")
        lines += ["", "## Posisi ditutup hari ini", "", "| id | akun | pair | sisi | lev | entry | keluar | alasan | net | fee | funding | ambigu |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in self.conn.execute("SELECT * FROM positions WHERE status='CLOSED' AND day_wib=? ORDER BY id", (day,)):
            lines.append(f"| {p['id']} | {p['account']} | {p['symbol']} | {p['side']} | {p['leverage']}x | {p['entry_price']:.6g} | {p['exit_price']:.6g} | {p['close_reason']} | "
                         f"{p['net_result']:+.4f} | {p['fees_total']:.4f} | {p['funding_total']:+.4f} | {('ya → ' + str(p['alt_outcome'])) if p['ambiguous'] else '-'} |")
        lines += ["", "## Order menunggu", "", "| id | akun | pair | sisi | tipe | harga | qty | lev | status | kedaluwarsa |", "|---|---|---|---|---|---|---|---|---|---|"]
        for o in self.orders():
            if o["reduce_only"]:
                continue
            lines.append(f"| {o['id']} | {o['account']} | {o['symbol']} | {o['side']} | {o['type']} | {o['price'] or 'MARKET'} | {o['qty']} | {o['leverage']}x | {o['status']} | {fmt_wib(o['expire_ts']) if o['expire_ts'] else '-'} |")
        amb = self.conn.execute("SELECT COUNT(*) FROM positions WHERE day_wib=? AND ambiguous=1", (day,)).fetchone()[0]
        lines += ["", f"Hasil yang ditentukan aturan ambigu hari ini: {amb}"]
        ev = self.conn.execute("SELECT ts, level, type, position_id, order_id, msg FROM events ORDER BY id DESC LIMIT 15").fetchall()
        lines += ["", "## Event terakhir", ""] + [f"- {fmt_wib(int(e['ts']))} {e['level']} {e['type']} pos={e['position_id'] or '-'} ord={e['order_id'] or '-'}: {e['msg']}" for e in ev]
        return "\n".join(lines)


# --------------------------------------------------------------------------- CLI
def _engine_for_cli() -> PaperEngine:
    pasar = connect(C.PASAR_DB, readonly=True)
    market = SqliteMarket(pasar)
    return PaperEngine(connect(C.PAPER_DB), market, log=C.setup_logging("paper_engine", to_stderr=False))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Mesin paper trading (CLI). Hasil hanya ditulis mesin.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    po = sub.add_parser("order", help="pasang order entry")
    po.add_argument("--akun", required=True, help="tiket|fade|breakout|rentang|swing")
    po.add_argument("--symbol", required=True)
    po.add_argument("--sisi", choices=(LONG, SHORT), required=True)
    po.add_argument("--qty", type=float, required=True)
    po.add_argument("--lev", type=int, required=True)
    po.add_argument("--harga", type=float, default=None, help="harga limit (kosong + --market = market order)")
    po.add_argument("--market", action="store_true")
    po.add_argument("--tp", type=float, default=None)
    po.add_argument("--sl", type=float, default=None)
    po.add_argument("--plan", default=None)
    po.add_argument("--pola", default=None)
    po.add_argument("--catatan", default=None)
    po.add_argument("--oleh", default="cli")
    pb = sub.add_parser("batal"); pb.add_argument("id", type=int)
    pt = sub.add_parser("tutup", help="minta tutup posisi (market di bar berikutnya)"); pt.add_argument("id", type=int)
    sub.add_parser("posisi")
    sub.add_parser("orders")
    sub.add_parser("budget")
    ps = sub.add_parser("step"); ps.add_argument("--sampai", default=None)
    pr = sub.add_parser("replay"); pr.add_argument("--dari", required=True); pr.add_argument("--sampai", required=True)
    pl = sub.add_parser("laporan"); pl.add_argument("--hari", default=None)
    pe = sub.add_parser("ekspor-tiket"); pe.add_argument("--hari", default=None); pe.add_argument("--out", default=str(C.ROOT / "jurnal" / "tiket.csv"))
    pd_ = sub.add_parser("rollover"); pd_.add_argument("--hari", required=True)
    pa = sub.add_parser("akun", help="arena: list | aktif <nama> | pensiun <nama> [--alasan]"); pa.add_argument("aksi", choices=("list", "aktif", "pensiun"))
    pa.add_argument("nama", nargs="?"); pa.add_argument("--alasan", default="")
    args = ap.parse_args(argv)

    eng = _engine_for_cli()
    if args.cmd == "init-db":
        print(f"paper.sqlite siap di {C.PAPER_DB}")
    elif args.cmd == "order":
        req = OrderRequest(account=args.akun, symbol=args.symbol, side=args.sisi, qty=args.qty, leverage=args.lev,
                           type="MARKET" if args.market else "LIMIT", price=args.harga, tp_price=args.tp, sl_price=args.sl,
                           post_only=not args.market, plan_id=args.plan, pattern=args.pola, note=args.catatan, created_by=args.oleh)
        res = eng.place_order(req)
        print(res)
        return 0 if res.ok else 1
    elif args.cmd == "batal":
        print("dibatalkan" if eng.cancel_order(args.id) else "tidak bisa dibatalkan (tidak ada / sudah selesai)")
    elif args.cmd == "tutup":
        print("permintaan tutup dicatat; eksekusi di bar berikutnya" if eng.close_position_request(args.id) else "posisi tidak ditemukan / tidak terbuka")
    elif args.cmd == "posisi":
        for p in eng.positions():
            print(json.dumps(p, ensure_ascii=False, default=str))
        print(f"{len(eng.positions())} posisi terbuka")
    elif args.cmd == "orders":
        for o in eng.orders():
            print(json.dumps(o, ensure_ascii=False, default=str))
    elif args.cmd == "budget":
        for acc in eng.accounts():
            print(json.dumps(eng.budget_status(acc), ensure_ascii=False))
    elif args.cmd == "akun":
        if args.aksi == "list":
            for acc in eng.accounts():
                print(json.dumps(eng.account_info(acc), ensure_ascii=False))
        else:
            ok = eng.set_account_status(args.nama or "", args.aksi, args.alasan)
            print(f"{args.nama} → {args.aksi}" if ok else "gagal: nama akun tidak dikenal atau bukan akun jenis tiket")
            return 0 if ok else 1
    elif args.cmd == "step":
        until = C.parse_iso_ms(args.sampai) if args.sampai else None
        print(eng.step(until_ms=until))
    elif args.cmd == "replay":
        print(eng.replay(C.parse_iso_ms(args.dari), C.parse_iso_ms(args.sampai)))
    elif args.cmd == "laporan":
        print(eng.report(args.hari))
    elif args.cmd == "ekspor-tiket":
        day = args.hari or day_wib(eng.clock())
        n = eng.export_tiket_csv(day, args.out)
        print(f"{n} baris ditulis ke {args.out}")
    elif args.cmd == "rollover":
        with tx(eng.conn):
            print(eng.rollover_day(args.hari))
    return 0


if __name__ == "__main__":
    sys.exit(main())
