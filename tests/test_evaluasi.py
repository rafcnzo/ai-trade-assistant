"""Tes evaluasi.py (E1–E3): statistik kelulusan §19.7 pada paper.sqlite sintetis. Tanpa jaringan."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
import evaluasi as E  # noqa: E402
from common import connect  # noqa: E402
from fixtures import BTC, DAY, FixtureMarket, t  # noqa: E402
from paper_engine import EngineConfig, PaperEngine  # noqa: E402

NOV = C.day_start_wib_ms("2026-11-10")


def pos(conn, account, net, reason, closed_ts, oid=None, plan=None, amb=0):
    conn.execute(
        "INSERT INTO positions(account,symbol,side,qty,entry_price,leverage,status,close_reason,net_result,closed_ts,day_wib,entry_order_id,plan_id,ambiguous,opened_ts) "
        "VALUES(?,?,?,?,?,?,'CLOSED',?,?,?,?,?,?,?,?)",
        (account, BTC, "LONG", 0.001, 82700, 100, reason, net, closed_ts, C.day_wib(closed_ts), oid, plan, amb, closed_ts - 60_000),
    )


def order(conn, account, status, created_ts, reject=None, by="hermes"):
    conn.execute(
        "INSERT INTO orders(account,symbol,side,type,reduce_only,qty,leverage,status,reject_code,created_by,created_ts,day_wib) VALUES(?,?,?,?,0,?,?,?,?,?,?,?)",
        (account, BTC, "LONG", "LIMIT", 0.001, 100, status, reject, by, created_ts, C.day_wib(created_ts)),
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.conn = connect(self.root / "paper.sqlite")
        PaperEngine(self.conn, FixtureMarket(), clock=lambda: t("10:00"), cfg=EngineConfig(acak_enabled=False))   # skema
        self.now = NOV + 20 * C.HOUR_MS

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()


class TestEvaluasi(Base):
    def test_e1_account_stats_two_months(self):
        with C.tx(self.conn):
            for i in range(24):
                base = t("10:00") if i < 12 else NOV + 10 * C.HOUR_MS
                net, reason = (0.2, "TP") if i % 6 else (-0.8, "HANGUS")
                pos(self.conn, "tiket", net, reason, base + i * C.HOUR_MS)
            order(self.conn, "tiket", "EXPIRED", t("10:00"))
            order(self.conn, "tiket", "EXPIRED", t("11:00"))
        s = E.account_stats(self.conn, "tiket", self.now)
        self.assertEqual((s["n_posisi"], s["tp_n"], s["hangus_n"], s["tidak_terisi_n"]), (24, 20, 4, 2))
        self.assertAlmostEqual(s["expectancy"], (20 * 0.2 - 4 * 0.8) / 24, places=9)
        self.assertAlmostEqual(s["win_rate"], 20 / 24, places=9)
        self.assertAlmostEqual(s["stabilitas"], (18 * 0.2 - 4 * 0.8) / 22, places=9)   # ceil(5% × 24) = 2 trade terbaik dibuang
        self.assertEqual(sorted(s["per_bulan"]), ["2026-10", "2026-11"])
        self.assertEqual((s["bulan_positif"], s["bulan_cukup"]), (2, 2))
        st = E.compute(self.conn, self.now)
        self.assertEqual(st["lulus"]["expectancy_2_bulan"], "lulus")
        self.assertEqual(st["lulus"]["stabilitas"], "lulus")
        self.assertTrue(st["lulus"]["sampel"].startswith("belum (24/200 tiket, 0/30 swing)"))
        json.dumps(st, default=str)

    def test_e2_small_sample_and_compliance(self):
        with C.tx(self.conn):
            for i in range(5):
                pos(self.conn, "tiket", 0.1, "TP", t("10:00") + i * C.HOUR_MS)
            order(self.conn, "tiket", "REJECTED", t("12:00"), reject="BUDGET_TIKET")
            order(self.conn, "tiket", "REJECTED", t("12:05"), reject="BUDGET_TIKET")
            order(self.conn, "tiket", "REJECTED", t("23:52"), reject="TIKET_EOD")
            order(self.conn, "tiket", "EXPIRED", t("22:45"))                 # pelanggaran agent: setelah 22:30
            order(self.conn, "tiket", "FILLED", t("22:10"))
            order(self.conn, "tiket", "FILLED", t("22:40"), by="engine")     # order mesin tidak dihitung
        s = E.account_stats(self.conn, "tiket", self.now)
        self.assertTrue(str(s["expectancy"]).startswith("tidak tersedia (n=5"))
        self.assertTrue(str(s["stabilitas"]).startswith("tidak tersedia"))
        k = E.compliance(self.conn)
        self.assertEqual((k["budget_ditolak_n"], k["eod_ditolak_n"], k["order_lewat_2230_n"]), (2, 1, 1))
        st = E.compute(self.conn, self.now)
        self.assertTrue(st["lulus"]["kepatuhan"].startswith("belum (1 order"))
        self.assertTrue(st["lulus"]["expectancy_2_bulan"].startswith("tidak tersedia"))
        self.assertTrue(str(st["lulus"]["vs_acak"]).startswith("tidak tersedia"))
        md = E.render_markdown(st)
        self.assertIn("tidak tersedia", md)
        self.assertIn("| kepatuhan aturan | belum", md)

    def test_e3_compare_tiket_vs_acak_and_cli(self):
        with C.tx(self.conn):
            for i in range(30):
                pos(self.conn, "tiket", 0.3 + 0.01 * (i % 5), "TP", t("10:00") + i * C.HOUR_MS, oid=100 + i)
                pos(self.conn, "acak", -0.5 + 0.01 * (i % 5), "HANGUS", t("10:00") + i * C.HOUR_MS, plan=f"ACAK:{100 + i}" if i < 12 else None)
        c = E.compare(self.conn)
        self.assertGreater(c["selisih_mean"], 0.7)
        self.assertLess(c["p_permutasi"], 0.05)
        self.assertEqual((c["n_pasangan"], c["tiket_tanpa_pasangan"]), (12, 18))
        self.assertEqual(c["sign_test"]["tiket_lebih_baik"], 12)
        self.assertLess(c["sign_test"]["p"], 0.01)
        st = E.compute(self.conn, self.now)
        self.assertEqual(st["lulus"]["vs_acak"], "lulus")
        self.assertIn("tiket lebih baik 12/12", E.render_markdown(st))
        # distribusi identik → p besar
        self.assertAlmostEqual(E.permutation_test([1.0, 2.0, 3.0] * 5, [1.0, 2.0, 3.0] * 5), 1.0, places=1)
        self.assertAlmostEqual(E.sign_test(6, 12), 1.0, places=6)
        self.assertLess(E.sign_test(12, 12), 0.001)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = E.main(["--json", "--db", str(self.root / "paper.sqlite"), "--sekarang", "2026-11-10T20:00"])
        self.assertEqual(rc, 0)
        d = json.loads(out.getvalue())
        self.assertEqual(d["tiket_vs_acak"]["n_pasangan"], 12)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            E.main(["--db", str(self.root / "paper.sqlite")])
        self.assertIn("# Statistik kelulusan", out.getvalue())


if __name__ == "__main__":
    unittest.main()
