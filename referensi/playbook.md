# Playbook Trading

Versi: 2026-10-11 (v1) · Aturan aktif: 8 / maks 25 · Status diubah **hanya oleh pemilik** (`uji` → `aktif` / `pensiun`).

Agent membaca file ini lewat `mcp_paper_baca_memori("playbook")` pada skill `tiket`/`cek`: aturan `aktif` wajib dipatuhi
(melanggar → SKIP), aturan `uji` dipertimbangkan dan pelanggarannya dicatat di jurnal (`aturan_dilanggar=P-xx`).
Statistik per aturan (tag di jurnal) menentukan kenaikan `uji` → `aktif` atau `pensiun` (§15.6 langkah 5).

## Aliran yang dipakai: price action + psikologi pasar
- Arah: struktur 15m/1h (HH/HL naik, LH/LL turun, selain itu range); konteks 4h/1d dari `ohlcv`.
- Entry: limit di level dengan ≥ 2 sentuhan, pada penolakan yang jelas (WICK, BREAKOUT_GAGAL) atau pullback searah tren.
- Psikologi: setiap setup menjawab "siapa yang terjebak, dan di mana mereka terpaksa keluar?" (panel psikologi + jejak grafik).
- Indikator hanya konteks (EMA-50, ATR, funding, OI); bukan pemicu entry.
- Yang TIDAK dipakai: sinyal grup/influencer, averaging down, market order mengejar harga, rencana tanpa stop/invalidasi.

## Aturan

Kategori: risiko · psikologi · price action · proses · fundamental. Sumber `mesin` = ditegakkan `paper_engine`/pemindai;
`skill tiket` = diperiksa agent di skill; buku = `slug bab NN hal.` (halaman PDF).

| ID | Aturan | Kategori | Sumber | Status | Sejak |
|---|---|---|---|---|---|
| P-01 | Tiket: margin + fee masuk ≤ $1 per hari WIB; tidak ada tiket baru setelah 22:30, semua ditutup 23:50 | risiko | mesin (`BUDGET_TIKET`, `TIKET_EOD`) | aktif | 2026-10-11 |
| P-02 | Tiket: leverage dipilih agar jarak likuidasi ≥ 2×ATR 5m; tidak menaikkan leverage demi muat budget | risiko | mesin + skill tiket | aktif | 2026-10-11 |
| P-03 | Entry hanya limit di/dekat level ≥ 2 sentuhan, searah tren 15m atau pada penolakan jelas (WICK/BREAKOUT_GAGAL); tanpa market order kecuali pemilik minta | price action | skill tiket | aktif | 2026-10-11 |
| P-04 | Setiap order punya TP; tiket: TP ≤ 1,5×ATR 15m dan untung bersih ≥ 3× fee bolak-balik; level invalidasi disebut sebelum order | proses | skill tiket | aktif | 2026-10-11 |
| P-05 | Swing: margin $10/trade, maks 2 posisi, wajib SL & TP, R:R setelah fee ≥ 2,5, likuidasi di luar SL + buffer | risiko | mesin (`RR_TOO_LOW`, `SWING_NEEDS_SL_TP`) | aktif | 2026-10-11 |
| P-06 | Tidak entry bila flag SUDAH_LARI (perubahan 24 jam > 20%) atau FUNDING_EKSTREM melawan arah; tidak mengejar harga yang sudah lewat level (`LIMIT_CROSSES` = SKIP) | price action | skill tiket; mastering-trading-psychology bab 10 hal. 305 ("Chasing stocks is a deadly unforgivable sin") | aktif | 2026-10-11 |
| P-07 | Setiap keputusan (termasuk SKIP) ditulis di jurnal dengan rencana, alasan, dan `aturan_dilanggar`; hasil hanya ditulis mesin | proses | skill tiket; mastering-trading-psychology bab 11 hal. 350–351 (recap trade rugi) | aktif | 2026-10-11 |
| P-08 | Tidak pernah menambah posisi yang sedang rugi (averaging down); tidak mengubah tiket menjadi swing | risiko | mastering-trading-psychology bab 08 hal. 158, bab 13 hal. 379 ("They never add to a losing trade... EVER."), bab 14 hal. 404 | aktif | 2026-10-11 |
| P-09 | Setelah 2 tiket HANGUS beruntun di hari yang sama, tidak ada tiket baru sampai hari berikutnya | psikologi | mastering-trading-psychology bab 05 hal. 16–17, bab 07 hal. 140 ("no trade or 1 trade challenge tomorrow") | uji | 2026-10-11 |
| P-10 | Hari setelah hari dengan net tiket ≤ −$0,80: maksimal 1 tiket | psikologi | mastering-trading-psychology bab 07 hal. 140 | uji | 2026-10-11 |
| P-11 | Sebelum entry, tulis R:R eksplisit (untung bersih vs rugi hangus); tidak bisa ditentukan = FOMO = SKIP | proses | mastering-trading-psychology bab 08 hal. 213 ("What is my risk to reward in this trade?"), bab 09 hal. 253 | uji | 2026-10-11 |
| P-12 | Tidak entry pada 15 menit pertama setelah candle 1h yang bodinya > 2×ATR (impuls); tunggu pullback pertama | price action | mastering-trading-psychology bab 14 hal. 406 ("before a pattern has either formed or been confirmed"); pemindai flag IMPULS | uji | 2026-10-11 |
| P-13 | Jangan SHORT di level yang berulang kali di-buy back (≥ 3 WICK bawah/BREAKOUT_GAGAL bawah di 5m dalam 1 jam) dan sebaliknya | price action | mastering-trading-psychology bab 09 hal. 251 (hammer doji berulang) | uji | 2026-10-11 |
| P-14 | Evaluasi strategi hanya dengan expectancy dari ≥ 30 tiket sejenis (per pola/`plan_id`), bukan P&L harian | proses | mastering-trading-psychology bab 06 hal. 77–78 ("You perhaps will need 30 trades"); `statistik_lulus` | uji | 2026-10-11 |
| P-15 | Pola chart dinyatakan hanya setelah breakout dikonfirmasi close (bukan wick) dan volume; target = tinggi pola dari titik breakout | price action | goodcrypto-pola-chart bab 02 hal. 3–6, bab 03 hal. 12 | uji | 2026-10-11 |
| P-16 | Koin kecil masuk watchlist tiket hanya jika lolos cek cepat: bukan MLM/Ponzi, tidak berlabel scam, bukan listing < 30 hari (flag BARU) | fundamental | panduan-analisis-crypto bab 08 hal. 19 ("Stay away from MLM-based coins."); flag BARU pemindai | uji | 2026-10-11 |
| P-17 | Tiket harian diperlakukan sebagai proses: tujuan harian = patuh aturan (tag di jurnal), bukan nominal; target per hari ≤ 1 trade bagus | psikologi | mastering-trading-psychology bab 12 hal. 357, 364; bab 10 hal. 298–302 ("your P&L is not a signal") | uji | 2026-10-11 |

Status: `uji` (baru, sedang diuji) · `aktif` (wajib; terbukti membantu / ditegakkan mesin) · `pensiun` (dihapus, alasan dicatat).

## Usulan yang sengaja tidak dimasukkan
- Risiko ≤ 2% ekuitas, max loss harian 1% / mingguan 3% (bab 08, 09, 12): sudah terwakili oleh budget tiket $1/hari dan swing $10/trade.
- Sembunyikan P&L unrealized (bab 06, 10): agent membaca `unrealized` dari tool hanya untuk laporan, bukan keputusan — dicakup P-17.
- Aturan gaya hidup (tidur, kafein — bab 13): untuk pemilik, bukan agent.
- Checklist fundamental lengkap (white paper, roadmap, tim — panduan bab 05–07): relevan untuk swing/investasi, belum untuk tiket intraday.

## Catatan perubahan
- 2026-10-11: versi awal (v1) dari aturan yang sudah ditegakkan mesin/skill + usulan dari 3 buku hasil konversi.
