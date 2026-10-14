"""Tes pemindai.py (S1–S10): pasar.sqlite sintetis, mesin paper in-memory, tanpa jaringan dan tanpa LLM."""
from __future__ import annotations

import contextlib
import io
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analisis as A  # noqa: E402
import common as C  # noqa: E402
import pemindai as P  # noqa: E402
from common import MINUTE_MS, connect  # noqa: E402
from fixtures import DAY, PEM, PEM2, bars_flat, bars_setup_long, seed_pasar, t  # noqa: E402
from paper_engine import OrderRequest, PaperEngine, SqliteMarket  # noqa: E402

END = t("10:00")            # bar 1m terakhir close 10:00 WIB
TICK = END + 5_000          # collector tick 10:00:05
NOW = END + 65_000          # cron 10:01:05


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.pasar = connect(self.root / "pasar.sqlite")
        self.clock = [NOW]
        self.market = SqliteMarket(self.pasar)
        self.engine = PaperEngine(connect(":memory:"), self.market, clock=lambda: self.clock[0])
        self.kand = connect(self.root / "kandidat.sqlite")
        self.cfg = P.PemindaiConfig()
        self.p = P.Pemindai(self.pasar, self.kand, self.engine, self.cfg, clock=lambda: self.clock[0])

    def tearDown(self):
        self.kand.close()
        self.engine.conn.close()
        self.pasar.close()
        self.tmp.cleanup()

    def seed(self, symbol=PEM, setup=True, mark=100.03, tick=TICK, **kw):
        bars = bars_setup_long(symbol, END) if setup else bars_flat(symbol, END)
        seed_pasar(self.pasar, symbol, bars, mark=mark if setup else 100.30, tick_ts=tick, **kw)

    def fresh(self, now):
        """Pindahkan jam dan buat tick collector segar (data bar tetap berakhir 10:00)."""
        self.clock[0] = now
        with C.tx(self.pasar):
            C.meta_set(self.pasar, "last_tick_ms", now - 5_000)


class TestSetup(Base):
    def test_s1_setup_long_wakes_agent(self):
        self.seed()
        res = self.p.run()
        self.assertTrue(res.wake, res.alasan)
        self.assertEqual(len(res.kandidat), 1)
        k = res.kandidat[0]
        self.assertEqual((k.symbol, k.arah_dugaan, k.plan_id, k.sentuhan), (PEM, "LONG", "K1", 3))
        self.assertGreaterEqual(k.score, 3)
        self.assertIn("WICK", k.flags)
        self.assertIn("VOL", k.flags)
        self.assertIn("DEKAT_LEVEL", k.flags)
        self.assertAlmostEqual(k.level, 100.0, places=6)
        self.assertEqual([d["leverage"] for d in k.lev_layak], [150, 125, 100])
        self.assertGreaterEqual(k.lev_layak[0]["x_atr5m"], 2.0)
        txt = P.format_text(res, self.cfg)
        lines = txt.splitlines()
        self.assertEqual(lines[-1], P.GATE_ON)
        self.assertTrue(any(ln.startswith(f"K1 {PEM} LONG skor {k.score}") for ln in lines), txt)
        self.assertIn('plan_id persis "K1"', txt)
        self.assertTrue(lines[-1].isascii())
        row = self.kand.execute("SELECT wake, n_kandidat, n_symbols, ok FROM pemindai_run").fetchone()
        self.assertEqual(tuple(row), (1, 1, 1, 1))
        kr = self.kand.execute("SELECT id, symbol, score, lev_layak FROM kandidat").fetchone()
        self.assertEqual((kr[0], kr[1], kr[2]), (1, PEM, k.score))
        self.assertEqual(json.loads(kr[3])[0]["leverage"], 150)
        self.assertEqual(self.p.wake_hari_ini(DAY), 1)

    def test_s1b_data_until_excludes_running_bucket(self):
        self.seed()
        # bar 1m tambahan 10:00 (awal bucket 5m yang belum lengkap), tick 10:01:05
        with C.tx(self.pasar):
            self.pasar.execute("INSERT INTO kline_1m(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,?,?,?,?)",
                               (PEM, END, 100.1, 100.9, 99.5, 100.2, 1, 9e9, 1, 0))
            C.meta_set(self.pasar, "last_tick_ms", END + 65_000)
        self.clock[0] = END + 70_000
        bars = A.load_bars(self.market, PEM, 48, self.clock[0])
        until = P.data_until_for(bars, END + 65_000, 5_000)
        self.assertEqual(until, END + MINUTE_MS)
        fit = P.fitur_simbol(bars, 100.03, until, self.cfg)
        self.assertEqual(fit["n_5m"], 72)                       # bucket 10:00 berjalan tidak ikut
        self.assertEqual(fit["jejak"][-1]["jejak"], "VOL")      # VOL dari bucket 09:55, bukan dari bar 9e9
        # tick lebih tua dari bar terakhir → batas mengikuti tick
        self.assertEqual(P.data_until_for(bars, END - 10 * MINUTE_MS, 5_000), C.floor_minute(END - 10 * MINUTE_MS - 5_000))
        self.assertIsNone(P.data_until_for([], TICK, 5_000))

    def test_s2_flat_market_no_candidate(self):
        self.seed(setup=False)
        res = self.p.run()
        self.assertFalse(res.wake)
        self.assertTrue(res.alasan.startswith("tidak ada kandidat (1 simbol"), res.alasan)
        self.assertEqual(res.dipindai[0]["keterangan"], "tidak ada level ≥2 sentuhan")
        txt = P.format_text(res, self.cfg)
        self.assertEqual(txt.splitlines()[-1], P.GATE_OFF)
        self.assertEqual(len(txt.splitlines()), 2)
        self.assertEqual(tuple(self.kand.execute("SELECT wake, n_kandidat FROM pemindai_run").fetchone()), (0, 0))
        self.assertEqual(self.kand.execute("SELECT COUNT(*) FROM kandidat").fetchone()[0], 0)
        verbose = P.format_text(res, self.cfg, verbose=True)
        self.assertIn("| simbol |", verbose)


class TestGates(Base):
    def test_s3_trading_hours(self):
        self.seed()
        self.fresh(t("06:30"))
        self.assertIn("di luar jam", self.p.run().alasan)
        self.fresh(t("22:45"))
        self.assertIn("di luar jam", self.p.run().alasan)
        self.cfg.jam_akhir = "23:00"
        res = self.p.run()
        self.assertTrue(res.wake, res.alasan)

    def test_s4_budget_exhausted(self):
        self.seed()
        self.engine.budget_status = lambda account, day=None: {"remaining": 0.05}
        res = self.p.run()
        self.assertFalse(res.wake)
        self.assertIn("tidak ada persona yang boleh buka", res.alasan)
        self.assertEqual(res.n_symbols, 0)   # tidak memindai sama sekali

    def test_s5_stale_tick(self):
        self.seed()
        self.clock[0] = TICK + 400_000
        res = self.p.run()
        self.assertIn("data basi", res.alasan)
        self.assertFalse(res.wake)
        # tanpa tick sama sekali
        with C.tx(self.pasar):
            self.pasar.execute("DELETE FROM meta WHERE key='last_tick_ms'")
        self.assertIn("collector belum pernah tick", self.p.run(now=NOW + 60_000).alasan)

    def test_s12_hourly_wake_cap(self):
        self.seed()
        with C.tx(self.kand):
            for i in range(3):
                self.kand.execute("INSERT INTO pemindai_run(ts,day_wib,wake,ok) VALUES(?,?,1,1)", (NOW - (i + 1) * 10 * MINUTE_MS, DAY))
        res = self.p.run()
        self.assertFalse(res.wake)
        self.assertIn("cap 3 wake/jam", res.alasan)
        with C.tx(self.kand):
            self.kand.execute("UPDATE pemindai_run SET ts=ts-? WHERE wake=1", (70 * MINUTE_MS,))   # semua lebih dari sejam lalu
        self.fresh(NOW + 5 * MINUTE_MS)
        self.assertTrue(self.p.run().wake)

    def test_s6_daily_wake_cap(self):
        self.seed()
        with C.tx(self.kand):
            for i in range(11):
                self.kand.execute("INSERT INTO pemindai_run(ts,day_wib,wake,ok) VALUES(?,?,1,1)", (t("07:00") + i * 5 * MINUTE_MS, DAY))
        res = self.p.run()
        self.assertTrue(res.wake)
        self.assertEqual(res.wake_hari_ini, 12)
        self.fresh(NOW + 5 * MINUTE_MS)
        res2 = self.p.run()
        self.assertIn("cap 12 wake/hari", res2.alasan)
        self.assertEqual(res2.n_symbols, 0)

    def test_s7_cooldown_and_score_rise(self):
        self.seed()
        self.assertTrue(self.p.run().wake)
        self.fresh(NOW + 5 * MINUTE_MS)
        res = self.p.run()
        self.assertFalse(res.wake)
        self.assertTrue(res.ditahan and res.ditahan[0]["alasan"].startswith("cooldown"), res.ditahan)
        self.assertTrue(res.alasan.startswith("tidak ada kandidat"))
        # skor naik dibanding kandidat sebelumnya → bangun lagi
        with C.tx(self.kand):
            self.kand.execute("UPDATE kandidat SET score=2")
        self.fresh(NOW + 10 * MINUTE_MS)
        self.assertTrue(self.p.run().wake)
        # cooldown kedaluwarsa setelah 30 menit
        self.fresh(NOW + 20 * MINUTE_MS)
        self.assertFalse(self.p.run().wake)
        self.fresh(NOW + 41 * MINUTE_MS)
        self.assertTrue(self.p.run().wake)
        self.assertEqual(self.kand.execute("SELECT COUNT(*) FROM kandidat").fetchone()[0], 3)

    def test_s8_retention_30_days(self):
        with C.tx(self.kand):
            for d in (31, 29):
                ts = NOW - d * C.DAY_MS
                self.kand.execute("INSERT INTO pemindai_run(ts,day_wib,wake,ok) VALUES(?,?,1,1)", (ts, C.day_wib(ts)))
                self.kand.execute("INSERT INTO kandidat(run_ts,day_wib,symbol,score) VALUES(?,?,?,?)", (ts, C.day_wib(ts), PEM, 3))
        self.p.retention(NOW)
        self.assertEqual(self.kand.execute("SELECT COUNT(*) FROM pemindai_run").fetchone()[0], 1)
        self.assertEqual(self.kand.execute("SELECT COUNT(*) FROM kandidat").fetchone()[0], 1)
        self.assertEqual(C.meta_get(self.kand, "last_retention_day"), DAY)

    def test_s9_exposure_holds_symbol_only(self):
        self.seed(PEM)
        self.seed(PEM2, rank=2)
        r = self.engine.place_order(OrderRequest("tiket", PEM, "LONG", 0.5, 100, price=99.5, tp_price=100.5, plan_id="UJI"))
        self.assertTrue(r.ok, str(r))
        res = self.p.run()
        self.assertTrue(res.wake, res.alasan)
        self.assertEqual([k.symbol for k in res.kandidat], [PEM2])
        self.assertEqual(res.ditahan[0], {"symbol": PEM, "alasan": "ada order/posisi", "score": None})
        self.assertLess(next(a["sisa"] for a in res.akun_aktif if a["akun"] == "tiket"), 0.5)   # saldo tiket tersisa setelah reservasi; persona lain masih $1
        self.assertEqual(res.kandidat[0].lev_layak[0]["leverage"], 150)
        self.assertEqual(sorted(self.p.universe()), sorted([PEM, PEM2]))
        # dua order tiket hidup → gate G4
        r2 = self.engine.place_order(OrderRequest("tiket", PEM2, "LONG", 0.2, 100, price=99.5, tp_price=100.5, plan_id="UJI2"))
        self.assertTrue(r2.ok, str(r2))
        self.fresh(NOW + 5 * MINUTE_MS)
        res2 = self.p.run()
        self.assertIn({"akun": "tiket", "alasan": "sudah 2 order hidup"}, res2.akun_ditahan)   # persona lain tetap boleh (arena)
        self.assertFalse(res2.wake)                                                        # kedua simbol sudah terpapar


class TestHangus(Base):
    def test_s11_gate_hangus_beruntun(self):
        self.seed()
        for acc in ("fade", "breakout", "rentang"):       # arena: uji gate P-09 hanya pada persona tiket
            self.engine.set_account_status(acc, "pensiun", "uji")
        def tutup(pid, reason, ts, net=-0.3):   # net kecil agar saldo bergulir tetap ≥ $0,50 (yang diuji di sini adalah G9, bukan saldo)
            with C.tx(self.engine.conn):
                self.engine.conn.execute("INSERT INTO positions(account,symbol,side,qty,entry_price,leverage,status,close_reason,closed_ts,day_wib,opened_ts,net_result) "
                                         "VALUES('tiket',?,'LONG',0.01,100,100,'CLOSED',?,?,?,?,?)", (f"X{pid}USDT", reason, ts, C.day_wib(ts), ts - 60_000, net))
        tutup(1, "HANGUS", t("08:00"))
        tutup(2, "TP", t("08:30"), net=0.9)
        self.assertEqual(self.engine.hangus_beruntun(DAY), 0)
        self.assertTrue(self.p.run().wake)                     # 1 HANGUS lalu TP → masih boleh
        tutup(3, "HANGUS", t("09:00"))
        tutup(4, "FUNDING_LIQ", t("09:30"))
        self.assertEqual(self.engine.hangus_beruntun(DAY), 2)
        self.fresh(NOW + 5 * MINUTE_MS)
        res = self.p.run()
        self.assertFalse(res.wake)
        self.assertIn("HANGUS beruntun", res.alasan)
        self.assertIn("P-09", res.alasan)
        self.assertIn("pensiun", res.alasan)                     # persona lain ditahan karena pensiun
        # hari berikutnya bebas lagi
        self.assertEqual(self.engine.hangus_beruntun(C.day_wib(NOW + C.DAY_MS)), 0)


class TestCli(unittest.TestCase):
    def test_s10_main_once_json_and_cron(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(tmp.name)
        pasar = connect(root / "pasar.sqlite")
        seed_pasar(pasar, PEM, bars_setup_long(PEM, END), mark=100.03, tick_ts=TICK)
        pasar.close()
        kand = root / "kandidat.sqlite"
        with mock.patch.object(C, "PASAR_DB", root / "pasar.sqlite"), mock.patch.object(C, "PAPER_DB", root / "paper.sqlite"), \
                mock.patch.object(C, "DATA_DIR", root), mock.patch.object(C, "LOG_DIR", root / "logs"), mock.patch.object(P, "KANDIDAT_DB", kand):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = P.main(["--once", "--json", "--sekarang", "2026-10-10T10:01:05"])
            lines = out.getvalue().strip().splitlines()
            self.assertEqual((rc, lines[-1]), (0, P.GATE_ON))
            d = json.loads(lines[0])
            self.assertEqual((d["wake"], d["kandidat"][0]["symbol"], d["kandidat"][0]["plan_id"]), (True, PEM, "K?"))
            k = connect(kand)
            self.assertEqual(k.execute("SELECT COUNT(*) FROM pemindai_run").fetchone()[0], 0)   # --once tidak menyimpan
            k.close()
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = P.main(["--cron", "--sekarang", "2026-10-10T10:01:05"])
            lines = out.getvalue().strip().splitlines()
            self.assertEqual((rc, lines[-1]), (0, P.GATE_ON))
            self.assertTrue(lines[0].startswith("PEMINDAI "), lines[0])
            k = connect(kand)
            self.assertEqual(tuple(k.execute("SELECT wake, n_kandidat FROM pemindai_run").fetchone()), (1, 1))
            k.close()
            # di luar jam lewat --jam-akhir (tick masih segar) → gate off, dua baris
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                P.main(["--cron", "--sekarang", "2026-10-10T10:01:05", "--jam-akhir", "10:00"])
            lines = out.getvalue().strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("di luar jam", lines[0])
            self.assertEqual(lines[1], P.GATE_OFF)
        # lepaskan handler log yang menunjuk folder sementara
        lg = logging.getLogger("pemindai")
        for h in list(lg.handlers):
            h.close()
            lg.removeHandler(h)
        lg._crypto_analyst_ready = False  # type: ignore[attr-defined]
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
