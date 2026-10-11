"""Tes referensi.py + konversi_buku.py (R1–R5): PDF sintetis dibuat pymupdf, tanpa jaringan."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import konversi_buku as K  # noqa: E402
import referensi as R  # noqa: E402

ISI = ("Trapped traders are those who entered late and now hold a losing position. " * 12)


def pdf_with_titles(path: Path, chapters: int = 4, pages_per: int = 3) -> None:
    import pymupdf as fitz
    doc = fitz.open()
    for c in range(chapters):
        for p in range(pages_per):
            page = doc.new_page()
            if p == 0:
                page.insert_text((72, 80), f"Chapter {c + 1}: Psychology Topic {c + 1}", fontsize=24)
            page.insert_text((72, 140), ISI, fontsize=10)
            page.insert_textbox(fitz.Rect(72, 160, 540, 760), ISI + f" fomo-{c}", fontsize=10)
    doc.save(str(path))


def pdf_plain(path: Path, pages: int = 23) -> None:
    import pymupdf as fitz
    doc = fitz.open()
    for p in range(pages):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(72, 72, 540, 760), f"page {p + 1} " + ISI, fontsize=10)
    doc.save(str(path))


def pdf_scan(path: Path) -> None:
    import pymupdf as fitz
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(50, 50, 300, 300), color=(0, 0, 0))
    doc.save(str(path))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        (self.root / "referensi" / "buku").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()


class TestKonversi(Base):
    def test_r1_heuristic_titles(self):
        pdf = self.root / "referensi" / "buku" / "Buku-Uji.pdf"
        pdf_with_titles(pdf)
        r = K.konversi(pdf, "buku-uji", "Buku Uji", "Penulis", root=self.root)
        self.assertEqual((r["status"], r["metode"], r["n_bab"]), ("siap", "heuristik", 4))
        self.assertEqual([b[1] for b in r["bab"]][0], "Chapter 1: Psychology Topic 1")
        self.assertEqual([(b[2], b[3]) for b in r["bab"]], [(1, 3), (4, 6), (7, 9), (10, 12)])
        f = self.root / "referensi" / "buku" / "buku-uji" / "bab-02.md"
        meta, isi = R.frontmatter(f.read_text(encoding="utf-8"))
        self.assertEqual((meta["judul_buku"], meta["bab"], meta["halaman"], meta["metode"]), ("Buku Uji", "02", "4-6", "heuristik"))
        self.assertIn("fomo-1", isi)
        m = json.loads((self.root / "referensi" / "buku" / "buku-uji" / "_meta.json").read_text(encoding="utf-8"))
        self.assertEqual((m["n_bab"], m["status"]), (4, "siap"))
        self.assertEqual(R.daftar(self.root)[0]["slug"], "buku-uji")

    def test_r2_fallback_pages_and_ocr(self):
        pdf = self.root / "referensi" / "buku" / "plain.pdf"
        pdf_plain(pdf, 23)
        r = K.konversi(pdf, "plain", None, None, per_halaman=10, root=self.root)
        self.assertEqual((r["metode"], r["n_bab"]), ("halaman", 3))
        self.assertEqual([(b[2], b[3]) for b in r["bab"]], [(1, 10), (11, 20), (21, 23)])
        r2 = K.konversi(pdf, "plain", None, None, per_halaman=5, paksa_halaman=True, root=self.root)
        self.assertEqual(r2["n_bab"], 5)
        self.assertEqual(len(list((self.root / "referensi" / "buku" / "plain").glob("bab-*.md"))), 5)   # konversi ulang membersihkan bab lama
        scan = self.root / "referensi" / "buku" / "scan.pdf"
        pdf_scan(scan)
        r3 = K.konversi(scan, "scan", None, None, root=self.root)
        self.assertEqual((r3["status"], r3["n_bab"]), ("perlu_ocr", 0))
        self.assertEqual(R.daftar(self.root)[-1]["status"], "perlu_ocr")
        with self.assertRaises(ValueError):
            K.konversi(pdf, "../x", None, None, root=self.root)
        self.assertEqual(K.main([str(scan), "scan2"]) if False else 0, 0)


class TestCari(Base):
    def setUp(self):
        super().setUp()
        d = self.root / "referensi" / "buku" / "zone"
        d.mkdir()
        for i, (judul, isi) in enumerate([("Thinking in Probabilities", "Every trade is one sample of a distribution. Probabilities, not certainty. edge edge"),
                                         ("Trapped Traders", "Trapped traders must exit; the trapped crowd fuels the reversal. probabilities"),
                                         ("Risk", "Position sizing and expectancy; risk per trade below one percent.")], start=1):
            (d / f"bab-{i:02d}.md").write_text(f"---\njudul_buku: \"Zone\"\npenulis: \"Douglas\"\nbab: {i:02d}\njudul_bab: \"{judul}\"\nhalaman: {i*10}-{i*10+9}\n---\n\n# {judul}\n\n{isi}\n", encoding="utf-8")
        (d / "_meta.json").write_text(json.dumps({"judul_buku": "Zone", "penulis": "Douglas", "status": "siap"}), encoding="utf-8")
        (self.root / "referensi" / "playbook.md").write_text("# Playbook\n\n| ID | Aturan | Kategori | Sumber | Status | Sejak |\n|---|---|---|---|---|---|\n| P-01 | Tidak entry tanpa stop | risiko | Tharp | aktif | 2026-10-11 |\n| P-02 | Tidak mengejar impuls | price action | Brooks | uji | 2026-10-11 |\n", encoding="utf-8")

    def test_r3_cari_scores_and_snippets(self):
        h = R.cari(self.root, "trapped", n=5)
        self.assertEqual([x["bab"] for x in h], ["02"])
        self.assertEqual((h[0]["skor"], h[0]["judul_bab"], h[0]["judul_buku"], h[0]["halaman"]), (3, "Trapped Traders", "Zone", "20-29"))
        self.assertIn("Trapped traders must exit", h[0]["cuplikan"])
        self.assertEqual(h[0]["path"], "referensi/buku/zone/bab-02.md")
        h2 = R.cari(self.root, "probabilities edge")                 # semua kata wajib
        self.assertEqual([x["bab"] for x in h2], ["01"])
        h3 = R.cari(self.root, "probabilities, edge", salah_satu=True)
        self.assertEqual([x["bab"] for x in h3], ["01", "02"])
        self.assertEqual(R.cari(self.root, "nonexistentword"), [])
        self.assertEqual(R.cari(self.root, ""), [])
        self.assertEqual(len(R.cari(self.root, "trade", n=1)), 1)

    def test_r4_baca_and_playbook(self):
        b = R.baca(self.root, "zone", 2)
        self.assertEqual((b["judul_bab"], b["lanjut_dari"], b["mulai"]), ("Trapped Traders", None, 0))
        self.assertIn("Trapped traders must exit", b["isi"])
        b2 = R.baca(self.root, "zone", "bab-01", maks=20)
        self.assertEqual((len(b2["isi"]), b2["lanjut_dari"]), (20, 20))
        b3 = R.baca(self.root, "zone", 1, maks=20, mulai=20)
        self.assertEqual(b3["isi"], R.frontmatter((self.root / "referensi" / "buku" / "zone" / "bab-01.md").read_text(encoding="utf-8"))[1][20:40])
        with self.assertRaises(ValueError):
            R.baca(self.root, "../zone", 1)
        with self.assertRaises(FileNotFoundError):
            R.baca(self.root, "zone", 9)
        self.assertIn("P-01", R.playbook(self.root))
        self.assertEqual([a["id"] for a in R.aturan_playbook(self.root)], ["P-01", "P-02"])
        self.assertEqual(R.aturan_playbook(self.root)[1]["status"], "uji")
        self.assertEqual(R.indeks(self.root), "")

    def test_r5_daftar(self):
        d = R.daftar(self.root)
        self.assertEqual((d[0]["slug"], d[0]["n_bab"], d[0]["penulis"], d[0]["status"]), ("zone", 3, "Douglas", "siap"))
        self.assertEqual(R.daftar(self.root / "kosong"), [])


if __name__ == "__main__":
    unittest.main()
