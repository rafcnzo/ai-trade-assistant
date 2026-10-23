---
name: crypto-analyst — Meja analis
description: Dashboard baca-saja berupa ruang observasi akuarium laut dalam; tiap analis diamati lewat tangki kaca beku, uang paper menyala sebagai cahaya biolumines.
colors:
  abyss: "#040d12"
  deep: "#06141b"
  water: "#0a2230"
  glass: "rgba(10,38,50,.52)"
  glass-hi: "rgba(120,220,230,.07)"
  glass-solid: "#0b2531"
  edge: "rgba(150,235,240,.14)"
  edge-hi: "rgba(200,255,250,.16)"
  line: "rgba(150,235,240,.10)"
  line2: "rgba(150,235,240,.20)"
  th-bg: "rgba(9,32,42,.94)"
  tooltip-bg: "rgba(4,18,25,.9)"
  ink: "#e6f4f1"
  muted: "#9dbcc2"
  dim: "#7896a0"
  glow: "#63e6ff"
  glow-ink: "#03141a"
  up: "#6be89a"
  down: "#ff7a6b"
  warn: "#f3c969"
  persona-tiket: "#ffd27a"
  persona-fade: "#8ab4ff"
  persona-breakout: "#c79bff"
  persona-rentang: "#ff9ad5"
  persona-acak: "#7896a0"
  persona-swing: "#ffb07a"
typography:
  headline:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    letterSpacing: "-0.025em"
  page-title:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.03em"
  value-lg:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 750
    letterSpacing: "-0.02em"
  nama-analis:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 750
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  body-md:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  body-small:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 550
  caption:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
  micro:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 600
  pil:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.04em"
  cap:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "10.5px"
    fontWeight: 800
    lineHeight: 1.5
    letterSpacing: "0.08em"
  mono:
    fontFamily: "ui-monospace, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  cap: "4px"
  kontrol: "10px"
  tooltip: "12px"
  baris: "14px"
  kaca: "18px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "10px"
  grid-meja: "14px"
  head: "16px"
  grid: "18px"
  bagian: "40px"
  gutter: "clamp(14px, 2.4vw, 36px)"
components:
  kaca:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.kaca}"
    padding: "16px 18px"
  tangki-analis:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.kaca}"
    padding: "14px 16px 12px"
  jump-link:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 14px"
    height: "34px"
  jump-link-on:
    backgroundColor: "{colors.glow}"
    textColor: "{colors.glow-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 14px"
    height: "34px"
  seg-button:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "30px"
  seg-button-on:
    backgroundColor: "{colors.glow}"
    textColor: "{colors.glow-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "30px"
  kontrol:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.kontrol}"
    padding: "6px 11px"
    height: "36px"
  pil:
    textColor: "{colors.muted}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  pil-ok:
    textColor: "{colors.up}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  pil-off:
    textColor: "{colors.down}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  pil-hold:
    textColor: "{colors.warn}"
    typography: "{typography.pil}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  tag:
    textColor: "{colors.muted}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    padding: "0 8px"
  tag-ok:
    textColor: "{colors.up}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    padding: "0 8px"
  tag-belum:
    textColor: "{colors.warn}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    padding: "0 8px"
  cap-exp:
    textColor: "{colors.warn}"
    typography: "{typography.cap}"
    rounded: "{rounded.cap}"
    padding: "0 6px"
  cap-can:
    textColor: "{colors.muted}"
    typography: "{typography.cap}"
    rounded: "{rounded.cap}"
    padding: "0 6px"
  cap-rej:
    textColor: "{colors.down}"
    typography: "{typography.cap}"
    rounded: "{rounded.cap}"
    padding: "0 6px"
  tooltip:
    backgroundColor: "{colors.tooltip-bg}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.tooltip}"
    padding: "10px 13px"
    width: "320px"
  th:
    backgroundColor: "{colors.th-bg}"
    textColor: "{colors.muted}"
    typography: "{typography.micro}"
    padding: "8px 10px"
  md-block:
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    width: "80ch"
  md-code:
    backgroundColor: "{colors.line}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    padding: "1px 6px"
---

# Design System: crypto-analyst — Meja analis

## Overview

**Creative North Star: "Ruang Observasi Laut Dalam"**

Dashboard ini adalah ruang observasi akuarium pada malam hari, dilirik sepanjang hari dari laptop pemilik. Halaman adalah
air laut dalam yang bergradasi dari permukaan yang masih tertembus cahaya ke dasar yang hampir hitam, dengan beberapa titik
biolumines buram yang diam dan berkas cahaya miring dari atas. Kaca di sini harfiah: setiap analis diamati lewat satu
tangki kaca beku (blur 18 px, tepi atas memantulkan cahaya 1 px, bayangan lembut ke bawah) yang puncaknya diterangi warna
persona analis itu; uang paper adalah cahaya: batang saldo menyala cyan, angka yang berubah berpendar lalu memudar.

Kepadatannya tinggi tetapi tenang: teks 12–15 px, sel bergaris padat di dalam kaca, angka tabular supaya kolom tidak
bergoyang saat polling 5 detik. Keadaan ditulis sebagai kalimat ("BTC LONG 5× · 61.240 → 61.730 · hangus 4,2 %"), bukan
kotak KPI. Label penjelas tidak tinggal di layar: definisi dan rincian ada di tooltip pada label bergaris putus atau di
blok `details`. Latar tidak bergerak; gerak hanya pada data (denyut biolumines, entri kejadian yang geser masuk, chevron).

Anti-referensi yang dikonfirmasi: dunia lama arang hangat + kuningan + tanpa kartu (13 Okt 2026) sudah diganti seluruhnya,
dan tetap ditolak: estimasi untuk data yang tidak ada ("tidak tersedia" beserta alasannya), serta aksi apa pun di dashboard
baca-saja.

**Key Characteristics:**
- Air bergradasi tetap (`water` → `deep` → `abyss`) dengan titik biolumines buram yang diam; tidak ada animasi latar.
- Satu wadah: panel kaca beku `.kaca`; bagian = judul di atas air + kolom-kolom kaca; tidak ada kaca di dalam kaca.
- Satu cahaya fokus cyan (`glow`) untuk pilihan, fokus, crosshair, dan cahaya uang; hijau fosfor/koral hanya arah uang;
  kuning umpan anglerfish untuk tunggu dan batas.
- Warna persona adalah cahaya: puncak tangki, nama analis, garis grafik arena; tidak pernah menjadi latar padat.
- Satu keluarga huruf, Plus Jakarta Sans, angka tabular di seluruh dokumen.
- Baca-saja: kontrol hanya memilih tampilan.

## Colors

Palet air laut dalam biru-hijau yang sangat gelap, tinta busa sejuk, satu cahaya cyan, tiga warna semantik bercahaya, dan
enam cahaya persona.

### Primary
- **Cahaya Fokus** (`glow`): pil navigasi aktif dan segmen aktif (diisi penuh, teks `glow-ink`), cincin fokus 2 px,
  garis bawah tooltip saat hover, `::selection`, `caret-color`, `accent-color` kotak centang, crosshair grafik (garis 60 %,
  label penuh), batang saldo yang sehat (gradien 55 % → penuh dengan pendar), batang biaya, area ekuitas, garis harga
  "masuk", chevron `details`, marker daftar dan tautan markdown, nomor kandidat di blok keputusan, pembatas hari di feed,
  "N terbuka"/"berjalan"/sisa swing, dan pendar angka yang berubah. Juga warna puncak tangki bawaan bila persona tidak dikenal.
- **Tinta di atas cahaya** (`glow-ink`): satu-satunya warna teks di atas `glow`.

### Secondary
- **Hijau fosfor** (`up`): untung, LONG masuk, TP, "boleh buka"/"aktif"/"jalan", titik kesehatan OK (dengan pendar 8 px),
  lilin naik, volume naik 26 %, garis harga target, tag `ok`.
- **Koral** (`down`): rugi, SHORT masuk, likuidasi, "pensiun"/mati/basi, batang saldo saat tidak boleh buka tiket, lilin
  turun, area drawdown, garis harga "hangus", cap `rej`, pesan galat, jarak hangus < 1 %.
- **Kuning umpan** (`warn`): tunggu dan batas: pil "berhenti", tag `belum` ("terlewat", "pensiun" di tabel arena), titik
  kesehatan waspada, batang biaya > 70 % batas, cap `exp`, garis harga order menunggu (putus-putus), penanda order
  kedaluwarsa/batal di grafik.

### Tertiary
- **Cahaya persona** (`persona-tiket` emas, `persona-fade` biru, `persona-breakout` ungu, `persona-rentang` merah muda,
  `persona-swing` jingga, `persona-acak` = `dim`): didefinisikan sebagai `--p-*` di `:root` dan dibaca `app.js` lewat
  `cssv()` ke `WARNA`. Dipakai sebagai `--w` tangki (pendar radial 16 % di puncak dan garis tepi atas 55 %), nama analis
  di tangki/feed/tabel/kecenderungan/keputusan, dan garis grafik arena (persona 2 px, acak 1 px putus-putus).

### Neutral
- **Permukaan air** (`water`), **Air dalam** (`deep`), **Dasar** (`abyss`): gradien latar `body` 180° (0 % / 42 % / 100 %)
  di bawah empat cahaya radial (cyan kiri atas, biru kanan atas, koral samar kiri bawah, hijau-laut di dasar), `fixed`.
  `abyss` juga latar `html`.
- **Kaca** (`glass`) + **kilau kaca** (`glass-hi`, gradien 120 px dari atas) + butiran `--grain` (SVG fractal noise 7,5 %):
  isi setiap panel kaca. **Kaca padat** (`glass-solid`): fallback tanpa `backdrop-filter`, latar `option`, dan sel Hasil
  sticky di tabel Riwayat ponsel.
- **Tepi kaca** (`edge`): tepi 1 px panel kaca dan bar navigasi; garis skala grafik (`GARIS` di `app.js`, nilai sama).
  **Kilau tepi** (`edge-hi`): pantulan 1 px di tepi atas dalam (`--shadow`).
- **Garis** (`line`): pemisah rambut antar baris, sel, item daftar, kepala panel; tepi titik kesehatan.
  **Garis-2** (`line2`): tepi kontrol, segmen, pil, tag, tooltip; tepi bawah `th`; pembatas hari dan antar blok keputusan;
  thumb scrollbar.
- **Kepala tabel** (`th-bg`): latar `th` sticky. **Tooltip** (`tooltip-bg`): latar `#tt` di atas blur 14 px.
- **Tinta busa** (`ink`): teks utama dan nilai tebal. **Redup** (`muted`): teks sekunder, lead, `th`, kontrol tak aktif,
  teks grafik, baris acak, "SKIP". **Pudar** (`dim`): waktu, panah `→`, keadaan kosong, "tidak tersedia", `small` di
  judul, footer, garis bawah putus label tooltip.

### Named Rules
**The Satu Cahaya Rule.** `glow` adalah satu-satunya aksen non-semantik; ia menyala pada pilihan, fokus, dan uang yang
bergerak, tidak pernah menjadi latar area atau teks tubuh. Isian penuh `glow` hanya untuk pilihan aktif (pil navigasi,
segmen), dan teks di atasnya selalu `glow-ink`.

**The Arah Uang Rule.** `up` dan `down` hanya mengatakan arah uang atau hidup/mati sistem; `warn` hanya tunggu atau batas.
Ketiganya tidak pernah menandai persona atau dekorasi.

**The Cahaya Persona Rule.** Warna persona hanya hadir sebagai cahaya (pendar puncak tangki, tepi atas, nama, garis
grafik). Tidak pernah sebagai latar padat atau warna semantik.

**The Tidak Tersedia Rule.** Data yang tidak ada ditulis "tidak tersedia" (atau "—") dalam `dim`, beserta alasan bila
ada; nol ditulis "$0,00". Tidak pernah estimasi, tidak pernah warna semantik.

## Typography

**Display Font:** Plus Jakarta Sans (dengan system-ui, -apple-system, Segoe UI, sans-serif)
**Body Font:** Plus Jakarta Sans (sama)
**Label/Mono Font:** ui-monospace, Consolas, monospace; hanya `code` dan `pre` di blok markdown.

**Character:** Satu keluarga dari desainer Jakarta, geometris dan hangat, dengan `tabular-nums` di `body` sehingga semua
angka sejajar. Hirarki datang dari bobot (700–800 untuk nama dan nilai) dan nada tinta, bukan dari ukuran besar. Dimuat
dari Google Fonts sebagai font variabel (sumbu bobot 400–800), jadi bobot antara 550/650/750 dirender apa adanya.

### Hierarchy
- **Headline** (700, 24px, -0,025 em; 21px ≤ 640 px): judul bagian `h2` di atas air; judulnya sendiri label tooltip.
- **Page title** (700, 22px, -0,03 em; 20px ≤ 640 px): "Meja analis" di header.
- **Nama analis** (750, 18px, -0,025 em): `h3` tangki dalam warna persona.
- **Value-lg** (750, 20px, -0,02 em): nilai "Bisa dipakai" di tangki.
- **Title** (700, 15px): judul panel kaca `h3` dengan `small` 12px 500 `dim` di kanan; `h2/h3/h4` markdown 17/15,5/14px.
- **Body** (400, 14.5px, 1.5; 14px ≤ 640 px): teks dasar; P/L posisi 750 15px; `.juara` 14,5px `muted` dengan `b` `ink`.
- **Body-md** (400, 14px, 1.65): blok markdown, maks 80ch.
- **Body-small** (400, 13.5px, 1.45): baris tangki, tabel, daftar, summary, `.ringkas`, lead bagian (maks 72ch).
- **Label** (550, 13px): pil navigasi, segmen, kontrol (600 untuk `.btn`), feed (400), tooltip (400, 1.45).
- **Caption** (400, 12.5px): baris kedua posisi, gaya analis, `.terakhir`, titik kesehatan, info grafik, footer.
- **Micro** (600, 12px): `th`; juga waktu feed (400) dan isi tag (400).
- **Pil** (700, 11px, 0,04 em, kapital): pil status tangki. Pembatas hari di feed: 11px 700, 0,06 em, kapital, `glow`.
- **Cap** (800, 10.5px, 0,08 em, kapital): cap order batal/kedaluwarsa/ditolak.
- **Mono** (400, 12.5px, 1.5): `code` dan `pre` markdown.

### Named Rules
**The Angka Tabular Rule.** Semua angka tabular (diset di `body`), rata kanan di kolom `.num`, diformat `id-ID`; USD
utama, IDR hanya dalam kurung.

**The Kalimat Bukan Kotak Rule.** Keadaan dinyatakan sebagai kalimat dengan nilai inline tebal (koin tebal, arah,
leverage, jarak ke target/hangus), bukan angka besar terpisah. Satu-satunya nilai besar adalah saldo "Bisa dipakai".

**The Layar Tipis Rule.** Satu baris per keadaan; rincian (harga masuk/target/stop, status order, saldo bergulir, syarat
juara, puncak modal, bacaan per indikator, kolom Riwayat yang dipangkas, rincian mesin/biaya) tinggal di tooltip atau
`details`.

**The Waktu Relatif Rule.** Di feed dan baris `.terakhir`, waktu relatif ("baru saja", "12 mnt", jam untuk hari ini,
"kemarin 21.40", lalu tanggal + jam); feed dipisah pembatas hari ("hari ini" disembunyikan bila kelompok teratas).
Di tempat lain jam WIB.

## Layout

Single-page scroll, tujuh `section.bag` berurutan **Sekarang, Pasar, Ringkasan, Peringkat, Riwayat, Konteks, Catatan AI**
(Pasar naik ke posisi 2 agar grafik besar tepat di bawah tangki). Header tipis `.top` di atas air (brand + subjudul
bertooltip, jam WIB 15px 650, titik kesehatan rata kanan), lalu bar lompat-bagian kaca berbentuk pil yang menempel
(`sticky`, top 10 px, z 20); pil aktif mengikuti bagian terlihat (`IntersectionObserver`, rootMargin -40 %/-55 %) dan di
layar sempit bar menggulir menyamping agar pil aktif di tengah. `main` ber-gutter `spacing.gutter`, bagian berpadding atas
40 px, `scroll-margin-top` 64 px; `.head` (judul + kontrol) berjarak 16 px ke isi.

Grid per bagian, semuanya `align-items: start`, jarak 18 px, anak `min-width: 0`:
- **Sekarang**: `minmax(0,1fr) 360px`: meja `repeat(auto-fit, minmax(230px,1fr))` jarak 14 px (empat tangki pada 1440) +
  baris pembanding acak/swing `minmax(260px,1fr)`; panel Kejadian 360 px.
- **Pasar**: `minmax(0,1fr) 300px`: jendela grafik 540 px + panel "Jejak pada koin ini" (maks 520 px gulir).
- **Ringkasan**: `minmax(0,1fr) minmax(0,1.3fr)`.
- **Peringkat**, **Riwayat**: `minmax(0,1fr) 340px`.
- **Konteks**: `repeat(auto-fit, minmax(300px,1fr))`.
- **Catatan AI**: satu panel kaca maks 1100 px.

Tinggi tetap: lilin 540 px, arena 240 px, ekuitas 220 px, drawdown 120 px. Feed maks 470 px, tabel maks 440 px dengan
gulir di dalam panel; markdown maks 60vh (catatan pasar di Konteks 320 px).

**Tablet (≤ 1100 px):** semua grid dua kolom jadi satu kolom; feed 340 px, kejadian 300 px, lilin 460 px.

**Ponsel (≤ 640 px):** `--r` 14 px, kaca padding 13/14 px, `h2` 21px, bagian berpadding 30 px. Kesehatan rata kiri selebar
penuh; bar lompat selebar gutter. Tangki bertumpuk satu kolom (jarak 10 px). **Tanpa gulir bersarang:** feed tidak
dibatasi tinggi dan hanya enam kejadian terbaru yang tampil (`li.lebih` disembunyikan, termasuk pemisah harinya; jam di atas kalimat, grid satu kolom); "Jejak pada koin ini" hanya
delapan baris. Grafik lilin **380 px** dengan padding 8/6 px. Kontrol kepala selebar penuh; filter Riwayat dua per baris.
Kecenderungan analis satu kolom. Tabel tetap bergulir di dalam panel, sel 7/8 px; di `#tbl-posisi` kolom **Hasil**
menempel di kanan (`sticky`, latar `glass-solid`) supaya hasil terlihat saat tabel digulir. Target sentuh **≥ 36 px**:
pil navigasi, tombol segmen, kontrol, kotak centang (label 36 px); summary `details` 40 px.

**Polling dan render.** Ringkasan 5 detik, grafik 15 detik, keputusan 30 detik, daftar koin/arena/ekuitas/kandidat 60 detik,
psikologi 5 menit. Nilai yang berubah ditandai `data-k` dan didenyutkan. `setHTML` melewati render wadah yang sedang
dibaca (tooltip terbuka atau fokus keyboard di dalamnya, `sibuk`).

## Elevation & Depth

Kedalaman adalah air dan kaca. Latar adalah lapisan cahaya tetap (gradien + titik biolumines blur 60 px + berkas cahaya
miring yang memudar ke bawah); panel kaca melayang di atasnya dengan `backdrop-filter: blur(18px) saturate(140%)`, butiran,
kilau atas, dan bayangan lembut ke bawah. Hanya satu tingkat kaca: tidak ada kaca di dalam kaca. Bila browser tidak
mendukung `backdrop-filter`, `.kaca` dan `.jump` memakai `glass-solid`.

### Shadow Vocabulary
- **Kaca** (`--shadow`: `0 1px 0 var(--edge-hi) inset, 0 22px 44px -26px rgba(0,0,0,.75), 0 2px 6px -2px rgba(0,0,0,.35)`):
  setiap panel kaca dan bar lompat-bagian.
- **Tangki** (sama, tetapi pantulan atas `color-mix(--w 55%)`): tepi atas tangki menyala warna persona.
- **Tooltip** (`0 14px 32px -12px rgba(0,0,0,.8)`): `#tt`, di atas blur 14 px.
- **Pendar** (`0 0 8–18px color-mix(<warna> 60–80%)`): titik kesehatan, batang saldo/biaya, pil navigasi aktif. Cahaya,
  bukan elevasi.

### Named Rules
**The Satu Lapis Kaca Rule.** Bagian = judul di atas air + kolom-kolom kaca. Isi panel dipisah garis rambut, tidak pernah
dengan panel kaca kedua; tooltip dan bar navigasi adalah lapisan yang mengambang, bukan kaca bersarang.

**The Air Diam Rule.** Latar tidak bergerak (hemat GPU, laptop menyala seharian); gerak hanya pada data.

## Shapes

Sudut lembut seperti kaca cetak: panel kaca 18 px (14 px di ponsel), baris pembanding 14 px, tooltip 12 px, kontrol 10 px;
pil navigasi, segmen, pil status, tag, titik kesehatan, batang 5 px, dan thumb scrollbar berbentuk kapsul penuh. Tepi 1 px
semi-transparan, tidak pernah tepi padat; pil dan tag berwarna mewarnai tepi 45 % dan isi 9–10 % warna semantiknya.
**Cap** adalah satu-satunya bentuk bersudut: kotak 4 px, tepi `1.5px double currentColor`, diputar -3°, opasitas 0,9,
seperti stempel pada tiket. Ikon satu-satunya: chevron SVG 12 px (stroke 1,6, ujung bulat) sebagai `mask` berwarna `glow`
di `details`, berputar 90° saat terbuka.

## Components

### Buttons (segmen dan kontrol tampilan)
Tidak ada tombol aksi primer; semua kontrol hanya memilih tampilan.
- **Segmen** (`.seg`): kapsul berbingkai `line2` di atas air 55 %, padding 3 px, tombol tanpa tepi `muted` 13px 550 tinggi
  30 px (36 px ponsel); hover `ink` di atas cyan 8 %; aktif isi `glow` + `glow-ink` 700. Rentang lilin, akun ekuitas, BTC/ETH.
- **Kontrol** (`select`, `input`, `.btn`): latar air 70 %, tepi `line2`, radius 10 px, 13px, tinggi min 36 px; hover tepi
  cyan 55 %; `.btn` 600 dengan hover isi cyan 12 %. Kotak centang `accent-color` `glow` 16 px.
- **Fokus global**: `outline: 2px solid glow`, offset 2 px, radius 6 px; di segmen aktif outline `glow-ink` offset -4 px.

### Chips
- **Pil status** (`.pil`): kapsul 11px 700 kapital, `ok` (boleh buka), `off` (pensiun), `hold` (berhenti), atau netral
  ("tidak tersedia"); hanya di kepala tangki, dibungkus label tooltip.
- **Tag** (`.tag`): kapsul 12px; `ok` "tepat"/"aktif", `belum` "terlewat"/"pensiun"; `takut`/`serakah` hanya mewarnai teks.
- **Cap** (`.cap`): stempel di depan kalimat order yang tidak jadi, agar tetap terlihat: `exp` "kedaluwarsa" (`warn`),
  `can` "batal" (`muted`), `rej` "ditolak" (`down`). Muncul di feed, "Jejak pada koin ini", dan tabel order Riwayat.

### Cards / Containers
- **Panel kaca** (`.kaca`): radius 18 px, isi kaca + butiran + kilau, tepi `edge`, bayangan kaca, padding 16/18 px. Judul
  panel `h3` dengan garis rambut bawah. Wadah satu-satunya.
- **Tangki analis** (`article.analis.kaca`): kaca dengan pendar radial persona di puncak, padding 14/16/12 px. Kepala grid:
  nama 18px 750 warna persona + pil di kanan, gaya analis 12,5px `muted` bertooltip di bawah. Blok saldo grid `auto 1fr
  auto`: label "Bisa dipakai" bertooltip (saldo bergulir, hasil hari ini, terkunci, aturan tiket), nilai 20px 750, `.hasil`
  hari ini di kanan (hanya bila bukan nol), batang 5 px menyala `glow` (`down` bila tidak boleh buka). Lalu baris posisi
  dan order bergaris rambut; kosong: "Menunggu radar." `dim`.
- **Tangki pensiun** (`.analis.pensiun`): `filter: grayscale(1)` dan opasitas 0,55; tangki tetap di tempatnya, pilnya
  `off` "pensiun".
- **Baris pembanding** (`.banding .baris.kaca`): kaca radius 14 px, padding 11/16 px, label tebal bertooltip ("Kembaran
  acak", "Swing") kiri, jumlah posisi atau P/L di kanan.

### Inputs / Fields
Hanya `select`, `input[type=date]`, input koin di filter Riwayat (tidak menulis data), dan kotak centang. Lihat Buttons.
Ikon kalender di-tint ke cyan; placeholder `dim`.

### Navigation
Bar lompat-bagian: kapsul kaca (air 62 % + blur 18 px + tepi `edge` + bayangan kaca), padding 5 px, jarak 2 px, scrollbar
tersembunyi. Pil 13px 550 `muted`, tinggi 34 px (36 px ponsel); hover `ink` di atas cyan 8 %; aktif isi `glow` + `glow-ink`
700 dengan pendar 18 px. Klik baris tabel (`tr.klik`) memilih koin dan menggulir ke Pasar.

### Tooltip (tanda tangan: label hanya di tooltip)
Label pendek bergaris bawah titik-titik 1 px `dim` (offset 3 px, `cursor: help`, `tabindex="0"`); hover/fokus mengubah
garis ke `glow` dan membuka `#tt`: fixed, maks 320 px, padding 10/13 px, `tooltip-bg` + blur 14 px, tepi `line2`, radius
12 px, 13px/1.45, `white-space: pre-line`, masuk 150 ms ease-out (opacity + geser 3 px). Ditutup saat menggulir. Semua
keterangan yang bukan nilai tinggal di sini, termasuk judul bagian dan judul panel.

### Baris posisi, order, dan `.terakhir` di tangki
- **Posisi**: baris 1 = koin tebal + arah + leverage sebagai label tooltip (masuk, target dan % lagi, stop, hangus % lagi,
  rencana, harga sekarang) dan P/L 750 15px `up`/`down` (`data-k`); baris 2 caption `muted` = "masuk → target" (panah
  `dim`), "hangus N,N %" (`down` bila < 1 %), dan untuk swing "sisa N % · TPn kena · n leg" dalam `glow`.
- **Order**: koin `muted` + arah + leverage bertooltip (status, target, waktu gugur, rencana), harga limit atau "pasar";
  baris 2 "menunggu harga · gugur HH.MM".
- **Terakhir** (`.terakhir`): baris penutup tangki, garis rambut atas, 12,5px `dim` dengan waktu `muted`; menampilkan yang
  lebih baru antara kejadian mesin dan keputusan jurnal: "49 mnt SKIP K222 1000PEPE · **R:R < 0,5 (P-19)**" dengan label
  alasan bertooltip (kalimat alasan utuh), atau "order #31 K…".

### Feed (Kejadian) dan Jejak
Panel kaca 360 px; `ol` grid `76px 1fr` per `li`, padding 8 px, garis rambut atas, 13px/1.42; waktu relatif 12px `dim`,
nama akun 700 dalam warna persona, cap bila order gugur/batal; baris acak diredupkan. Pembatas hari `li.hari` (hanya di
feed) 11px 700 kapital `glow` dengan garis `line2` di atas. Entri baru (`.masuk`) geser masuk 200 ms ease-out dari -6 px.
"Jejak pada koin ini" memakai grid `44px 1fr` dengan jam WIB, maks 14 entri, teks dari `markerText()`.

### Tablewrap
Gulir di dalam panel, maks 440 px; tabel 13,5px, sel 8/10 px, garis rambut bawah, `nowrap`; `th` sticky `th-bg` 12px 600
`muted` dengan tepi `line2`; `.num` rata kanan; `tr.klik` hover cyan 7 %; baris acak `muted`. Riwayat dipangkas ke kolom
inti (posisi: Ditutup, Analis, Koin, Keluar, Hasil; order: Dibuat, Analis, Koin, Apa yang terjadi); sel Koin label tooltip.

### Keputusan analis (Catatan AI)
Format sama dengan pesan Telegram, satu blok `.kep` per kandidat radar, terbaru dulu; enam pertama terbuka, sisanya di
`details` "N kandidat lebih awal". Di atasnya `.ringkas`: "N kandidat · N order · N SKIP · SKIP tepat **a/b**" ("SKIP
tepat" bertooltip). Blok dipisah garis `line2` (bukan kaca). Kepala `.kep-h` 14px: **K221** `glow`, label tooltip
"**DOGE** beli" (mark, level, sentuhan, ATR 15m, tren, tanda, skor, hasil order bayangan), jam 12,5px `dim`, ringkas
`muted`. Lalu tablewrap tanpa batas tinggi, `table-layout: fixed`, kolom sejajar di semua blok:
- **Desktop:** Analis 110 px (nama warna persona) · Hasil 150 px ("SKIP" `muted`, atau "**order #31** beli" bertooltip
  limit/leverage/target/status) · Timbangan sisa ("skip 3 · open 2", sisi pemenang `down`/`up` dan sisi lain `muted`, tag
  `veto` koral dan tag `belum` "tidak sesuai" bertooltip, boleh membungkus; keputusan lama tanpa poin: label kategori
  bertooltip) · Penilaian 170 px
  (tag `ok` "tepat", tag `belum` "terlewat +$0,56", "netral"/"belum dinilai"/"tidak tersedia" `dim` bertooltip, hasil order
  nyata `up`/`down` + alasan keluar `muted`, "berjalan" `glow`). Tabel min 560 px, gulir di dalam tablewrap.
- **≤ 640 px:** min-width dilepas; kolom 84 / 52 / sisa / 92 px, dan sel Timbangan boleh membungkus baris.
- **Poin alasan** (`tr.poin` tepat di bawah baris analisnya; baris analis tanpa garis bawah): satu sel `colspan=4` berisi
  `.poin-grid` dua kolom (satu kolom ≤ 640 px) di atas air gelap 35 % dengan garis `line` dan radius 12 px. "Alasan SKIP n"
  12px 700 `down` dan "Alasan OPEN n" `up`, daftar 13px dengan penanda bulat warna sisinya; poin `VETO:` ditulis `ink` 600
  dengan cap `rej` "veto" tegak di depannya; sisi kosong = "tidak ada" `dim`. Kalimat isi jurnal (bila ada) di bawahnya 12,5px `muted`.

### Details
Garis rambut atas, margin atas 12 px; summary 13,5px 550 `muted`, padding 11 px dengan indent 20 px untuk chevron `glow`,
tinggi min 40 px; marker bawaan disembunyikan; hover `ink`; chevron berputar 90° dalam 150 ms.

### Blok markdown (`.md`)
Catatan AI dirender `md()` ke HTML terbatas, langsung di dalam panel (tanpa kotak sendiri): 14px/1.65, maks 80ch, maks 60vh
gulir; `h2`–`h4` 700 17/15,5/14px (`h4` `muted`); marker daftar dan tautan `glow`; `blockquote` `muted` bergaris kiri
`line2`; `code` mono di atas cyan 8 % radius 5 px; `pre` di atas air gelap bertepi `line`, radius 10 px; `hr` garis rambut;
tabel lewat tablewrap tanpa batas tinggi, 13px. Paragraf satu baris "Kunci: nilai" dirender dengan kunci tebal.

### Grafik (Lightweight Charts)
`baseOpts`: latar transparan (kaca terlihat), teks `muted` Plus Jakarta Sans 12px, grid cyan 5 %, tepi skala `edge`,
crosshair `glow` 60 % dengan label `glow`, lokal `id-ID` dan jam WIB. Lilin `up`/`down` tanpa tepi; volume 26 % di 15 %
bawah. Penanda: masuk panah `up`/`down` (acak `dim`), TP lingkaran `up`, likuidasi kotak `down` (acak 50 %), kedaluwarsa/
batal lingkaran kecil `warn`. Garis harga 1 px berlabel: masuk `glow`, target `up`, stop `muted`, hangus `down`, order
`warn` putus-putus. Ekuitas area `glow` 28 % → 2 %; drawdown area `down` terbalik 2 % → 40 %; arena garis per persona.

### Titik kesehatan
Kapsul 12,5px `muted` bertepi `line` di atas air 40 %, titik 8 px: `ok` `up`, `warn` `warn`, `bad` `down` (teks dan tepi
ikut koral), masing-masing berpendar 8 px; tanpa status `dim`. Semua rincian di tooltip.

### Denyut polling (tanda tangan)
Angka yang berubah (`data-k`) berpendar biolumines: `text-shadow` `glow` 14 px + teks putih yang memudar 700 ms
`cubic-bezier(.16,1,.3,1)`. Dimatikan oleh `prefers-reduced-motion` bersama geser masuk feed dan transisi tooltip.

## Do's and Don'ts

### Do:
- **Do** letakkan setiap kelompok isi di satu panel kaca `.kaca` (blur 18 px, radius 18 px, tepi `edge`, `--shadow`) di
  bawah judul bagian yang berdiri di atas air; pisahkan isi panel dengan garis rambut `line`.
- **Do** pakai `glow` hanya untuk pilihan, fokus, crosshair, dan cahaya uang; teks di atas isian `glow` selalu `glow-ink`.
- **Do** warnai uang dengan `up`/`down` menurut tanda, tebal, tabular, rata kanan di tabel; nol ditulis "$0,00".
- **Do** baca warna di `app.js` dari variabel CSS (`cssv()`, `K`, `WARNA`); token baru ditambahkan di `:root`, bukan di JS.
- **Do** tampilkan warna persona sebagai cahaya: pendar puncak tangki, tepi atas, nama, garis grafik.
- **Do** biarkan order batal/kedaluwarsa/ditolak tetap terlihat dengan cap bersudut 4 px berputar -3°.
- **Do** pudarkan tangki analis pensiun (grayscale, opasitas 0,55) di tempatnya, bukan menyembunyikannya.
- **Do** taruh rincian dan definisi di tooltip pada label bergaris putus yang bisa difokus, atau di `details`; jangan render
  ulang wadah yang sedang dibaca.
- **Do** tandai nilai berubah dengan `data-k` untuk denyut 700 ms; hormati `prefers-reduced-motion`.
- **Do** di ≤ 640 px: satu kolom, tanpa gulir bersarang di feed (enam baris), grafik 380 px, kolom Hasil `#tbl-posisi`
  menempel, target sentuh ≥ 36 px.

### Don't:
- **Don't** menaruh kaca di dalam kaca, atau kembali ke dunia arang hangat + kuningan tanpa kartu.
- **Don't** menganimasikan latar air, titik biolumines, atau berkas cahaya.
- **Don't** memakai `up`/`down`/`warn` untuk persona atau dekorasi, atau warna persona sebagai latar padat.
- **Don't** menambah aksi primer, tombol beli/jual, atau input yang menulis data; dashboard hanya membaca.
- **Don't** menambah baris keterangan di bawah nilai; pindahkan ke tooltip atau `details`.
- **Don't** memakai huruf selain Plus Jakarta Sans, kecuali mono untuk `code`/`pre` markdown.
- **Don't** menampilkan jargon mesin (kode event, nama tabel, JSON); terjemahkan ke kalimat Indonesia.
- **Don't** mengestimasi angka yang tidak tersedia atau memberinya warna semantik.
