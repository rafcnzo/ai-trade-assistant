"""Tes mcp_server.py (M1–M10): tool dipanggil langsung lewat Tools dengan FixtureMarket; tanpa Hermes, tanpa jaringan."""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import common as C  # noqa: E402
from budget_guard import BudgetGuard  # noqa: E402
from common import MINUTE_MS, connect  # noqa: E402
from fixtures import BTC, CN, DAY, DAY_MS, FixtureMarket, t  # noqa: E402
import hipotesis as H  # noqa: E402
from mcp_server import TOOL_NAMES, Ctx, Tools, register  # noqa: E402
from paper_engine import EngineConfig, PaperEngine  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.clock = [t("10:03", sec=27)]
        self.market = FixtureMarket().set_mark(BTC, 82800.0, t("10:03")).set_mark(CN, 2.0, t("10:03"))
        # 24 jam bar 1m konstan untuk BTC (range 2) + 1 jam untuk CN
        start = t("10:03") - 24 * C.HOUR_MS
        for i in range(24 * 60):
            self.market.add_bar(BTC, start + i * MINUTE_MS, 82800, 82801, 82799, 82800)
        for i in range(60):
            self.market.add_bar(CN, t("09:03") + i * MINUTE_MS, 2.0, 2.01, 1.99, 2.0)
        h0 = t("10:03") - t("10:03") % C.HOUR_MS - 60 * C.HOUR_MS
        for i in range(60):                                   # bar 1h BTC: range 100 → ATR14 = 100
            self.market.add_bar_1h(BTC, h0 + i * C.HOUR_MS, 82800, 82850, 82750, 82800)
        self.engine = PaperEngine(connect(":memory:"), self.market, clock=lambda: self.clock[0], cfg=EngineConfig(acak_enabled=False))
        self.pasar = connect(self.root / "pasar.sqlite")
        C.init_schema(self.pasar, C.SCRIPTS_DIR / "schema_pasar.sql", "1")
        with C.tx(self.pasar):
            C.meta_set(self.pasar, "last_tick_ms", t("10:03"))
            self.pasar.execute("INSERT INTO mark_snapshot(symbol,ts,mark,index_price,last_funding_rate,next_funding_time) VALUES(?,?,?,?,?,?)",
                               (BTC, t("10:03"), 82800.0, 82790.0, 0.0001, t("15:00")))
            self.pasar.execute("INSERT INTO symbol_info(symbol,status,contract_type,quote_asset,onboard_date,liq_fee) VALUES(?,?,?,?,?,?)",
                               (BTC, "TRADING", "PERPETUAL", "USDT", t("10:00") - 2000 * C.DAY_MS, 0.0125))
        self.kand = self.root / "kandidat.sqlite"
        self.ctx = Ctx(engine=self.engine, market=self.market, pasar=self.pasar, root=self.root, clock=lambda: self.clock[0],
                       guard_factory=lambda: BudgetGuard(self.root / "budget.sqlite", clock=lambda: self.clock[0], kill_file=self.root / "STOP"),
                       kandidat_path=self.kand, psikologi_path=self.root / "psikologi.sqlite", proxy_health=None)
        self.tools = Tools(ctx=self.ctx)

    def tearDown(self):
        self.pasar.close()
        self.engine.conn.close()
        self.tmp.cleanup()

    def js(self, obj):
        return json.loads(json.dumps(obj, ensure_ascii=False))


class TestOrders(Base):
    def test_m1_pasang_order_ok_and_reject(self):
        r = self.tools.pasang_order("tiket", BTC, "LONG", 0.001, 100, harga=82700.0, tp=83500.0, plan_id="K1", pola="uji")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["order_id"], 1)
        self.assertIn("OK order #1", r["pesan"])
        self.assertIn("activate_ts_wib", r)
        self.js(r)
        row = self.engine.orders()[0]
        self.assertEqual(row["created_by"], "hermes")
        r2 = self.tools.pasang_order("tiket", BTC, "LONG", 0.001, 200, harga=82700.0)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["reject_code"], "LEVERAGE_CAP")
        r3 = self.tools.pasang_order("tiket", BTC, "SIDEWAYS", 0.001, 100, harga=82700.0)
        self.assertFalse(r3["ok"])

    def test_m2_batal_tutup(self):
        r = self.tools.pasang_order("tiket", BTC, "LONG", 0.001, 100, harga=82700.0)
        self.assertTrue(self.tools.batal_order(r["order_id"])["ok"])
        self.assertFalse(self.tools.batal_order(r["order_id"])["ok"])
        self.assertFalse(self.tools.tutup_posisi(99)["ok"])
        r = self.tools.pasang_order("tiket", BTC, "LONG", 0.001, 100, harga=82700.0)
        self.market.add_bar(BTC, t("10:04"), 82790, 82800, 82650, 82700)
        self.clock[0] = t("10:06")
        self.engine.step()
        self.assertEqual(self.tools.posisi()["n"], 1)
        self.assertTrue(self.tools.tutup_posisi(1)["ok"])
        self.assertEqual(self.tools.order_menunggu(termasuk_reduce_only=True)["n"], 1)
        self.assertEqual(self.tools.order_menunggu()["n"], 0)

    def test_m3_non_latin_roundtrip(self):
        r = self.tools.pasang_order("tiket", CN, "SHORT", 4, 10, harga=2.1, tp=2.0)
        self.assertTrue(r["ok"], r)
        out = self.js(self.tools.order_menunggu())
        self.assertEqual(out["order"][0]["symbol"], CN)
        self.assertIn("expire_ts_wib", out["order"][0])
        b = self.tools.budget_tiket()
        self.assertAlmostEqual(b["tiket"]["reserved"], 0.84 + 8.4 * 0.0002, places=6)
        self.assertEqual(b["swing"]["open"], 0)
        self.assertIn(CN, self.tools.laporan_paper()["markdown"])
        self.assertEqual(self.tools.riwayat()["n"], 0)


class TestMarketTools(Base):
    def test_m4_tabel_tiket(self):
        tab = self.tools.tabel_tiket(BTC, "LONG", entry=82700.0)
        self.assertNotIn("error", tab, tab)
        rows = {r["leverage"]: r for r in tab["baris"]}
        self.assertAlmostEqual(rows[150]["jarak_liq_pct"], 0.2678, places=3)
        self.assertAlmostEqual(rows[150]["fee_pct_tiket"], 6.0, places=6)
        self.assertIn("tidak bisa", rows[75]["keterangan"])
        self.assertAlmostEqual(tab["atr"]["1m"], 2.0, places=6)
        self.assertIsNotNone(tab["atr"]["5m"])
        self.assertEqual(tab["sumber_entry"], "input")
        self.assertEqual(tab["budget"]["remaining"], 1.0)
        self.js(tab)
        one = self.tools.tabel_tiket(BTC, "SHORT", leverage=100, target_pct=1.0)
        self.assertEqual([r["leverage"] for r in one["baris"]], [100])
        self.assertEqual(one["sumber_entry"], "mark terakhir")

    def test_m5_harga_fresh_and_stale(self):
        h = self.tools.harga(BTC)
        self.assertEqual((h["mark"], h["status"], h["funding_terakhir"]), (82800.0, "OK", 0.0001))
        self.assertIn("mark_ts_wib", h)
        self.clock[0] = t("10:10")
        self.assertEqual(self.tools.harga(BTC)["status"], "BASI")
        w = self.tools.waktu_sekarang()
        self.assertEqual((w["status_data"], w["hari_wib"]), ("BASI", DAY))
        self.assertEqual(self.tools.harga("NOPEUSDT")["status"], "tidak tersedia")
        info = self.tools.simbol_info(BTC)
        self.assertEqual((info["tick_size"], info["umur_listing_hari"], info["bracket"][0]["max_leverage"]), ("0.1", 2000, 150))

    def test_m5b_ohlcv_and_status(self):
        o = self.tools.ohlcv(BTC, "5m", 10)
        self.assertEqual(o["tf"], "5m")
        self.assertEqual(len(o["bars"]), 10)
        self.assertAlmostEqual(o["atr14"], 2.0, places=6)
        self.assertIn("bar_terakhir_wib", o)
        self.assertEqual(self.tools.ohlcv(BTC, "7m")["ok"], False)
        self.assertEqual(self.tools.ohlcv(CN, "1h")["status"], "tidak tersedia")
        s = self.tools.status_sistem()
        self.assertEqual((s["collector"]["status"], s["kill_switch"], s["pemindai"]), ("OK", False, "tidak tersedia"))
        tv = self.tools.top_volume(5)
        self.assertIn("catatan", tv)


class TestNotes(Base):
    def test_m6_jurnal_path_from_clock(self):
        r = self.tools.tulis_jurnal("keputusan", "../../x SKIP BTC", "alasan: jauh dari level", symbol=BTC, kandidat_id=7)
        self.assertEqual(r["path"], f"jurnal/agent/{DAY}.md")
        txt = (self.root / "jurnal" / "agent" / f"{DAY}.md").read_text(encoding="utf-8")
        self.assertIn("10:03 WIB — keputusan — ../../x SKIP BTC", txt)
        self.assertIn("kandidat=7", txt)
        self.assertFalse((self.root / "x").exists())
        self.assertEqual(self.tools.tulis_jurnal("salah", "a", "b")["ok"], False)
        r2 = self.tools.tulis_jurnal("keputusan", "[tiket] K8 BTCUSDT LONG - SKIP", "P-19", symbol=BTC, kandidat_id=8, alasan_skip="rr_p19")
        self.assertTrue(r2["ok"], r2)
        self.assertIn("kandidat=8 alasan=RR_P19", (self.root / "jurnal" / "agent" / f"{DAY}.md").read_text(encoding="utf-8"))
        bad = self.tools.tulis_jurnal("keputusan", "K9 SKIP", "x", alasan_skip="MALAS")
        self.assertFalse(bad["ok"])
        self.assertIn("alasan_skip harus salah satu", bad["error"])
        m = self.tools.baca_memori("jurnal")
        self.assertTrue(m["ada"])
        self.assertIn("SKIP BTC", m["isi"])
        self.assertFalse(self.tools.baca_memori("pelajaran")["ada"])

    def test_m7_hipotesis_limit_and_pola(self):
        for i in range(3):
            r = self.tools.tulis_hipotesis("breakout-gagal", BTC, "1h", "close_arah", "atas", batas_hari=3, kondisi=f"kondisi {i} | pipa")
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["id"], f"H-{i + 1:04d}")
        self.assertEqual(r["batas"], C.day_wib(t("10:03") + 3 * C.DAY_MS))
        r4 = self.tools.tulis_hipotesis("breakout-gagal", BTC, "1h", "close_arah", "atas", kondisi="k")
        self.assertFalse(r4["ok"])
        self.assertIn("3 hipotesis", r4["error"])
        self.assertFalse(self.tools.tulis_hipotesis("pola-ngawur", BTC, "1h", "close_arah", "atas", kondisi="k")["ok"])
        m = self.tools.baca_memori("hipotesis")
        self.assertIn("| H-0003 |", m["isi"])
        self.assertIn("kondisi 2 / pipa", m["isi"])
        self.assertFalse((self.root / "pasar" / "hipotesis.md").exists())        # view ditulis uji_hipotesis.py, bukan mcp_server
        u = self.tools.usul_pelajaran("kompresi", "ringkas", "bukti", 12)
        self.assertEqual((u["id"], u["status"]), ("U-001", "uji"))
        c = self.tools.tulis_catatan_harian("kerumunan long", jejak_grafik="WICK di 82650", rezim="range")
        self.assertTrue(c["ok"])
        txt = (self.root / "pasar" / "harian" / f"{DAY}.md").read_text(encoding="utf-8")
        self.assertIn("rezim: range", txt)
        self.tools.tulis_catatan_harian("revisi")
        self.assertIn("## Revisi", (self.root / "pasar" / "harian" / f"{DAY}.md").read_text(encoding="utf-8"))

    def test_m8_kandidat_terbaru(self):
        self.assertEqual(self.tools.kandidat_terbaru()["kandidat"], [])
        k = connect(self.kand)
        C.init_schema(k, C.SCRIPTS_DIR / "schema_kandidat.sql", "1")
        with C.tx(k):
            k.execute("INSERT INTO pemindai_run(ts,day_wib,n_symbols,n_kandidat,wake,alasan,ok) VALUES(?,?,?,?,?,?,?)", (t("10:00"), DAY, 20, 1, 1, "ada kandidat", 1))
            k.execute("INSERT INTO kandidat(run_ts,day_wib,symbol,arah_dugaan,mark,level,score,flags,lev_layak) VALUES(?,?,?,?,?,?,?,?,?)",
                      (t("10:00"), DAY, BTC, "LONG", 82800.0, 82650.0, 4, json.dumps(["WICK", "VOL"]), json.dumps([{"leverage": 100}])))
        k.close()
        r = self.tools.kandidat_terbaru()
        self.assertEqual(r["kandidat"][0]["flags"], ["WICK", "VOL"])
        self.assertEqual(r["kandidat"][0]["lev_layak"][0]["leverage"], 100)
        self.assertEqual(r["run"]["wake"], 1)
        self.assertEqual(r["kandidat"][0]["plan_id"], "K1")
        s = self.tools.status_sistem()
        self.assertEqual(s["pemindai"]["wake_hari_ini"], 1)
        # run berikutnya tanpa kandidat tidak mengosongkan daftar: tetap run wake=1 terakhir
        k = connect(self.kand)
        with C.tx(k):
            k.execute("INSERT INTO pemindai_run(ts,day_wib,n_symbols,n_kandidat,wake,alasan,ok) VALUES(?,?,?,?,?,?,?)", (t("10:05"), DAY, 20, 0, 0, "tidak ada kandidat", 1))
        k.close()
        r2 = self.tools.kandidat_terbaru()
        self.assertEqual([x["plan_id"] for x in r2["kandidat"]], ["K1"])
        self.assertEqual((r2["run"]["ts"], r2["run_terakhir"]["wake"]), (t("10:00"), 0))

    def test_m10_ohlcv_from_kline_1h(self):
        start = t("10:03") - 30 * C.DAY_MS
        start -= start % C.HOUR_MS
        for i in range(30 * 24):
            px = 80000 + (i % 24) * 10
            self.market.add_bar_1h(BTC, start + i * C.HOUR_MS, px, px + 50, px - 50, px + 5)
        o4 = self.tools.ohlcv(BTC, "4h", 5)
        self.assertEqual((o4["sumber"], o4["tf"]), ("kline_1h", "4h"))
        self.assertGreaterEqual(o4["n_bar"], 170)
        self.assertEqual(o4["bars"][-1]["open_time"] % (4 * C.HOUR_MS), 0)
        o1d = self.tools.ohlcv(BTC, "1d", 3)
        self.assertEqual((o1d["sumber"], o1d["n_bar"] >= 28), ("kline_1h", True))
        o1h = self.tools.ohlcv(BTC, "1h", 3)
        self.assertEqual(o1h["sumber"], "kline_1h")
        self.assertLessEqual(o1h["bars"][-1]["open_time"] + C.HOUR_MS, t("10:03"))
        # tanpa kline_1h → 1h jatuh ke resample 1m; 4h tidak tersedia dengan catatan
        cn1h = self.tools.ohlcv(CN, "1h")
        self.assertEqual((cn1h["status"], cn1h["sumber"]), ("tidak tersedia", "resample_1m"))
        self.assertIn("kline_1h belum cukup", self.tools.ohlcv(CN, "4h")["catatan"])


class TestHipotesisStatistik(Base):
    def test_m11_structured_hipotesis_and_statistik_lulus(self):
        r = self.tools.tulis_hipotesis("kompresi", BTC, "1h", "gerak_atr", "bawah", nilai=2.0, batas_hari=3, kondisi="range 10 bar 1h < 2×ATR")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["id"], r["harga_awal"]), ("H-0001", 82800.0))
        self.assertAlmostEqual(r["atr_awal"], 100.0, places=6)
        recs = H.load_jsonl(self.root / "pasar" / "hipotesis.jsonl")
        self.assertEqual((recs[0]["jenis"], recs[0]["oleh"], recs[0]["batas_ms"]), ("gerak_atr", "hermes", t("10:03", sec=27) + 3 * C.DAY_MS))
        self.assertFalse(self.tools.tulis_hipotesis("kompresi", BTC, "1h", "sentuh_harga", "atas", nilai=80000.0, kondisi="k")["ok"])   # sisi salah
        self.assertFalse(self.tools.tulis_hipotesis("kompresi", BTC, "2h", "close_arah", "atas", kondisi="k")["ok"])
        self.assertFalse(self.tools.tulis_hipotesis("kompresi", BTC, "1h", "close_arah", "atas", kondisi="k", batas_hari=9)["ok"])
        self.assertFalse(self.tools.tulis_hipotesis("kompresi", "NOPEUSDT", "1h", "close_arah", "atas", kondisi="k")["ok"])    # tanpa mark
        self.assertFalse(self.tools.tulis_hipotesis("kompresi", BTC, "1h", "close_arah", "atas", kondisi="")["ok"])
        m = self.tools.baca_memori("hipotesis")
        self.assertTrue(m["ada"])
        self.assertIn("| H-0001 |", m["isi"])
        self.assertIn("terbuka", m["isi"])
        self.assertFalse((self.root / "pasar" / "hipotesis.md").exists())
        s = self.tools.statistik_lulus()
        self.assertTrue(s["lulus"]["sampel"].startswith("belum"))
        self.assertTrue(str(s["akun"]["tiket"]["expectancy"]).startswith("tidak tersedia"))
        self.assertIn("# Statistik kelulusan", s["markdown"])
        self.assertIn("statistik_lulus", TOOL_NAMES)
        self.assertEqual(len(TOOL_NAMES), 31)


class TestPanelPsikologi(Base):
    def test_m12_panel_psikologi_and_frontmatter(self):
        import psikologi as P
        self.assertEqual(self.tools.panel_psikologi()["status"], "tidak tersedia")
        conn = connect(self.root / "psikologi.sqlite")
        C.init_schema(conn, C.SCRIPTS_DIR / "schema_psikologi.sql", "1")
        ts = t("10:00")
        rows = [P.Baris(ts, BTC, "funding", 0.0004, P.SERAKAH, "uji", ""), P.Baris(ts, BTC, "oi_24h", 0.12, P.SERAKAH, "uji", "penumpukan"),
                P.Baris(ts, BTC, "harga_24h", 0.002, P.NETRAL, "uji", ""), P.Baris(ts, BTC, "taker", 0.85, P.NETRAL, "uji", ""),
                P.Baris(ts, "*", "fng", 72.0, P.NETRAL, "uji", "")]
        P.simpan(conn, rows, "awal", 1, None, 10)
        conn.close()
        p = self.tools.panel_psikologi(BTC)
        self.assertEqual((p["status"], p["serakah_ekstrem"], p["takut_ekstrem"], len(p["indikator"])), ("OK", 2, 0, 5))
        self.assertTrue(any("funding tinggi" in d for d in p["divergensi"]))
        self.clock[0] = t("14:00")
        self.assertEqual(self.tools.panel_psikologi()["status"], "BASI")
        self.clock[0] = t("10:03", sec=27)
        self.assertTrue(self.tools.tulis_catatan_harian("ringkasan", rezim="range")["ok"])
        txt = (self.root / "pasar" / "harian" / f"{DAY}.md").read_text(encoding="utf-8")
        self.assertIn("fng: 72\n", txt)
        self.assertIn("funding_btc: 0.0004\n", txt)
        self.assertIn("panel_serakah_ekstrem: 2\n", txt)
        self.assertIn("panel_psikologi", TOOL_NAMES)


class TestReferensi(Base):
    def test_m13_cari_baca_playbook_jurnal(self):
        d = self.root / "referensi" / "buku" / "zone"
        d.mkdir(parents=True)
        (d / "bab-01.md").write_text("---\njudul_buku: \"Zone\"\npenulis: \"Douglas\"\nbab: 01\njudul_bab: \"Trapped\"\nhalaman: 1-9\n---\n\n# Trapped\n\nTrapped traders fuel reversals.\n", encoding="utf-8")
        (d / "_meta.json").write_text(json.dumps({"judul_buku": "Zone", "penulis": "Douglas", "status": "siap"}), encoding="utf-8")
        (self.root / "referensi" / "playbook.md").write_text("# Playbook\n\n| ID | Aturan | Kategori | Sumber | Status | Sejak |\n|---|---|---|---|---|---|\n| P-01 | Tidak entry tanpa stop | risiko | Tharp | aktif | 2026-10-11 |\n", encoding="utf-8")
        r = self.tools.cari_referensi("trapped")
        self.assertEqual((len(r["hasil"]), r["hasil"][0]["judul_buku"], r["buku"][0]["slug"]), (1, "Zone", "zone"))
        self.assertIn("Trapped traders fuel", r["hasil"][0]["cuplikan"])
        self.assertEqual(self.tools.cari_referensi("nothinghere")["hasil"], [])
        b = self.tools.baca_referensi("zone", 1)
        self.assertEqual((b["judul_bab"], b["lanjut_dari"]), ("Trapped", None))
        self.assertFalse(self.tools.baca_referensi("../zone", 1)["ok"])
        self.assertFalse(self.tools.baca_referensi("zone", 7)["ok"])
        pb = self.tools.baca_memori("playbook")
        self.assertTrue(pb["ada"])
        self.assertIn("P-01", pb["isi"])
        self.assertFalse(self.tools.baca_memori("indeks")["ada"])
        self.tools.tulis_jurnal("keputusan", "K9 BTC SKIP", "melanggar P-01", symbol=BTC, aturan_dilanggar="P-01")
        txt = (self.root / "jurnal" / "agent" / f"{DAY}.md").read_text(encoding="utf-8")
        self.assertIn("aturan_dilanggar=P-01", txt)
        self.assertIn("cari_referensi", TOOL_NAMES)


class TestSusulan(Base):
    def test_m14_catatan_harian_untuk_hari_lain(self):
        r = self.tools.tulis_catatan_harian("evaluasi susulan", rezim="range", hari="2026-10-09")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["path"], "pasar/harian/2026-10-09.md")
        self.assertIn("tanggal: 2026-10-09", (self.root / "pasar" / "harian" / "2026-10-09.md").read_text(encoding="utf-8"))
        self.assertFalse(self.tools.tulis_catatan_harian("x", hari="2026-12-31")["ok"])     # masa depan
        self.assertFalse(self.tools.tulis_catatan_harian("x", hari="kemarin")["ok"])


class TestArenaTools(Base):
    def test_m17_tambah_jatah_radar(self):
        import json as _j
        self.assertFalse(self.tools.tambah_jatah_radar(0)["ok"])
        self.assertFalse(self.tools.tambah_jatah_radar(99)["ok"])
        r = self.tools.tambah_jatah_radar(6)
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["tambahan_sekarang"], r["ditambah"]), (6, 6))
        d = _j.loads((self.root / "data" / "radar_jatah.json").read_text(encoding="utf-8"))
        self.assertEqual((d["day_wib"], d["tambah"], d["oleh"]), (C.day_wib(self.clock[0]), 6, "pemilik:/radar"))
        r2 = self.tools.tambah_jatah_radar(20)
        self.assertEqual(r2["tambahan_sekarang"], 24)                                    # kumulatif, dipotong di 24
        import pemindai as P
        self.assertEqual(P.jatah_tambahan(C.day_wib(self.clock[0]), self.root / "data" / "radar_jatah.json"), 24)
        self.assertEqual(P.jatah_tambahan("2000-01-01", self.root / "data" / "radar_jatah.json"), 0)   # hari lain → 0
        g = self.ctx.guard_factory()
        try:
            with C.tx(g.conn):
                g.conn.execute("INSERT INTO api_calls(ts,day_wib,month_wib,model_requested,model_served,purpose,input_tokens,output_tokens,cost_usd) VALUES(?,?,?,?,?,?,?,?,?)",
                               (self.clock[0], C.day_wib(self.clock[0]), C.month_wib(self.clock[0]), "m", "m", "uji", 1, 1, g.daily_cap))
        finally:
            g.conn.close()
        self.assertIn("batas", self.tools.tambah_jatah_radar(1)["error"])                 # biaya hari ini sudah di cap

    def test_m18_rencana_swing(self):
        r = self.tools.pasang_rencana_swing(BTC, "LONG", 20, legs=[{"harga": 82700.0, "persen": 100}], tps=[{"harga": 88000.0, "persen": 50}], sl=81000.0, trail_atr=2.0, plan_id="SW")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["plan_group"], len(r["order_ids"]), r["runner_pct"]), (1, 1, 50.0))
        self.assertAlmostEqual(r["atr_15m"], 2.0, places=6)                       # bar fixture: range 2 → ATR 2 → trail 4.0
        self.assertEqual(r["trail_dist"], 4.0)
        self.assertIn("OK rencana #1", r["pesan"])
        self.js(r)
        b = self.tools.budget_tiket()["swing"]
        self.assertEqual((b["open"], b["pending"], len(b["rencana"])), (0, 1, 1))
        self.assertEqual(self.tools.pasang_rencana_swing(BTC, "LONG", 20, legs=[{"harga": 82700.0, "persen": 100}], tps=[{"harga": 83000.0, "persen": 50}], sl=81000.0)["reject_code"], "RR_TOO_LOW")
        self.assertEqual(self.tools.tambah_leg_swing(99, 50, 82000.0, harga=82500.0)["reject_code"], "POSITION")
        om = self.tools.order_menunggu()["order"]
        self.assertEqual((om[0]["plan_group"], om[0]["leg_pct"]), (1, 100.0))
        c = self.tools.batal_order(plan_group=1)
        self.assertEqual((c["ok"], c["dibatalkan"]), (True, 1))
        self.assertFalse(self.tools.batal_order()["ok"])
        # tanpa ATR (simbol tanpa bar) + runner → ATR_TIDAK_TERSEDIA
        self.assertEqual(self.tools.pasang_rencana_swing(CN, "SHORT", 5, legs=[{"harga": 2.1, "persen": 100}], tps=[{"harga": 1.9, "persen": 50}], sl=2.3)["reject_code"], "ATR_TIDAK_TERSEDIA")

    def test_m16_papan_arena_dan_budget_persona(self):
        b = self.tools.budget_tiket()
        self.assertEqual(sorted(b["persona"]), ["breakout", "fade", "rentang", "tiket"])
        self.assertTrue(all(v["boleh_buka"] for v in b["persona"].values()))
        r = self.tools.pasang_order("fade", BTC, "SHORT", 0.001, 100, harga=82900.0, tp=82600.0, plan_id="K2")
        self.assertTrue(r["ok"], r)
        self.assertLess(self.tools.budget_tiket()["persona"]["fade"]["remaining"], 0.2)
        ar = self.tools.papan_arena()
        self.assertEqual([p["akun"] for p in ar["persona"]][0], "tiket")
        self.assertIsNone(ar["juara"])
        self.assertIn("# Arena", ar["markdown"])
        self.engine.set_account_status("rentang", "pensiun", "uji")
        self.assertFalse(self.tools.pasang_order("rentang", BTC, "LONG", 0.001, 100, harga=82700.0)["ok"])
        self.assertFalse(self.tools.budget_tiket()["persona"]["rentang"]["boleh_buka"])


class TestRegistration(unittest.TestCase):
    def test_m9_register_fastmcp(self):
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("paper-uji")
        names = register(mcp, Tools(ctx_factory=lambda: (_ for _ in ()).throw(RuntimeError("tidak dipanggil"))))
        self.assertEqual(len(names), 31)
        listed = asyncio.run(mcp.list_tools())
        self.assertEqual(sorted(x.name for x in listed), sorted(TOOL_NAMES))
        po = [x for x in listed if x.name == "pasang_order"][0]
        self.assertEqual(set(po.inputSchema["required"]), {"akun", "symbol", "sisi", "qty", "leverage"})
        self.assertIn("PAPER", po.description)


if __name__ == "__main__":
    unittest.main()
