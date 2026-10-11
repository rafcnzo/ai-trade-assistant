"""psikologi.py — panel psikologi pasar (§16.2), dikumpulkan mekanis tiap jam oleh cron Hermes `psikologi` (--no-agent).

Penulis tunggal data/psikologi.sqlite. Sumber: Fear & Greed (alternative.me), funding (pasar.sqlite), OI 24 jam + harga 24 jam
(Binance futures/data + kline_1h), L/S akun & top trader, taker buy/sell (Binance futures/data), likuidasi 24 jam (OKX, sampel
±100 order terakhir), premium Coinbase (vs Binance spot, dikoreksi USDT/USD), premium IDR (Indodax, via USDT/IDR), suplai
stablecoin 7 hari (DefiLlama). Setiap indikator diberi zona takut/serakah; TIDAK ADA skor gabungan. Sumber yang gagal ditulis
"tidak tersedia" beserta alasannya. Stdout `--cron` kosong (diam); `--once` mencetak panel.
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

import common as C  # noqa: E402
from common import HOUR_MS, NetError  # noqa: E402

SCHEMA_VERSION = "1"
PSIKOLOGI_DB = C.DATA_DIR / "psikologi.sqlite"
FAPI = "https://fapi.binance.com"
PASAR = "*"
TAKUT, NETRAL, SERAKAH, NA = "takut_ekstrem", "netral", "serakah_ekstrem", "tidak tersedia"
INDIKATOR_SIMBOL = ("funding", "oi_24h", "harga_24h", "ls_akun", "ls_top", "taker", "liq_long_24h", "liq_short_24h")
INDIKATOR_PASAR = ("fng", "premium_coinbase", "premium_idr", "stablecoin_7d")
# ambang awal §16.2: (takut ≤ lo, serakah ≥ hi)
ZONA_AWAL: dict[str, tuple[float, float]] = {
    "fng": (25, 75), "funding": (-0.0001, 0.0003), "ls_akun": (0.8, 2.0), "taker": (0.8, 1.2),
    "premium_coinbase": (-0.001, 0.001), "premium_idr": (0.0, 0.01), "stablecoin_7d": (-0.01, 0.01),
}
LABEL = {
    "fng": "Fear & Greed", "funding": "Funding rate (terakhir)", "oi_24h": "Δ OI 24 jam", "harga_24h": "Δ harga 24 jam",
    "ls_akun": "L/S rasio akun", "ls_top": "L/S top trader (posisi)", "taker": "Taker buy/sell (4 jam)",
    "liq_long_24h": "Likuidasi long 24 jam (n)", "liq_short_24h": "Likuidasi short 24 jam (n)",
    "premium_coinbase": "Premium Coinbase", "premium_idr": "Premium IDR (Indodax)", "stablecoin_7d": "Δ suplai stablecoin 7 hari",
}


@dataclass
class PsikologiConfig:
    symbols: tuple = ("BTCUSDT", "ETHUSDT")
    timeout: float = 12.0
    retries: int = 2
    basi_s: int = 3 * 3600
    retention_days: int = 400
    persentil_min_hari: int = 90
    kapitulasi_oi: float = -0.05
    kapitulasi_harga: float = -0.03
    penumpukan_oi: float = 0.10
    penumpukan_harga_abs: float = 0.01
    liq_dominan: float = 2.0


@dataclass
class Baris:
    ts: int
    symbol: str
    indikator: str
    nilai: Optional[float]
    zona: str
    sumber: str
    catatan: str = ""


# --------------------------------------------------------------------------- sumber jaringan
class Sumber:
    """Satu metode per endpoint; semua lewat common.http_get (DoH untuk host yang diblokir ISP)."""

    def __init__(self, cfg: PsikologiConfig):
        self.cfg = cfg
        C.RESOLVER.hosts.update({"api.exchange.coinbase.com", "www.okx.com"})
        C.ensure_resolver()

    def _get(self, url, params=None):
        data, _ = C.http_get(url, params, timeout=self.cfg.timeout, retries=self.cfg.retries)
        return data

    def fng(self) -> float:
        d = self._get("https://api.alternative.me/fng/", {"limit": 1})
        return float(d["data"][0]["value"])

    def oi_hist(self, symbol: str) -> list[tuple[int, float]]:
        d = self._get(f"{FAPI}/futures/data/openInterestHist", {"symbol": symbol, "period": "1h", "limit": 25})
        return [(int(x["timestamp"]), float(x["sumOpenInterestValue"])) for x in d]

    def ls_akun(self, symbol: str) -> float:
        d = self._get(f"{FAPI}/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": "1h", "limit": 1})
        return float(d[-1]["longShortRatio"])

    def ls_top(self, symbol: str) -> float:
        d = self._get(f"{FAPI}/futures/data/topLongShortPositionRatio", {"symbol": symbol, "period": "1h", "limit": 1})
        return float(d[-1]["longShortRatio"])

    def taker(self, symbol: str) -> list[float]:
        d = self._get(f"{FAPI}/futures/data/takerlongshortRatio", {"symbol": symbol, "period": "1h", "limit": 4})
        return [float(x["buySellRatio"]) for x in d]

    def liq_okx(self, uly: str, since_ms: int) -> tuple[int, int, int]:
        """(n_long, n_short, n_total_sampel) dari ±100 order likuidasi terakhir."""
        d = self._get("https://www.okx.com/api/v5/public/liquidation-orders", {"instType": "SWAP", "uly": uly, "state": "filled"})
        det = []
        for item in d.get("data", []):
            det += item.get("details", [])
        recent = [x for x in det if int(x.get("time", 0)) >= since_ms]
        n_long = sum(1 for x in recent if x.get("posSide") == "long")
        n_short = sum(1 for x in recent if x.get("posSide") == "short")
        return n_long, n_short, len(det)

    def spot_binance(self, symbol: str = "BTCUSDT") -> float:
        return float(self._get("https://api.binance.com/api/v3/ticker/price", {"symbol": symbol})["price"])

    def coinbase(self, product: str) -> float:
        return float(self._get(f"https://api.exchange.coinbase.com/products/{product}/ticker")["price"])

    def indodax(self, pair: str) -> float:
        return float(self._get(f"https://indodax.com/api/ticker/{pair}")["ticker"]["last"])

    def stablecoin(self) -> tuple[float, float]:
        """(suplai USD sekarang, suplai 7 hari lalu)."""
        d = self._get("https://stablecoins.llama.fi/stablecoincharts/all")
        rows = [(int(x["date"]), float(x["totalCirculatingUSD"]["peggedUSD"])) for x in d if x.get("totalCirculatingUSD", {}).get("peggedUSD")]
        rows.sort()
        now_s = rows[-1][0]
        past = [v for t_, v in rows if t_ <= now_s - 7 * 86400]
        if not past:
            raise NetError("riwayat stablecoin < 7 hari")
        return rows[-1][1], past[-1]


# --------------------------------------------------------------------------- data pasar lokal (readonly)
def funding_terakhir(pasar: sqlite3.Connection, symbol: str) -> Optional[float]:
    r = pasar.execute("SELECT last_funding_rate FROM mark_snapshot WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)).fetchone()
    return float(r[0]) if r and r[0] is not None else None


def harga_24h(pasar: sqlite3.Connection, symbol: str, now_ms: int) -> Optional[float]:
    """Perubahan relatif close 1h terakhir vs 24 bar sebelumnya (kline_1h)."""
    try:
        rows = pasar.execute("SELECT open_time, close FROM kline_1h WHERE symbol=? AND open_time<=? ORDER BY open_time DESC LIMIT 25",
                             (symbol, now_ms)).fetchall()
    except sqlite3.Error:
        return None
    if len(rows) < 25 or not rows[-1][1]:
        return None
    return float(rows[0][1]) / float(rows[-1][1]) - 1.0


# --------------------------------------------------------------------------- zona
def batas_zona(conn: Optional[sqlite3.Connection], indikator: str, symbol: str, cfg: PsikologiConfig) -> tuple[Optional[tuple[float, float]], str]:
    """(lo, hi) dan mode: 'persentil' bila riwayat ≥ persentil_min_hari hari, selain itu ambang awal §16.2."""
    awal = ZONA_AWAL.get(indikator)
    if conn is None:
        return awal, "awal"
    try:
        rows = [float(r[0]) for r in conn.execute(
            "SELECT nilai FROM panel WHERE indikator=? AND symbol=? AND nilai IS NOT NULL ORDER BY ts", (indikator, symbol))]
        hari = conn.execute("SELECT COUNT(DISTINCT ts/86400000) FROM panel WHERE indikator=? AND symbol=? AND nilai IS NOT NULL",
                            (indikator, symbol)).fetchone()[0]
    except sqlite3.Error:
        return awal, "awal"
    if hari < cfg.persentil_min_hari or len(rows) < 100:
        return awal, "awal"
    xs = sorted(rows)
    p = lambda q: xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]  # noqa: E731
    return (p(0.10), p(0.90)), "persentil"


def zona_dari_batas(nilai: Optional[float], batas: Optional[tuple[float, float]]) -> str:
    if nilai is None:
        return NA
    if batas is None:
        return NETRAL
    lo, hi = batas
    if nilai <= lo:
        return TAKUT
    if nilai >= hi:
        return SERAKAH
    return NETRAL


# --------------------------------------------------------------------------- pengumpulan
def _coba(fn: Callable, nama: str, log: logging.Logger):
    try:
        return fn(), ""
    except NetError as e:
        log.warning("%s: %s", nama, e)
        return None, f"{type(e).__name__}: {str(e)[:120]}"
    except (KeyError, IndexError, TypeError, ValueError) as e:
        log.warning("%s: format tak terduga: %s", nama, e)
        return None, f"format tak terduga: {type(e).__name__}"


def kumpulkan(now_ms: int, sumber, pasar: Optional[sqlite3.Connection], cfg: PsikologiConfig,
              conn: Optional[sqlite3.Connection] = None, log: Optional[logging.Logger] = None) -> tuple[list[Baris], str]:
    """Satu snapshot untuk semua simbol + pasar luas. Mengembalikan (baris, mode_zona)."""
    log = log or logging.getLogger("psikologi")
    out: list[Baris] = []
    modes: set[str] = set()

    def zona(ind: str, sym: str, nilai: Optional[float]) -> str:
        batas, mode = batas_zona(conn, ind, sym, cfg)
        modes.add(mode)
        return zona_dari_batas(nilai, batas)

    def add(sym, ind, nilai, src, cat="", z=None):
        out.append(Baris(now_ms, sym, ind, None if nilai is None else float(nilai), z if z is not None else zona(ind, sym, nilai), src, cat))

    for sym in cfg.symbols:
        fr = funding_terakhir(pasar, sym) if pasar is not None else None
        add(sym, "funding", fr, "pasar.sqlite mark_snapshot", "" if fr is not None else "tidak ada snapshot collector")
        oi, err = _coba(lambda: sumber.oi_hist(sym), f"oi_hist {sym}", log)
        oi_chg = None
        if oi and len(oi) >= 25 and oi[0][1]:
            oi_chg = oi[-1][1] / oi[0][1] - 1.0
        elif oi is not None:
            err = f"hanya {len(oi)} titik OI"
        px_chg = harga_24h(pasar, sym, now_ms) if pasar is not None else None
        z_oi, cat = NETRAL, ""
        if oi_chg is None:
            z_oi, cat = NA, err
        elif px_chg is None:
            cat = "harga 24j tidak tersedia (kline_1h)"
        elif oi_chg <= cfg.kapitulasi_oi and px_chg <= cfg.kapitulasi_harga:
            z_oi, cat = TAKUT, "kapitulasi: OI turun tajam + harga turun"
        elif oi_chg >= cfg.penumpukan_oi and abs(px_chg) < cfg.penumpukan_harga_abs:
            z_oi, cat = SERAKAH, "penumpukan leverage: OI naik > 10% + harga datar"
        add(sym, "oi_24h", oi_chg, "binance futures/data openInterestHist (nilai USD)", cat, z=z_oi)
        add(sym, "harga_24h", px_chg, "pasar.sqlite kline_1h", "" if px_chg is not None else "kline_1h < 25 bar", z=NETRAL if px_chg is not None else NA)
        v, err = _coba(lambda: sumber.ls_akun(sym), f"ls_akun {sym}", log)
        add(sym, "ls_akun", v, "binance globalLongShortAccountRatio 1h", err)
        v, err = _coba(lambda: sumber.ls_top(sym), f"ls_top {sym}", log)
        add(sym, "ls_top", v, "binance topLongShortPositionRatio 1h", err or "divergensi vs akun = catatan", z=NETRAL if v is not None else NA)
        tk, err = _coba(lambda: sumber.taker(sym), f"taker {sym}", log)
        tv = (sum(tk) / len(tk)) if tk else None
        add(sym, "taker", tv, "binance takerlongshortRatio 1h (rata-rata 4)", err)
        uly = sym.replace("USDT", "-USDT")
        lq, err = _coba(lambda: sumber.liq_okx(uly, now_ms - 24 * HOUR_MS), f"liq {sym}", log)
        if lq is None:
            add(sym, "liq_long_24h", None, "okx liquidation-orders", err, z=NA)
            add(sym, "liq_short_24h", None, "okx liquidation-orders", err, z=NA)
        else:
            nl, ns, ntot = lq
            cat = f"sampel {ntot} order terakhir OKX (terbatas)"
            zl = TAKUT if nl > cfg.liq_dominan * max(ns, 1) else NETRAL
            zs = SERAKAH if ns > cfg.liq_dominan * max(nl, 1) else NETRAL
            add(sym, "liq_long_24h", nl, "okx liquidation-orders", cat, z=zl)
            add(sym, "liq_short_24h", ns, "okx liquidation-orders", cat, z=zs)

    v, err = _coba(sumber.fng, "fng", log)
    add(PASAR, "fng", v, "alternative.me", err)
    spot, err_spot = _coba(lambda: sumber.spot_binance("BTCUSDT"), "spot", log)
    cb, err_cb = _coba(lambda: sumber.coinbase("BTC-USD"), "coinbase btc", log)
    usdt, err_usdt = _coba(lambda: sumber.coinbase("USDT-USD"), "coinbase usdt", log)
    if spot and cb and usdt:
        add(PASAR, "premium_coinbase", cb / (spot * usdt) - 1.0, "coinbase BTC-USD vs binance spot × USDT-USD", "dikoreksi USDT/USD")
    else:
        add(PASAR, "premium_coinbase", None, "coinbase/binance", err_spot or err_cb or err_usdt)
    btcidr, e1 = _coba(lambda: sumber.indodax("btcidr"), "indodax btc", log)
    usdtidr, e2 = _coba(lambda: sumber.indodax("usdtidr"), "indodax usdt", log)
    if spot and btcidr and usdtidr:
        add(PASAR, "premium_idr", btcidr / (usdtidr * spot) - 1.0, "indodax btcidr vs usdtidr × binance spot", "via USDT/IDR Indodax, bukan kurs resmi")
    else:
        add(PASAR, "premium_idr", None, "indodax/binance", err_spot or e1 or e2)
    st, err = _coba(sumber.stablecoin, "stablecoin", log)
    if st and st[1]:
        add(PASAR, "stablecoin_7d", st[0] / st[1] - 1.0, "defillama stablecoincharts/all", f"suplai ${st[0] / 1e9:.1f} M")
    else:
        add(PASAR, "stablecoin_7d", None, "defillama", err)
    mode = "persentil" if modes == {"persentil"} else ("campuran" if "persentil" in modes else "awal")
    return out, mode


# --------------------------------------------------------------------------- divergensi & ringkasan
def divergensi(nilai: dict) -> list[str]:
    """nilai: {indikator: float|None} untuk satu simbol (+ pasar luas digabung). Divergensi sering lebih penting dari angka tunggal."""
    out = []
    g = nilai.get
    if g("harga_24h") is not None and g("oi_24h") is not None and g("harga_24h") > 0.01 and g("oi_24h") < -0.02:
        out.append("harga naik tapi OI turun: rally karena short tertutup, bukan pembeli baru")
    if g("harga_24h") is not None and g("oi_24h") is not None and g("harga_24h") < -0.01 and g("oi_24h") > 0.02:
        out.append("harga turun tapi OI naik: short baru masuk mengejar harga (rawan squeeze)")
    if g("funding") is not None and g("taker") is not None and g("funding") > 0.0002 and g("taker") < 0.9:
        out.append("funding tinggi (long membayar) tapi taker sell dominan: long bertahan melawan penjual agresif")
    if g("ls_akun") is not None and g("ls_top") is not None and g("ls_akun") > 1.5 and g("ls_top") < 1.0:
        out.append("ritel mayoritas long, top trader net short: kerumunan melawan uang besar")
    if g("ls_akun") is not None and g("ls_top") is not None and g("ls_akun") < 0.8 and g("ls_top") > 1.2:
        out.append("ritel mayoritas short, top trader net long")
    if g("premium_coinbase") is not None and g("fng") is not None and g("premium_coinbase") < -0.0005 and g("fng") > 60:
        out.append("sentimen serakah tapi premium Coinbase negatif: tanpa permintaan spot AS")
    return out


def snapshot_terakhir(conn: sqlite3.Connection, symbol: str, before_ms: Optional[int] = None) -> list[dict]:
    q = "SELECT MAX(ts) FROM panel WHERE symbol=?" + (" AND ts<=?" if before_ms else "")
    r = conn.execute(q, (symbol, before_ms) if before_ms else (symbol,)).fetchone()
    if not r or r[0] is None:
        return []
    ts = int(r[0])
    rows = conn.execute("SELECT * FROM panel WHERE ts=? AND symbol IN (?, ?) ORDER BY symbol DESC, indikator", (ts, symbol, PASAR)).fetchall()
    return [dict(x) for x in rows]


def panel_untuk(conn: sqlite3.Connection, symbol: str, now_ms: int, cfg: Optional[PsikologiConfig] = None) -> dict:
    cfg = cfg or PsikologiConfig()
    rows = snapshot_terakhir(conn, symbol)
    if not rows:
        return {"symbol": symbol, "status": NA, "alasan": "belum ada snapshot untuk simbol ini (cron psikologi belum jalan)"}
    ts = int(rows[0]["ts"])
    umur = (now_ms - ts) // 1000
    nilai = {r["indikator"]: r["nilai"] for r in rows}
    lalu = {r["indikator"]: r["nilai"] for r in snapshot_terakhir(conn, symbol, ts - 24 * HOUR_MS + 1)}
    perubahan = {k: (nilai[k] - lalu[k]) for k in nilai if nilai.get(k) is not None and lalu.get(k) is not None}
    run = conn.execute("SELECT mode_zona FROM panel_run WHERE ts=?", (ts,)).fetchone()
    return {
        "symbol": symbol, "ts": ts, "waktu": C.fmt_wib(ts), "umur_s": umur, "status": "OK" if umur <= cfg.basi_s else "BASI",
        "indikator": [{"indikator": r["indikator"], "label": LABEL.get(r["indikator"], r["indikator"]), "symbol": r["symbol"], "nilai": r["nilai"],
                       "zona": r["zona"], "sumber": r["sumber"], "catatan": r["catatan"]} for r in rows],
        "takut_ekstrem": sum(1 for r in rows if r["zona"] == TAKUT), "serakah_ekstrem": sum(1 for r in rows if r["zona"] == SERAKAH),
        "tidak_tersedia": sum(1 for r in rows if r["zona"] == NA),
        "divergensi": divergensi(nilai), "perubahan_24j": perubahan, "mode_zona": run["mode_zona"] if run else "awal",
        "catatan": "tidak ada skor gabungan: baca indikator dan divergensinya masing-masing; likuidasi OKX sampel terbatas; premium IDR via USDT/IDR",
    }


def _fmt(ind: str, v) -> str:
    if v is None:
        return "tidak tersedia"
    if ind in ("funding", "premium_coinbase", "premium_idr"):
        return f"{v * 100:+.4f}%"
    if ind in ("oi_24h", "harga_24h", "stablecoin_7d"):
        return f"{v * 100:+.2f}%"
    if ind.startswith("liq_"):
        return f"{int(v)}"
    return f"{v:.3f}" if ind != "fng" else f"{v:.0f}"


def ringkas_teks(panel: dict) -> str:
    if panel.get("status") == NA:
        return f"Panel psikologi {panel['symbol']}: tidak tersedia — {panel['alasan']}"
    lines = [f"# Panel psikologi {panel['symbol']} — {panel['waktu']} (umur {panel['umur_s']} s, {panel['status']}, zona: {panel['mode_zona']})",
             "", "| indikator | nilai | zona | sumber | catatan |", "|---|---|---|---|---|"]
    for r in panel["indikator"]:
        lines.append(f"| {r['label']} | {_fmt(r['indikator'], r['nilai'])} | {r['zona']} | {r['sumber']} | {r['catatan']} |")
    lines += ["", f"Takut ekstrem: {panel['takut_ekstrem']} · Serakah ekstrem: {panel['serakah_ekstrem']} · Tidak tersedia: {panel['tidak_tersedia']} (tidak ada skor gabungan)"]
    lines += ["Divergensi: " + ("; ".join(panel["divergensi"]) if panel["divergensi"] else "tidak ada")]
    return "\n".join(lines)


# --------------------------------------------------------------------------- simpan & run
def simpan(conn: sqlite3.Connection, baris: list[Baris], mode: str, ok: int, err: Optional[str], duration_ms: int) -> None:
    with C.tx(conn):
        conn.executemany("INSERT OR REPLACE INTO panel(ts,symbol,indikator,nilai,zona,sumber,catatan) VALUES(?,?,?,?,?,?,?)",
                         [(b.ts, b.symbol, b.indikator, b.nilai, b.zona, b.sumber, b.catatan) for b in baris])
        n_gagal = sum(1 for b in baris if b.nilai is None)
        if baris:
            conn.execute("INSERT OR REPLACE INTO panel_run(ts,ok,n_ok,n_gagal,mode_zona,err,duration_ms) VALUES(?,?,?,?,?,?,?)",
                         (baris[0].ts, ok, len(baris) - n_gagal, n_gagal, mode, err, duration_ms))


def retention(conn: sqlite3.Connection, now_ms: int, cfg: PsikologiConfig) -> None:
    cutoff = now_ms - cfg.retention_days * C.DAY_MS
    with C.tx(conn):
        conn.execute("DELETE FROM panel WHERE ts<?", (cutoff,))
        conn.execute("DELETE FROM panel_run WHERE ts<?", (cutoff,))


def run(conn: sqlite3.Connection, pasar: Optional[sqlite3.Connection], sumber, now_ms: int, cfg: Optional[PsikologiConfig] = None,
        log: Optional[logging.Logger] = None) -> dict:
    cfg = cfg or PsikologiConfig()
    log = log or logging.getLogger("psikologi")
    C.init_schema(conn, C.SCRIPTS_DIR / "schema_psikologi.sql", SCHEMA_VERSION)
    t0 = time.monotonic()
    baris, mode, err = [], "awal", None
    try:
        baris, mode = kumpulkan(now_ms, sumber, pasar, cfg, conn, log)
        ok = 1
    except Exception as e:  # noqa: BLE001 - cron tidak boleh jatuh
        ok, err = 0, f"{type(e).__name__}: {e}"
        log.exception("psikologi gagal")
    dur = int((time.monotonic() - t0) * 1000)
    simpan(conn, baris, mode, ok, err, dur)
    retention(conn, now_ms, cfg)
    n_gagal = sum(1 for b in baris if b.nilai is None)
    log.info("run %s: %d indikator, %d tidak tersedia, zona %s, %d ms", C.fmt_wib(now_ms), len(baris), n_gagal, mode, dur)
    return {"ts": now_ms, "ok": ok, "n": len(baris), "n_gagal": n_gagal, "mode": mode, "err": err, "duration_ms": dur}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Panel psikologi pasar (§16.2) — kumpulkan & simpan; tanpa LLM.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cron", action="store_true", help="kumpulkan & simpan, diam (default)")
    g.add_argument("--once", action="store_true", help="kumpulkan & simpan, cetak panel")
    g.add_argument("--lihat", action="store_true", help="hanya cetak panel terakhir dari DB")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sekarang", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    log = C.setup_logging("psikologi", to_stderr=bool(args.once or args.lihat))
    cfg = PsikologiConfig()
    now = C.parse_iso_ms(args.sekarang) if args.sekarang else C.now_ms()
    conn = C.connect(PSIKOLOGI_DB)
    try:
        if not args.lihat:
            pasar = C.connect(C.PASAR_DB, readonly=True) if C.PASAR_DB.exists() else None
            try:
                with C.single_instance_lock("psikologi"):
                    run(conn, pasar, Sumber(cfg), now, cfg, log)
            except C.AlreadyRunning:
                return 0
            finally:
                if pasar is not None:
                    pasar.close()
        if args.once or args.lihat:
            p = panel_untuk(conn, args.symbol, now, cfg)
            print(json.dumps(p, ensure_ascii=False, default=str) if args.json else ringkas_teks(p))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
