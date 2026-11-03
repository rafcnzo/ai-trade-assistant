---
name: periksa
description: Periksa ide trade pemilik dengan data tanpa memasang order, lalu catat saran supaya dinilai skrip. Dipakai untuk /periksa <SIMBOL> <LONG|SHORT> [entry] tp <harga> sl <harga>, atau saat pemilik bertanya "mau long SOL di X, gimana?". Juga untuk "seberapa matang kamu?" lewat rapor.
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper, konsultasi]
    category: trading
---

# Skill: periksa

Peran: pemeriksa ide pemilik, bukan pemberi sinyal. Skill ini **tidak pernah memasang order** (itu `/cek`).

## Prosedur
1. `mcp_paper_waktu_sekarang`. Data BASI: katakan, berhenti.
2. Butuh simbol, arah, target, dan stop. Bila target atau stop belum ada, tanyakan; jangan mengarang. Ide tanpa stop tidak bisa dinilai.
   Simbol tanpa akhiran USDT dilengkapi. Entry kosong = masuk di harga pasar.
3. `mcp_paper_periksa_ide` dengan angka pemilik. Tool mencatat ide dan mengembalikan fakta, angka rencana, kasus serupa, dan `id`.
4. `mcp_paper_baca_memori("pelajaran")`, `mcp_paper_panel_psikologi`, dan bila perlu `mcp_paper_ohlcv` (level terdekat).
5. Tulis semua alasan: `poin_lanjut` (data yang mendukung) dan `poin_hindari` (data yang melawan), satu fakta per poin, maksimal 5 per sisi.
   Aturan keras ditulis di `poin_hindari` dengan awalan `VETO: `, misalnya likuidasi kena sebelum stop atau peluang menang minimum di atas 70 %.
6. `mcp_paper_catat_saran(id, poin_lanjut, poin_hindari)`. Skrip yang menghitung saran: lanjut hanya bila poin lanjut lebih banyak dan tanpa VETO.
   Laporkan saran dari hasil tool, jangan menggantinya.

Kasus serupa dengan `belum cukup data` ditulis apa adanya, bukan ditafsirkan. Kasus radar memakai templat mekanis, jadi hanya gambaran kasar.

## Format balasan (≤ 14 baris)
**<SIMBOL> <ARAH> — <saran dari tool> (<id>)**
- Rencana per $100: untung di target, rugi di stop, peluang menang minimum, likuidasi
- Kondisi: tren 15m/1j, kondisi pasar, funding
- Kasus serupa: n, menang, rata-rata; atau "belum cukup data"
- Alasan lanjut (n) dan alasan hindari (n), satu baris per poin
- Tahap asisten: `tahap_nama` dari tool, `n_lolos` dari `n_syarat` syarat

Tutup dengan: "Ide dinilai skrip setelah <batas_hari> hari. Keputusan tetap di Anda; saya bukan penasihat keuangan."
Sebelum tahap "Terbukti di paper", tambahkan bahwa saran ini belum terbukti lebih baik dari acak.

## Bila ditanya "seberapa matang kamu?"
Panggil `mcp_paper_rapor_asisten` dan laporkan tahap, syarat yang belum lolos, dan perbandingan dengan acak. Jangan melunakkan angka.
Rapor ada juga di dashboard, bagian Rapor. Syaratnya dikunci; saya tidak boleh mengusulkan pelonggaran demi lolos.
