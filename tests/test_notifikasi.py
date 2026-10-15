"""Tes notifikasi.py (N1–N3): kejadian mesin paper → pesan Telegram, kursor, CLI. Tanpa jaringan, tanpa Hermes."""
from __future__ import annotations

import contextlib
import io
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
import notifikasi as N  # noqa: E402
from common import MINUTE_MS, connect  # noqa: E402
from fixtures import BTC, FixtureMarket, t  # noqa: E402
from paper_engine import LONG, EngineConfig, OrderRequest, PaperEngine  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.cur = self.root / "notif.json"
        self.market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03"))
        self.clock = [t("10:03", sec=27)]
        self.conn = connect(self.root / "paper.sqlite")
        self.eng = PaperEngine(self.conn, self.market, clock=lambda: self.clock[0], cfg=EngineConfig(acak_enabled=False))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def run_bar(self, ot):
        self.clock[0] = ot + 2 * MINUTE_MS
        return self.eng.step()

    def order(self, price=82700.0, tp=None, sl=None, **kw):
        r = self.eng.place_order(OrderRequest("tiket", BTC, LONG, 0.001, 100, price=price, tp_price=tp, sl_price=sl, **kw))
        self.assertTrue(r.ok, str(r))
        return r

    def notif(self, **kw):
        return N.run(self.conn, self.cur, now=self.clock[0], **kw)


class TestNotifikasi(Base):
    def test_n1_init_fill_tp(self):
        self.assertEqual(self.notif(), "")                      # kali pertama: kursor diset, tidak mengirim
        self.assertEqual(N.read_cursor(self.cur), 0)
        self.order(tp=83000.0, plan_id="K7", created_by="hermes")
        msg = self.notif()
        self.assertIn("📣 Paper trading — 1 kejadian baru", msg)
        self.assertIn("🆕 Order #1 tiket BTCUSDT LONG LIMIT 0.001 @ 82700 100x · TP 83000 · SL - · K7 · oleh hermes", msg)
        self.assertTrue(msg.splitlines()[1].startswith("10:03 "), msg)
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        msg = self.notif()
        self.assertIn("✅ TERISI posisi #1 tiket BTCUSDT LONG 0.001 @ 82700 (THROUGH) 100x · margin $0.8270 · liq 82201.8 · TP 83000 · SL - · K7", msg)
        self.market.add_bar(BTC, t("10:05"), 82700, 83100, 82690, 83050)
        self.run_bar(t("10:05"))
        msg = self.notif()
        self.assertIn("🎯 TP posisi #1 tiket BTCUSDT LONG keluar 83000 · net +$0.2669 (pnl +$0.3000, fee $0.0331, funding +$0.0000)", msg)
        self.assertEqual(self.notif(), "")                      # tidak ada yang baru → stdout kosong → Hermes diam
        self.assertEqual(N.read_cursor(self.cur), 3)

    def test_n5_rencana_swing(self):
        from paper_engine import PlanRequest
        from fixtures import PEM
        self.notif()
        self.market.set_mark(PEM, 100.0, t("10:03"))
        r = self.eng.place_plan(PlanRequest(symbol=PEM, side="LONG", leverage=10, legs=[{"harga": 99.5, "persen": 50}, {"harga": 99.0, "persen": 50}],
                                            tps=[{"harga": 104.0, "persen": 50}, {"harga": 106.0, "persen": 25}], sl_price=97.5, trail_dist=0.6, margin=10.0, created_by="hermes"))
        self.assertTrue(r.ok, r)
        msg = self.notif()
        self.assertIn("leg 50% rencana #1", msg)
        self.assertIn("📐 Rencana swing bertahap (order #1): swing PEMUSDT LONG 10x tangga: 2 leg", msg)
        self.market.add_bar(PEM, t("10:04"), 100.0, 100.2, 98.9, 99.1)
        self.run_bar(t("10:04"))
        msg = self.notif()
        self.assertIn("➕ TAMBAH posisi #1: PEMUSDT LONG leg 2", msg)
        self.market.add_bar(PEM, t("10:05"), 99.1, 104.1, 99.0, 103.5)
        self.run_bar(t("10:05"))
        msg = self.notif()
        self.assertIn("🎯 TP SEBAGIAN posisi #1 swing: PEMUSDT LONG TP1 50%", msg)
        self.assertIn("🛡️ Pengaman posisi #1 PEMUSDT LONG: PEMUSDT LONG TP1 terisi; SL sisa dipindah ke harga masuk rata", msg)
        self.market.add_bar(PEM, t("10:06"), 103.5, 106.1, 103.4, 105.8)
        self.run_bar(t("10:06"))
        self.assertIn("🪜 Trailing aktif posisi #1", self.notif())
        self.market.add_bar(PEM, t("10:07"), 105.8, 106.5, 105.8, 106.2)
        self.run_bar(t("10:07"))
        self.assertEqual(self.notif(), "")                                       # TRAIL_GESER dilewati → diam
        self.market.add_bar(PEM, t("10:08"), 106.2, 106.3, 105.0, 105.1)
        self.run_bar(t("10:08"))
        msg = self.notif()
        self.assertIn("🏁 TRAILING STOP posisi #1 swing PEMUSDT LONG keluar", msg)

    def test_n2_cancel_and_expire(self):
        self.notif()
        self.order()
        self.eng.cancel_order(1, who="hermes")
        msg = self.notif()
        self.assertIn("2 kejadian baru", msg)
        self.assertIn("❌ Order #1 tiket BTCUSDT LONG @ 82700 dibatalkan (oleh hermes)", msg)
        self.order()                                            # #2, budget sudah dilepas
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82750, 82780)
        self.market.add_bar(BTC, t("23:50"), 82790, 82800, 82750, 82780)
        self.run_bar(t("23:50"))
        msg = self.notif()
        self.assertIn("⌛ Order #2 tiket BTCUSDT LONG @ 82700 kedaluwarsa — tidak terisi", msg)

    def test_n3_liquidation_limit_and_cli(self):
        self.notif()
        self.order()
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        self.market.add_bar(BTC, t("10:05"), 82700, 82710, 82190, 82300)
        self.run_bar(t("10:05"))
        net = self.conn.execute("SELECT net_result, close_reason FROM positions WHERE id=1").fetchone()
        self.assertEqual(net[1], "HANGUS")
        msg = self.notif(cfg=N.NotifConfig(max_events=2))
        self.assertIn("2 kejadian baru (+1 lebih lama tidak ditampilkan)", msg)
        self.assertNotIn("🆕", msg)
        self.assertIn(f"💀 LIKUIDASI posisi #1 tiket BTCUSDT LONG liq 82201.8 · rugi {N.fmt_usd(net[0], True)} (margin + fee hangus)", msg)
        self.assertEqual(N.read_cursor(self.cur), 3)
        # CLI: --uji tidak menyentuh kursor; --kursor + --cron mengirim ulang; --reset ke akhir
        with mock.patch.object(C, "PAPER_DB", self.root / "paper.sqlite"), mock.patch.object(C, "DATA_DIR", self.root), \
                mock.patch.object(C, "LOG_DIR", self.root / "logs"), mock.patch.object(N, "NOTIF_PATH", self.cur):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(N.main(["--uji", "2"]), 0)
            lines = out.getvalue().strip().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertIn("TERISI", lines[1])
            self.assertEqual(N.read_cursor(self.cur), 3)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                N.main(["--kursor", "1"])
            self.assertEqual(N.read_cursor(self.cur), 1)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                N.main(["--cron"])
            self.assertIn("2 kejadian baru", out.getvalue())
            self.assertEqual(N.read_cursor(self.cur), 3)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                N.main(["--cron"])
            self.assertEqual(out.getvalue(), "")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                N.main(["--kursor", "0"])
                N.main(["--reset"])
            self.assertEqual(N.read_cursor(self.cur), 3)
        lg = logging.getLogger("notifikasi")
        for h in list(lg.handlers):
            h.close()
            lg.removeHandler(h)
        lg._crypto_analyst_ready = False  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()


class TestAcakNotif(Base):
    def test_n4_acak_events_skipped(self):
        self.eng.cfg.acak_enabled = True
        self.notif()
        self.order(tp=83000.0)
        msg = self.notif()
        self.assertIn("2 kejadian baru", msg)                     # ORDER_NEW tiket + 🎲; ORDER_NEW acak dilewati
        self.assertNotIn("acak BTCUSDT", msg)
        self.assertIn("🎲 Bayangan acak: order #2", msg)
        self.assertEqual(N.read_cursor(self.cur), 3)             # kursor tetap melewati kejadian acak
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82750, 82780)
        self.run_bar(t("10:04"))                                  # hanya bayangan yang terisi
        self.assertEqual(self.notif(), "")
        self.assertEqual(N.read_cursor(self.cur), 4)
