---
name: tiket
description: Prosedur menilai kandidat tiket $1 (Binance USDT-M Futures, paper) dan memasang order paper lewat tool mcp_paper_*. Dipakai saat pemindai menemukan kandidat, atau saat pemilik minta "cek setup", "cek tiket", "pasang tiket".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper, tiket, price-action]
    category: trading
---

# Skill: tiket

## Kapan dipakai
- Cron `pemindai-tiket` membangunkan saya dengan ringkasan kandidat.
- Pemilik bertanya tentang setup tiket untuk simbol tertentu.

## Prosedur (urutan wajib)
1. `mcp_paper_waktu_sekarang`. Berhenti jika `status_data` = BASI (katakan datanya basi) atau `menit_ke_eod` < 80
   (tidak ada tiket baru setelah 22:30 WIB).
2. `mcp_paper_budget_tiket`. Berhenti jika `tiket.remaining` < 0,10 (katakan budget hari ini habis).
3. Ambil kandidat: `mcp_paper_kandidat_terbaru(limit=5)` (atau simbol yang disebut pemilik). Dari cron: nilai HANYA
   kandidat yang ID-nya (`K<id>`) disebut di ringkasan pemindai. Lewati simbol yang sudah punya order/posisi
   (`mcp_paper_order_menunggu`, `mcp_paper_posisi`). Maksimal 2 order tiket hidup pada satu waktu.
4. Per kandidat, kumpulkan FAKTA:
   - `mcp_paper_harga` (mark, funding, kesegaran),
   - `mcp_paper_ohlcv` tf 15m lalu 5m: tren, level terdekat (`level_atas`/`level_bawah`, sentuhan), ATR, jejak
     (WICK, VOL, BREAKOUT_GAGAL, IMPULS, KOMPRESI),
   - `mcp_paper_tabel_tiket` untuk sisi yang dipertimbangkan, `entry` = level yang dituju.
5. Uji aturan (semua harus lolos, kalau tidak → SKIP dengan alasan):
   - entry adalah limit di/dekat level dengan ≥ 2 sentuhan, searah tren 15m atau pada penolakan yang jelas (WICK/BREAKOUT_GAGAL);
   - ada leverage di tabel dengan `x_atr.5m` ≥ 2,0 dan `fee_pct_tiket` ≤ 6;
   - target realistis: TP ≤ 1,5×ATR 15m dari entry dan `untung_bersih` ≥ 3× `fee_bolak_balik`;
   - tidak ada flag SUDAH_LARI atau FUNDING_EKSTREM yang melawan arah;
   - level invalidasi bisa disebut (biasanya likuidasi = stop untuk tiket).
6. Tulis rencana bersyarat (format):
   `Pemicu: ... | Batal jika: ... | Leverage: Nx → liq ≈ ... (k×ATR5m) | TP: ... (+p%) → untung bersih ≈ $..., win rate minimum ≈ ..% | Terjebak jika benar: ... | Terjebak jika salah: ...`
7. `mcp_paper_pasang_order(akun="tiket", symbol, sisi, qty=<dari tabel>, leverage, harga=<level>, tp, plan_id=<field plan_id kandidat, mis. "K17">, pola=<pola>, catatan=<rencana>)`.
   Jangan mengarang ID; tanpa kandidat pemindai (permintaan pemilik) pakai `plan_id="MANUAL"`.
   Kode tolak: `LIMIT_CROSSES` → harga sudah lewat level, nilai ulang sekali atau SKIP (jangan `market=true`);
   `BUDGET_TIKET`/`TIKET_EOD` → SKIP; lainnya → laporkan apa adanya.
8. **Selalu** `mcp_paper_tulis_jurnal(jenis="keputusan", judul, isi=<rencana + alasan>, symbol, kandidat_id, order_id)`, termasuk saat SKIP.
9. Balasan Telegram ≤ 12 baris: keputusan per kandidat, id order, alasan utama, risiko, satu kalimat
   "ini paper trading; untuk uang sungguhan keputusan ada di Anda".

## Jebakan
- Jangan menaikkan leverage demi muat budget; kalau `tabel_tiket` bilang "tidak bisa", jawabannya SKIP.
- Jangan memakai `market=true` kecuali pemilik secara eksplisit meminta.
- Data `BASI` bukan alasan menebak; katakan dan berhenti.
- Simbol non-latin (mis. `龙虾USDT`) sah; pakai persis seperti dikembalikan tool.

## Verifikasi
Setelah memasang: `mcp_paper_order_menunggu` menunjukkan order dengan `plan_id` yang sama; jurnal hari ini
(`mcp_paper_baca_memori("jurnal")`) memuat keputusannya.
