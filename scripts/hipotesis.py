"""hipotesis.py — modul murni untuk hipotesis pasar terstruktur (§16.5–16.6).

Dipakai mcp_server.py (membuat record → pasar/hipotesis.jsonl) dan uji_hipotesis.py (menilai, baseline, pelajaran).
Prediksi harus terukur supaya skrip yang menilai, bukan model:
  jenis = sentuh_harga  : high/low menyentuh `nilai` (harga) ke arah `arah` dalam `batas_hari`
          gerak_atr     : harga bergerak ≥ `nilai` × ATR14(tf) dari harga_awal ke arah `arah`
          close_arah    : close bar terakhir horizon berada di sisi `arah` dari harga_awal
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterable, Optional

import analisis as A
import common as C
from common import Bar

TF = ("1h", "4h", "1d")
JENIS = ("sentuh_harga", "gerak_atr", "close_arah")
ARAH = ("atas", "bawah")
POLA = (
    "penumpukan-leverage", "breakout-gagal", "kapitulasi", "divergensi-funding", "reaksi-berita-terbalik",
    "kompresi", "pullback-ke-level", "wick-penolakan", "lonjakan-volume", "euforia-komunitas", "panik-komunitas",
)
ATR_N = 14
MIN_COVERAGE = 0.9
BASELINE_N = 200
BASELINE_MIN_VALID = 30
BASELINE_DAYS = 120
PROMOSI_MIN_SAMPEL = 10
PROMOSI_MARGIN = 0.15
PENSIUN_MARGIN = 0.05
MAX_AKTIF = 15
NILAI_ULANG_HARI = 30
JENDELA_NILAI_ULANG_HARI = 90
VERSI = 1


# --------------------------------------------------------------------------- record
def new_record(hid: str, now_ms: int, pola: str, symbol: str, tf: str, jenis: str, arah: str, nilai: Optional[float],
               batas_hari: int, kondisi: str, catatan: str, harga_awal: Optional[float], atr_awal: Optional[float], oleh: str) -> dict:
    if pola not in POLA:
        raise ValueError(f"pola harus salah satu dari: {', '.join(POLA)}")
    if tf not in TF:
        raise ValueError(f"tf harus salah satu dari: {', '.join(TF)}")
    if jenis not in JENIS:
        raise ValueError(f"jenis harus salah satu dari: {', '.join(JENIS)}")
    if arah not in ARAH:
        raise ValueError("arah harus atas|bawah")
    if not isinstance(batas_hari, int) or not 1 <= batas_hari <= 7:
        raise ValueError("batas_hari harus bilangan bulat 1–7")
    if not symbol or not symbol.strip():
        raise ValueError("symbol wajib")
    if harga_awal is None or harga_awal <= 0:
        raise ValueError("harga_awal (mark) tidak tersedia untuk simbol ini")
    if jenis == "sentuh_harga":
        if nilai is None or nilai <= 0:
            raise ValueError("sentuh_harga butuh nilai = harga target")
        if (arah == "atas" and nilai <= harga_awal) or (arah == "bawah" and nilai >= harga_awal):
            raise ValueError(f"harga target {nilai} harus di sisi {arah} dari harga awal {harga_awal}")
    elif jenis == "gerak_atr":
        if nilai is None or nilai <= 0:
            raise ValueError("gerak_atr butuh nilai = kelipatan ATR (> 0)")
        if atr_awal is None or atr_awal <= 0:
            raise ValueError(f"ATR{ATR_N} {tf} tidak tersedia untuk simbol ini; pakai jenis lain")
    else:
        nilai = None
    if not kondisi or not kondisi.strip():
        raise ValueError("kondisi (terukur) wajib diisi")
    batas_ms = now_ms + batas_hari * C.DAY_MS
    return {
        "id": hid, "dibuat_ms": int(now_ms), "dibuat": C.fmt_wib(now_ms), "hari": C.day_wib(now_ms), "pola": pola,
        "symbol": symbol.strip(), "tf": tf, "jenis": jenis, "arah": arah, "nilai": nilai, "harga_awal": float(harga_awal),
        "atr_awal": float(atr_awal) if atr_awal else None, "batas_hari": batas_hari, "batas_ms": int(batas_ms),
        "batas": C.day_wib(batas_ms), "kondisi": kondisi.strip(), "catatan": (catatan or "").strip(), "oleh": oleh, "versi": VERSI,
    }


def horizon(rec: dict, tf_ms: int) -> tuple[int, int]:
    """(open_time bucket pertama yang boleh dipakai, batas_ms). Tidak ada look-back: bucket yang memuat saat dibuat dibuang."""
    awal = -(-int(rec["dibuat_ms"]) // tf_ms) * tf_ms
    return awal, int(rec["batas_ms"])


def target_price(rec: dict) -> Optional[float]:
    if rec["jenis"] == "sentuh_harga":
        return float(rec["nilai"])
    if rec["jenis"] == "gerak_atr":
        if not rec.get("atr_awal"):
            return None
        d = float(rec["nilai"]) * float(rec["atr_awal"])
        return float(rec["harga_awal"]) + d if rec["arah"] == "atas" else float(rec["harga_awal"]) - d
    return float(rec["harga_awal"])


def judge(rec: dict, bars_tf: list[Bar]) -> dict:
    """Menilai satu hipotesis dengan bar tf yang sudah close. Hasil: benar | salah | ambigu."""
    tf_ms = A.TF_MS[rec["tf"]]
    awal, batas = horizon(rec, tf_ms)
    use = [b for b in bars_tf if b.open_time >= awal and b.open_time + tf_ms <= batas]
    expected = max(0, (batas - awal) // tf_ms)
    tgt = target_price(rec)
    if expected == 0:
        return {"hasil": "ambigu", "alasan": "horizon tidak memuat satu bar penuh pun", "n_bar": 0, "ekstrem": None, "target": tgt}
    if len(use) < MIN_COVERAGE * expected:
        return {"hasil": "ambigu", "alasan": f"data bar {len(use)}/{expected} (< {MIN_COVERAGE:.0%})", "n_bar": len(use), "ekstrem": None, "target": tgt}
    atas = rec["arah"] == "atas"
    if rec["jenis"] in ("sentuh_harga", "gerak_atr"):
        if tgt is None:
            return {"hasil": "ambigu", "alasan": "ATR awal tidak tersedia", "n_bar": len(use), "ekstrem": None, "target": None}
        ekstrem = max(b.high for b in use) if atas else min(b.low for b in use)
        benar = ekstrem >= tgt if atas else ekstrem <= tgt
        kata = "high" if atas else "low"
        alasan = f"{kata} {ekstrem:.6g} {'≥' if atas else '≤'} target {tgt:.6g}" if benar else f"{kata} {ekstrem:.6g} tidak mencapai target {tgt:.6g}"
    else:
        ekstrem = use[-1].close
        benar = ekstrem > tgt if atas else ekstrem < tgt
        alasan = f"close terakhir {ekstrem:.6g} {'>' if atas else '<'} harga awal {tgt:.6g}" if benar else f"close terakhir {ekstrem:.6g} tidak di sisi {rec['arah']} dari {tgt:.6g}"
    return {"hasil": "benar" if benar else "salah", "alasan": alasan, "n_bar": len(use), "ekstrem": float(ekstrem), "target": tgt}


def baseline(rec: dict, bars_tf: list[Bar], rng: random.Random, n: int = BASELINE_N) -> dict:
    """Seberapa sering prediksi yang sama terjadi dari titik awal acak (jarak dipertahankan relatif: persen / kelipatan ATR)."""
    tf_ms = A.TF_MS[rec["tf"]]
    hz = int(rec["batas_hari"]) * C.DAY_MS
    if not bars_tf:
        return {"rate": None, "n_valid": 0, "n_benar": 0, "n_ambigu": 0, "alasan": "tidak ada bar"}
    last_close = bars_tf[-1].open_time + tf_ms
    cands = [i for i in range(ATR_N + 2, len(bars_tf)) if bars_tf[i].open_time + hz <= last_close]
    if len(cands) < BASELINE_MIN_VALID:
        return {"rate": None, "n_valid": 0, "n_benar": 0, "n_ambigu": 0, "alasan": f"hanya {len(cands)} titik awal yang mungkin (< {BASELINE_MIN_VALID})"}
    rel = (float(rec["nilai"]) - float(rec["harga_awal"])) / float(rec["harga_awal"]) if rec["jenis"] == "sentuh_harga" else None
    benar = valid = ambigu = 0
    for _ in range(n):
        i = rng.choice(cands)
        start = bars_tf[i].open_time
        h0 = bars_tf[i - 1].close
        a0 = A.atr(bars_tf[:i], ATR_N)
        if rec["jenis"] == "gerak_atr" and not a0:
            ambigu += 1
            continue
        nilai = h0 * (1 + rel) if rel is not None else rec["nilai"]
        r2 = dict(rec, dibuat_ms=start, batas_ms=start + hz, harga_awal=h0, atr_awal=a0, nilai=nilai)
        j = judge(r2, bars_tf)
        if j["hasil"] == "ambigu":
            ambigu += 1
            continue
        valid += 1
        benar += j["hasil"] == "benar"
    return {"rate": (benar / valid) if valid >= BASELINE_MIN_VALID else None, "n_valid": valid, "n_benar": benar, "n_ambigu": ambigu}


def hit_rate(hasil: Iterable[str]) -> Optional[float]:
    xs = [h for h in hasil if h in ("benar", "salah")]
    return (sum(1 for h in xs if h == "benar") / len(xs)) if xs else None


# --------------------------------------------------------------------------- jsonl & render
def load_jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    out = []
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
    return out


def append_jsonl(path: Path, rec: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _cell(s) -> str:
    return str(s).replace("|", "/").replace("\n", " ").strip()


def _prediksi(rec: dict) -> str:
    if rec["jenis"] == "sentuh_harga":
        return f"{rec['symbol']} {rec['tf']} menyentuh {rec['nilai']:.6g} ({rec['arah']})"
    if rec["jenis"] == "gerak_atr":
        return f"{rec['symbol']} {rec['tf']} bergerak ≥ {rec['nilai']}×ATR ke {rec['arah']} dari {rec['harga_awal']:.6g}"
    return f"{rec['symbol']} {rec['tf']} close akhir di sisi {rec['arah']} dari {rec['harga_awal']:.6g}"


def render_hipotesis_md(records: list[dict], hasil: dict) -> str:
    lines = ["# Hipotesis", "", "_Dibuat agent lewat tool `tulis_hipotesis` (pasar/hipotesis.jsonl); dinilai skrip `uji_hipotesis.py` — file ini di-generate, jangan diedit._", "",
             "| ID | Dibuat | Pola | Kondisi (terukur) | Prediksi | Batas | Status | Hasil | Baseline |", "|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        h = hasil.get(r["id"])
        status = h["hasil"] if h else "terbuka"
        base = h.get("baseline", {}).get("rate") if h else None
        lines.append(f"| {r['id']} | {r['hari']} | {r['pola']} | {_cell(r['kondisi'])} | {_cell(_prediksi(r))} | {r['batas']} | {status} | "
                     f"{_cell(h['alasan']) if h else '—'} | {f'{base:.0%}' if base is not None else '—'} |")
    return "\n".join(lines) + "\n"


def render_pelajaran_md(lessons: list[dict]) -> str:
    lines = ["# Pelajaran", "", "_Ditulis skrip `uji_hipotesis.py` dari hipotesis yang dinilai (§16.6): naik bila sampel ≥ 10 dan hit rate ≥ baseline + 15 poin; "
             "dinilai ulang tiap 30 hari dengan data 90 hari; pensiun bila turun ke sekitar baseline. Jangan diedit manual._", ""]
    for status, judul in (("aktif", "## Aktif"), ("pensiun", "## Pensiun")):
        rows = [l for l in lessons if l["status"] == status]
        lines += [judul, "", "| ID | Pola | Ringkasan | Sampel | Hit rate | Baseline | Rezim | Status | Dinilai ulang |", "|---|---|---|---|---|---|---|---|---|"]
        for l in rows:
            lines.append(f"| {l['id']} | {l['pola']} | {_cell(l['ringkasan'])} | {l['sampel']} | {l['hit_rate']:.0%} | {l['baseline']:.0%} | {l['rezim']} | "
                         f"{l['status']}{(' (' + _cell(l['alasan_pensiun']) + ')') if l.get('alasan_pensiun') else ''} | {l['dinilai_ulang']} |")
        if not rows:
            lines.append("| — | | | | | | | | |")
        lines.append("")
    return "\n".join(lines)
