---
version: 1
slug: "dashboard-index-html"
primary_target: "dashboard/index.html"
related_targets: ["dashboard/app.js","dashboard/style.css"]
---

# Surface: dashboard (/, dashboard/index.html + app.js + style.css)

Mode: Operate. Layar pantau pemilik sambil bekerja; dilirik, bukan dibaca. Pengganti total dashboard lama (keputusan 13 Okt 2026).

Audience/job: pemilik memantau empat analis AI (persona arena) yang paper trading; prioritas 3 detik pertama = apa yang
sedang terjadi sekarang (posisi, order, kejadian), lalu siapa unggul, lalu konteks. Baca-saja; tidak ada aksi.

Constraints pinned by brief: rich text yang mudah dibaca; label/keterangan hanya di tooltip (hover + fokus keyboard);
warna sederhana, elegan, kontras tinggi; Bahasa Indonesia; "tidak tersedia" bukan estimasi; tanpa isi buku referensi.

## Direction contract

Redesign 23 Okt 2026 (permintaan pemilik: lebih modern, gaya morphism, palet baru, responsif ponsel). Dipin: glassmorphism, gelap,
tetap bisa dilirik dalam 3 detik, grafik candlestick tetap besar dan utama. Undian concept-seed 6d51b20c → indeks 4; pemilik memilih
kartu undian di halaman keputusan (key 9ed99581). Dunia lama (arang hangat, kuningan, tanpa kartu) adalah anti-referensi.

WORLD: Ruang observasi akuarium laut dalam pada malam hari. Kaca di sini harfiah: tiap analis diamati lewat satu tangki kaca beku;
uang paper adalah cahaya biolumines di dalamnya.

THESIS: Empat tangki kaca sejajar memuat seluruh status analis (saldo, posisi, P/L hidup, order, keputusan terakhir) dalam sel
bergaris padat; aliran kejadian adalah panel kaca di sisi; grafik harga adalah jendela besar tepat di bawahnya.

OWN-WORLD: air laut dalam bergradasi (#0a2230 → #06141b → #040d12) dengan cahaya permukaan dari atas dan beberapa titik biolumines
buram yang diam; panel kaca beku (blur 18 px, saturate, tepi atas memantul cahaya 1 px, bayangan lembut ke bawah); tinta busa
#e6f4f1; satu cahaya fokus cyan #63e6ff (pilihan, fokus, crosshair); untung hijau fosfor #6be89a, rugi koral #ff7a6b, peringatan
kuning umpan anglerfish #f3c969; warna persona sebagai cahaya di puncak tangki masing-masing. Satu keluarga huruf: Plus Jakarta Sans
(desainer Jakarta), angka tabular. Raises: sel bergaris padat (japanese-high-density-web), order batal/kedaluwarsa dicap dan tetap
terlihat (jet-age ticket wallet), tangki analis pensiun pudar abu-abu (character goods catalog).

STORY: "Siapa pegang apa, berapa jauh dari target/hangus, apa yang baru terjadi" → "harga koin yang dipegang (grafik besar)" →
"pasar sekilas & kebiasaan analis" → "siapa unggul vs acaknya" → riwayat → konteks → catatan AI.

FIRST VIEWPORT (1440): header tipis di atas air (nama, jam WIB, titik kesehatan); bar lompat-bagian kaca berbentuk pil yang menempel.
Empat tangki analis + panel kejadian 360 px. Grafik candlestick dimulai tepat di bawah lipatan, tinggi 540 px.

FORM: single-page scroll; urutan bagian diubah (Pasar naik ke posisi 2, keputusan pemilik: urutan tidak dipin). Aturan wadah: bagian =
judul di atas air + kolom-kolom sebagai panel kaca; tidak ada kaca di dalam kaca. Interaksi tanda tangan: angka yang berubah saat polling
5 detik menyala biolumines (cahaya cyan memudar 700 ms ease-out); entri kejadian baru masuk dengan geser 200 ms. Latar tidak bergerak
(hemat GPU, laptop menyala seharian). Ponsel: satu kolom, tangki bertumpuk, grafik 380 px, tabel bergulir di dalam panelnya,
target sentuh ≥ 36 px.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Unresolved
Mode terang (belum diminta; dunia ini gelap); ekspor riwayat (belum diminta).
