# STATUS — keadaan proyek sekarang

> Baca file ini dulu saat memulai sesi di perangkat mana pun. Perbarui setiap kali ada perubahan.
> Riwayat perubahan: `docs/CHANGELOG.md`. Spesifikasi: `docs/rencana-asisten-crypto.md`. Operasi: `docs/OPERASI.md`.

Diperbarui: 2026-10-11 17:45 WIB (perangkat: laptop Windows "laptop-l5i0361r")

## Arsitektur (sejak 11 Okt siang)

Otak asisten = **Hermes Agent v0.21.6** native Windows (Telegram + CLI). Claude Code hanya membangun proyek.
```
Folder Startup user (login, tanpa jendela)
 ├─ crypto-analyst_collector.vbs → run_collector.cmd     data pasar + mesin paper            (JALAN)
 ├─ crypto-analyst_proxy.vbs     → run_budget_proxy.cmd  127.0.0.1:8585 → Anthropic, cap $10/hari (JALAN, key_set)
 └─ Hermes_Gateway.vbs           → Hermes gateway        Telegram + cron
      ├─ MCP "paper"               scripts/mcp_server.py, 23 tool  (+statistik_lulus; tulis_hipotesis terstruktur)
      ├─ cron pemindai-tiket       1-59/5 * * * * → pemindai_cron.py → scripts/pemindai.py --cron (tanpa LLM);
      │                            agent (Opus 5.5, low) hanya dibangunkan bila baris terakhir {"wakeAgent": true}
      ├─ cron evaluasi-harian      23:55 WIB → skill evaluasi-harian → Telegram
      ├─ cron notif-paper          * * * * * --no-agent → notif_cron.py → scripts/notifikasi.py --cron (tanpa LLM):
      │                            kejadian paper (terisi/TP/STOP/likuidasi/kedaluwarsa/batal) → Telegram, kosong = diam
      └─ cron uji-hipotesis        40 23 * * * --no-agent → uji_cron.py → scripts/uji_hipotesis.py --cron (tanpa LLM):
                                   nilai hipotesis jatuh tempo + baseline + pelajaran → Telegram bila ada hasil
```
Mesin paper v2: setiap order tiket agent mendapat bayangan acak di akun `acak` (pembanding §19.7, dibuat mesin, tidak dinotifikasi).
Pemindai menulis `data/kandidat.sqlite` (penulis tunggal); collector kini juga mengisi `kline_1h` (120 hari) untuk konteks 1h/4h/1d.

## Milestone

| Milestone | Isi | Status |
|---|---|---|
| 1 | Mesin paper trading: collector, paper_engine, budget_guard, 43 tes | **Selesai**, live |
| 2a | Hermes: budget_proxy, analisis, mcp_server (22 tool), SOUL + skill `tiket` + `sync.py` + `setup_hermes.cmd`, docs | **Selesai & terverifikasi** (`hermes -z` menjawab lewat tool MCP; biaya tercatat). Sisa: uji dari Telegram oleh user |
| 2b | `pemindai.py` + `kandidat.sqlite`, `kline_1h` di collector, 2 cron job (`pemindai-tiket`, `evaluasi-harian`) | **Selesai & terpasang** (91 tes; cron `pemindai-tiket` f27a23cad20c dan `evaluasi-harian` d38d3262d1b5 aktif; nol biaya terverifikasi) |
| 3a | Baseline acak (akun `acak`), statistik kelulusan (`evaluasi.py` + tool `statistik_lulus`), hipotesis terstruktur dinilai skrip (`hipotesis.py`, `uji_hipotesis.py`, cron 23:40) | **Selesai & terpasang** (109 tes; cron `uji-hipotesis` f497508f3dd4 aktif, MCP 23 tool, collector skema v2) |
| 3b | Panel psikologi pasar harian (§16.2) | Belum mulai |
| 3c | Referensi buku & playbook (§15) — menunggu ebook | Belum mulai |

## Yang harus dilakukan user

1. Uji Telegram pertama **lolos** (posisi/order benar, shell ditolak, `/cek SOL LONG` → SKIP beralasan + jurnal).
   Berikutnya: tutup-buka chat bot, cek menu `/` berisi 14 perintah proyek, coba `/posisi`, `/budget`, `/status`;
   laporkan apakah tebal/daftar sudah dirender.
1b. Amati Telegram: keputusan agent hanya saat pemindai menemukan kandidat (order uji #1/#2 sudah dibatalkan 17:05 WIB,
   gate G4 terbuka); notifikasi 📣 saat ada kejadian paper; 23:55 evaluasi harian.
2. Opsional: pasang spend limit di workspace Console Anthropic; `hermes doctor --fix` untuk saran `custom_providers → providers`;
   sembunyikan skill bundel Hermes yang tidak dipakai dengan mengganti nama folder di `%LOCALAPPDATA%\hermes\skills\` menjadi `_nama`.

## Yang sedang berjalan

- Collector, proxy, dan gateway Hermes jalan di luar sandbox (launcher Startup). Cek: `collector.py status`,
  `curl 127.0.0.1:8585/healthz`, `hermes gateway status`.
- Order paper uji #1/#2 (tiket) dibatalkan 16:50 WIB atas permintaan user; #3 swing ETH SHORT 10x @ 2.511,3 masih ACTIVE.
- **Posisi tiket pertama dari agent sendiri**: #1 SOLUSDT SHORT 0,67 @ 109,41 75x (K3), liq 110,317, TP 109,14 (order #8),
  terisi 16:53 WIB. Hasilnya menentukan budget tiket hari ini. Status: `paper_engine.py posisi` / `/posisi` di Telegram.
- Cron Hermes aktif sejak 16:43 WIB: `pemindai-tiket` tiap 5 menit (`1-59/5`), `evaluasi-harian` 23:55. `hermes cron list`.
- Collector skema v2: `kline_1h` 20 simbol × 120 hari (57.620 bar) terisi dalam 4 tick; weight tick kembali ±91.
- Biaya API hari ini: ≈ $1,62 (25 panggilan: uji Telegram/CLI + wake pemindai pertama). Laporan: `budget_guard.py laporan`.

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
| 2b | Gate off tidak mengirim apa pun ke Telegram: `cron/executions.db` `delivery_outcome=suppressed`, output run "Script gate returned wakeAgent=false — agent skipped" | ✅ |
| 2b | Jalur positif 16:51 WIB: pemindai bangun dengan 3 kandidat (K1 XRP SHORT, K2 BTC LONG, K3 SOL SHORT, skor 3); agent memasang order #7 SOL SHORT 75x @ 109,41 TP 109,14 `plan_id=K3` (persis), SKIP K1/K2 dengan alasan di jurnal; 2 panggilan Opus ≈ $0,30; order terisi 16:53 → posisi #1 | ✅ |
| 2b | 23:55 evaluasi harian tiba di Telegram | ⬜ menunggu |
| 2b+ | `test_notifikasi` N1–N3 (init sunyi, order/terisi/TP, batal/kedaluwarsa, likuidasi, batas 20, CLI), `test_hermes_sync` H5 | ✅ |
| 2b+ | Cron `notif-paper` 4c19f528cc31 terdaftar (mode no-agent); `hermes cron run notif-paper` 17:01 WIB mengirim 2 kejadian (#6 order SOL, #7 terisi) → `delivery_outcome=delivered`, kursor #7; tanpa panggilan API | ✅ |
| 3a | `test_paper_engine` T20–T23 (bayangan acak: dibuat, terisi+TP relatif+EOD, dilewati tanpa merusak order asli, deterministik/ACAK_EOD), `test_evaluasi` E1–E3, `test_uji_hipotesis` U1–U5, `test_mcp_server` M11 + M9 (23 tool), `test_notifikasi` N4 | ✅ 109 tes |
| 3a | Collector dimulai ulang 17:35 WIB dengan skema paper v2; `paper_engine.py budget` menampilkan tiket/swing/acak; tick normal (weight 91) | ✅ |
| 3a | Cron `uji-hipotesis` f497508f3dd4 (40 23, no-agent) terdaftar; gateway restart PID 16660; `hermes mcp test paper` → 23 tool; `hermes cron run uji-hipotesis` → 0 dinilai, `delivery_outcome=suppressed`, `api_calls` tetap 29 | ✅ |
| 3a | Jalur positif: order tiket agent berikutnya menghasilkan baris `acak` `ACAK:<id>`; `evaluasi.py` berjalan pada data nyata; agent menulis hipotesis terstruktur via Telegram | ⬜ menunggu kejadian |

## Keputusan yang berlaku

- Jaringan rumah memblokir DNS Binance → DoH di dalam skrip; DNS Windows tidak diubah.
- Budget tiket `margin + fee masuk ≤ $1`/hari WIB; order tiket kedaluwarsa & posisi ditutup paksa 23:50 WIB; tidak ada tiket baru setelah 22:30.
- Ambiguitas intrabar pesimis (liq → SL → TP), ditandai `ambiguous`.
- Budget API: $10/hari, $190/bulan, $1/panggilan, ditegakkan `budget_proxy.py`; kill switch `data/STOP_AGENT`.
- Model agent: `claude-opus-5-5`, effort `low`; pemindai mekanis (tanpa LLM) membangunkan agent hanya bila ada kandidat.
- Pemindai: jadwal `1-59/5` (bar 1m tersimpan detik :05), `data_until` dari bar tersimpan (bukan jam dinding), gate G1–G8,
  skor ≥ 3, jarak liq ≥ 2×ATR 5m, cooldown 30 menit per simbol, maks 12 wake/hari, jam 07:00–22:30 WIB. Knob: `PemindaiConfig`.
- `kandidat_terbaru` = run terakhir yang membangunkan agent; `plan_id` order tiket = `K<id>` dari kandidat (`MANUAL` bila dari pemilik).
- Agent hanya lewat MCP (23 tool whitelist); toolset terminal/file/browser dimatikan di cron, telegram, cli.
- `mcp==1.30.0` (FastMCP). Hermes diinstal dari terminal user, bukan dari Claude Code.
- Di laptop ini, proses dari Claude Code tervirtualisasi (MSIX): yang menyentuh `%LOCALAPPDATA%\hermes`, Startup, atau
  perintah `hermes` dijalankan lewat `explorer.exe "<path>\hermes\setup_hermes.cmd"` / `run_logged.cmd` (lihat OPERASI).
- Proxy menolak budget habis / kill switch dengan 403 (bukan 429) agar SDK tidak mengulang.
- `hermes cron create --script` harus path **relatif** terhadap `HERMES_HOME\scripts` (`pemindai_cron.py`); path absolut ditolak.
- Baseline acak = bayangan per order tiket (sisi acak `Random("acak-v1:<id>")`, entry market bar berikutnya, TP/SL jarak sama, budget
  cermin $1/hari); dibuat di dalam `PaperEngine.place_order` (satu penulis), tidak dinotifikasi ke Telegram.
- Hipotesis harus terstruktur (`jenis` sentuh_harga|gerak_atr|close_arah, tf, arah, nilai, batas 1–7 hari); dinilai `uji_hipotesis.py`
  dengan baseline 200 titik acak/120 hari; pelajaran naik/pensiun otomatis (§16.6). Kepemilikan file: `hipotesis.jsonl` ← mcp_server;
  `hipotesis-hasil.jsonl`, `hipotesis.md`, `pelajaran.{jsonl,md}` ← uji_hipotesis.py. `pelajaran-usulan.md` hanya diputuskan pemilik.
- Notifikasi kejadian paper memakai cron Hermes `--no-agent` (stdout = pesan, kosong = diam), bukan Bot API langsung:
  token Telegram tetap hanya di Hermes, nol biaya LLM. Kursor `data/notif.json` (penulis tunggal `notifikasi.py`).
- Run cron dengan `{"wakeAgent": false}` tidak dikirim ke Telegram (`delivery_outcome=suppressed`). Jejak run:
  `%LOCALAPPDATA%\hermes\cron\output\<job_id>\<waktu>.md` dan `cron\executions.db`.
- Repo GitHub `rafcnzo/ai-trade-assistant`; `data/`, `logs/`, `jurnal/`, `laporan/`, `pasar/harian`, `pasar/komunitas`, `referensi/buku/` tidak di-commit.

## Pertanyaan terbuka

- Biaya per wake: panggilan kedua pada wake 16:51 berbiaya $0,27 (cache write prompt sistem baru setelah gateway restart);
  wake berikutnya seharusnya ±$0,05–0,10 bila cache hangat. Pantau `budget_guard.py laporan` beberapa hari.
- Kandidat skor 3 semuanya "DEKAT_LEVEL + VOL" (tanpa penolakan segar). Setelah ada data beberapa hari, pertimbangkan
  `score_min=4` atau bobot VOL lebih kecil supaya wake lebih selektif.
