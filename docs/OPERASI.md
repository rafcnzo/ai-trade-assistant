# Panduan Operasi — Milestone 1 (mesin paper trading)

Spesifikasi lengkap: `docs/rencana-asisten-crypto.md`. Konvensi proyek: `CLAUDE.md`.

## Komponen

| File | Peran | Penulis DB |
|---|---|---|
| `scripts/collector.py` | Mengambil kline 1m (harga terakhir + mark), kline 1h (120 hari), funding, snapshot mark, peringkat volume; memanggil mesin tiap menit | `data/pasar.sqlite` |
| `scripts/pemindai.py` | Pemindai kandidat tiket mekanis (tanpa LLM) tiap 5 menit lewat cron Hermes; membangunkan agent hanya bila ada kandidat | `data/kandidat.sqlite` |
| `scripts/notifikasi.py` | Notifikasi kejadian paper (terisi, TP, STOP, likuidasi, kedaluwarsa, batal) ke Telegram tiap menit lewat cron Hermes `--no-agent` (tanpa LLM) | `data/notif.json` |
| `scripts/evaluasi.py` | Statistik kelulusan §19.7 (expectancy, stabilitas, kepatuhan, tiket vs akun `acak`); baca saja | — |
| `scripts/psikologi.py` | Panel psikologi pasar §16.2 tiap jam (FNG, funding, OI, L/S, taker, likuidasi OKX, premium Coinbase/IDR, stablecoin) dengan zona & divergensi; cron Hermes `--no-agent` | `data/psikologi.sqlite` |
| `scripts/konversi_buku.py`, `scripts/referensi.py` | Konversi ebook → `referensi/buku/<slug>/bab-NN.md`; pencarian kata kunci & pembacaan bab untuk tool MCP | `referensi/buku/<slug>/` |
| `scripts/hipotesis.py`, `scripts/uji_hipotesis.py` | Hipotesis terstruktur: skema/penilaian/baseline (murni) dan skrip harian 23:40 yang menilai, menghitung baseline, mengelola pelajaran | `pasar/hipotesis-hasil.jsonl`, `pasar/hipotesis.md`, `pasar/pelajaran.{jsonl,md}` |
| `scripts/paper_engine.py` | Simulasi order/posisi/likuidasi/fee/funding; CLI order manual; laporan | `data/paper.sqlite` |
| `scripts/budget_guard.py` | Biaya API Anthropic: cap harian $10, bulanan $190, per panggilan $1; kill switch | `data/budget.sqlite` |
| `scripts/budget_proxy.py` | Proxy 127.0.0.1:8585 → api.anthropic.com untuk Hermes; menegakkan cap lewat budget_guard; memegang API key asli | (lewat budget_guard) |
| `scripts/mcp_server.py` | Server MCP stdio untuk Hermes: 28 tool (data pasar, order paper, laporan, jurnal, hipotesis, statistik kelulusan, panel psikologi, referensi buku) | `jurnal/agent/`, `pasar/harian/`, `pasar/hipotesis.md`, `pasar/pelajaran-usulan.md` |
| `scripts/analisis.py` | Resample, EMA/RSI/ATR Wilder, swing & level, jejak psikologi, tabel leverage, top volume | — |
| `scripts/common.py` | Waktu WIB, resolver DoH, HTTP + pacing weight, SQLite, Decimal, logging | — |
| `hermes/` | Aset Hermes: `SOUL.md`, skill `tiket` & `evaluasi-harian`, pembungkus cron, snippet config, `sync.py` | → `HERMES_HOME` |
| `scripts/dashboard.py` + `dashboard/` | Dashboard lokal baca-saja `http://127.0.0.1:8586`: chart candlestick + marker trade, posisi/order live, riwayat, ekuitas, statistik, pemindai, psikologi, jurnal | — |
| `run_collector.cmd`, `run_budget_proxy.cmd`, `run_dashboard.cmd` | Pembungkus launcher Startup (tanpa jendela konsol) | — |

Semua perintah dijalankan dari folder proyek dengan interpreter venv:

```bash
.venv/Scripts/python.exe scripts/collector.py status
```

## Jaringan rumah dan DoH

Wi-Fi rumah (ISP Centrin) mengarahkan `binance.com`, `okx.com`, `bybit.com` ke halaman blokir
Kominfo di level DNS. `common.DohResolver` menerjemahkan nama host Binance lewat DNS-over-HTTPS
(Cloudflare, cadangan Google) di dalam proses, hanya untuk host dalam allowlist. Pengaturan DNS
Windows tidak disentuh. Jika suatu saat respons berupa halaman blokir, `http_get` melempar
`BlockedError`, event `BLOCKED` dicatat, dan tidak ada data yang disimpan.

## Menjalankan collector

Sekali tick (uji):
```bash
.venv/Scripts/python.exe scripts/collector.py --n 20 run --once
```

Loop terus-menerus (jendela konsol):
```bash
.venv/Scripts/python.exe scripts/collector.py run
```

Hanya data tanpa mesin paper: tambahkan `--tanpa-mesin`.

### Pendaftaran Task Scheduler (dijalankan sendiri oleh pengguna)

Buat tugas yang berjalan saat login, lewat Command Prompt:

```bash
schtasks /Create /TN "crypto-analyst collector" /TR "\"C:\Users\hp\crypto-analyst\run_collector.cmd\"" /SC ONLOGON /RL LIMITED /F
```

Lalu buka Task Scheduler → tugas tersebut → Properties:
- **Settings**: centang "Run task as soon as possible after a scheduled start is missed";
  "If the task is already running" → "Do not start a new instance"; hapus centang
  "Stop the task if it runs longer than".
- **Conditions**: hapus centang "Start the task only if the computer is on AC power" dan
  "Stop if the computer switches to battery power".

Jalankan sekarang tanpa logout: `schtasks /Run /TN "crypto-analyst collector"`.
Hentikan: `schtasks /End /TN "crypto-analyst collector"`, atau tutup proses `pythonw.exe` di Task Manager.

Log: `logs/collector.log` (rotasi 5 MB × 5) dan `logs/collector.out.log`.

### Membaca log collector

- `tick ...: 20 simbol, 60 bar, 5400 ms, weight 90` — normal. Weight adalah pemakaian limit Binance per
  menit (batas 1.200; pacing otomatis mulai 1.000). Tick pertama setelah celah panjang bisa mencapai ±850.
- `bar1h 21` — bar 1 jam baru (sekali per jam, ≥ 60 s setelah jam bulat, 1 permintaan kecil per simbol). Simbol baru
  di-backfill 120 hari, maksimal 5 simbol per tick (±4 tick untuk 20 simbol; weight tick sementara ±100–400).
  `collector.py status` menampilkan cakupan `Bar 1h`. Retensi 180 hari.
- `GAP` — tidak ada tick > 2,5 menit (laptop tidur); celah diisi otomatis.
- `BAR_REVISED` — Binance mengubah bar yang sudah diproses mesin. Revisi < 0,01% diabaikan. Dicatat sebagai
  event WARNING hanya jika simbol itu punya order/posisi; periksa apakah level likuidasi/TP terpengaruh.
- `BLOCKED` — respons berupa halaman blokir ISP walau lewat DoH; tidak ada data yang disimpan.

## Setelah laptop tidur / mati

Tidak ada mode khusus. Saat tick berikutnya, collector mencatat event `GAP`, mengisi
kline yang bolong dari Binance (maks 30 hari ke belakang), lalu mesin memproses semua bar
yang belum diproses dalam urutan waktu. Funding, tutup paksa 23:50 WIB, dan pergantian hari
terjadi pada bar historis yang benar. Hasilnya sama persis dengan seandainya laptop terus menyala
(diuji di `tests/test_paper_engine.py::TestCatchUpAndDeterminism`).

## Arena: empat persona trader

Tabel `account` (paper.sqlite) memuat akun jenis `tiket` = persona: `tiket` (price action), `fade` (lawan kerumunan: panel psikologi
≥ 2 ekstrem + divergensi), `breakout` (tembus dengan VOL, entry uji ulang), `rentang` (mean reversion saat 15m sideways/KOMPRESI).
Masing-masing: saldo bergulir $1/hari, maks 2 order hidup, P-09/P-18, bayangan acak sendiri (pairing `plan_id=ACAK:<order_id>`).
Satu wake pemindai = satu sesi skill `arena` yang memutuskan untuk semua persona aktif (baris `Akun aktif:` di pesan pemindai).

- Papan: `evaluasi.py --arena`, tool `papan_arena`, `/arena-papan`, dashboard tab Arena. Juara hanya bila ≥ 30 trade.
- Seleksi: cron `nilai-arena` (Senin 07:30, `--no-agent`) menjalankan `evaluasi.py --nilai-arena --cron`: persona aktif dengan
  ≥ 30 trade, ≥ 30 hari, dan kalah dari acaknya (selisih < 0, p permutasi < 0,2) → `status=pensiun` (mesin menolak order baru,
  `ACCOUNT_PENSIUN`; posisi yang ada tetap diproses). Pesan Telegram hanya bila ada perubahan.
- Pemilik: `paper_engine.py akun list|aktif <nama>|pensiun <nama> --alasan ...`. Menambah persona = tambah baris `account` (kind `tiket`)
  + aturannya di `hermes/skills/arena/SKILL.md`.

## Saldo tiket harian (bergulir)

Tiap hari WIB saldo tiket mulai $1. Hasil bersih posisi tiket yang ditutup hari itu **menambah/mengurangi** saldo (TP → jatah bertambah,
hangus → berkurang). Yang bisa dipakai = saldo − terkunci (margin + fee posisi terbuka) − tereservasi (order hidup). Aturan:
satu tiket ≤ $1 (`tiket_max_per_order`), dan bila saldo < $0,50 (`tiket_min_saldo`) tidak ada tiket baru sampai besok. Akun `acak`
mengikuti aturan sama. Lihat `paper_engine.py budget` (`saldo`, `remaining`, `boleh_buka`, `maks_order_sekarang`).

## Order paper manual

```bash
# tiket: limit LONG BTC 0.001 @ 82700, 100x, TP 83500 (stop = likuidasi)
.venv/Scripts/python.exe scripts/paper_engine.py order --akun tiket --symbol BTCUSDT --sisi LONG --qty 0.001 --lev 100 --harga 82700 --tp 83500 --plan A --pola pullback-ke-level

# swing: wajib --tp dan --sl, margin ≤ $10, R:R ≥ 2,5 setelah fee
.venv/Scripts/python.exe scripts/paper_engine.py order --akun swing --symbol ETHUSDT --sisi SHORT --qty 0.01 --lev 10 --harga 2600 --tp 2400 --sl 2680

.venv/Scripts/python.exe scripts/paper_engine.py orders        # order menunggu
.venv/Scripts/python.exe scripts/paper_engine.py posisi        # posisi terbuka
.venv/Scripts/python.exe scripts/paper_engine.py batal 3       # batalkan order #3
.venv/Scripts/python.exe scripts/paper_engine.py tutup 2       # minta tutup posisi #2 (market di bar berikutnya)
.venv/Scripts/python.exe scripts/paper_engine.py budget
.venv/Scripts/python.exe scripts/paper_engine.py laporan --hari 2026-10-11
.venv/Scripts/python.exe scripts/paper_engine.py ekspor-tiket --hari 2026-10-11   # → jurnal/tiket.csv
```

Order dievaluasi oleh collector pada tick berikutnya (bar yang sudah close). Order yang dibuat
pada menit T baru berlaku dari bar T+1 (tanpa look-ahead). Order tiket kedaluwarsa 23:50 WIB
(`TIDAK_TERISI`); posisi tiket yang masih terbuka ditutup paksa di open bar 23:50 (`EOD`, taker).

### Kode penolakan order

`SYMBOL_UNAVAILABLE`, `LEVERAGE_UNKNOWN` (bracket belum ada untuk simbol itu, cek di aplikasi),
`LEVERAGE_CAP`, `QTY_STEP`, `MIN_QTY`, `MIN_NOTIONAL`, `TICK_SIZE`, `PRICE_BAND`, `LIMIT_CROSSES`
(limit memotong mark; pakai `--market` untuk taker), `BUDGET_TIKET` (margin + fee masuk > sisa $1
hari ini), `TIKET_EOD`, `BUDGET_SWING`, `SWING_MAX_OPEN`, `SWING_NEEDS_SL_TP`, `LIQ_INSIDE_STOP`,
`RR_TOO_LOW`, `BAD_TP`, `BAD_SL`. Order yang ditolak tetap tercatat (`status=REJECTED`).

## Membaca hasil

- `close_reason`: `TP`, `HANGUS` (likuidasi di mark price), `STOP`, `MANUAL`, `EOD`, `FUNDING_LIQ`, `DELISTED`.
- `ambiguous=1` + `alt_outcome`: hasil ditentukan aturan pesimis karena dalam satu bar 1 menit
  dua kejadian sama-sama mungkin (mis. likuidasi dan TP). Alternatif optimisnya dicatat supaya
  statistik bisa dicek ulang dengan kedua asumsi. Laporan harian menampilkan jumlahnya.
- `net_result = pnl − fee + funding`. Untuk `HANGUS`, pnl = −margin (margin saat itu, setelah funding).
- `jurnal/tiket.csv`: satu baris per tiket (`TP|HANGUS|MANUAL|TIDAK_TERISI|SKIP`), kolom
  `aturan_dilanggar` dan `emosi` diisi manual.

## Biaya API (agent Hermes)

```bash
.venv/Scripts/python.exe scripts/budget_guard.py harga
.venv/Scripts/python.exe scripts/budget_guard.py status
.venv/Scripts/python.exe scripts/budget_guard.py laporan --hari 2026-10-11
```
Kill switch: buat file `data/STOP_AGENT` → semua panggilan ditolak sampai file dihapus.

## Tes

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -v
```
Semua tes berjalan tanpa jaringan (pasar sintetis `tests/fixtures.py`).

## Reset

- Hapus semua data paper: tutup collector, hapus `data/paper.sqlite*`. Data pasar tetap.
- Hapus data pasar: hapus `data/pasar.sqlite*`; collector mengisi ulang 48 jam terakhir saat start.
- Retensi otomatis: kline 21 hari (kecuali rentang hidup posisi ±1 jam), snapshot 3 hari,
  peringkat volume 7 hari, log 30 hari.

## Catatan ketelitian simulasi

- Harga likuidasi memakai rumus isolated Binance dengan MMR dan `cum` dari tier bracket notional.
  Nilai di aplikasi Binance bisa berbeda beberapa tick (cadangan fee, pembulatan). Angka final
  selalu dari kalkulator exchange.
- Limit terisi hanya jika harga *menembus* level. Ini masih sedikit optimis dibanding antrean
  order nyata; `TIDAK_TERISI` adalah hasil yang sah dan dipantau.
- **Pengaman breakeven (P-18):** posisi tiket/acak yang punya TP dan belum punya SL, begitu mark menempuh ≥ 80% jalan ke TP
  (`EngineConfig.tiket_breakeven_mfe`), mendapat SL di harga masuk (event `BREAKEVEN`). Hasilnya STOP kecil (fee + slippage),
  bukan hangus, bila harga berbalik. Berlaku sama untuk akun acak supaya perbandingan adil.
- **Autopsi posisi:** `paper_engine.autopsi(id)` / tool `mcp_paper_autopsi_posisi(id)`: MFE (persen jalan ke TP, kapan), MAE (persen
  jalan ke likuidasi), menit di sisi untung/rugi, kembali ke entry setelah MFE, kejadian, pelajaran mekanis. Skill evaluasi-harian
  wajib memanggilnya untuk tiap posisi yang ditutup.
- Interval funding per simbol dibaca dari `fundingInfo` (ada yang 4 jam / 1 jam), tapi
  settlement memakai riwayat `fundingRate` yang sebenarnya, jadi tidak bergantung pada asumsi 8 jam.

## Hermes Agent (otak asisten)

Asisten sehari-hari berjalan di **Hermes Agent** (Nous Research) native Windows; Claude Code hanya membangun proyek.
Rantainya: Telegram/CLI → Hermes → `mcp_server.py` (satu-satunya pintu ke mesin paper) dan → `budget_proxy.py` → Anthropic.

### 1. Instalasi Hermes (dari terminal Anda sendiri, bukan dari Claude Code)
Proses yang dijalankan dari dalam aplikasi Claude melihat folder `AppData` yang tervirtualisasi, sehingga
instalasi dari sana gagal/tidak terlihat oleh Task Scheduler. Jalankan di PowerShell biasa (bukan admin):

```powershell
$env:GIT_CONFIG_COUNT=1; $env:GIT_CONFIG_KEY_0='core.longpaths'; $env:GIT_CONFIG_VALUE_0='true'; iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```
`core.longpaths` hanya berlaku di sesi itu; tanpa ini `git` gagal pada dokumen i18n Hermes ("Filename too long").
Setelah selesai: buka terminal baru, `hermes --version`, `hermes doctor`. Lokasi: `%LOCALAPPDATA%\hermes`
(`config.yaml`, `.env`, `SOUL.md`, `skills\`, `scripts\`, `cron\`).

### 2. Rahasia (jalankan sendiri; jangan pernah lewat chat atau repo)
```bash
setx ANTHROPIC_API_KEY <key-dari-console-anthropic>
```
```bash
hermes config set TELEGRAM_BOT_TOKEN <token-dari-BotFather>
```
```bash
hermes config set TELEGRAM_ALLOWED_USERS <user-id-telegram-anda>
```
`ANTHROPIC_API_KEY` dibaca hanya oleh `budget_proxy.py` (buka terminal baru setelah `setx`). Hermes memegang key dummy.
Pasang juga spend limit di workspace Console Anthropic (mis. $200/bulan) sebagai lapis kedua.

### 3. Satu skrip setup: `hermes\setup_hermes.cmd` (idempoten)
Jalankan dari terminal Anda (atau klik dua kali). Skrip ini:
1. `hermes/sync.py` — menyalin `SOUL.md`, skill `tiket` & `evaluasi-harian`, dan `scripts/pemindai_cron.py` ke `HERMES_HOME`;
2. `hermes/merge_config.py` — mengubah `config.yaml` secara tekstual dengan backup: `cron.catch_up_missed=false`,
   `cron.allow_agent_scheduling=false`, `agent.disabled_toolsets`, `platform_toolsets` cli/telegram/cron →
   `[clarify, memory, skills, mcp-paper]`, dan blok `mcp_servers.paper` (28 tool whitelist);
3. menaruh launcher `crypto-analyst_proxy.vbs`, `crypto-analyst_collector.vbs`, dan `crypto-analyst_dashboard.vbs` di folder **Startup** user
   (proxy & collector otomatis jalan saat login, tanpa jendela; Task Scheduler "saat login" butuh admin di laptop ini);
4. menyalakan proxy & collector sekarang (instance kedua keluar sendiri karena lock), lalu
   `hermes --version`, `hermes doctor`, `hermes mcp test paper` (harus 28 tool), `hermes cron list`.

Log: `logs/hermes_setup.log`. Cek proxy: `curl http://127.0.0.1:8585/healthz` (`key_set` harus `true`).
Log proxy: `logs/budget_proxy.log` (satu baris per panggilan: model, token, biaya). Budget habis → Hermes menerima
HTTP 403 `permission_error: budget_guard: ...` (403 dipilih karena SDK tidak mengulangnya, jadi agent langsung melapor);
kill switch `data/STOP_AGENT` memblokir semua panggilan.

> **Catatan untuk Claude Code di laptop ini:** proses yang dibuat dari dalam aplikasi Claude (paket MSIX) melihat
> `AppData` yang tervirtualisasi dan tugas terjadwal yang dibuatnya hanya "Queued". Cara yang terbukti bekerja:
> `explorer.exe "C:\Users\hp\crypto-analyst\hermes\setup_hermes.cmd"` (Explorer menjalankan skrip di luar sandbox).
> Untuk perintah Hermes lain: tulis satu perintah per baris ke `logs/hermes_cmd.txt`, lalu
> `explorer.exe "...\hermes\run_logged.cmd"`; hasilnya di `logs/hermes_run.log`.

### 4. Memperbarui aset setelah `git pull`
```bash
hermes\setup_hermes.cmd
```
`hermes/sync.py --check` mengembalikan 1 jika aset di HERMES_HOME tertinggal dari repo. `merge_config.py` tidak mengubah
apa pun bila sudah sesuai. Setelah mengubah skill/SOUL: `hermes gateway restart`.

### 5. Gateway, Telegram, cron
Wizard `hermes setup` sudah memasang `Hermes_Gateway.vbs` di folder Startup (fallback karena Task Scheduler butuh admin).
`hermes gateway start|status|stop|restart`. Cron (baris `hermes cron create` dari `hermes/sync.py --snippet`; `--script` harus relatif terhadap `HERMES_HOME\scripts`): `pemindai-tiket`
tiap 5 menit (skrip tanpa LLM; agent hanya dibangunkan bila ada kandidat), `evaluasi-harian` 23:55 WIB, dan `notif-paper`
tiap menit (`--no-agent`: stdout skrip dikirim apa adanya ke Telegram, kosong = diam; nol biaya LLM), serta `uji-hipotesis`
23:40 WIB (`--no-agent`; menilai hipotesis jatuh tempo sebelum evaluasi harian 23:55), dan `psikologi` menit ke-7 tiap jam
(`--no-agent`, diam; mengisi `data/psikologi.sqlite`).
`evaluasi-susulan` (08:20, 11:20, 14:20, 17:20, 20:20) hanya membangunkan agent bila catatan harian kemarin belum ada — pengganti
evaluasi 23:55 yang terlewat karena laptop mati. Cron lain yang terlewat **tidak** dikejar (`catch_up_missed=false`).
`hermes cron list`, `hermes cron run <nama>` untuk uji manual, `hermes cron pause <nama>`.
`hermes doctor` menyarankan memindahkan entri `custom_providers` ke `providers.<key>.api`; jalur `model.provider: custom`
+ `base_url` tetap berfungsi, jadi ini opsional.

### 5b. Perintah di Telegram
Menu `/` dibatasi 14 perintah (`platforms.telegram.extra.command_menu`, mode `replace`), supaya perintah proyek tidak
tenggelam di antara ±120 perintah bawaan Hermes. Pesan kaya (`rich_messages: true`) merender tabel/daftar asli.

| Perintah | Fungsi |
|---|---|
| `/posisi` | Posisi terbuka + order menunggu |
| `/budget` | Sisa budget tiket, swing, biaya API vs cap |
| `/laporan [YYYY-MM-DD]` | Laporan paper harian + ringkasan keputusan agent |
| `/cek <SIMBOL> <LONG\|SHORT> [entry] [tp]` | Nilai setup tiket, pasang order paper atau SKIP |
| `/batal <id>` · `/batal semua` · `/batal posisi <id>` | Batalkan order / minta tutup posisi |
| `/status` | Kesehatan collector, proxy, pemindai, kill switch |
| `/psikologi` | Panel psikologi pasar BTC/ETH: zona takut/serakah per indikator, divergensi, siapa yang terjebak |
| `/referensi <kata kunci>` | Cari & kutip buku referensi (judul, bab, halaman, kutipan ≤ 15 kata) |
| `/arena-papan` | Papan peringkat 4 persona arena vs pembanding acak |
| `/tiket`, `/evaluasi-harian` | Skill inti (dipakai cron; bisa dipanggil manual) |
| `/help`, `/new`, `/usage` | Bawaan Hermes (`/whoami`, `/model`, `/commands` keluar dari menu agar muat 14; tetap bisa diketik) |

Setiap perintah adalah satu sesi agent (≈ $0,02–0,10 lewat proxy). Chat bebas juga bisa; agent memilih skill sendiri.
Jika menu tidak terlihat: tutup dan buka lagi chat bot (klien Telegram men-cache menu), atau ketik `/commands`.

### 6. Uji cepat
- `hermes -z "jam dan budget tiket sekarang?"` → jawaban memuat umur tick collector.
- Telegram: "posisi dan order" → sama dengan `paper_engine.py posisi` / `orders`.
- Telegram: "pasang tiket BTC LONG limit <harga> 100x TP <harga>" → `paper_engine.py orders` memuat `created_by=hermes`.
- "jalankan perintah shell" → agent menjawab tidak punya tool itu.
- `budget_guard.py status` menunjukkan panggilan Opus dengan biaya; `logs/budget_proxy.log` berisi barisnya.

### 7. Troubleshooting
| Gejala | Penyebab / tindakan |
|---|---|
| Hermes: error 403 `budget_guard` | Cap tercapai atau kill switch; `budget_guard.py status`; hapus `data/STOP_AGENT` bila sengaja |
| Hermes: koneksi ke 127.0.0.1:8585 ditolak | Proxy mati: `schtasks /Run /TN "crypto-analyst budget proxy"`; lihat `logs/budget_proxy.out.log` |
| Proxy: `env ANTHROPIC_API_KEY tidak diset` | `setx` lalu buka terminal baru / login ulang agar Task Scheduler membaca env user |
| `hermes mcp test paper` gagal start | Cek `logs/mcp_server.log`; pastikan `command` menunjuk `.venv\Scripts\python.exe`; tambahkan `SYSTEMROOT: C:\Windows` di `env` jika Python mengeluh soal random |
| Tool menjawab `status_data: BASI` | Collector mati; `collector.py status`; jalankan tugas collector |
| Agent memasang order padahal kandidat jelek | Periksa `jurnal/agent/<hari>.md`; sesuaikan aturan di `hermes/skills/tiket/SKILL.md`, `sync.py`, uji lagi |
| Proses `python.exe` MCP tertinggal | Gateway dihentikan paksa; tutup lewat Task Manager (`idle_timeout_seconds` membersihkan yang idle) |

## Pemindai mekanis (`scripts/pemindai.py`)

Skrip **tanpa LLM** yang dijalankan cron Hermes `pemindai-tiket` tiap 5 menit (`1-59/5 * * * *`; menit :00 terlalu dini
karena bar 1m tersimpan pada detik :05) lewat `HERMES_HOME\scripts\pemindai_cron.py`. Membaca `pasar.sqlite` (readonly) dan
`paper.sqlite` (hanya metode baca), menulis `data/kandidat.sqlite` (`pemindai_run`, `kandidat`). Agent (Opus 5.5, effort low)
hanya dibangunkan bila baris terakhir stdout persis `{"wakeAgent": true}`; `{"wakeAgent": false}` = tidak ada biaya.

Uji manual (tidak menyimpan, memindai walau gate menahan, tabel per simbol dengan alasan):
```bash
.venv/Scripts/python.exe scripts/pemindai.py --once
```
Opsi: `--json` (keluaran mesin), `--sekarang 2026-10-11T10:01` (jam uji), `--n 30` (universe), `--jam-mulai/--jam-akhir`.
Mode cron (menyimpan hasil): `--cron`. Log: `logs/pemindai.log`.

Cara kerja per simbol (top 20 volume ∪ simbol berposisi):
1. Bar 1m 48 jam → bucket 5m/15m/1h **yang sudah lengkap** (`data_until` = akhir bar tersimpan, dibatasi tick collector − 5 s;
   bukan jam dinding).
2. Level = klaster swing 5m ∪ 15m (lebar 0,5×ATR), hanya ≥ 2 sentuhan; level terdekat dari mark dan jaraknya dalam ATR 5m (maks 2).
3. Arah dugaan: BREAKOUT_GAGAL atas → SHORT / bawah → LONG; WICK bawah di level → LONG / atas → SHORT; tanpa penolakan:
   level di bawah mark → LONG (pullback ke support), di atas → SHORT.
4. Skor: dekat level (≤ 0,5×ATR 5m) +2; WICK segar (≤ 3 bucket 5m) searah +2; BREAKOUT_GAGAL segar searah +2; VOL +1;
   SUDAH_LARI (|24 jam| > 20%) −1; FUNDING_EKSTREM melawan arah −1. Flag tanpa skor: IMPULS, KOMPRESI, MELAWAN_TREN_15M, `*_LAMA`.
5. Leverage layak = baris `tabel_leverage` (entry = level, sisa budget tiket hari ini) dengan jarak likuidasi ≥ 2×ATR 5m;
   dicoba 150/125/100x, atau leverage maks simbol bila lebih kecil.

Kandidat = skor ≥ 3 **dan** ada leverage layak; peringkat (skor, jarak), maksimal 3, masing-masing mendapat ID `K<id>`.

Gate (yang pertama gagal menang; alasan ada di baris pertama stdout dan `pemindai_run.alasan`):

| Gate | Alasan di stdout |
|---|---|
| G1 | `data basi` — tick collector > 180 s |
| G2 | `di luar jam 07:00–22:30 WIB` |
| G3 | `budget tiket habis` — sisa < $0,10 |
| G4 | `sudah 2 order tiket hidup` |
| G5 | `cap 12 wake/hari tercapai` |
| G6 | simbol dengan order/posisi → `Ditahan: … (ada order/posisi)` |
| G7 | `cooldown` 30 menit per simbol, kecuali skor naik |
| G8 | `tidak ada kandidat (N simbol dipindai)` |
| G9 | `N tiket HANGUS beruntun hari ini (playbook P-09)` — 2 likuidasi beruntun → berhenti sampai hari berikutnya (dicek sebelum pemindaian, `max_hangus_beruntun`) |

Membaca baris kandidat: `K7 UNIUSDT SHORT skor 4 | mark 7.5635 | level 7.563 (5 sentuhan 5m, 0.03×ATR5m di bawah; wick atas
menolak level) | jejak BREAKOUT_GAGAL_LAMA, WICK | ATR5m 0.0203 (0.27%) | 24j +1.5% | funding +0.0042% | tren15m turun |
lev layak: 75x liq 7.618 (2.7×ATR5m)`. Agent wajib memakai `plan_id` persis `K<id>` saat memasang order
(`mcp_paper_kandidat_terbaru` mengembalikan field `plan_id` dari run terakhir yang membangunkan agent).

Knob: `PemindaiConfig` di `scripts/pemindai.py` (`top_n`, `lookback_h`, `score_min`, `x_atr5m_min`, `cooldown_min`,
`max_wake_per_day`, `jam_mulai`/`jam_akhir`, `leverages`). Perkiraan biaya: ≤ 12 wake/hari × $0,05–0,15 < $2/hari.

Verifikasi nol biaya: catat `budget_guard.py status`, jalankan `hermes cron run pemindai-tiket` saat tidak ada kandidat
(mis. gate G4 aktif) → `kandidat.sqlite` mendapat baris `pemindai_run` dengan `wake=0` dan `api_calls` tidak bertambah.
Dari Telegram: `/status` (field `pemindai`), atau minta "kandidat terbaru".

| Gejala | Tindakan |
|---|---|
| Ingin melihat run cron yang tidak membangunkan agent | Tidak ada pesan Telegram (`delivery_outcome=suppressed`); lihat `%LOCALAPPDATA%\hermes\cron\output\<job_id>\*.md`, `cron\executions.db`, atau `pemindai_run` di `data/kandidat.sqlite` (`/status` di Telegram) |
| `pemindai gagal (exit 1)` di Telegram/log | `pemindai.py --once` di terminal untuk melihat traceback; `logs/pemindai.log` |
| Selalu `data basi` | Collector mati/tersendat: `collector.py status`, `logs/collector.log` |
| Tidak pernah ada kandidat | Normal di pasar datar; di tabel `--once` banyak `skor 2 < 3` = dekat level tanpa penolakan. Ubah `score_min` hanya setelah beberapa hari data |
| Kandidat ada tapi agent tidak memasang order | Alasan SKIP di `jurnal/agent/<hari>.md`; aturan di `hermes/skills/tiket/SKILL.md` |
| Order terisi/TP tapi tidak ada notifikasi Telegram | `hermes cron list` → `notif-paper` aktif? `notifikasi.py --uji 3` menampilkan kejadiannya? `logs/notif_cron.log` berisi error? Kursor `data/notif.json` melompat (`--kursor <id>` untuk mengirim ulang) |

## Notifikasi Telegram (`scripts/notifikasi.py`)

Cron Hermes `notif-paper` (`* * * * *`, `--no-agent --script notif_cron.py --deliver telegram --failure-deliver local`)
menjalankan `scripts/notifikasi.py --cron` tiap menit **tanpa LLM**: membaca `paper.sqlite` (`events` ⋈ `orders` ⋈ `positions`,
readonly), mengirim kejadian baru sejak kursor `data/notif.json`, lalu memajukan kursor. Stdout kosong = Hermes tidak
mengirim apa pun. Kali pertama (tanpa kursor) hanya menandai kejadian terakhir — tidak mengirim riwayat lama.

Contoh pesan:
```
📣 Paper trading — 2 kejadian baru
10:04 ✅ TERISI posisi #4 tiket BTCUSDT LONG 0.001 @ 82700 (THROUGH) 100x · margin $0.8270 · liq 82201.8 · TP 83000 · SL - · K7
10:05 🎯 TP posisi #4 tiket BTCUSDT LONG keluar 83000 · net +$0.2669 (pnl +$0.3000, fee $0.0331, funding +$0.0000)
```
Jenis: 🆕 order baru, ❌ dibatalkan, ⌛ kedaluwarsa (tidak terisi), ✅ terisi, 🎯 TP, 🛑 STOP, 🔚 tutup manual, 🌙 tutup EOD,
💀 likuidasi (termasuk karena funding), ⏳ permintaan tutup; `⚠️ AMBIGU` bila mesin menandai ambiguitas intrabar.
Maksimal 20 kejadian per pesan (sisanya diringkas "+n lebih lama").

```bash
.venv/Scripts/python.exe scripts/notifikasi.py --uji 5
```
`--uji N` mencetak N kejadian terakhir tanpa mengubah kursor; `--kursor ID` mengirim ulang kejadian setelah ID pada run
berikutnya; `--reset` melompat ke kejadian terakhir. Log: `logs/notifikasi.log`; kegagalan pembungkus: `logs/notif_cron.log`
(pembungkus selalu diam saat gagal supaya Telegram tidak dibanjiri; `--failure-deliver local` menahan notice Hermes).
Kejadian yang dibuat agent lewat Telegram (order baru) tetap dinotifikasi — itu konfirmasi bahwa mesin menerimanya.

## Baseline acak (akun `acak`)

Setiap order **tiket** yang dipasang agent/CLI (bukan mesin) otomatis mendapat bayangan di akun paper `acak`: simbol, leverage,
qty, dan jarak TP/SL sama, tetapi **sisi acak** dan **entry market** di open bar berikutnya (± slippage). Sisi =
`random.Random(f"acak-v1:{order_id}").choice(LONG, SHORT)` — deterministik, bisa diverifikasi ulang. Jarak TP/SL disimpan
relatif (`orders.tp_pct/sl_pct`) dan diresolusi saat terisi, dibulatkan ke tick menjauh dari untung. Akun acak punya budget
cermin $1/hari sendiri (`BUDGET_ACAK`, `ACAK_EOD`), ditutup paksa 23:50, dan **tidak pernah** menghalangi order asli: bila
bayangan gagal, hanya event `ACAK_SKIP` yang dicatat. Membatalkan order tiket ikut membatalkan bayangan yang belum terisi.
Kejadian akun acak tidak dinotifikasi ke Telegram (hanya satu baris 🎲 saat dibuat).

```bash
.venv/Scripts/python.exe scripts/paper_engine.py budget
```
menampilkan tiket, swing, dan acak; `laporan` memuat blok "Tiket vs acak (hari ini)". Matikan dengan `EngineConfig.acak_enabled=False`
(hanya untuk uji). Skema paper v2: kolom `tp_pct/sl_pct` ditambah otomatis saat mesin pertama kali jalan dengan kode baru —
collector **harus dimulai ulang** setelah update agar mesin di dalamnya mengenal kolom itu.

## Statistik kelulusan (`scripts/evaluasi.py`)

```bash
.venv/Scripts/python.exe scripts/evaluasi.py
```
Markdown (atau `--json`, `--sejak YYYY-MM-DD`) per akun tiket/swing/acak: posisi selesai, expectancy per trade setelah fee,
win rate, TP/HANGUS/STOP/EOD/TIDAK_TERISI, ambigu, stabilitas (tanpa 5% trade terbaik), bulan positif; blok tiket vs acak
(selisih mean + uji permutasi 2000×, sign test berpasangan atas pasangan `entry_order_id` ↔ `ACAK:<id>`); kepatuhan
(order tiket setelah 22:30 WIB = pelanggaran agent; percobaan yang ditolak mesin dicatat terpisah); tabel kriteria §19.7 dengan
status `lulus | belum (…) | tidak tersedia (…)`. Di bawah 10 sampel semua angka ditulis "tidak tersedia" — ini disengaja.
Agent memakai tool `mcp_paper_statistik_lulus` yang mengembalikan data yang sama.

## Uji hipotesis & pelajaran (`scripts/uji_hipotesis.py`)

Agent menulis hipotesis **terstruktur** lewat `mcp_paper_tulis_hipotesis(pola, symbol, tf, jenis, arah, nilai, batas_hari, kondisi)`
→ `pasar/hipotesis.jsonl` (append, penulis mcp_server). `jenis`: `sentuh_harga` (nilai = harga target), `gerak_atr`
(nilai = kelipatan ATR14 tf dari harga saat dibuat), `close_arah` (close bar terakhir horizon di sisi `arah`). `tf` 1h|4h|1d,
`batas_hari` 1–7, maks 3/hari. Horizon mulai dari bucket **setelah** saat dibuat (tanpa look-back).

Cron Hermes `uji-hipotesis` (`40 23 * * *`, `--no-agent`) menjalankan `uji_hipotesis.py --cron`:
1. hipotesis yang jatuh tempo (batas + 10 menit) dinilai dengan `kline_1h` (4h/1d di-resample): `benar | salah | ambigu`
   (ambigu bila bar < 90% dari yang diharapkan);
2. **baseline** per hipotesis: 200 titik awal acak dalam 120 hari data, prediksi yang sama (jarak relatif/kelipatan ATR) →
   seberapa sering kebetulan terjadi; `rate` None bila < 30 titik valid;
3. **pelajaran** per pola (§16.6): sampel ≥ 10 dan hit rate ≥ baseline + 15 poin → `L-NN aktif`; dinilai ulang tiap 30 hari
   dengan hasil 90 hari terakhir; turun ke ≤ baseline + 5 poin → `pensiun` (alasan dicatat); maks 15 aktif;
4. menulis `pasar/hipotesis-hasil.jsonl` (append), `pasar/pelajaran.jsonl`, dan view `pasar/hipotesis.md`, `pasar/pelajaran.md`
   (ditulis ulang; jangan diedit manual). Stdout = pesan Telegram hanya bila ada yang dinilai/berubah.

```bash
.venv/Scripts/python.exe scripts/uji_hipotesis.py --once
```
(`--sekarang 2026-10-14T23:40` untuk uji, `--json`). Log: `logs/uji_hipotesis.log`, pembungkus `logs/uji_cron.log`.
`mcp_paper_baca_memori("hipotesis")` merender tabel langsung dari jsonl + hasil, jadi agent melihat hipotesis baru tanpa menunggu
run malam. Usulan pelajaran dari agent (`pasar/pelajaran-usulan.md`, status `uji`) **tidak** otomatis naik: pemilik yang
memutuskan dengan mengedit file itu; skrip hanya melaporkan jumlahnya.

| Gejala | Tindakan |
|---|---|
| Hipotesis lama berstatus `terbuka` terus | `uji_hipotesis.py --once`: cek jatuh tempo (batas + 10 menit) dan `kline_1h` simbolnya (`collector.py status`) |
| Banyak `ambigu` | Simbol baru/koin dengan `kline_1h` kurang dari horizon; atau bar 1d (UTC) belum lengkap — tunggu run berikutnya |
| `tulis_hipotesis` ditolak "ATR tidak tersedia" | `kline_1h` simbol itu belum terisi (butuh > 15 bar tf); pakai `sentuh_harga`/`close_arah` |

## Panel psikologi pasar (`scripts/psikologi.py`)

Cron Hermes `psikologi` (`7 * * * *`, `--no-agent`, diam) menjalankan `psikologi.py --cron`: mengumpulkan 12 indikator §16.2 untuk
BTCUSDT, ETHUSDT (per simbol) dan pasar luas (`*`), memberi zona, lalu menyimpan ke `data/psikologi.sqlite` (`panel`, `panel_run`).
Agent membacanya lewat `mcp_paper_panel_psikologi(symbol)`; pemilik lewat `/psikologi`; catatan harian otomatis mendapat frontmatter
`panel_takut_ekstrem`, `panel_serakah_ekstrem`, `fng`, `funding_btc`.

| Indikator | Sumber | Zona awal (takut ≤ · serakah ≥) |
|---|---|---|
| Fear & Greed | alternative.me | 25 · 75 |
| Funding rate terakhir | `pasar.sqlite` mark_snapshot (tanpa jaringan) | −0,01% · +0,03% |
| Δ OI 24 jam + Δ harga 24 jam | Binance `futures/data/openInterestHist` (nilai USD) + `kline_1h` | kapitulasi: OI ≤ −5% & harga ≤ −3% (takut); penumpukan: OI ≥ +10% & |harga| < 1% (serakah) |
| L/S rasio akun | Binance `globalLongShortAccountRatio` 1h | 0,8 · 2,0 |
| L/S top trader (posisi) | Binance `topLongShortPositionRatio` 1h | hanya catatan/divergensi |
| Taker buy/sell (rata-rata 4 jam) | Binance `takerlongshortRatio` 1h | 0,8 · 1,2 |
| Likuidasi long/short 24 jam | OKX `liquidation-orders` (±100 order terakhir — **sampel terbatas**) | dominasi > 2× |
| Premium Coinbase | Coinbase BTC-USD ÷ (Binance spot × Coinbase USDT-USD) − 1 | −0,10% · +0,10% |
| Premium IDR | Indodax btcidr ÷ (usdtidr × Binance spot) − 1 (bukan kurs resmi) | 0% · +1,0% |
| Δ suplai stablecoin 7 hari | DefiLlama `stablecoincharts/all` | −1% · +1% |

Setelah ≥ 90 hari data (≥ 100 titik), zona indikator memakai persentil 10/90 dari datanya sendiri (`mode_zona: persentil`;
`campuran` saat sebagian). **Tidak ada skor gabungan** — hanya hitungan indikator di zona ekstrem dan daftar **divergensi**
(harga naik & OI turun; harga turun & OI naik; funding tinggi & taker sell; ritel long vs top trader short; FNG serakah &
premium Coinbase negatif). Sumber yang gagal/diblokir → `nilai NULL`, zona `tidak tersedia`, alasan di `catatan`; run tetap `ok`.
Host `api.exchange.coinbase.com` dan `www.okx.com` ikut diresolusi lewat DoH (`common.BINANCE_HOSTS`).

```bash
.venv/Scripts/python.exe scripts/psikologi.py --once
```
(`--lihat` hanya membaca DB, `--symbol ETHUSDT`, `--json`, `--sekarang`). Log: `logs/psikologi.log`; pembungkus `logs/psikologi_cron.log`.
Retensi 400 hari. Weight Binance: 8 permintaan/jam (weight 1) — tidak memengaruhi collector.

| Gejala | Tindakan |
|---|---|
| Semua indikator Binance `tidak tersedia` | Blokir ISP berubah (`BlockedError` di log) → cek `looks_blocked`, DoH; indikator lain tetap jalan |
| Likuidasi selalu 0 | Endpoint OKX hanya memberi ±100 order terakhir; bila semuanya > 24 jam, nilainya 0 — baca `catatan` |
| `/psikologi` menjawab BASI | Cron `psikologi` tidak jalan > 3 jam: `hermes cron list`, `logs/psikologi_cron.log` |

## Referensi buku & playbook (`scripts/konversi_buku.py`, `scripts/referensi.py`)

Ebook (PDF/EPUB yang dibeli resmi / gratis legal) ditaruh di `referensi/buku/` (gitignored). Konversi per bab:
```bash
.venv/Scripts/python.exe scripts/konversi_buku.py referensi/buku/Buku.pdf slug-buku --judul "Judul" --penulis "Penulis"
```
Hasil: `referensi/buku/<slug>/bab-NN.md` (frontmatter `judul_buku, penulis, bab, judul_bab, halaman, sumber, metode`) + `_meta.json`.
Bab dari bookmark PDF bila ada; tanpa bookmark → heuristik judul berfont besar (3–80 kandidat); gagal → potong tiap `--per-halaman`
(default 10; `--paksa-halaman` memaksa). PDF hasil scan (tanpa lapisan teks) → `_meta.json` `perlu_ocr`, exit 2: OCR dulu di luar
proyek. Judul bab hasil heuristik bisa terpotong — rapikan di `referensi/indeks.md`, bukan di file bab.

- `referensi/indeks.md` (di-commit): peta bab per buku — judul, ringkasan 1 kalimat, kata kunci — ditulis Claude Code setelah
  membaca hasil konversi; `mcp_paper_baca_memori("indeks")`.
- `referensi/playbook.md` (di-commit): aturan pribadi berstatus `aktif` (wajib; sebagian ditegakkan mesin/skill tiket), `uji`
  (usulan dari buku; dipertimbangkan), `pensiun`. **Hanya pemilik yang mengubah status.** Agent membacanya di skill `tiket`
  (langkah 4b) dan mencatat pelanggaran di jurnal (`aturan_dilanggar=P-xx`). Maks 25 aturan.
- Tool: `mcp_paper_cari_referensi(kata_kunci, n)` (semua kata harus muncul; skor = jumlah kemunculan; cuplikan ≤ 320 karakter),
  `mcp_paper_baca_referensi(slug, bab, mulai)` (≤ 12k karakter per panggilan). Tanpa embedding/vector DB (§15.1).
- Telegram: `/referensi <kata kunci>`; aturan SOUL "Referensi": konsep psikologi/risiko/pola → cari & kutip judul + bab.

Buku saat ini: `mastering-trading-psychology` (14 bab heuristik; bab 1–4 adalah halaman depan), `panduan-analisis-crypto`
(9 bab), `goodcrypto-pola-chart` (3 bab). Menambah buku: taruh file, jalankan konversi, minta Claude Code menambah entri indeks.

| Gejala | Tindakan |
|---|---|
| Bab terlalu banyak/sedikit | `--per-halaman 15` atau `--paksa-halaman`; konversi ulang menimpa bab lama |
| `cari_referensi` kosong | Kata kunci bahasa Inggris, 1–3 kata; coba `salah_satu=true`; cek `indeks.md` untuk istilah buku |
| `perlu_ocr` | Jalankan OCR (mis. ocrmypdf) di luar proyek, lalu konversi ulang |

## Dashboard lokal (`scripts/dashboard.py`)

Buka **http://127.0.0.1:8586** (hanya lokal; autostart lewat `crypto-analyst_dashboard.vbs`; manual: `run_dashboard.cmd` atau
`.venv/Scripts/python.exe scripts/dashboard.py`). Baca saja — tidak menulis DB mana pun; polling ringkasan 5 s, chart 15 s.

- **Chart**: candlestick + volume dari `kline_1m` (1m/5m/15m) atau `kline_1h` (1h/4h/1d), sumbu waktu WIB; marker dari mesin paper:
  ▲/▼ entry, ● TP (hijau), ■ likuidasi (merah), ● STOP/EOD/manual (abu), ● kecil kuning = order kedaluwarsa/batal; garis harga = entry,
  TP, SL, liq posisi terbuka dan harga order limit hidup. Akun `acak` disembunyikan kecuali dicentang. Dropdown simbol: aktif →
  pernah ditradingkan → top 30 volume.
- **Panel kanan**: budget tiket/swing/acak, posisi terbuka (unrealized dari mark terakhir), order menunggu, 8 eksekusi cron Hermes terakhir.
- **Bar status**: jam, collector (OK/BASI + umur), pemindai (run terakhir, wake hari ini, alasan gate), biaya API hari ini/bulan vs cap, KILL SWITCH.
- **Riwayat**: kurva ekuitas kumulatif (tiket/swing/acak), posisi ditutup, order kedaluwarsa/batal/ditolak, ringkasan harian; klik baris →
  chart lompat ke simbolnya. **Statistik** = `evaluasi.compute`. **Pemindai** = run wake terakhir + 24 run. **Psikologi** = panel BTC/ETH.
  **Jurnal** = jurnal agent, catatan harian, hipotesis, pelajaran, playbook, indeks.
- API JSON (GET): `/api/ringkasan`, `/api/simbol`, `/api/candles?symbol&tf&n`, `/api/marker?symbol`, `/api/riwayat?akun&hari&symbol`,
  `/api/ekuitas`, `/api/statistik`, `/api/psikologi?symbol`, `/api/kandidat`, `/api/teks?jenis&hari`.

| Gejala | Tindakan |
|---|---|
| Chart kosong, tabel terisi | Pustaka `lightweight-charts` dari unpkg tidak termuat (offline) — muat ulang saat online; tabel tetap jalan |
| `tidak ada bar` untuk simbol | Collector hanya menyimpan top 30 volume + simbol berposisi; pilih simbol lain |
| Halaman tidak terbuka | `run_dashboard.cmd`; cek `logs/dashboard.log` / `dashboard.out.log`; port 8586 bentrok → `--port` |

## Milestone berikutnya

- Referensi: tambah buku prioritas §15.3 (Douglas, Tharp, Brooks, Volman) saat tersedia; OCR untuk PDF scan.
- Tuning pemindai dari data nyata (`lookback_h` 96 untuk level 15m, `score_min`, bobot VOL, `leverages`).
