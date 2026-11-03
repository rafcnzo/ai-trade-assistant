"""asisten.py — konsultasi pemilik: ide trade dicatat, dinilai skrip, dan diringkas jadi rapor kematangan (fungsi murni, tanpa LLM).

Alur: tool periksa_ide (mcp_server) mencatat ide pemilik ke pasar/konsultasi.jsonl, tool catat_saran menambah saran agent;
uji_hipotesis.py menilai ide yang jatuh tempo dengan bar 1 menit ke pasar/konsultasi-hasil.jsonl; dashboard dan tool rapor_asisten
hanya membaca keduanya. Semua hasil per $100 nilai posisi supaya ide berbeda ukuran bisa dibandingkan.

Syarat rapor dikunci 3 Nov 2026 sebelum ada satu pun ide dinilai. Mengubahnya setelah melihat hasil membatalkan arti rapor;
perubahan apa pun wajib tertulis di CHANGELOG dengan alasannya. Rapor dihitung ulang tiap kali, jadi tahap bisa turun lagi.
"""
from __future__ import annotations

import json
import random
from typing import Optional

import common as C
import kontrafaktual as K
from common import MINUTE_MS
from paper_engine import LONG, SHORT, EngineConfig, fee_amount, liq_price, pick_bracket
from uji_variasi import selang_per_hari

VERSI = 1
NILAI_POSISI = 100.0
LEV_BAWAAN = 10
BATAS_HARI_BAWAAN = 3
BATAS_HARI_MAKS = 7
MAKS_IDE_PER_HARI = 10
SARAN_MAKS_MENIT = 60      # saran sesudah ini ditolak: tidak boleh ditulis setelah harga terlihat bergerak
DUPLIKAT_MENIT = 60
COBA_ULANG_MS = 36 * C.HOUR_MS
MIRIP_MIN_N = 20
REZIM_HARI = 20
REZIM_PERSEN = 10.0

# syarat rapor (dikunci, lihat docstring)
MIN_SARAN = 100
MIN_RENTANG_HARI = 90
MIN_HARI_BERBEDA = 30
MIN_REZIM = 2
MIN_PER_REZIM = 20
MIN_PER_KELOMPOK = 10      # lanjut dan hindari, sebelum dibandingkan
MIN_PER_PARUH = 15
P_MAKS = 0.05
PERMUTASI = 2000
TAHAP = ("Mengumpulkan pengalaman", "Berpengalaman, belum terbukti", "Terbukti di paper")


def rezim_dari(perubahan_persen: Optional[float]) -> str:
    """Kondisi pasar dari perubahan harga BTC 20 hari."""
    if perubahan_persen is None:
        return "tidak tersedia"
    return "naik" if perubahan_persen > REZIM_PERSEN else ("turun" if perubahan_persen < -REZIM_PERSEN else "datar")


def melawan_tren(sisi: str, tren: Optional[str]) -> bool:
    return (tren == "naik" and sisi == SHORT) or (tren == "turun" and sisi == LONG)


def new_ide(iid: str, now_ms: int, symbol: str, sisi: str, tp: float, sl: float, entry: Optional[float], leverage: int, batas_hari: int,
            harga: float, tren_15m: str, rezim: str, catatan: str = "") -> dict:
    if sisi not in (LONG, SHORT):
        raise ValueError("sisi harus LONG atau SHORT")
    if not 1 <= int(batas_hari) <= BATAS_HARI_MAKS:
        raise ValueError(f"batas_hari harus 1–{BATAS_HARI_MAKS}")
    if int(leverage) < 1:
        raise ValueError("leverage minimal 1")
    long = sisi == LONG
    if entry is not None and ((long and entry >= harga) or (not long and entry <= harga)):
        raise ValueError(f"limit {sisi} {entry} sudah lewat harga sekarang {harga}; kosongkan entry untuk masuk di harga pasar")
    acuan = entry if entry is not None else harga
    if (long and not sl < acuan < tp) or (not long and not tp < acuan < sl):
        raise ValueError(f"untuk {sisi} harus {'sl < masuk < tp' if long else 'tp < masuk < sl'} (masuk {acuan}, tp {tp}, sl {sl})")
    eod = C.ceil_minute(now_ms + int(batas_hari) * C.DAY_MS)
    return {"jenis": "ide", "id": iid, "dibuat_ms": int(now_ms), "dibuat": C.fmt_wib(now_ms), "hari": C.day_wib(now_ms), "symbol": symbol, "sisi": sisi,
            "entry": entry, "harga": harga, "tp": tp, "sl": sl, "leverage": int(leverage), "batas_hari": int(batas_hari), "eod_ms": eod,
            "tren_15m": tren_15m, "melawan_tren": melawan_tren(sisi, tren_15m), "rezim": rezim, "catatan": (catatan or "").strip()[:300], "versi": VERSI}


def hitung_rencana(sisi: str, acuan: float, tp: float, sl: float, leverage: int, brackets: list, limit: bool, cfg: Optional[EngineConfig] = None) -> dict:
    """Angka rencana per $100 nilai posisi: untung di target, rugi di stop, peluang menang minimum, dan jarak likuidasi. Slippage belum termasuk."""
    cfg = cfg or EngineConfig()
    qty = NILAI_POSISI / acuan
    masuk = fee_amount(NILAI_POSISI, limit, cfg)
    untung = abs(tp - acuan) * qty - masuk - fee_amount(tp * qty, True, cfg)
    rugi = abs(acuan - sl) * qty + masuk + fee_amount(sl * qty, False, cfg)
    b = pick_bracket(brackets, NILAI_POSISI) if brackets else None
    margin = NILAI_POSISI / leverage
    liq = liq_price(sisi, qty, acuan, margin, b.mmr if b else 0.0, b.cum if b else 0.0)
    return {"nilai_posisi": NILAI_POSISI, "margin": round(margin, 4), "untung_di_tp": round(untung, 4), "rugi_di_sl": round(rugi, 4),
            "rr": round(untung / rugi, 3) if rugi > 0 else None, "menang_minimum": round(rugi / (untung + rugi), 4) if untung > 0 else None,
            "likuidasi": liq, "likuidasi_sebelum_stop": liq >= sl if sisi == LONG else liq <= sl, "catatan": "per $100 nilai posisi, sudah termasuk fee, belum termasuk slippage dan funding"}


# --------------------------------------------------------------------------- penilaian
def templat_ide(ide: dict, brackets: list) -> dict:
    acuan = ide["entry"] if ide.get("entry") is not None else ide["harga"]
    b = pick_bracket(brackets, NILAI_POSISI) if brackets else None
    aktif = C.ceil_minute(int(ide["dibuat_ms"]) + 1)
    t = {"side": ide["sisi"], "entry": acuan, "tp": ide["tp"], "sl": ide["sl"], "lev": ide["leverage"], "qty": NILAI_POSISI / acuan,
         "mmr": b.mmr if b else 0.0, "cum": b.cum if b else 0.0, "aktif_ms": aktif, "eod_ms": int(ide["eod_ms"]), "tanpa_be": True}
    if ide.get("entry") is None:
        t["market_ms"] = aktif
    return t


def templat_cermin(t: dict, sim: dict) -> dict:
    """Arah sebaliknya, jarak target dan stop sama, masuk market di menit setelah ide terisi. Fee masuk taker, jadi sedikit lebih mahal dari limit."""
    e = float(sim["entry_isi"])
    masuk = int(sim["terisi_ms"]) + MINUTE_MS
    return {**t, "side": SHORT if t["side"] == LONG else LONG, "entry": e, "tp": e - (t["tp"] - e), "sl": e + (e - t["sl"]),
            "aktif_ms": masuk, "market_ms": masuk}


def nilai_ide(ide: dict, market, now_ms: int, slip: float, cfg: Optional[EngineConfig] = None) -> Optional[dict]:
    """Satu baris hasil. None = belum bisa dinilai final (bar mungkin menyusul); dicoba lagi pada run berikutnya."""
    t = templat_ide(ide, market.brackets(ide["symbol"]))
    pairs = market.bars(ide["symbol"], t["aktif_ms"] - MINUTE_MS, t["eod_ms"])
    sim = K.simulasi(t, pairs, slip, cfg)
    if sim["hasil"] == "ambigu" and now_ms < t["eod_ms"] + COBA_ULANG_MS:
        return None
    rec = {"id": ide["id"], "hari": ide["hari"], "symbol": ide["symbol"], "sisi": ide["sisi"], "rezim": ide.get("rezim"), "hasil": sim["hasil"], "net": sim.get("net"),
           "terisi_ms": sim.get("terisi_ms"), "keluar_ms": sim.get("keluar_ms"), "alasan": sim.get("alasan"), "cermin_hasil": None, "cermin_net": None,
           "dinilai_ms": now_ms, "versi": VERSI}
    if sim.get("terisi_ms") is not None and sim["hasil"] != "ambigu":
        tc = templat_cermin(t, sim)
        sc = K.simulasi(tc, market.bars(ide["symbol"], tc["aktif_ms"] - MINUTE_MS, tc["eod_ms"]), slip, cfg)
        rec["cermin_hasil"], rec["cermin_net"] = sc["hasil"], sc.get("net")
    return rec


# --------------------------------------------------------------------------- catatan
def pisah(records: list[dict]) -> tuple[dict, dict]:
    """({id: ide}, {id: saran pertama}) dari isi pasar/konsultasi.jsonl."""
    ide, saran = {}, {}
    for r in records:
        if r.get("jenis") == "ide":
            ide[r["id"]] = r
        elif r.get("jenis") == "saran":
            saran.setdefault(r["id"], r)
    return ide, saran


def _kelompok(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "rata": None, "menang": None}
    return {"n": len(xs), "rata": sum(xs) / len(xs), "menang": sum(1 for x in xs if x > K.NET_EPS) / len(xs)}


def mirip(skip_records: list[dict], records: list[dict], hasil: list[dict], symbol: str, sisi: str, lawan: bool) -> list[dict]:
    """Berapa kali kondisi serupa muncul di catatan dan bagaimana hasilnya. Hanya data yang sudah dinilai; n kecil dinyatakan belum cukup."""
    radar_arah, radar_koin = [], []
    for r in skip_records:
        if r.get("hasil") in ("ambigu", "TIDAK_TERISI") or r.get("net") is None or not r.get("qty") or not r.get("entry"):
            continue
        per100 = float(r["net"]) / (float(r["qty"]) * float(r["entry"])) * NILAI_POSISI
        if r.get("symbol") == symbol:
            radar_koin.append(per100)
        if r.get("arah") == sisi:
            try:
                flags = json.loads(r["flags"]) if isinstance(r.get("flags"), str) else list(r.get("flags") or [])
            except ValueError:
                flags = []
            if ("MELAWAN_TREN_15M" in flags) == lawan:
                radar_arah.append(per100)
    ide, _ = pisah(records)
    lama = [float(h["net"]) for h in hasil if h.get("net") is not None and h.get("hasil") not in ("ambigu", "TIDAK_TERISI")
            and h.get("sisi") == sisi and bool(ide.get(h["id"], {}).get("melawan_tren")) == lawan]
    tren = "melawan tren 15m" if lawan else "tidak melawan tren 15m"
    out = []
    for nama, xs in ((f"Radar: {sisi} {tren}", radar_arah), (f"Radar: koin {symbol}", radar_koin), (f"Ide Anda dulu: {sisi} {tren}", lama)):
        g = _kelompok(xs)
        out.append({"kelompok": nama, **g, "bacaan": "cukup data" if g["n"] >= MIRIP_MIN_N else f"belum cukup data (butuh ≥ {MIRIP_MIN_N})"})
    return out


# --------------------------------------------------------------------------- rapor
def _p_acak(pilihan: list[float], semua: list[float]) -> Optional[float]:
    """Peluang pilihan sebanyak ini yang diambil acak dari semua ide menghasilkan rata-rata setinggi saran agent."""
    if len(pilihan) < MIN_PER_KELOMPOK or len(semua) - len(pilihan) < MIN_PER_KELOMPOK:
        return None
    rng = random.Random(7)
    target = sum(pilihan) / len(pilihan)
    kena = sum(1 for _ in range(PERMUTASI) if sum(rng.sample(semua, len(pilihan))) / len(pilihan) >= target)
    return (kena + 1) / (PERMUTASI + 1)


def _syarat(kunci: str, nama: str, arti: str, nilai: str, lolos: bool, kemajuan: float) -> dict:
    return {"kunci": kunci, "nama": nama, "arti": arti, "nilai": nilai, "lolos": bool(lolos), "kemajuan": round(max(0.0, min(1.0, kemajuan)), 3)}


def rapor(records: list[dict], hasil: list[dict], now_ms: int) -> dict:
    ide, saran = pisah(records)
    hasil_map = {h["id"]: h for h in hasil}
    terisi = [h for h in hasil if h.get("net") is not None and h.get("hasil") not in ("ambigu", "TIDAK_TERISI")]
    dinilai = [h for h in terisi if h["id"] in saran]
    lanjut = [h for h in dinilai if saran[h["id"]]["saran"] == "lanjut"]
    hindari = [h for h in dinilai if saran[h["id"]]["saran"] == "hindari"]
    nets = lambda hs: [float(h["net"]) for h in hs]  # noqa: E731
    acak = lambda hs: [(float(h["net"]) + float(h["cermin_net"])) / 2 for h in hs if h.get("cermin_net") is not None]  # noqa: E731

    n = len(dinilai)
    hari = sorted({h["hari"] for h in dinilai})
    rentang = 0
    if hari:
        rentang = (C.parse_iso_ms(hari[-1] + "T00:00:00+07:00") - C.parse_iso_ms(hari[0] + "T00:00:00+07:00")) // C.DAY_MS + 1
    rezim: dict = {}
    for h in dinilai:
        if h.get("rezim") in ("naik", "turun", "datar"):
            rezim[h["rezim"]] = rezim.get(h["rezim"], 0) + 1
    rezim_cukup = sum(1 for v in rezim.values() if v >= MIN_PER_REZIM)
    g_lanjut, g_acak = _kelompok(nets(lanjut)), _kelompok(acak(lanjut))
    selang = selang_per_hari([(h["hari"], float(h["net"])) for h in lanjut]) if len(lanjut) >= MIN_PER_KELOMPOK else None
    p = _p_acak(nets(lanjut), nets(dinilai))
    hari_l = sorted({h["hari"] for h in lanjut})
    tengah = hari_l[len(hari_l) // 2] if len(hari_l) >= 2 else None
    awal = [float(h["net"]) for h in lanjut if tengah and h["hari"] < tengah]
    akhir = [float(h["net"]) for h in lanjut if tengah and h["hari"] >= tengah]
    uang = lambda x: "belum ada" if x is None else ("+" if x > 0 else "−" if x < 0 else "") + "$" + f"{abs(x):.2f}".replace(".", ",")  # noqa: E731

    untung = g_lanjut["n"] >= MIN_PER_KELOMPOK and g_lanjut["rata"] > 0 and selang is not None and selang[0] > 0
    kalahkan = g_acak["n"] >= MIN_PER_KELOMPOK and g_lanjut["rata"] > g_acak["rata"] and p is not None and p < P_MAKS
    tahan = len(awal) >= MIN_PER_PARUH and len(akhir) >= MIN_PER_PARUH and sum(awal) > 0 and sum(akhir) > 0
    syarat = [
        _syarat("pengalaman", "Cukup banyak saran", f"Minimal {MIN_SARAN} saran bot yang idenya benar-benar terisi dan sudah dinilai skrip.",
                f"{n} dari {MIN_SARAN}", n >= MIN_SARAN, n / MIN_SARAN),
        _syarat("lama", "Cukup lama", f"Rentang minimal {MIN_RENTANG_HARI} hari, dari minimal {MIN_HARI_BERBEDA} hari berbeda, supaya bukan satu pekan yang kebetulan.",
                f"{rentang} dari {MIN_RENTANG_HARI} hari · {len(hari)} dari {MIN_HARI_BERBEDA} hari berbeda",
                rentang >= MIN_RENTANG_HARI and len(hari) >= MIN_HARI_BERBEDA, min(rentang / MIN_RENTANG_HARI, len(hari) / MIN_HARI_BERBEDA)),
        _syarat("kondisi", "Beberapa kondisi pasar", f"Minimal {MIN_REZIM} kondisi pasar (BTC 20 hari naik, turun, atau datar), masing-masing minimal {MIN_PER_REZIM} saran.",
                f"{rezim_cukup} dari {MIN_REZIM} kondisi · " + (", ".join(f"{k} {v}" for k, v in sorted(rezim.items())) or "belum ada"),
                rezim_cukup >= MIN_REZIM, sum(min(v, MIN_PER_REZIM) for v in sorted(rezim.values(), reverse=True)[:MIN_REZIM]) / (MIN_REZIM * MIN_PER_REZIM)),
        _syarat("untung", "Untung setelah biaya", "Ide yang disarankan lanjut rata-rata untung setelah fee, dan batas bawah selang 90 % (hari diambil ulang utuh) di atas nol.",
                (f"{uang(g_lanjut['rata'])} per $100" if g_lanjut["n"] else "belum ada saran lanjut yang terisi") + (f" · batas bawah {uang(selang[0])}" if selang else ""), untung, 1.0 if untung else 0.0),
        _syarat("acak", "Mengalahkan acak", f"Lebih baik dari arah dilempar koin, dan peluang hasilnya hanya kebetulan di bawah {P_MAKS:.0%}.",
                (f"{uang(g_lanjut['rata'])} vs acak {uang(g_acak['rata'])}" if g_acak["n"] else "belum ada saran lanjut yang terisi") + (f" · peluang kebetulan {'di bawah 1%' if p < 0.01 else f'{p:.0%}'}" if p is not None else ""), kalahkan, 1.0 if kalahkan else 0.0),
        _syarat("tahan", "Tahan di data baru", f"Untung di paruh awal dan paruh akhir hari, masing-masing minimal {MIN_PER_PARUH} saran.",
                f"paruh awal {len(awal)} saran, {uang(sum(awal) / len(awal) if awal else None)} · paruh akhir {len(akhir)} saran, {uang(sum(akhir) / len(akhir) if akhir else None)}",
                tahan, 1.0 if tahan else 0.0),
    ]
    tahap = 2 if all(s["lolos"] for s in syarat) else (1 if all(s["lolos"] for s in syarat[:3]) else 0)
    terakhir = []
    for i in sorted(ide.values(), key=lambda r: -int(r["dibuat_ms"]))[:12]:
        h = hasil_map.get(i["id"])
        terakhir.append({k: i.get(k) for k in ("id", "dibuat_ms", "symbol", "sisi", "entry", "harga", "tp", "sl", "rezim", "eod_ms")} | {
            "saran": (saran.get(i["id"]) or {}).get("saran"), "poin_lanjut": (saran.get(i["id"]) or {}).get("poin_lanjut") or [], "poin_hindari": (saran.get(i["id"]) or {}).get("poin_hindari") or [],
            "hasil": h["hasil"] if h else None, "net": h.get("net") if h else None, "cermin_net": h.get("cermin_net") if h else None})
    return {"tahap": tahap, "tahap_nama": TAHAP[tahap], "syarat": syarat, "n_lolos": sum(1 for s in syarat if s["lolos"]), "n_syarat": len(syarat),
            "n_ide": len(ide), "n_menunggu": sum(1 for i in ide if i not in hasil_map), "n_tanpa_saran": sum(1 for i in ide if i not in saran),
            "banding": {"ide": _kelompok(nets(terisi)), "lanjut": g_lanjut, "hindari": _kelompok(nets(hindari)), "acak": {**_kelompok(acak(terisi)), "menang": None}},   # rata-rata dua arah: "menang" tidak bermakna
            "terakhir": terakhir, "sekarang": now_ms, "catatan": "Hasil per $100 nilai posisi, setelah fee dan slippage, tanpa funding. Paper trading; rapor tidak menjamin hasil ke depan."}


def pengetahuan(skip_records: list[dict], hip_hasil: list[dict], lessons: list[dict], now_ms: int) -> dict:
    """Bukti lain di luar konsultasi: pelajaran aktif, radar, dan hipotesis agent."""
    t = K.temuan(skip_records, now_ms)
    hip = [h for h in hip_hasil if h.get("hasil") in ("benar", "salah") and (h.get("baseline") or {}).get("rate") is not None]
    aktif = [l for l in lessons if l.get("status") == "aktif"]
    return {"pelajaran_aktif": len(aktif), "pelajaran": [l.get("ringkasan") for l in aktif][:6],
            "radar": {k: t[k] for k in ("n", "win", "mean", "impas")} if t else None,
            "hindari": [b for b in (t["baris"] if t else []) if b["bacaan"].startswith("indikasi buruk")][:5],
            "lebih_baik": [b for b in (t["baris"] if t else []) if b["bacaan"].startswith("indikasi lebih baik")][:5],
            "hipotesis": {"n": len(hip), "benar": sum(1 for h in hip if h["hasil"] == "benar") / len(hip),
                          "acak": sum(h["baseline"]["rate"] for h in hip) / len(hip)} if hip else None}


def render_konsultasi(r: dict) -> str:
    """Bagian pelajaran.md yang dibaca agent sebelum memberi saran. Kosong bila belum ada ide."""
    if not r["n_ide"]:
        return ""
    b = r["banding"]
    f = lambda g: (f"{g['n']} terisi, " + (f"menang {g['menang']:.0%}, " if g["menang"] is not None else "") + f"rata-rata {g['rata']:+.2f} per $100").replace(".", ",") if g["n"] else "belum ada yang terisi"  # noqa: E731
    return "\n".join(["## Dari konsultasi pemilik", "",
                      f"_Tahap: {r['tahap_nama']} ({r['n_lolos']} dari {r['n_syarat']} syarat). Ide dicatat lewat periksa_ide, dinilai skrip. Sebelum syarat terpenuhi, angka ini belum membuktikan apa pun._", "",
                      f"- **Semua ide pemilik:** {f(b['ide'])}.", f"- **Disarankan lanjut:** {f(b['lanjut'])}.", f"- **Disarankan hindari:** {f(b['hindari'])}.",
                      f"- **Arah dilempar koin:** {f(b['acak'])}.", ""])
