"""Tes utilitas common.py dan parser collector.py. Tanpa jaringan."""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from collector import kline_limit, parse_brackets, parse_kline, parse_mark_kline, parse_symbol_info  # noqa: E402

BLOCK_HTML = """<html>
\t<body>
\t\t<br>
\t\tMaaf, konten terlarang ini tidak dapat kami tampilkan.<br>
\t\tBerdasarkan Surat Edaran Kominfo 1598/SE/DJPT.1/KOMINFO/7/2010 kami dilarang untuk menyediakan akses terhadap konten terlarang ini.<br>
"""


class TestBlockDetection(unittest.TestCase):
    def test_block_page_detected(self):
        self.assertTrue(C.looks_blocked(BLOCK_HTML, "text/html"))
        self.assertTrue(C.looks_blocked(BLOCK_HTML, ""))
        self.assertTrue(C.looks_blocked("<html><body>x</body></html>", "text/html; charset=utf-8"))

    def test_json_not_blocked(self):
        self.assertFalse(C.looks_blocked('{"serverTime": 1791692292805}', "application/json"))
        self.assertFalse(C.looks_blocked('[{"symbol":"BTCUSDT"}]', "application/json;charset=UTF-8"))


class TestTime(unittest.TestCase):
    def test_wib_helpers(self):
        ms = C.day_start_wib_ms("2026-10-10") + 10 * C.HOUR_MS + 3 * C.MINUTE_MS + 27_000
        self.assertEqual(C.day_wib(ms), "2026-10-10")
        self.assertEqual(C.month_wib(ms), "2026-10")
        self.assertEqual(C.fmt_wib(ms), "2026-10-10 10:03:27 WIB")
        self.assertEqual(C.ceil_minute(ms) - C.floor_minute(ms), C.MINUTE_MS)
        self.assertEqual(C.ceil_minute(C.floor_minute(ms)), C.floor_minute(ms))
        self.assertEqual(C.wib_clock_ms(ms, "23:50"), C.day_start_wib_ms("2026-10-10") + 23 * C.HOUR_MS + 50 * C.MINUTE_MS)
        self.assertEqual(C.next_day_start_wib_ms(ms), C.day_start_wib_ms("2026-10-11"))
        self.assertEqual(C.next_month_start_wib_ms(ms), C.day_start_wib_ms("2026-11-01"))
        self.assertEqual(C.parse_iso_ms("2026-10-10T10:03"), C.floor_minute(ms))
        self.assertEqual(C.parse_iso_ms("2026-10-10"), C.day_start_wib_ms("2026-10-10"))
        # 08:00 UTC = 15:00 WIB
        self.assertEqual(C.to_wib(C.day_start_wib_ms("2026-10-10") + 15 * C.HOUR_MS).hour, 15)
        self.assertEqual(C.to_utc(C.day_start_wib_ms("2026-10-10") + 15 * C.HOUR_MS).hour, 8)


class TestDecimalAndSymbols(unittest.TestCase):
    def test_round_step(self):
        self.assertEqual(C.round_step("0.00123", "0.001"), Decimal("0.001"))
        self.assertEqual(C.round_step("0.00123", "0.001", "up"), Decimal("0.002"))
        self.assertEqual(C.round_step(82700.07, "0.1"), Decimal("82700.0"))
        self.assertEqual(C.round_step("7", "1"), Decimal("7"))
        self.assertTrue(C.is_multiple("0.003", "0.001"))
        self.assertFalse(C.is_multiple("0.0015", "0.001"))
        self.assertTrue(C.is_multiple(82700.0, "0.1"))
        self.assertEqual(C.fmt_dec("0.00100"), "0.001")

    def test_symbols(self):
        self.assertEqual(C.base_asset("BTCUSDT"), "BTC")
        self.assertEqual(C.base_asset("1000PEPEUSDT"), "PEPE")
        self.assertEqual(C.base_asset("1000000MOGUSDT"), "MOG")
        self.assertEqual(C.tier_for("ETHUSDT", 5), "mayor")
        self.assertEqual(C.tier_for("SOLUSDT", 3), "large")
        self.assertEqual(C.tier_for("METUSDT", 8), "large")
        self.assertEqual(C.tier_for("METUSDT", 15), "small")
        self.assertEqual(C.symbol_slug("BTCUSDT"), "BTCUSDT")
        self.assertEqual(C.symbol_slug("龙虾USDT"), "u-9f99-867e_USDT")
        self.assertEqual(C.symbol_slug("1000PEPEUSDT"), "1000PEPEUSDT")


class TestSqlite(unittest.TestCase):
    def test_tx_nested_and_rollback(self):
        conn = C.connect(":memory:")
        conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        with C.tx(conn):
            C.meta_set(conn, "a", 1)
            with C.tx(conn):
                C.meta_set(conn, "b", 2)
        self.assertEqual((C.meta_get(conn, "a"), C.meta_get(conn, "b")), ("1", "2"))
        with self.assertRaises(RuntimeError):
            with C.tx(conn):
                C.meta_set(conn, "c", 3)
                raise RuntimeError("batal")
        self.assertIsNone(C.meta_get(conn, "c"))
        self.assertFalse(conn.in_transaction)


class TestCollectorParsers(unittest.TestCase):
    def test_parse_symbol_info_and_brackets(self):
        info = {"symbols": [{
            "symbol": "BTCUSDT", "status": "TRADING", "contractType": "PERPETUAL", "baseAsset": "BTC", "quoteAsset": "USDT",
            "onboardDate": 1569398400000, "liquidationFee": "0.012500",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.10", "minPrice": "556.80", "maxPrice": "4529764"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                {"filterType": "MIN_NOTIONAL", "notional": "50"},
                {"filterType": "PERCENT_PRICE", "multiplierUp": "1.0500", "multiplierDown": "0.9500"},
            ],
        }]}
        finfo = [{"symbol": "BTCUSDT", "fundingIntervalHours": 4, "adjustedFundingRateCap": "0.02", "adjustedFundingRateFloor": "-0.02"}]
        p = parse_symbol_info(info, finfo)["BTCUSDT"]
        self.assertEqual((p["tick_size"], p["qty_step"], p["min_qty"], p["min_notional"]), ("0.10", "0.001", "0.001", "50"))
        self.assertEqual((p["pct_up"], p["pct_down"], p["funding_interval_h"]), (1.05, 0.95, 4))
        self.assertAlmostEqual(p["liq_fee"], 0.0125)
        b = parse_brackets([{"symbol": "BTCUSDT", "riskBrackets": [
            {"bracketSeq": 1, "bracketNotionalFloor": 0, "bracketNotionalCap": 300000, "bracketMaintenanceMarginRate": 0.004,
             "cumFastMaintenanceAmount": 0, "minOpenPosLeverage": 1, "maxOpenPosLeverage": 150}]}])
        self.assertEqual(b[0], ("BTCUSDT", 1, 0.0, 300000.0, 150, 1, 0.004, 0.0))

    def test_kline_limit_keeps_weight_small(self):
        m = C.MINUTE_MS
        self.assertEqual(kline_limit(1000 * m, 1001 * m), 4)       # refetch 2 bar → limit kecil (weight 1)
        self.assertEqual(kline_limit(1000 * m, 1000 * m), 3)
        self.assertEqual(kline_limit(0, 47 * 60 * m), 1500)         # backfill 48 jam → halaman penuh
        self.assertEqual(kline_limit(0, 90 * m), 93)
        h = C.HOUR_MS
        self.assertEqual(kline_limit(0, 2880 * h, tf_ms=h), 1500)     # backfill 120 hari bar 1h → halaman penuh
        self.assertEqual(kline_limit(1000 * h, 1001 * h, tf_ms=h), 4)  # tick rutin 1h: 2 bar → weight 1

    def test_parse_klines(self):
        k = [1791602340000, "82537.80", "82548.10", "82537.70", "82548.00", "13.866", 1791602399999, "1144507.16590", 511, "6.1", "503400.1", "0"]
        self.assertEqual(parse_kline("BTCUSDT", k), ("BTCUSDT", 1791602340000, 82537.8, 82548.1, 82537.7, 82548.0, 13.866, 1144507.1659, 511, 503400.1))
        m = [1791692220000, "82845.20000000", "82850.56041304", "82845.10000000", "82850.00000000", "0", 1791692279999, "0", 0, "0", "0", "0"]
        self.assertEqual(parse_mark_kline("BTCUSDT", m), ("BTCUSDT", 1791692220000, 82845.2, 82850.56041304, 82845.1, 82850.0))


if __name__ == "__main__":
    unittest.main()
