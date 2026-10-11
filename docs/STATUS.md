# STATUS — keadaan proyek sekarang

> Baca file ini dulu saat memulai sesi di perangkat mana pun. Perbarui setiap kali ada perubahan.
> Riwayat perubahan: `docs/CHANGELOG.md`. Spesifikasi: `docs/rencana-asisten-crypto.md`. Operasi: `docs/OPERASI.md`.

Diperbarui: 2026-10-11 16:50 WIB (perangkat: laptop Windows "laptop-l5i0361r")

## Arsitektur (sejak 11 Okt siang)

Otak asisten = **Hermes Agent v0.21.6** native Windows (Telegram + CLI). Claude Code hanya membangun proyek.
```
Folder Startup user (login, tanpa jendela)
 ├─ crypto-analyst_collector.vbs → run_collector.cmd     data pasar + mesin paper            (JALAN)
 ├─ crypto-analyst_proxy.vbs     → run_budget_proxy.cmd  127.0.0.1:8585 → Anthropic, cap $10/hari (JALAN, key_set)
 └─ Hermes_Gateway.vbs           → Hermes gateway        Telegram + cron
      ├─ MCP "paper"               scripts/mcp_server.py, 22 tool  (TERHUBUNG, hermes mcp test paper OK)
      ├─ cron pemindai-tiket       1-59/5 * * * * → pemindai_cron.py → scripts/pemindai.py --cron (tanpa LLM);
      │                            agent (Opus 5.5, low) hanya dibangunkan bila baris terakhir {"wakeAgent": true}
      └─ cron evaluasi-harian      23:55 WIB → skill evaluasi-harian → Telegram
```
Pemindai menulis `data/kandidat.sqlite` (penulis tunggal); collector kini juga mengisi `kline_1h` (120 hari) untuk konteks 1h/4h/1d.

## Milestone

| Milestone | Isi | Status |
|---|---|---|
| 1 | Mesin paper trading: collector, paper_engine, budget_guard, 43 tes | **Selesai**, live |
| 2a | Hermes: budget_proxy, analisis, mcp_server (22 tool), SOUL + skill `tiket` + `sync.py` + `setup_hermes.cmd`, docs | **Selesai & terverifikasi** (`hermes -z` menjawab lewat tool MCP; biaya tercatat). Sisa: uji dari Telegram oleh user |
| 2b | `pemindai.py` + `kandidat.sqlite`, `kline_1h` di collector, 2 cron job (`pemindai-tiket`, `evaluasi-harian`) | **Selesai & terpasang** (91 tes; cron `pemindai-tiket` f27a23cad20c dan `evaluasi-harian` d38d3262d1b5 aktif; nol biaya terverifikasi) |
| 3 | Baseline acak, kriteria lulus §19.7, memori pasar lengkap (§16), referensi buku (§15) | Belum mulai |

## Yang harus dilakukan user

1. Uji Telegram pertama **lolos** (posisi/order benar, shell ditolak, `/cek SOL LONG` → SKIP beralasan + jurnal).
   Berikutnya: tutup-buka chat bot, cek menu `/` berisi 14 perintah proyek, coba `/posisi`, `/budget`, `/status`;
   laporkan apakah tebal/daftar sudah dirender.
1b. Order tiket uji #1 (BTC) dan #2 (ETH) menahan gate pemindai ("sudah 2 order tiket hidup"). Kalau ingin pemindai
   benar-benar membangunkan agent hari ini: `/batal semua` di Telegram atau `paper_engine.py batal 1` + `batal 2`.
   Lalu amati Telegram: pesan "PEMINDAI … K<id> …" + keputusan agent hanya saat ada kandidat; 23:55 evaluasi harian.
2. Opsional: pasang spend limit di workspace Console Anthropic; `hermes doctor --fix` untuk saran `custom_providers → providers`;
   sembunyikan skill bundel Hermes yang tidak dipakai dengan mengganti nama folder di `%LOCALAPPDATA%\hermes\skills\` menjadi `_nama`.

## Yang sedang berjalan

- Collector, proxy, dan gateway Hermes jalan di luar sandbox (launcher Startup). Cek: `collector.py status`,
  `curl 127.0.0.1:8585/healthz`, `hermes gateway status`.
- Order paper uji 11 Okt 11:42 WIB: #1 tiket BTC LONG 150x @ 82.915,7; #2 tiket ETH LONG 100x @ 2.431,1 (jauh);
  #3 swing ETH SHORT 10x @ 2.511,3. Status: `paper_engine.py laporan`.
- Cron Hermes aktif sejak 16:43 WIB: `pemindai-tiket` tiap 5 menit (`1-59/5`), `evaluasi-harian` 23:55. `hermes cron list`.
- Collector skema v2: `kline_1h` 20 simbol × 120 hari (57.620 bar) terisi dalam 4 tick; weight tick kembali ±91.
- Biaya API hari ini: ≈ $0,75 (16 panggilan uji Telegram/CLI). Laporan: `budget_guard.py laporan`.

## Verifikasi

| # | Item | Hasil |
|---|---|---|
| M1 | Unit test T1–T19, B1–B3 | ✅ |
| M1 | Collector live lewat DoH, backfill, pacing | ✅ (weight tick ±90) |
| M1 | Order manual diterima/ditolak dengan kode benar | ✅ |
| M1 | Soak 24 jam, uji tidur laptop, likuidasi vs aplikasi Binance | ⬜ berjalan / user |
| 2a | `test_budget_proxy` P1–P9 (upstream palsu, stream byte-identik, 429 tanpa upstream, kill switch) | ✅ |
| 2a | `test_analisis` A1–A6, `test_mcp_server` M1–M9 (22 tool terdaftar di FastMCP), `test_hermes_sync` H1–H4 | ✅ |
| 2a | `hermes --version` (v0.21.6), `hermes mcp test paper` → 22 tool, `config.yaml` tergabung (toolset tanpa terminal/file) | ✅ |
| 2a | `/healthz` ok + `key_set`; `hermes -z` menjawab jam/umur tick/budget lewat tool MCP; proxy mencatat 2 panggilan $0,0955 | ✅ |
| 2a | Kill switch `data/STOP_AGENT` → Hermes ditolak 403 tanpa biaya (`hermes -z` melapor langsung, proxy `TOLAK`) | ✅ |
| 2a | Telegram: posisi/order; pasang tiket → `created_by=hermes`; "jalankan shell" → tidak punya tool | ✅ (user, 11 Okt) |
| 2b | `test_pemindai` S1–S10, `test_collector_1h` C1–C3, M8 `plan_id`, M10 `ohlcv` 1h/4h/1d, `kline_limit` 1h | ✅ 91 tes |
| 2b | `pemindai.py --once` data nyata: 20 simbol, tabel per simbol, kandidat UNI/XRP, gate line ASCII | ✅ |
| 2b | Collector restart dengan skema v2 → `collector.py status`: `Bar 1h: 20 simbol, 57620 bar, 13 Jun → 11 Okt`; weight tick 282 → 191 → 91 | ✅ |
| 2b | `hermes cron list` memuat `pemindai-tiket` (1-59/5) & `evaluasi-harian` (55 23); `hermes cron run pemindai-tiket` → `pemindai_run` wake=0 "sudah 2 order tiket hidup", `api_calls` tetap 16 | ✅ |
| 2b | Scheduler gateway menjalankan `pemindai-tiket` sendiri: run 16:46:25 WIB tercatat di `pemindai_run` (wake=0), `api_calls` tetap 16 | ✅ |
| 2b | Jalur positif: wake alami → order `plan_id=K<id>` / SKIP + jurnal; 23:55 evaluasi harian tiba; apakah gate-off sampai ke Telegram | ⬜ menunggu kejadian / user |

## Keputusan yang berlaku

- Jaringan rumah memblokir DNS Binance → DoH di dalam skrip; DNS Windows tidak diubah.
- Budget tiket `margin + fee masuk ≤ $1`/hari WIB; order tiket kedaluwarsa & posisi ditutup paksa 23:50 WIB; tidak ada tiket baru setelah 22:30.
- Ambiguitas intrabar pesimis (liq → SL → TP), ditandai `ambiguous`.
- Budget API: $10/hari, $190/bulan, $1/panggilan, ditegakkan `budget_proxy.py`; kill switch `data/STOP_AGENT`.
- Model agent: `claude-opus-5-5`, effort `low`; pemindai mekanis (tanpa LLM) membangunkan agent hanya bila ada kandidat.
- Pemindai: jadwal `1-59/5` (bar 1m tersimpan detik :05), `data_until` dari bar tersimpan (bukan jam dinding), gate G1–G8,
  skor ≥ 3, jarak liq ≥ 2×ATR 5m, cooldown 30 menit per simbol, maks 12 wake/hari, jam 07:00–22:30 WIB. Knob: `PemindaiConfig`.
- `kandidat_terbaru` = run terakhir yang membangunkan agent; `plan_id` order tiket = `K<id>` dari kandidat (`MANUAL` bila dari pemilik).
- Agent hanya lewat MCP (22 tool whitelist); toolset terminal/file/browser dimatikan di cron, telegram, cli.
- `mcp==1.30.0` (FastMCP). Hermes diinstal dari terminal user, bukan dari Claude Code.
- Di laptop ini, proses dari Claude Code tervirtualisasi (MSIX): yang menyentuh `%LOCALAPPDATA%\hermes`, Startup, atau
  perintah `hermes` dijalankan lewat `explorer.exe "<path>\hermes\setup_hermes.cmd"` / `run_logged.cmd` (lihat OPERASI).
- Proxy menolak budget habis / kill switch dengan 403 (bukan 429) agar SDK tidak mengulang.
- `hermes cron create --script` harus path **relatif** terhadap `HERMES_HOME\scripts` (`pemindai_cron.py`); path absolut ditolak.
- Repo GitHub `rafcnzo/ai-trade-assistant`; `data/`, `logs/`, `jurnal/`, `laporan/`, `pasar/harian`, `pasar/komunitas`, `referensi/buku/` tidak di-commit.

## Pertanyaan terbuka

- Apakah Hermes mengirim stdout skrip cron ke Telegram saat `{"wakeAgent": false}` (tiap 5 menit dua baris)? Jika ya,
  kecilkan output gate-off menjadi satu baris atau pakai `--deliver` lain. Dicek setelah cron terpasang.
- `platform_toolsets.cron` dan nama tool `mcp_paper_*` sudah terkonfirmasi bekerja (Telegram/CLI); untuk cron dikonfirmasi
  saat wake pertama.
