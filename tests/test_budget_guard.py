"""Tes penjaga budget API (B1–B3). Tanpa jaringan."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from budget_guard import BudgetExceeded, BudgetGuard  # noqa: E402
from fixtures import DAY, DAY2, Usage, t  # noqa: E402

OPUS, HAIKU = "claude-opus-5-5", "claude-haiku-5-5"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [t("10:00")]
        self.kill = Path(self.tmp.name) / "STOP_AGENT"
        self.g = BudgetGuard(Path(self.tmp.name) / "budget.sqlite", clock=lambda: self.clock[0], kill_file=self.kill)

    def tearDown(self):
        self.g.conn.close()
        self.tmp.cleanup()


class TestArithmetic(Base):
    def test_b1_opus_all_fields(self):
        self.assertAlmostEqual(self.g.estimate(OPUS, 1000, 200), 0.008, places=9)
        self.assertAlmostEqual(self.g.estimate(OPUS, 0, 0, cache_read=10_000), 0.002, places=9)
        self.assertAlmostEqual(self.g.estimate(OPUS, 0, 0, cw5=5_000), 0.025, places=9)
        self.assertAlmostEqual(self.g.estimate(OPUS, 0, 0, cw1h=1_000), 0.008, places=9)
        self.assertAlmostEqual(self.g.estimate(OPUS, 1000, 200, speed="fast"), 0.016, places=9)

    def test_b1_haiku_tier(self):
        self.assertAlmostEqual(self.g.estimate(HAIKU, 10_000, 1_000), (10_000 * 0.10 + 1_000 * 0.50) / 1e6, places=12)
        self.assertAlmostEqual(self.g.estimate(HAIKU, 150_000, 1_000), (150_000 * 0.50 + 1_000 * 2.50) / 1e6, places=12)

    def test_b1_unknown_model_billed_as_opus(self):
        self.assertAlmostEqual(self.g.estimate("claude-unknown-9", 1000, 200), self.g.estimate(OPUS, 1000, 200), places=12)

    def test_b1_record_parses_usage(self):
        cost = self.g.record(OPUS, Usage(1000, 200, cache_read=10_000, cw5=5_000, cw1h=1_000), purpose="uji")
        self.assertAlmostEqual(cost, 0.008 + 0.002 + 0.025 + 0.008, places=9)
        row = self.g.conn.execute("SELECT * FROM api_calls").fetchone()
        self.assertEqual((row["cache_write_5m_tokens"], row["cache_write_1h_tokens"]), (5_000, 1_000))
        cost2 = self.g.record(OPUS, {"input_tokens": 100, "output_tokens": 10, "cache_creation_input_tokens": 400}, purpose="dict")
        self.assertAlmostEqual(cost2, (100 * 4 + 10 * 20 + 400 * 4 * 1.25) / 1e6, places=12)


class TestCaps(Base):
    def test_b2_daily_cap_blocks_until_midnight(self):
        self.g.record(OPUS, Usage(2_000_000, 100_000))   # 8 + 2 = $10 → tepat di cap
        d = self.g.allow(OPUS, 1000, 100)
        self.assertFalse(d.ok)
        self.assertIn("harian", d.reason)
        self.assertEqual(d.blocked_until, C.day_start_wib_ms(DAY2))
        self.clock[0] = t("09:00", C.day_start_wib_ms(DAY2))
        self.assertTrue(self.g.allow(OPUS, 1000, 100).ok)

    def test_b2_monthly_cap(self):
        for _ in range(19):
            self.g.record(OPUS, Usage(2_000_000, 100_000))   # 19 × $10 = $190
            self.clock[0] += C.DAY_MS                        # hari berbeda, bulan sama (Okt)
        d = self.g.allow(OPUS, 1000, 100)
        self.assertFalse(d.ok)
        self.assertIn("bulanan", d.reason)
        self.assertEqual(d.blocked_until, C.next_month_start_wib_ms(self.clock[0]))

    def test_b2_max_single_call_and_kill_switch(self):
        d = self.g.allow(OPUS, 200_000, 20_000)   # 0.8 + 0.4 = $1.2 > $1
        self.assertFalse(d.ok)
        self.assertIn("per panggilan", d.reason)
        self.kill.write_text("stop", encoding="utf-8")
        d = self.g.allow(HAIKU, 10, 10)
        self.assertFalse(d.ok)
        self.assertIn("kill switch", d.reason)
        self.kill.unlink()
        self.assertTrue(self.g.allow(HAIKU, 10, 10).ok)

    def test_b2_call_context_manager(self):
        with self.g.call(HAIKU, "saring", 6000, 300, ref="k1") as c:
            c.usage = Usage(6000, 300)
            c.served_model = HAIKU
        self.assertAlmostEqual(self.g.spent(day=DAY), (6000 * 0.10 + 300 * 0.50) / 1e6, places=12)
        self.g.record(OPUS, Usage(2_000_000, 100_000))
        with self.assertRaises(BudgetExceeded):
            with self.g.call(OPUS, "putus", 1000, 100):
                pass


class TestIdempotencyAndBoundaries(Base):
    def test_b3_request_id_idempotent(self):
        c1 = self.g.record(OPUS, Usage(1000, 200), request_id="req_1")
        c2 = self.g.record(OPUS, Usage(1000, 200), request_id="req_1")
        self.assertGreater(c1, 0)
        self.assertEqual(c2, 0.0)
        self.assertEqual(self.g.conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0], 1)

    def test_b3_wib_day_boundary(self):
        self.clock[0] = t("23:59")
        self.g.record(OPUS, Usage(1000, 200))
        self.clock[0] = t("00:01", C.day_start_wib_ms(DAY2))
        self.g.record(OPUS, Usage(1000, 200))
        self.assertAlmostEqual(self.g.spent(day=DAY), 0.008, places=9)
        self.assertAlmostEqual(self.g.spent(day=DAY2), 0.008, places=9)
        self.assertAlmostEqual(self.g.spent(month=DAY[:7]), 0.016, places=9)

    def test_b3_served_model_billing(self):
        cost = self.g.record(HAIKU, Usage(1000, 200), served_model=OPUS)
        self.assertAlmostEqual(cost, 0.008, places=9)
        row = self.g.conn.execute("SELECT model_requested, model_served FROM api_calls").fetchone()
        self.assertEqual(tuple(row), (HAIKU, OPUS))
        self.assertIn(OPUS, self.g.status(DAY)["by_model"])
        self.assertIn("$", self.g.report(DAY))
        self.assertIn("claude-opus-5-5", self.g.price_report())


if __name__ == "__main__":
    unittest.main()
