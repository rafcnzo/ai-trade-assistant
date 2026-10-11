"""Tes psikologi.py (PS1–PS6): panel psikologi dengan sumber palsu, tanpa jaringan."""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
import psikologi as P  # noqa: E402
from common import HOUR_MS, BlockedError, HttpError, connect  # noqa: E402
from fixtures import t  # noqa: E402

NOW = t("10:07")


class FakeSumber:
    def __init__(self, **over):
        self.v = {
            "fng": 61.0, "ls_akun": 1.4474, "ls_top": 1.5225, "taker": [0.93, 0.95, 0.92, 0.94], "spot": 82976.06,
            "cb_btc": 82894.37, "cb_usdt": 0.99898, "btcidr": 1475910000.0, "usdtidr": 17787.0,
            "stable": (3.10e11, 3.05e11), "oi": [(NOW - (24 - i) * HOUR_MS, 7.5e9 * (1 + 0.001 * i)) for i in range(25)],
            "liq": (30, 10, 100),
        }
        self.v.update(over)
        self.calls = []

    def _g(self, k):
        self.calls.append(k)
        v = self.v[k]
        if isinstance(v, Exception):
            raise v
        return v

    def fng(self): return self._g("fng")
    def oi_hist(self, s): return self._g("oi")
    def ls_akun(self, s): return self._g("ls_akun")
    def ls_top(self, s): return self._g("ls_top")
    def taker(self, s): return self._g("taker")
    def liq_okx(self, uly, since): return self._g("liq")
    def spot_binance(self, s="BTCUSDT"): return self._g("spot")
    def coinbase(self, p): return self._g("cb_btc" if p == "BTC-USD" else "cb_usdt")
    def indodax(self, p): return self._g("btcidr" if p == "btcidr" else "usdtidr")
    def stablecoin(self): return self._g("stable")


def seed_pasar(conn, symbol, funding, closes):
    C.init_schema(conn, C.SCRIPTS_DIR / "schema_pasar.sql", "2")
    with C.tx(conn):
        conn.execute("INSERT OR REPLACE INTO mark_snapshot(symbol,ts,mark,index_price,last_funding_rate,next_funding_time) VALUES(?,?,?,?,?,?)",
                     (symbol, NOW, 82800, 82800, funding, NOW + HOUR_MS))
        for i, c in enumerate(closes):
            ot = NOW - NOW % HOUR_MS - (len(closes) - 1 - i) * HOUR_MS
            conn.execute("INSERT OR REPLACE INTO kline_1h(symbol,open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote) VALUES(?,?,?,?,?,?,0,0,0,0)",
                         (symbol, ot, c, c, c, c))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.conn = connect(self.root / "psikologi.sqlite")
        self.pasar = connect(self.root / "pasar.sqlite")
        seed_pasar(self.pasar, "BTCUSDT", 0.0004, [80000 + 10 * i for i in range(25)])      # harga +0.3%
        seed_pasar(self.pasar, "ETHUSDT", -0.0002, [2500] * 25)
        self.cfg = P.PsikologiConfig()

    def tearDown(self):
        self.conn.close()
        self.pasar.close()
        self.tmp.cleanup()

    def by(self, rows, sym, ind):
        return next(r for r in rows if r["symbol"] == sym and r["indikator"] == ind)


class TestPanel(Base):
    def test_ps1_collect_zones_save_read(self):
        res = P.run(self.conn, self.pasar, FakeSumber(), NOW, self.cfg)
        self.assertEqual((res["ok"], res["n"], res["n_gagal"], res["mode"]), (1, 2 * 8 + 4, 0, "awal"))
        p = P.panel_untuk(self.conn, "BTCUSDT", NOW + 60_000, self.cfg)
        rows = p["indikator"]
        self.assertEqual((p["status"], p["umur_s"], len(rows)), ("OK", 60, 12))
        self.assertEqual(self.by(rows, "*", "fng")["zona"], P.NETRAL)
        self.assertEqual(self.by(rows, "BTCUSDT", "funding")["zona"], P.SERAKAH)       # 0.0004 ≥ 0.0003
        self.assertEqual(self.by(rows, "BTCUSDT", "taker")["zona"], P.NETRAL)
        self.assertAlmostEqual(self.by(rows, "BTCUSDT", "taker")["nilai"], 0.935, places=6)
        self.assertAlmostEqual(self.by(rows, "BTCUSDT", "oi_24h")["nilai"], 0.024, places=6)
        self.assertAlmostEqual(self.by(rows, "BTCUSDT", "harga_24h")["nilai"], 240 / 80000, places=9)
        self.assertEqual(self.by(rows, "BTCUSDT", "liq_long_24h")["zona"], P.TAKUT)       # 30 long vs 10 short
        self.assertIn("sampel 100", self.by(rows, "BTCUSDT", "liq_long_24h")["catatan"])
        self.assertAlmostEqual(self.by(rows, "*", "premium_coinbase")["nilai"], 82894.37 / (82976.06 * 0.99898) - 1, places=9)
        self.assertAlmostEqual(self.by(rows, "*", "premium_idr")["nilai"], 1475910000 / (17787 * 82976.06) - 1, places=9)
        self.assertAlmostEqual(self.by(rows, "*", "stablecoin_7d")["nilai"], 3.10 / 3.05 - 1, places=6)
        self.assertEqual(self.by(rows, "*", "stablecoin_7d")["zona"], P.SERAKAH)
        eth = P.panel_untuk(self.conn, "ETHUSDT", NOW, self.cfg)
        self.assertEqual(self.by(eth["indikator"], "ETHUSDT", "funding")["zona"], P.TAKUT)
        self.assertEqual(eth["divergensi"], [])
        txt = P.ringkas_teks(p)
        self.assertIn("tidak ada skor gabungan", txt)
        self.assertIn("| Fear & Greed | 61 | netral |", txt)
        self.assertEqual(tuple(self.conn.execute("SELECT n_ok, n_gagal FROM panel_run").fetchone()), (20, 0))

    def test_ps2_source_failures_do_not_break_run(self):
        fs = FakeSumber(fng=BlockedError("diblokir"), cb_btc=HttpError(503, "down", "u"), oi=[(NOW, 1.0)] * 3)
        res = P.run(self.conn, self.pasar, fs, NOW, self.cfg)
        self.assertEqual(res["ok"], 1)
        p = P.panel_untuk(self.conn, "BTCUSDT", NOW, self.cfg)
        fng = self.by(p["indikator"], "*", "fng")
        self.assertEqual((fng["nilai"], fng["zona"]), (None, P.NA))
        self.assertIn("BlockedError", fng["catatan"])
        self.assertEqual(self.by(p["indikator"], "*", "premium_coinbase")["zona"], P.NA)
        self.assertIn("hanya 3 titik OI", self.by(p["indikator"], "BTCUSDT", "oi_24h")["catatan"])
        self.assertEqual(self.conn.execute("SELECT n_gagal FROM panel_run").fetchone()[0], 2 + 2)   # fng, premium, oi BTC, oi ETH
        self.assertEqual(p["tidak_tersedia"], 3)
        # --cron diam walau ada sumber gagal
        with mock.patch.object(P, "PSIKOLOGI_DB", self.root / "p2.sqlite"), mock.patch.object(C, "PASAR_DB", self.root / "pasar.sqlite"), \
                mock.patch.object(C, "DATA_DIR", self.root), mock.patch.object(C, "LOG_DIR", self.root / "logs"), \
                mock.patch.object(P, "Sumber", lambda cfg: fs):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = P.main(["--cron", "--sekarang", "2026-10-10T10:07"])
            self.assertEqual((rc, out.getvalue()), (0, ""))
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                P.main(["--lihat", "--sekarang", "2026-10-10T10:08"])
            self.assertIn("# Panel psikologi BTCUSDT", out.getvalue())
        import logging
        lg = logging.getLogger("psikologi")
        for h in list(lg.handlers):
            h.close()
            lg.removeHandler(h)
        lg._crypto_analyst_ready = False  # type: ignore[attr-defined]

    def test_ps3_divergensi(self):
        self.assertEqual(len(P.divergensi({"harga_24h": 0.02, "oi_24h": -0.03})), 1)
        self.assertIn("short baru", P.divergensi({"harga_24h": -0.02, "oi_24h": 0.03})[0])
        self.assertIn("funding tinggi", P.divergensi({"funding": 0.0003, "taker": 0.85})[0])
        self.assertIn("ritel mayoritas long", P.divergensi({"ls_akun": 1.6, "ls_top": 0.9})[0])
        self.assertIn("premium Coinbase negatif", P.divergensi({"premium_coinbase": -0.001, "fng": 70})[0])
        self.assertEqual(P.divergensi({"harga_24h": 0.02, "oi_24h": 0.03, "funding": 0.0001, "taker": 1.0, "fng": 50}), [])
        self.assertEqual(P.divergensi({"harga_24h": None, "oi_24h": -0.03}), [])

    def test_ps4_percentile_mode_after_90_days(self):
        C.init_schema(self.conn, C.SCRIPTS_DIR / "schema_psikologi.sql", "1")
        with C.tx(self.conn):
            for d in range(100):
                for h in (0, 12):
                    ts = NOW - d * C.DAY_MS - h * HOUR_MS
                    self.conn.execute("INSERT INTO panel(ts,symbol,indikator,nilai,zona,sumber,catatan) VALUES(?,?,?,?,?,?,?)",
                                      (ts, "*", "fng", float((d * 2 + h) % 100), P.NETRAL, "uji", ""))
        batas, mode = P.batas_zona(self.conn, "fng", "*", self.cfg)
        self.assertEqual(mode, "persentil")
        self.assertTrue(5 <= batas[0] <= 15 and 85 <= batas[1] <= 95, batas)
        self.assertEqual(P.batas_zona(self.conn, "fng", "BTCUSDT", self.cfg), ((25, 75), "awal"))     # tanpa riwayat → ambang awal
        self.assertEqual(P.batas_zona(None, "ls_akun", "BTCUSDT", self.cfg), ((0.8, 2.0), "awal"))
        self.assertEqual(P.batas_zona(None, "oi_24h", "BTCUSDT", self.cfg), (None, "awal"))
        res = P.run(self.conn, self.pasar, FakeSumber(), NOW, self.cfg)
        self.assertEqual(res["mode"], "campuran")       # fng persentil, lainnya awal

    def test_ps5_oi_regimes(self):
        oi_down = [(NOW - (24 - i) * HOUR_MS, 8e9 * (1 - 0.003 * i)) for i in range(25)]      # −6.9%
        self.pasar.close()
        self.pasar = connect(self.root / "pasar.sqlite")
        seed_pasar(self.pasar, "BTCUSDT", 0.0001, [80000 - 150 * i for i in range(25)])      # −4.4%
        rows, _ = P.kumpulkan(NOW, FakeSumber(oi=oi_down), self.pasar, P.PsikologiConfig(symbols=("BTCUSDT",)))
        oi = self.by([vars(r) for r in rows], "BTCUSDT", "oi_24h")
        self.assertEqual(oi["zona"], P.TAKUT)
        self.assertIn("kapitulasi", oi["catatan"])
        oi_up = [(NOW - (24 - i) * HOUR_MS, 8e9 * (1 + 0.005 * i)) for i in range(25)]        # +12.7%
        seed_pasar(self.pasar, "BTCUSDT", 0.0001, [80000 + 5 * i for i in range(25)])         # +0.15%
        rows, _ = P.kumpulkan(NOW, FakeSumber(oi=oi_up), self.pasar, P.PsikologiConfig(symbols=("BTCUSDT",)))
        oi = self.by([vars(r) for r in rows], "BTCUSDT", "oi_24h")
        self.assertEqual((oi["zona"], "penumpukan" in oi["catatan"]), (P.SERAKAH, True))
        rows, _ = P.kumpulkan(NOW, FakeSumber(), None, P.PsikologiConfig(symbols=("BTCUSDT",)))
        d = {(r.symbol, r.indikator): r for r in rows}
        self.assertEqual((d[("BTCUSDT", "funding")].zona, d[("BTCUSDT", "harga_24h")].zona, d[("BTCUSDT", "oi_24h")].zona), (P.NA, P.NA, P.NETRAL))

    def test_ps6_retention_and_history(self):
        P.run(self.conn, self.pasar, FakeSumber(fng=40.0), NOW - 25 * HOUR_MS, self.cfg)
        P.run(self.conn, self.pasar, FakeSumber(fng=70.0), NOW, self.cfg)
        p = P.panel_untuk(self.conn, "BTCUSDT", NOW, self.cfg)
        self.assertAlmostEqual(p["perubahan_24j"]["fng"], 30.0)
        self.assertEqual(self.by(p["indikator"], "*", "fng")["nilai"], 70.0)
        with C.tx(self.conn):
            self.conn.execute("INSERT INTO panel(ts,symbol,indikator,nilai,zona,sumber,catatan) VALUES(?,?,?,?,?,?,?)",
                              (NOW - 401 * C.DAY_MS, "*", "fng", 1.0, P.NETRAL, "uji", ""))
        P.retention(self.conn, NOW, self.cfg)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM panel WHERE indikator='fng'").fetchone()[0], 2)
        self.assertEqual(P.panel_untuk(self.conn, "SOLUSDT", NOW, self.cfg)["status"], P.NA)
        self.assertIn("tidak tersedia", P.ringkas_teks(P.panel_untuk(self.conn, "SOLUSDT", NOW, self.cfg)))


if __name__ == "__main__":
    unittest.main()
