# STATUS — keadaan proyek sekarang

> Baca file ini dulu saat memulai sesi di perangkat mana pun. Perbarui setiap kali ada perubahan.
> Riwayat perubahan: `docs/CHANGELOG.md`. Spesifikasi: `docs/rencana-asisten-crypto.md`. Operasi: `docs/OPERASI.md`.

Diperbarui: 2026-10-11 15:55 WIB (perangkat: laptop Windows "laptop-l5i0361r")

## Arsitektur (sejak 11 Okt siang)

Otak asisten = **Hermes Agent v0.21.6** native Windows (Telegram + CLI). Claude Code hanya membangun proyek.
```
Folder Startup user (login, tanpa jendela)
 ├─ crypto-analyst_collector.vbs → run_collector.cmd     data pasar + mesin paper            (JALAN)
 ├─ crypto-analyst_proxy.vbs     → run_budget_proxy.cmd  127.0.0.1:8585 → Anthropic, cap $10/hari (JALAN, key_set)
 └─ Hermes_Gateway.vbs           → Hermes gateway        Telegram + cron (cron job belum dibuat: 2b)
      └─ MCP "paper"               scripts/mcp_server.py, 22 tool  (TERHUBUNG, hermes mcp test paper OK)
```

## Milestone

| Milestone | Isi | Status |
|---|---|---|
| 1 | Mesin paper trading: collector, paper_engine, budget_guard, 43 tes | **Selesai**, live |
| 2a | Hermes: budget_proxy, analisis, mcp_server (22 tool), SOUL + skill `tiket` + `sync.py` + `setup_hermes.cmd`, docs | **Selesai & terverifikasi** (`hermes -z` menjawab lewat tool MCP; biaya tercatat). Sisa: uji dari Telegram oleh user |
| 2b | `pemindai.py` + `kandidat.sqlite`, `kline_1h` di collector, 2 cron job (`pemindai-tiket`, `evaluasi-harian`) | Belum mulai (skill, skema kandidat, pembungkus cron sudah ada) |
| 3 | Baseline acak, kriteria lulus §19.7, memori pasar lengkap (§16), referensi buku (§15) | Belum mulai |

## Yang harus dilakukan user

1. Uji Telegram pertama **lolos** (posisi/order benar, shell ditolak, `/cek SOL LONG` → SKIP beralasan + jurnal).
   Berikutnya: tutup-buka chat bot, cek menu `/` berisi 14 perintah proyek, coba `/posisi`, `/budget`, `/status`;
   laporkan apakah tebal/daftar sudah dirender.
2. Opsional: pasang spend limit di workspace Console Anthropic; `hermes doctor --fix` untuk saran `custom_providers → providers`;
   sembunyikan skill bundel Hermes yang tidak dipakai dengan mengganti nama folder di `%LOCALAPPDATA%\hermes\skills\` menjadi `_nama`.

## Yang sedang berjalan

- Collector, proxy, dan gateway Hermes jalan di luar sandbox (launcher Startup). Cek: `collector.py status`,
  `curl 127.0.0.1:8585/healthz`, `hermes gateway status`.
- Order paper uji 11 Okt 11:42 WIB: #1 tiket BTC LONG 150x @ 82.915,7; #2 tiket ETH LONG 100x @ 2.431,1 (jauh);
  #3 swing ETH SHORT 10x @ 2.511,3. Status: `paper_engine.py laporan`.
- Biaya API hari ini: ≈ $0,10 (2 panggilan uji). Laporan: `budget_guard.py laporan`.

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
| 2a | Telegram: posisi/order; pasang tiket → `created_by=hermes`; "jalankan shell" → tidak punya tool | ⬜ user |

## Keputusan yang berlaku

- Jaringan rumah memblokir DNS Binance → DoH di dalam skrip; DNS Windows tidak diubah.
- Budget tiket `margin + fee masuk ≤ $1`/hari WIB; order tiket kedaluwarsa & posisi ditutup paksa 23:50 WIB; tidak ada tiket baru setelah 22:30.
- Ambiguitas intrabar pesimis (liq → SL → TP), ditandai `ambiguous`.
- Budget API: $10/hari, $190/bulan, $1/panggilan, ditegakkan `budget_proxy.py`; kill switch `data/STOP_AGENT`.
- Model agent: `claude-opus-5-5`, effort `low`; pemindai mekanis (tanpa LLM) membangunkan agent hanya bila ada kandidat.
- Agent hanya lewat MCP (22 tool whitelist); toolset terminal/file/browser dimatikan di cron, telegram, cli.
- `mcp==1.30.0` (FastMCP). Hermes diinstal dari terminal user, bukan dari Claude Code.
- Di laptop ini, proses dari Claude Code tervirtualisasi (MSIX): yang menyentuh `%LOCALAPPDATA%\hermes`, Startup, atau
  perintah `hermes` dijalankan lewat `explorer.exe "<path>\hermes\setup_hermes.cmd"` / `run_logged.cmd` (lihat OPERASI).
- Proxy menolak budget habis / kill switch dengan 403 (bukan 429) agar SDK tidak mengulang.
- Repo GitHub `rafcnzo/ai-trade-assistant`; `data/`, `logs/`, `jurnal/`, `laporan/`, `pasar/harian`, `pasar/komunitas`, `referensi/buku/` tidak di-commit.

## Pertanyaan terbuka

- Semantik Hermes yang belum dikonfirmasi dari instalasi nyata: nama entri `platform_toolsets.cron`, apakah `tools.include`
  memakai nama bare atau `mcp_paper_*`, dan apakah stdout skrip cron sampai ke agent atau hanya ke kanal (skill `tiket`
  tidak bergantung padanya: ia memanggil `kandidat_terbaru`). Dicek saat `hermes mcp test paper` / `hermes tools`.
