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

THESIS: Meja analis: satu baris meja per analis dengan apa yang sedang ia pegang sekarang, ditulis sebagai kalimat
(bukan tabel KPI), dan kejadian mesin mengalir di sampingnya. Menolak susunan default "kartu angka besar + tab".

OWN-WORLD: arang hangat gelap sebagai meja, tinta gading, satu aksen kuningan untuk fokus/pilihan, mint = untung,
koral = rugi, hanya garis rambut 1px sebagai pemisah; satu keluarga huruf (Inter) dengan angka tabular; tanpa kartu di dalam kartu;
label kecil bergaris putus yang membuka tooltip.

STORY: "Siapa pegang apa, berapa jauh dari target/hangus, apa yang baru terjadi" → "siapa yang unggul vs acaknya" → "pasar
sedang bagaimana, mesin sehat, biaya".

FIRST VIEWPORT (1440): header tipis (nama, jam WIB, titik kesehatan ber-tooltip). Meja empat kolom analis, tiap kolom:
nama + gaya, pil status, batang saldo bergulir, posisi terbuka sebagai kalimat kaya + P/L hidup, order menunggu, keputusan
terakhir. Baris tipis pembanding acak & swing. Kolom kanan 360px: aliran kejadian terbaru (relatif waktu). Tidak ada aksi primer.

FORM: single-page scroll dengan lompat-bagian; posisi daftar: dipin oleh brief user (tanpa undian; seed key: none/pinned).
Interaksi tanda tangan: denyut kuningan (garis bawah 600 ms ease-out) pada angka yang berubah saat polling 5 detik, dan
entri kejadian baru masuk dengan geser 200 ms. Tidak ada motion lain.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Unresolved
Mode terang (belum diminta); ekspor riwayat (belum diminta).
