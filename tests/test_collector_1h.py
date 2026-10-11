"""Tes kline_1h di collector (C1–C3): API tiruan tanpa jaringan."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from collector import Collector, CollectorConfig  # noqa: E402
from common import HOUR_MS, connect  # noqa: E402
from fixtures import PEM, t  # noqa: E402


class FakeApi:
    """Mengembalikan bar 1h sintetis untuk rentang yang diminta dan mencatat setiap panggilan."""

    def __init__(self):
        self.calls: list[tuple] = []

    def klines_tf(self, symbol, interval, start_ms, end_ms=None, limit=1500):
        self.calls.append((symbol, interval, start_ms, end_ms, limit))
        assert interval == "1h"
        step = HOUR_MS
        rows = []
        ot = start_ms - start_ms % step
        if ot < start_ms:
            ot += step
        while len(rows) < limit and (end_ms is None or ot <= end_ms):
            px = 100 + (ot // step) % 7
            rows.append([ot, str(px), str(px + 1), str(px - 1), str(px + 0.5), "10", ot + step - 1, "1000", 50, "5", "500", "0"])
            ot += step
        return rows


class TestKline1h(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.conn = connect(Path(self.tmp.name) / "pasar.sqlite")
        self.api = FakeApi()
        self.cfg = CollectorConfig()
        self.c = Collector(self.conn, self.api, self.cfg)
        self.hour0 = t("10:00")   # batas jam (WIB = UTC+7, batas jam selaras UTC)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM kline_1h WHERE symbol=?", (PEM,)).fetchone()[0]

    def test_c1_backfill_120_days_two_requests(self):
        n = self.c.update_klines_1h([PEM], self.hour0 + 61_000)
        self.assertEqual(len(self.api.calls), 2)
        self.assertEqual(self.api.calls[0][4], 1500)
        self.assertLessEqual(self.api.calls[1][4], 1383)
        self.assertEqual(n, 120 * 24 + 1)                  # inklusif: bar tertua .. bar close terakhir
        self.assertEqual(self.count(), 120 * 24 + 1)
        r = self.conn.execute("SELECT MIN(open_time), MAX(open_time) FROM kline_1h").fetchone()
        self.assertEqual(r[1], self.hour0 - HOUR_MS)       # bar 09:00 (close 10:00) adalah yang terakhir
        self.assertEqual(r[0] % HOUR_MS, 0)
        self.assertEqual(C.meta_get(self.conn, "last_1h_hour"), str(self.hour0 // HOUR_MS))

    def test_c2_once_per_hour_with_grace(self):
        self.c.update_klines_1h([PEM], self.hour0 + 61_000)
        self.api.calls.clear()
        # jam yang sama → tidak ada permintaan
        self.assertEqual(self.c.update_klines_1h([PEM], self.hour0 + 30 * 60_000), 0)
        self.assertEqual(self.api.calls, [])
        # jam berikutnya, masih dalam grace → belum
        self.assertEqual(self.c.update_klines_1h([PEM], self.hour0 + HOUR_MS + 30_000), 0)
        self.assertEqual(self.api.calls, [])
        # lewat grace → 1 permintaan kecil (refetch bar terakhir + bar baru)
        n = self.c.update_klines_1h([PEM], self.hour0 + HOUR_MS + 61_000)
        self.assertEqual(len(self.api.calls), 1)
        self.assertLessEqual(self.api.calls[0][4], 4)
        self.assertEqual(n, 2)
        self.assertEqual(self.count(), 120 * 24 + 2)
        # simbol yang sudah punya bar terakhir tidak diminta lagi walau penanda jam dihapus
        with C.tx(self.conn):
            C.meta_set(self.conn, "last_1h_hour", 0)
        self.api.calls.clear()
        self.assertEqual(self.c.update_klines_1h([PEM], self.hour0 + HOUR_MS + 90_000), 0)
        self.assertEqual(self.api.calls, [])

    def test_c2b_backfill_budget_per_tick(self):
        syms = [f"S{i}USDT" for i in range(7)]
        self.c.update_klines_1h(syms, self.hour0 + 61_000)
        self.assertEqual(len({c[0] for c in self.api.calls}), 5)   # maks 5 simbol baru per tick
        self.assertIsNone(C.meta_get(self.conn, "last_1h_hour"))   # belum semua punya cursor → jam belum ditandai
        self.api.calls.clear()
        self.c.update_klines_1h(syms, self.hour0 + 120_000)
        self.assertEqual(sorted({c[0] for c in self.api.calls}), sorted(syms[5:]))
        self.assertEqual(C.meta_get(self.conn, "last_1h_hour"), str(self.hour0 // HOUR_MS))

    def test_c3_retention_180_days(self):
        now = C.now_ms()
        old = now - 181 * C.DAY_MS
        keep = now - 100 * C.DAY_MS
        with C.tx(self.conn):
            for ot in (old, old + HOUR_MS, keep):
                self.conn.execute("INSERT INTO kline_1h(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                  (PEM, ot - ot % HOUR_MS, 1, 1, 1, 1, 0, 0, 0, 0))
        removed = self.c.retention()
        self.assertEqual(removed["kline_1h"], 2)
        self.assertEqual(self.count(), 1)


if __name__ == "__main__":
    unittest.main()
