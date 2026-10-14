---
name: evaluasi-harian
description: Evaluasi harian paper trading pukul 21:30 WIB (posisi yang ditutup sesudahnya, termasuk EOD 23:50, masuk evaluasi besok): laporan hasil, biaya API, catatan psikologi pasar, maksimal 3 hipotesis terukur, dan usulan pelajaran. Dipakai oleh cron evaluasi-harian atau saat pemilik minta "evaluasi hari ini".
version: 1.4.0
metadata:
  hermes:
    tags: [trading, paper, evaluasi, memori-pasar]
    category: trading
---

# Skill: evaluasi-harian

## Prosedur
1. `mcp_paper_waktu_sekarang`, lalu `mcp_paper_status_sistem` (collector, proxy, pemindai, kill switch).
2. FAKTA hari ini: `mcp_paper_laporan_paper`, `mcp_paper_riwayat`, `mcp_paper_budget_tiket`, `mcp_paper_biaya_api`.
3. Baca memori: `mcp_paper_baca_memori("pelajaran")` (pelajaran yang sudah dinilai skrip — pakai sebagai konteks),
   `mcp_paper_baca_memori("hipotesis")` (hasil uji hipotesis 23:40 malam ini: benar/salah/ambigu + baseline),
   `mcp_paper_statistik_lulus` (sampel, expectancy, tiket vs akun `acak`, kepatuhan; tulis "tidak tersedia" apa adanya).
   Lalu keputusan sendiri: `mcp_paper_baca_memori("jurnal")`. **Untuk setiap posisi yang ditutup hari itu panggil
   `mcp_paper_autopsi_posisi(id)`** dan tulis 2–3 kalimat per posisi: seberapa dekat ke TP (`persen_jalan_ke_tp`, kapan), kapan
   berbalik, apa yang benar dan apa yang salah (level? waktu? TP terlalu rapat? pengaman BREAKEVEN bekerja?), bukan sekadar "HANGUS".
   Per keputusan: rencana vs hasil
   (`TP` / `HANGUS` / `TIDAK_TERISI` / `SKIP` / `MANUAL`), apakah aturan skill tiket dipatuhi, berapa yang
   `ambiguous` (hasil ditentukan aturan pesimis).
4. Konteks pasar: `mcp_paper_panel_psikologi("BTCUSDT")` dan `("ETHUSDT")` (zona takut/serakah per indikator, divergensi,
   perubahan 24 jam — tidak ada skor gabungan; indikator `tidak tersedia` disebut apa adanya), `mcp_paper_top_volume`,
   `mcp_paper_ohlcv` BTCUSDT 1h dan ETHUSDT 1h (tren, jejak, level). Divergensi panel adalah bahan utama hipotesis
   `penumpukan-leverage`, `kapitulasi`, `divergensi-funding`.
5. `mcp_paper_tulis_catatan_harian(ringkasan_psikologi, jejak_grafik, reaksi_berita="tidak tersedia", rezim)`:
   2–4 kalimat: siapa yang dominan, siapa yang terjebak, apa yang berubah dari kemarin.
6. Maksimal 3 `mcp_paper_tulis_hipotesis(pola, symbol, tf, jenis, arah, nilai, batas_hari, kondisi)`:
   `jenis` = `sentuh_harga` (nilai = harga target), `gerak_atr` (nilai = kelipatan ATR14 tf, mis. 2.0), atau `close_arah`;
   `tf` 1h|4h|1d; `arah` atas|bawah; `batas_hari` 1–7; `kondisi` = fakta terukur pemicunya. Contoh:
   `tulis_hipotesis("kompresi", "BTCUSDT", "4h", "gerak_atr", "bawah", 2.0, 3, "range 10 bar 4h = 1.4×ATR, funding +0.03%")`.
   Hipotesis dinilai skrip saat jatuh tempo, bukan saya; baseline dihitung dari titik awal acak.
7. `mcp_paper_usul_pelajaran` hanya jika satu pola berulang ≥ 3 kali di jurnal/riwayat dengan hasil konsisten.
   Status `uji`; bukan aturan sebelum disetujui pemilik.
8. Balasan Telegram ≤ 20 baris: hasil hari ini (jumlah tiket, TP/HANGUS/TIDAK_TERISI, net), biaya API vs cap,
   pelajaran singkat, hipotesis baru (ID), hal yang perlu pemilik putuskan.

## Evaluasi susulan (laptop mati pukul 21:30)
Jika pesan cron/pemilik menyebut tanggal tertentu, evaluasi **tanggal itu**: `hari="YYYY-MM-DD"` pada `mcp_paper_laporan_paper`,
`mcp_paper_riwayat`, `mcp_paper_biaya_api`, `mcp_paper_baca_memori("jurnal", hari)`, dan `mcp_paper_tulis_catatan_harian(..., hari=...)`.
Panel psikologi & ohlcv tetap kondisi sekarang (sebutkan itu). Hipotesis baru boleh dibuat seperti biasa (bertanggal hari ini).

## Jebakan
- Jangan menyimpulkan "strategi bekerja/tidak" dari < 10 sampel; sebut jumlah sampel.
- Jangan menulis hipotesis yang tidak bisa salah ("pasar akan volatil").
- Jika proxy menunjukkan biaya hari ini > 70% cap, sebutkan sebagai risiko.
- Jangan menulis pelajaran sendiri dan jangan menilai hipotesis sendiri: `pasar/pelajaran.md` dan hasil hipotesis hanya
  ditulis skrip. Usulan lewat `mcp_paper_usul_pelajaran` berstatus `uji` sampai pemilik memutuskan.
- Akun `acak` adalah bayangan acak yang dibuat mesin untuk pembanding; saya tidak pernah memasang order di akun itu.
