# Panduan Operasi — Milestone 1 (mesin paper trading)

Spesifikasi lengkap: `docs/rencana-asisten-crypto.md`. Konvensi proyek: `CLAUDE.md`.

## Komponen

| File | Peran | Penulis DB |
|---|---|---|
| `scripts/collector.py` | Mengambil kline 1m (harga terakhir + mark), kline 1h (120 hari), funding, snapshot mark, peringkat volume; memanggil mesin tiap menit | `data/pasar.sqlite` |
| `scripts/pemindai.py` | Pemindai kandidat tiket mekanis (tanpa LLM) tiap 5 menit lewat cron Hermes; membangunkan agent hanya bila ada kandidat | `data/kandidat.sqlite` |
| `scripts/paper_engine.py` | Simulasi order/posisi/likuidasi/fee/funding; CLI order manual; laporan | `data/paper.sqlite` |
| `scripts/budget_guard.py` | Biaya API Anthropic: cap harian $10, bulanan $190, per panggilan $1; kill switch | `data/budget.sqlite` |
| `scripts/budget_proxy.py` | Proxy 127.0.0.1:8585 → api.anthropic.com untuk Hermes; menegakkan cap lewat budget_guard; memegang API key asli | (lewat budget_guard) |
| `scripts/mcp_server.py` | Server MCP stdio untuk Hermes: 22 tool (data pasar, order paper, laporan, jurnal, hipotesis) | `jurnal/agent/`, `pasar/harian/`, `pasar/hipotesis.md`, `pasar/pelajaran-usulan.md` |
| `scripts/analisis.py` | Resample, EMA/RSI/ATR Wilder, swing & level, jejak psikologi, tabel leverage, top volume | — |
| `scripts/common.py` | Waktu WIB, resolver DoH, HTTP + pacing weight, SQLite, Decimal, logging | — |
| `hermes/` | Aset Hermes: `SOUL.md`, skill `tiket` & `evaluasi-harian`, pembungkus cron, snippet config, `sync.py` | → `HERMES_HOME` |
| `run_collector.cmd`, `run_budget_proxy.cmd` | Pembungkus untuk Task Scheduler (tanpa jendela konsol) | — |

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
   `[clarify, memory, skills, mcp-paper]`, dan blok `mcp_servers.paper` (22 tool whitelist);
3. menaruh launcher `crypto-analyst_proxy.vbs` dan `crypto-analyst_collector.vbs` di folder **Startup** user
   (proxy & collector otomatis jalan saat login, tanpa jendela; Task Scheduler "saat login" butuh admin di laptop ini);
4. menyalakan proxy & collector sekarang (instance kedua keluar sendiri karena lock), lalu
   `hermes --version`, `hermes doctor`, `hermes mcp test paper` (harus 22 tool), `hermes cron list`.

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
tiap 5 menit (skrip tanpa LLM; agent hanya dibangunkan bila ada kandidat) dan `evaluasi-harian` 23:55 WIB.
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
| `/tiket`, `/evaluasi-harian` | Skill inti (dipakai cron; bisa dipanggil manual) |
| `/help`, `/new`, `/usage`, `/commands`, `/whoami`, `/model` | Bawaan Hermes |

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

## Milestone berikutnya

- **Milestone 3**: baseline acak (order acak dengan budget yang sama) sebagai pembanding, kriteria lulus §19.7,
  memori pasar lengkap (§16: pelajaran yang dinilai skrip), referensi buku (§15), tuning pemindai dari data nyata
  (`lookback_h` 96 untuk level 15m, `score_min`, `leverages`).
