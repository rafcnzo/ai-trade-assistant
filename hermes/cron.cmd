@echo off
rem Dua cron job Hermes untuk crypto-analyst. Dicetak dengan path nyata oleh hermes/sync.py.
rem Jalankan sekali setelah `hermes gateway install`. Cek: hermes cron list

hermes cron create "*/5 * * * *" "Pemindai mekanis baru saja menemukan kandidat tiket (ringkasannya ada di pesan ini). Jalankan skill tiket: ambil kandidat lewat mcp_paper_kandidat_terbaru, periksa fakta lewat tool mcp_paper_*, lalu untuk setiap kandidat putuskan: pasang order paper bersyarat (akun tiket, limit, TP, leverage dari tabel_tiket, plan_id=K<id>) atau lewati dengan alasan. Catat setiap keputusan dengan mcp_paper_tulis_jurnal. Balas ringkas untuk Telegram (maks 12 baris). Ini paper trading; jangan menyarankan beli/jual uang sungguhan." --name pemindai-tiket --skill tiket --script "{{HERMES_HOME}}\scripts\pemindai_cron.py" --deliver telegram --model claude-opus-5-5 --reasoning-effort low

hermes cron create "55 23 * * *" "Jalankan skill evaluasi-harian untuk hari ini (WIB): laporan paper, biaya API, catatan harian, maksimal 3 hipotesis terukur, usulan pelajaran bila ada pola berulang. Balas ringkas untuk Telegram (maks 20 baris)." --name evaluasi-harian --skill evaluasi-harian --deliver telegram --model claude-opus-5-5 --reasoning-effort low
