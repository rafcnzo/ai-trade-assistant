# CHANGELOG

Format: entri terbaru di atas. Setiap entri: tanggal WIB, perangkat, apa yang berubah, kenapa, file terdampak.
Perubahan kode dan entri changelog masuk dalam commit yang sama.

## 2026-10-11 (malam) — laptop Windows — menu Telegram ringkas, pesan kaya, skill pintas

**Apa:** skill pintas `posisi`, `budget`, `laporan`, `cek <SIMBOL> <ARAH>`, `batal`, `status` (tiap skill = perintah
`/nama` di Telegram); `merge_config.py` menambah blok `platforms.telegram.extra` (`rich_messages: true`,
`command_menu` mode `replace`, maks 14, prioritas skill kita + help/new/usage/commands/whoami/model);
SOUL.md: aturan format markdown Telegram + daftar perintah pintas; `tests/test_merge_config.py`.

**Kenapa:** uji Telegram pertama oleh user lolos secara perilaku (daftar order, tolak shell, SKIP SOL dengan alasan),
tapi tampilannya polos dan menu `/` berisi 60 perintah bawaan/skill bundel Hermes sehingga `/tiket` tersembunyi
("61 hidden" di gateway.log).

**Catatan:** skill bundel Hermes (apple, productivity, dst.) tidak bisa dimatikan lewat config; direktori yang
diawali `_` diabaikan, itu opsi bila ingin mengurangi token prompt sistem (±3k, di-cache).

**File:** `hermes/skills/{posisi,budget,laporan,cek,batal,status}/SKILL.md`, `hermes/SOUL.md`, `hermes/merge_config.py`,
`tests/test_merge_config.py`, `docs/OPERASI.md`, `docs/STATUS.md`.

## 2026-10-11 (sore, lanjutan) — laptop Windows — Hermes terpasang dan terverifikasi end-to-end

**Apa:** Hermes Agent v0.21.6 terpasang oleh user (wizard: provider custom → proxy, `api_mode: anthropic_messages`,
context 200k, Telegram + allowlist, toolset Telegram minimal). Skrip baru: `hermes/merge_config.py` (penggabungan
`config.yaml` tekstual, idempoten, dengan backup), `hermes/setup_hermes.cmd` (sync + merge + launcher Startup +
nyalakan proxy/collector + cek Hermes), `hermes/run_logged.cmd` (pelaksana perintah dari `logs/hermes_cmd.txt`),
`hermes/startup/*.vbs` (launcher Startup proxy & collector). Proxy menolak dengan **403** `permission_error`
(bukan 429) agar SDK tidak mengulang saat budget habis.

**Hasil verifikasi:** `hermes mcp test paper` → 22 tool terhubung (4 s); `hermes -z` menjawab jam/umur tick/budget
lewat tool MCP; proxy mencatat 2 panggilan Opus = $0,0955 (cache write 16k token prompt sistem, lalu cache read);
gateway jalan (Startup `Hermes_Gateway.vbs`); `config.yaml` tergabung (`cron.catch_up_missed=false`,
`disabled_toolsets`, `platform_toolsets` cli/telegram/cron = `[clarify, memory, skills, mcp-paper]`, `mcp_servers.paper`).

**Temuan sandbox (penting untuk sesi Claude Code berikutnya di laptop ini):** proses dari dalam aplikasi Claude
(MSIX) melihat `AppData` tervirtualisasi; tugas terjadwal yang dibuat dari sana hanya "Queued" dan tidak pernah
jalan; tugas "saat login" butuh admin. Yang bekerja: `explorer.exe "<path>\setup_hermes.cmd"` / `run_logged.cmd`
(Explorer menjalankan skrip di luar sandbox) dan launcher di folder Startup. Didokumentasikan di OPERASI §Hermes.

**File:** `scripts/budget_proxy.py`, `tests/test_budget_proxy.py`, `hermes/merge_config.py`, `hermes/setup_hermes.cmd`,
`hermes/run_logged.cmd`, `hermes/startup/*.vbs`, `docs/OPERASI.md`, `docs/STATUS.md`.

## 2026-10-11 (sore) — laptop Windows — Milestone 2a: integrasi Hermes Agent (kode selesai)

**Apa:** `scripts/budget_proxy.py` (proxy 127.0.0.1:8585 → api.anthropic.com; cap lewat `BudgetGuard`; stream SSE
diteruskan sambil dibaca; key asli hanya dari env `ANTHROPIC_API_KEY`), `scripts/analisis.py` (resample, EMA/RSI/ATR
Wilder, swing, klaster level, jejak psikologi, tabel leverage §17.3, top volume §17.7), `scripts/mcp_server.py`
(FastMCP stdio, 22 tool whitelist untuk Hermes), `PaperEngine.history()`, `scripts/schema_kandidat.sql`,
`hermes/` (SOUL.md, skill `tiket` & `evaluasi-harian`, `scripts/pemindai_cron.py`, `config.snippet.yaml`, `cron.cmd`,
`sync.py`), `run_budget_proxy.cmd`, 31 tes baru (total 74), `mcp==1.30.0` di `requirements.txt`, CLAUDE.md dan
OPERASI.md (bagian "Hermes Agent").

**Kenapa:** user memutuskan otak asisten adalah Hermes Agent (native Windows, Telegram + CLI), bukan Claude Code.
Hermes memanggil model sendiri, jadi cap $10/hari hanya bisa ditegakkan oleh proxy di depan Anthropic. Mesin paper
diekspos lewat MCP agar agent tidak pernah menyentuh DB/skrip langsung.

**Keputusan dan temuan:**
- Installer Hermes **harus dijalankan dari terminal user**, bukan dari Claude Code: proses di dalam aplikasi Claude
  (paket MSIX) melihat `AppData` tervirtualisasi, sehingga `uv` gagal ("Missing expected target directory") dan hasil
  instalasi tidak akan terlihat oleh Task Scheduler. Juga butuh `core.longpaths=true` (env sesi) karena dokumen i18n
  Hermes melampaui 260 karakter.
- Paket MCP dipin `mcp==1.30.0` (`FastMCP`); 2.x mengganti API (`MCPServer`) dan belum diverifikasi.
- Proxy mencatat biaya **sebelum** mengirim respons (non-stream) / sebelum penutup chunked (stream), supaya klien tidak
  pernah melihat jawaban yang belum tercatat.
- Jarak likuidasi BTC 150x yang persis: `1 − (1−1/150)/(1−0,004) = 0,2678%` (dokumen menulis 0,27%).
- Tool MCP memberi label `BASI` bila tick collector > 90 detik (collector 60 detik), menyimpang dari §3.3 (5 menit).

**Belum (menunggu user):** instalasi Hermes dari terminal sendiri, `setx ANTHROPIC_API_KEY`, token/allowlist Telegram,
Task Scheduler proxy, gabung snippet config, `hermes mcp test paper`, `hermes gateway install`. Lihat `STATUS.md`.

**File:** `scripts/budget_proxy.py`, `scripts/analisis.py`, `scripts/mcp_server.py`, `scripts/paper_engine.py`,
`scripts/schema_kandidat.sql`, `hermes/*`, `tests/test_{budget_proxy,analisis,mcp_server,hermes_sync}.py`,
`run_budget_proxy.cmd`, `requirements.txt`, `CLAUDE.md`, `docs/OPERASI.md`, `docs/STATUS.md`, `docs/rencana-asisten-crypto.md`.

## 2026-10-11 (siang) — laptop Windows — weight tick dan saringan BAR_REVISED

**Apa:** `collector.py`: (1) `kline_limit()` — jumlah bar yang diminta mengikuti kebutuhan, bukan selalu 1500;
weight tick rutin turun dari ±451 ke ±90 per menit (weight Binance mengikuti `limit`, bukan jumlah baris
yang kembali). (2) Revisi bar < 0,01% diabaikan (`REVISION_MIN_REL`); revisi lebih besar jadi event
`BAR_REVISED` hanya jika simbol punya order/posisi (`PaperEngine.has_exposure`), selain itu hanya log INFO.
Tes `test_kline_limit_keeps_weight_small` ditambah.

**Kenapa:** log soak pertama dipenuhi `BAR_REVISED` tak berarti (Binance merapikan mark kline yang baru close
dengan selisih 0,001%), dan weight 451/menit membatasi jumlah simbol yang bisa dipantau.

**File:** `scripts/collector.py`, `scripts/paper_engine.py`, `tests/test_common.py`, `docs/OPERASI.md`.

## 2026-10-11 — laptop Windows — Milestone 1 selesai

**Apa:** mesin paper trading lengkap: `scripts/common.py`, `scripts/collector.py`, `scripts/paper_engine.py`,
`scripts/budget_guard.py`, skema `scripts/schema_{pasar,paper,budget}.sql`, 43 unit test di `tests/`,
`docs/OPERASI.md`, `run_collector.cmd`, `CLAUDE.md`, `.claude/settings.json`, venv + `requirements.txt`.

**Kenapa:** milestone 1 rencana v1.3 (§19.9 langkah 1, 2, 4): data pasar mulai terkumpul sekarang;
agent menyusul di milestone 3.

**Keputusan dan temuan saat implementasi:**
- Wi-Fi rumah (ISP Centrin) memblokir `binance.com` di level DNS (halaman Kominfo). Koneksi ke IP asli
  dengan SNI lolos. Dipilih resolver DoH di dalam skrip (patch `socket.getaddrinfo` hanya untuk host Binance);
  DNS Windows tidak diubah. Deteksi halaman blokir → `BlockedError`, data tidak disimpan.
- Endpoint publik yang dipakai diverifikasi: `time`, `klines` (1500 bar), `markPriceKlines`, `premiumIndex`,
  `fundingRate`, `fundingInfo`, `ticker/24hr`, `exchangeInfo`, dan `www.binance.com/bapi/.../common/brackets`
  (leverage maks + MMR + cum untuk 1.061 simbol, tidak terdokumentasi).
- Bug ditemukan oleh tes T15 dan diperbaiki: funding terhitung dua kali karena jendela event dibuka dari
  `open_time` bar sebelumnya, bukan dari close-nya.
- Budget tiket mencakup fee masuk (`margin + fee ≤ $1`), karena wallet $1 nyata tidak bisa membuka margin $1.
- Satu proses `collector.py run` memiliki data dan jam mesin; CLI/agent hanya menyisipkan order.

**Verifikasi:** 43/43 tes hijau; collector live 20 simbol × 48 jam dalam 19 s (weight 856); 3 order paper
diterima, 3 ditolak dengan kode benar. Soak 24 jam dan uji tidur laptop masih berjalan (lihat `STATUS.md`).

## 2026-10-08 → 2026-10-11 — perencanaan

Rencana v1.0 → v1.3 (`docs/rencana-asisten-crypto.md`): review, uji sumber data, gaya trading tiket $1 dan
swing $10, komunitas, memori pasar, referensi buku, agent paper trading dengan budget API $10/hari.
