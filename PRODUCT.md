# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Satu pengguna: pemilik proyek, trader crypto perorangan yang sedang menguji apakah AI (Hermes Agent) bisa trading
futures lebih baik daripada acak. Dashboard dibuka di laptop sepanjang hari sebagai **layar pantau sambil bekerja**:
dilirik sekilas, bukan dibaca. Ia memahami istilah trading dasar (LONG/SHORT, TP/SL, leverage, drawdown) tetapi tidak
ingin membaca jargon mesin (kode event, nama tabel, JSON).

## Product Purpose
Memantau **empat "analis" AI** (persona arena: `tiket` price action, `fade` lawan kerumunan, `breakout` tembus + uji ulang,
`rentang` mean reversion) yang masing-masing melakukan paper trading dengan jatah $1 per hari, plus pembanding acak
(`acak`) dan akun `swing`. Pertanyaan yang harus terjawab dalam urutan ini:
1. **Apa yang sedang terjadi sekarang** — posisi terbuka dan order menunggu tiap analis, harga live, kejadian terakhir
   (fill, TP, SL, breakeven, hangus, likuidasi). Ini prioritas 3 detik pertama (keputusan pemilik, 13 Okt 2026).
2. Siapa yang unggul — papan peringkat persona vs bayangan acaknya, saldo bergulir hari ini, status aktif/pensiun.
3. Konteks — suasana pasar (panel psikologi), kesehatan sistem, biaya API.
Sukses = pemilik bisa menilai dalam sekali lirik apakah ada yang perlu diperiksa, dan percaya angkanya karena semua
ditulis mesin, bukan agent.

## Positioning
Bukan terminal trading dan bukan laporan: ini **papan pengamat** atas beberapa agen yang bersaing dengan uang paper yang
sama. Perbedaan dari dashboard exchange: tidak ada tombol beli/jual, tidak ada input, semua baca-saja; nilai utamanya
adalah perbandingan antar-persona dan terhadap acak, bukan satu akun.

## Operating Context
- Backend: `scripts/dashboard.py` (Starlette/uvicorn, `127.0.0.1:8586`, **baca-saja**, koneksi SQLite readonly singkat).
  Endpoint yang ada: `/api/ringkasan`, `/api/arena`, `/api/ohlcv`, `/api/riwayat`, `/api/kejadian`, `/api/psikologi`, dll.
  Frontend statis di `dashboard/` (index.html, app.js, style.css), Lightweight Charts v4 dari CDN unpkg, font Google.
- Data: `data/paper.sqlite` (akun, order, posisi, fill, event), `data/pasar.sqlite` (tick, ohlcv), `data/kandidat.sqlite`,
  `data/psikologi.sqlite`, `data/budget.sqlite`; catatan markdown di `pasar/harian/`, `jurnal/agent/`.
- Agent berjalan terpisah (Hermes, cron tiap 5 menit saat ada kandidat); notifikasi utama lewat Telegram. Dashboard
  melengkapi Telegram, bukan menggantikannya.
- Waktu selalu WIB. Uang selalu USD/USDT; IDR hanya konversi dalam kurung.
- Jaringan rumah memblokir DNS exchange; resolusi ditangani di proses collector. Dashboard tidak memanggil exchange.

## Capabilities and Constraints
- Hanya membaca. Tidak boleh ada endpoint atau kontrol yang menulis DB/berkas (aturan keras CLAUDE.md).
- Data yang tidak tersedia ditampilkan "tidak tersedia" beserta alasannya; **tidak pernah diestimasi**.
- Akun dinamis dari tabel `account` (`kind` tiket|acak|swing, `status` aktif|pensiun); persona bisa bertambah/pensiun.
- Aturan mesin yang perlu terlihat: saldo bergulir ($1 + hasil bersih hari ini, minimum $0,50 untuk tiket baru, satu tiket
  ≤ $1), EOD 23:50, tidak ada tiket baru setelah 22:30, breakeven P-18 (SL ke harga masuk setelah 80 % jalan ke TP),
  maksimal 2 order hidup per akun, pensiun otomatis mingguan (≥ 30 trade, ≥ 30 hari, kalah dari acak p < 0,2).
- Terminologi tetap: persona/analis, tiket (trade harian kecil), bayangan acak, hangus (SL), TP, breakeven, likuidasi,
  saldo bergulir, drawdown, juara sementara.
- Bahasa UI: Indonesia; identifier kode Inggris.
- Pemilik meminta (13 Okt 2026): **rich text yang mudah dibaca**; label dan keterangan dipindahkan ke **tooltip** supaya
  layar tidak penuh teks; warna sederhana, elegan, kontras tinggi. (Konstanta visual yang mengikat, dicatat tanpa diperluas.)
- Undecided: apakah dashboard perlu mode terang; apakah riwayat perlu ekspor (belum diminta).

## Brand Commitments
Nama proyek: `crypto-analyst`. Tidak ada logo atau identitas visual resmi. Suara: lugas, Indonesia sehari-hari, tanpa
hype; tidak pernah menyarankan beli/jual uang sungguhan.

## Evidence on Hand
- Data nyata paper trading sejak Okt 2026 di `data/*.sqlite` (gitignored): beberapa trade tiket termasuk satu likuidasi
  SOL dan beberapa TP; arena 4 persona baru berjalan sejak 12 Okt 2026, sehingga sampel per persona masih kecil.
- Catatan pasar harian dan jurnal agent (markdown) tersedia untuk dibaca; isi buku referensi **tidak boleh** tampil.
- Tidak ada testimoni, benchmark, atau klaim performa; jangan dibuat.

## Product Principles
1. Keadaan sekarang dulu, peringkat kedua, konteks ketiga.
2. Angka hanya dari mesin; sumber dan waktu pembaruan selalu terlihat.
3. Lebih sedikit teks di layar; penjelasan tinggal di tooltip dan tidak menghalangi lirikan.
4. Setiap persona diperlakukan sama; acak selalu tampil sebagai pembanding, bukan peserta.
5. Ketidaktersediaan data adalah informasi, bukan kesalahan tampilan.

## Accessibility & Inclusion
Dibaca lama di layar laptop (sering malam): kontras teks tinggi, ukuran teks dasar ≥ 14 px, warna naik/turun tidak jadi
satu-satunya pembeda (sertakan tanda/ikon). Tooltip harus bisa dibuka lewat keyboard (fokus), bukan hanya hover.
