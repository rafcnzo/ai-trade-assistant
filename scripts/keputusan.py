"""keputusan.py — merakit keputusan arena per kandidat dari jurnal agent (fungsi murni, tidak menulis apa pun).

Satu sumber format untuk dua tampilan:
- Telegram: `mcp_server.tulis_jurnal` mengembalikan `ringkasan_markdown` (judul, fakta, tabel Persona | Hasil | Alasan) yang disalin
  agent apa adanya. Karena memuat tabel, adapter Telegram Hermes selalu mengirimnya sebagai Rich Message (Bot API 10.1).
- Dashboard: `/api/keputusan` memakai `kelompok()` yang sama, ditambah hasil order nyata dan penilaian SKIP (pasar/skip-hasil.jsonl).
"""
from __future__ import annotations

import json
import math
import re
from typing import Optional

import common as C
import kontrafaktual as K

URUT_PERSONA = ("tiket", "fade", "breakout", "rentang")
LABEL_ALASAN = {
    "RR_P19": "R:R < 0,5 (P-19)", "TP_ATR15": "TP terlalu jauh", "TREN_15M": "melawan tren 15m", "SENTUHAN": "level lemah",
    "LIQ_ATR5": "likuidasi terlalu dekat", "SUDAH_LARI": "harga sudah lari", "FUNDING": "funding melawan", "BASI": "data basi",
    "LIMIT_CROSSES": "harga sudah lewat level", "BUDGET": "saldo tidak cukup", "EOD": "dekat jam tutup", "DUPLIKAT": "sudah ada order/posisi",
    "PANEL_FADE": "panel tidak ekstrem", "NO_VOL_TEMBUS": "tanpa tembus bervolume", "NO_SIDEWAYS": "tidak sideways", "PLAYBOOK": "aturan playbook",
    "LAIN": "lainnya",
}
PENUTUP = "Paper trading; keputusan uang sungguhan ada di Anda."

_TREN = re.compile(r"tren15m (\w+)")
_HEAD = re.compile(r"^## (\d{2}):(\d{2}) WIB — (\w+) — (.+)$")


def _px(x) -> str:
    """Harga dengan 6 angka penting tanpa notasi ilmiah (koin berharga sangat kecil tetap terbaca)."""
    if x is None:
        return "—"
    v = float(x)
    if v == 0 or not math.isfinite(v):
        return "0" if v == 0 else "—"
    d = max(0, 6 - int(math.floor(math.log10(abs(v)))) - 1)
    s = f"{v:.{d}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _pct(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + " %"


def _ts(hari: Optional[str], jam: Optional[str]) -> Optional[int]:
    if not hari or not jam or ":" not in jam:
        return None
    h, m = jam.split(":")
    return C.day_start_wib_ms(hari) + int(h) * C.HOUR_MS + int(m) * C.MINUTE_MS


def sel(teks: Optional[str], maks: int = 260) -> str:
    """Teks aman untuk sel tabel markdown: satu baris, tanpa pipa, dipotong di batas kata."""
    s = re.sub(r"\s+", " ", (teks or "").replace("|", "/")).strip()
    if len(s) <= maks:
        return s
    cut = s[:maks].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def fakta_kandidat(k: dict) -> dict:
    try:
        flags = json.loads(k["flags"]) if isinstance(k.get("flags"), str) else list(k.get("flags") or [])
    except ValueError:
        flags = []
    tren = _TREN.search(k.get("ringkasan") or "")
    mark, atr15 = k.get("mark"), k.get("atr_15m")
    return {"kandidat_id": k.get("id"), "symbol": k.get("symbol"), "arah": k.get("arah_dugaan"), "mark": mark, "level": k.get("level"),
            "sentuhan": k.get("sentuhan"), "atr_15m": atr15, "atr_15m_pct": (atr15 / mark * 100) if (atr15 and mark) else None,
            "tren_15m": tren.group(1) if tren else None, "tanda": [f for f in flags if f != "DEKAT_LEVEL"], "skor": k.get("score"),
            "run_ts": k.get("run_ts"), "jam": C.fmt_wib(int(k["run_ts"]))[11:16] if k.get("run_ts") else None}


def kalimat_fakta(f: dict) -> str:
    parts = [f"mark **{_px(f['mark'])}**", f"level **{_px(f['level'])}**" + (f" ({f['sentuhan']} sentuhan)" if f.get("sentuhan") else "")]
    if f.get("atr_15m"):
        parts.append(f"ATR 15m {_px(f['atr_15m'])}" + (f" ({_pct(f['atr_15m_pct'])})" if f.get("atr_15m_pct") else ""))
    if f.get("tren_15m"):
        parts.append(f"tren 15m {f['tren_15m']}")
    if f.get("tanda"):
        parts.append("tanda " + ", ".join(f["tanda"]))
    return " · ".join(parts)


def _ringkas(baris: list[dict]) -> str:
    order = [b["persona"] for b in baris if b["keputusan"] == "ORDER"]
    skip = sum(1 for b in baris if b["keputusan"] == "SKIP")
    if not order:
        return "semua persona SKIP" if skip > 1 else "SKIP"
    return f"{len(order)} order ({', '.join(order)})" + (f" · {skip} SKIP" if skip else "")


def _penilaian(row: dict, sk: Optional[dict]) -> dict:
    if row["keputusan"] == "ORDER":
        p, o = row.get("posisi"), row.get("order")
        if p is not None:
            if p.get("status") == "OPEN":
                return {"jenis": "berjalan"}
            return {"jenis": "hasil", "net": p.get("net_result"), "hasil": p.get("close_reason")}
        if o is not None and o.get("status") in ("EXPIRED", "CANCELED", "REJECTED"):
            return {"jenis": "order", "status": o["status"], "kode": o.get("reject_code")}
        return {"jenis": "order", "status": (o or {}).get("status") or "tidak tersedia"}
    if sk is None:
        return {"jenis": "belum"}
    d = (sk.get("keputusan") or {}).get(row["persona"]) or {}
    return {"jenis": d.get("label") or K.label_skip(sk), "net": sk.get("net"), "hasil": sk.get("hasil")}


def blok(md_text: str) -> list[dict]:
    """Pecah jurnal menjadi blok `## HH:MM WIB — jenis — judul` (teks utuh) untuk memisahkan keputusan dan catatan lain."""
    out: list[dict] = []
    for line in (md_text or "").splitlines():
        m = _HEAD.match(line.strip())
        if m:
            out.append({"jam": f"{m.group(1)}:{m.group(2)}", "jenis": m.group(3), "judul": m.group(4).strip(), "baris": [line]})
        elif out:
            out[-1]["baris"].append(line)
    for b in out:
        b["teks"] = "\n".join(b["baris"]).strip()
        b["keputusan_kandidat"] = bool(K.parse_keputusan(b["teks"]))
    return out


def kelompok(md_text: str, kandidat: Optional[dict] = None, orders: Optional[dict] = None, posisi: Optional[dict] = None,
             skip: Optional[dict] = None, hari: Optional[str] = None) -> dict:
    """Keputusan per kandidat (terbaru dulu) + catatan non-keputusan.
    kandidat: {id: baris kandidat}; orders: {order_id: baris order}; posisi: {entry_order_id: baris posisi};
    skip: {kandidat_id: rekaman skip-hasil}."""
    rows = K.parse_keputusan(md_text or "")
    per = K.keputusan_per_kandidat(rows)
    jam_awal: dict = {}
    for r in rows:
        if r["kandidat_id"] not in jam_awal or r["jam"] < jam_awal[r["kandidat_id"]]:
            jam_awal[r["kandidat_id"]] = r["jam"]
    groups = []
    for kid, d in per.items():
        k = (kandidat or {}).get(kid)
        fakta = fakta_kandidat(k) if k else None
        symbol = (fakta or {}).get("symbol") or next((x.get("symbol") for x in d.values() if x.get("symbol")), None)
        arah = (fakta or {}).get("arah") or next((x.get("arah") for x in d.values() if x.get("arah")), None)
        sk = (skip or {}).get(kid)
        baris = []
        for persona in sorted(d, key=lambda p: (URUT_PERSONA.index(p) if p in URUT_PERSONA else 9, p)):
            x = d[persona]
            row = {"persona": persona, "keputusan": x["keputusan"], "alasan": x.get("alasan"),
                   "label_alasan": LABEL_ALASAN.get(x.get("alasan")) if x.get("alasan") else None,
                   "teks": x.get("teks") or "", "jam": x.get("jam"), "ts": _ts(hari, x.get("jam")), "order_id": x.get("order_id")}
            oid = x.get("order_id")
            if oid and orders and oid in orders:
                o = orders[oid]
                row["order"] = {k2: o.get(k2) for k2 in ("id", "account", "side", "type", "price", "leverage", "tp_price", "sl_price", "status", "reject_code")}
            if oid and posisi and oid in posisi:
                p = posisi[oid]
                row["posisi"] = {k2: p.get(k2) for k2 in ("id", "status", "close_reason", "net_result")}
            row["penilaian"] = _penilaian(row, sk)
            baris.append(row)
        groups.append({"kandidat_id": kid, "jam": jam_awal.get(kid), "ts": _ts(hari, jam_awal.get(kid)), "symbol": symbol, "arah": arah,
                       "fakta": fakta, "baris": baris, "ringkas": _ringkas(baris),
                       "bayangan": {"hasil": sk.get("hasil"), "net": sk.get("net")} if sk else None})
    groups.sort(key=lambda g: (g["jam"] or "", g["kandidat_id"]), reverse=True)
    lain = [b["teks"] for b in blok(md_text) if not b["keputusan_kandidat"]]
    return {"hari": hari, "kandidat": groups, "lain_md": "\n\n".join(lain)}


def render_markdown(g: dict) -> str:
    """Pesan Telegram satu kandidat: judul, fakta, tabel. Tabel memicu Rich Message di adapter Telegram Hermes."""
    judul = f"**Arena K{g['kandidat_id']} · {g.get('symbol') or '?'}{(' ' + g['arah']) if g.get('arah') else ''}"
    judul += f" · {g['jam']} WIB**" if g.get("jam") else "**"
    lines = [f"{judul} — {g['ringkas']}", ""]
    if g.get("fakta"):
        lines += [kalimat_fakta(g["fakta"]).replace("mark", "Mark", 1), ""]
    lines += ["| Persona | Hasil | Alasan |", "|---|---|---|"]
    for b in g["baris"]:
        if b["keputusan"] == "ORDER":
            hasil = f"**ORDER #{b['order_id']}**" if b.get("order_id") else "**ORDER**"
            o = b.get("order") or {}
            rinci = (f"{o.get('side', '')} limit {_px(o.get('price'))} · {o.get('leverage')}× · TP {_px(o.get('tp_price'))} — " if o.get("price") else "")
            alasan = rinci + sel(b["teks"], 220)
        else:
            hasil = "SKIP"
            alasan = sel(b["teks"]) or (b.get("label_alasan") or "—")
        lines.append(f"| {b['persona']} | {hasil} | {alasan} |")
    return "\n".join(lines)
