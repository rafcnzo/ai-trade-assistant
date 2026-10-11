"""Tes dashboard.py (D1–D4): endpoint baca-saja lewat starlette TestClient; tanpa jaringan, tanpa browser."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
import dashboard as D  # noqa: E402
from common import MINUTE_MS, connect  # noqa: E402
from fixtures import BTC, PEM, bars_setup_long, seed_pasar, t  # noqa: E402
from paper_engine import LONG, EngineConfig, OrderRequest, PaperEngine, SqliteMarket  # noqa: E402

END = t("10:00")


class Base(unittest.TestCase):
    def setUp(self):
        from starlette.testclient import TestClient
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        self.clock = [END + 65_000]
        self.data = D.Data(root=self.root, pasar=self.root / "pasar.sqlite", paper=self.root / "paper.sqlite", budget=self.root / "budget.sqlite",
                           kandidat=self.root / "kandidat.sqlite", psikologi=self.root / "psikologi.sqlite", hermes_exec=self.root / "nope.db",
                           clock=lambda: self.clock[0])
        self.client = TestClient(D.make_app(self.data, static_dir=self.root / "static"))

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self):
        pasar = connect(self.root / "pasar.sqlite")
        seed_pasar(pasar, PEM, bars_setup_long(PEM, END), mark=100.03, tick_ts=END + 5_000)
        pasar.close()
        pasar_ro = connect(self.root / "pasar.sqlite", readonly=True)
        eng = PaperEngine(connect(self.root / "paper.sqlite"), SqliteMarket(pasar_ro), clock=lambda: self.clock[0], cfg=EngineConfig(acak_enabled=True))
        return eng, pasar_ro


class TestDashboard(Base):
    def test_d1_empty_everything_is_200(self):
        for path in ("/api/ringkasan", "/api/simbol", "/api/candles?symbol=X&tf=5m", "/api/marker?symbol=X", "/api/riwayat", "/api/ekuitas",
                     "/api/statistik", "/api/psikologi", "/api/kandidat", "/api/teks?jenis=jurnal", "/api/teks?jenis=hipotesis"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
        rk = self.client.get("/api/ringkasan").json()
        self.assertEqual((rk["collector"]["status"], rk["budget"]["tiket"]["status"], rk["pemindai"]["status"], rk["kill_switch"]), ("tidak tersedia",) * 3 + (False,))
        self.assertEqual(self.client.get("/api/psikologi").json()["status"], "tidak tersedia")
        self.assertEqual(self.client.get("/api/candles?symbol=X&tf=7m").json(), [])
        self.assertEqual(self.client.get("/").status_code, 404)                       # tanpa static dir
        self.assertEqual(self.client.get("/static/..%5Cx").status_code, 400)
        self.assertEqual(self.client.get("/static/.env").status_code, 400)

    def test_d2_candles_resample(self):
        eng, pasar_ro = self.seed()
        c5 = self.client.get(f"/api/candles?symbol={PEM}&tf=5m&n=100").json()
        self.assertEqual(len(c5), 72)
        self.assertEqual(c5[-1]["time"], (END - 5 * MINUTE_MS) // 1000)
        self.assertEqual(c5[-1]["tf_ms"], 5 * MINUTE_MS)
        self.assertAlmostEqual(c5[-1]["low"], 100.01, places=6)
        c1 = self.client.get(f"/api/candles?symbol={PEM}&tf=1m&n=10").json()
        self.assertEqual(len(c1), 10)
        self.assertEqual(self.client.get(f"/api/candles?symbol={PEM}&tf=1h").json(), [])      # kline_1h kosong
        s = self.client.get("/api/simbol").json()
        self.assertEqual(s["top"], [PEM])
        rk = self.client.get("/api/ringkasan").json()
        self.assertEqual((rk["collector"]["status"], rk["budget"]["tiket"]["remaining"]), ("OK", 1.0))
        eng.conn.close()
        pasar_ro.close()

    def test_d3_markers_positions_history_equity(self):
        eng, pasar_ro = self.seed()
        r = eng.place_order(OrderRequest("tiket", PEM, LONG, 0.5, 100, price=99.5, tp_price=100.5, plan_id="K1", created_by="hermes"))
        self.assertTrue(r.ok, str(r))
        rk = self.client.get("/api/ringkasan").json()
        self.assertEqual(len(rk["order"]), 2)                                            # tiket + bayangan acak
        self.assertLess(rk["budget"]["tiket"]["remaining"], 0.6)
        mk = self.client.get(f"/api/marker?symbol={PEM}").json()
        self.assertEqual([g["jenis"] for g in mk["garis"]], ["order"])                 # bayangan acak = MARKET, tanpa garis harga
        # isi bayangan acak (market di bar berikutnya) lalu tutup EOD
        from fixtures import FixtureMarket  # noqa: F401
        import sqlite3
        w = connect(self.root / "pasar.sqlite")
        with C.tx(w):
            for i in range(3):
                ot = END + i * MINUTE_MS
                w.execute("INSERT OR REPLACE INTO kline_1m(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,1,1,1,1)", (PEM, ot, 100.1, 100.15, 100.05, 100.1))
                w.execute("INSERT OR REPLACE INTO mark_kline_1m(symbol,open_time,open,high,low,close) VALUES(?,?,?,?,?,?)", (PEM, ot, 100.1, 100.15, 100.05, 100.1))
            ot = C.wib_clock_ms(END, "23:50")
            w.execute("INSERT OR REPLACE INTO kline_1m(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,1,1,1,1)", (PEM, ot, 100.2, 100.25, 100.15, 100.2))
            w.execute("INSERT OR REPLACE INTO mark_kline_1m(symbol,open_time,open,high,low,close) VALUES(?,?,?,?,?,?)", (PEM, ot, 100.2, 100.25, 100.15, 100.2))
        w.close()
        self.clock[0] = C.wib_clock_ms(END, "23:52")
        eng.step()
        mk = self.client.get(f"/api/marker?symbol={PEM}").json()
        jenis = sorted(m["jenis"] for m in mk["marker"])
        self.assertEqual(jenis, ["ENTRY", "EOD", "EXPIRED"])                              # acak terisi+EOD, tiket kedaluwarsa
        self.assertTrue(all(m["account"] == "acak" for m in mk["marker"] if m["jenis"] in ("ENTRY", "EOD")))
        rw = self.client.get("/api/riwayat?akun=acak").json()
        self.assertEqual((len(rw["posisi"]), rw["posisi"][0]["close_reason"]), (1, "EOD"))
        self.assertEqual(self.client.get("/api/riwayat?akun=tiket").json()["order"][0]["status"], "EXPIRED")
        eq = self.client.get("/api/ekuitas").json()
        self.assertEqual((len(eq["acak"]), eq["tiket"]), (1, []))
        st = self.client.get("/api/statistik").json()
        self.assertTrue(st["lulus"]["sampel"].startswith("belum"))
        eng.conn.close()
        pasar_ro.close()

    def test_d4_static_and_teks(self):
        (self.root / "static").mkdir()
        (self.root / "static" / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (self.root / "static" / "app.js").write_text("1", encoding="utf-8")
        self.assertEqual(self.client.get("/").text, "<html>ok</html>")
        self.assertEqual(self.client.get("/static/app.js").text, "1")
        self.assertEqual(self.client.get("/static/none.js").status_code, 404)
        (self.root / "referensi").mkdir()
        (self.root / "referensi" / "playbook.md").write_text("# Playbook\n| P-01 |", encoding="utf-8")
        self.assertIn("P-01", self.client.get("/api/teks?jenis=playbook").json()["isi"])
        self.assertEqual(self.client.get("/api/teks?jenis=jurnal").json()["isi"], "")
        self.assertIn("error", self.client.get("/api/teks?jenis=zzz").json())


if __name__ == "__main__":
    unittest.main()
