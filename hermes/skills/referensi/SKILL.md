---
name: referensi
description: Cari dan kutip buku referensi trading milik pemilik (psikologi, risiko, price action, crypto) lewat tool mcp_paper_cari_referensi / mcp_paper_baca_referensi. Dipakai saat pemilik ketik /referensi <kata kunci> atau bertanya "menurut buku", "apa kata Douglas/Brooks", atau saat jawaban menyentuh konsep psikologi/risiko/pola.
version: 1.0.0
metadata:
  hermes:
    tags: [referensi, buku, playbook]
    category: trading
---

# Skill: referensi

## Prosedur
1. `mcp_paper_cari_referensi(kata_kunci, n=5)`; kata kunci bahasa Inggris (buku berbahasa Inggris), 1–3 kata inti.
   Kosong? Coba sinonim sekali, lalu katakan "tidak ditemukan di buku yang ada" — jangan mengarang kutipan.
2. Bila perlu konteks: `mcp_paper_baca_referensi(slug, bab)`; bab panjang → lanjutkan dengan `mulai=lanjut_dari`.
3. Balasan ≤ 10 baris: untuk tiap hasil (maks 3): **judul buku — bab NN "judul bab"** (halaman), parafrase 1–2 kalimat,
   kutipan langsung ≤ 15 kata dalam tanda kutip. Tutup dengan 1 kalimat: hubungannya dengan aturan playbook (`mcp_paper_baca_memori("playbook")`)
   atau situasi pasar yang ditanyakan.

## Jebakan
- Kutipan harus persis dari `cuplikan`/`isi` tool; jangan menyusun kalimat lalu menyebutnya kutipan.
- Jangan menyalin bab panjang ke chat; isi buku untuk pemakaian pribadi pemilik.
- Buku yang `perlu_ocr` belum bisa dicari; sebutkan bila pemilik menanyakannya.
