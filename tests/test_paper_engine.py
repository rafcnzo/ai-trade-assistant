"""Tes mesin paper trading (T1–T19). Tanpa jaringan; pasar sintetis dari fixtures.FixtureMarket."""
from __future__ import annotations

import os
import random
import sys
from decimal import Decimal
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from common import D, MINUTE_MS, connect, is_multiple  # noqa: E402
from fixtures import BTC, CN, DAY, DAY2, DAY_MS, NOBR, XYZ, FixtureMarket, t  # noqa: E402
from paper_engine import (  # noqa: E402
    LONG, SHORT, EngineConfig, OrderRequest, PaperEngine, liq_price, limit_fill, pick_bracket, size_for_margin,
)
from fixtures import FILTERS, BRACKETS  # noqa: E402

GRACE = 5_000


class Base(unittest.TestCase):
    def setUp(self):
        self.market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03"))
        self.clock_ms = [t("10:03", sec=27)]
        self.eng = PaperEngine(connect(":memory:"), self.market, clock=lambda: self.clock_ms[0], cfg=EngineConfig(acak_enabled=False))

    # --- helper
    def at(self, ms: int):
        self.clock_ms[0] = ms

    def run_bar(self, open_time: int):
        """Memproses semua bar sampai (termasuk) bar open_time."""
        self.at(open_time + 2 * MINUTE_MS)
        return self.eng.step()

    def tiket_long(self, price=82700.0, qty=0.001, lev=100, tp=None, sl=None, **kw):
        return self.eng.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=qty, leverage=lev, price=price, tp_price=tp, sl_price=sl, **kw))

    def tiket_short(self, price=82900.0, qty=0.001, lev=100, tp=None, sl=None, **kw):
        return self.eng.place_order(OrderRequest(account="tiket", symbol=BTC, side=SHORT, qty=qty, leverage=lev, price=price, tp_price=tp, sl_price=sl, **kw))

    def pos(self, pid=1):
        r = self.eng.conn.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

    def order(self, oid):
        return dict(self.eng.conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone())

    def fills(self, pid=1):
        return [dict(r) for r in self.eng.conn.execute("SELECT * FROM fills WHERE position_id=? ORDER BY id", (pid,))]


class TestFills(Base):
    def test_t1_limit_through(self):
        res = self.tiket_long()
        self.assertTrue(res.ok, res)
        self.assertAlmostEqual(res.margin_usdt, 0.827, places=6)
        self.assertEqual(res.activate_ts, t("10:04"))
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        rep = self.run_bar(t("10:04"))
        self.assertEqual(rep["fills"], 1)
        p = self.pos()
        self.assertEqual(p["status"], "OPEN")
        self.assertEqual(p["entry_price"], 82700)
        f = self.fills()[0]
        self.assertEqual(f["rule"], "THROUGH")
        self.assertEqual(f["is_maker"], 1)
        self.assertAlmostEqual(f["fee_usdt"], 82.7 * 0.0002, places=8)
        self.assertAlmostEqual(p["liq_price"], (82.7 - 0.827) / (0.001 * 0.996), places=4)
        kinds = [r[0] for r in self.eng.conn.execute("SELECT kind FROM ledger ORDER BY id")]
        self.assertEqual(kinds, ["MARGIN_LOCK", "MARGIN_RELEASE", "MARGIN_LOCK", "FEE"])
        self.assertEqual(self.order(res.order_id)["status"], "FILLED")

    def test_t2_touch_does_not_fill(self):
        self.tiket_long()
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82700, 82750)
        rep = self.run_bar(t("10:04"))
        self.assertEqual(rep["fills"], 0)
        self.assertEqual(self.order(1)["status"], "ACTIVE")
        self.assertIsNone(self.pos())

    def test_t3_gap_open(self):
        self.tiket_long()
        self.market.add_bar(BTC, t("10:04"), 82600, 82650, 82550, 82600)
        self.run_bar(t("10:04"))
        p = self.pos()
        self.assertEqual(p["entry_price"], 82600)
        self.assertEqual(self.fills()[0]["rule"], "GAP_OPEN")

    def test_t4_expire_eod_tidak_terisi(self):
        self.tiket_long()
        bs = self.eng.budget_status("tiket", DAY)
        self.assertAlmostEqual(bs["reserved"], 0.827 + 82.7 * 0.0002, places=6)
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82750, 82780)
        self.market.add_bar(BTC, t("23:50"), 82790, 82800, 82750, 82780)
        self.run_bar(t("23:50"))
        self.assertEqual(self.order(1)["status"], "EXPIRED")
        bs = self.eng.budget_status("tiket", DAY)
        self.assertAlmostEqual(bs["reserved"], 0.0)
        self.assertAlmostEqual(bs["remaining"], 1.0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tiket.csv"
            n = self.eng.export_tiket_csv(DAY, path)
            self.assertEqual(n, 1)
            self.assertIn("TIDAK_TERISI", path.read_text(encoding="utf-8"))

    def test_t13_market_order_taker(self):
        res = self.eng.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=0.001, leverage=100, type="MARKET", post_only=False))
        self.assertTrue(res.ok, res)
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        p = self.pos()
        self.assertAlmostEqual(p["entry_price"], 82790 * (1 + 0.0002), places=6)
        f = self.fills()[0]
        self.assertEqual(f["rule"], "MARKET_OPEN")
        self.assertEqual(f["is_maker"], 0)
        self.assertAlmostEqual(f["fee_usdt"], p["notional_entry"] * 0.0005, places=8)

    def test_t16_no_lookahead(self):
        self.tiket_long()  # dibuat 10:03:27 → aktif dari bar 10:04
        self.market.add_bar(BTC, t("10:03"), 82790, 82800, 82600, 82650)   # menembus, tapi bar 10:03
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82750, 82780)   # tidak menembus
        self.run_bar(t("10:04"))
        self.assertIsNone(self.pos())
        self.assertEqual(self.order(1)["status"], "ACTIVE")


class TestLiquidation(Base):
    def open_long(self, **kw):
        self.tiket_long(**kw)
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        self.assertEqual(self.pos()["status"], "OPEN")
        return self.pos()["liq_price"]

    def test_t5_liq_on_mark_not_last(self):
        liq = self.open_long()
        # last tidak menyentuh liq, mark menyentuh → HANGUS
        self.market.add_bar(BTC, t("10:05"), 82700, 82750, 82300, 82400, mark=(82690, 82740, liq - 50, 82350))
        self.run_bar(t("10:05"))
        p = self.pos()
        self.assertEqual(p["close_reason"], "HANGUS")
        self.assertAlmostEqual(p["realized_pnl"], -0.827, places=6)
        self.assertEqual(p["ambiguous"], 0)
        self.assertEqual(self.eng.conn.execute("SELECT COUNT(*) FROM liquidations").fetchone()[0], 1)

    def test_t5b_last_below_liq_but_mark_above_stays_open(self):
        liq = self.open_long()
        self.market.add_bar(BTC, t("10:05"), 82700, 82750, liq - 100, 82400, mark=(82690, 82740, liq + 50, 82350))
        self.run_bar(t("10:05"))
        self.assertEqual(self.pos()["status"], "OPEN")

    def test_t6_tp_and_liq_same_bar(self):
        liq = self.open_long(tp=83500.0)
        self.market.add_bar(BTC, t("10:05"), 82700, 83600, 82100, 83000, mark=(82690, 83590, liq - 10, 83000))
        self.run_bar(t("10:05"))
        p = self.pos()
        self.assertEqual(p["close_reason"], "HANGUS")
        self.assertEqual(p["ambiguous"], 1)
        self.assertEqual(p["alt_outcome"], "TP")
        with C.tx(self.eng.conn):
            rows = self.eng.rollover_day(DAY)
        self.assertEqual(rows[0]["ambiguous_n"], 1)

    def test_t7_entry_and_liq_same_bar(self):
        self.tiket_long()
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82100, 82200)
        rep = self.run_bar(t("10:04"))
        p = self.pos()
        self.assertEqual(rep["fills"], 1)
        self.assertEqual(p["close_reason"], "HANGUS")
        self.assertEqual(p["alt_outcome"], "OPEN")
        self.assertEqual(p["ambiguous"], 1)

    def test_t8_entry_then_tp_next_bar(self):
        self.tiket_long(tp=83000.0)
        self.market.add_bar(BTC, t("10:04"), 82790, 83100, 82650, 83000)   # TP tercapai di bar entry → tidak dihitung
        self.run_bar(t("10:04"))
        self.assertEqual(self.pos()["status"], "OPEN")
        self.market.add_bar(BTC, t("10:05"), 83000, 83200, 82900, 83100)   # high > 83000 → THROUGH
        self.run_bar(t("10:05"))
        p = self.pos()
        self.assertEqual(p["close_reason"], "TP")
        self.assertEqual(p["exit_price"], 83000)
        self.assertAlmostEqual(p["realized_pnl"], 0.3, places=6)
        fees = 82.7 * 0.0002 + 83.0 * 0.0002
        self.assertAlmostEqual(p["fees_total"], fees, places=8)
        self.assertAlmostEqual(p["net_result"], 0.3 - fees, places=8)
        self.assertEqual(self.order(p["tp_order_id"])["status"], "FILLED")

    def test_t14_stop_trigger_and_oco(self):
        self.open_long(tp=83500.0, sl=82400.0)
        p = self.pos()
        self.assertIsNotNone(p["sl_order_id"])
        self.assertEqual(self.order(p["tp_order_id"])["oco_group"], p["id"])
        self.market.add_bar(BTC, t("10:05"), 82700, 82750, 82380, 82450, mark=(82690, 82740, 82350, 82450))
        self.run_bar(t("10:05"))
        p = self.pos()
        self.assertEqual(p["close_reason"], "STOP")
        self.assertAlmostEqual(p["exit_price"], 82400 * (1 - 0.0002), places=6)
        self.assertEqual(self.order(p["sl_order_id"])["status"], "FILLED")
        self.assertEqual(self.order(p["tp_order_id"])["status"], "CANCELED")
        self.assertEqual(self.fills()[-1]["is_maker"], 0)

    def test_t14b_stop_gap(self):
        self.open_long(sl=82400.0)
        self.market.add_bar(BTC, t("10:05"), 82300, 82350, 82250, 82300)
        self.run_bar(t("10:05"))
        p = self.pos()
        self.assertEqual(p["close_reason"], "STOP")
        self.assertEqual(self.fills()[-1]["rule"], "STOP_GAP")
        self.assertAlmostEqual(p["exit_price"], 82300 * (1 - 0.0002), places=6)

    def test_t17_liq_formula(self):
        self.assertAlmostEqual(liq_price(LONG, 0.001, 82900, 82.9 / 150, 0.004, 0), 82678.0, delta=1.0)
        self.assertAlmostEqual(liq_price(LONG, 0.001, 82900, 8.29, 0.004, 0), 74910.0, delta=1.0)
        self.assertAlmostEqual(liq_price(SHORT, 0.001, 82900, 82.9 / 150, 0.004, 0), 83121.0, delta=1.0)
        base = liq_price(LONG, 5, 82900, 2763.3, 0.005, 0)
        with_cum = liq_price(LONG, 5, 82900, 2763.3, 0.005, 300.0)
        self.assertAlmostEqual(base - with_cum, 300.0 / (5 * 0.995), places=6)
        self.assertEqual(pick_bracket(BRACKETS[BTC], 100).bracket, 1)
        self.assertEqual(pick_bracket(BRACKETS[BTC], 400_000).bracket, 2)
        self.assertEqual(size_for_margin(82700, 100, 1.0, FILTERS[BTC]), C.D("0.001"))
        self.assertIsNone(size_for_margin(82700, 10, 1.0, FILTERS[BTC]))

    def test_mark_fallback_to_last(self):
        self.tiket_long()
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700, no_mark=True)
        self.run_bar(t("10:04"))
        self.assertEqual(self.pos()["status"], "OPEN")
        liq = self.pos()["liq_price"]
        self.market.add_bar(BTC, t("10:05"), 82700, 82750, liq - 10, 82300, no_mark=True)
        self.run_bar(t("10:05"))
        self.assertEqual(self.pos()["close_reason"], "HANGUS")
        self.assertEqual(self.eng.conn.execute("SELECT mark_source FROM liquidations").fetchone()[0], "last")


class TestFunding(Base):
    def test_t9_funding_long_pays_short_receives(self):
        self.tiket_long()
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        liq_before = self.pos()["liq_price"]
        self.market.add_funding(BTC, t("15:00") + 2, 0.0001, 82700.0)
        self.market.add_bar(BTC, t("15:00"), 82700, 82750, 82650, 82700)
        self.run_bar(t("15:00"))
        p = self.pos()
        self.assertAlmostEqual(p["funding_total"], -0.001 * 82700 * 0.0001, places=8)
        self.assertAlmostEqual(p["margin_now"], 0.827 - 0.00827, places=8)
        self.assertGreater(p["liq_price"], liq_before)
        fp = self.eng.conn.execute("SELECT * FROM funding_payments").fetchone()
        self.assertAlmostEqual(fp["liq_after"], p["liq_price"], places=8)
        # short menerima: hari berikutnya (budget tiket hari ini sudah terpakai posisi 1)
        d2 = C.day_start_wib_ms(DAY2)
        self.at(t("09:00", d2, sec=30))                       # aktif dari bar 09:01
        r = self.tiket_short(price=82900.0, lev=100)
        self.assertTrue(r.ok, r)
        self.market.add_bar(BTC, t("09:01", d2), 82900, 82950, 82850, 82900)   # open == limit → bukan gap; high > limit → THROUGH
        self.run_bar(t("09:01", d2))
        self.assertEqual(self.pos(2)["status"], "OPEN")
        self.assertEqual(self.pos(2)["side"], SHORT)
        self.market.add_funding(BTC, t("15:00", d2) + 2, 0.0001, 82900.0)
        self.market.add_bar(BTC, t("15:00", d2), 82900, 82950, 82850, 82900)
        self.run_bar(t("15:00", d2))
        self.assertAlmostEqual(self.pos(2)["funding_total"], +0.001 * 82900 * 0.0001, places=8)
        self.assertAlmostEqual(self.pos(1)["funding_total"], -0.001 * 82700 * 0.0001 - 0.001 * 82900 * 0.0001, places=8)

    def test_t9b_funding_liq(self):
        self.tiket_long()
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        self.market.add_funding(BTC, t("15:00") + 2, 0.02, 82700.0)       # 2% × $82.7 = $1.65 > margin
        self.market.add_bar(BTC, t("15:00"), 82700, 82750, 82650, 82700)
        self.run_bar(t("15:00"))
        p = self.pos()
        self.assertEqual(p["close_reason"], "FUNDING_LIQ")
        self.assertEqual(p["status"], "CLOSED")


class TestBudgetAndValidation(Base):
    def test_t10_tiket_budget(self):
        a = self.tiket_long(lev=100)                      # butuh 0.827 + 0.01654
        self.assertTrue(a.ok)
        b = self.tiket_long(lev=150)                      # butuh 0.5513 + 0.01654 → total > 1
        self.assertFalse(b.ok)
        self.assertEqual(b.reject_code, "BUDGET_TIKET")
        self.assertTrue(self.eng.cancel_order(a.order_id))
        c = self.tiket_long(lev=150)
        self.assertTrue(c.ok, c)
        # terisi lalu hangus → tidak ada isi ulang
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        liq = self.pos()["liq_price"]
        self.market.add_bar(BTC, t("10:05"), 82700, 82750, liq - 20, 82300)
        self.run_bar(t("10:05"))
        self.assertEqual(self.pos()["close_reason"], "HANGUS")
        bs = self.eng.budget_status("tiket", DAY)
        self.assertAlmostEqual(bs["used"], 82.7 / 150 + 82.7 * 0.0002, places=6)
        d = self.tiket_long(lev=100)
        self.assertEqual(d.reject_code, "BUDGET_TIKET")
        # hari berikutnya: budget baru
        self.at(t("09:00", C.day_start_wib_ms(DAY2)))
        self.assertAlmostEqual(self.eng.budget_status("tiket")["remaining"], 1.0)
        e = self.tiket_long(lev=100)
        self.assertTrue(e.ok, e)

    def test_t10b_tiket_after_eod_rejected(self):
        self.at(t("23:55"))
        r = self.tiket_long()
        self.assertEqual(r.reject_code, "TIKET_EOD")

    def test_t11_swing_rules(self):
        sw = lambda **kw: self.eng.place_order(OrderRequest(account="swing", symbol=BTC, side=LONG, **kw))  # noqa: E731
        self.assertEqual(sw(qty=0.002, leverage=10, price=82700.0, tp_price=88000.0, sl_price=81000.0).reject_code, "BUDGET_SWING")
        self.assertEqual(sw(qty=0.001, leverage=10, price=82700.0).reject_code, "SWING_NEEDS_SL_TP")
        self.assertEqual(sw(qty=0.001, leverage=100, price=82700.0, tp_price=88000.0, sl_price=82100.0).reject_code, "LIQ_INSIDE_STOP")
        self.assertEqual(sw(qty=0.001, leverage=10, price=82700.0, tp_price=83000.0, sl_price=82000.0).reject_code, "RR_TOO_LOW")
        ok = sw(qty=0.001, leverage=10, price=82700.0, tp_price=88000.0, sl_price=81000.0)
        self.assertTrue(ok.ok, ok)
        ok2 = sw(qty=0.001, leverage=10, price=82600.0, tp_price=88000.0, sl_price=81000.0)
        self.assertTrue(ok2.ok, ok2)
        self.assertEqual(sw(qty=0.001, leverage=10, price=82500.0, tp_price=88000.0, sl_price=81000.0).reject_code, "SWING_MAX_OPEN")
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        p = self.pos()
        self.assertEqual(p["account"], "swing")
        self.assertIsNotNone(p["tp_order_id"])
        self.assertIsNotNone(p["sl_order_id"])
        self.assertEqual(self.order(p["sl_order_id"])["type"], "STOP_MARKET")

    def test_t12_validation_codes(self):
        o = lambda **kw: self.eng.place_order(OrderRequest(**{"account": "tiket", "symbol": BTC, "side": LONG, "qty": 0.001, "leverage": 100, "price": 82700.0, **kw}))  # noqa: E731
        self.assertEqual(o(leverage=200).reject_code, "LEVERAGE_CAP")
        self.assertEqual(o(qty=0.0015).reject_code, "QTY_STEP")
        self.assertEqual(o(price=40000.0).reject_code, "MIN_NOTIONAL")
        self.assertEqual(o(price=82700.05).reject_code, "TICK_SIZE")
        self.assertEqual(o(price=82900.0).reject_code, "LIMIT_CROSSES")
        self.assertEqual(o(symbol="NOPEUSDT").reject_code, "SYMBOL_UNAVAILABLE")
        self.market.set_mark(NOBR, 1.0)
        self.assertEqual(o(symbol=NOBR, qty=10, leverage=5, price=0.9).reject_code, "LEVERAGE_UNKNOWN")
        self.market.set_mark(XYZ, 1.0)
        self.assertEqual(o(symbol=XYZ, qty=5, leverage=5, price=0.9).reject_code, "MIN_QTY")
        self.assertEqual(o(price=70000.0).reject_code, "PRICE_BAND")
        self.assertEqual(o(tp_price=82000.0).reject_code, "BAD_TP")
        self.assertEqual(o(sl_price=83000.0).reject_code, "BAD_SL")
        self.assertEqual(o(account="lain").reject_code, "ACCOUNT")
        n = self.eng.conn.execute("SELECT COUNT(*) FROM orders WHERE status='REJECTED'").fetchone()[0]
        self.assertEqual(n, 12)

    def test_t18_non_latin_symbol(self):
        self.market.set_mark(CN, 2.0, t("10:03"))
        r = self.eng.place_order(OrderRequest(account="tiket", symbol=CN, side=SHORT, qty=4, leverage=10, price=2.1, tp_price=2.0))
        self.assertTrue(r.ok, r)
        self.market.add_bar(CN, t("10:04"), 2.09, 2.12, 2.08, 2.1)
        self.run_bar(t("10:04"))
        p = self.pos()
        self.assertEqual(p["symbol"], CN)
        self.assertEqual(p["status"], "OPEN")
        self.assertEqual(C.symbol_slug(CN), "u-9f99-867e_USDT")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tiket.csv"
            self.eng.export_tiket_csv(DAY, path)
            self.assertIn(CN, path.read_text(encoding="utf-8"))
        self.assertIn(CN, self.eng.report(DAY))


class TestCatchUpAndDeterminism(unittest.TestCase):
    """T15: 30 jam bar lintas tengah malam WIB + funding + EOD, dan replay == live-step."""

    def scenario(self, live: bool):
        market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03"))
        clock = [t("10:03", sec=27)]
        eng = PaperEngine(connect(":memory:"), market, clock=lambda: clock[0], cfg=EngineConfig())
        eng.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=0.001, leverage=100, price=82700.0, tp_price=86000.0, plan_id="A"))
        eng.place_order(OrderRequest(account="swing", symbol=BTC, side=LONG, qty=0.001, leverage=10, price=82600.0, tp_price=88000.0, sl_price=81000.0))
        bars = [
            (t("10:04"), 82790, 82800, 82550, 82600),       # kedua entry terisi
            (t("12:00"), 82600, 82900, 82500, 82800),
            (t("15:00"), 82800, 82850, 82700, 82750),       # funding 08:00 UTC
            (t("23:50"), 82750, 82800, 82700, 82780),       # EOD: tiket ditutup di open
            (t("00:00", C.day_start_wib_ms(DAY2)), 82780, 82900, 82700, 82850),   # rollover hari
            (t("07:00", C.day_start_wib_ms(DAY2)), 82850, 82900, 82800, 82880),
            (t("15:00", C.day_start_wib_ms(DAY2)), 82880, 82950, 82850, 82900),   # funding hari 2
        ]
        market.add_funding(BTC, t("15:00") + 2, 0.0001, 82750.0)
        market.add_funding(BTC, t("15:00", C.day_start_wib_ms(DAY2)) + 2, -0.0002, 82900.0)
        for b in bars:
            market.add_bar(BTC, *b)
            if live:
                clock[0] = b[0] + 2 * MINUTE_MS
                eng.step()
        if not live:
            clock[0] = bars[-1][0] + 2 * MINUTE_MS
            eng.step()
        return eng

    def dump(self, eng):
        out = {}
        for table in ("positions", "orders", "fills", "ledger", "funding_payments", "liquidations", "daily_summary", "cursor"):
            out[table] = [tuple(r) for r in eng.conn.execute(f"SELECT * FROM {table} ORDER BY rowid" if table != "cursor" and table != "daily_summary" else f"SELECT * FROM {table}")]
        return out

    def test_t15_catchup_and_replay_identical(self):
        live = self.scenario(live=True)
        replay = self.scenario(live=False)
        self.assertEqual(self.dump(live), self.dump(replay))
        tiket = dict(live.conn.execute("SELECT * FROM positions WHERE account='tiket'").fetchone())
        self.assertEqual(tiket["close_reason"], "EOD")
        self.assertAlmostEqual(tiket["exit_price"], 82750 * (1 - 0.0002), places=6)
        self.assertEqual(C.day_wib(tiket["closed_ts"]), DAY)
        self.assertEqual(tiket["closed_bar"], t("23:50"))
        self.assertAlmostEqual(tiket["funding_total"], -0.001 * 82750 * 0.0001, places=8)
        swing = dict(live.conn.execute("SELECT * FROM positions WHERE account='swing'").fetchone())
        self.assertEqual(swing["status"], "OPEN")
        self.assertEqual(live.conn.execute("SELECT COUNT(*) FROM funding_payments WHERE position_id=?", (swing["id"],)).fetchone()[0], 2)
        self.assertAlmostEqual(swing["funding_total"], -0.001 * 82750 * 0.0001 + 0.001 * 82900 * 0.0002, places=8)
        ds = {r["account"]: dict(r) for r in live.conn.execute("SELECT * FROM daily_summary WHERE day_wib=?", (DAY,))}
        self.assertEqual(ds["tiket"]["other_close_n"], 1)
        self.assertEqual(ds["swing"]["filled_n"], 1)
        self.assertEqual(live.cursor_for(BTC), t("15:00", C.day_start_wib_ms(DAY2)))


class TestConcurrency(unittest.TestCase):
    def test_t19_two_connections(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "paper.sqlite"
            market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03"))
            clock = [t("10:03", sec=27)]
            a = PaperEngine(connect(path), market, clock=lambda: clock[0])
            b = PaperEngine(connect(path), market, clock=lambda: clock[0])
            self.assertEqual(a.conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            r = b.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=0.001, leverage=100, price=82700.0))
            self.assertTrue(r.ok, r)
            market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
            clock[0] = t("10:06")
            a.step()
            self.assertEqual(b.positions()[0]["status"], "OPEN")
            # order dari B saat A memegang transaksi baca
            cur = a.conn.execute("SELECT COUNT(*) FROM positions")
            r2 = b.place_order(OrderRequest(account="swing", symbol=BTC, side=LONG, qty=0.001, leverage=10, price=82600.0, tp_price=88000.0, sl_price=81000.0))
            cur.fetchall()
            self.assertTrue(r2.ok, r2)
            a.conn.close()
            b.conn.close()


if __name__ == "__main__":
    unittest.main()


class TestAcak(unittest.TestCase):
    """T20–T23: bayangan acak per order tiket (§19.7)."""

    def setUp(self):
        self.market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03"))
        self.clock_ms = [t("10:03", sec=27)]
        self.eng = PaperEngine(connect(":memory:"), self.market, clock=lambda: self.clock_ms[0], cfg=EngineConfig())

    def run_bar(self, ot):
        self.clock_ms[0] = ot + 2 * MINUTE_MS
        return self.eng.step()

    def order(self, **kw):
        return self.eng.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=0.001, leverage=100, price=82700.0, tp_price=83000.0, **kw))

    def row(self, table, rid, eng=None):
        return dict((eng or self.eng).conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone())

    def events(self):
        return [e[0] for e in self.eng.conn.execute("SELECT type FROM events ORDER BY id")]

    def test_t20_shadow_created(self):
        r = self.order()
        self.assertTrue(r.ok, str(r))
        self.assertEqual(r.shadow_order_id, 2)
        s = self.row("orders", 2)
        self.assertEqual((s["account"], s["type"], s["plan_id"], s["qty"], s["leverage"], s["created_by"], s["post_only"]),
                         ("acak", "MARKET", "ACAK:1", 0.001, 100, "engine", 0))
        self.assertAlmostEqual(s["tp_pct"], 300 / 82700, places=9)
        self.assertIsNone(s["sl_pct"])
        self.assertIsNone(s["tp_price"])
        self.assertEqual(s["side"], random.Random("acak-v1:1").choice((LONG, SHORT)))
        self.assertIn("seed acak-v1", s["note"])
        bs = self.eng.budget_status("tiket")
        self.assertAlmostEqual(bs["reserved"], 0.827 + 82.7 * 0.0002, places=6)     # acak tidak ikut dihitung
        ak = self.eng.budget_status("acak")
        self.assertEqual(ak["account"], "acak")
        self.assertAlmostEqual(ak["reserved"], 0.828 + 82.8 * 0.0005, places=6)      # market: ref = mark, fee taker
        self.assertEqual(self.events(), ["ORDER_NEW", "ORDER_NEW", "ACAK_SHADOW"])

    def test_t21_shadow_fill_tp_resolution_and_eod(self):
        self.order()
        side = self.row("orders", 2)["side"]
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82750, 82780)      # limit tiket 82700 tidak tersentuh
        rep = self.run_bar(t("10:04"))
        self.assertEqual(rep["fills"], 1)
        p = self.row("positions", 1)
        slip = self.eng.slip(BTC)
        self.assertEqual(p["account"], "acak")
        self.assertAlmostEqual(p["entry_price"], 82790 * (1 + slip) if side == LONG else 82790 * (1 - slip), places=6)
        pct = D(300) / D(82700)
        exp_tp = C.round_step(D(p["entry_price"]) * ((1 + pct) if side == LONG else (1 - pct)), Decimal("0.1"), "down" if side == LONG else "up")
        self.assertAlmostEqual(p["tp_price"], float(exp_tp), places=6)
        self.assertTrue(is_multiple(D(str(p["tp_price"])), Decimal("0.1")))
        self.assertIsNone(p["sl_price"])
        self.assertEqual(self.eng.conn.execute("SELECT is_maker, rule FROM fills WHERE position_id=1").fetchone()[1], "MARKET_OPEN")
        self.assertEqual(self.row("orders", 1)["status"], "ACTIVE")
        # EOD: order tiket kedaluwarsa, posisi acak ditutup paksa
        self.market.add_bar(BTC, t("23:50"), 82790, 82800, 82750, 82780)
        self.run_bar(t("23:50"))
        self.assertEqual(self.row("orders", 1)["status"], "EXPIRED")
        self.assertEqual(self.row("positions", 1)["close_reason"], "EOD")
        rows = self.eng.rollover_day(DAY)
        self.assertEqual([r["account"] for r in rows], ["tiket", "swing", "acak"])
        self.assertEqual((rows[0]["tidak_terisi_n"], rows[2]["filled_n"], rows[2]["other_close_n"]), (1, 1, 1))
        rep = self.eng.report(DAY)
        self.assertIn("Tiket vs acak", rep)
        self.assertIn("| acak | 1 | 0 | 0 | 1 | 0 |", rep)
        self.assertIn("Acak (bayangan pembanding", rep)

    def test_t22_shadow_skip_never_breaks_order(self):
        self.eng.cfg.acak_budget = 0.01
        r = self.order()
        self.assertTrue(r.ok, str(r))
        self.assertIsNone(r.shadow_order_id)
        s = self.row("orders", 2)
        self.assertEqual((s["account"], s["status"], s["reject_code"]), ("acak", "REJECTED", "BUDGET_ACAK"))
        self.assertIn("ACAK_SKIP", self.events())
        self.eng.cfg.acak_budget = 1.0
        # swing tidak memicu bayangan
        r2 = self.eng.place_order(OrderRequest("swing", BTC, LONG, 0.001, 10, price=82600.0, tp_price=83400.0, sl_price=82400.0))
        self.assertTrue(r2.ok, str(r2))
        self.assertIsNone(r2.shadow_order_id)
        # acak_enabled=False tidak memicu
        self.assertTrue(self.eng.cancel_order(1))
        self.eng.cfg.acak_enabled = False
        r3 = self.order()
        self.assertTrue(r3.ok, str(r3))
        self.assertIsNone(r3.shadow_order_id)
        self.assertEqual(self.eng.conn.execute("SELECT COUNT(*) FROM orders WHERE account='acak'").fetchone()[0], 1)
        # batal: bayangan NEW ikut dibatalkan, reservasi acak dilepas
        self.eng.cfg.acak_enabled = True
        self.assertTrue(self.eng.cancel_order(r3.order_id))
        r4 = self.order()
        sid = r4.shadow_order_id
        self.assertIsNotNone(sid)
        self.assertTrue(self.eng.cancel_order(r4.order_id))
        self.assertEqual(self.row("orders", sid)["status"], "CANCELED")
        self.assertIn("ikut order asli", self.row("orders", sid)["note"])
        self.assertAlmostEqual(self.eng.budget_status("acak")["reserved"], 0.0)
        # pengguna tidak boleh memasang order acak langsung
        r5 = self.eng.place_order(OrderRequest("acak", BTC, LONG, 0.001, 100, price=82700.0))
        self.assertEqual(r5.reject_code, "ACCOUNT")

    def test_t23_deterministic_side_and_eod_code(self):
        other = PaperEngine(connect(":memory:"), self.market, clock=lambda: self.clock_ms[0], cfg=EngineConfig())
        a = self.order()
        b = other.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=0.001, leverage=100, price=82700.0, tp_price=83000.0))
        self.assertEqual(self.row("orders", a.shadow_order_id)["side"], self.row("orders", b.shadow_order_id, other)["side"])
        self.clock_ms[0] = t("23:55")
        r = self.eng.place_order(OrderRequest(account="acak", symbol=BTC, side=LONG, qty=0.001, leverage=100, type="MARKET", post_only=False,
                                              shadow_of=1, created_by="engine"))
        self.assertEqual(r.reject_code, "ACAK_EOD")


class TestBreakevenAutopsi(Base):
    """T24–T25: pengaman breakeven setelah ≥ 80% jalan ke TP (P-18) dan autopsi mekanis."""

    def test_t24_breakeven_after_mfe(self):
        self.tiket_long(tp=83000.0)                                   # entry 82700, TP +300 → 80% = 82940
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)   # terisi
        self.run_bar(t("10:04"))
        self.market.add_bar(BTC, t("10:05"), 82700, 82950, 82690, 82900)   # high 82950 = 83% jalan; SL baru dipasang di bar BERIKUTNYA
        self.run_bar(t("10:05"))
        p = self.pos()
        self.assertEqual((p["status"], p["sl_price"], p["best_mark"]), ("OPEN", None, 82950.0))
        self.market.add_bar(BTC, t("10:06"), 82900, 82910, 82600, 82650)   # SL dipasang 82700 lalu tertembus → STOP, bukan hangus
        self.run_bar(t("10:06"))
        p = self.pos()
        self.assertEqual((p["close_reason"], p["sl_price"]), ("STOP", 82700.0))
        self.assertIn("BREAKEVEN", [e[0] for e in self.eng.conn.execute("SELECT type FROM events WHERE position_id=1")])
        self.assertGreater(p["net_result"], -0.1)                       # rugi hanya fee + slippage, bukan −$0.83
        # tanpa pengaman (cfg 0): tidak ada SL
        eng2 = PaperEngine(connect(":memory:"), self.market, clock=lambda: self.clock_ms[0], cfg=EngineConfig(acak_enabled=False, tiket_breakeven_mfe=0))
        self.at(t("10:03", sec=27))
        eng2.place_order(OrderRequest(account="tiket", symbol=BTC, side=LONG, qty=0.001, leverage=100, price=82700.0, tp_price=83000.0))
        self.at(t("10:07")); eng2.step()
        self.assertIsNone(dict(eng2.conn.execute("SELECT * FROM positions WHERE id=1").fetchone())["sl_price"])

    def test_t25_autopsi(self):
        self.tiket_long(tp=83000.0)
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.run_bar(t("10:04"))
        self.market.add_bar(BTC, t("10:05"), 82700, 82880, 82690, 82850)   # 60% jalan (belum breakeven)
        self.run_bar(t("10:05"))
        self.market.add_bar(BTC, t("10:06"), 82850, 82860, 82190, 82300)   # likuidasi
        self.run_bar(t("10:06"))
        a = self.eng.autopsi(1)
        self.assertEqual((a["hasil"], a["side"], a["n_bar"]), ("HANGUS", "LONG", 3))
        self.assertAlmostEqual(a["mfe"]["persen_jalan_ke_tp"], 60.0, places=1)
        self.assertEqual((a["mfe"]["harga"], a["mfe"]["menit_sejak_buka"]), (82880.0, 0))   # dibuka 10:04:30, MFE bar 10:05
        self.assertGreater(a["mae"]["persen_jalan_ke_liq"], 100)
        self.assertEqual(a["kembali_ke_entry_setelah_mfe"], C.fmt_wib(t("10:06")))
        self.assertTrue(any("level/arah salah" in x or "tidak ada pola" in x or "berbalik" in x for x in a["pelajaran_mekanis"]))
        self.assertIn("OPEN", [k["type"] for k in a["kejadian"]])
        with self.assertRaises(ValueError):
            self.eng.autopsi(99)
