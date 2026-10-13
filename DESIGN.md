---
name: crypto-analyst — Meja analis
description: Dashboard baca-saja berupa meja arang hangat, tinta gading, satu aksen kuningan; mint untung, koral rugi, hanya garis rambut sebagai pemisah.
colors:
  arang: "#1a1816"
  arang-2: "#201d1a"
  arang-3: "#27231f"
  arang-tooltip: "#120f0d"
  garis: "#332e28"
  garis-2: "#433c34"
  sep: "#4e463b"
  garis-grafik: "#242019"
  gading: "#ece9e1"
  redup: "#aab0b7"
  pudar: "#7d838b"
  kuningan: "#d9b35c"
  kuningan-tinta: "#1a1500"
  mint: "#5bd4a3"
  koral: "#f07b7b"
  amber: "#e3b04b"
  persona-tiket: "#d9b35c"
  persona-fade: "#8ab4f8"
  persona-breakout: "#5bd4a3"
  persona-rentang: "#e39bd0"
  persona-acak: "#7d838b"
  persona-swing: "#f0a35b"
typography:
  title:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "23px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  nama-analis:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    letterSpacing: "-0.01em"
  subtitle:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.5
  body-md:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  body-small:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
  caption:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
  micro:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  pil:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    letterSpacing: "0.02em"
  mono:
    fontFamily: "ui-monospace, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  hairline: "2px"
  focus: "3px"
  code: "4px"
  control: "6px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "10px"
  lg: "14px"
  kepala: "18px"
  xl: "22px"
  bagian-bawah: "26px"
  gap-kolom: "28px"
  bagian: "30px"
  gutter: "clamp(16px, 2.4vw, 36px)"
components:
  seg-button:
    backgroundColor: "{colors.arang-2}"
    textColor: "{colors.redup}"
    typography: "{typography.label}"
    padding: "6px 10px"
    height: "30px"
  seg-button-on:
    backgroundColor: "{colors.kuningan}"
    textColor: "{colors.kuningan-tinta}"
    typography: "{typography.label}"
    padding: "6px 10px"
    height: "30px"
  jump-link:
    textColor: "{colors.redup}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 11px"
  jump-link-hover:
    backgroundColor: "{colors.arang-3}"
    textColor: "{colors.gading}"
    rounded: "{rounded.pill}"
    padding: "6px 11px"
  jump-link-on:
    backgroundColor: "{colors.kuningan}"
    textColor: "{colors.kuningan-tinta}"
    rounded: "{rounded.pill}"
    padding: "6px 11px"
  select-input:
    backgroundColor: "{colors.arang-2}"
    textColor: "{colors.gading}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
    height: "32px"
  judul-bagian:
    textColor: "{colors.gading}"
    typography: "{typography.title}"
    padding: "0 0 8px"
  judul-bagian-bar:
    backgroundColor: "{colors.kuningan}"
    width: "28px"
    height: "2px"
  pil:
    textColor: "{colors.redup}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  pil-ok:
    textColor: "{colors.mint}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  pil-off:
    textColor: "{colors.koral}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  pil-hold:
    textColor: "{colors.amber}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  tag:
    textColor: "{colors.redup}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    padding: "0 7px"
  tag-ok:
    textColor: "{colors.mint}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    padding: "0 7px"
  tag-belum:
    textColor: "{colors.amber}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    padding: "0 7px"
  tooltip:
    backgroundColor: "{colors.arang-tooltip}"
    textColor: "{colors.gading}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
    width: "320px"
  md-block:
    backgroundColor: "{colors.arang-2}"
    textColor: "{colors.gading}"
    typography: "{typography.body-md}"
    rounded: "{rounded.control}"
    padding: "16px 20px"
    width: "80ch"
  md-code:
    backgroundColor: "{colors.arang-3}"
    textColor: "{colors.gading}"
    typography: "{typography.mono}"
    rounded: "{rounded.code}"
    padding: "1px 5px"
---

# Design System: crypto-analyst — Meja analis

## Overview

**Creative North Star: "Meja Analis"**

Dashboard ini adalah satu meja kerja gelap yang dilirik sepanjang hari, bukan layar yang dibaca. Permukaannya arang
hangat (kecoklatan, bukan kebiruan) tanpa kartu, tanpa panel bertumpuk; di dalam bagian hanya ada garis rambut 1 px,
antar bagian garis pemisah 2 px yang sedikit lebih terang, dan tiap judul bagian membawa satu garis kuningan pendek
28 × 2 px di bawahnya. Tinta gading menulis kalimat utuh ("BTC LONG 5× · 61.240 → 61.730 · hangus 4,2 %"), bukan
angka besar dalam kotak KPI. Satu aksen kuningan dipakai hemat untuk hal yang sedang dipilih, difokus, atau baru
berubah; mint dan koral hanya berbicara soal untung dan rugi; amber memberi tanda tunggu atau batas yang mendekat.

Kepadatannya tinggi tetapi tenang: ukuran teks 12–15 px, baris 1,45–1,6, angka tabular supaya kolom tidak bergoyang
saat polling 5 detik. Di layar hanya tinggal yang dilirik: nilai, arah, jarak; saldo rinci, harga masuk/target/stop,
status order, syarat juara, dan bacaan per indikator dipindahkan ke tooltip pada label bergaris putus atau ke blok
`details`. Bagian yang sedang dibaca (tooltip terbuka atau fokus di dalamnya) tidak dirender ulang. Gerak hanya tiga dan
semuanya pendek: denyut garis bawah kuningan pada angka yang berubah, entri kejadian baru yang masuk dengan geser, dan
chevron `details` yang berputar.

Dunia ini menolak susunan default "kartu angka besar + tab", menolak kartu di dalam kartu, dan menolak estimasi: data
yang tidak ada ditulis "tidak tersedia" beserta alasannya, dalam warna pudar, bukan diganti angka tebakan.

**Key Characteristics:**
- Satu permukaan arang hangat; hirarki lewat garis rambut, pemisah bagian 2 px, dan nada teks (gading → redup → pudar),
  bukan lewat kotak.
- Satu keluarga huruf (Inter) dengan angka tabular; tebal 600 untuk nilai dan status terpilih, 700 hanya untuk nama analis.
- Satu aksen kuningan untuk pilihan/fokus/perubahan/tautan dan garis pendek di bawah judul bagian; mint = untung,
  koral = rugi, amber = tunggu/batas.
- Layar tipis: satu baris per keadaan, rincian di tooltip atau `details`; catatan AI dirender sebagai markdown.
- Baca-saja: tidak ada aksi primer, tidak ada tombol beli/jual; kontrol hanya memilih tampilan.

## Colors

Palet arang hangat bernada coklat dengan tiga nada tinta dan satu aksen logam; warna semantik hanya untuk arah uang dan
kesehatan.

### Primary
- **Kuningan** (`kuningan`): satu-satunya aksen. Dipakai pada garis pendek 28 × 2 px di bawah tiap judul bagian, pilihan
  aktif (pil navigasi, segmen aktif), cincin fokus 2 px, garis bawah tooltip saat hover, nama analis di aliran kejadian,
  batang saldo yang sehat, garis & area ekuitas, garis silang grafik lilin, seleksi teks, `accent-color` kotak centang,
  tautan di blok markdown, dan denyut angka berubah. Teks di atas kuningan selalu **Kuningan-tinta** (`kuningan-tinta`),
  hampir hitam hangat.

### Secondary
- **Mint** (`mint`): untung, posisi LONG masuk, TP, status "boleh buka"/"aktif"/"lolos", titik kesehatan OK, lilin naik,
  zona "sangat serakah".
- **Koral** (`koral`): rugi, SHORT masuk, likuidasi, status "berhenti"/mati, batang saldo saat tidak boleh buka tiket,
  lilin turun, area drawdown, pesan galat, zona "sangat takut", jarak hangus < 1 %, drawdown sekarang di bawah puncak.
- **Amber** (`amber`): peringatan dan tunggu: pil "berhenti" (hold), tag "belum", titik kesehatan waspada, batang biaya
  > 70 % batas, penanda order kedaluwarsa/batal, "Yang tidak nyambung".

### Tertiary
- **Warna persona** (`persona-tiket` = kuningan, `persona-fade` biru lembut, `persona-breakout` = mint, `persona-rentang`
  merah muda, `persona-acak` = pudar, `persona-swing` jingga): identitas tiap akun pada nama di tabel Peringkat dan garis
  pada grafik arena (acak: garis putus-putus 1 px, persona: 2 px). Didefinisikan di `app.js` (`WARNA`), bukan di CSS;
  tidak dipakai sebagai warna permukaan.

### Neutral
- **Arang** (`arang`): latar halaman, latar grafik, latar sticky `th`, dan cincin dalam titik kesehatan.
- **Arang-2** (`arang-2`): latar kontrol (select, input, tombol segmen), baris tabel yang dapat diklik saat hover, dan
  blok markdown `.md`.
- **Arang-3** (`arang-3`): trek batang saldo/biaya, hover pil navigasi, latar `code`/`pre` di dalam markdown.
- **Arang-tooltip** (`arang-tooltip`): latar tooltip, satu-satunya permukaan lebih gelap dari halaman.
- **Garis** (`garis`): pemisah rambut 1 px antar baris, item daftar, header, `hr` markdown, tepi skala grafik.
- **Garis-2** (`garis-2`): tepi kontrol, pil/tag, tooltip, cincin luar titik kesehatan, thumb scrollbar, pembatas hari
  di feed, garis kiri `blockquote`.
- **Sep** (`sep`): pemisah 2 px antar bagian (`section.bag`), satu tingkat lebih terang dari garis-2; hanya di sini.
- **Garis-grafik** (`garis-grafik`): grid Lightweight Charts (lebih redup dari garis halaman).
- **Gading** (`gading`): teks utama, nilai tebal (termasuk `b` di kalimat ringkas Peringkat/Riwayat), jam.
- **Redup** (`redup`): teks sekunder: subjudul, lead, kalimat ringkas Peringkat dan Riwayat, label kontrol, header
  tabel, baris akun acak, teks grafik, `h4` dan `i` di markdown.
- **Pudar** (`pudar`): teks tersier: waktu di feed, pembatas hari, panah `→` di baris posisi, catatan, keadaan kosong
  ("Menunggu radar."), "tidak tersedia", hasil hari ini saat nol, titik kesehatan tanpa status, chevron `details`,
  marker daftar markdown.

### Named Rules
**The Satu Kuningan Rule.** Kuningan menandai pilihan, fokus, perubahan, tautan, dan garis pendek di bawah judul bagian;
tidak pernah menjadi latar area atau warna teks tubuh. Teks di atas kuningan selalu kuningan-tinta.

**The Mint-Koral Rule.** Mint dan koral hanya mengatakan arah uang atau hidup/mati sistem (untung/rugi, LONG/SHORT, OK/mati).
Tidak dipakai untuk dekorasi atau untuk menandai persona.

**The Garis Rambut Rule.** Di dalam bagian, pemisah hanya garis 1 px `garis`; antar bagian garis 2 px `sep`. Tidak ada
kartu, kotak latar, atau bayangan untuk memecah halaman. Tepi `garis-2` hanya pada kontrol, pil/tag, tooltip, pembatas
hari, dan kutipan.

**The Tidak Tersedia Rule.** Data yang tidak ada ditulis "tidak tersedia" (atau "—" untuk satu nilai) dalam `pudar`,
dengan alasan bila ada. Nilai nol ditulis "$0,00", bukan dikosongkan. Tidak pernah diisi estimasi, dan tidak pernah
diberi warna semantik.

## Typography

**Display Font:** Inter (dengan system-ui, -apple-system, Segoe UI, sans-serif)
**Body Font:** Inter (sama)
**Label/Mono Font:** ui-monospace, Consolas, monospace; hanya untuk `code` dan `pre` di dalam blok markdown. Angka memakai
Inter dengan `font-variant-numeric: tabular-nums` di seluruh dokumen.

**Character:** Satu keluarga, satu suara. Judul bagian (23 px, dengan garis kuningan 28 × 2 px di bawahnya) sedikit lebih
besar dari nama halaman (21 px) karena bagianlah yang dilirik; nama analis 17 px tebal 700 adalah satu-satunya bobot 700.
Hirarki selebihnya dari nada warna (gading/redup/pudar) dan tebal 600 pada nilai, bukan dari ukuran. Inter dimuat dari
Google Fonts pada bobot 400/500/600/700.

### Hierarchy
- **Title** (600, 23px, tracking -0,01 em, padding bawah 8 px + garis kuningan): judul bagian (Sekarang, Peringkat,
  Pasar, Riwayat, Konteks, Catatan AI).
- **Headline** (600, 21px): nama halaman "Meja analis" di header.
- **Nama analis** (700, 17px): `h3` di header kolom analis; satu-satunya bobot 700.
- **Subtitle** (600, 15px; 14px untuk judul aside feed; 17/15.5/14 px untuk `h2/h3/h4` di markdown): judul kolom dan aside.
- **Body** (400, 14.5px, 1.5): teks dasar halaman; nilai P/L dan nama koin tebal 600 pada ukuran yang sama; nilai saldo
  tebal 600 15px; kalimat ringkas Peringkat (`.juara`) 14.5px redup dengan `b` gading. Lead bagian maks 72ch.
- **Body-md** (400, 14px, 1.6): isi blok markdown, maks 80ch.
- **Body-small** (400, 13.5px, 1.45–1.55): item daftar, baris posisi/order, tabel, summary `details`, kalimat ringkas
  Riwayat (`.ringkas`, redup dengan `b` gading).
- **Label** (400–500, 13px): kontrol, tooltip, feed, subjudul header, titik kesehatan, tabel di markdown; `th` 500 12.5px.
- **Caption** (400, 12.5px): baris kedua posisi (entry → target · hangus), hasil hari ini di blok saldo, gaya analis,
  keterangan, footer.
- **Micro** (400, 12px): waktu di feed/kejadian, `small` di judul, isi tag.
- **Pil** (600, 11.5px, tracking 0,02 em, huruf kapital): pil status analis. Pembatas hari di feed memakai ukuran yang
  sama dengan tracking 0,04 em, warna pudar, bobot 400.
- **Mono** (400, 12.5px, 1.5): `code` inline dan blok `pre` di markdown.

### Named Rules
**The Angka Tabular Rule.** Semua angka tabular-nums (diset di `html, body`), rata kanan di kolom `.num`, dan diformat
`id-ID`; mata uang USD, IDR hanya dalam kurung.

**The Kalimat Bukan Kotak Rule.** Keadaan dinyatakan sebagai kalimat kaya (nama koin tebal, arah, leverage, jarak ke
target/hangus) dengan nilai inline tebal; bukan sebagai angka besar terpisah.

**The Layar Tipis Rule.** Satu baris per keadaan di layar; rinciannya (harga masuk/target/stop, status order, saldo
bergulir, syarat juara, puncak modal, bacaan per indikator) hidup di tooltip pada label bergaris putus atau di blok
`details`, bukan sebagai baris tambahan.

**The Waktu Relatif Rule.** Di feed, waktu ditulis relatif ("baru saja", "12 mnt", jam untuk hari ini, "kemarin 21:40",
lalu "13 Okt 21:40"), dan hari dipisah oleh pembatas "hari ini / kemarin / tanggal". Di tempat lain waktu tetap jam WIB.

## Layout

Single-page scroll dengan enam bagian (`section.bag`) berurutan Sekarang, Peringkat, Pasar, Riwayat, Konteks, Catatan
AI; tiap bagian berpadding 30 px atas / 26 px bawah dan dipisah garis 2 px `sep` (bagian terakhir tanpa); kepala bagian
(`.head`) berjarak 18 px ke isi dan `h2`-nya membawa garis kuningan 28 × 2 px di bawah (padding bawah 8 px). `main`
ber-gutter horizontal `clamp(16px, 2.4vw, 36px)` dan padding bawah 40 px. Header tipis (`.top`, padding 14 px / 10 px)
lalu navigasi lompat-bagian sticky (`.jump`, latar arang 88 % + blur 8 px, z-index 20) yang menyembunyikan scrollbar-nya
dan memudar 28 px di tepi kanan lewat `mask-image`; `scroll-margin-top` 52 px.

Bagian berdata memakai grid dua kolom: isi utama `minmax(0,1fr)` + kolom kanan tetap (360 px untuk feed di Sekarang;
340 px di Peringkat dan Riwayat; 300 px untuk kejadian di Pasar), jarak 28 px, `align-items: start`. Meja analis adalah
grid `repeat(auto-fit, minmax(215px, 1fr))` dengan jarak kolom 22 px dan tanpa jarak baris (tiap kolom membawa garis
bawahnya sendiri). Pembanding acak/swing `minmax(260px, 1fr)`; Konteks `minmax(300px, 1fr)` dengan jarak 28 px.

Ritme vertikal: 7–8 px padding item daftar/feed/sel tabel, 10 px baris pembanding/summary, 14 px padding atas kolom
analis, 4 px jarak baris saldo. Semua anak grid `min-width: 0` supaya tabel dan grafik tidak meledakkan kolom.

Tinggi tetap: grafik lilin 460 px, arena 240 px, ekuitas 220 px, drawdown 120 px; feed maksimal 560 px dan tabel 440 px
dengan scroll internal, blok markdown maksimal 60vh (320 px untuk catatan pasar di Konteks).

**Responsif.** ≤ 1100 px: semua grid dua kolom menjadi satu kolom; feed maksimal 320 px. ≤ 640 px: teks dasar 14 px,
header menjadi kolom (jarak 6 px), kesehatan rata kiri, meja satu kolom, grafik lilin 320 px, sel tabel 7 px / 8 px.
`prefers-reduced-motion`: denyut dan geser masuk dimatikan.

**Polling dan render.** Ringkasan tiap 5 detik, grafik 15 detik, arena/ekuitas/kandidat 60 detik, psikologi 5 menit;
perubahan nilai ditandai `data-k` dan didenyutkan. Render `#meja`, `#banding`, `#feed`, dan `#health` dilewati selama
tooltip terbuka atau fokus keyboard berada di dalamnya (`setHTML`/`sibuk`), supaya yang sedang dibaca tidak hilang.

## Elevation & Depth

Sistem ini datar: kedalaman diberikan oleh nada permukaan (arang → arang-2 → arang-3) dan garis (rambut 1 px di dalam
bagian, 2 px antar bagian), bukan bayangan. Hanya dua pengecualian, keduanya lapisan yang memang melayang di atas
halaman: tooltip memakai bayangan lembut, dan navigasi lompat-bagian memakai latar tembus pandang + blur dengan tepi
kanan yang memudar. Titik kesehatan memakai dua cincin `box-shadow` (2 px arang, 1 px garis-2) sebagai tepi, bukan
sebagai elevasi.

### Shadow Vocabulary
- **Tooltip** (`box-shadow: 0 8px 24px -8px rgba(0,0,0,.7)`): hanya pada `#tt` saat tampil.
- **Cincin titik kesehatan** (`box-shadow: 0 0 0 2px var(--bg), 0 0 0 3px var(--line2)`): tepi titik 9 px.
- **Denyut** (`box-shadow: inset 0 -2px 0 var(--brass)` → transparan, 600 ms ease-out): garis bawah pada angka berubah.

### Named Rules
**The Datar Kecuali Melayang Rule.** Permukaan di dalam halaman tidak pernah berbayang. Bayangan hanya pada lapisan yang
benar-benar mengambang di atas konten (tooltip); navigasi sticky memakai blur dan mask, bukan bayangan.

## Shapes

Sudut nyaris tegak: kontrol, tooltip, blok markdown, dan `pre` berradius 6 px (`control`); `code` inline 4 px; batang
saldo/biaya 4 px tinggi dengan radius 2 px; cincin fokus radius 3 px; pil navigasi, pil status, dan tag berbentuk kapsul
penuh (999 px). Garis: `garis` 1 px untuk pemisah dalam bagian, `sep` 2 px antar bagian, `garis-2` 1 px untuk kontrol dan
kapsul, dan satu garis kuningan 28 × 2 px persegi (tanpa radius) di bawah tiap judul bagian. Kapsul status mewarnai
tepinya dengan warna semantik 45 % (`color-mix(in srgb, <warna> 45%, transparent)`), tidak pernah diisi penuh. Titik
kesehatan bulat 9 px. Ikon satu-satunya adalah chevron SVG 12 px (stroke 1,5, ujung bulat) sebagai mask berwarna pudar
pada `details`, berputar 90° saat terbuka. Scrollbar tipis, thumb `garis-2` radius 5 px dengan tepi 2 px arang;
scrollbar navigasi disembunyikan.

## Components

### Buttons (segmen dan kontrol tampilan)
Tidak ada tombol aksi primer; semua tombol hanya memilih tampilan.
- **Seg control** (`.seg`): bingkai 1 px `garis-2` radius 6 px berisi tombol tanpa tepi, latar arang-2, teks redup 13 px,
  padding 6 px / 10 px, tinggi min 30 px; hover teks gading; aktif latar kuningan + teks kuningan-tinta tebal 600; fokus
  outline kuningan offset -2 px. Dipakai untuk rentang lilin, akun ekuitas, BTC/ETH.
- **Pil navigasi** (`.jump a`): kapsul 999 px, padding 6 px / 11 px, teks redup; hover gading di atas arang-3; aktif
  kuningan + kuningan-tinta tebal 600.
- **.btn / select / input**: latar arang-2, tepi garis-2, radius 6 px, padding 6 px / 10 px, 13 px, tinggi min 32 px;
  hover tepi menjadi redup. Kotak centang (`.toggle`) memakai `accent-color` kuningan, 15 px, label redup 13 px.
- **Fokus global**: `outline: 2px solid` kuningan, offset 2 px, radius 3 px.

### Judul bagian
`section.bag > .head h2`: 23 px 600, `position: relative`, padding bawah 8 px, dengan `::after` 28 × 2 px kuningan rata
kiri di dasar; judulnya sendiri adalah label bergaris putus yang membuka tooltip penjelas bagian. `.head` flex
kiri-kanan (judul + kontrol), margin bawah 18 px.

### Chips
- **Pil status** (`.pil`): kapsul 11.5 px kapital 600, padding 1 px / 7 px, tepi garis-2 teks redup; varian `ok` mint,
  `off` koral, `hold` amber dengan tepi warna 45 %. Hanya di header kolom analis.
- **Tag** (`.tag`): kapsul 12 px, padding 0 / 7 px, line-height 1.6, tepi garis-2 teks redup; `ok` mint, `belum` amber
  (keduanya mewarnai tepi); `takut` koral dan `serakah` mint hanya mewarnai teks. Dipakai di tabel dan daftar syarat.

### Cards / Containers
Tidak ada kartu. Kolom analis (`.analis`) adalah kolom meja: padding 14 px atas / 12 px bawah, garis rambut atas (dari
`.meja`) dan bawah, tanpa latar, tanpa radius. Header kolom grid dua kolom (nama 17 px 700 + gaya 12.5 px redup di
kiri, pil di kanan), jarak 8 px. Satu-satunya "kotak" adalah blok markdown `.md` (lihat di bawah).

### Inputs / Fields
Hanya `select` (koin, akun, jenis catatan, hari) dan kotak centang; lihat Buttons. Tidak ada input teks bebas yang
menulis data.

### Navigation
Lompat-bagian sticky di bawah header, scroll horizontal tanpa scrollbar dengan pudar 28 px di tepi kanan, jarak 2 px
antar pil; `.on` mengikuti bagian yang terlihat. Header `.top`: brand (h1 + subjudul redup 13 px bergaris putus), jam
WIB (tebal 500 gading), titik kesehatan rata kanan.

### Tip tooltip (tanda tangan)
Label pendek bergaris putus 1 px `pudar` (offset 3 px, `cursor: help`); hover/fokus mengubah garis menjadi kuningan dan
membuka `#tt`: fixed, maks 320 px, padding 9 px / 12 px, latar arang-tooltip, tepi garis-2, radius 6 px, 13 px / 1.45,
`white-space: pre-line` (isi multi-baris dipisah `\n`), masuk 150 ms ease-out (opacity + geser 2 px). Semua keterangan
yang bukan nilai tinggal di sini, termasuk rincian dinamis (saldo bergulir, harga masuk/target/stop, status order,
syarat juara, puncak modal). Selama tooltip terbuka, wadah yang memuatnya tidak dirender ulang.

### Saldo bar
Grid `auto 1fr auto` 13 px redup: label "Bisa dipakai" bergaris putus (tooltip-nya memuat saldo bergulir, hasil hari
ini, terkunci, dan aturan tiket), nilai tebal 600 15 px gading, lalu `.hasil` 12.5 px di kanan yang hanya terisi bila
hasil hari ini bukan nol (mint/koral; pudar saat kosong), lalu batang 4 px trek arang-3 radius 2 px berisi `i` kuningan
(koral saat tidak boleh buka tiket). Tidak ada baris teks di bawah batang. Pola batang yang sama (`.biaya .bar`) dipakai
untuk biaya AI; `warn` amber di atas 70 % batas.

### Baris posisi, order, dan keadaan kosong
- **Posisi** (`li.posisi`): baris 1 = nama koin tebal + arah + leverage sebagai label bergaris putus (`tabindex="0"`,
  tooltip berisi waktu/harga masuk, target dengan % lagi, stop, hangus % lagi, rencana, harga sekarang) dan P/L hidup
  tebal 600 mint/koral (`data-k`); baris 2 (`.l2`, 12.5 px redup, flex gap 10 px) = "harga masuk → target" dengan panah
  `.ke` pudar, lalu "hangus N,N %" (koral bila < 1 %).
- **Order** (`li.order`): baris 1 = koin + arah + leverage bergaris putus (tooltip: status, target, waktu gugur, rencana)
  dan harga limit atau "pasar" redup; baris 2 = "menunggu harga · gugur HH.MM" dengan titik `.ke` pudar. Nama koin
  order redup, bukan gading.
- **Kosong** (`li.nihil`): "Menunggu radar." pudar 13 px, padding 6 px.

### Baris pembanding (`.banding .baris`)
Flex kiri-kanan 13.5 px redup, padding 10 px, garis rambut bawah: label tebal bergaris putus ("Kembaran acak", "Swing";
tooltip berisi gaya, sisa jatah, jumlah posisi/order, dan rincian tiap posisi swing) dan di kanan hanya jumlah posisi
atau daftar "KOIN ARAH" + P/L tebal mint/koral; bila tidak ada: "tidak ada posisi" atau "tidak tersedia".

### Kalimat ringkas
- **Peringkat** (`.juara`, 14.5 px redup, `b` gading): "Juara sementara **X**: rata-rata … per trade dari N trade." atau
  "Belum ada juara · N aktif · N trade · **total** · terdepan **X**", dengan "Belum ada juara" bergaris putus (tooltip:
  syarat ≥ 30 trade).
- **Riwayat** (`.ringkas`, 13.5 px redup, `b` gading): "N trade · **total** · dari puncak X · terdalam Y" dengan "dari
  puncak" dan "terdalam" bergaris putus (tooltip: puncak modal, posisi sekarang, tanggal terdalam); X koral bila di bawah
  puncak.

### Feed (aliran kejadian)
`ol` tanpa bullet, maks 560 px scroll; tiap `li` grid `82px 1fr` (kolom waktu cukup untuk "kemarin 21:40"), padding
7 px, garis rambut atas, 13 px / 1.4; waktu relatif pudar 12 px `nowrap`, nama akun kuningan 600; baris acak diredupkan
(teks redup, nama pudar). Pembatas hari (`li.hari`): blok 11.5 px kapital tracking 0,04 em pudar, padding 8 px / 2 px,
garis atas `garis-2`; tidak muncul untuk kelompok "hari ini" paling atas. Entri baru (`.masuk`) geser masuk 200 ms
ease-out dari -6 px. Pola `.ev` di Pasar memakai grid `44px 1fr` dengan jam WIB, tanpa animasi; teksnya dari
`markerText()` dalam bahasa Indonesia ("LONG di 61.240", "target tercapai di …", "modal hangus di …", "order … tidak
pernah tersentuh", "ditutup di … (stop / jam 23:50)").

### List
`.list li`: padding 8 px, garis rambut bawah (kecuali terakhir), 13.5 px / 1.5; baris `.k` kiri-kanan, sub `.s` redup
12.5 px, `.utama` 14.5 px. `.syarat li` memakai pola kiri-kanan yang sama dengan padding 9 px. Bacaan pasar menampilkan
hanya ringkasan tebal (`.utama`) dan "Yang tidak nyambung" (amber, bergaris putus); kalimat per indikator berada di
`details` "Bacaan per indikator (N)" di dalam item terakhir.

### Tablewrap
Pembungkus scroll dengan garis rambut atas-bawah, maks 440 px; tabel 13.5 px, sel padding 8 px / 10 px, garis rambut
bawah tiap baris (terakhir tanpa), `nowrap`; `th` sticky latar arang teks redup 500 12.5 px; `.num` rata kanan; baris
`.klik` hover arang-2; baris akun acak diredupkan. Di dalam `.md`, tablewrap tanpa batas tinggi dan tabel 13 px.

### Details
Pembuka bagian sekunder: garis rambut atas, margin atas 14 px, summary redup 13.5 px padding 10 px dengan indent kiri
18 px untuk chevron SVG pudar 12 px (mask) yang berputar 90° dalam 150 ms saat terbuka; marker bawaan disembunyikan;
hover summary menjadi gading.

### Blok markdown (`.md`)
Catatan AI (jurnal, catatan pasar harian, evaluasi 23:55) dirender oleh `md()` ke HTML terbatas: `h2`–`h4` (600;
17 / 15.5 / 14 px, `h4` redup; margin 18 px / 6 px), `p` (margin 6 px), `ul`/`ol` (indent 22 px, marker pudar),
`blockquote` (redup, garis kiri 1 px garis-2, indent 12 px), `code` (mono 12.5 px di atas arang-3, radius 4 px),
`pre` (mono, arang-3, radius 6 px, padding 10 px / 12 px, `pre-wrap`), `hr` (garis rambut), tabel (tablewrap), dan `a`
(kuningan). Wadah: latar arang-2, tepi garis, radius 6 px, padding 16 px / 20 px, 14 px / 1.6, maks 80ch, maks 60vh
scroll. Baris "Kunci: nilai" dirender dengan kunci tebal.

### Grafik (Lightweight Charts)
Latar arang, teks redup Inter 12 px, grid garis-grafik, tepi skala `garis`; lilin dan sumbu mint/koral tanpa tepi;
volume mint/koral 28 %; garis silang kuningan; ekuitas area kuningan (30 % → 2 %); drawdown area koral terbalik
(2 % → 40 %); garis arena per warna persona. Penanda: masuk panah mint/koral (acak pudar), TP lingkaran mint,
likuidasi kotak koral, kedaluwarsa/batal lingkaran amber kecil; keterangan penanda "Nama: <markerText>" dalam bahasa
Indonesia.

## Do's and Don'ts

### Do:
- **Do** pisahkan baris dan item dengan garis rambut 1 px `garis`, dan bagian dengan garis 2 px `sep`; biarkan latar
  tetap arang.
- **Do** beri tiap judul bagian garis kuningan 28 × 2 px di bawahnya; selain itu pakai kuningan hanya untuk pilihan
  aktif, fokus, tautan, nama akun di feed, dan denyut perubahan; teks di atasnya kuningan-tinta.
- **Do** warnai angka uang dengan mint/koral berdasarkan tanda, tebal 600, tabular, rata kanan di tabel; nol ditulis "$0,00".
- **Do** tulis satu baris per keadaan; taruh rincian dan definisi di tooltip lewat label bergaris putus yang juga bisa
  difokus keyboard (`tabindex="0"`) atau di blok `details`, dan jangan render ulang wadah yang sedang dibaca.
- **Do** tulis "tidak tersedia" (atau "—") dalam pudar beserta alasan ketika data tidak ada.
- **Do** tandai nilai yang berubah dengan `data-k` supaya denyut 600 ms berjalan; entri baru masuk dengan geser 200 ms;
  hormati `prefers-reduced-motion`.
- **Do** tulis waktu di feed secara relatif dengan pembatas hari; di tempat lain pakai jam WIB.
- **Do** runtuhkan grid dua kolom menjadi satu pada ≤ 1100 px dan meja analis menjadi satu kolom pada ≤ 640 px.

### Don't:
- **Don't** tambahkan kartu, panel berlatar, atau kotak di dalam kotak; `.md` adalah satu-satunya blok berlatar.
- **Don't** pakai bayangan pada permukaan di dalam halaman; bayangan hanya untuk tooltip yang melayang.
- **Don't** pakai mint/koral untuk hal selain arah uang atau hidup/mati sistem, dan jangan pakai warna persona sebagai
  latar.
- **Don't** tambahkan aksi primer, tombol beli/jual, atau input yang menulis data; dashboard hanya membaca.
- **Don't** tambahkan baris keterangan di bawah nilai; kalau perlu dijelaskan, pindahkan ke tooltip atau `details`.
- **Don't** tambahkan motion selain denyut garis bawah, geser masuk entri, dan putaran chevron; durasi tetap 150–600 ms
  ease-out.
- **Don't** pakai bobot 700 di luar nama analis, dan jangan pakai huruf mono di luar `code`/`pre` markdown.
- **Don't** tampilkan jargon mesin (kode event, nama tabel, JSON) di layar; terjemahkan ke kalimat Indonesia.
- **Don't** mengestimasi angka yang tidak tersedia atau memberinya warna semantik.
