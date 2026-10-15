---
name: swing
description: Rencana swing bertahap (P-20): entry tangga atau piramida, TP 50% / 25% / runner trailing ATR, breakeven setelah TP1. Dipakai saat pemilik ketik /swing <koin>, minta "rencana swing", atau saat skill cek menemukan setup 4H/1D yang sehat.
version: 1.0.0
metadata:
  hermes:
    tags: [trading, swing, bertahap]
    category: trading
---

# Skill: swing — rencana bertahap

Akun `swing`: margin **$10 total per rencana**, maksimal 2 rencana, R:R rencana ≥ 2,5 setelah fee, hanya saat pasar sehat.
Mesin menegakkan semuanya lewat `mcp_paper_pasang_rencana_swing`; saya mengusulkan level, mesin memutuskan sah/tidak.

## Prosedur
1. `mcp_paper_waktu_sekarang`; `mcp_paper_budget_tiket` → `swing.open + swing.pending < 2`, kalau tidak: berhenti, sebutkan rencana yang sedang jalan.
2. Pasar sehat (§17.5): `mcp_paper_ohlcv` 1d, 4h, 1h. Syarat: 1D dan 4H searah (EMA20 > EMA50 untuk LONG, sebaliknya SHORT), funding normal
   (`mcp_paper_harga`), ada ruang ≥ 1 R ke level 4H berikutnya. `mcp_paper_panel_psikologi` untuk tahu siapa yang terjebak.
   Salah satu gagal → SKIP, tulis alasannya.
3. Pilih mode:
   - **tangga** (pullback ke zona level 1h/4h): 2–3 leg, misalnya 50/30/20, leg pertama di tepi zona, jarak antar leg ≥ 0,5×ATR 4H,
     SL di luar zona di bawah leg terjauh + buffer. Semua leg = limit; tidak ada `market`.
   - **piramida** (tembus + uji ulang): 1 leg awal (100% dari rencana awal, margin ≤ $5 agar ada ruang add), lalu
     `mcp_paper_tambah_leg_swing` **hanya saat posisi sudah untung ≥ 1×ATR 15m di atas entry rata**: add ke-1 ≤ 60%, add ke-2 ≤ 40%
     dari leg pertama, SL baru naik ke bawah leg baru (Turtle: stop mengikuti unit terakhir). Maksimal 4 leg total.
4. Target: TP1 = level berikutnya (≥ 1 R dari entry rata), TP2 = level setelahnya; bawaan 50% / 25%, sisa 25% runner dengan
   `trail_atr=2` (2×ATR 15m, dihitung mesin). Tanpa runner → isi TP sampai 100% (boleh 60/40).
5. Hitung sendiri sebelum memasang: R:R rencana = (0,5·(TP1−entry) + 0,25·(TP2−entry) + 0,25·(TP2−entry)) / (entry−SL) ≥ 2,5.
   Kalau tidak sampai: perlebar TP ke level berikutnya atau SKIP; jangan menyempitkan SL ke dalam zona.
6. `mcp_paper_pasang_rencana_swing(symbol, sisi, leverage, legs, tps, sl, trail_atr=2, mode, plan_id, pola, catatan)`.
   Leverage 5–20× (liq harus di luar SL dengan buffer); `MIN_NOTIONAL`/`MIN_QTY` ditolak → kurangi jumlah leg atau naikkan leverage sedikit, bukan memaksa.
7. `mcp_paper_tulis_jurnal` (judul `[swing] <koin> <sisi> - rencana #<id>` atau `- SKIP`): tesis, siapa yang terjebak jika benar/salah,
   level invalidasi, mode, leg, TP, R:R.
8. Balas ≤ 12 baris: mode, leg (harga·%), TP (harga·%), runner & trailing, SL, margin, R:R, dan kalimat invalidasi.

## Setelah terpasang (apa yang mesin lakukan sendiri)
- Leg terisi → posisi digabung (entry rata). TP1 terisi → SL sisa ke breakeven, leg yang belum terisi **dibatalkan** (tidak menambah
  posisi yang sedang dikurangi). Semua TP tetap terisi → runner di-trail dari harga terbaik bar sebelumnya. Hasil keluar: `TP`, `TRAIL`,
  `STOP`, `HANGUS`.
- `/posisi` menampilkan `sisa x% · TP1 ✓`; `/batal rencana <id>` = `mcp_paper_batal_order(plan_group=<id>)` membatalkan leg yang belum terisi;
  `mcp_paper_tutup_posisi` menutup sisa posisi.

## Jebakan
- Jangan menambah posisi yang rugi (averaging down, bab 3 buku psikologi): mesin menolak `ADD_NOT_IN_PROFIT`, jangan mencoba memutar lewat rencana baru.
- Jangan memasang rencana hanya karena tiket sepi; swing butuh 1D/4H searah.
- Jangan mengubah TP/SL dengan menutup dan membuka ulang; sebutkan ke pemilik kalau rencana perlu diganti.
- Referensi: LuxAlgo "Scaling In/Out" (parsial = % dari qty awal, add hanya by rule), aturan Turtle (add tiap ½N, maks 4 unit, stop ikut
  unit terakhir), "half off at +1R, stop ke breakeven". Buku Aziz & Baehr bab 3: averaging down = bahaya nomor satu.
