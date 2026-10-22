"""Tes kontrafaktual.py + tahap SKIP di uji_hipotesis.py (K1–K5): parser jurnal, klasifikasi alasan, simulasi order bayangan,
penilaian idempoten, pelajaran SKIP. Tanpa jaringan."""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
import hipotesis as H  # noqa: E402
import kontrafaktual as K  # noqa: E402
import uji_hipotesis as U  # noqa: E402
from common import MINUTE_MS  # noqa: E402
from fixtures import BRACKETS, DAY, DAY2, FILTERS, PEM, FixtureMarket, t  # noqa: E402

SLIP = 0.0005
JURNAL = """
## 08:17 WIB — keputusan — [tiket] K175-K177 - SKIP
Semua di bawah P-19: TP 1,5×ATR15m tidak cukup.

## 08:21 WIB — keputusan — [fade] K176 SOLUSDT LONG - SKIP
_symbol=SOLUSDT kandidat=176 alasan=PANEL_FADE_

Panel 0 ekstrem, tidak ada divergensi.

## 08:31 WIB — keputusan — [breakout] K181 XRPUSDT - SKIP
_symbol=XRPUSDT kandidat=181_

Tidak ada flag VOL dan close 5m kembali di dalam level.

## 08:40 WIB — keputusan — K182 BNBUSDT SHORT - order #7
_symbol=BNBUSDT kandidat=182 order=7_

Level 3 sentuhan, wick menolak.

## 08:41 WIB — keputusan — [tiket] K182 BNBUSDT SHORT - SKIP
_symbol=BNBUSDT kandidat=182_

Melawan tren 15m.

## 09:00 WIB — catatan — budget
Tidak relevan.
"""


def kandidat(**kw) -> dict:
    k = {"id": 1, "run_ts": t("10:03", sec=27), "day_wib": DAY, "symbol": PEM, "arah_dugaan": "LONG", "level": 99.5, "atr_15m": 1.0,
         "lev_layak": json.dumps([{"leverage": 20, "qty": "0.1"}, {"leverage": 10, "qty": "0.1"}]), "score": 4, "flags": "[]"}
    k.update(kw)
    return k


def tpl(**kw) -> dict:
    tp_ = K.templat(kandidat(**kw), FILTERS[PEM], BRACKETS[PEM])
    assert tp_["ok"], tp_
    return tp_


def flat_bars(m: FixtureMarket, start: str, end: str, px: float, day_ms: int = None):
    """Bar datar (range ±0.05) dari start sampai end inklusif."""
    a, b = t(start), t(end)
    for ot in range(a, b + 1, MINUTE_MS):
        m.add_bar(PEM, ot, px, px + 0.05, px - 0.05, px)


class TestParser(unittest.TestCase):
    def test_k1_parse_variants(self):
        rows = K.parse_keputusan(JURNAL)
        got = {(r["persona"], r["kandidat_id"], r["keputusan"]) for r in rows}
        self.assertIn(("tiket", 175, "SKIP"), got)
        self.assertIn(("tiket", 177, "SKIP"), got)                         # rentang K175-K177
        self.assertIn(("fade", 176, "SKIP"), got)
        self.assertIn(("breakout", 181, "SKIP"), got)                      # tanpa arah
        self.assertIn(("tiket", 182, "ORDER"), got)                        # judul tanpa persona = tiket
        self.assertEqual(len([r for r in rows if r["kandidat_id"] == 176]), 2)
        fade = next(r for r in rows if r["persona"] == "fade")
        self.assertEqual(fade["alasan"], "PANEL_FADE")                     # dari meta alasan=
        kp = K.keputusan_per_kandidat(rows)
        self.assertEqual(kp[182]["tiket"]["keputusan"], "ORDER")           # ORDER mengalahkan SKIP persona yang sama
        self.assertEqual(kp[181]["breakout"]["alasan"], "NO_VOL_TEMBUS")
        self.assertEqual(kp[175]["tiket"]["alasan"], "RR_P19")

    def test_k2_klasifikasi(self):
        self.assertEqual(K.klasifikasi_alasan("Data OHLCV basi + SUDAH_LARI"), "BASI")
        self.assertEqual(K.klasifikasi_alasan("untung bersih < 0,5× rugi hangus (P-19/U-001)"), "RR_P19")
        self.assertEqual(K.klasifikasi_alasan("melawan tren 15m (naik)"), "TREN_15M")
        self.assertEqual(K.klasifikasi_alasan("LIMIT_CROSSES saat pasang"), "LIMIT_CROSSES")
        self.assertEqual(K.klasifikasi_alasan("hanya 1 indikator ekstrem", "fade"), "PANEL_FADE")
        self.assertEqual(K.klasifikasi_alasan("tren 15m naik, bukan sideways", "rentang"), "NO_SIDEWAYS")
        self.assertEqual(K.klasifikasi_alasan("tanpa VOL", "breakout"), "NO_VOL_TEMBUS")
        self.assertEqual(K.klasifikasi_alasan("cuaca buruk"), "LAIN")


class TestSimulasi(unittest.TestCase):
    def setUp(self):
        self.m = FixtureMarket()

    def sim(self, tp_=None):
        tp_ = tp_ or tpl()
        return K.simulasi(tp_, self.m.bars(PEM, tp_["aktif_ms"] - MINUTE_MS, tp_["eod_ms"]), SLIP)

    def test_k3_templat(self):
        tp_ = tpl()
        self.assertEqual((tp_["side"], tp_["entry"], tp_["tp"], tp_["lev"], tp_["qty"]), ("LONG", 99.5, 101.0, 10, 0.1))   # leverage layak terendah
        self.assertEqual((tp_["aktif_ms"], tp_["eod_ms"]), (t("10:04"), t("23:50")))
        self.assertAlmostEqual(tp_["liq"], (0.1 * 99.5 - 0.995) / (0.1 * (1 - 0.004)), places=6)
        s = K.templat(kandidat(arah_dugaan="SHORT", level=100.504), FILTERS[PEM], BRACKETS[PEM])
        self.assertEqual((s["entry"], s["tp"]), (100.51, 99.01))               # dibulatkan menjauh dari mark / mendekati entry
        self.assertFalse(K.templat(kandidat(lev_layak="[]"), FILTERS[PEM], BRACKETS[PEM])["ok"])
        self.assertFalse(K.templat(kandidat(atr_15m=None), FILTERS[PEM], BRACKETS[PEM])["ok"])

    def test_k3_tp_hangus_tidak_terisi_eod_breakeven(self):
        # TP
        self.m.add_bar(PEM, t("10:04"), 100.0, 100.2, 99.4, 99.8)          # isi THROUGH 99.5; bar entry tanpa TP
        self.m.add_bar(PEM, t("10:05"), 99.8, 101.1, 99.7, 101.0)          # TP 101
        r = self.sim()
        self.assertEqual(r["hasil"], "TP")
        self.assertAlmostEqual(r["net"], 1.5 * 0.1 - 0.0002 * (9.95 + 10.1), places=6)
        self.assertEqual(K.label_skip(r), "salah")
        # HANGUS
        self.m = FixtureMarket()
        self.m.add_bar(PEM, t("10:04"), 100.0, 100.2, 99.4, 99.8)
        self.m.add_bar(PEM, t("10:05"), 99.8, 99.9, 89.0, 89.5)
        r = self.sim()
        self.assertEqual(r["hasil"], "HANGUS")
        self.assertAlmostEqual(r["net"], -0.995 - 0.0002 * 9.95, places=6)
        self.assertEqual(K.label_skip(r), "benar")
        # tidak terisi sepanjang hari (bar lengkap)
        self.m = FixtureMarket()
        flat_bars(self.m, "10:04", "23:50", 100.0)
        r = self.sim()
        self.assertEqual((r["hasil"], K.label_skip(r)), ("TIDAK_TERISI", "netral"))
        # EOD: terisi lalu datar sampai 23:50 → tutup di open bar 23:50 dengan slippage (taker)
        self.m = FixtureMarket()
        self.m.add_bar(PEM, t("10:04"), 100.0, 100.2, 99.4, 99.8)
        flat_bars(self.m, "10:05", "23:50", 99.8)
        r = self.sim()
        self.assertEqual(r["hasil"], "EOD")
        self.assertAlmostEqual(r["keluar"], 99.8 * (1 - SLIP), places=9)
        # breakeven P-18: harga menempuh ≥ 80% ke TP lalu kembali → STOP_BE di harga masuk (rugi kecil karena fee+slip)
        self.m = FixtureMarket()
        self.m.add_bar(PEM, t("10:04"), 100.0, 100.2, 99.4, 99.8)
        self.m.add_bar(PEM, t("10:05"), 99.8, 100.8, 99.7, 100.7)          # 1.3/1.5 = 87%
        self.m.add_bar(PEM, t("10:06"), 100.7, 100.7, 99.3, 99.4)          # SL BE kena
        r = self.sim()
        self.assertEqual(r["hasil"], "STOP_BE")
        self.assertLess(r["net"], 0)
        self.assertGreater(r["mfe_tp"], 0.8)
        # bar entry pesimis: masuk dan menyentuh likuidasi di bar yang sama → HANGUS
        self.m = FixtureMarket()
        self.m.add_bar(PEM, t("10:04"), 100.0, 101.5, 89.0, 95.0)
        self.assertEqual(self.sim()["hasil"], "HANGUS")

    def test_k3_cakupan_ambigu(self):
        self.m.add_bar(PEM, t("10:04"), 100.0, 100.2, 99.6, 100.0)          # tidak terisi, lalu data hilang
        flat_bars(self.m, "10:05", "12:00", 100.0)
        r = self.sim()
        self.assertEqual((r["hasil"], K.label_skip(r)), ("ambigu", "ambigu"))


class TestNilaiSkip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        kc = C.connect(self.root / "data" / "kandidat.sqlite")
        C.init_schema(kc, C.SCRIPTS_DIR / "schema_kandidat.sql", "1")
        with C.tx(kc):
            for k in (kandidat(id=1), kandidat(id=2, arah_dugaan="SHORT", level=100.5, run_ts=t("10:03", sec=30)),
                      kandidat(id=3, day_wib=DAY2, run_ts=t("10:03", C.day_start_wib_ms(DAY2)))):
                kc.execute("INSERT INTO kandidat(id,run_ts,day_wib,symbol,arah_dugaan,mark,level,sentuhan,jarak_atr5m,atr_15m,lev_layak,score,flags) "
                           "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (k["id"], k["run_ts"], k["day_wib"], k["symbol"], k["arah_dugaan"], 100.0, k["level"], 3, 0.3,
                                                                k["atr_15m"], k["lev_layak"], k["score"], k["flags"]))
        kc.close()
        (self.root / "jurnal" / "agent").mkdir(parents=True)
        (self.root / "jurnal" / "agent" / f"{DAY}.md").write_text(
            "## 10:04 WIB — keputusan — [tiket] K1 PEMUSDT LONG - SKIP\n_kandidat=1 alasan=TREN_15M_\n\nmelawan tren\n\n"
            "## 10:04 WIB — keputusan — [fade] K1 PEMUSDT LONG - SKIP\n_kandidat=1_\n\ntidak ada divergensi\n\n"
            "## 10:05 WIB — keputusan — [tiket] K2 PEMUSDT SHORT - order #9\n_kandidat=2 order=9_\n\nmasuk\n", encoding="utf-8")
        self.m = FixtureMarket()
        self.m.add_bar(PEM, t("10:04"), 100.0, 100.2, 99.4, 99.8)           # K1 terisi; K2 (SHORT 100.5) tidak
        self.m.add_bar(PEM, t("10:05"), 99.8, 101.1, 99.7, 101.0)           # K1 TP; K2 terisi THROUGH 100.5
        flat_bars(self.m, "10:06", "23:50", 101.0)                           # K2 SHORT rugi sampai EOD

    def tearDown(self):
        self.tmp.cleanup()

    def test_k4_nilai_skip_idempoten_dan_run(self):
        now = t("10:00", C.day_start_wib_ms(DAY2) + 3 * C.DAY_MS)           # > 36 jam setelah 23:50 DAY2
        log = logging.getLogger("tes")
        recs = U.nilai_skip(self.root, self.m, now, log)
        by = {r["kandidat_id"]: r for r in recs}
        self.assertEqual(sorted(by), [1, 2, 3])                              # DAY2 sudah tutup juga
        self.assertEqual(by[1]["hasil"], "TP")
        self.assertEqual(by[1]["keputusan"]["tiket"], {**by[1]["keputusan"]["tiket"], "keputusan": "SKIP", "alasan": "TREN_15M", "label": "salah"})
        self.assertEqual(by[1]["keputusan"]["fade"]["alasan"], "PANEL_FADE")
        self.assertEqual(by[2]["hasil"], "EOD")
        self.assertEqual(by[2]["keputusan"]["tiket"]["label"], "order")
        self.assertEqual((by[3]["hasil"], by[3]["keputusan"]), ("ambigu", {}))   # tanpa bar → ambigu final (> 36 jam), tanpa keputusan
        self.assertEqual(U.nilai_skip(self.root, self.m, now, log), [])     # idempoten
        self.assertEqual(len(H.load_jsonl(self.root / "pasar" / "skip-hasil.jsonl")), 3)
        # ambigu < 36 jam setelah 23:50 → ditunda (bar mungkin masih menyusul)
        r3 = Path(tempfile.mkdtemp(dir=self.tmp.name))
        (r3 / "data").mkdir()
        import shutil
        shutil.copy(self.root / "data" / "kandidat.sqlite", r3 / "data" / "kandidat.sqlite")
        mid = t("10:00", C.day_start_wib_ms(DAY2) + C.DAY_MS)             # 10 jam setelah 23:50 DAY2
        self.assertEqual({r["kandidat_id"] for r in U.nilai_skip(r3, self.m, mid, log)}, {1, 2})
        # kandidat hari ini tidak dinilai; ambigu < 36 jam ditunda
        self.tmp2 = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        r2 = Path(self.tmp2.name)
        (r2 / "data").mkdir()
        import shutil
        shutil.copy(self.root / "data" / "kandidat.sqlite", r2 / "data" / "kandidat.sqlite")
        early = t("08:00", C.day_start_wib_ms(DAY2))
        got = {r["kandidat_id"] for r in U.nilai_skip(r2, self.m, early, log)}
        self.assertEqual(got, {1, 2})                                        # K3 (DAY2) = hari ini → belum
        self.tmp2.cleanup()
        # run penuh: pesan memuat baris SKIP, skip.md & pelajaran.md dibuat
        s = U.run(self.root, self.m, now + C.HOUR_MS)
        self.assertEqual(s["pesan"], "")                                    # tidak ada kandidat baru → diam
        (self.root / "pasar" / "skip-hasil.jsonl").unlink()
        s = U.run(self.root, self.m, now + 2 * C.HOUR_MS)
        self.assertIn("🚦 SKIP dinilai", s["pesan"])
        self.assertIn("SKIP benar 0, salah 2", s["pesan"])
        self.assertIn("Peluang terbesar terlewat: K1 PEMUSDT LONG → TP", s["pesan"])
        md = (self.root / "pasar" / "skip.md").read_text(encoding="utf-8")
        self.assertIn("| tiket | 1 | 0 | 1 | 0 | 0% |", md)
        self.assertIn("## Dari keputusan SKIP", (self.root / "pasar" / "pelajaran.md").read_text(encoding="utf-8"))


class TestPelajaranSkip(unittest.TestCase):
    def recs(self, now, n_lose=20, n_win=20, skip_lose=16, skip_win=2, kat="TREN_15M", start=0):
        out = []
        for i in range(n_lose + n_win):
            lose = i < n_lose
            kep = {}
            if (lose and i < skip_lose) or (not lose and i - n_lose < skip_win):
                kep["tiket"] = {"keputusan": "SKIP", "alasan": kat, "label": "benar" if lose else "salah"}
            out.append({"kandidat_id": start + i, "run_ts": now - C.DAY_MS, "hasil": "HANGUS" if lose else "TP", "net": -1.0 if lose else 0.4, "keputusan": kep})
        return out

    def test_k5_promosi_dan_pensiun(self):
        now = t("21:15")
        les, ch = K.update_skip_lessons(self.recs(now), [], now)
        pola = {l["pola"]: l for l in les}
        self.assertEqual(set(pola), {"skip:tiket:TREN_15M", "skip:semua:TREN_15M"})
        l = pola["skip:tiket:TREN_15M"]
        self.assertEqual((l["sumber"], l["arah"], l["sampel"], l["status"]), ("skip", "menyaring", 18, "aktif"))
        self.assertAlmostEqual(l["hit_rate"], 16 / 18)
        self.assertAlmostEqual(l["baseline"], 0.5)
        self.assertTrue(any("AKTIF" in c for c in ch))
        # sampel < 15 → tidak ada pelajaran
        self.assertEqual(K.update_skip_lessons(self.recs(now, skip_lose=10, skip_win=1), [], now)[0], [])
        # "melewatkan": SKIP kebanyakan pada kandidat yang untung
        les2, _ = K.update_skip_lessons(self.recs(now, skip_lose=3, skip_win=15, kat="RR_P19"), [], now)
        self.assertEqual({l["arah"] for l in les2}, {"melewatkan"})
        # 31 hari kemudian akurasi ≈ baseline → pensiun
        later = now + 31 * C.DAY_MS
        les3, ch3 = K.update_skip_lessons(self.recs(later, skip_lose=9, skip_win=9, start=1000), les, later)
        self.assertEqual({l["status"] for l in les3}, {"pensiun"})
        self.assertTrue(all("PENSIUN" in c for c in ch3))
        # render: pelajaran hipotesis dan SKIP terpisah
        md = H.render_pelajaran_md(les + [{"id": "L-01", "pola": "kompresi", "ringkasan": "x", "sampel": 10, "hit_rate": 0.7, "baseline": 0.4,
                                            "rezim": "semua", "status": "aktif", "dinilai_ulang": DAY}])
        self.assertIn("| L-01 | kompresi |", md)
        self.assertIn("| tiket | TREN_15M | menyaring |", md)
        self.assertNotIn("LS-0", md.split("## Dari keputusan SKIP")[0])


if __name__ == "__main__":
    unittest.main()
