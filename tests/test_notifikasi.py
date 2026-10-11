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
from paper_engine import LONG, OrderRequest, PaperEngine  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.cur = self.root / "notif.json"
        self.market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03"))
        self.clock = [t("10:03", sec=27)]
        self.conn = connect(self.root / "paper.sqlite")
        self.eng = PaperEngine(self.conn, self.market, clock=lambda: self.clock[0])

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
