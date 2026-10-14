# STATUS — keadaan proyek sekarang

> Baca file ini dulu saat memulai sesi di perangkat mana pun. Perbarui setiap kali ada perubahan.
> Riwayat perubahan: `docs/CHANGELOG.md`. Spesifikasi: `docs/rencana-asisten-crypto.md`. Operasi: `docs/OPERASI.md`.

Diperbarui: 2026-10-14 14:40 WIB (perangkat: laptop Windows "laptop-l5i0361r")

## Arsitektur (sejak 11 Okt siang)

Otak asisten = **Hermes Agent v0.21.6** native Windows (Telegram + CLI). Claude Code hanya membangun proyek.
```
Folder Startup user (login, tanpa jendela)
 ├─ crypto-analyst_collector.vbs → run_collector.cmd     data pasar + mesin paper            (JALAN)
 ├─ crypto-analyst_proxy.vbs     → run_budget_proxy.cmd  127.0.0.1:8585 → Anthropic, cap $10/hari (JALAN, key_set)
 ├─ crypto-analyst_dashboard.vbs → run_dashboard.cmd     http://127.0.0.1:8586 dashboard baca-saja (chart + riwayat) (JALAN)
 └─ Hermes_Gateway.vbs           → Hermes gateway        Telegram + cron
      ├─ MCP "paper"               scripts/mcp_server.py, 29 tool  (+statistik_lulus, panel_psikologi, cari/baca_referensi, autopsi_posisi, papan_arena, tambah_jatah_radar)
      ├─ cron pemindai-tiket       1-59/5 * * * * → pemindai_cron.py → scripts/pemindai.py --cron (tanpa LLM) → skill ARENA (4 persona);
      │                            agent (Opus 5.5, low) hanya dibangunkan bila baris terakhir {"wakeAgent": true}
      ├─ cron evaluasi-harian      23:55 WIB → skill evaluasi-harian → Telegram
      ├─ cron notif-paper          * * * * * --no-agent → notif_cron.py → scripts/notifikasi.py --cron (tanpa LLM):
      │                            kejadian paper (terisi/TP/STOP/likuidasi/kedaluwarsa/batal) → Telegram, kosong = diam
      ├─ cron uji-hipotesis        40 23 * * * --no-agent → uji_cron.py → scripts/uji_hipotesis.py --cron (tanpa LLM):
      │                            nilai hipotesis jatuh tempo + baseline + pelajaran → Telegram bila ada hasil
      ├─ cron psikologi            7 * * * * --no-agent → psikologi_cron.py → scripts/psikologi.py --cron (diam):
      │                            12 indikator §16.2 BTC/ETH/pasar → data/psikologi.sqlite; agent: panel_psikologi, pemilik: /psikologi
      ├─ cron evaluasi-susulan     20 8-21/3 * * * → susulan_cron.py (gate: pasar/harian/<kemarin>.md belum ada) → evaluasi kemarin
      └─ cron nilai-arena          30 7 * * 1 --no-agent → arena_cron.py → evaluasi.py --nilai-arena (pensiun persona yang kalah)
```
Arena: akun persona `tiket`, `fade`, `breakout`, `rentang` (tabel `account`, saldo $1/hari masing-masing, bayangan acak per order).
Mesin paper v2: setiap order tiket agent mendapat bayangan acak di akun `acak` (pembanding §19.7, dibuat mesin, tidak dinotifikasi).
Pemindai menulis `data/kandidat.sqlite` (penulis tunggal); collector kini juga mengisi `kline_1h` (120 hari) untuk konteks 1h/4h/1d.

## Milestone

| Milestone | Isi | Status |
|---|---|---|
| 1 | Mesin paper trading: collector, paper_engine, budget_guard, 43 tes | **Selesai**, live |
| 2a | Hermes: budget_proxy, analisis, mcp_server (22 tool), SOUL + skill `tiket` + `sync.py` + `setup_hermes.cmd`, docs | **Selesai & terverifikasi** (`hermes -z` menjawab lewat tool MCP; biaya tercatat). Sisa: uji dari Telegram oleh user |
| 2b | `pemindai.py` + `kandidat.sqlite`, `kline_1h` di collector, 2 cron job (`pemindai-tiket`, `evaluasi-harian`) | **Selesai & terpasang** (91 tes; cron `pemindai-tiket` f27a23cad20c dan `evaluasi-harian` d38d3262d1b5 aktif; nol biaya terverifikasi) |
| 3a | Baseline acak (akun `acak`), statistik kelulusan (`evaluasi.py` + tool `statistik_lulus`), hipotesis terstruktur dinilai skrip (`hipotesis.py`, `uji_hipotesis.py`, cron 23:40) | **Selesai & terpasang** (109 tes; cron `uji-hipotesis` f497508f3dd4 aktif, MCP 23 tool, collector skema v2) |
| 3b | Panel psikologi pasar (§16.2): `psikologi.py` + `psikologi.sqlite`, tool `panel_psikologi`, skill `/psikologi`, frontmatter catatan harian, cron tiap jam; pemindai `top_n=30`, `top_k=5` | **Selesai & terpasang** (116 tes; cron `psikologi` 85f32aac4251 aktif, MCP 24 tool, menu `/psikologi`) |
| AR | Arena: 4 persona di akun terpisah (`account.kind=tiket`, status aktif/pensiun), skill `arena` satu sesi untuk semua persona, `papan_arena` (28 tool), `evaluasi.py --arena/--nilai-arena`, cron `nilai-arena` mingguan, dashboard tab Arena, `/arena-papan` | **Selesai & terpasang** (138 tes; cron pemindai → skill arena, nilai-arena mingguan, 28 tool, dashboard tab Arena) |
| RD2 | `/radar <N>`: tool `tambah_jatah_radar` (29 tool) → `data/radar_jatah.json`, pemindai menambah cap hari itu; skill `radar`, menu menggantikan `/usage`; M17, S13 (145 tes) | **Selesai & terpasang** |
| RD | Radar: cap 3 wake/jam (G5) + `score_min` 3 → 4, karena 12 wake harian habis pukul 09:31 dan skor 3 hampir selalu di-SKIP (S12, 143 tes) | **Selesai & terpasang** |
| P19 | Gate R:R minimum tiket di mesin (`tiket_min_rr` 0,5, `RR_TOO_LOW`, playbook P-19 dari U-001); susulan menjalankan uji hipotesis terlewat; evaluasi-harian 21:30 & uji-hipotesis 21:15 (laptop mati malam) | **Selesai & terpasang** (142 tes; T28) |
| D2 | Dashboard "Meja analis" (13 Okt): satu halaman gulir, meja 4 analis + aliran kejadian (`/api/kejadian`), tooltip untuk semua keterangan, Ringkasan (top koin + kecenderungan analis, `/api/ringkas`), palet arang/gading/kuningan; `PRODUCT.md`, `DESIGN.md`, brief `.impeccable/surfaces/`; tes D7 (140) | **Selesai & terpasang** |
| D | Dashboard lokal: chart trading (Lightweight Charts) + marker mesin paper, posisi/order live, riwayat + **trailing drawdown per akun**, rapor, radar, suasana pasar, catatan AI; bahasa awam; autostart | **Selesai & jalan** (128 tes; D1–D5) |
| 3c | Referensi buku & playbook (§15): `konversi_buku.py`, `referensi.py`, tool `cari_referensi`/`baca_referensi`, `/referensi`, `referensi/indeks.md`, `referensi/playbook.md` v1, aturan SOUL "Referensi", playbook di skill tiket | **Selesai & terpasang** (122 tes; 3 buku terkonversi; MCP 26 tool; `/referensi` di menu) |

## Yang harus dilakukan user

0. **Playbook:** buka `referensi/playbook.md`, baca aturan berstatus `uji` (usulan dari buku), ubah ke `aktif` yang Anda setujui
   atau hapus. Hanya Anda yang mengubah status. Tambah ebook lain ke `referensi/buku/` lalu minta konversi + indeks.
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
- 11 Okt: tiket #1 SOL SHORT 75x (K3) HANGUS −$0,99 (diproses saat laptop nyala 12 Okt pagi); swing #3 ETH SHORT terisi → posisi swing #2 terbuka.
- Laptop mati 11 Okt ±22:03 → evaluasi 23:55 tidak jalan; mekanisme `evaluasi-susulan` ditambahkan 12 Okt.
- Autopsi SOL #1: 89% jalan ke TP dalam 47 menit (109,17 vs TP 109,14), kembali ke entry 18:08, chop 4 jam, hangus 22:40 oleh
  impuls pasar. Tindak lanjut: P-18 pengaman breakeven (mesin) + tool `autopsi_posisi` wajib di evaluasi harian.
- **Posisi tiket pertama dari agent sendiri**: #1 SOLUSDT SHORT 0,67 @ 109,41 75x (K3), liq 110,317, TP 109,14 (order #8),
  terisi 16:53 WIB. Hasilnya menentukan budget tiket hari ini. Status: `paper_engine.py posisi` / `/posisi` di Telegram.
- Cron Hermes: `pemindai-tiket` 1-59/5, `notif-paper` tiap menit, `psikologi` tiap jam, `uji-hipotesis` 23:40, `evaluasi-harian` 23:55, `evaluasi-susulan` 08:20/11:20/…/20:20 (hanya bila kemarin belum dievaluasi). `hermes cron list`.
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
| 2b | 23:55 evaluasi harian tiba di Telegram | ⬜ (11 Okt terlewat: laptop mati 22:03; dikerjakan lewat `evaluasi-susulan` 12 Okt 08:38 → `pasar/harian/2026-10-11.md` terbentuk) |
| A | T24 breakeven (SL ke entry setelah 83% jalan → STOP kecil, bukan hangus; cfg 0 = mati), T25 autopsi, M9/M11 → 27 tool | ✅ |
| AR | Deploy 17:45 WIB: collector/dashboard restart skema v3 (`akun list`: tiket, breakout, fade, rentang aktif + acak + swing); cron `pemindai-tiket` dibuat ulang 6841faf27e63 dengan `--skill arena`; `nilai-arena` e31dc173d9a8 (Senin 07:30); gateway PID 12200; `hermes mcp test paper` → 28; `/api/arena` 4 persona | ✅ |
| AR | Wake pertama arena: jurnal berisi keputusan per persona, order di akun berbeda, bayangan acak per order | ⬜ menunggu kejadian |
| S | Cron `evaluasi-susulan` 4186108ae29c terdaftar; `cron run` → agent mengevaluasi 11 Okt dengan `hari=`, catatan harian kemarin terbentuk, gate kembali false | ✅ |
| 2b+ | `test_notifikasi` N1–N3 (init sunyi, order/terisi/TP, batal/kedaluwarsa, likuidasi, batas 20, CLI), `test_hermes_sync` H5 | ✅ |
| 2b+ | Cron `notif-paper` 4c19f528cc31 terdaftar (mode no-agent); `hermes cron run notif-paper` 17:01 WIB mengirim 2 kejadian (#6 order SOL, #7 terisi) → `delivery_outcome=delivered`, kursor #7; tanpa panggilan API | ✅ |
| 3a | `test_paper_engine` T20–T23 (bayangan acak: dibuat, terisi+TP relatif+EOD, dilewati tanpa merusak order asli, deterministik/ACAK_EOD), `test_evaluasi` E1–E3, `test_uji_hipotesis` U1–U5, `test_mcp_server` M11 + M9 (23 tool), `test_notifikasi` N4 | ✅ 109 tes |
| 3a | Collector dimulai ulang 17:35 WIB dengan skema paper v2; `paper_engine.py budget` menampilkan tiket/swing/acak; tick normal (weight 91) | ✅ |
| 3a | Cron `uji-hipotesis` f497508f3dd4 (40 23, no-agent) terdaftar; gateway restart PID 16660; `hermes mcp test paper` → 23 tool; `hermes cron run uji-hipotesis` → 0 dinilai, `delivery_outcome=suppressed`, `api_calls` tetap 29 | ✅ |
| 3a | Jalur positif: order tiket agent berikutnya menghasilkan baris `acak` `ACAK:<id>`; `evaluasi.py` berjalan pada data nyata; agent menulis hipotesis terstruktur via Telegram | ⬜ menunggu kejadian |
| 3b | `test_psikologi` PS1–PS6 (zona, sumber gagal, divergensi, persentil, rezim OI, retensi), M12 panel + frontmatter, M9 → 24 tool, merge menu `psikologi` | ✅ 116 tes |
| 3b | `psikologi.py --once` nyata 17:55 WIB: 20 indikator, 0 tidak tersedia (FNG 61, funding −0,0017%, L/S akun 1,45, top 1,52, taker 1,09, likuidasi short 86 vs long 14 → serakah, premium ≈ 0, stablecoin −0,3%) | ✅ |
| 3b | Cron `psikologi` 85f32aac4251 (7 * * * *, no-agent) terdaftar; gateway restart PID 21172; menu Telegram 14 perintah termasuk `/psikologi`; `hermes mcp test paper` → 24 tool; `cron run psikologi` 17:59 → `panel_run` ok 20/0, `delivery_outcome=suppressed`, `api_calls` tetap 29 | ✅ |
| 3b | `/psikologi` dari Telegram (user); catatan harian 23:55 punya frontmatter `fng`/`funding_btc` | ⬜ user / menunggu |
| 3c | `test_referensi` R1–R5 (heuristik judul pada PDF sintetis, potongan halaman, perlu_ocr, cari/baca/daftar, slug aman), M13, M9 → 26 | ✅ 122 tes |
| 3c | Konversi nyata: mastering-trading-psychology 14 bab (hal 1–408), panduan-analisis-crypto 9 bab, goodcrypto-pola-chart 3 bab; `referensi/buku/` tidak ter-commit | ✅ |
| 3c | `indeks.md` terisi untuk 3 buku; `playbook.md` v1: aturan aktif (ditegakkan mesin/skill) + usulan `uji` dari buku dengan rujukan bab | ✅ |
| 3c | Sync skill `referensi` + SOUL + menu (`/referensi` menggantikan `/model`), gateway restart PID 27388, `hermes mcp test paper` → 26 tool, menu Telegram 14 perintah | ✅ |
| 3c | Whitelist `tools.include` di config.yaml hidup ketinggalan (22 tool) → snippet dibuat dari TOOL_NAMES, merge menyamakan daftar; setup_hermes + gateway restart; `hermes mcp test paper` → 28 | ✅ (12 Okt malam) |
| 3c | `/referensi fomo` dari Telegram; `/cek` menyebut playbook; pemilik memutuskan status aturan `uji` | ⬜ user (P-09/11/15 sudah diaktifkan) |
| D | `test_dashboard` D1–D4 (DB kosong → 200 & tidak tersedia, candles resample, marker/riwayat/ekuitas dari engine, statis aman); dashboard nyata: chart ETH/SOL dengan garis order #3, marker, panel budget/posisi/cron, API cost | ✅ |

## Keputusan yang berlaku

- Jaringan rumah memblokir DNS Binance → DoH di dalam skrip; DNS Windows tidak diubah.
- Arena (12 Okt): persona = akun jenis `tiket` di tabel `account`; seleksi mekanis mingguan (≥ 30 trade, ≥ 30 hari, kalah dari acaknya
  p < 0,2 → pensiun); juara hanya dilaporkan, jatah tidak diubah (v1). Satu wake = satu sesi untuk semua persona (hemat konteks).
- Saldo tiket harian bergulir (12 Okt, keputusan user): mulai $1, TP menambah, hangus mengurangi, minimum $0,50 untuk buka tiket baru,
  satu tiket ≤ $1 (margin + fee); kedaluwarsa & tutup paksa 23:50; tidak ada tiket baru setelah 22:30. Akun acak mengikuti aturan yang sama.
- Ambiguitas intrabar pesimis (liq → SL → TP), ditandai `ambiguous`.
- Budget API: $10/hari, $190/bulan, $1/panggilan, ditegakkan `budget_proxy.py`; kill switch `data/STOP_AGENT`.
- Model agent: `claude-opus-5-5`, effort `low`; pemindai mekanis (tanpa LLM) membangunkan agent hanya bila ada kandidat.
- Pemindai: jadwal `1-59/5` (bar 1m tersimpan detik :05), `data_until` dari bar tersimpan (bukan jam dinding), gate G1–G8,
  skor ≥ 3, jarak liq ≥ 2×ATR 5m, cooldown 30 menit per simbol, maks 12 wake/hari, jam 07:00–22:30 WIB. Knob: `PemindaiConfig`.
  Watchlist = **top 30 volume 24 jam** (bukan daftar tetap); maks 5 kandidat skor tertinggi per wake (`top_k`).
  Gate G9 (playbook P-09): 2 tiket HANGUS beruntun di hari yang sama → pemindai tidak membangunkan agent sampai besok.
- Panel psikologi: tanpa skor gabungan; zona awal §16.2 lalu persentil 10/90 setelah 90 hari; likuidasi dari OKX (Binance
  `allForceOrders` diblokir ISP); premium IDR via USDT/IDR Indodax. Host Coinbase/OKX lewat DoH.
- Referensi: tanpa vector DB; Hermes mencari lewat tool MCP (bukan `@path`/Grep seperti spesifikasi lama). Isi buku tidak
  pernah ke chat/repo (cuplikan ≤ 320 karakter, kutipan ≤ 15 kata). Playbook: status diubah hanya oleh pemilik.
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
