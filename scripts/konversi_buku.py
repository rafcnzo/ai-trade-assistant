"""konversi_buku.py — pecah ebook (PDF/EPUB) menjadi referensi/buku/<slug>/bab-NN.md (§15.4).

  .venv/Scripts/python.exe scripts/konversi_buku.py referensi/buku/Buku.pdf slug-buku --judul "Judul" --penulis "Penulis"

PDF: pymupdf. Bab dari bookmark (get_toc) bila ada; tanpa bookmark → heuristik judul (baris berfont besar di bagian atas
halaman, 3–80 kandidat); gagal → potong tiap --per-halaman. PDF tanpa teks (hasil scan) → _meta.json status perlu_ocr, exit 2.
EPUB: ebooklib + beautifulsoup4, bab = item spine berteks. Isi buku tidak pernah masuk git (referensi/buku/ di-gitignore).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from referensi import slug_ok  # noqa: E402

VERSI_KONVERSI = 1
MIN_CHARS_PER_PAGE = 200


@dataclass
class Bab:
    nomor: int
    judul: str
    halaman_awal: int   # 1-based
    halaman_akhir: int
    teks: str


# --------------------------------------------------------------------------- PDF
def _pages_text(doc) -> list[str]:
    return [p.get_text("text") for p in doc]


def _bersih(t: str) -> str:
    t = re.sub(r"-\n(?=[a-z])", "", t)          # pemenggalan kata di ujung baris
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def judul_heuristik(doc, min_n: int = 3, max_n: int = 80) -> list[tuple[int, str]]:
    """[(halaman 0-based, judul)] dari span berfont besar di 30% atas halaman."""
    sizes: Counter = Counter()
    cand: list[tuple[int, float, str]] = []
    for i, page in enumerate(doc):
        h = page.rect.height or 1
        for b in page.get_text("dict").get("blocks", []):
            for ln in b.get("lines", []):
                txt = "".join(s.get("text", "") for s in ln.get("spans", [])).strip()
                if not txt:
                    continue
                size = max(s.get("size", 0) for s in ln.get("spans", []))
                sizes[round(size, 1)] += len(txt)
                y = ln.get("bbox", [0, 0, 0, 0])[1]
                if 4 <= len(txt) <= 80 and y < 0.30 * h:
                    cand.append((i, size, txt))
    if not sizes:
        return []
    total = sum(sizes.values())
    acc, p97 = 0, None
    for sz in sorted(sizes):
        acc += sizes[sz]
        if acc >= 0.97 * total:
            p97 = sz
            break
    body = max(sizes, key=sizes.get)
    thr = max(p97 or 0, body * 1.3)
    out: list[tuple[int, str]] = []
    seen_page = set()
    for i, size, txt in cand:
        if size >= thr and i not in seen_page and not re.fullmatch(r"[\d\s.•-]+", txt):
            out.append((i, txt))
            seen_page.add(i)
    if not (min_n <= len(out) <= max_n):
        return []
    return out


def bab_pdf(path: Path, per_halaman: int, paksa_halaman: bool = False) -> tuple[list[Bab], str]:
    import pymupdf as fitz

    doc = fitz.open(str(path))
    pages = _pages_text(doc)
    n = len(pages)
    if n == 0 or sum(len(p) for p in pages) / n < MIN_CHARS_PER_PAGE:
        return [], "perlu_ocr"
    starts: list[tuple[int, str]] = []
    metode = "halaman"
    if not paksa_halaman:
        toc = [(lvl, t, pg) for lvl, t, pg in doc.get_toc() if lvl == 1 and 1 <= pg <= n]
        if len(toc) >= 2:
            starts = [(pg - 1, t.strip()) for _, t, pg in toc]
            metode = "bookmark"
        else:
            hs = judul_heuristik(doc)
            if hs:
                starts, metode = hs, "heuristik"
    if not starts:
        starts = [(i, f"Halaman {i + 1}–{min(n, i + per_halaman)}") for i in range(0, n, per_halaman)]
    if starts[0][0] != 0:
        starts.insert(0, (0, "Pendahuluan"))
    babs = []
    for k, (p0, judul) in enumerate(starts):
        p1 = starts[k + 1][0] if k + 1 < len(starts) else n
        teks = _bersih("\n\n".join(pages[p0:p1]))
        babs.append(Bab(k + 1, judul, p0 + 1, p1, teks))
    return babs, metode


# --------------------------------------------------------------------------- EPUB
def bab_epub(path: Path) -> tuple[list[Bab], str]:
    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    book = epub.read_epub(str(path))
    babs = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        teks = _bersih(soup.get_text("\n"))
        if len(teks) < 400:
            continue
        h = soup.find(["h1", "h2", "h3"])
        judul = h.get_text(" ", strip=True) if h else item.get_name()
        babs.append(Bab(len(babs) + 1, judul[:120], 0, 0, teks))
    return babs, "epub"


# --------------------------------------------------------------------------- tulis
def tulis(root: Path, slug: str, sumber: Path, judul_buku: str, penulis: str, babs: list[Bab], metode: str) -> Path:
    d = root / "referensi" / "buku" / slug
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("bab-*.md"):
        old.unlink()
    for b in babs:
        hal = f"{b.halaman_awal}-{b.halaman_akhir}" if b.halaman_awal else "-"
        fm = (f"---\njudul_buku: \"{judul_buku}\"\npenulis: \"{penulis}\"\nbab: {b.nomor:02d}\njudul_bab: \"{b.judul.replace(chr(34), chr(39))}\"\n"
              f"halaman: {hal}\nsumber: \"{sumber.name}\"\nmetode: {metode}\nversi_konversi: {VERSI_KONVERSI}\n---\n\n")
        (d / f"bab-{b.nomor:02d}.md").write_text(fm + f"# {b.judul}\n\n{b.teks}\n", encoding="utf-8")
    meta = {"slug": slug, "judul_buku": judul_buku, "penulis": penulis, "sumber": sumber.name, "metode": metode, "n_bab": len(babs),
            "status": "siap" if babs else "perlu_ocr", "versi_konversi": VERSI_KONVERSI, "dikonversi": C.fmt_wib(C.now_ms()),
            "bab": [{"bab": b.nomor, "judul": b.judul, "halaman": [b.halaman_awal, b.halaman_akhir], "karakter": len(b.teks)} for b in babs]}
    (d / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def konversi(path: Path, slug: str, judul: Optional[str], penulis: Optional[str], per_halaman: int = 10, paksa_halaman: bool = False,
             root: Optional[Path] = None) -> dict:
    root = root or C.ROOT
    if not slug_ok(slug):
        raise ValueError("slug: huruf kecil/angka/minus, 2–61 karakter")
    if not path.exists():
        raise FileNotFoundError(str(path))
    ext = path.suffix.lower()
    if ext == ".pdf":
        babs, metode = bab_pdf(path, per_halaman, paksa_halaman)
    elif ext == ".epub":
        babs, metode = bab_epub(path)
    else:
        raise ValueError("hanya .pdf atau .epub")
    judul = judul or path.stem.replace("-", " ").replace("_", " ")
    d = tulis(root, slug, path, judul, penulis or "-", babs, metode)
    return {"slug": slug, "dir": d.as_posix(), "n_bab": len(babs), "metode": metode, "status": "siap" if babs else "perlu_ocr",
            "bab": [(b.nomor, b.judul, b.halaman_awal, b.halaman_akhir, len(b.teks)) for b in babs]}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Konversi ebook ke referensi/buku/<slug>/bab-NN.md")
    ap.add_argument("file")
    ap.add_argument("slug")
    ap.add_argument("--judul", default=None)
    ap.add_argument("--penulis", default=None)
    ap.add_argument("--per-halaman", type=int, default=10)
    ap.add_argument("--paksa-halaman", action="store_true", help="abaikan bookmark/heuristik, potong per halaman")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    r = konversi(Path(args.file), args.slug, args.judul, args.penulis, args.per_halaman, args.paksa_halaman)
    if r["status"] == "perlu_ocr":
        print(f"{args.file}: tidak ada lapisan teks (hasil scan) → perlu OCR dulu; _meta.json ditandai perlu_ocr")
        return 2
    print(f"{r['slug']}: {r['n_bab']} bab (metode {r['metode']}) → {r['dir']}")
    for nomor, judul, a, b, k in r["bab"]:
        print(f"  bab-{nomor:02d} hal {a}-{b} ({k} karakter): {judul}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
