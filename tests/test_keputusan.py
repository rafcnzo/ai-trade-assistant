"""Tes keputusan.py (KP1–KP3): rakit keputusan arena per kandidat dari jurnal; markdown Telegram baku; tanpa jaringan."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import keputusan as KP  # noqa: E402
from fixtures import DAY  # noqa: E402

# pola yang dipakai adapter Telegram Hermes (gateway/platforms/helpers.py TABLE_SEPARATOR_RE) untuk memilih Rich Message
HERMES_TABLE_SEPARATOR_RE = re.compile(r'^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*){1,}\|?\s*$')

JURNAL = """
## 07:12 WIB — keputusan — [rentang] K221 DOGEUSDT LONG - SKIP
_symbol=DOGEUSDT kandidat=221 alasan=RR_P19_

Ada sideways | kompresi, tapi target ke tengah range terlalu kecil.

## 07:12 WIB — keputusan — [tiket] K221 DOGEUSDT LONG - SKIP
_symbol=DOGEUSDT kandidat=221 alasan=RR_P19 poin=3-2_

**Alasan SKIP (3):**
- VETO: untung $0,34 vs hangus $1,00 (P-19)
- level baru 2 sentuhan
- tren 15m sideways
**Alasan OPEN (2):**
- penolakan wick jelas
- funding netral

Target paling jauh hanya untung $0,34 vs hangus $1,00 (P-19).

## 07:13 WIB — keputusan — [fade] K221 DOGEUSDT LONG - order #31
_symbol=DOGEUSDT kandidat=221 order=31_

Takut ekstrem + divergensi; LONG di support.

## 07:20 WIB — keputusan — [breakout] K222 1000PEPEUSDT SHORT - SKIP
_symbol=1000PEPEUSDT kandidat=222 alasan=NO_VOL_TEMBUS_

Tembus gagal.

## 08:00 WIB — catatan — budget
Saldo masih cukup.
"""

KAND = {221: {"id": 221, "symbol": "DOGEUSDT", "arah_dugaan": "LONG", "mark": 0.07869, "level": 0.07872, "sentuhan": 2,
              "atr_15m": 0.0002626679, "flags": json.dumps(["DEKAT_LEVEL", "WICK"]), "score": 4, "run_ts": 1791857520000,
              "ringkasan": "DOGEUSDT LONG skor 4 | tren15m sideways | lev layak: 75x"}}
ORDERS = {31: {"id": 31, "account": "fade", "side": "LONG", "type": "LIMIT", "price": 0.0787, "leverage": 50, "tp_price": 0.0791, "status": "FILLED"}}
POSISI = {31: {"id": 5, "status": "CLOSED", "close_reason": "TP", "net_result": 0.12}}
SKIP = {221: {"kandidat_id": 221, "hasil": "HANGUS", "net": -0.9,
              "keputusan": {"tiket": {"label": "benar"}, "rentang": {"label": "benar"}, "fade": {"label": "order"}}}}


class TestKeputusan(unittest.TestCase):
    def test_kp1_kelompok(self):
        out = KP.kelompok(JURNAL, KAND, ORDERS, POSISI, SKIP, DAY)
        self.assertEqual([g["kandidat_id"] for g in out["kandidat"]], [222, 221])          # terbaru dulu
        g = out["kandidat"][1]
        self.assertEqual([b["persona"] for b in g["baris"]], ["tiket", "fade", "rentang"])  # urutan persona tetap
        self.assertEqual((g["jam"], g["symbol"], g["arah"], g["ringkas"]), ("07:12", "DOGEUSDT", "LONG", "1 order (fade) · 2 SKIP"))
        tiket = g["baris"][0]
        self.assertEqual((tiket["alasan"], tiket["label_alasan"], tiket["penilaian"]["jenis"]), ("RR_P19", "R:R < 0,5 (P-19)", "benar"))
        self.assertEqual(tiket["teks"], "Target paling jauh hanya untung $0,34 vs hangus $1,00 (P-19).")       # poin tidak bocor ke teks
        self.assertEqual((tiket["poin_skip"][1], tiket["poin_open"]), ("level baru 2 sentuhan", ["penolakan wick jelas", "funding netral"]))
        self.assertEqual(tiket["timbangan"], {"skip": 3, "open": 2, "veto": True, "hitungan": "SKIP", "sesuai": True})
        self.assertIsNone(g["baris"][1]["timbangan"])                                                   # keputusan lama tanpa poin
        fade = g["baris"][1]
        self.assertEqual((fade["order_id"], fade["order"]["leverage"], fade["penilaian"]), (31, 50, {"jenis": "hasil", "net": 0.12, "hasil": "TP"}))
        self.assertEqual(g["fakta"]["tanda"], ["WICK"])
        self.assertEqual(g["fakta"]["tren_15m"], "sideways")
        k222 = out["kandidat"][0]
        self.assertEqual((k222["fakta"], k222["baris"][0]["penilaian"]["jenis"], k222["ringkas"]), (None, "belum", "SKIP"))
        self.assertIn("## 08:00 WIB — catatan — budget", out["lain_md"])
        self.assertNotIn("K221", out["lain_md"])

    def test_kp2_markdown_telegram_baku(self):
        g = KP.kelompok(JURNAL, KAND, ORDERS, None, None, DAY)["kandidat"][1]
        md = KP.render_markdown(g)
        lines = md.splitlines()
        self.assertEqual(lines[0], "**Arena K221 · DOGEUSDT LONG · 07:12 WIB** — 1 order (fade) · 2 SKIP")
        self.assertIn("Mark **0.07869** · level **0.07872** (2 sentuhan) · ATR 15m 0.000262668 (0,33 %) · tren 15m sideways · tanda WICK", md)
        self.assertIn("| Persona | Hasil | Timbangan |", lines)
        self.assertTrue(any(HERMES_TABLE_SEPARATOR_RE.match(l) for l in lines))              # → Hermes mengirim sebagai Rich Message
        self.assertIn("| tiket | SKIP | skip 3 · open 2 · veto |", lines)
        self.assertIn("| fade | **ORDER #31** LONG limit 0.0787 · 50× · TP 0.0791 | — |", lines)
        self.assertIn("| rentang | SKIP | — |", lines)
        self.assertTrue(all(l.count("|") == 4 for l in lines if l.startswith("|")))
        self.assertEqual(lines.index("| Persona | Hasil | Timbangan |") - lines.index(next(l for l in lines if l.startswith("Mark"))), 2)   # baris kosong sebelum tabel
        # poin per persona di bawah tabel, urutan persona sama dengan tabel
        i = lines.index("**tiket — SKIP**")
        self.assertEqual(lines[i + 1:i + 8], ["Alasan SKIP (3):", "- VETO: untung $0,34 vs hangus $1,00 (P-19)", "- level baru 2 sentuhan",
                                              "- tren 15m sideways", "Alasan OPEN (2):", "- penolakan wick jelas", "- funding netral"])
        self.assertLess(i, lines.index("**fade — ORDER**"))
        self.assertIn("- Ada sideways / kompresi, tapi target ke tengah range terlalu kecil.", lines)   # keputusan lama: satu poin dari teks

    def test_kp3_angka_dan_sel(self):
        self.assertEqual([KP._px(x) for x in (1.97078e-05, 0.00440663, 82592.6, 106.42, 0, None)], ["0.0000197078", "0.00440663", "82592.6", "106.42", "0", "—"])
        panjang = "kata " * 100
        s = KP.sel(panjang, 50)
        self.assertTrue(s.endswith("…") and len(s) <= 51)
        self.assertEqual(KP.sel("a | b\nc"), "a / b c")


if __name__ == "__main__":
    unittest.main()
