"""referensi.py — pencarian & pembacaan bab buku yang sudah dikonversi (§15), modul murni tanpa jaringan.

Tata letak: referensi/buku/<slug>/bab-NN.md (frontmatter judul_buku, penulis, bab, judul_bab, halaman, …; gitignored),
referensi/indeks.md dan referensi/playbook.md (di-commit). Tanpa embedding/vector DB: pencarian kata kunci sederhana
(semua kata harus muncul), skor = jumlah kemunculan, cuplikan ≤ konteks karakter. Dipakai mcp_server.py (cari_referensi,
baca_referensi) dan tes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
MAKS_BACA = 12_000


def root_buku(root: Path) -> Path:
    return Path(root) / "referensi" / "buku"


def slug_ok(slug: str) -> bool:
    return bool(SLUG_RE.match(slug or ""))


def frontmatter(text: str) -> tuple[dict, str]:
    """Memisahkan frontmatter YAML sederhana (key: value per baris) dari isi."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta: dict = {}
    for ln in text[4:end].splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[end + 5:]


def daftar(root: Path) -> list[dict]:
    """Buku yang sudah dikonversi: [{slug, judul_buku, penulis, n_bab, status}]."""
    out = []
    base = root_buku(root)
    if not base.exists():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        meta_p = d / "_meta.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
        babs = sorted(d.glob("bab-*.md"))
        out.append({"slug": d.name, "judul_buku": meta.get("judul_buku", d.name), "penulis": meta.get("penulis", "-"),
                    "n_bab": len(babs), "status": meta.get("status", "siap" if babs else "kosong")})
    return out


def _bab_files(root: Path, slug: Optional[str] = None) -> list[Path]:
    base = root_buku(root)
    if not base.exists():
        return []
    dirs = [base / slug] if slug else [p for p in base.iterdir() if p.is_dir()]
    files: list[Path] = []
    for d in dirs:
        if d.is_dir():
            files += sorted(d.glob("bab-*.md"))
    return files


def _kata(kata_kunci: str) -> list[str]:
    return [k.lower() for k in re.split(r"[\s,;]+", (kata_kunci or "").strip()) if len(k) >= 2]


def cari(root: Path, kata_kunci: str, n: int = 5, konteks: int = 320, slug: Optional[str] = None, salah_satu: bool = False) -> list[dict]:
    kata = _kata(kata_kunci)
    if not kata:
        return []
    hasil = []
    for f in _bab_files(root, slug):
        meta, isi = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        low = isi.lower()
        hits = {k: low.count(k) for k in kata}
        if (not salah_satu and any(v == 0 for v in hits.values())) or sum(hits.values()) == 0:
            continue
        first = min(low.find(k) for k in kata if low.find(k) >= 0)
        a = max(0, first - konteks // 3)
        cuplikan = re.sub(r"\s+", " ", isi[a:a + konteks]).strip()
        hasil.append({"slug": f.parent.name, "bab": meta.get("bab", f.stem), "judul_bab": meta.get("judul_bab", ""),
                      "judul_buku": meta.get("judul_buku", f.parent.name), "penulis": meta.get("penulis", ""), "halaman": meta.get("halaman", ""),
                      "path": f.relative_to(root).as_posix(), "skor": sum(hits.values()), "kemunculan": hits,
                      "cuplikan": ("…" if a > 0 else "") + cuplikan + "…"})
    hasil.sort(key=lambda h: (-h["skor"], h["slug"], h["bab"]))
    return hasil[:n]


def baca(root: Path, slug: str, bab, maks: int = MAKS_BACA, mulai: int = 0) -> dict:
    if not slug_ok(slug):
        raise ValueError("slug tidak valid (huruf kecil, angka, tanda minus)")
    try:
        nomor = int(str(bab).replace("bab-", ""))
    except ValueError:
        raise ValueError("bab harus nomor, mis. 3 atau bab-03")
    f = root_buku(root) / slug / f"bab-{nomor:02d}.md"
    if not f.exists():
        raise FileNotFoundError(f"{slug} bab {nomor} tidak ada; lihat daftar bab lewat indeks")
    meta, isi = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
    mulai = max(0, int(mulai))
    potongan = isi[mulai:mulai + maks]
    return {**meta, "slug": slug, "path": f.relative_to(root).as_posix(), "mulai": mulai, "panjang": len(isi),
            "lanjut_dari": (mulai + maks) if mulai + maks < len(isi) else None, "isi": potongan}


def playbook(root: Path) -> str:
    p = Path(root) / "referensi" / "playbook.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def indeks(root: Path) -> str:
    p = Path(root) / "referensi" / "indeks.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def aturan_playbook(root: Path) -> list[dict]:
    """Baris tabel aturan `| P-xx | ... |` → [{id, aturan, kategori, sumber, status}]."""
    out = []
    for ln in playbook(root).splitlines():
        if ln.startswith("| P-"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 5:
                out.append({"id": c[0], "aturan": c[1], "kategori": c[2], "sumber": c[3], "status": c[4]})
    return out
