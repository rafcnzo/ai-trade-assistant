"""kontrafaktual.py — menilai keputusan SKIP agent dengan order bayangan mekanis (tanpa LLM, fungsi murni).

Setiap kandidat pemindai (data/kandidat.sqlite) mendapat SATU templat order yang sama untuk semua persona:
  sisi = arah_dugaan, limit di level (dibulatkan menjauh dari mark), leverage layak terendah dari lev_layak ($1 tiket),
  TP = level ± 1,5×ATR15m (batas atas aturan tiket P-04), tanpa SL + pengaman breakeven P-18, kedaluwarsa/keluar 23:50 WIB.
Simulasi bar 1 menit mengikuti urutan PaperEngine._process_bar (EOD → breakeven dari bar sebelumnya → likuidasi → stop → TP;
bar entry hanya cek likuidasi). Hasil: TP | HANGUS | STOP_BE | EOD | TIDAK_TERISI | ambigu, plus net setelah fee.
Label SKIP persona: benar (net < 0), salah (net > 0, peluang terlewat), netral (tidak terisi / ≈ 0), ambigu.

Dipakai oleh scripts/uji_hipotesis.py (penulis tunggal pasar/skip-hasil.jsonl, pasar/skip.md, pasar/pelajaran.*).
"""
from __future__ import annotations

import json
import re
from typing import Iterable, Optional

import common as C
from common import MINUTE_MS, MarkBar
from paper_engine import LONG, SHORT, EngineConfig, fee_amount, liq_hit, liq_price, limit_fill, pick_bracket, stop_trigger

VERSI = 1
TP_ATR15 = 1.5            # TP templat = 1,5 × ATR 15m dari entry (batas atas aturan tiket)
P19_RR = 0.5              # R:R minimum tiket (P-19) — dicatat, tidak memfilter
BREAKEVEN_MFE = 0.8       # P-18
EOD_WIB = "23:50"
MIN_COVERAGE = 0.9
NET_EPS = 1e-4
LS_MIN_SAMPEL = 15        # SKIP non-netral per kelompok sebelum pelajaran
LS_MARGIN = 0.15          # selisih akurasi vs baseline untuk promosi
LS_PENSIUN = 0.05
LS_JENDELA_HARI = 30
LS_NILAI_ULANG_HARI = 30
LS_MAX_AKTIF = 15

KATEGORI = ("RR_P19", "TP_ATR15", "TREN_15M", "SENTUHAN", "LIQ_ATR5", "SUDAH_LARI", "FUNDING", "BASI", "LIMIT_CROSSES",
            "BUDGET", "EOD", "DUPLIKAT", "PANEL_FADE", "NO_VOL_TEMBUS", "NO_SIDEWAYS", "PLAYBOOK", "LAIN")
KATEGORI_ARTI = {
    "RR_P19": "untung di TP < 0,5× risiko hangus (P-19)", "TP_ATR15": "TP terlalu jauh dari 1,5×ATR 15m",
    "TREN_15M": "melawan tren 15m / tidak searah", "SENTUHAN": "level kurang sentuhan / penolakan belum jelas",
    "LIQ_ATR5": "jarak likuidasi < 2×ATR 5m", "SUDAH_LARI": "harga sudah lari / mengejar", "FUNDING": "funding ekstrem melawan",
    "BASI": "data atau panel basi", "LIMIT_CROSSES": "limit memotong mark", "BUDGET": "saldo/jatah tidak cukup",
    "EOD": "terlalu dekat jam tutup", "DUPLIKAT": "sudah ada order/posisi di simbol", "PANEL_FADE": "panel psikologi tidak ekstrem/tanpa divergensi (fade)",
    "NO_VOL_TEMBUS": "tidak ada VOL / tidak tembus (breakout)", "NO_SIDEWAYS": "tidak sideways / tanpa kompresi (rentang)",
    "PLAYBOOK": "melanggar aturan playbook lain", "LAIN": "lainnya",
}

# urutan penting: alasan administratif dulu, lalu syarat persona, lalu syarat teknis umum
_KATA = [
    ("BASI", r"\bbasi\b"),
    ("LIMIT_CROSSES", r"limit_crosses|memotong mark|sudah lewat level"),
    ("BUDGET", r"budget_tiket|boleh_buka|saldo .*(habis|tidak cukup|< ?\$?0[,.]5)|jatah habis"),
    ("EOD", r"\beod\b|22[:.]30|menit_ke_eod|jam tutup"),
    ("DUPLIKAT", r"sudah ada (order|posisi)|order hidup|duplikat|sudah 2 order"),
    ("RR_P19", r"p-19|u-001|r:r|0[,.]5\s*[×x]"),
]
_PERSONA_KATA = {
    "fade": [("PANEL_FADE", r"divergensi|ekstrem|panel")],
    "breakout": [("NO_VOL_TEMBUS", r"\bvol\b|tembus|breakout")],
    "rentang": [("NO_SIDEWAYS", r"sideways|kompresi|range|rentang")],
}
_UMUM_KATA = [
    ("SUDAH_LARI", r"sudah_lari|sudah lari|mengejar|rsi\w* ?[7-9]\d"),
    ("TREN_15M", r"melawan tren|tren 15m|searah|counter.?trend"),
    ("SENTUHAN", r"sentuhan|penolakan|wick|level baru"),
    ("LIQ_ATR5", r"liq|×atr ?5m|x_atr|2[,.]?\d*\s*×\s*atr"),
    ("TP_ATR15", r"atr ?15m|tp terlalu"),
    ("FUNDING", r"funding"),
    ("PANEL_FADE", r"divergensi"),
    ("NO_VOL_TEMBUS", r"\bvol\b"),
    ("NO_SIDEWAYS", r"sideways|kompresi"),
    ("PLAYBOOK", r"\bp-\d\d\b|playbook"),
]


# --------------------------------------------------------------------------- keputusan dari jurnal
_HEAD = re.compile(r"^## (\d{2}):(\d{2}) WIB — (\w+) — (.+)$")
_META = re.compile(r"^_(.+)_$")
_K = re.compile(r"K(\d+)(?:\s*[-–]\s*K?(\d+))?")
_PERSONA = re.compile(r"^\[(\w+)\]")
_POIN_HEAD = re.compile(r"^\*\*Alasan (SKIP|OPEN) \(\d+\):\*\*$")
_VETO = re.compile(r"^VETO\s*:\s*", re.I)
POIN_MAKS = 5


def poin_bersih(p) -> str:
    """Satu poin alasan: satu baris, tanpa pipa/penanda daftar, maksimal 140 karakter."""
    s = re.sub(r"\s+", " ", str(p or "").replace("|", "/")).strip().lstrip("-*• ").strip()
    return s if len(s) <= 140 else s[:139].rsplit(" ", 1)[0] + "…"


def timbang(poin_skip: list, poin_open: list, keputusan: Optional[str]) -> dict:
    """Hitungan keputusan: OPEN hanya bila poin open > poin skip dan tidak ada poin VETO (aturan keras); seri = SKIP."""
    s, o = len(poin_skip or []), len(poin_open or [])
    veto = any(_VETO.match(p) for p in (poin_skip or []))
    hitungan = "SKIP" if veto or s >= o else "ORDER"
    return {"skip": s, "open": o, "veto": veto, "hitungan": hitungan, "sesuai": keputusan is None or hitungan == keputusan}


def blok_poin(poin_skip: list, poin_open: list) -> str:
    """Bagian poin di jurnal (dibaca balik oleh parse_keputusan)."""
    out = []
    for nama, xs in (("SKIP", poin_skip), ("OPEN", poin_open)):
        if xs:
            out.append(f"**Alasan {nama} ({len(xs)}):**")
            out += [f"- {p}" for p in xs]
    return "\n".join(out)


def klasifikasi_alasan(teks: str, persona: str = "tiket") -> str:
    s = (teks or "").lower()
    for kat, pola in _KATA + _PERSONA_KATA.get(persona, []) + _UMUM_KATA:
        if re.search(pola, s):
            return kat
    return "LAIN"


def parse_keputusan(md: str) -> list[dict]:
    """Keputusan kandidat dari jurnal agent: [{persona, kandidat_id, keputusan: SKIP|ORDER, alasan, teks, jam}]."""
    out: list[dict] = []
    blocks: list[tuple[str, str, list[str]]] = []
    for line in md.splitlines():
        m = _HEAD.match(line.strip())
        if m:
            blocks.append((f"{m.group(1)}:{m.group(2)}", m.group(3) + "|" + m.group(4).strip(), []))
        elif blocks:
            blocks[-1][2].append(line)
    for jam, head, body in blocks:
        jenis, judul = head.split("|", 1)
        if jenis != "keputusan":
            continue
        up = judul.upper()
        if "SKIP" in up:
            kep = "SKIP"
        elif re.search(r"ORDER #\d+", up):
            kep = "ORDER"
        else:
            continue
        pm = _PERSONA.match(judul)
        persona = pm.group(1).lower() if pm else "tiket"
        meta: dict = {}
        teks_lines = []
        poin: dict = {"SKIP": [], "OPEN": []}
        sisi = None
        for ln in body:
            mm = _META.match(ln.strip())
            if mm and not meta and "=" in mm.group(1):
                meta = dict(kv.split("=", 1) for kv in mm.group(1).split() if "=" in kv)
                continue
            ph = _POIN_HEAD.match(ln.strip())
            if ph:
                sisi = ph.group(1)
                continue
            if sisi and ln.strip().startswith("- "):
                poin[sisi].append(ln.strip()[2:].strip())
                continue
            if ln.strip():
                sisi = None
                teks_lines.append(ln.strip())
        ids: set[int] = set()
        for a, b in _K.findall(judul):
            lo = int(a)
            hi = int(b) if b else lo
            if hi < lo or hi - lo > 50:
                hi = lo
            ids.update(range(lo, hi + 1))
        if meta.get("kandidat", "").isdigit():
            ids.add(int(meta["kandidat"]))
        if not ids:
            continue
        teks = " ".join(teks_lines)[:400]
        alasan = meta.get("alasan") if meta.get("alasan") in KATEGORI else (
            klasifikasi_alasan(" ".join([judul, teks] + poin["SKIP"]), persona) if kep == "SKIP" else None)
        om = re.search(r"order #(\d+)", judul, re.I)
        order_id = int(meta["order"]) if meta.get("order", "").isdigit() else (int(om.group(1)) if om else None)
        am = re.search(r"\b(LONG|SHORT)\b", judul)
        sm = re.search(r"K\d+(?:\s*[-–]\s*K?\d+)?\s+([^\s\-]+USDT)\b", judul)
        symbol = meta.get("symbol") or (sm.group(1) if sm else None)
        for kid in sorted(ids):
            out.append({"persona": persona, "kandidat_id": kid, "keputusan": kep, "alasan": alasan, "teks": teks, "jam": jam,
                        "order_id": order_id if kep == "ORDER" else None, "arah": am.group(1) if am else None, "symbol": symbol,
                        "poin_skip": list(poin["SKIP"]), "poin_open": list(poin["OPEN"])})
    return out


def keputusan_per_kandidat(rows: Iterable[dict]) -> dict:
    """{kandidat_id: {persona: {...}}}; ORDER mengalahkan SKIP bila persona menulis keduanya."""
    out: dict = {}
    for r in rows:
        d = out.setdefault(r["kandidat_id"], {})
        cur = d.get(r["persona"])
        if cur is None or (cur["keputusan"] == "SKIP" and r["keputusan"] == "ORDER"):
            d[r["persona"]] = {k: r.get(k) for k in ("keputusan", "alasan", "teks", "jam", "order_id", "arah", "symbol", "poin_skip", "poin_open")}
    return out


# --------------------------------------------------------------------------- templat & simulasi
def templat(k: dict, filters, brackets: list, cfg: Optional[EngineConfig] = None) -> dict:
    """Order bayangan mekanis untuk satu kandidat. Mengembalikan {'ok': False, 'alasan': ...} bila tidak bisa dibentuk."""
    cfg = cfg or EngineConfig()
    side = k["arah_dugaan"]
    if side not in (LONG, SHORT):
        return {"ok": False, "alasan": "arah tidak dikenal"}
    try:
        lev_rows = json.loads(k["lev_layak"]) if isinstance(k["lev_layak"], str) else (k["lev_layak"] or [])
    except ValueError:
        lev_rows = []
    lev_rows = [r for r in lev_rows if r.get("leverage") and r.get("qty")]
    if not lev_rows:
        return {"ok": False, "alasan": "tidak ada leverage layak"}
    atr15 = k.get("atr_15m")
    if not atr15 or atr15 <= 0:
        return {"ok": False, "alasan": "ATR 15m tidak tersedia"}
    row = min(lev_rows, key=lambda r: int(r["leverage"]))
    lev, qty = int(row["leverage"]), float(row["qty"])
    tick = filters.tick_size if filters else None
    long = side == LONG
    entry = float(C.round_step(C.D(str(k["level"])), tick, "down" if long else "up")) if tick else float(k["level"])
    tp_raw = entry + TP_ATR15 * atr15 if long else entry - TP_ATR15 * atr15
    tp = float(C.round_step(C.D(str(tp_raw)), tick, "down" if long else "up")) if tick else tp_raw
    notional = qty * entry
    margin = notional / lev
    b = pick_bracket(brackets, notional)
    mmr, cum = (b.mmr, b.cum) if b else (0.0, 0.0)
    liq = liq_price(side, qty, entry, margin, mmr, cum)
    fee_in = fee_amount(notional, True, cfg)
    reward = abs(tp - entry) * qty - fee_in - fee_amount(tp * qty, True, cfg)
    risk = margin + fee_in
    run_ts = int(k["run_ts"])
    return {"ok": True, "side": side, "entry": entry, "tp": tp, "lev": lev, "qty": qty, "margin": margin, "liq": liq,
            "mmr": mmr, "cum": cum, "rr": reward / risk if risk > 0 else 0.0, "lolos_p19": reward / risk >= P19_RR if risk > 0 else False,
            "aktif_ms": C.ceil_minute(run_ts + 1), "eod_ms": C.wib_clock_ms(run_ts, EOD_WIB), "atr15": atr15}


def simulasi(tp_: dict, pairs: list, slip: float, cfg: Optional[EngineConfig] = None) -> dict:
    """Simulasi templat pada pasangan (Bar, MarkBar|None) 1 menit urut waktu. Tidak menulis apa pun."""
    cfg = cfg or EngineConfig()
    side, entry, tp, qty = tp_["side"], tp_["entry"], tp_["tp"], tp_["qty"]
    long = side == LONG
    sign = 1 if long else -1
    start, eod = tp_["aktif_ms"], tp_["eod_ms"]
    pairs = [(b, m) for b, m in pairs if start <= b.open_time <= eod]
    pos = None
    hasil = None
    n_seen = 0
    end_ms = eod

    def mk_mark(b, m):
        return m if m is not None else MarkBar(b.symbol, b.open_time, b.open, b.high, b.low, b.close, source="last")

    def tutup(px, alasan, is_maker, ts):
        realized = (px - pos["entry"]) * qty * sign
        fee_out = fee_amount(px * qty, is_maker, cfg)
        return {"hasil": alasan, "keluar": px, "net": realized - pos["fee_in"] - fee_out, "keluar_ms": ts}

    for b, m in pairs:
        n_seen += 1
        mark = mk_mark(b, m)
        ot = b.open_time
        if pos is None:
            if ot >= eod:
                hasil = {"hasil": "TIDAK_TERISI", "net": 0.0, "keluar_ms": ot}
                break
            fill = limit_fill(long, entry, b)
            if not fill:
                continue
            px = fill[0]
            margin = qty * px / tp_["lev"]
            pos = {"entry": px, "margin": margin, "fee_in": fee_amount(qty * px, True, cfg),
                   "liq": liq_price(side, qty, px, margin, tp_["mmr"], tp_["cum"]), "sl": None, "terisi_ms": ot,
                   "best": mark.high if long else mark.low, "worst": mark.low if long else mark.high}
            if liq_hit(side, pos["liq"], mark):
                hasil = {"hasil": "HANGUS", "net": -pos["margin"] - pos["fee_in"], "keluar": pos["liq"], "keluar_ms": ot}
                break
            continue
        if ot >= eod:
            px = b.open * (1 - slip) if long else b.open * (1 + slip)
            hasil = tutup(px, "EOD", False, ot)
            break
        if pos["sl"] is None:
            jarak = abs(tp - pos["entry"])
            tempuh = (pos["best"] - pos["entry"]) * sign
            if jarak > 0 and tempuh / jarak >= BREAKEVEN_MFE:
                pos["sl"] = pos["entry"]
        tp_fill = limit_fill(not long, tp, b)
        sl_fill = stop_trigger(side, pos["sl"], mark, b, slip) if pos["sl"] is not None else None
        if liq_hit(side, pos["liq"], mark):
            hasil = {"hasil": "HANGUS", "net": -pos["margin"] - pos["fee_in"], "keluar": pos["liq"], "keluar_ms": ot}
            break
        if sl_fill:
            hasil = tutup(sl_fill[0], "STOP_BE", False, ot)
            break
        if tp_fill:
            hasil = tutup(tp_fill[0], "TP", True, ot)
            break
        pos["best"] = max(pos["best"], mark.high) if long else min(pos["best"], mark.low)
        pos["worst"] = min(pos["worst"], mark.low) if long else max(pos["worst"], mark.high)

    if hasil is not None:
        end_ms = hasil["keluar_ms"]
    expected = max(1, (min(end_ms, eod) - start) // MINUTE_MS + 1)
    seen = sum(1 for b, _ in pairs if b.open_time <= end_ms)
    coverage = seen / expected
    if hasil is None:
        if pos is None:
            hasil = {"hasil": "TIDAK_TERISI", "net": 0.0, "keluar_ms": eod}
        elif pairs:
            lb = pairs[-1][0]
            px = lb.close * (1 - slip) if long else lb.close * (1 + slip)
            hasil = tutup(px, "EOD", False, lb.open_time)
        coverage = n_seen / max(1, (eod - start) // MINUTE_MS + 1)
    if coverage < MIN_COVERAGE:
        return {"hasil": "ambigu", "net": None, "coverage": round(coverage, 3), "alasan": f"cakupan bar 1m {coverage:.0%} < {MIN_COVERAGE:.0%}"}
    out = {**hasil, "coverage": round(min(coverage, 1.0), 3)}
    if pos is not None:
        jarak = abs(tp - pos["entry"]) or 1.0
        out.update(terisi_ms=pos["terisi_ms"], entry_isi=pos["entry"], mfe_tp=round((pos["best"] - pos["entry"]) * sign / jarak, 3))
    out["net"] = round(out["net"], 6) if out.get("net") is not None else None
    return out


def label_skip(hasil: dict) -> str:
    if hasil.get("hasil") == "ambigu":
        return "ambigu"
    if hasil.get("hasil") == "TIDAK_TERISI":
        return "netral"
    net = hasil.get("net") or 0.0
    return "salah" if net > NET_EPS else ("benar" if net < -NET_EPS else "netral")


# --------------------------------------------------------------------------- rekap & pelajaran
def _sampel(records: list[dict], since_ms: int) -> tuple[Optional[float], list[tuple[str, str, str]]]:
    """Baseline akurasi SKIP acak (= 1 − P(templat untung | terisi)) dan daftar (persona, kategori, label) SKIP non-netral."""
    recent = [r for r in records if int(r["run_ts"]) >= since_ms]
    terisi = [r for r in recent if r["hasil"] not in ("ambigu", "TIDAK_TERISI")]
    win = sum(1 for r in terisi if (r.get("net") or 0) > NET_EPS)
    lose = sum(1 for r in terisi if (r.get("net") or 0) < -NET_EPS)
    base = (lose / (win + lose)) if (win + lose) else None
    items = []
    for r in recent:
        for persona, d in (r.get("keputusan") or {}).items():
            if d.get("keputusan") == "SKIP" and d.get("label") in ("benar", "salah"):
                items.append((persona, d.get("alasan") or "LAIN", d["label"]))
    return base, items


def update_skip_lessons(records: list[dict], lessons: list[dict], now_ms: int) -> tuple[list[dict], list[str]]:
    """Pelajaran dari SKIP (sumber='skip'): kelompok (persona, kategori) dan (semua, kategori)."""
    lessons = [dict(l) for l in lessons]
    perubahan: list[str] = []
    base, items = _sampel(records, now_ms - LS_JENDELA_HARI * C.DAY_MS)
    groups: dict[tuple[str, str], list[str]] = {}
    for persona, kat, lab in items:
        groups.setdefault((persona, kat), []).append(lab)
        groups.setdefault(("semua", kat), []).append(lab)
    by_pola = {l["pola"]: l for l in lessons}
    for (persona, kat), labs in sorted(groups.items()):
        pola = f"skip:{persona}:{kat}"
        n = len(labs)
        acc = sum(1 for x in labs if x == "benar") / n
        les = by_pola.get(pola)
        if les is None:
            if base is None or n < LS_MIN_SAMPEL or abs(acc - base) < LS_MARGIN:
                continue
            if sum(1 for l in lessons if l["status"] == "aktif") >= LS_MAX_AKTIF:
                perubahan.append(f"{pola} memenuhi syarat tapi pelajaran SKIP aktif sudah {LS_MAX_AKTIF}")
                continue
            arah = "menyaring" if acc > base else "melewatkan"
            lid = f"LS-{len(lessons) + 1:02d}"
            siapa = "semua analis" if persona == "semua" else persona
            teks = (f"SKIP {siapa} karena {KATEGORI_ARTI.get(kat, kat)}: {acc:.0%} tepat dari {n} kandidat vs {base:.0%} bila SKIP acak — "
                    + ("alasan ini terbukti menyaring kandidat buruk" if arah == "menyaring" else "alasan ini sering melewatkan peluang; tinjau syaratnya"))
            les = {"id": lid, "sumber": "skip", "pola": pola, "persona": persona, "kategori": kat, "arah": arah, "ringkasan": teks,
                   "sampel": n, "hit_rate": acc, "baseline": base, "rezim": "30 hari", "status": "aktif",
                   "dibuat": C.day_wib(now_ms), "dibuat_ms": now_ms, "dinilai_ulang_ms": now_ms + LS_NILAI_ULANG_HARI * C.DAY_MS,
                   "dinilai_ulang": C.day_wib(now_ms + LS_NILAI_ULANG_HARI * C.DAY_MS), "alasan_pensiun": None}
            lessons.append(les)
            by_pola[pola] = les
            perubahan.append(f"{lid} {pola} AKTIF ({arah}: {acc:.0%} vs {base:.0%}, n={n})")
        elif les["status"] == "aktif" and now_ms >= int(les["dinilai_ulang_ms"]):
            if base is not None and n >= LS_MIN_SAMPEL:
                les.update(sampel=n, hit_rate=acc, baseline=base)
                beda = acc - base if les["arah"] == "menyaring" else base - acc
                if beda < LS_PENSIUN:
                    les["status"] = "pensiun"
                    les["alasan_pensiun"] = f"akurasi 30 hari {acc:.0%} ≈ baseline {base:.0%} pada {C.day_wib(now_ms)}"
                    perubahan.append(f"{les['id']} {pola} PENSIUN ({les['alasan_pensiun']})")
                else:
                    perubahan.append(f"{les['id']} {pola} dinilai ulang: {acc:.0%} vs {base:.0%} (n={n}), tetap aktif")
            else:
                perubahan.append(f"{les['id']} {pola} dinilai ulang ditunda: n={n} < {LS_MIN_SAMPEL}")
            les["dinilai_ulang_ms"] = now_ms + LS_NILAI_ULANG_HARI * C.DAY_MS
            les["dinilai_ulang"] = C.day_wib(les["dinilai_ulang_ms"])
    return lessons, perubahan


def akurasi_persona(records: list[dict], since_ms: int) -> dict:
    """{persona: {n, benar, salah, netral, akurasi}} untuk SKIP sejak since_ms."""
    out: dict = {}
    for r in records:
        if int(r["run_ts"]) < since_ms:
            continue
        for persona, d in (r.get("keputusan") or {}).items():
            if d.get("keputusan") != "SKIP" or d.get("label") == "ambigu":
                continue
            s = out.setdefault(persona, {"n": 0, "benar": 0, "salah": 0, "netral": 0})
            s["n"] += 1
            s[d["label"]] += 1
    for s in out.values():
        nn = s["benar"] + s["salah"]
        s["akurasi"] = s["benar"] / nn if nn else None
    return out


def render_skip_md(records: list[dict], now_ms: int) -> str:
    since = now_ms - LS_JENDELA_HARI * C.DAY_MS
    base, items = _sampel(records, since)
    recent = [r for r in records if int(r["run_ts"]) >= since]
    hasil_n: dict = {}
    for r in recent:
        hasil_n[r["hasil"]] = hasil_n.get(r["hasil"], 0) + 1
    lines = ["# Penilaian SKIP", "",
             "_Ditulis skrip `uji_hipotesis.py` (modul `kontrafaktual.py`). Setiap kandidat pemindai dinilai dengan order bayangan mekanis "
             "(limit di level, leverage layak terendah, TP 1,5×ATR15m, breakeven P-18, tutup 23:50). SKIP **benar** = bayangan rugi, "
             "**salah** = bayangan untung (peluang terlewat), **netral** = tidak terisi. Jangan diedit manual._", "",
             f"Jendela {LS_JENDELA_HARI} hari: {len(recent)} kandidat dinilai — " + ", ".join(f"{k} {v}" for k, v in sorted(hasil_n.items())) + ".",
             f"Baseline (akurasi bila SKIP acak): {base:.0%}." if base is not None else "Baseline: tidak tersedia (belum ada kandidat terisi).", "",
             "## Per analis", "", "| Analis | SKIP | Benar | Salah | Netral | Akurasi |", "|---|---|---|---|---|---|"]
    acc = akurasi_persona(records, since)
    for p, s in sorted(acc.items()):
        akurasi = f"{s['akurasi']:.0%}" if s["akurasi"] is not None else "—"
        lines.append(f"| {p} | {s['n']} | {s['benar']} | {s['salah']} | {s['netral']} | {akurasi} |")
    if not acc:
        lines.append("| — | | | | | |")
    lines += ["", "## Per alasan (semua analis)", "", "| Alasan | n | Akurasi | Arti |", "|---|---|---|---|"]
    per_kat: dict = {}
    for _, kat, lab in items:
        per_kat.setdefault(kat, []).append(lab)
    for kat, labs in sorted(per_kat.items(), key=lambda x: -len(x[1])):
        a = sum(1 for x in labs if x == "benar") / len(labs)
        lines.append(f"| {kat} | {len(labs)} | {a:.0%} | {KATEGORI_ARTI.get(kat, kat)} |")
    if not per_kat:
        lines.append("| — | | | |")
    lines += ["", "## Peluang terbesar yang terlewat (7 hari)", "", "| Kandidat | Hari | Simbol | Arah | Hasil bayangan | Net | Di-SKIP oleh |", "|---|---|---|---|---|---|---|"]
    week = [r for r in records if int(r["run_ts"]) >= now_ms - 7 * C.DAY_MS and (r.get("net") or 0) > NET_EPS]
    for r in sorted(week, key=lambda r: -(r.get("net") or 0))[:5]:
        siapa = ", ".join(sorted(p for p, d in (r.get("keputusan") or {}).items() if d.get("keputusan") == "SKIP")) or "—"
        lines.append(f"| K{r['kandidat_id']} | {r['hari']} | {r['symbol']} | {r['arah']} | {r['hasil']} | {r['net']:+.4f} | {siapa} |")
    if not week:
        lines.append("| — | | | | | | |")
    return "\n".join(lines) + "\n"
