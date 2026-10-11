# Panduan Operasi — Milestone 1 (mesin paper trading)

Spesifikasi lengkap: `docs/rencana-asisten-crypto.md`. Konvensi proyek: `CLAUDE.md`.

## Komponen

| File | Peran | Penulis DB |
|---|---|---|
| `scripts/collector.py` | Mengambil kline 1m (harga terakhir + mark), funding, snapshot mark, peringkat volume; memanggil mesin tiap menit | `data/pasar.sqlite` |
| `scripts/paper_engine.py` | Simulasi order/posisi/likuidasi/fee/funding; CLI order manual; laporan | `data/paper.sqlite` |
| `scripts/budget_guard.py` | Biaya API Anthropic: cap harian $10, bulanan $190, per panggilan $1; kill switch | `data/budget.sqlite` |
| `scripts/common.py` | Waktu WIB, resolver DoH, HTTP + pacing weight, SQLite, Decimal, logging | — |
| `run_collector.cmd` | Pembungkus untuk Task Scheduler (tanpa jendela konsol) | — |

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

## Biaya API (untuk agent di milestone 3)

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

## Milestone berikutnya

- **Milestone 2**: skrip asisten harian (`topvolume`, `tiket`, `snapshot`, `ohlcv`, `jejak_grafik`,
  `psikologi`, `derivatif`, `makro`, `unlock`, `posisi`, `stats_jurnal`), CLAUDE.md profil trader
  lengkap (§6), 4 slash command, memori pasar (§16), referensi buku (§15).
- **Milestone 3**: `pemindai.py` (tanpa LLM) + `agent.py` (Haiku 5.5 saring, Opus 5.5 putuskan)
  di atas `paper_engine.place_order` dan `budget_guard.call`, baseline acak, kriteria lulus §19.7.
