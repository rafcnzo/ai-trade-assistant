"""Tes asisten.py (A1–A8): ide dicatat, dinilai, syarat rapor; tool MCP dan endpoint dashboard memakai data yang sama. Tanpa jaringan."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import asisten as AS  # noqa: E402
import common as C  # noqa: E402
import hipotesis as H  # noqa: E402
import uji_hipotesis as U  # noqa: E402
from common import MINUTE_MS  # noqa: E402
from fixtures import BTC, FixtureMarket, t  # noqa: E402
from test_mcp_server import Base as McpBase  # noqa: E402

T0 = t("10:03", sec=27)


def ide(tp=110.0, sl=95.0, entry=None, sisi="LONG", batas=1, now=T0, iid="Q-0001", harga=100.0):
    return AS.new_ide(iid, now, BTC, sisi, tp, sl, entry, 10, batas, harga, "naik", "datar")


def pasar(fn, n=1500, mulai=T0 - T0 % MINUTE_MS):
    """Bar 1m dari fungsi harga fn(i); wick 0,1 di tiap sisi."""
    m = FixtureMarket()
    for i in range(n):
        p = fn(i)
        m.add_bar(BTC, mulai + i * MINUTE_MS, p, p + 0.1, p - 0.1, p)
    return m


def baris(i, hari, net, saran, rezim="datar", cermin=-0.1):
    return ({"jenis": "ide", "id": f"Q-{i:04d}", "dibuat_ms": T0 + i, "hari": hari, "symbol": BTC, "sisi": "LONG", "eod_ms": T0, "rezim": rezim},
            {"jenis": "saran", "id": f"Q-{i:04d}", "saran": saran, "poin_lanjut": [], "poin_hindari": []},
            {"id": f"Q-{i:04d}", "hari": hari, "symbol": BTC, "sisi": "LONG", "rezim": rezim, "hasil": "TP" if net > 0 else "STOP", "net": net, "cermin_net": cermin})


def susun(jumlah, net_lanjut, net_hindari, rezim=lambda i: "datar", hari_total=120):
    rec, has = [], []
    for i in range(jumlah):
        hari = C.day_wib(T0 + (i * hari_total // jumlah) * C.DAY_MS)
        lanjut = i % 2 == 0
        a, b, c = baris(i, hari, net_lanjut(i) if lanjut else net_hindari(i), "lanjut" if lanjut else "hindari", rezim(i))
        rec += [a, b]
        has.append(c)
    return rec, has


class TestIde(unittest.TestCase):
    def test_a1_validasi_arah_target_stop(self):
        self.assertEqual(ide()["eod_ms"], C.ceil_minute(T0 + C.DAY_MS))
        for kw in ({"tp": 90.0}, {"sl": 105.0}, {"sisi": "SHORT"}, {"entry": 101.0}, {"batas": 8}):
            with self.assertRaises(ValueError):
                ide(**kw)
        self.assertEqual(ide(entry=99.0)["entry"], 99.0)
        self.assertTrue(AS.new_ide("Q", T0, BTC, "LONG", 110.0, 95.0, None, 10, 1, 100.0, "turun", "datar")["melawan_tren"])

    def test_a2_hitung_rencana(self):
        r = AS.hitung_rencana("LONG", 100.0, 110.0, 95.0, 10, [], False)
        self.assertAlmostEqual(r["untung_di_tp"], 10 - 0.05 - 0.022, places=2)
        self.assertGreater(r["rugi_di_sl"], 5.0)
        self.assertLess(r["menang_minimum"], 0.5)
        self.assertFalse(r["likuidasi_sebelum_stop"])
        self.assertTrue(AS.hitung_rencana("LONG", 100.0, 110.0, 80.0, 10, [], False)["likuidasi_sebelum_stop"])

    def test_a3_nilai_target_stop_tidak_terisi_cermin(self):
        slip = 0.0005
        naik = AS.nilai_ide(ide(), pasar(lambda i: 100 + i * 0.05), T0 + 2 * C.DAY_MS, slip)
        self.assertEqual(naik["hasil"], "TP")
        self.assertGreater(naik["net"], 9.0)
        self.assertEqual(naik["cermin_hasil"], "STOP")     # kebalikannya: stop 10 di atas, kena target ide lebih dulu
        self.assertLess(naik["cermin_net"], 0)
        turun = AS.nilai_ide(ide(), pasar(lambda i: 100 - i * 0.05), T0 + 2 * C.DAY_MS, slip)
        self.assertEqual(turun["hasil"], "STOP")
        self.assertLess(turun["net"], -5.0)
        datar = AS.nilai_ide(ide(entry=90.0, sl=85.0), pasar(lambda i: 100.0), T0 + 2 * C.DAY_MS, slip)
        self.assertEqual((datar["hasil"], datar["net"], datar["cermin_net"]), ("TIDAK_TERISI", 0.0, None))

    def test_a4_tanpa_pengaman_breakeven(self):
        # naik 90 % jalan ke target lalu jatuh: rencana pemilik tidak digeser ke breakeven, jadi kena stop penuh
        harga = lambda i: 100 + i * 0.05 if i <= 180 else 109 - (i - 180) * 0.05  # noqa: E731
        r = AS.nilai_ide(ide(), pasar(harga), T0 + 2 * C.DAY_MS, 0.0005)
        self.assertEqual(r["hasil"], "STOP")
        self.assertLess(r["net"], -4.0)

    def test_a5_data_kurang_dicoba_lagi_lalu_ambigu(self):
        m = pasar(lambda i: 100.0, n=100)
        self.assertIsNone(AS.nilai_ide(ide(), m, T0 + C.DAY_MS + C.HOUR_MS, 0.0005))
        self.assertEqual(AS.nilai_ide(ide(), m, T0 + 4 * C.DAY_MS, 0.0005)["hasil"], "ambigu")


class TestRapor(unittest.TestCase):
    def test_a6_kosong_jujur(self):
        r = AS.rapor([], [], T0)
        self.assertEqual((r["tahap"], r["n_lolos"], r["n_ide"]), (0, 0, 0))
        self.assertEqual(r["banding"]["lanjut"]["rata"], None)
        self.assertEqual(AS.render_konsultasi(r), "")
        json.dumps(r)

    def test_a7_syarat_tahap(self):
        rezim = lambda i: "naik" if i % 4 < 2 else "datar"  # noqa: E731
        # banyak dan lama, tapi saran lanjut sama buruknya: berpengalaman, belum terbukti
        rec, has = susun(120, lambda i: -0.5 + (i % 7) * 0.01, lambda i: -0.5 + (i % 7) * 0.01, rezim)
        r = AS.rapor(rec, has, T0)
        self.assertEqual(r["tahap"], 1)
        self.assertEqual({s["kunci"] for s in r["syarat"] if s["lolos"]}, {"pengalaman", "lama", "kondisi"})
        # saran lanjut jelas untung, saran hindari rugi, di kedua paruh: terbukti
        rec, has = susun(120, lambda i: 1.0 + (i % 7) * 0.1, lambda i: -1.0 - (i % 7) * 0.1, rezim)
        r = AS.rapor(rec, has, T0)
        self.assertEqual(r["tahap"], 2, r["syarat"])
        self.assertEqual(r["n_lolos"], 6)
        # hasil bagus tapi hanya sedikit: tetap tahap awal, walau angkanya positif
        rec, has = susun(30, lambda i: 1.0, lambda i: -1.0, rezim, hari_total=20)
        self.assertEqual(AS.rapor(rec, has, T0)["tahap"], 0)
        # untung hanya di paruh awal: gagal tahan di data baru
        rec, has = susun(120, lambda i: 2.0 if i < 60 else -0.2, lambda i: -1.0, rezim)
        s = {x["kunci"]: x["lolos"] for x in AS.rapor(rec, has, T0)["syarat"]}
        self.assertFalse(s["tahan"])
        # satu kondisi pasar saja: belum boleh naik
        rec, has = susun(120, lambda i: 1.0, lambda i: -1.0)
        self.assertEqual(AS.rapor(rec, has, T0)["tahap"], 0)

    def test_a8_mirip_belum_cukup_data(self):
        skip = [{"hasil": "TP", "net": 0.2, "qty": 1.0, "entry": 100.0, "symbol": BTC, "arah": "LONG", "flags": json.dumps(["WICK"])} for _ in range(25)]
        skip += [{"hasil": "HANGUS", "net": -1.0, "qty": 1.0, "entry": 100.0, "symbol": "X", "arah": "LONG", "flags": ["MELAWAN_TREN_15M"]}]
        g = AS.mirip(skip, [], [], BTC, "LONG", False)
        self.assertEqual((g[0]["n"], g[0]["bacaan"]), (25, "cukup data"))
        self.assertAlmostEqual(g[0]["rata"], 0.2)
        self.assertEqual(g[1]["n"], 25)
        self.assertEqual(g[2]["n"], 0)
        self.assertIn("belum cukup", g[2]["bacaan"])
        self.assertEqual(AS.mirip(skip, [], [], BTC, "LONG", True)[0]["n"], 1)


class TestAlur(McpBase):
    def periksa(self, **kw):
        a = {"symbol": "BTC", "sisi": "long", "tp": 83500.0, "sl": 82000.0}
        return self.tools.periksa_ide(**{**a, **kw})

    def test_a9_periksa_tidak_memasang_order(self):
        r = self.periksa()
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["id"], r["symbol"], r["jenis_masuk"]), ("Q-0001", BTC, "harga pasar"))
        self.assertEqual(self.engine.orders(), [])
        self.assertEqual(r["kondisi_pasar"], "tidak tersedia")     # kline_1h fixture hanya 60 jam: tidak diestimasi
        self.assertEqual(self.periksa()["sudah_tercatat"], True)   # pertanyaan yang sama tidak dihitung dua kali
        self.assertEqual(len(H.load_jsonl(self.root / "pasar" / "konsultasi.jsonl")), 1)
        self.js(r)
        self.assertFalse(self.periksa(tp=82000.0, sl=83500.0)["ok"])
        self.assertFalse(self.tools.periksa_ide("TIDAKADA", "LONG", 2.0, 1.0)["ok"])

    def test_a10_saran_dihitung_sekali_dan_tepat_waktu(self):
        i = self.periksa()["id"]
        self.assertEqual(self.tools.catat_saran(i, ["a", "b"], ["c"])["saran"], "lanjut")
        self.assertFalse(self.tools.catat_saran(i, ["a"], [])["ok"])                     # tidak bisa diubah
        j = self.periksa(tp=83600.0)["id"]
        self.assertEqual(self.tools.catat_saran(j, ["a", "b"], ["VETO: likuidasi kena dulu"])["saran"], "hindari")
        k = self.periksa(tp=83700.0)["id"]
        self.clock[0] += 61 * MINUTE_MS
        self.assertFalse(self.tools.catat_saran(k, ["a"], [])["ok"])                     # setelah harga bergerak: ditolak
        self.assertFalse(self.tools.catat_saran("Q-9999", ["a"], [])["ok"])
        self.assertEqual(self.tools.rapor_asisten()["n_ide"], 3)
        self.assertEqual(self.tools.rapor_asisten()["n_tanpa_saran"], 1)

    def test_a11_batas_harian_dan_data_basi(self):
        for n in range(AS.MAKS_IDE_PER_HARI):
            self.assertTrue(self.periksa(tp=83000.0 + n)["ok"])
        self.assertIn("besok", self.periksa(tp=84000.0)["error"])
        self.clock[0] += 5 * MINUTE_MS
        self.assertEqual(self.periksa(tp=84100.0)["status"], "BASI")

    def test_a12_uji_hipotesis_menilai_sekali(self):
        i = self.periksa(batas_hari=1, tp=82900.0, sl=82700.0)["id"]
        self.tools.catat_saran(i, ["a", "b"], ["c"])
        mulai = C.ceil_minute(self.clock[0])
        for n in range(1500):
            p = 82800 + n
            self.market.add_bar(BTC, mulai + n * MINUTE_MS, p, p + 1, p - 1, p)
        now = self.clock[0] + 2 * C.DAY_MS
        s = U.run(self.root, self.market, now)
        self.assertEqual([r["hasil"] for r in s["ide_dinilai"]], ["TP"])
        self.assertIn("Ide Q-0001", s["pesan"])
        self.assertIn("Rapor asisten", s["pesan"])
        self.assertEqual(s["rapor"]["banding"]["lanjut"]["n"], 1)
        self.assertIn("Dari konsultasi pemilik", (self.root / "pasar" / "pelajaran.md").read_text(encoding="utf-8"))
        self.assertEqual(U.run(self.root, self.market, now + C.HOUR_MS)["ide_dinilai"], [])
        self.assertEqual(len(H.load_jsonl(self.root / "pasar" / "konsultasi-hasil.jsonl")), 1)


class TestDashboard(unittest.TestCase):
    def test_a13_endpoint_rapor(self):
        import dashboard as D
        from starlette.testclient import TestClient
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            data = D.Data(root=root, pasar=root / "p.sqlite", paper=root / "x.sqlite", budget=root / "b.sqlite", kandidat=root / "k.sqlite",
                          psikologi=root / "s.sqlite", hermes_exec=root / "e.db", clock=lambda: T0)
            r = TestClient(D.make_app(data, static_dir=root)).get("/api/rapor").json()
            self.assertEqual((r["tahap"], r["n_ide"], r["pengetahuan"]["pelajaran_aktif"]), (0, 0, 0))
            self.assertEqual(len(r["syarat"]), 6)
            self.assertIsNone(r["pengetahuan"]["radar"])


if __name__ == "__main__":
    unittest.main()
