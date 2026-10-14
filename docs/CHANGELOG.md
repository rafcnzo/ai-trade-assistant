# CHANGELOG

Format: entri terbaru di atas. Setiap entri: tanggal WIB, perangkat, apa yang berubah, kenapa, file terdampak.
Perubahan kode dan entri changelog masuk dalam commit yang sama.

## 2026-10-14 (siang, 13:40) — laptop Windows — belajar dari kesalahan: gate R:R P-19, uji hipotesis ikut susulan, evaluasi 21:30

**Apa:** `paper_engine.py`: `tiket_min_rr` (bawaan 0,5; env `PAPER_TIKET_MIN_RR`) — order persona dengan TP ditolak `RR_TOO_LOW` bila untung bersih di TP
< 0,5× risiko hangus (margin + fee masuk); `hermes/scripts/susulan_cron.py` menjalankan `uji_hipotesis.py --cron` sebelum membangunkan agent
(hipotesis jatuh tempo yang terlewat dinilai, hasil diteruskan); `hermes/cron.cmd` + Hermes: `evaluasi-harian` 23:55 → 21:30 (prompt menyebut EOD
kemarin), `uji-hipotesis` 23:40 → 21:15; skill evaluasi-harian + teks susulan disesuaikan; playbook P-19 aktif (U-001 diterima pemilik); tes T28,
fixtures menyetel `PAPER_TIKET_MIN_RR=0` untuk fixture lama (142 hijau).

**Kenapa:** laporan user 14 Okt: evaluasi malam tidak pernah jalan (laptop mati 23:55; susulan pagi yang bekerja), uji hipotesis tidak pernah jalan
(0 hipotesis dinilai), dan AI mengulang pola rugi yang sudah diusulkan agent sendiri (hangus ≈ −$1 vs TP +$0,1–0,3) karena usulan menunggu keputusan pemilik.
**File:** `scripts/paper_engine.py`, `hermes/{cron.cmd,scripts/susulan_cron.py,skills/evaluasi-harian/SKILL.md}`, `referensi/playbook.md`, tests, docs.

## 2026-10-13 (pagi, 09:40) — laptop Windows — dashboard dibangun ulang: "Meja analis"

**Apa:** `dashboard/{index.html,style.css,app.js}` ditulis ulang (skill impeccable, code-led): satu halaman gulir dengan lompat-bagian; bagian
Sekarang = meja empat analis (persona) dengan posisi/order sebagai kalimat kaya + P/L hidup, saldo bergulir, keputusan terakhir, baris acak/swing,
dan aliran kejadian mesin; Pasar, Peringkat (+ syarat lulus), Riwayat (+ perjalanan modal/drawdown), Konteks (suasana, mesin, biaya), Catatan AI.
Semua keterangan pindah ke tooltip (hover + fokus keyboard, Esc). Palet: arang hangat, tinta gading, aksen kuningan, mint/koral. Denyut pada angka
yang berubah. `dashboard.py`: endpoint baca-saja `/api/kejadian` (tabel `events` + akun/simbol dari posisi/order); tes D7 (140 hijau).
Artefak desain: `PRODUCT.md`, `DESIGN.md`, `.impeccable/surfaces/dashboard-index-html.md` (brief + kontrak arah); `.impeccable/review/` di-gitignore.
Putaran review (finish reviewer): latar dibuat hangat, urutan bagian Sekarang → Peringkat → Pasar, waktu relatif + pembatas hari di aliran kejadian,
render tidak menimpa wadah yang sedang di-hover/fokus (tooltip keyboard), chevron SVG, skala judul. Permintaan user lanjutan: Catatan AI dirender dari
markdown (judul, daftar, tabel, tebal/miring), pembatas antar-bagian dipertegas (`--sep`, aksen kuningan di bawah judul), teks panjang dipangkas
(rincian posisi/saldo/juara/modal/bacaan pasar pindah ke tooltip atau `details`). Permintaan lanjutan: bagian **Ringkasan** (`/api/ringkas`):
5 koin teramai 24 jam (ticker_24h) + kecenderungan tiap analis dihitung mesin dari `positions` (arah, koin favorit, leverage, menang, lama pegang,
cara keluar, pola, jam sibuk); tabel Riwayat tinggal kolom inti (rincian di tooltip koin); Mesin/Biaya satu baris per item. Tes D8 (141).

**Kenapa:** permintaan user: dashboard pemantau "para analis yang sedang paper trade", rich text terbaca, label/informasi di tooltip, warna
sederhana-elegan-kontras; jawaban wawancara: ganti total, dibaca sendiri sambil bekerja, prioritas = apa yang terjadi sekarang.
**File:** `dashboard/*`, `scripts/dashboard.py`, `tests/test_dashboard.py`, `PRODUCT.md`, `DESIGN.md`, `.impeccable/surfaces/`, `.gitignore`, docs, CLAUDE.md.

## 2026-10-12 (malam, 19:10) — laptop Windows — whitelist tool MCP di config.yaml disamakan dengan TOOL_NAMES

**Apa:** `hermes/config.snippet.yaml` daftar `mcp_servers.paper.tools.include` dibuat ulang dari `TOOL_NAMES` (28 tool); `merge_config.ensure_mcp_block` kini mengganti daftar include pada blok yang sudah ada (perubahan `ubah mcp_servers.paper.tools.include (N tool)`), bukan hanya membuat blok bila belum ada. Tes `TestIncludeSync` (snippet == TOOL_NAMES; merge memperbaiki config lama; idempoten) — 139 hijau.

**Kenapa:** laporan user dari Telegram: `/referensi` gagal, agent hanya melihat 26 tool tanpa `cari_referensi`/`baca_referensi` — config.yaml hidup masih memakai whitelist lama (22 tool) karena merge tidak pernah menyentuh blok yang sudah ada. **File:** `hermes/config.snippet.yaml`, `hermes/merge_config.py`, `tests/test_merge_config.py`, docs.

## 2026-10-12 (sore, 17:30) — laptop Windows — Arena: empat persona trader AI bersaing

**Apa:** skema paper v3: akun persona `fade`, `breakout`, `rentang` (kind `tiket`) + kolom `account.status`; `PaperEngine` memakai tabel
`account` sebagai sumber kebenaran (`accounts()`, `is_daily()`, `kind()`, `set_account_status()`, CLI `akun list|aktif|pensiun`); bayangan acak
untuk setiap persona; `ACCOUNT_PENSIUN`. Pemindai: gate saldo/order hidup/P-09 per persona, baris `Akun aktif:` di stdout. `evaluasi.py`:
`papan_arena`, `nilai_arena`, `--arena`, `--nilai-arena --cron` (pensiun otomatis: ≥ 30 trade, ≥ 30 hari, kalah dari acaknya p < 0,2);
`compare()`/`pairs()` per akun. MCP: `papan_arena` (28 tool), `budget_tiket` memuat semua persona. Skill `arena` (menggantikan `tiket`
di cron pemindai; satu sesi untuk semua persona, maks 1 order/persona/wake), skill `arena-papan` (`/arena-papan`, menu menggantikan
`/commands`), SOUL. Cron `nilai-arena` Senin 07:30 (`arena_cron.py`). Dashboard: tab Arena (kartu, tabel, ekuitas semua persona),
pemilih akun dinamis, kartu KPI juara sementara. Tes T27, S4/S9/S11 (per persona), E4, M16, D6, H7 — 138 hijau.

**Kenapa:** permintaan user: "sistem yang terbukti makin baik lewat angka" — seleksi antar gaya trading dengan jatah sama dan pembanding
acak masing-masing, bukan satu persona. **File:** `scripts/{schema_paper.sql,paper_engine,pemindai,evaluasi,mcp_server,notifikasi,dashboard}.py`,
`dashboard/*`, `hermes/{cron.cmd,merge_config.py,SOUL.md,scripts/arena_cron.py,skills/arena,skills/arena-papan}`, tests, docs, CLAUDE.md.

## 2026-10-12 (pagi, 09:45) — laptop Windows — saldo tiket harian bergulir (TP menambah jatah)

**Apa:** `paper_engine.budget_harian()` (murni, dipakai engine & dashboard): saldo = $1 + Σ net posisi ditutup hari itu; bisa dipakai =
saldo − terkunci (posisi terbuka) − tereservasi (order); `boleh_buka` bila saldo ≥ `tiket_min_saldo` (0,50); satu order ≤ `tiket_max_per_order`
(1,00). `BUDGET_TIKET` punya tiga alasan (minimum, per tiket, sisa). Pemindai G3 memakai `boleh_buka` + maks per order; laporan, dashboard,
skill tiket, SOUL, playbook P-01 diperbarui. Tes T10 disesuaikan, T26 baru (TP → tiket kedua boleh; hangus kedua → berhenti; besok reset).

**Kenapa:** keputusan user: plafon $1/hari membatasi sampel; dengan saldo bergulir, hari yang bagus memberi lebih banyak trade (lebih banyak
sampel untuk belajar) tanpa menambah risiko di luar $1 awal + hasil hari itu. **File:** `scripts/{paper_engine,dashboard,pemindai}.py`,
`dashboard/*`, `hermes/{SOUL.md,skills/tiket}`, `referensi/playbook.md`, tests, docs.

## 2026-10-12 (pagi, 09:20) — laptop Windows — autopsi posisi + pengaman breakeven (P-18)

**Apa:** `PaperEngine.autopsi(id)` + tool MCP `autopsi_posisi` (27 tool): MFE/MAE dalam persen jalan ke TP/liq, waktu, menit di sisi
untung/rugi, kembali ke entry setelah MFE, kejadian, pelajaran mekanis; skill evaluasi-harian v1.4 wajib memanggilnya per posisi ditutup.
`EngineConfig.tiket_breakeven_mfe=0.8`: posisi tiket/acak dengan TP tanpa SL mendapat SL di harga masuk setelah mark menempuh ≥ 80%
jalan ke TP (event `BREAKEVEN`). Playbook P-18 (aktif, mesin). Tes T24–T25.

**Kenapa:** user bertanya kenapa SOL #1 hangus tanpa evaluasi. Autopsi: SHORT 109,41 → 109,17 (89% ke TP 109,14) dalam 47 menit, kembali ke
entry 18:08, chop 4 jam, hangus 22:40 oleh impuls pasar. Evaluasi sebelumnya hanya menulis "HANGUS" karena tidak ada data MFE; sekarang
mekanis. Pengaman breakeven mengubah kasus seperti ini dari −$0,99 menjadi −$0,03.

**File:** `scripts/paper_engine.py`, `scripts/mcp_server.py`, `hermes/skills/evaluasi-harian/SKILL.md`, `referensi/playbook.md`, tests, docs.

## 2026-10-12 (pagi, 08:50) — laptop Windows — evaluasi susulan bila laptop mati pukul 23:55

**Apa:** cron Hermes `evaluasi-susulan` (`20 8-21/3 * * *`, skill evaluasi-harian) dengan gate `hermes/scripts/susulan_cron.py`: bangun
hanya bila `pasar/harian/<kemarin>.md` belum ada (dan sudah lewat 07:00) → agent mengevaluasi TANGGAL KEMARIN. `tulis_catatan_harian`
mendapat parameter `hari` (YYYY-MM-DD, tidak boleh masa depan); skill evaluasi-harian v1.3 bagian "Evaluasi susulan". Tes M14, H6 (130 hijau).

**Kenapa:** semalam laptop mati ±22:03 sehingga uji hipotesis 23:40 dan evaluasi 23:55 tidak pernah jalan; `catch_up_missed=false` sengaja
(agar pemindai tidak dikejar), jadi butuh mekanisme susulan khusus evaluasi. Verifikasi pagi: collector mengisi celah, posisi SOL #1 diproses
dari bar historis (HANGUS −$0,99 di 23:xx), notifikasi terkirim 08:30, radar membangunkan agent 08:31 (2 SKIP, $0,55).

**File:** `hermes/scripts/susulan_cron.py`, `hermes/cron.cmd`, `hermes/skills/evaluasi-harian/SKILL.md`, `scripts/mcp_server.py`, tests, docs.

## 2026-10-11 (malam, 19:25) — laptop Windows — dashboard: trailing drawdown + desain ulang untuk trader awam

**Apa:** `dashboard.ekuitas_drawdown()` (ekuitas kumulatif, puncak, trailing drawdown, drawdown maks + waktunya) per akun di `/api/ekuitas`;
tab Riwayat punya pilihan akun, 4 kartu (hasil, puncak, penurunan sekarang, penurunan terdalam), chart ekuitas + chart drawdown (sinkron).
Frontend ditulis ulang dengan bahasa awam: kartu KPI (jatah modal, posisi berjalan, hasil tiket vs pembanding acak, penurunan dari puncak,
swing), chip kesehatan dengan kalimat ("Data harga segar (41 dtk)"), setiap panel punya penjelasan satu kalimat, istilah teknis diganti
(unrealized → untung/rugi kalau ditutup sekarang, liq → modal hangus, EOD → ditutup jam 23:50, acak → pembanding acak/lempar koin),
daftar "Kejadian pada koin ini" sebagai versi teks marker, rapor kelulusan sebagai checklist, kode penolakan mesin diterjemahkan,
indikator psikologi diberi arti. Tipografi Inter + JetBrains Mono untuk angka. Tes D5.

**Kenapa:** permintaan pemilik: trailing drawdown per akun, dan UI sebelumnya tidak terbaca trader awam. **File:** `scripts/dashboard.py`,
`dashboard/*`, `tests/test_dashboard.py`.

## 2026-10-11 (malam, 19:10) — laptop Windows — dashboard lokal: chart trading live + riwayat

**Apa:** `scripts/dashboard.py` (Starlette/uvicorn, sudah ada sebagai dependensi mcp; `127.0.0.1:8586`; semua koneksi DB readonly
singkat; `single_instance_lock`) + `dashboard/` (index.html, app.js, style.css; TradingView Lightweight Charts v4 dari unpkg).
Chart candlestick+volume 1m–1d dengan marker entry/TP/likuidasi/EOD/kedaluwarsa dan garis entry/TP/SL/liq/order dari mesin paper;
panel budget, posisi (unrealized), order, cron Hermes; bar status collector/pemindai/biaya API/kill switch; tab Riwayat (ekuitas
tiket/swing/acak, posisi ditutup, order gagal, ringkasan harian), Statistik, Pemindai, Psikologi, Jurnal. Sumbu waktu digeser ke WIB.
`run_dashboard.cmd` + `hermes/startup/crypto-analyst_dashboard.vbs`; `setup_hermes.cmd` memasang & menyalakannya.

**Kenapa:** pemilik ingin memantau live dengan chart asli dan riwayat trade tanpa membuka CLI/Telegram. **Tes:** D1–D4 (127 hijau).
**File:** `scripts/dashboard.py`, `dashboard/*`, `run_dashboard.cmd`, `hermes/startup/crypto-analyst_dashboard.vbs`, `hermes/setup_hermes.cmd`,
`tests/test_dashboard.py`, docs, CLAUDE.md.

## 2026-10-11 (malam, 18:50) — laptop Windows — P-09 jadi gate mekanis pemindai (G9)

**Apa:** `PaperEngine.hangus_beruntun(day)` (jumlah posisi tiket HANGUS/FUNDING_LIQ berturut-turut di akhir hari) dan gate G9 di `pemindai.gate_awal` (`max_hangus_beruntun=2`) → setelah 2 likuidasi beruntun, agent tidak dibangunkan sampai hari berikutnya. Tes S11. Playbook P-09 sumber = mesin + skill. **Kenapa:** permintaan pemilik: aturan psikologi ini lebih aman ditegakkan mesin daripada diingat agent. **File:** `scripts/paper_engine.py`, `scripts/pemindai.py`, `tests/test_pemindai.py`, `referensi/playbook.md`, docs.

## 2026-10-11 (malam, 18:40) — laptop Windows — playbook: P-09, P-11, P-15 diaktifkan pemilik

**Apa:** status `uji` → `aktif` untuk P-09 (stop setelah 2 HANGUS beruntun), P-11 (R:R eksplisit sebelum entry, tidak bisa = SKIP), P-15 (pola chart hanya setelah close breakout + volume). Aturan aktif: 11. **Kenapa:** keputusan pemilik setelah membaca usulan dari buku (§15.6). **File:** `referensi/playbook.md`.

## 2026-10-11 (malam, 18:45) — laptop Windows — Milestone 3c: referensi buku, playbook, tool cari/baca_referensi

**Apa:** `scripts/konversi_buku.py` (pymupdf/ebooklib: bab dari bookmark → heuristik judul berfont besar → potongan halaman;
PDF scan → `perlu_ocr`), `scripts/referensi.py` (daftar, cari kata kunci dengan skor & cuplikan, baca bab berpotongan, playbook,
indeks). Tool MCP `cari_referensi`, `baca_referensi` (26 tool); `baca_memori` jenis `playbook` & `indeks`; `tulis_jurnal`
parameter `aturan_dilanggar`. Skill `referensi` (`/referensi`, menu menggantikan `/model`), aturan SOUL "Referensi", skill
`tiket` langkah 4b membaca playbook. `referensi/indeks.md` (3 buku) dan `referensi/playbook.md` v1 (aturan aktif yang sudah
ditegakkan mesin/skill + usulan `uji` dari buku dengan rujukan bab) di-commit; `referensi/buku/` tetap gitignored.
`requirements.txt` + pymupdf 1.28.2, EbookLib 0.20, beautifulsoup4 4.15.0.

**Kenapa:** §15 — konsistensi aliran, kutipan yang bisa dicek (judul + bab + path), dan playbook pribadi. Spesifikasi lama memakai
`@path` + Grep oleh Claude Code; dengan Hermes tanpa tool file, akses lewat MCP. Tiga PDF user tidak punya bookmark → heuristik.

**Tes:** R1–R5, M13, M9 → 26 (122 hijau). Konversi nyata: 14 + 9 + 3 bab. **File:** `scripts/{konversi_buku,referensi,mcp_server}.py`,
`hermes/{SOUL.md,merge_config.py,skills/referensi,skills/tiket}`, `referensi/{indeks,playbook}.md`, `tests/*`, `requirements.txt`, docs, CLAUDE.md.

## 2026-10-11 (petang, 18:05) — laptop Windows — Milestone 3b: panel psikologi pasar; watchlist top 30 / 5 kandidat

**Apa:** `scripts/psikologi.py` (penulis tunggal `data/psikologi.sqlite`, `schema_psikologi.sql`): 12 indikator §16.2 untuk BTC/ETH/
pasar luas (FNG alternative.me; funding dari pasar.sqlite; Δ OI 24j Binance `futures/data` + Δ harga 24j kline_1h → kapitulasi/
penumpukan; L/S akun & top trader; taker 4 jam; likuidasi OKX ±100 order; premium Coinbase dikoreksi USDT/USD; premium IDR via
Indodax; suplai stablecoin 7 hari DefiLlama), zona takut/serakah (ambang awal → persentil 10/90 setelah 90 hari), divergensi,
retensi 400 hari; sumber gagal → `tidak tersedia` + alasan. Tool MCP `panel_psikologi` (24 tool); `tulis_catatan_harian` mengisi
frontmatter `panel_*`, `fng`, `funding_btc`. Skill `psikologi` (`/psikologi`, menu Telegram menggantikan `/whoami`;
`merge_config.py` kini memperbarui baris `priority` yang sudah ada). Skill `evaluasi-harian` v1.2 memakai panel. Cron Hermes
`psikologi` `7 * * * *` `--no-agent` + `hermes/scripts/psikologi_cron.py`. `common.BINANCE_HOSTS` + Coinbase & OKX (DoH).
Pemindai: `top_n=30`, `top_k=5`; prompt cron & skill tiket `kandidat_terbaru(limit=5)`.

**Kenapa:** catatan harian agent selama ini menulis "panel psikologi tidak tersedia"; §16.2 membutuhkan data positioning/sentimen
mekanis sebagai bahan hipotesis (`penumpukan-leverage`, `kapitulasi`, `divergensi-funding`). Pertanyaan user "kenapa top 3":
watchlist memang top volume 24 jam; yang tampak 3 adalah `top_k` kandidat skor tertinggi — dinaikkan ke 5 dengan universe 30.

**Tes:** PS1–PS6, M12, M9 → 24 (116 hijau). Probe jaringan: semua sumber bisa diakses lewat DoH; `fapi/v1/allForceOrders`
diblokir → likuidasi dari OKX. **File:** `scripts/{psikologi.py,schema_psikologi.sql,common.py,mcp_server.py,pemindai.py}`,
`hermes/{cron.cmd,SOUL.md,merge_config.py,scripts/psikologi_cron.py,skills/psikologi,skills/evaluasi-harian,skills/tiket}`,
`tests/test_psikologi.py`, `tests/test_mcp_server.py`, `docs/*`, `CLAUDE.md`.

## 2026-10-11 (petang, 18:30) — laptop Windows — Milestone 3a: baseline acak, statistik kelulusan, hipotesis dinilai skrip

**Apa:** (1) `paper_engine.py` skema v2: akun `acak`, kolom `orders.tp_pct/sl_pct` (migrasi otomatis), `_shadow_acak` —
setiap order tiket agent/CLI mendapat bayangan sisi acak (`Random("acak-v1:<id>")`), entry market bar berikutnya, jarak TP/SL sama
(diresolusi saat terisi, dibulatkan menjauh dari untung), budget cermin $1/hari (`BUDGET_ACAK`/`ACAK_EOD`), EOD 23:50, batal ikut;
`report()` blok tiket vs acak, `rollover_day` 3 akun, `OrderResult.shadow_order_id`. (2) `scripts/evaluasi.py` + tool MCP
`statistik_lulus` (23 tool): expectancy, per bulan, win rate, stabilitas (−5% terbaik), kepatuhan (order tiket > 22:30), tiket vs acak
(permutasi 2000× + sign test berpasangan), tabel kriteria §19.7 dengan `lulus | belum | tidak tersedia`. (3) `scripts/hipotesis.py`
(murni) + `scripts/uji_hipotesis.py`: `tulis_hipotesis` kini terstruktur (`symbol, tf, jenis, arah, nilai, batas_hari, kondisi`) →
`pasar/hipotesis.jsonl`; skrip 23:40 menilai (benar/salah/ambigu, tanpa look-back), baseline 200 titik acak/120 hari `kline_1h`,
pelajaran naik (≥10 sampel, ≥ baseline+15) / dinilai ulang 30 hari / pensiun; view `hipotesis.md`, `pelajaran.md` ditulis skrip.
`baca_memori("hipotesis")` merender dari jsonl. (4) cron `uji-hipotesis` `40 23 * * *` `--no-agent` + `hermes/scripts/uji_cron.py`;
skill `evaluasi-harian` v1.1 (baca pelajaran/hipotesis/statistik, parameter hipotesis baru, larangan menilai sendiri); SOUL.md.
`notifikasi.py` melewati kejadian akun acak (baris 🎲 saat dibuat).

**Kenapa:** §19.6–19.7 dan §16.5–16.6 — agar bisa dinilai apakah agent benar-benar lebih baik dari acak dan belajar, dengan
skrip sebagai penilai (model cenderung membenarkan ceritanya). Cakupan dibatasi 3a atas keputusan user; 3b (panel psikologi)
dan 3c (buku) menyusul.

**Tes:** T20–T23, E1–E3, U1–U5, M11, N4, M9 → 23 tool; tes lama memakai `EngineConfig(acak_enabled=False)`. Total 109 hijau.

**File:** `scripts/{paper_engine,schema_paper.sql,evaluasi,hipotesis,uji_hipotesis,mcp_server,notifikasi}.py`,
`hermes/{cron.cmd,SOUL.md,scripts/uji_cron.py,skills/evaluasi-harian/SKILL.md}`, `tests/*`, `docs/*`, `CLAUDE.md`.

## 2026-10-11 (sore, 17:25) — laptop Windows — notifikasi kejadian paper ke Telegram; order uji dibatalkan

**Apa:** `scripts/notifikasi.py` (baru; penulis tunggal `data/notif.json`): membaca `paper.sqlite` `events` ⋈ `orders` ⋈
`positions`, memformat kejadian (🆕 order, ❌ batal, ⌛ kedaluwarsa, ✅ terisi, 🎯 TP, 🛑 STOP, 🔚/🌙 tutup, 💀 likuidasi,
⚠️ ambigu) dan mencetak hanya yang baru sejak kursor; `hermes/scripts/notif_cron.py` (pembungkus, diam saat gagal);
cron `notif-paper` `* * * * *` `--no-agent --deliver telegram --failure-deliver local` di `hermes/cron.cmd`.
Order tiket uji #1 (BTC) dan #2 (ETH) dibatalkan lewat `paper_engine.py batal` atas permintaan user; #3 swing tetap.

**Kenapa:** user ingin tahu di Telegram saat order terisi / TP / SL / likuidasi tanpa bertanya ke agent. Mode `--no-agent`
Hermes mengirim stdout skrip apa adanya (kosong = diam) sehingga tidak ada biaya LLM dan token Telegram tetap hanya di
Hermes. Pembatalan #1/#2 membuka gate G4 supaya pemindai bisa membangunkan agent.

**Wake pertama (16:51 WIB, setelah #1/#2 dibatalkan):** pemindai menemukan 3 kandidat skor 3; agent (konteks cron)
memanggil tool MCP, memasang order #7 SOL SHORT 75x @ 109,41 TP 109,14 dengan `plan_id=K3` persis, SKIP K1/K2 dengan
alasan tertulis di `jurnal/agent/2026-10-11.md`; biaya 2 panggilan ≈ $0,30 (termasuk cache write). Order terisi 16:53 →
posisi tiket #1. Pertanyaan terbuka "apakah agent memakai plan_id yang benar" terjawab: ya.

**Tes:** `tests/test_notifikasi.py` N1–N3, `test_hermes_sync` H5. **File:** `scripts/notifikasi.py`,
`hermes/scripts/notif_cron.py`, `hermes/cron.cmd`, `tests/test_notifikasi.py`, `tests/test_hermes_sync.py`, `CLAUDE.md`, `docs/*`.

## 2026-10-11 (sore, 16:40) — laptop Windows — Milestone 2b: pemindai mekanis, kline_1h, cron Hermes

**Apa:** `scripts/pemindai.py` (baru; penulis tunggal `data/kandidat.sqlite`): tiap 5 menit memindai 20 koin top volume
∪ simbol berposisi tanpa LLM — level = klaster swing 5m∪15m (≥ 2 sentuhan), jejak 5m (WICK/BREAKOUT_GAGAL/VOL),
skor, arah dugaan, kelayakan leverage lewat `analisis.tabel_leverage` (jarak liq ≥ 2×ATR 5m untuk sisa budget tiket),
gate G1–G8 (data basi, jam 07:00–22:30, budget < $0,10, ≥ 2 order tiket hidup, cap 12 wake/hari, exposure, cooldown 30 menit,
skor < 3). Stdout = ringkasan untuk agent + baris terakhir `{"wakeAgent": true|false}` (kontrak cron Hermes; false = nol biaya).
Collector: tabel `kline_1h` (`SCHEMA_VERSION="2"`, backfill 120 hari per simbol baru maks 5 simbol/tick, 1 permintaan kecil
per simbol per jam, retensi 180 hari), `BinanceFapi.klines_tf`, `kline_limit(tf_ms=)`. `SqliteMarket.bars_1h`,
`analisis.load_bars_1h`. `mcp_server.ohlcv` menerima `1d`; 1h/4h/1d dari `kline_1h` (field `sumber`), fallback resample 1m.
`kandidat_terbaru` memakai run terakhir yang `wake=1` (run kosong sesudahnya tidak mengosongkan daftar) + field `plan_id`.
`hermes/cron.cmd`: jadwal `1-59/5 * * * *` (bar 1m tersimpan pada detik :05, jadi :00 terlalu dini) dan prompt yang
menyebut `plan_id`; skill `tiket` langkah 3/7 memakai `plan_id` dari kandidat, `MANUAL` untuk permintaan pemilik.

**Kenapa:** agent sebelumnya hanya bekerja saat diajak bicara. Sekarang ia bekerja sendiri dengan biaya hanya saat
ada kandidat (≤ 12 wake/hari × ≈ $0,05–0,15). `data_until` dihitung dari bar yang tersimpan (bukan jam dinding)
supaya bucket 5m yang belum lengkap tidak pernah ikut.

**Tes:** `tests/test_pemindai.py` S1–S10 (setup LONG sintetis → wake K1; datar → off; jam; budget; basi; cap; cooldown +
skor naik + kedaluwarsa; retensi; exposure; CLI `--once/--cron/--json/--sekarang`), `tests/test_collector_1h.py` C1–C3
(+C2b budget backfill), `test_mcp_server` M8 `plan_id` + M10 `ohlcv` dari `kline_1h`, `test_common` `kline_limit` 1h.
Total 91 tes hijau. Uji data nyata: `pemindai.py --once` → 20 simbol, 2 kandidat (UNI, XRP SHORT skor 4), gate off
karena 2 order tiket uji masih hidup.

**Deploy (16:43 WIB):** collector dimulai ulang (skema v2; `kline_1h` 20 simbol × 120 hari terisi dalam 4 tick, weight
282 → 91); `hermes cron create` lewat `run_logged.cmd`: `evaluasi-harian` d38d3262d1b5, `pemindai-tiket` f27a23cad20c —
percobaan pertama ditolak karena `--script` harus **relatif** terhadap `HERMES_HOME\scripts` (cron.cmd diperbaiki:
`--script pemindai_cron.py`). `hermes cron run pemindai-tiket` → `pemindai_run` wake=0 "sudah 2 order tiket hidup",
`api_calls` tetap 16 (nol biaya). Gateway dimulai ulang (PID 24408) agar skill `tiket` baru terbaca. Run terjadwal
pertama 16:46:25 WIB berjalan sendiri; gate off → `delivery_outcome=suppressed` (tidak ada pesan Telegram), jadi tidak
perlu mengecilkan output gate-off.

**File:** `scripts/pemindai.py`, `scripts/collector.py`, `scripts/schema_pasar.sql`, `scripts/paper_engine.py`,
`scripts/analisis.py`, `scripts/mcp_server.py`, `hermes/cron.cmd`, `hermes/skills/tiket/SKILL.md`, `tests/fixtures.py`,
`tests/test_pemindai.py`, `tests/test_collector_1h.py`, `tests/test_mcp_server.py`, `tests/test_common.py`, `docs/*`, `CLAUDE.md`.

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
