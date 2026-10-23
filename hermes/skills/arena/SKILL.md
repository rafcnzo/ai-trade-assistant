---
name: arena
description: Menilai kandidat pemindai untuk SEMUA persona arena (tiket = price action, fade = lawan kerumunan, breakout = tembus + uji ulang, rentang = mean reversion) dan memasang order paper di akun masing-masing. Dipakai oleh cron pemindai-tiket. Untuk permintaan pemilik "cek setup" pakai skill tiket/cek.
version: 1.2.0
metadata:
  hermes:
    tags: [trading, paper, arena, persona]
    category: trading
---

# Skill: arena

Satu wake pemindai = satu sesi untuk semua persona. Fakta dikumpulkan **sekali**, lalu tiap persona memutuskan dengan aturannya sendiri.
Semua persona tunduk pada playbook (`mcp_paper_baca_memori("playbook")`) dan mesin (saldo bergulir $1/hari per akun, EOD, P-18).

## Prosedur
1. `mcp_paper_waktu_sekarang` (BASI → berhenti). `mcp_paper_budget_tiket` → field `persona`: hanya akun dengan `boleh_buka=true`
   dan `status=aktif` yang boleh dipasangi order. Pesan pemindai juga memuat baris **"Akun aktif: ..."** — ikuti itu.
2. `mcp_paper_kandidat_terbaru(limit=5)`; nilai hanya kandidat yang ID-nya disebut pemindai. Lewati simbol yang sudah punya order/posisi
   di akun yang sama (`mcp_paper_order_menunggu(akun)`, `mcp_paper_posisi(akun)`).
3. FAKTA per kandidat (sekali, dipakai semua persona): `mcp_paper_harga`, `mcp_paper_ohlcv` 15m lalu 5m (tren, level, ATR, jejak),
   `mcp_paper_panel_psikologi` untuk simbol itu (BTCUSDT/ETHUSDT) atau pasar luas, `mcp_paper_tabel_tiket` per sisi (entry = level).
4. **Per persona aktif**, uji syarat masuknya; lolos → `mcp_paper_pasang_order(akun=<persona>, ..., plan_id=K<id>, pola=<persona>:<pola>)`,
   tidak lolos → SKIP. Maksimal **1 order per persona per wake**; maksimal 2 order hidup per akun.

   | Persona | Masuk hanya bila | Arah & target |
   |---|---|---|
   | `tiket` | aturan skill tiket langkah 5 (level ≥ 2 sentuhan, searah tren 15m atau penolakan jelas, liq ≥ 2×ATR 5m, TP ≤ 1,5×ATR 15m & untung ≥ 3× fee, tidak SUDAH_LARI/FUNDING_EKSTREM melawan) | sesuai arah dugaan pemindai |
   | `fade` | panel psikologi: ≥ 2 indikator di zona ekstrem **dan** ada `divergensi`; kandidat berada di level resistance (bila serakah) / support (bila takut) | **melawan kerumunan**: serakah → SHORT di resistance, takut → LONG di support; TP ≤ 1×ATR 15m |
   | `breakout` | flag `VOL` ada **dan** close 5m terakhir sudah di luar level (tembus); entry = limit di level (uji ulang), bukan mengejar | searah tembus; TP = tinggi pola/level berikutnya, ≤ 1,5×ATR 15m |
   | `rentang` | tren 15m `sideways` **dan** ada `KOMPRESI` atau level adalah tepi range (≥ 3 sentuhan) dengan sisi lain range jelas | melawan gerakan ke tepi: di tepi atas SHORT, tepi bawah LONG; TP = tengah range (≤ 1×ATR 15m) |

   Semua persona: leverage dari `tabel_tiket` dengan `x_atr.5m ≥ 2`; `LIMIT_CROSSES` → SKIP (jangan market).
   **Timbang dulu, lalu putuskan.** Per persona tulis `poin_skip` (semua alasan untuk TIDAK masuk) dan `poin_open` (semua alasan
   untuk masuk): 1–5 poin per sisi, satu fakta per poin, pendek (≤ 1 kalimat, sebut angkanya), sisi yang kosong boleh `[]`.
   Aturan keras (P-19 R:R, BASI, saldo/BUDGET, EOD, `LIMIT_CROSSES`, liq < 2×ATR 5m, playbook aktif) ditulis di `poin_skip` dengan
   awalan `VETO: ` dan selalu berarti SKIP. Keputusan = hitungan: masuk **hanya** bila poin_open > poin_skip dan tidak ada VETO;
   seri = SKIP. Jangan memecah satu alasan menjadi beberapa poin atau menambah poin supaya hitungan berpihak; poin dibaca pemilik
   dan dinilai skrip.
5. Jurnal **per persona per kandidat**: `mcp_paper_tulis_jurnal(jenis="keputusan", judul="[<persona>] K<id> SIMBOL ARAH - order #n|SKIP", isi, symbol, kandidat_id, order_id, aturan_dilanggar, alasan_skip, poin_skip, poin_open)`.
   `poin_skip`/`poin_open` wajib (tool menolak keputusan kandidat tanpa poin); `isi` cukup satu kalimat ringkasan atau rencana bersyarat.
   Hasil memuat `timbangan`; bila ada `peringatan` "tidak sesuai hitungan", keputusan tetap tercatat dan ditandai untuk evaluasi.
   SKIP juga mengisi `alasan_skip` = satu kategori syarat yang paling menentukan:
   `RR_P19` · `TP_ATR15` · `TREN_15M` · `SENTUHAN` · `LIQ_ATR5` · `SUDAH_LARI` · `FUNDING` · `BASI` · `LIMIT_CROSSES` · `BUDGET` · `EOD` · `DUPLIKAT` ·
   `PANEL_FADE` (fade) · `NO_VOL_TEMBUS` (breakout) · `NO_SIDEWAYS` (rentang) · `PLAYBOOK` · `LAIN`.
   Setiap SKIP dinilai skrip esok hari dengan order bayangan mekanis; alasan yang terbukti menyaring atau sering melewatkan peluang
   muncul di `pasar/pelajaran.md` bagian "Dari keputusan SKIP" — jangan mengubah keputusan supaya angka itu terlihat bagus.
6. **Balasan Telegram = format baku, selalu sama** (dirender sebagai pesan kaya di Telegram dan identik dengan dashboard):
   - Untuk setiap kandidat yang dinilai, salin **persis** field `ringkasan_markdown` dari hasil `tulis_jurnal` kandidat itu yang
     `n_persona`-nya terbesar (biasanya panggilan terakhir untuk kandidat itu). Isinya: judul, satu baris fakta, tabel
     `Persona | Hasil | Timbangan` ("skip 3 · open 2"), lalu poin "Alasan SKIP"/"Alasan OPEN" tiap persona di bawah tabel.
     Salin semuanya, termasuk poin; jangan mengubah tabel menjadi daftar, jangan menambah/menghapus kolom, jangan menulis ulang angkanya.
   - Beberapa kandidat → tabel-tabel itu berurutan, dipisah satu baris kosong.
   - Setelah semua tabel boleh **satu** baris `**Catatan:** …` (≤ 1 kalimat) hanya bila ada hal penting yang tidak ada di tabel.
   - Baris terakhir selalu: `Paper trading; keputusan uang sungguhan ada di Anda.`
   - Bila `ringkasan_markdown` tidak ada (tool gagal), tulis sendiri tabel dengan kolom yang sama — tetap tabel, bukan daftar.
   - Tidak ada kandidat / data BASI: satu baris saja, lalu berhenti.

## Jebakan
- Jangan memakai akun yang `boleh_buka=false`/`pensiun`; mesin menolak (`BUDGET_TIKET`, `ACCOUNT_PENSIUN`) dan itu pelanggaran.
- Jangan memaksa persona masuk supaya "ada trade"; SKIP adalah hasil sah — arena mengukur persona yang disiplin, bukan yang rajin.
- Poin adalah fakta yang bisa dicek (angka, level, indikator), bukan perasaan ("kelihatannya kuat"). Poin yang sama untuk
  semua persona boleh, tetapi tiap persona menimbang dengan syarat masuknya sendiri.
- Satu kandidat boleh dipakai beberapa persona dengan arah berbeda (mis. breakout LONG, fade SHORT) — itu sah, akunnya terpisah.
- Jangan memformat ulang balasan sesuka hati (daftar berpoin, paragraf "Interpretasi"): tanpa tabel, Telegram jatuh ke format biasa dan
  pemilik melihat pesan yang berganti-ganti bentuk. Tabel baku dari `tulis_jurnal` adalah satu-satunya format laporan wake.
