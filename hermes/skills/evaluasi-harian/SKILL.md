---
name: evaluasi-harian
description: Evaluasi harian paper trading pukul 23:55 WIB: laporan hasil, biaya API, catatan psikologi pasar, maksimal 3 hipotesis terukur, dan usulan pelajaran. Dipakai oleh cron evaluasi-harian atau saat pemilik minta "evaluasi hari ini".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper, evaluasi, memori-pasar]
    category: trading
---

# Skill: evaluasi-harian

## Prosedur
1. `mcp_paper_waktu_sekarang`, lalu `mcp_paper_status_sistem` (collector, proxy, pemindai, kill switch).
2. FAKTA hari ini: `mcp_paper_laporan_paper`, `mcp_paper_riwayat`, `mcp_paper_budget_tiket`, `mcp_paper_biaya_api`.
3. Baca keputusan sendiri: `mcp_paper_baca_memori("jurnal")`. Per keputusan: rencana vs hasil
   (`TP` / `HANGUS` / `TIDAK_TERISI` / `SKIP` / `MANUAL`), apakah aturan skill tiket dipatuhi, berapa yang
   `ambiguous` (hasil ditentukan aturan pesimis).
4. Konteks pasar: `mcp_paper_top_volume`, `mcp_paper_ohlcv` BTCUSDT 1h dan ETHUSDT 1h (tren, jejak, level),
   `mcp_paper_harga` untuk funding. Panel psikologi lengkap belum tersedia → tulis "tidak tersedia", jangan mengarang.
5. `mcp_paper_tulis_catatan_harian(ringkasan_psikologi, jejak_grafik, reaksi_berita="tidak tersedia", rezim)`:
   2–4 kalimat: siapa yang dominan, siapa yang terjebak, apa yang berubah dari kemarin.
6. Maksimal 3 `mcp_paper_tulis_hipotesis`: `pola` dari daftar tool, `kondisi` terukur (angka, simbol, tf),
   `prediksi` terukur (mis. "candle 4H turun ≥ 2×ATR dalam 72 jam"), `batas_hari` 1–7. Hipotesis dinilai skrip, bukan saya.
7. `mcp_paper_usul_pelajaran` hanya jika satu pola berulang ≥ 3 kali di jurnal/riwayat dengan hasil konsisten.
   Status `uji`; bukan aturan sebelum disetujui pemilik.
8. Balasan Telegram ≤ 20 baris: hasil hari ini (jumlah tiket, TP/HANGUS/TIDAK_TERISI, net), biaya API vs cap,
   pelajaran singkat, hipotesis baru (ID), hal yang perlu pemilik putuskan.

## Jebakan
- Jangan menyimpulkan "strategi bekerja/tidak" dari < 10 sampel; sebut jumlah sampel.
- Jangan menulis hipotesis yang tidak bisa salah ("pasar akan volatil").
- Jika proxy menunjukkan biaya hari ini > 70% cap, sebutkan sebagai risiko.
