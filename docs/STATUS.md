# STATUS — keadaan proyek sekarang

> Baca file ini dulu saat memulai sesi di perangkat mana pun. Perbarui setiap kali ada perubahan.
> Riwayat perubahan: `docs/CHANGELOG.md`. Spesifikasi: `docs/rencana-asisten-crypto.md`. Operasi: `docs/OPERASI.md`.

Diperbarui: 2026-10-11 13:10 WIB (perangkat: laptop Windows "laptop-l5i0361r")

## Arsitektur (sejak 11 Okt siang)

Otak asisten = **Hermes Agent** native Windows (Telegram + CLI). Claude Code hanya membangun proyek.
```
Task Scheduler (login)
 ├─ run_collector.cmd      data pasar + mesin paper            (jalan, dari sesi Claude Code; Task Scheduler belum didaftarkan)
 ├─ run_budget_proxy.cmd   127.0.0.1:8585 → Anthropic, cap $10/hari  (kode siap; belum didaftarkan; butuh ANTHROPIC_API_KEY di env user)
 └─ Hermes gateway         cron pemindai (2b) + evaluasi harian (2b) + Telegram
      └─ MCP "paper"       scripts/mcp_server.py, 22 tool       (kode siap; 74 tes hijau)
```

## Milestone

| Milestone | Isi | Status |
|---|---|---|
| 1 | Mesin paper trading: collector, paper_engine, budget_guard, 43 tes | **Selesai**, live |
| 2a | Hermes: budget_proxy, analisis, mcp_server (22 tool), SOUL + skill `tiket` + `sync.py`, docs | **Kode selesai, 74 tes hijau.** Menunggu instalasi Hermes & rahasia oleh user (daftar di bawah) |
| 2b | `pemindai.py` + `kandidat.sqlite`, `kline_1h` di collector, skill `evaluasi-harian` dipasang ke cron, 2 cron job | Belum mulai (skill, skema kandidat, dan pembungkus cron sudah ada) |
| 3 | Baseline acak, kriteria lulus §19.7, memori pasar lengkap (§16), referensi buku (§15) | Belum mulai |

## Yang harus dilakukan user (urutan)

1. Install Hermes **dari PowerShell sendiri** (perintah di `docs/OPERASI.md` → Hermes Agent §1). Instalasi dari dalam
   Claude Code gagal karena virtualisasi AppData. Buka terminal baru, `hermes --version`.
2. `setx ANTHROPIC_API_KEY <key>` (terminal baru setelahnya); spend limit di Console.
3. `hermes config set TELEGRAM_BOT_TOKEN <token>` dan `hermes config set TELEGRAM_ALLOWED_USERS <user_id>`.
4. Daftarkan Task Scheduler proxy dan collector (`docs/OPERASI.md`).
5. Kabari Claude: ia menjalankan `hermes/sync.py`, menggabungkan snippet ke `config.yaml`, `hermes mcp test paper`,
   `hermes gateway install`, lalu uji cepat (§6 OPERASI).

## Yang sedang berjalan

- Collector + mesin paper dari sesi Claude Code (ID proses lihat Task Manager `python.exe` dengan `collector.py run`).
- Order paper uji 11 Okt 11:42 WIB: #1 tiket BTC LONG 150x @ 82.915,7; #2 tiket ETH LONG 100x @ 2.431,1 (jauh);
  #3 swing ETH SHORT 10x @ 2.511,3. Status: `paper_engine.py laporan`.

## Verifikasi

| # | Item | Hasil |
|---|---|---|
| M1 | Unit test T1–T19, B1–B3 | ✅ |
| M1 | Collector live lewat DoH, backfill, pacing | ✅ (weight tick ±90) |
| M1 | Order manual diterima/ditolak dengan kode benar | ✅ |
| M1 | Soak 24 jam, uji tidur laptop, likuidasi vs aplikasi Binance | ⬜ berjalan / user |
| 2a | `test_budget_proxy` P1–P9 (upstream palsu, stream byte-identik, 429 tanpa upstream, kill switch) | ✅ |
| 2a | `test_analisis` A1–A6, `test_mcp_server` M1–M9 (22 tool terdaftar di FastMCP), `test_hermes_sync` H1–H4 | ✅ |
| 2a | `hermes --version`, `hermes mcp test paper` → 22 tool, `hermes tools` tanpa terminal/file | ⬜ menunggu instalasi |
| 2a | `curl 127.0.0.1:8585/healthz`; `hermes -z "jam dan budget tiket sekarang?"`; `budget_guard.py status` mencatat biaya | ⬜ |
| 2a | Telegram: posisi/order; pasang tiket → `created_by=hermes`; "jalankan shell" → tidak punya tool; `STOP_AGENT` memblokir | ⬜ |

## Keputusan yang berlaku

- Jaringan rumah memblokir DNS Binance → DoH di dalam skrip; DNS Windows tidak diubah.
- Budget tiket `margin + fee masuk ≤ $1`/hari WIB; order tiket kedaluwarsa & posisi ditutup paksa 23:50 WIB; tidak ada tiket baru setelah 22:30.
- Ambiguitas intrabar pesimis (liq → SL → TP), ditandai `ambiguous`.
- Budget API: $10/hari, $190/bulan, $1/panggilan, ditegakkan `budget_proxy.py`; kill switch `data/STOP_AGENT`.
- Model agent: `claude-opus-5-5`, effort `low`; pemindai mekanis (tanpa LLM) membangunkan agent hanya bila ada kandidat.
- Agent hanya lewat MCP (22 tool whitelist); toolset terminal/file/browser dimatikan di cron, telegram, cli.
- `mcp==1.30.0` (FastMCP). Hermes diinstal dari terminal user, bukan dari Claude Code.
- Repo GitHub `rafcnzo/ai-trade-assistant`; `data/`, `logs/`, `jurnal/`, `laporan/`, `pasar/harian`, `pasar/komunitas`, `referensi/buku/` tidak di-commit.

## Pertanyaan terbuka

- Semantik Hermes yang belum dikonfirmasi dari instalasi nyata: nama entri `platform_toolsets.cron`, apakah `tools.include`
  memakai nama bare atau `mcp_paper_*`, dan apakah stdout skrip cron sampai ke agent atau hanya ke kanal (skill `tiket`
  tidak bergantung padanya: ia memanggil `kandidat_terbaru`). Dicek saat `hermes mcp test paper` / `hermes tools`.
