@echo off
rem Tujuh cron job Hermes untuk crypto-analyst. Dicetak oleh hermes/sync.py --snippet.
rem --script harus path RELATIF terhadap HERMES_HOME\scripts (Hermes menolak path absolut).
rem Jalankan sekali setelah `hermes gateway install`. Cek: hermes cron list

hermes cron create "1-59/5 * * * *" "Pemindai mekanis baru saja menemukan kandidat tiket; ringkasannya dengan ID K<id> dan baris Akun aktif ada di pesan ini. Jalankan skill ARENA: (1) mcp_paper_kandidat_terbaru(limit=5), nilai HANYA kandidat yang ID-nya disebut; (2) fakta sekali lewat tool mcp_paper_* (waktu_sekarang, budget_tiket, harga, ohlcv 15m lalu 5m, panel_psikologi, tabel_tiket dengan entry = level); (3) untuk SETIAP persona di baris Akun aktif (tiket, fade, breakout, rentang) uji syarat masuknya; lolos → pasang order paper di akun persona itu dengan plan_id persis K<id>, tidak lolos → SKIP; maks 1 order per persona per wake; (4) mcp_paper_tulis_jurnal per persona per kandidat dengan judul [persona] K<id> ...; (5) kandidat kosong atau status_data BASI → jawab satu baris dan berhenti. Balas ringkas untuk Telegram (maks 14 baris). Ini paper trading; jangan menyarankan beli/jual uang sungguhan." --name pemindai-tiket --skill arena --script pemindai_cron.py --deliver telegram --model claude-opus-5-5 --reasoning-effort low

hermes cron create "30 21 * * *" "Jalankan skill evaluasi-harian untuk hari ini (WIB) pukul 21:30: laporan paper, biaya API, catatan harian, maksimal 3 hipotesis terukur, usulan pelajaran bila ada pola berulang. Posisi yang ditutup setelah 21:30 (termasuk EOD 23:50) masuk evaluasi besok: awali dengan hasil EOD kemarin bila ada. Balas ringkas untuk Telegram (maks 20 baris)." --name evaluasi-harian --skill evaluasi-harian --deliver telegram --model claude-opus-5-5 --reasoning-effort low

hermes cron create "* * * * *" --name notif-paper --no-agent --script notif_cron.py --deliver telegram --failure-deliver local

hermes cron create "15 21 * * *" --name uji-hipotesis --no-agent --script uji_cron.py --deliver telegram --failure-deliver local

hermes cron create "7 * * * *" --name psikologi --no-agent --script psikologi_cron.py --deliver telegram --failure-deliver local

hermes cron create "20 8-21/3 * * *" "Pesan ini dari gate evaluasi susulan: evaluasi harian untuk tanggal yang disebut belum dibuat karena laptop mati pukul 21:30. Jalankan skill evaluasi-harian untuk TANGGAL ITU (bukan hari ini): pakai parameter hari pada laporan_paper, riwayat, biaya_api, baca_memori jurnal, dan tulis_catatan_harian(hari=...). Awali balasan dengan 'Evaluasi susulan <tanggal>'. Ringkas untuk Telegram (maks 20 baris). Paper trading." --name evaluasi-susulan --skill evaluasi-harian --script susulan_cron.py --deliver telegram --model claude-opus-5-5 --reasoning-effort low

hermes cron create "30 7 * * 1" --name nilai-arena --no-agent --script arena_cron.py --deliver telegram --failure-deliver local
