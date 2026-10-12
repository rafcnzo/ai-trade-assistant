---
name: arena
description: Menilai kandidat pemindai untuk SEMUA persona arena (tiket = price action, fade = lawan kerumunan, breakout = tembus + uji ulang, rentang = mean reversion) dan memasang order paper di akun masing-masing. Dipakai oleh cron pemindai-tiket. Untuk permintaan pemilik "cek setup" pakai skill tiket/cek.
version: 1.0.0
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
5. Jurnal **per persona per kandidat**: `mcp_paper_tulis_jurnal(jenis="keputusan", judul="[<persona>] K<id> SIMBOL ARAH - order #n|SKIP", isi, symbol, kandidat_id, order_id, aturan_dilanggar)`.
   SKIP cukup satu kalimat alasan (syarat mana yang gagal).
6. Balasan Telegram ≤ 14 baris: satu baris per persona yang masuk (akun, simbol, arah, lev, entry, TP, liq) dan satu baris ringkas untuk
   persona yang SKIP ("fade: SKIP, tidak ada divergensi"). Tutup: "paper trading; keputusan uang sungguhan ada di Anda".

## Jebakan
- Jangan memakai akun yang `boleh_buka=false`/`pensiun`; mesin menolak (`BUDGET_TIKET`, `ACCOUNT_PENSIUN`) dan itu pelanggaran.
- Jangan memaksa persona masuk supaya "ada trade"; SKIP adalah hasil sah — arena mengukur persona yang disiplin, bukan yang rajin.
- Satu kandidat boleh dipakai beberapa persona dengan arah berbeda (mis. breakout LONG, fade SHORT) — itu sah, akunnya terpisah.
