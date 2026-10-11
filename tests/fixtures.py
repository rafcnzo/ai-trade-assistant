"""Fixture bersama untuk tes: pasar sintetis tanpa jaringan."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from common import Bar, MarkBar, MINUTE_MS  # noqa: E402
from paper_engine import Bracket, FundingEvent, SymbolFilters  # noqa: E402

DAY = "2026-10-10"
DAY2 = "2026-10-11"
DAY_MS = C.day_start_wib_ms(DAY)

BTC = "BTCUSDT"
XYZ = "XYZUSDT"          # small cap: step 1, min_qty 10, 50x, mmr 1.5%
CN = "龙虾USDT"           # simbol non-latin: 10x, mmr 5%
NOBR = "NOBRUSDT"        # ada filter tapi tanpa bracket
PEM = "PEMUSDT"          # simbol pemindai: harga ~100, tick 0.01, 150x mmr 0.4%
PEM2 = "PEM2USDT"

FILTERS = {
    BTC: SymbolFilters(BTC, "TRADING", Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("50"), 1.05, 0.95, 8),
    XYZ: SymbolFilters(XYZ, "TRADING", Decimal("0.0001"), Decimal("1"), Decimal("10"), Decimal("5"), 1.10, 0.90, 8),
    CN: SymbolFilters(CN, "TRADING", Decimal("0.00001"), Decimal("1"), Decimal("1"), Decimal("5"), 1.10, 0.90, 4),
    NOBR: SymbolFilters(NOBR, "TRADING", Decimal("0.01"), Decimal("1"), Decimal("1"), Decimal("5"), 1.10, 0.90, 8),
    PEM: SymbolFilters(PEM, "TRADING", Decimal("0.01"), Decimal("0.01"), Decimal("0.01"), Decimal("5"), 1.10, 0.90, 8),
    PEM2: SymbolFilters(PEM2, "TRADING", Decimal("0.01"), Decimal("0.01"), Decimal("0.01"), Decimal("5"), 1.10, 0.90, 8),
}
BRACKETS = {
    BTC: [Bracket(1, 0, 300_000, 150, 0.004, 0.0), Bracket(2, 300_000, 800_000, 100, 0.005, 300.0)],
    XYZ: [Bracket(1, 0, 5_000, 50, 0.015, 0.0)],
    CN: [Bracket(1, 0, 10_000, 10, 0.05, 0.0)],
    NOBR: [],
    PEM: [Bracket(1, 0, 50_000, 150, 0.004, 0.0)],
    PEM2: [Bracket(1, 0, 50_000, 150, 0.004, 0.0)],
}


def t(hhmm: str, day_ms: int = DAY_MS, sec: int = 0) -> int:
    h, m = hhmm.split(":")
    return day_ms + int(h) * C.HOUR_MS + int(m) * MINUTE_MS + sec * 1000


class FixtureMarket:
    def __init__(self):
        self._bars: dict[str, dict[int, tuple[Bar, Optional[MarkBar]]]] = {}
        self._funding: dict[str, list[FundingEvent]] = {}
        self._mark: dict[str, tuple[float, int]] = {}
        self._tier: dict[str, str] = {}
        self._bars_1h: dict[str, dict[int, Bar]] = {}

    # --- isi
    def add_bar(self, symbol: str, open_time: int, o: float, h: float, l: float, c: float, mark=None, no_mark: bool = False):
        bar = Bar(symbol, open_time, o, h, l, c, 1.0, o, 10, 0.5)
        if no_mark:
            mb = None
        elif mark is None:
            mb = MarkBar(symbol, open_time, o, h, l, c)
        else:
            mb = MarkBar(symbol, open_time, *mark)
        self._bars.setdefault(symbol, {})[open_time] = (bar, mb)
        return self

    def add_bar_1h(self, symbol: str, open_time: int, o: float, h: float, l: float, c: float, qv: float = 1000.0):
        self._bars_1h.setdefault(symbol, {})[open_time] = Bar(symbol, open_time, o, h, l, c, qv / o, qv, 100, qv / 2)
        return self

    def add_funding(self, symbol: str, funding_time: int, rate: float, mark_price: Optional[float] = None):
        self._funding.setdefault(symbol, []).append(FundingEvent(symbol, funding_time, rate, mark_price))
        return self

    def set_mark(self, symbol: str, price: float, ts: int = 0):
        self._mark[symbol] = (price, ts)
        return self

    def set_tier(self, symbol: str, tier: str):
        self._tier[symbol] = tier
        return self

    # --- MarketData
    def bars(self, symbol, after_open_time, until_open_time):
        d = self._bars.get(symbol, {})
        return [d[k] for k in sorted(d) if after_open_time < k <= until_open_time]

    def bars_1h(self, symbol, after_open_time, until_open_time):
        d = self._bars_1h.get(symbol, {})
        return [d[k] for k in sorted(d) if after_open_time < k <= until_open_time]

    def funding_events(self, symbol, after_ms, until_ms):
        return [e for e in sorted(self._funding.get(symbol, []), key=lambda e: e.funding_time) if after_ms < e.funding_time <= until_ms]

    def filters(self, symbol):
        return FILTERS.get(symbol)

    def brackets(self, symbol):
        return list(BRACKETS.get(symbol, []))

    def last_mark(self, symbol):
        return self._mark.get(symbol)

    def tier(self, symbol):
        return self._tier.get(symbol, C.tier_for(symbol))


class Usage:
    """Tiruan objek usage SDK Anthropic."""

    class _CC:
        def __init__(self, m5=0, h1=0):
            self.ephemeral_5m_input_tokens = m5
            self.ephemeral_1h_input_tokens = h1

    def __init__(self, input_tokens=0, output_tokens=0, cache_read=0, cw5=None, cw1h=None, cache_creation_input_tokens=0, speed=None):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_creation = self._CC(cw5 or 0, cw1h or 0) if (cw5 is not None or cw1h is not None) else None
        self.speed = speed


# --------------------------------------------------------------------------- pemindai: pasar.sqlite sintetis
def bars_flat(symbol: str, end_ms: int, n5: int = 72, base: float = 100.30) -> list[Bar]:
    """n5 bucket 5m datar (range 0,06, volume rata) yang berakhir pada end_ms; tanpa swing → tanpa level."""
    start = end_ms - n5 * 5 * MINUTE_MS
    out = []
    for i in range(n5 * 5):
        out.append(Bar(symbol, start + i * MINUTE_MS, base, base + 0.03, base - 0.03, base, 10.0, 1000.0, 10, 500.0))
    return out


def bars_setup_long(symbol: str, end_ms: int, n5: int = 72, base: float = 100.30, level: float = 100.00) -> list[Bar]:
    """Setup LONG: n5 bucket 5m berakhir pada end_ms; swing low tepat di `level` pada 3 bucket (−52, −32, −12 dari akhir),
    bucket terakhir wick bawah menolak `level` (body 0,02, wick 0,07) dengan volume 3× rata-rata."""
    start = end_ms - n5 * 5 * MINUTE_MS
    out = []
    for i in range(n5):
        o = c = base
        h, l, qv = base + 0.03, base - 0.03, 1000.0
        if i in (n5 - 52, n5 - 32, n5 - 12):
            l = level
        if i == n5 - 1:
            o, h, l, c, qv = level + 0.10, level + 0.12, level + 0.01, level + 0.08, 3000.0
        for k in range(5):
            out.append(Bar(symbol, start + (i * 5 + k) * MINUTE_MS, o, h, l, c, qv / 100, qv, 10, qv / 2))
    return out


def seed_pasar(conn, symbol: str, bars: list[Bar], mark: float, tick_ts: int, rank: int = 1, pct_24h: float = 1.5,
               funding: float = 0.0001, filters: Optional[SymbolFilters] = None, brackets: Optional[list] = None) -> None:
    """Isi pasar.sqlite sementara untuk satu simbol: filter, bracket, kline_1m + mark_kline_1m, ticker_24h, mark_snapshot, meta tick.
    Bisa dipanggil berulang untuk simbol lain dengan tick_ts yang sama (universe = simbol pada ts ticker terakhir)."""
    f = filters or FILTERS[symbol]
    br = BRACKETS[symbol] if brackets is None else brackets
    C.init_schema(conn, C.SCRIPTS_DIR / "schema_pasar.sql", "2")
    with C.tx(conn):
        conn.execute(
            "INSERT OR REPLACE INTO symbol_info(symbol,status,contract_type,base_asset,quote_asset,onboard_date,tick_size,qty_step,min_qty,min_notional,"
            "pct_up,pct_down,liq_fee,funding_interval_h,updated_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (symbol, f.status, "PERPETUAL", symbol[:-4], "USDT", tick_ts - 400 * C.DAY_MS, str(f.tick_size), str(f.qty_step), str(f.min_qty),
             str(f.min_notional), f.pct_up, f.pct_down, 0.0125, f.funding_interval_h, tick_ts),
        )
        conn.execute("DELETE FROM leverage_bracket WHERE symbol=?", (symbol,))
        for b in br:
            conn.execute("INSERT INTO leverage_bracket(symbol,bracket,notional_floor,notional_cap,max_leverage,min_leverage,mmr,cum,updated_ts) VALUES(?,?,?,?,?,?,?,?,?)",
                         (symbol, b.bracket, b.notional_floor, b.notional_cap, b.max_leverage, 1, b.mmr, b.cum, tick_ts))
        conn.executemany(
            "INSERT OR REPLACE INTO kline_1m(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [(b.symbol, b.open_time, b.open, b.high, b.low, b.close, b.volume, b.quote_volume, b.trades, b.taker_buy_quote) for b in bars],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO mark_kline_1m(symbol,open_time,open,high,low,close) VALUES(?,?,?,?,?,?)",
            [(b.symbol, b.open_time, b.open, b.high, b.low, b.close) for b in bars],
        )
        conn.execute("INSERT OR REPLACE INTO ticker_24h(ts,symbol,rank,last,pct_24h,quote_volume) VALUES(?,?,?,?,?,?)",
                     (tick_ts, symbol, rank, mark, pct_24h, 1e9 / rank))
        conn.execute("INSERT OR REPLACE INTO mark_snapshot(symbol,ts,mark,index_price,last_funding_rate,next_funding_time) VALUES(?,?,?,?,?,?)",
                     (symbol, tick_ts, mark, mark, funding, tick_ts + C.HOUR_MS))
        C.meta_set(conn, "last_tick_ms", tick_ts)
