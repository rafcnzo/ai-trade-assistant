"""Tes hipotesis.py + uji_hipotesis.py (U1–U5): penilaian, ambigu, baseline, pelajaran. Tanpa jaringan."""
from __future__ import annotations

import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
import hipotesis as H  # noqa: E402
import uji_hipotesis as U  # noqa: E402
from common import HOUR_MS, Bar  # noqa: E402
from fixtures import BTC, DAY_MS, FixtureMarket, t  # noqa: E402

BASE = DAY_MS - 10 * C.DAY_MS   # awal data sintetis


def ladder(n: int = 48, start: int = BASE) -> list[Bar]:
    """Bar 1h menaik 1 per jam: close 100+i, high +0.5, low −0.5."""
    return [Bar(BTC, start + i * HOUR_MS, 100 + i - 0.2, 100 + i + 0.5, 100 + i - 0.5, 100 + i, 1, 1000, 10, 500) for i in range(n)]


def rec(jenis, arah, nilai=None, tf="1h", dibuat=BASE + 10 * HOUR_MS + 5 * C.MINUTE_MS, batas_hari=1, harga_awal=110.0, atr_awal=1.0, **kw):
    return H.new_record("H-0001", dibuat, "kompresi", BTC, tf, jenis, arah, nilai, batas_hari, "range 10 bar < 2×ATR", "", harga_awal, atr_awal, "uji", **kw)


def wave_market(days: int = 130) -> FixtureMarket:
    m = FixtureMarket()
    rng = random.Random(7)
    for i in range(days * 24):
        px = 80000 + 1500 * math.sin(i / 37.0) + 400 * math.sin(i / 5.0) + rng.uniform(-60, 60)
        m.add_bar_1h(BTC, BASE - days * C.DAY_MS + i * HOUR_MS, px, px + 90, px - 90, px + rng.uniform(-30, 30))
    return m


class TestJudge(unittest.TestCase):
    def test_u1_three_kinds_no_lookback(self):
        bars = ladder()
        # horizon: bucket pertama = 11:00 (dibuat 10:05), batas = dibuat + 24 jam → bar 11..33
        self.assertEqual(H.judge(rec("sentuh_harga", "atas", 130.0), bars)["hasil"], "benar")
        self.assertEqual(H.judge(rec("sentuh_harga", "atas", 134.0), bars)["hasil"], "salah")     # high maks bar 33 = 133.5
        self.assertEqual(H.judge(rec("sentuh_harga", "bawah", 108.0), bars)["hasil"], "salah")    # low bar 5–10 < 108 tapi sebelum awal → tidak dihitung
        j = H.judge(rec("gerak_atr", "atas", 5.0), bars)
        self.assertEqual((j["hasil"], j["target"]), ("benar", 115.0))
        self.assertEqual(H.judge(rec("gerak_atr", "bawah", 2.0), bars)["hasil"], "salah")
        self.assertEqual(H.judge(rec("close_arah", "atas"), bars)["hasil"], "benar")
        j2 = H.judge(rec("close_arah", "bawah"), bars)
        self.assertEqual((j2["hasil"], j2["n_bar"], j2["ekstrem"]), ("salah", 23, 133.0))
        with self.assertRaises(ValueError):
            rec("sentuh_harga", "atas", 90.0)            # target di sisi salah
        with self.assertRaises(ValueError):
            rec("gerak_atr", "atas", 2.0, atr_awal=None)
        with self.assertRaises(ValueError):
            rec("close_arah", "atas", tf="2h")
        with self.assertRaises(ValueError):
            rec("close_arah", "atas", batas_hari=9)

    def test_u2_ambiguous_and_not_due(self):
        bars = ladder()
        sparse = [b for i, b in enumerate(bars) if i % 3]           # 1/3 bar hilang → coverage 67%
        j = H.judge(rec("sentuh_harga", "atas", 130.0), sparse)
        self.assertEqual(j["hasil"], "ambigu")
        self.assertIn("data bar", j["alasan"])
        r = rec("gerak_atr", "atas", 2.0)
        r["atr_awal"] = None
        self.assertEqual(H.judge(r, bars)["hasil"], "ambigu")
        self.assertEqual(H.judge(rec("close_arah", "atas"), [])["hasil"], "ambigu")
        # belum jatuh tempo → run() tidak menilai, pesan kosong
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            root = Path(d)
            H.append_jsonl(root / "pasar" / "hipotesis.jsonl", rec("close_arah", "atas"))
            s = U.run(root, FixtureMarket(), BASE + 20 * HOUR_MS)
            self.assertEqual((s["dinilai"], s["pesan"]), ([], ""))
            self.assertFalse((root / "pasar" / "hipotesis-hasil.jsonl").exists())


class TestBaseline(unittest.TestCase):
    def test_u3_baseline_deterministic_and_bounded(self):
        m = wave_market()
        bars = m.bars_1h(BTC, 0, BASE + C.DAY_MS)
        r = rec("gerak_atr", "atas", 1.5, dibuat=BASE - 3 * C.DAY_MS, harga_awal=80000.0, atr_awal=150.0, batas_hari=2)
        b1 = H.baseline(r, bars, random.Random("uji-v1:H-0001"))
        b2 = H.baseline(r, bars, random.Random("uji-v1:H-0001"))
        self.assertEqual(b1, b2)
        self.assertTrue(0.0 <= b1["rate"] <= 1.0)
        self.assertLessEqual(b1["n_valid"], H.BASELINE_N)
        self.assertGreaterEqual(b1["n_valid"], H.BASELINE_MIN_VALID)
        b3 = H.baseline(rec("sentuh_harga", "atas", 80100.0, dibuat=BASE - 3 * C.DAY_MS, harga_awal=80000.0, batas_hari=2), bars, random.Random("x"))
        self.assertIsNotNone(b3["rate"])
        self.assertIsNone(H.baseline(r, bars[:60], random.Random("x"))["rate"])     # data terlalu sedikit


class TestLessons(unittest.TestCase):
    def mk(self, pola, n, benar, base, start_id=1, dinilai_ms=BASE):
        recs, hasil = [], {}
        for i in range(n):
            hid = f"H-{start_id + i:04d}"
            recs.append({"id": hid, "pola": pola, "symbol": BTC, "tf": "1h", "jenis": "close_arah", "arah": "atas", "nilai": None,
                         "harga_awal": 100.0, "atr_awal": 1.0, "batas_hari": 1, "dibuat_ms": BASE, "batas_ms": BASE + C.DAY_MS,
                         "hari": C.day_wib(BASE), "batas": C.day_wib(BASE + C.DAY_MS), "kondisi": "k", "catatan": ""})
            hasil[hid] = {"id": hid, "hasil": "benar" if i < benar else "salah", "alasan": "a", "dinilai_ms": dinilai_ms,
                          "baseline": {"rate": base, "n_valid": 100, "n_benar": int(base * 100)}}
        return recs, hasil

    def test_u4_promotion_cap_and_usulan(self):
        recs, hasil = self.mk("kompresi", 12, 10, 0.3)
        r2, h2 = self.mk("wick-penolakan", 9, 9, 0.1, start_id=100)
        recs += r2
        hasil.update(h2)
        lessons, ch = U.update_lessons(recs, hasil, [], BASE + 2 * C.DAY_MS, U.UjiConfig())
        self.assertEqual([l["id"] for l in lessons], ["L-01"])
        self.assertEqual((lessons[0]["pola"], lessons[0]["status"], lessons[0]["sampel"]), ("kompresi", "aktif", 12))
        self.assertAlmostEqual(lessons[0]["hit_rate"], 10 / 12)
        self.assertEqual(len(ch), 1)
        self.assertIn("L-01 kompresi AKTIF", ch[0])
        md = H.render_pelajaran_md(lessons)
        self.assertIn("| L-01 | kompresi |", md)
        self.assertIn("## Pensiun", md)
        # cap 15 aktif
        full = [dict(lessons[0], id=f"L-{i:02d}", pola=f"p{i}") for i in range(1, 16)]
        lessons2, ch2 = U.update_lessons(recs, hasil, full, BASE + 2 * C.DAY_MS, U.UjiConfig())
        self.assertEqual(len(lessons2), 15)
        self.assertTrue(any("sudah 15" in c for c in ch2))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            root = Path(d)
            p = root / "pasar" / "pelajaran-usulan.md"
            p.parent.mkdir(parents=True)
            p.write_text("# Usulan\n\n| ID | Tanggal | Pola | Ringkasan | Bukti | Sampel | Status |\n|---|---|---|---|---|---|---|\n"
                         "| U-001 | 2026-10-11 | kompresi | r | b | 3 | uji |\n| U-002 | 2026-10-11 | kompresi | r | b | 3 | uji |\n"
                         "| U-003 | 2026-10-11 | kompresi | r | b | 3 | aktif |\n", encoding="utf-8")
            before = p.read_text(encoding="utf-8")
            self.assertEqual(U.usulan_menunggu(root), 2)
            s = U.run(root, FixtureMarket(), BASE)
            self.assertEqual(p.read_text(encoding="utf-8"), before)
            self.assertEqual(s["usulan_uji"], 2)

    def test_u5_reevaluate_retire_and_end_to_end(self):
        recs, hasil = self.mk("kompresi", 12, 10, 0.3, dinilai_ms=BASE - 95 * C.DAY_MS)   # di luar jendela 90 hari saat dinilai ulang
        lessons, _ = U.update_lessons(recs, hasil, [], BASE, U.UjiConfig())
        later = BASE + 31 * C.DAY_MS
        r2, h2 = self.mk("kompresi", 12, 4, 0.3, start_id=50, dinilai_ms=later - C.DAY_MS)     # 90 hari terakhir: 33% ≈ baseline
        lessons2, ch = U.update_lessons(recs + r2, {**hasil, **h2}, lessons, later, U.UjiConfig())
        self.assertEqual(lessons2[0]["status"], "pensiun")
        self.assertIn("PENSIUN", ch[0])
        self.assertIn("pensiun (hit rate 90 hari", H.render_pelajaran_md(lessons2))
        # end-to-end: satu hipotesis jatuh tempo pada data pasar sintetis
        m = wave_market(20)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            root = Path(d)
            dibuat = BASE - 3 * C.DAY_MS + 5 * C.MINUTE_MS
            bars = m.bars_1h(BTC, dibuat, dibuat + C.DAY_MS)
            lo = min(b.low for b in bars[1:]) - 1
            H.append_jsonl(root / "pasar" / "hipotesis.jsonl",
                           H.new_record("H-0001", dibuat, "kapitulasi", BTC, "1h", "sentuh_harga", "bawah", lo, 1, "kondisi", "", bars[0].open, 150.0, "uji"))
            now = dibuat + C.DAY_MS + HOUR_MS
            s = U.run(root, m, now)
            self.assertEqual(len(s["dinilai"]), 1)
            self.assertEqual(s["dinilai"][0]["hasil_"]["hasil"], "salah")
            self.assertIn("H-0001 kapitulasi BTCUSDT 1h sentuh_harga bawah", s["pesan"])
            self.assertIn("SALAH", s["pesan"])
            res = H.load_jsonl(root / "pasar" / "hipotesis-hasil.jsonl")
            self.assertEqual((len(res), res[0]["baseline"]["seed"]), (1, "uji-v1:H-0001"))
            self.assertTrue((root / "pasar" / "hipotesis.md").exists())
            self.assertIn("| H-0001 |", (root / "pasar" / "hipotesis.md").read_text(encoding="utf-8"))
            self.assertTrue((root / "pasar" / "pelajaran.md").exists())
            # run kedua: tidak menilai ulang, pesan kosong
            s2 = U.run(root, m, now + HOUR_MS)
            self.assertEqual((s2["dinilai"], s2["pesan"]), ([], ""))


if __name__ == "__main__":
    unittest.main()
