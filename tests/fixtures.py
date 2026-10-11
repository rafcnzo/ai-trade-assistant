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

FILTERS = {
    BTC: SymbolFilters(BTC, "TRADING", Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("50"), 1.05, 0.95, 8),
    XYZ: SymbolFilters(XYZ, "TRADING", Decimal("0.0001"), Decimal("1"), Decimal("10"), Decimal("5"), 1.10, 0.90, 8),
    CN: SymbolFilters(CN, "TRADING", Decimal("0.00001"), Decimal("1"), Decimal("1"), Decimal("5"), 1.10, 0.90, 4),
    NOBR: SymbolFilters(NOBR, "TRADING", Decimal("0.01"), Decimal("1"), Decimal("1"), Decimal("5"), 1.10, 0.90, 8),
}
BRACKETS = {
    BTC: [Bracket(1, 0, 300_000, 150, 0.004, 0.0), Bracket(2, 300_000, 800_000, 100, 0.005, 300.0)],
    XYZ: [Bracket(1, 0, 5_000, 50, 0.015, 0.0)],
    CN: [Bracket(1, 0, 10_000, 10, 0.05, 0.0)],
    NOBR: [],
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
