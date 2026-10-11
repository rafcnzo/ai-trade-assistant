"""analisis.py — fungsi analisis murni (tanpa LLM, tanpa pandas).

Resample bar 1 menit, EMA/RSI/ATR versi Wilder, swing fraktal, klaster level, jejak psikologi di grafik
(spesifikasi §10.3, §16.3), tabel leverage tiket (§17.3), dan watchlist top volume (§17.7).
Dipakai oleh mcp_server.py dan pemindai.py. Hanya membaca; tidak menulis database.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Optional

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from common import DAY_MS, HOUR_MS, MINUTE_MS, Bar  # noqa: E402
from paper_engine import LONG, SHORT, Bracket, EngineConfig, SymbolFilters, fee_amount, liq_price, pick_bracket, size_for_margin  # noqa: E402

TF_MS = {"1m": MINUTE_MS, "5m": 5 * MINUTE_MS, "15m": 15 * MINUTE_MS, "1h": HOUR_MS, "4h": 4 * HOUR_MS, "1d": DAY_MS}


# --------------------------------------------------------------------------- resample
def resample(bars: list[Bar], tf_ms: int, now_ms: Optional[int] = None) -> list[Bar]:
    """Gabungkan bar 1m menjadi bucket `tf_ms` (selaras UTC). Hanya bucket yang sudah close:
    jika `now_ms` diberikan, bucket dengan open+tf > now dibuang; jika tidak, bucket terakhir dibuang."""
    if not bars:
        return []
    out: list[Bar] = []
    cur: Optional[dict] = None
    for b in sorted(bars, key=lambda x: x.open_time):
        bucket = b.open_time - b.open_time % tf_ms
        if cur is None or cur["open_time"] != bucket:
            if cur is not None:
                out.append(_mk(cur))
            cur = {"symbol": b.symbol, "open_time": bucket, "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                   "volume": b.volume, "quote_volume": b.quote_volume, "trades": b.trades, "taker_buy_quote": b.taker_buy_quote}
        else:
            cur["high"] = max(cur["high"], b.high)
            cur["low"] = min(cur["low"], b.low)
            cur["close"] = b.close
            cur["volume"] += b.volume
            cur["quote_volume"] += b.quote_volume
            cur["trades"] += b.trades
            cur["taker_buy_quote"] += b.taker_buy_quote
    if cur is not None:
        out.append(_mk(cur))
    if now_ms is None:
        return out[:-1]
    return [b for b in out if b.open_time + tf_ms <= now_ms]


def _mk(d: dict) -> Bar:
    return Bar(d["symbol"], d["open_time"], d["open"], d["high"], d["low"], d["close"], d["volume"], d["quote_volume"], d["trades"], d["taker_buy_quote"])


# --------------------------------------------------------------------------- indikator (Wilder)
def ema(values: list[float], n: int) -> list[float]:
    """EMA ewm(span=n, adjust=False): nilai pertama = data pertama. Butuh warm-up ≥ 3n agar stabil."""
    if not values:
        return []
    a = 2.0 / (n + 1)
    out = [float(values[0])]
    for v in values[1:]:
        out.append(a * float(v) + (1 - a) * out[-1])
    return out


def ema_last(values: list[float], n: int, warmup_mult: int = 3) -> Optional[float]:
    if len(values) < n * warmup_mult:
        return None
    return ema(values, n)[-1]


def rsi(closes: list[float], n: int = 14) -> Optional[float]:
    """RSI Wilder (rata-rata gain/loss dengan alpha 1/n, seed rata-rata sederhana n pertama)."""
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - 100.0 / (1.0 + rs)


def true_ranges(bars: list[Bar]) -> list[float]:
    out = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close
        out.append(max(h - l, abs(h - pc), abs(l - pc)))
    return out


def atr_series(bars: list[Bar], n: int = 14) -> list[Optional[float]]:
    """ATR Wilder; None sebelum tersedia n true range."""
    trs = true_ranges(bars)
    out: list[Optional[float]] = [None] * len(bars)
    if len(trs) < n:
        return out
    a = sum(trs[:n]) / n
    out[n] = a   # bar ke-n (indeks n) adalah bar ke-n yang punya TR
    for i in range(n, len(trs)):
        a = (a * (n - 1) + trs[i]) / n
        out[i + 1] = a
    return out


def atr(bars: list[Bar], n: int = 14) -> Optional[float]:
    s = atr_series(bars, n)
    return s[-1] if s else None


# --------------------------------------------------------------------------- swing & level
@dataclass(frozen=True)
class Swing:
    ts: int
    price: float
    kind: str  # "high" | "low"


@dataclass
class Level:
    price: float
    touches: int
    last_ts: int
    kinds: str = ""


def swings(bars: list[Bar], left: int = 3, right: int = 3) -> list[Swing]:
    """Swing fraktal: high tertinggi (atau low terendah) dibanding `left` bar kiri dan `right` bar kanan."""
    out: list[Swing] = []
    for i in range(left, len(bars) - right):
        win = bars[i - left: i + right + 1]
        b = bars[i]
        if b.high >= max(x.high for x in win) and sum(1 for x in win if x.high == b.high) == 1:
            out.append(Swing(b.open_time, b.high, "high"))
        if b.low <= min(x.low for x in win) and sum(1 for x in win if x.low == b.low) == 1:
            out.append(Swing(b.open_time, b.low, "low"))
    return out


def cluster_levels(sw: Iterable[Swing], width: float) -> list[Level]:
    """Klaster swing yang harganya berjarak ≤ width dari rata-rata klaster; kekuatan = jumlah sentuhan."""
    items = sorted(sw, key=lambda s: s.price)
    out: list[Level] = []
    for s in items:
        if out and abs(s.price - out[-1].price) <= width:
            lv = out[-1]
            n = lv.touches
            lv.price = (lv.price * n + s.price) / (n + 1)
            lv.touches = n + 1
            lv.last_ts = max(lv.last_ts, s.ts)
            if s.kind[0] not in lv.kinds:
                lv.kinds += s.kind[0]
        else:
            out.append(Level(s.price, 1, s.ts, s.kind[0]))
    return out


def nearest(levels: list[Level], price: float, n: int = 3) -> tuple[list[Level], list[Level]]:
    """(level di atas harga, terdekat dulu), (level di bawah harga, terdekat dulu)."""
    above = sorted([lv for lv in levels if lv.price > price], key=lambda lv: lv.price)[:n]
    below = sorted([lv for lv in levels if lv.price <= price], key=lambda lv: -lv.price)[:n]
    return above, below


# --------------------------------------------------------------------------- jejak psikologi (§16.3)
@dataclass
class JejakConfig:
    wick_ratio: float = 2.0        # wick ≥ 2× body
    wick_level_atr: float = 0.25   # ujung wick dalam 0,25×ATR dari level
    vol_mult: float = 2.0          # volume ≥ 2× rata-rata 20 bar sebelumnya
    vol_lookback: int = 20
    impuls_n: int = 4
    impuls_body_atr: float = 0.7
    kompresi_bars: int = 10
    kompresi_atr_mult: float = 2.0  # range 10 bar < 2×ATR → kompresi
    breakout_return_bars: int = 3
    lookback: int = 20             # bar terakhir yang diperiksa untuk wick/breakout


def jejak(bars: list[Bar], levels: list[Level], atr_val: Optional[float], cfg: Optional[JejakConfig] = None) -> list[dict]:
    """Mendeteksi jejak mekanis pada bar yang sudah close. Setiap item: {jejak, ts, keterangan, level?}."""
    cfg = cfg or JejakConfig()
    out: list[dict] = []
    if not bars or not atr_val or atr_val <= 0:
        return out
    recent = bars[-cfg.lookback:]
    # WICK penolakan di level
    for b in recent:
        body = abs(b.close - b.open)
        upper = b.high - max(b.open, b.close)
        lower = min(b.open, b.close) - b.low
        for wick, end, arah in ((upper, b.high, "atas"), (lower, b.low, "bawah")):
            if wick >= cfg.wick_ratio * max(body, 1e-12) and wick > 0:
                for lv in levels:
                    if abs(end - lv.price) <= cfg.wick_level_atr * atr_val:
                        out.append({"jejak": "WICK", "ts": b.open_time, "arah": arah, "level": lv.price, "sentuhan": lv.touches,
                                    "keterangan": f"wick {arah} {wick / atr_val:.1f}×ATR menolak level {lv.price:.6g}"})
                        break
    # VOL lonjakan pada bar terakhir
    if len(bars) > cfg.vol_lookback:
        prev = bars[-cfg.vol_lookback - 1:-1]
        avg = sum(x.quote_volume for x in prev) / len(prev)
        last = bars[-1]
        if avg > 0 and last.quote_volume >= cfg.vol_mult * avg:
            out.append({"jejak": "VOL", "ts": last.open_time, "rasio": round(last.quote_volume / avg, 2),
                        "arah": "naik" if last.close >= last.open else "turun",
                        "keterangan": f"volume {last.quote_volume / avg:.1f}× rata-rata {cfg.vol_lookback} bar, candle {'naik' if last.close >= last.open else 'turun'}"})
    # BREAKOUT_GAGAL: close keluar level lalu kembali ≤ N bar
    for lv in levels:
        for i in range(max(1, len(bars) - cfg.lookback), len(bars)):
            b = bars[i]
            prev = bars[i - 1]
            if prev.close <= lv.price < b.close:       # tembus ke atas
                for j in range(i + 1, min(len(bars), i + 1 + cfg.breakout_return_bars)):
                    if bars[j].close < lv.price:
                        out.append({"jejak": "BREAKOUT_GAGAL", "ts": bars[j].open_time, "arah": "atas", "level": lv.price,
                                    "keterangan": f"tembus {lv.price:.6g} ke atas lalu close kembali di bawah dalam {j - i} bar; pembeli breakout terjebak"})
                        break
            elif prev.close >= lv.price > b.close:     # tembus ke bawah
                for j in range(i + 1, min(len(bars), i + 1 + cfg.breakout_return_bars)):
                    if bars[j].close > lv.price:
                        out.append({"jejak": "BREAKOUT_GAGAL", "ts": bars[j].open_time, "arah": "bawah", "level": lv.price,
                                    "keterangan": f"tembus {lv.price:.6g} ke bawah lalu close kembali di atas dalam {j - i} bar; penjual breakdown terjebak"})
                        break
    # IMPULS: ≥ n candle searah dengan body > k×ATR
    run, direction = 0, 0
    for b in bars[-cfg.lookback:]:
        d = 1 if b.close > b.open else (-1 if b.close < b.open else 0)
        if d != 0 and d == direction and abs(b.close - b.open) > cfg.impuls_body_atr * atr_val:
            run += 1
        elif d != 0 and abs(b.close - b.open) > cfg.impuls_body_atr * atr_val:
            direction, run = d, 1
        else:
            direction, run = 0, 0
        if run >= cfg.impuls_n:
            out.append({"jejak": "IMPULS", "ts": b.open_time, "arah": "naik" if direction > 0 else "turun",
                        "keterangan": f"{run} candle {'naik' if direction > 0 else 'turun'} beruntun dengan body > {cfg.impuls_body_atr}×ATR; risiko mengejar harga"})
            run = 0
    # KOMPRESI
    if len(bars) >= cfg.kompresi_bars:
        win = bars[-cfg.kompresi_bars:]
        rng = max(x.high for x in win) - min(x.low for x in win)
        if rng < cfg.kompresi_atr_mult * atr_val:
            out.append({"jejak": "KOMPRESI", "ts": win[-1].open_time, "range_atr": round(rng / atr_val, 2),
                        "keterangan": f"range {cfg.kompresi_bars} bar hanya {rng / atr_val:.1f}×ATR; energi menumpuk"})
    out.sort(key=lambda x: x["ts"])
    return out


# --------------------------------------------------------------------------- tren (§10.3)
def tren(bars: list[Bar], ema_n: int = 50) -> str:
    """naik: HH+HL dan close > EMA; turun: LH+LL dan close < EMA; selain itu sideways."""
    if len(bars) < max(ema_n, 20):
        return "tidak tersedia"
    e = ema([b.close for b in bars], ema_n)[-1]
    sw = swings(bars)
    highs = [s.price for s in sw if s.kind == "high"][-2:]
    lows = [s.price for s in sw if s.kind == "low"][-2:]
    close = bars[-1].close
    if len(highs) == 2 and len(lows) == 2:
        if highs[1] > highs[0] and lows[1] > lows[0] and close > e:
            return "naik"
        if highs[1] < highs[0] and lows[1] < lows[0] and close < e:
            return "turun"
    return "sideways"


# --------------------------------------------------------------------------- tabel leverage tiket (§17.3)
def tabel_leverage(sisi: str, entry: float, f: SymbolFilters, brackets: list[Bracket], atr_map: dict[str, Optional[float]],
                   budget_sisa: float, cfg: Optional[EngineConfig] = None, leverages: Optional[list[int]] = None,
                   targets: Iterable[float] = (0.5, 1.0, 2.0)) -> dict:
    """Per leverage: qty terbesar yang muat budget (margin + fee masuk ≤ budget), likuidasi, jarak dalam ATR, fee, win rate minimum."""
    cfg = cfg or EngineConfig()
    b1 = pick_bracket(brackets, 1.0)
    lev_max = b1.max_leverage if b1 else 0
    if leverages is None:
        leverages = sorted({lv for lv in (lev_max, 150, 125, 100, 75, 50, 25, 10) if 0 < lv <= lev_max}, reverse=True)
    rows = []
    for lev in leverages:
        margin_max = budget_sisa / (1.0 + lev * cfg.fee_maker)
        qty = size_for_margin(entry, lev, margin_max, f)
        if qty is None:
            rows.append({"leverage": lev, "keterangan": "tidak bisa: qty/notional di bawah minimum untuk budget ini"})
            continue
        q = float(qty)
        notional = q * entry
        b = pick_bracket(brackets, notional)
        if b is None or lev > b.max_leverage:
            rows.append({"leverage": lev, "keterangan": f"di atas leverage maks {b.max_leverage if b else '?'}x untuk notional ini"})
            continue
        margin = notional / lev
        liq = liq_price(sisi, q, entry, margin, b.mmr, b.cum)
        jarak = abs(entry - liq)
        fee_in = fee_amount(notional, True, cfg)
        fee_rt = 2 * fee_in
        row = {
            "leverage": lev, "qty": C.fmt_dec(qty), "notional": round(notional, 4), "margin": round(margin, 6),
            "fee_masuk": round(fee_in, 6), "fee_bolak_balik": round(fee_rt, 6), "fee_pct_tiket": round(fee_rt / margin * 100, 2),
            "liq": round(liq, 8), "jarak_liq_pct": round(jarak / entry * 100, 4),
            "x_atr": {tf: (round(jarak / a, 2) if a else None) for tf, a in atr_map.items()},
            "target": [],
        }
        rugi_hangus = margin + fee_in
        for tpct in targets:
            untung = notional * tpct / 100.0 - fee_rt
            wr = rugi_hangus / (rugi_hangus + untung) if untung > 0 else None
            row["target"].append({"pct": tpct, "untung_bersih": round(untung, 4), "winrate_min_pct": (round(wr * 100, 1) if wr else None)})
        rows.append(row)
    return {"sisi": sisi, "entry": entry, "budget_sisa": round(budget_sisa, 6), "leverage_maks": lev_max,
            "atr": {tf: (round(a, 8) if a else None) for tf, a in atr_map.items()}, "baris": rows,
            "catatan": "limit order masuk & TP (fee maker); rugi saat hangus = margin + fee masuk; aturan uji: jarak liq ≥ 2×ATR 5m"}


# --------------------------------------------------------------------------- top volume (§17.7)
FLAG_LARI_PCT = 20.0
FLAG_BARU_HARI = 30
FUNDING_TINGGI = 0.0003
FUNDING_RENDAH = -0.0001


def top_volume(pasar: sqlite3.Connection, n: int = 20, now_ms: Optional[int] = None) -> dict:
    """Watchlist dinamis dari ticker_24h terbaru + bracket + symbol_info + mark_snapshot. Tanpa CoinGecko (mcap tidak tersedia)."""
    now_ms = now_ms or C.now_ms()
    r = pasar.execute("SELECT MAX(ts) FROM ticker_24h").fetchone()
    if r is None or r[0] is None:
        return {"ts": None, "baris": [], "catatan": "ticker_24h kosong; collector belum jalan"}
    ts = int(r[0])
    rows = pasar.execute(
        """SELECT t.rank, t.symbol, t.last, t.pct_24h, t.quote_volume, s.onboard_date, s.status,
                  (SELECT max_leverage FROM leverage_bracket b WHERE b.symbol=t.symbol AND b.bracket=1) AS lev,
                  (SELECT mmr FROM leverage_bracket b WHERE b.symbol=t.symbol AND b.bracket=1) AS mmr,
                  (SELECT last_funding_rate FROM mark_snapshot m WHERE m.symbol=t.symbol ORDER BY ts DESC LIMIT 1) AS funding
           FROM ticker_24h t LEFT JOIN symbol_info s ON s.symbol=t.symbol
           WHERE t.ts=? AND t.rank<=? ORDER BY t.rank""",
        (ts, n),
    ).fetchall()
    out = []
    for x in rows:
        flags = []
        pct = x["pct_24h"] or 0.0
        if abs(pct) > FLAG_LARI_PCT:
            flags.append("SUDAH_LARI")
        umur = None
        if x["onboard_date"]:
            umur = (now_ms - int(x["onboard_date"])) // DAY_MS
            if umur < FLAG_BARU_HARI:
                flags.append("BARU")
        if x["lev"] is None:
            flags.append("LEVERAGE_TIDAK_TERSEDIA")
        fr = x["funding"]
        if fr is not None and (fr > FUNDING_TINGGI or fr < FUNDING_RENDAH):
            flags.append("FUNDING_EKSTREM")
        out.append({
            "peringkat": x["rank"], "symbol": x["symbol"], "harga": x["last"], "pct_24j": pct,
            "volume_24j_usd": x["quote_volume"], "tier": C.tier_for(x["symbol"], x["rank"]),
            "leverage_maks": x["lev"], "mmr_tier1": x["mmr"], "funding": fr, "umur_listing_hari": umur,
            "mcap": "tidak tersedia", "flag": flags,
        })
    return {"ts": ts, "ts_wib": C.fmt_wib(ts), "umur_menit": (now_ms - ts) // MINUTE_MS, "baris": out}


def load_bars(market, symbol: str, hours: float, until_ms: int) -> list[Bar]:
    start = int(until_ms - hours * HOUR_MS) - 1
    return [b for b, _ in market.bars(symbol, start, until_ms)]
