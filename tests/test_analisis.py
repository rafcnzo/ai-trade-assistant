"""Tes analisis.py (A1–A6): resample, EMA/ATR/RSI Wilder, swing/level, jejak, tabel leverage, top volume."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analisis as A  # noqa: E402
import common as C  # noqa: E402
from common import MINUTE_MS, Bar  # noqa: E402
from fixtures import BRACKETS, BTC, DAY_MS, FILTERS, t  # noqa: E402
from paper_engine import LONG, EngineConfig  # noqa: E402


def bars_from(symbol: str, start: int, rows, step_ms: int = MINUTE_MS) -> list[Bar]:
    out = []
    for i, r in enumerate(rows):
        o, h, l, c = r[:4]
        qv = r[4] if len(r) > 4 else 100.0
        out.append(Bar(symbol, start + i * step_ms, o, h, l, c, 1.0, qv, 10, 50.0))
    return out


class TestResample(unittest.TestCase):
    def test_a1_resample_alignment_and_closed_only(self):
        start = t("10:00")
        rows = [(100 + i, 101 + i, 99 + i, 100.5 + i, 10) for i in range(12)]   # 12 bar 1m = 10:00..10:11
        bars = bars_from(BTC, start, rows)
        rb = A.resample(bars, 5 * MINUTE_MS, now_ms=t("10:12"))
        self.assertEqual([b.open_time for b in rb], [t("10:00"), t("10:05")])   # bucket 10:10 belum close
        self.assertEqual((rb[0].open, rb[0].high, rb[0].low, rb[0].close, rb[0].quote_volume), (100, 105, 99, 104.5, 50))
        rb2 = A.resample(bars, 5 * MINUTE_MS)
        self.assertEqual(len(rb2), 2)
        rb3 = A.resample(bars, 5 * MINUTE_MS, now_ms=t("10:15"))
        self.assertEqual(len(rb3), 3)


class TestIndicators(unittest.TestCase):
    def test_a2_ema_rsi_atr_hand_values(self):
        e = A.ema([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 3)
        self.assertAlmostEqual(e[1], 1.5)
        self.assertAlmostEqual(e[2], 2.25)
        self.assertAlmostEqual(e[-1], 9.001953125)
        self.assertIsNone(A.ema_last([1, 2, 3], 3))
        # RSI: 14 naik +1 lalu 14 turun -1 → RSI Wilder dihitung tangan
        closes = [100 + i for i in range(15)] + [114 - i for i in range(1, 15)]
        r = A.rsi(closes, 14)
        # ag mulai 1, al 0; tiap langkah turun: ag=ag*13/14, al=(al*13+1)/14
        ag, al = 1.0, 0.0
        for _ in range(14):
            ag, al = ag * 13 / 14, (al * 13 + 1) / 14
        self.assertAlmostEqual(r, 100 - 100 / (1 + ag / al), places=9)
        self.assertEqual(A.rsi([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], 14), 100.0)
        self.assertIsNone(A.rsi([1, 2, 3], 14))
        # ATR: bar konstan high-low = 2 tanpa gap → ATR 2
        bars = bars_from(BTC, t("10:00"), [(100, 101, 99, 100)] * 30)
        self.assertAlmostEqual(A.atr(bars, 14), 2.0)
        s = A.atr_series(bars, 14)
        self.assertIsNone(s[13])
        self.assertAlmostEqual(s[14], 2.0)
        # ATR Wilder dengan satu TR besar
        bars2 = bars_from(BTC, t("10:00"), [(100, 101, 99, 100)] * 15 + [(100, 115, 99, 100)])
        self.assertAlmostEqual(A.atr(bars2, 14), (2.0 * 13 + 16.0) / 14)


class TestSwingsLevels(unittest.TestCase):
    def zigzag(self):
        # harga: naik ke 110, turun ke 100, naik ke 110, turun ke 100, naik ke 110, turun 100, lalu datar
        prices = []
        for _ in range(3):
            prices += [102, 105, 108, 110, 108, 105, 102, 100]
        prices += [101, 101, 101, 101]
        rows = [(p, p + 0.5, p - 0.5, p, 10) for p in prices]
        return bars_from(BTC, t("10:00"), rows)

    def test_a3_swings_cluster_nearest(self):
        bars = self.zigzag()
        sw = A.swings(bars, 3, 3)
        highs = [s.price for s in sw if s.kind == "high"]
        lows = [s.price for s in sw if s.kind == "low"]
        self.assertEqual(highs, [110.5, 110.5, 110.5])
        self.assertEqual(lows, [99.5, 99.5, 99.5])
        levels = A.cluster_levels(sw, width=0.5)
        self.assertEqual([(round(lv.price, 1), lv.touches) for lv in levels], [(99.5, 3), (110.5, 3)])
        above, below = A.nearest(levels, 101.0)
        self.assertEqual((above[0].price, below[0].price), (110.5, 99.5))
        self.assertIn(A.tren(bars[-60:] if len(bars) >= 60 else bars, 10), ("sideways", "tidak tersedia", "naik", "turun"))


class TestJejak(unittest.TestCase):
    def test_a4_jejak_wick_vol_breakout(self):
        base = [(100, 100.6, 99.4, 100, 100)] * 30
        bars = bars_from(BTC, t("10:00"), base)
        atr_v = A.atr(bars)
        self.assertAlmostEqual(atr_v, 1.2)
        levels = [A.Level(99.0, 3, t("09:00"), "l")]
        # wick bawah panjang menyentuh level 99.0
        bars_w = bars + bars_from(BTC, t("10:30"), [(100, 100.2, 98.9, 99.9, 100)])
        j = A.jejak(bars_w, levels, atr_v)
        self.assertTrue(any(x["jejak"] == "WICK" and x["arah"] == "bawah" for x in j), j)
        # volume spike di bar terakhir
        bars_v = bars + bars_from(BTC, t("10:30"), [(100, 100.3, 99.7, 100.2, 500)])
        j = A.jejak(bars_v, [], atr_v)
        self.assertTrue(any(x["jejak"] == "VOL" and x["rasio"] >= 2 for x in j), j)
        # breakout gagal: close di atas 101 lalu kembali ke bawah dalam 2 bar
        lv = [A.Level(101.0, 2, t("09:00"), "h")]
        bars_b = bars + bars_from(BTC, t("10:30"), [(100, 101.8, 99.9, 101.5, 100), (101.5, 101.9, 100.2, 100.4, 100)])
        j = A.jejak(bars_b, lv, atr_v)
        self.assertTrue(any(x["jejak"] == "BREAKOUT_GAGAL" and x["arah"] == "atas" for x in j), j)
        # impuls: 4 candle naik body 1.0 > 0.7×ATR
        bars_i = bars + bars_from(BTC, t("10:30"), [(100 + i, 101.2 + i, 99.9 + i, 101 + i, 100) for i in range(4)])
        j = A.jejak(bars_i, [], atr_v)
        self.assertTrue(any(x["jejak"] == "IMPULS" for x in j), j)
        # kompresi: 10 bar terakhir range kecil
        bars_k = bars + bars_from(BTC, t("10:30"), [(100, 100.1, 99.9, 100, 100)] * 10)
        atr_k = A.atr(bars_k)
        j = A.jejak(bars_k, [], atr_k)
        self.assertTrue(any(x["jejak"] == "KOMPRESI" for x in j), j)


class TestTabelLeverage(unittest.TestCase):
    def test_a5_tabel_leverage_btc(self):
        atr_map = {"1m": 47.0, "5m": 98.0, "15m": 236.0, "1h": 399.0}
        tab = A.tabel_leverage(LONG, 82900.0, FILTERS[BTC], BRACKETS[BTC], atr_map, 1.0, EngineConfig())
        rows = {r["leverage"]: r for r in tab["baris"]}
        self.assertEqual(tab["leverage_maks"], 150)
        self.assertAlmostEqual(rows[150]["jarak_liq_pct"], 0.2678, places=3)   # 1 − (1−1/150)/(1−0,004)
        self.assertAlmostEqual(rows[150]["fee_pct_tiket"], 6.0, places=6)
        self.assertAlmostEqual(rows[100]["jarak_liq_pct"], 0.6024, places=3)
        self.assertIn("tidak bisa", rows[75]["keterangan"])
        self.assertEqual(rows[150]["qty"], "0.001")
        t1 = [x for x in rows[150]["target"] if x["pct"] == 1.0][0]
        # untung bersih = 82.9×1% − 2×0.0002×82.9 = 0.829 − 0.03316
        self.assertAlmostEqual(t1["untung_bersih"], 0.829 - 0.03316, places=4)
        self.assertAlmostEqual(rows[150]["x_atr"]["5m"], round(abs(82900 - rows[150]["liq"]) / 98.0, 2), places=2)


class TestTopVolume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.conn = C.connect(Path(self.tmp.name) / "pasar.sqlite")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_a6_top_volume_flags(self):
        conn = self.conn
        if True:
            C.init_schema(conn, C.SCRIPTS_DIR / "schema_pasar.sql", "1")
            now = t("12:00")
            ts = now - 2 * MINUTE_MS
            with C.tx(conn):
                conn.executemany("INSERT INTO ticker_24h(ts,symbol,rank,last,pct_24h,quote_volume) VALUES(?,?,?,?,?,?)", [
                    (ts, "BTCUSDT", 1, 82900.0, -1.1, 1.2e10), (ts, "METUSDT", 2, 1.5, 70.4, 5.7e8), (ts, "NEWUSDT", 3, 0.5, 3.0, 2e8),
                    (ts - 10 * MINUTE_MS, "OLDUSDT", 1, 1.0, 0.0, 1e9),
                ])
                conn.executemany("INSERT INTO symbol_info(symbol,status,contract_type,quote_asset,onboard_date) VALUES(?,?,?,?,?)", [
                    ("BTCUSDT", "TRADING", "PERPETUAL", "USDT", now - 2000 * C.DAY_MS), ("METUSDT", "TRADING", "PERPETUAL", "USDT", now - 362 * C.DAY_MS),
                    ("NEWUSDT", "TRADING", "PERPETUAL", "USDT", now - 5 * C.DAY_MS),
                ])
                conn.executemany("INSERT INTO leverage_bracket(symbol,bracket,notional_floor,notional_cap,max_leverage,min_leverage,mmr,cum,updated_ts) VALUES(?,?,?,?,?,?,?,?,?)", [
                    ("BTCUSDT", 1, 0, 300000, 150, 1, 0.004, 0, now), ("METUSDT", 1, 0, 5000, 50, 1, 0.015, 0, now),
                ])
                conn.executemany("INSERT INTO mark_snapshot(symbol,ts,mark,index_price,last_funding_rate,next_funding_time) VALUES(?,?,?,?,?,?)", [
                    ("BTCUSDT", ts, 82900.0, 82890.0, 0.00001, 0), ("METUSDT", ts, 1.5, 1.49, 0.0009, 0),
                ])
            out = A.top_volume(conn, 20, now)
            rows = {r["symbol"]: r for r in out["baris"]}
            self.assertEqual(out["umur_menit"], 2)
            self.assertEqual(set(rows), {"BTCUSDT", "METUSDT", "NEWUSDT"})
            self.assertEqual(rows["BTCUSDT"]["flag"], [])
            self.assertIn("SUDAH_LARI", rows["METUSDT"]["flag"])
            self.assertIn("FUNDING_EKSTREM", rows["METUSDT"]["flag"])
            self.assertIn("BARU", rows["NEWUSDT"]["flag"])
            self.assertIn("LEVERAGE_TIDAK_TERSEDIA", rows["NEWUSDT"]["flag"])
            self.assertEqual(rows["BTCUSDT"]["leverage_maks"], 150)
            self.assertEqual(rows["BTCUSDT"]["mcap"], "tidak tersedia")


if __name__ == "__main__":
    unittest.main()
