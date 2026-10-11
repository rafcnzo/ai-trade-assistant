"""pemindai.py — pemindai kandidat tiket mekanis, TANPA LLM.

Dijalankan tiap 5 menit oleh cron Hermes lewat hermes/scripts/pemindai_cron.py. Membaca pasar.sqlite (readonly)
dan paper.sqlite (hanya metode baca PaperEngine), menulis data/kandidat.sqlite (penulis tunggal), lalu mencetak
ringkasan untuk agent dan baris gate terakhir: {"wakeAgent": true} bila ada kandidat, {"wakeAgent": false} bila tidak.
Hermes hanya membangunkan agent (biaya LLM) saat gate true.

Aturan: spesifikasi §16.3 (jejak), §17.3 (leverage, jarak likuidasi ≥ 2×ATR 5m), §19.3–19.5 (gate, budget), playbook P-09 (gate G9).
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisis as A  # noqa: E402
import common as C  # noqa: E402
from common import HOUR_MS, MINUTE_MS, Bar, fmt_wib  # noqa: E402
from paper_engine import LONG, SHORT, TIKET, Bracket, EngineConfig, PaperEngine, SqliteMarket, SymbolFilters, pick_bracket  # noqa: E402

SCHEMA_VERSION = "1"
KANDIDAT_DB = C.DATA_DIR / "kandidat.sqlite"
GATE_ON = '{"wakeAgent": true}'
GATE_OFF = '{"wakeAgent": false}'


# --------------------------------------------------------------------------- konfigurasi & data
@dataclass
class PemindaiConfig:
    top_n: int = 30          # watchlist = top volume 24 jam (bukan daftar tetap)
    lookback_h: int = 48
    bar_grace_ms: int = 5_000
    atr_n: int = 14
    level_width_atr: float = 0.5
    min_touches: int = 2
    dekat_atr5m: float = 0.5
    max_jarak_atr5m: float = 2.0
    jejak: A.JejakConfig = field(default_factory=lambda: A.JejakConfig(lookback=12))
    fresh_bars_5m: int = 3
    leverages: tuple = (150, 125, 100)
    lev_max_fallback: bool = True
    x_atr5m_min: float = 2.0
    score_min: int = 3
    top_k: int = 5           # kandidat skor tertinggi yang dikirim ke agent per wake
    stale_s: int = 180
    budget_min: float = 0.10
    jam_mulai: str = "07:00"
    jam_akhir: str = "22:30"
    max_wake_per_day: int = 12
    cooldown_min: int = 30
    max_live_tiket: int = 2
    max_hangus_beruntun: int = 2   # playbook P-09: setelah 2 tiket HANGUS beruntun, tidak ada tiket baru hari itu
    retention_days: int = 30


@dataclass
class Kandidat:
    symbol: str
    arah_dugaan: str
    dasar_arah: str
    mark: float
    level: float
    sentuhan: int
    level_tf: str
    jarak_atr5m: float
    atr_1m: Optional[float]
    atr_5m: float
    atr_15m: Optional[float]
    atr_1h: Optional[float]
    pct_24h: Optional[float]
    funding: Optional[float]
    tren_15m: str
    lev_layak: list = field(default_factory=list)
    score: int = 0
    flags: list = field(default_factory=list)
    jejak: list = field(default_factory=list)
    ringkasan: str = ""
    id: Optional[int] = None

    @property
    def plan_id(self) -> str:
        return f"K{self.id}" if self.id is not None else "K?"


@dataclass
class RunResult:
    ts: int
    day_wib: str
    data_tick_ts: Optional[int]
    n_symbols: int = 0
    kandidat: list = field(default_factory=list)
    ditahan: list = field(default_factory=list)      # [{"symbol", "alasan", "score"}]
    dipindai: list = field(default_factory=list)     # debug per simbol (untuk --once/--json)
    wake: bool = False
    alasan: str = ""
    budget_sisa: Optional[float] = None
    wake_hari_ini: int = 0
    duration_ms: int = 0
    ok: int = 1
    err: Optional[str] = None


# --------------------------------------------------------------------------- fungsi murni
def data_until_for(bars: list[Bar], tick_ts: Optional[int], grace_ms: int) -> Optional[int]:
    """Batas data yang boleh dipakai: akhir bar 1m terakhir yang tersimpan, dibatasi tick collector − grace.
    Tidak memakai jam dinding, supaya bucket 5m yang belum lengkap tidak pernah ikut."""
    if not bars:
        return None
    last = max(b.open_time for b in bars) + MINUTE_MS
    if tick_ts:
        return min(last, C.floor_minute(tick_ts - grace_ms))
    return last


def fitur_simbol(bars: list[Bar], mark: float, data_until: Optional[int], cfg: PemindaiConfig) -> Optional[dict]:
    """ATR multi-tf, level (klaster swing 5m ∪ 15m, ≥ min_touches), level terdekat, jejak 5m, tren 15m."""
    if not bars or not data_until or not mark:
        return None
    closed = [b for b in bars if b.open_time + MINUTE_MS <= data_until]
    if len(closed) < 60:
        return None
    b5 = A.resample(closed, 5 * MINUTE_MS, data_until)
    b15 = A.resample(closed, 15 * MINUTE_MS, data_until)
    b1h = A.resample(closed, HOUR_MS, data_until)
    if len(b5) < 16 or len(b15) < 16:
        return None
    atr5 = A.atr(b5, cfg.atr_n)
    if not atr5 or atr5 <= 0:
        return None
    atr1 = A.atr(closed[-300:], cfg.atr_n) if len(closed) > cfg.atr_n + 1 else None
    atr15 = A.atr(b15, cfg.atr_n)
    atr1h = A.atr(b1h, cfg.atr_n) if len(b1h) > cfg.atr_n + 1 else None
    lv5 = A.cluster_levels(A.swings(b5), cfg.level_width_atr * atr5)
    lv15 = A.cluster_levels(A.swings(b15), cfg.level_width_atr * (atr15 or atr5))
    levels = [{"price": lv.price, "touches": lv.touches, "tf": "5m", "last_ts": lv.last_ts} for lv in lv5]
    for lv in lv15:   # level 15m yang berimpit dengan level 5m digabung (sentuhan terbanyak), bukan diduplikasi
        same = next((x for x in levels if abs(x["price"] - lv.price) <= cfg.level_width_atr * atr5), None)
        if same is None:
            levels.append({"price": lv.price, "touches": lv.touches, "tf": "15m", "last_ts": lv.last_ts})
        else:
            same.update(touches=max(same["touches"], lv.touches), tf="5m+15m", last_ts=max(same["last_ts"], lv.last_ts))
    kuat = [lv for lv in levels if lv["touches"] >= cfg.min_touches]
    nearest = min(kuat, key=lambda lv: abs(mark - lv["price"])) if kuat else None
    jarak = abs(mark - nearest["price"]) / atr5 if nearest else None
    jj = A.jejak(b5, [A.Level(lv["price"], lv["touches"], lv["last_ts"]) for lv in levels], atr5, cfg.jejak)
    return {
        "data_until": data_until, "n_1m": len(closed), "n_5m": len(b5), "n_15m": len(b15),
        "atr_1m": atr1, "atr_5m": atr5, "atr_15m": atr15, "atr_1h": atr1h,
        "levels": kuat, "level": nearest, "jarak_atr5m": jarak, "jejak": jj, "tren_15m": A.tren(b15),
    }


def _dekat_level(item: dict, level_price: float, atr5: float) -> bool:
    lv = item.get("level")
    return lv is not None and abs(float(lv) - level_price) <= 0.25 * atr5


def tentukan_arah(level: dict, mark: float, jejak: list[dict], data_until: int, atr5: float, cfg: PemindaiConfig) -> tuple[str, str]:
    """Arah dugaan dari penolakan terbaru di level terdekat; tanpa penolakan: pullback ke sisi level."""
    fresh_ts = data_until - cfg.fresh_bars_5m * 5 * MINUTE_MS
    for item in sorted(jejak, key=lambda x: -x["ts"]):
        if item["ts"] < fresh_ts or not _dekat_level(item, level["price"], atr5):
            continue
        if item["jejak"] == "BREAKOUT_GAGAL":
            return (SHORT, "breakout gagal ke atas; pembeli terjebak") if item["arah"] == "atas" else (LONG, "breakdown gagal; penjual terjebak")
        if item["jejak"] == "WICK":
            return (LONG, "wick bawah menolak level") if item["arah"] == "bawah" else (SHORT, "wick atas menolak level")
    return (LONG, "pullback ke support") if level["price"] <= mark else (SHORT, "pullback ke resistance")


def hitung_skor(fitur: dict, arah: str, pct_24h: Optional[float], funding: Optional[float], cfg: PemindaiConfig) -> tuple[int, list[str]]:
    score, flags = 0, []
    level, atr5, data_until = fitur["level"], fitur["atr_5m"], fitur["data_until"]
    fresh_ts = data_until - cfg.fresh_bars_5m * 5 * MINUTE_MS
    if fitur["jarak_atr5m"] is not None and fitur["jarak_atr5m"] <= cfg.dekat_atr5m:
        score += 2
        flags.append("DEKAT_LEVEL")
    for item in fitur["jejak"]:
        fresh = item["ts"] >= fresh_ts
        j = item["jejak"]
        if j == "WICK" and level and _dekat_level(item, level["price"], atr5):
            ok = (item["arah"] == "bawah" and arah == LONG) or (item["arah"] == "atas" and arah == SHORT)
            if ok and fresh:
                score += 2
                flags.append("WICK")
            elif ok:
                flags.append("WICK_LAMA")
        elif j == "BREAKOUT_GAGAL" and level and _dekat_level(item, level["price"], atr5):
            ok = (item["arah"] == "atas" and arah == SHORT) or (item["arah"] == "bawah" and arah == LONG)
            if ok and fresh:
                score += 2
                flags.append("BREAKOUT_GAGAL")
            elif ok:
                flags.append("BREAKOUT_GAGAL_LAMA")
        elif j == "VOL" and fresh:
            score += 1
            flags.append("VOL")
        elif j in ("IMPULS", "KOMPRESI"):
            flags.append(j)
    if pct_24h is not None and abs(pct_24h) > A.FLAG_LARI_PCT:
        score -= 1
        flags.append("SUDAH_LARI")
    if funding is not None and ((funding > A.FUNDING_TINGGI and arah == LONG) or (funding < A.FUNDING_RENDAH and arah == SHORT)):
        score -= 1
        flags.append("FUNDING_EKSTREM")
    tren = fitur.get("tren_15m")
    if (tren == "naik" and arah == SHORT) or (tren == "turun" and arah == LONG):
        flags.append("MELAWAN_TREN_15M")
    seen: list[str] = []
    for f in flags:
        if f not in seen:
            seen.append(f)
    return score, seen


def leverage_layak(arah: str, entry: float, f: SymbolFilters, brackets: list[Bracket], atr5: float, budget_sisa: float,
                   eng_cfg: EngineConfig, cfg: PemindaiConfig) -> list[dict]:
    b1 = pick_bracket(brackets, 1.0)
    lev_max = b1.max_leverage if b1 else 0
    levs = [lv for lv in cfg.leverages if lv <= lev_max] or ([lev_max] if cfg.lev_max_fallback and lev_max else [])
    if not levs or budget_sisa <= 0:
        return []
    tab = A.tabel_leverage(arah, entry, f, brackets, {"5m": atr5}, budget_sisa, eng_cfg, levs)
    out = []
    for r in tab["baris"]:
        x = r.get("x_atr", {}).get("5m") if "qty" in r else None
        if x is not None and x >= cfg.x_atr5m_min:
            out.append({"leverage": r["leverage"], "qty": r["qty"], "liq": r["liq"], "jarak_liq_pct": r["jarak_liq_pct"], "x_atr5m": x})
    return out


def _fmt_pct(x: Optional[float], digits: int = 1) -> str:
    return "tidak tersedia" if x is None else f"{x:+.{digits}f}%"


def ringkasan_kandidat(k: Kandidat) -> str:
    sisi = "di bawah" if k.level <= k.mark else "di atas"
    jejak = ", ".join(fl for fl in k.flags if fl != "DEKAT_LEVEL") or "-"
    lev = ", ".join(f"{d['leverage']}x liq {d['liq']:.6g} ({d['x_atr5m']:.1f}×ATR5m)" for d in k.lev_layak) or "tidak ada"
    return (f"{k.symbol} {k.arah_dugaan} skor {k.score} | mark {k.mark:.6g} | level {k.level:.6g} ({k.sentuhan} sentuhan {k.level_tf}, "
            f"{k.jarak_atr5m:.2f}×ATR5m {sisi}; {k.dasar_arah}) | jejak {jejak} | ATR5m {k.atr_5m:.6g} ({k.atr_5m / k.mark * 100:.2f}%) | "
            f"24j {_fmt_pct(k.pct_24h)} | funding {_fmt_pct(k.funding * 100 if k.funding is not None else None, 4)} | tren15m {k.tren_15m} | lev layak: {lev}")


def format_text(res: RunResult, cfg: PemindaiConfig, verbose: bool = False) -> str:
    tick = res.data_tick_ts
    umur = (res.ts - tick) // 1000 if tick else None
    sisa = f"${res.budget_sisa:.4f}" if res.budget_sisa is not None else "tidak tersedia"
    if not res.wake and not verbose:
        return f"PEMINDAI {fmt_wib(res.ts)} | tidak membangunkan agent: {res.alasan}\n{GATE_OFF}"
    lines = [f"PEMINDAI {fmt_wib(res.ts)} | data {fmt_wib(tick) if tick else 'tidak tersedia'}"
             + (f" (umur {umur} s)" if umur is not None else "") + f" | {res.n_symbols} simbol | budget tiket sisa {sisa} | wake hari ini {res.wake_hari_ini}/{cfg.max_wake_per_day}"]
    if res.alasan and not res.wake:
        lines.append(f"Tidak membangunkan agent: {res.alasan}")
    for k in res.kandidat:
        lines.append(f"{k.plan_id} {k.ringkasan}")
    if res.ditahan:
        lines.append("Ditahan: " + "; ".join(f"{d['symbol']} ({d['alasan']})" for d in res.ditahan))
    if verbose:
        lines.append("| simbol | mark | level | jarak×ATR5m | skor | flag | lev layak | keterangan |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for d in res.dipindai:
            lines.append(f"| {d.get('symbol')} | {d.get('mark', '-')} | {d.get('level', '-')} | {d.get('jarak_atr5m', '-')} | {d.get('score', '-')} | "
                         f"{','.join(d.get('flags', [])) or '-'} | {d.get('n_lev', '-')} | {d.get('keterangan', '')} |")
    if res.wake:
        ids = ", ".join(k.plan_id for k in res.kandidat)
        lines.append(f"Tindakan: jalankan skill tiket, nilai {ids}; pakai plan_id persis \"{res.kandidat[0].plan_id}\" dst. Paper trading.")
    lines.append(GATE_ON if res.wake else GATE_OFF)
    return "\n".join(lines)


def to_json(res: RunResult) -> dict:
    d = asdict(res)
    d["kandidat"] = [dict(asdict(k), plan_id=k.plan_id) for k in res.kandidat]
    return d


# --------------------------------------------------------------------------- pemindai
class Pemindai:
    def __init__(self, pasar: sqlite3.Connection, kandidat: sqlite3.Connection, engine: PaperEngine,
                 cfg: Optional[PemindaiConfig] = None, clock: Optional[Callable[[], int]] = None, log: Optional[logging.Logger] = None):
        self.pasar = pasar
        self.kand = kandidat
        self.engine = engine
        self.market = engine.market
        self.cfg = cfg or PemindaiConfig()
        self.clock = clock or C.now_ms
        self.log = log or logging.getLogger("pemindai")
        C.init_schema(kandidat, C.SCRIPTS_DIR / "schema_kandidat.sql", SCHEMA_VERSION)

    # ---- data
    def tick_ts(self) -> Optional[int]:
        v = C.meta_get(self.pasar, "last_tick_ms")
        return int(v) if v else None

    def universe(self) -> list[str]:
        r = self.pasar.execute("SELECT MAX(ts) FROM ticker_24h").fetchone()
        syms: list[str] = []
        if r and r[0] is not None:
            syms = [x[0] for x in self.pasar.execute(
                "SELECT symbol FROM ticker_24h WHERE ts=? AND rank<=? ORDER BY rank", (int(r[0]), self.cfg.top_n))]
        for s in self.engine.active_symbols():
            if s not in syms:
                syms.append(s)
        return syms

    def symbol_meta(self, symbol: str) -> tuple[Optional[float], Optional[float]]:
        t = self.pasar.execute("SELECT pct_24h FROM ticker_24h WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)).fetchone()
        m = self.pasar.execute("SELECT last_funding_rate FROM mark_snapshot WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)).fetchone()
        return (float(t[0]) if t and t[0] is not None else None), (float(m[0]) if m and m[0] is not None else None)

    # ---- gate
    def gate_awal(self, now: int, tick: Optional[int], budget_sisa: float, live_tiket: int, day: str) -> Optional[str]:
        cfg = self.cfg
        if tick is None:
            return "data tidak tersedia (collector belum pernah tick)"
        if now - tick > cfg.stale_s * 1000:
            return f"data basi: tick terakhir {(now - tick) // 60000} menit lalu"
        hhmm = C.to_wib(now).strftime("%H:%M")
        if hhmm < cfg.jam_mulai or hhmm >= cfg.jam_akhir:
            return f"di luar jam {cfg.jam_mulai}–{cfg.jam_akhir} WIB"
        if budget_sisa < cfg.budget_min:
            return f"budget tiket habis (sisa ${budget_sisa:.2f})"
        if live_tiket >= cfg.max_live_tiket:
            return f"sudah {live_tiket} order tiket hidup"
        hb = self.engine.hangus_beruntun(day)
        if hb >= cfg.max_hangus_beruntun:
            return f"{hb} tiket HANGUS beruntun hari ini (playbook P-09): berhenti sampai besok"
        w = self.wake_hari_ini(day)
        if w >= cfg.max_wake_per_day:
            return f"cap {cfg.max_wake_per_day} wake/hari tercapai"
        return None

    def wake_hari_ini(self, day: str) -> int:
        return int(self.kand.execute("SELECT COUNT(*) FROM pemindai_run WHERE day_wib=? AND wake=1", (day,)).fetchone()[0])

    def cooldown(self, symbol: str, score: int, now: int) -> Optional[str]:
        r = self.kand.execute("SELECT MAX(score), MAX(run_ts) FROM kandidat WHERE symbol=? AND run_ts>=?",
                              (symbol, now - self.cfg.cooldown_min * MINUTE_MS)).fetchone()
        if r and r[0] is not None and score <= int(r[0]):
            return f"cooldown: skor {score} ≤ {int(r[0])} pada {C.to_wib(int(r[1])).strftime('%H:%M')}"
        return None

    # ---- pindai
    def pindai_simbol(self, symbol: str, now: int, tick: Optional[int], budget_sisa: float) -> tuple[Optional[Kandidat], dict]:
        dbg: dict = {"symbol": symbol}
        f = self.market.filters(symbol)
        if f is None or f.status != "TRADING":
            dbg["keterangan"] = "simbol tidak TRADING"
            return None, dbg
        lm = self.market.last_mark(symbol)
        if not lm:
            dbg["keterangan"] = "tidak ada mark"
            return None, dbg
        mark = float(lm[0])
        dbg["mark"] = round(mark, 6)
        bars = A.load_bars(self.market, symbol, self.cfg.lookback_h, now)
        until = data_until_for(bars, tick, self.cfg.bar_grace_ms)
        fit = fitur_simbol(bars, mark, until, self.cfg)
        if fit is None:
            dbg["keterangan"] = "data kurang"
            return None, dbg
        if fit["level"] is None or fit["jarak_atr5m"] is None:
            dbg["keterangan"] = "tidak ada level ≥2 sentuhan"
            return None, dbg
        dbg["level"] = round(fit["level"]["price"], 6)
        dbg["jarak_atr5m"] = round(fit["jarak_atr5m"], 2)
        if fit["jarak_atr5m"] > self.cfg.max_jarak_atr5m:
            dbg["keterangan"] = f"jauh dari level ({fit['jarak_atr5m']:.1f}×ATR5m)"
            return None, dbg
        pct, funding = self.symbol_meta(symbol)
        arah, dasar = tentukan_arah(fit["level"], mark, fit["jejak"], fit["data_until"], fit["atr_5m"], self.cfg)
        score, flags = hitung_skor(fit, arah, pct, funding, self.cfg)
        lev = leverage_layak(arah, float(fit["level"]["price"]), f, self.market.brackets(symbol), fit["atr_5m"], budget_sisa, self.engine.cfg, self.cfg)
        k = Kandidat(symbol=symbol, arah_dugaan=arah, dasar_arah=dasar, mark=mark, level=float(fit["level"]["price"]),
                     sentuhan=int(fit["level"]["touches"]), level_tf=fit["level"]["tf"], jarak_atr5m=float(fit["jarak_atr5m"]),
                     atr_1m=fit["atr_1m"], atr_5m=fit["atr_5m"], atr_15m=fit["atr_15m"], atr_1h=fit["atr_1h"], pct_24h=pct, funding=funding,
                     tren_15m=fit["tren_15m"], lev_layak=lev, score=score, flags=flags, jejak=fit["jejak"][-6:])
        k.ringkasan = ringkasan_kandidat(k)
        dbg.update({"arah": arah, "score": score, "flags": flags, "n_lev": len(lev)})
        if score < self.cfg.score_min:
            dbg["keterangan"] = f"skor {score} < {self.cfg.score_min}"
            return None, dbg
        if not lev:
            dbg["keterangan"] = "tidak ada leverage dengan jarak liq ≥ 2×ATR5m untuk budget ini"
            return None, dbg
        dbg["keterangan"] = "kandidat"
        return k, dbg

    def run(self, now: Optional[int] = None, persist: bool = True, scan_even_if_gated: bool = False) -> RunResult:
        now = now if now is not None else self.clock()
        t0 = time.monotonic()
        day = C.day_wib(now)
        tick = self.tick_ts()
        res = RunResult(ts=now, day_wib=day, data_tick_ts=tick)
        try:
            bs = self.engine.budget_status(TIKET, day)
            res.budget_sisa = float(bs["remaining"])
            res.wake_hari_ini = self.wake_hari_ini(day)
            live = [o for o in self.engine.orders(TIKET) if not o.get("reduce_only")]
            gate = self.gate_awal(now, tick, res.budget_sisa, len(live), day)
            if gate and not scan_even_if_gated:
                res.alasan = gate
            else:
                syms = self.universe()
                res.n_symbols = len(syms)
                cands: list[Kandidat] = []
                for sym in syms:
                    if self.engine.has_exposure(sym):
                        res.ditahan.append({"symbol": sym, "alasan": "ada order/posisi", "score": None})
                        res.dipindai.append({"symbol": sym, "keterangan": "ada order/posisi"})
                        continue
                    k, dbg = self.pindai_simbol(sym, now, tick, res.budget_sisa)
                    res.dipindai.append(dbg)
                    if k is None:
                        continue
                    cd = self.cooldown(sym, k.score, now)
                    if cd:
                        res.ditahan.append({"symbol": sym, "alasan": cd, "score": k.score})
                        dbg["keterangan"] = cd
                        continue
                    cands.append(k)
                cands.sort(key=lambda x: (-x.score, x.jarak_atr5m))
                res.kandidat = cands[: self.cfg.top_k]
                if gate:
                    res.alasan = gate
                elif res.kandidat:
                    res.wake = True
                    res.alasan = f"{len(res.kandidat)} kandidat"
                else:
                    res.alasan = f"tidak ada kandidat ({res.n_symbols} simbol dipindai)"
        except Exception as e:  # noqa: BLE001 - pemindai tidak boleh menjatuhkan cron
            res.ok, res.err, res.wake = 0, f"{type(e).__name__}: {e}", False
            res.alasan = f"gagal: {res.err}"
            self.log.exception("pemindai gagal")
        finally:
            res.duration_ms = int((time.monotonic() - t0) * 1000)
            if persist:
                try:
                    self.persist(res)
                    self.retention(now)
                except Exception as e:  # noqa: BLE001
                    self.log.error("persist gagal: %s", e)
        self.log.info("run %s: wake=%s %s (%d simbol, %d ms)", fmt_wib(now), res.wake, res.alasan, res.n_symbols, res.duration_ms)
        return res

    def persist(self, res: RunResult) -> None:
        with C.tx(self.kand):
            self.kand.execute(
                "INSERT OR REPLACE INTO pemindai_run(ts,day_wib,data_tick_ts,n_symbols,n_kandidat,wake,alasan,budget_sisa,duration_ms,ok,err) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (res.ts, res.day_wib, res.data_tick_ts, res.n_symbols, len(res.kandidat) if res.wake else 0, int(res.wake), res.alasan,
                 res.budget_sisa, res.duration_ms, res.ok, res.err),
            )
            if res.wake:
                for k in res.kandidat:
                    cur = self.kand.execute(
                        "INSERT INTO kandidat(run_ts,day_wib,symbol,arah_dugaan,mark,level,sentuhan,jarak_atr5m,atr_1m,atr_5m,atr_15m,atr_1h,pct_24h,funding,lev_layak,score,flags,ringkasan) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (res.ts, res.day_wib, k.symbol, k.arah_dugaan, k.mark, k.level, k.sentuhan, k.jarak_atr5m, k.atr_1m, k.atr_5m, k.atr_15m, k.atr_1h,
                         k.pct_24h, k.funding, json.dumps(k.lev_layak), k.score, json.dumps(k.flags), k.ringkasan),
                    )
                    k.id = cur.lastrowid
        if res.wake:
            res.wake_hari_ini += 1

    def retention(self, now: int) -> None:
        day = C.day_wib(now)
        if C.meta_get(self.kand, "last_retention_day") == day:
            return
        cutoff = now - self.cfg.retention_days * C.DAY_MS
        with C.tx(self.kand):
            self.kand.execute("DELETE FROM kandidat WHERE run_ts<?", (cutoff,))
            self.kand.execute("DELETE FROM pemindai_run WHERE ts<?", (cutoff,))
            C.meta_set(self.kand, "last_retention_day", day)
        self.kand.execute("PRAGMA wal_checkpoint(TRUNCATE)")


# --------------------------------------------------------------------------- CLI
def build(cfg: PemindaiConfig, clock: Optional[Callable[[], int]] = None, log: Optional[logging.Logger] = None) -> Pemindai:
    pasar = C.connect(C.PASAR_DB, readonly=True)
    market = SqliteMarket(pasar)
    engine = PaperEngine(C.connect(C.PAPER_DB), market, clock=clock, log=log)
    return Pemindai(pasar, C.connect(KANDIDAT_DB), engine, cfg, clock, log)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Pemindai kandidat tiket mekanis (tanpa LLM).")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--cron", action="store_true", help="mode cron Hermes: simpan hasil, cetak ringkasan + baris gate")
    mode.add_argument("--once", action="store_true", help="uji manual: tanpa simpan, tabel per simbol")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--jam-mulai", default=None)
    ap.add_argument("--jam-akhir", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sekarang", default=None, help="override jam (ISO WIB) untuk uji")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    cron = args.cron or not args.once
    cfg = PemindaiConfig()
    if args.n:
        cfg.top_n = args.n
    if args.jam_mulai:
        cfg.jam_mulai = args.jam_mulai
    if args.jam_akhir:
        cfg.jam_akhir = args.jam_akhir
    clock = (lambda ms=C.parse_iso_ms(args.sekarang): ms) if args.sekarang else None
    log = C.setup_logging("pemindai", to_stderr=not cron)
    if not C.PASAR_DB.exists():
        print(f"PEMINDAI {fmt_wib(C.now_ms())} | tidak membangunkan agent: pasar.sqlite belum ada (collector belum jalan)")
        print(GATE_OFF)
        return 0
    try:
        if cron:
            with C.single_instance_lock("pemindai"):
                p = build(cfg, clock, log)
                res = p.run(persist=True)
        else:
            p = build(cfg, clock, log)
            res = p.run(persist=False, scan_even_if_gated=True)
    except C.AlreadyRunning:
        print(f"PEMINDAI {fmt_wib(C.now_ms())} | tidak membangunkan agent: pemindai masih berjalan")
        print(GATE_OFF)
        return 0
    if args.json:
        print(json.dumps(to_json(res), ensure_ascii=False, default=str))
        print(GATE_ON if res.wake else GATE_OFF)
    else:
        print(format_text(res, cfg, verbose=not cron))
    return 0


if __name__ == "__main__":
    sys.exit(main())
