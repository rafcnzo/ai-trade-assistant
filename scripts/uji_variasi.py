"""uji_variasi.py — uji susunan tiket lain pada kandidat radar yang sudah ada (hanya membaca, tanpa LLM, tidak menulis DB).

Pertanyaan: adakah kombinasi leverage / target / stop loss yang rata-ratanya positif setelah fee?
Agar hasil terbaik dari banyak kombinasi tidak sekadar kebetulan: kandidat dibagi dua menurut hari; variasi dipilih dari paruh awal
dan hanya dinilai di paruh akhir. Selang keyakinan memakai bootstrap per hari karena kandidat satu hari saling terkait.
Cara masuk (`saring`): semua/searah = limit di level; kebalikan = ikut tembusan (lawan arah kandidat, market setelah bar 1m menutup di balik level);
konfirmasi = arah kandidat, market setelah candle 5m menyentuh level lalu menutup kembali di sisinya; konfirmasi_wick = idem, hanya kandidat bertanda WICK.
Kebalikan dan konfirmasi harus terjadi dalam 240 menit sejak kandidat. Batas: satu rezim pasar, order keluar paling lambat 23:50.

    .venv/Scripts/python.exe scripts/uji_variasi.py [--json]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
import kontrafaktual as K  # noqa: E402
from paper_engine import LONG, EngineConfig, SqliteMarket, fee_amount, liq_price, pick_bracket  # noqa: E402

LEVERAGE = (5, 10, 25, 50)
TP_ATR = (1.0, 1.5, 2.0, 3.0)
SL_ATR = (None, 0.5, 1.0, 1.5)
MARGIN = 1.0
MIN_N = 30
BOOTSTRAP = 2000
BATAS_MNT = 240
CARA_MASUK = ("kebalikan", "konfirmasi", "konfirmasi_wick")


def titik_masuk(cara: str, k: dict, pairs: list) -> Optional[tuple[str, int, float]]:
    """(sisi, open_time bar entry, harga open) untuk entry market; None bila syaratnya tidak terjadi. Hanya memakai bar yang sudah tutup."""
    long = k["arah_dugaan"] == LONG
    level = float(k["level"])
    batas = int(k["run_ts"]) + BATAS_MNT * C.MINUTE_MS
    bars = [b for b, _ in pairs if b.open_time >= C.ceil_minute(int(k["run_ts"]) + 1)]
    if cara == "kebalikan":
        for i, b in enumerate(bars[:-1]):
            if b.open_time > batas:
                return None
            if (long and b.close < level) or (not long and b.close > level):
                return ("SHORT" if long else "LONG"), bars[i + 1].open_time, bars[i + 1].open
        return None
    if cara == "konfirmasi_wick" and '"WICK"' not in (k.get("flags") or ""):
        return None
    tf = 5 * C.MINUTE_MS
    rendah, tinggi, awal = None, None, None
    for i, b in enumerate(bars[:-1]):
        if b.open_time > batas:
            return None
        ember = b.open_time // tf
        if ember != awal:
            awal, rendah, tinggi = ember, b.low, b.high
        rendah, tinggi = min(rendah, b.low), max(tinggi, b.high)
        if (b.open_time + C.MINUTE_MS) % tf == 0:   # candle 5m baru dianggap tutup di menit terakhirnya
            if (long and rendah < level and b.close > level) or (not long and tinggi > level and b.close < level):
                return k["arah_dugaan"], bars[i + 1].open_time, bars[i + 1].open
    return None


def templat_variasi(k: dict, f, brackets: list, lev: int, tp_atr: float, sl_atr: Optional[float], cfg: Optional[EngineConfig] = None,
                    masuk: Optional[tuple[str, int, float]] = None) -> Optional[dict]:
    """Templat simulasi untuk satu susunan; None bila mesin paper akan menolaknya (qty, nilai minimum, leverage, SL di luar likuidasi)."""
    cfg = cfg or EngineConfig()
    atr = k.get("atr_15m")
    if not f or not brackets or not atr or atr <= 0:
        return None
    side = masuk[0] if masuk else k["arah_dugaan"]
    long = side == LONG
    arah_r = "down" if long else "up"
    entry = float(C.round_step(C.D(str(masuk[2] if masuk else k["level"])), f.tick_size, arah_r))
    if entry <= 0:
        return None
    biaya_per_notional = 1 / lev + fee_amount(1.0, not masuk, cfg)         # batas satu tiket $1 termasuk fee masuk
    qty_d = C.round_step(C.D(str(MARGIN / biaya_per_notional / entry)), f.qty_step, "down")
    qty = float(qty_d)
    notional = qty * entry
    if qty <= 0 or qty_d < f.min_qty or C.D(str(notional)) < f.min_notional:
        return None
    b = pick_bracket(brackets, notional)
    if b is None or lev > b.max_leverage:
        return None
    margin = notional / lev
    liq = liq_price(side, qty, entry, margin, b.mmr, b.cum)
    sgn = 1 if long else -1
    tp = float(C.round_step(C.D(str(entry + sgn * tp_atr * atr)), f.tick_size, arah_r))
    sl = float(C.round_step(C.D(str(entry - sgn * sl_atr * atr)), f.tick_size, "up" if long else "down")) if sl_atr else None
    if sl is not None and ((long and liq >= sl) or (not long and liq <= sl)):
        return None
    run_ts = int(k["run_ts"])
    return {"side": side, "entry": entry, "tp": tp, "sl": sl, "lev": lev, "qty": qty, "margin": margin, "mmr": b.mmr, "cum": b.cum,
            "aktif_ms": masuk[1] if masuk else C.ceil_minute(run_ts + 1), "eod_ms": C.wib_clock_ms(run_ts, K.EOD_WIB),
            **({"market_ms": masuk[1]} if masuk else {})}


def ringkas(baris: list[tuple[str, float]]) -> Optional[dict]:
    """baris = [(hari, net)] order terisi."""
    if not baris:
        return None
    nets = [n for _, n in baris]
    untung = sum(n for n in nets if n > 0)
    rugi = -sum(n for n in nets if n < 0)
    return {"n": len(nets), "mean": sum(nets) / len(nets), "menang": sum(1 for n in nets if n > K.NET_EPS) / len(nets), "total": sum(nets),
            "pf": (untung / rugi) if rugi else None}


def selang_per_hari(baris: list[tuple[str, float]], seed: int = 7, ulang: int = BOOTSTRAP) -> Optional[tuple[float, float]]:
    """Selang 90 % rata-rata per order; hari diambil ulang utuh."""
    per: dict[str, list[float]] = {}
    for h, n in baris:
        per.setdefault(h, []).append(n)
    hari = list(per)
    if len(hari) < 2:
        return None
    rng = random.Random(seed)
    hasil = []
    for _ in range(ulang):
        xs = [x for h in rng.choices(hari, k=len(hari)) for x in per[h]]
        hasil.append(sum(xs) / len(xs))
    hasil.sort()
    return hasil[int(0.05 * ulang)], hasil[int(0.95 * ulang)]


def bagi_hari(semua_hari: list[str]) -> set[str]:
    """Paruh awal hari (untuk memilih)."""
    h = sorted(set(semua_hari))
    return set(h[: len(h) // 2])


def nilai_variasi(hasil: dict, hari_latih: set[str], min_n: int = MIN_N) -> list[dict]:
    """hasil = {(lev, tp, sl, saring): [(hari, net)]}. Urut menurut rata-rata paruh awal. Lolos hanya bila kedua paruh dan batas bawah selang positif."""
    out = []
    for v, baris in hasil.items():
        latih = [b for b in baris if b[0] in hari_latih]
        uji = [b for b in baris if b[0] not in hari_latih]
        rl, ru = ringkas(latih), ringkas(uji)
        if not rl or not ru or rl["n"] < min_n or ru["n"] < min_n:
            continue
        out.append({"lev": v[0], "tp": v[1], "sl": v[2], "saring": v[3], "latih": rl, "uji": ru, "semua": ringkas(baris)})
    out.sort(key=lambda r: -r["latih"]["mean"])
    for r in out:
        baris = hasil[(r["lev"], r["tp"], r["sl"], r["saring"])]
        r["selang_uji"] = selang_per_hari([b for b in baris if b[0] not in hari_latih])
        r["lolos"] = r["latih"]["mean"] > 0 and r["uji"]["mean"] > 0 and bool(r["selang_uji"]) and r["selang_uji"][0] > 0
    return out


def jalankan(pasar, kand) -> dict:
    market = SqliteMarket(pasar)
    rows = [dict(r) for r in kand.execute("SELECT * FROM kandidat ORDER BY id")]
    hasil: dict = {}
    tak_terisi = tak_boleh = dipakai = 0
    tanpa_data = 0
    slip_cache: dict = {}
    cfg = EngineConfig()
    for k in rows:
        f, br = market.filters(k["symbol"]), market.brackets(k["symbol"])
        if not f or not br or not k.get("atr_15m"):
            tanpa_data += 1
            continue
        eod = C.wib_clock_ms(int(k["run_ts"]), K.EOD_WIB)
        pairs = market.bars(k["symbol"], C.ceil_minute(int(k["run_ts"]) + 1) - C.MINUTE_MS, eod)
        slip = slip_cache.setdefault(k["symbol"], cfg.slippage.get(market.tier(k["symbol"]), cfg.slippage["small"]))
        try:
            flags = json.loads(k["flags"] or "[]")
        except ValueError:
            flags = []
        melawan = "MELAWAN_TREN_15M" in flags
        ada = False
        titik = {c: titik_masuk(c, k, pairs) for c in CARA_MASUK}
        for lev in LEVERAGE:
            for tp in TP_ATR:
                for sl in SL_ATR:
                    t = templat_variasi(k, f, br, lev, tp, sl, cfg)
                    if t is None:
                        tak_boleh += 1
                        continue
                    s = K.simulasi(t, pairs, slip, cfg)
                    if s["hasil"] == "ambigu":
                        continue
                    ada = True
                    if s["hasil"] == "TIDAK_TERISI":
                        tak_terisi += 1
                        continue
                    hasil.setdefault((lev, tp, sl, "semua"), []).append((k["day_wib"], float(s["net"])))
                    if not melawan:
                        hasil.setdefault((lev, tp, sl, "searah"), []).append((k["day_wib"], float(s["net"])))
                    for cara, m in titik.items():
                        if m is None:
                            continue
                        t2 = templat_variasi(k, f, br, lev, tp, sl, cfg, m)
                        if t2 is None:
                            continue
                        s2 = K.simulasi(t2, pairs, slip, cfg)
                        if s2["hasil"] not in ("ambigu", "TIDAK_TERISI") and s2.get("net") is not None:
                            hasil.setdefault((lev, tp, sl, cara), []).append((k["day_wib"], float(s2["net"])))
        dipakai += 1 if ada else 0
    hari = [k["day_wib"] for k in rows]
    latih = bagi_hari(hari)
    return {"n_kandidat": len(rows), "n_dipakai": dipakai, "tanpa_data": tanpa_data, "n_variasi": len(hasil), "hari": sorted(set(hari)),
            "hari_latih": sorted(latih), "baris": nilai_variasi(hasil, latih)}


def _u(x: float) -> str:
    return ("+" if x > 0 else "−" if x < 0 else "") + "$" + f"{abs(x):.3f}".replace(".", ",")


def _nama(r: dict) -> str:
    return f"{r['lev']}× · TP {r['tp']:g} · " + (f"SL {r['sl']:g}" if r["sl"] else "tanpa SL") + {"semua": "", "searah": " · searah tren"}.get(r["saring"], " · " + r["saring"])


def render(o: dict) -> str:
    b = o["baris"]
    lines = [f"# Uji variasi tiket ({o['hari'][0]} s.d. {o['hari'][-1]})", "",
             f"{o['n_kandidat']} kandidat, {o['n_dipakai']} punya data harga 1 menit; {len(b)} variasi ber-sampel cukup. "
             f"Paruh awal {o['hari_latih'][0]}…{o['hari_latih'][-1]} untuk memilih, sisanya untuk menguji. TP/SL dalam kelipatan ATR 15m; margin $1.", ""]
    lolos = [r for r in b if r["lolos"]]
    lines += [f"**Lolos (kedua paruh positif dan batas bawah selang > 0): {len(lolos)} dari {len(b)}.**",
              f"Paruh awal positif: {sum(r['latih']['mean'] > 0 for r in b)}; paruh akhir positif: {sum(r['uji']['mean'] > 0 for r in b)}; keduanya: {sum(r['latih']['mean'] > 0 and r['uji']['mean'] > 0 for r in b)}.", ""]
    head = "| Variasi | Paruh awal | Paruh akhir (n) | Menang akhir | Selang 90 % akhir | Lolos |"
    lines += ["## 12 teratas menurut paruh awal", "", head, "|---|---|---|---|---|---|"]
    for r in b[:12]:
        sel = f"{_u(r['selang_uji'][0])} … {_u(r['selang_uji'][1])}" if r["selang_uji"] else "tidak tersedia"
        lines.append(f"| {_nama(r)} | {_u(r['latih']['mean'])} | {_u(r['uji']['mean'])} ({r['uji']['n']}) | {r['uji']['menang']:.0%} | {sel} | {'ya' if r['lolos'] else 'tidak'} |")
    lines += ["", "## Pengaruh tiap pilihan (rata-rata semua data, tanpa saringan arah)", ""]
    for judul, kunci in (("Leverage", "lev"), ("Target", "tp"), ("Stop loss", "sl")):
        g: dict = {}
        for r in b:
            if r["saring"] == "semua":
                g.setdefault(r[kunci], []).append(r["semua"]["mean"])
        lines.append(f"- {judul}: " + " · ".join(f"{('tanpa' if a is None else a)}: {_u(sum(x) / len(x))}" for a, x in sorted(g.items(), key=lambda t: (t[0] is not None, t[0] or 0))))
    lines += ["", "## Per cara masuk", "", "| Cara masuk | Variasi | Positif paruh awal | Positif paruh akhir | Keduanya | Lolos | Rata-rata per $100 |", "|---|---|---|---|---|---|---|"]
    for cara in ("semua", "searah") + CARA_MASUK:
        rs = [r for r in b if r["saring"] == cara]
        if rs:
            per100 = sum(r["semua"]["mean"] / (MARGIN * r["lev"]) * 100 for r in rs) / len(rs)
            lines.append(f"| {cara} | {len(rs)} | {sum(r['latih']['mean'] > 0 for r in rs)} | {sum(r['uji']['mean'] > 0 for r in rs)} | "
                         f"{sum(r['latih']['mean'] > 0 and r['uji']['mean'] > 0 for r in rs)} | {sum(r['lolos'] for r in rs)} | {_u(per100)} |")
    lines.append("")
    per_lev: dict = {}
    for r in b:
        if r["saring"] == "semua":
            per_lev.setdefault(r["lev"], []).append(r["semua"]["mean"] / (MARGIN * r["lev"]) * 100)
    lines.append("- Per $100 nilai posisi (leverage kecil rugi lebih sedikit karena posisinya kecil, bukan karena lebih pintar): "
                 + " · ".join(f"{lv}×: {_u(sum(x) / len(x))}" for lv, x in sorted(per_lev.items())))
    kedua = [r for r in b if r["latih"]["mean"] > 0 and r["uji"]["mean"] > 0]
    if kedua:
        lines.append("- Positif di kedua paruh: " + "; ".join(f"{_nama(r)} ({_u(r['latih']['mean'])} / {_u(r['uji']['mean'])}, n={r['uji']['n']})" for r in kedua))
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Uji variasi leverage/TP/SL pada kandidat radar (hanya membaca).")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    pasar = C.connect(C.PASAR_DB, readonly=True)
    kand = C.connect(C.DATA_DIR / "kandidat.sqlite", readonly=True)
    try:
        o = jalankan(pasar, kand)
    finally:
        pasar.close()
        kand.close()
    print(json.dumps(o, ensure_ascii=False, default=str) if args.json else render(o))
    return 0


if __name__ == "__main__":
    sys.exit(main())
