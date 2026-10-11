# STATUS — keadaan proyek sekarang

> Baca file ini dulu saat memulai sesi di perangkat mana pun. Perbarui setiap kali ada perubahan.
> Riwayat perubahan: `docs/CHANGELOG.md`. Spesifikasi: `docs/rencana-asisten-crypto.md`. Operasi: `docs/OPERASI.md`.

Diperbarui: 2026-10-11 11:50 WIB (perangkat: laptop Windows "laptop-l5i0361r")

## Milestone

| Milestone | Isi | Status |
|---|---|---|
| 1 | Mesin paper trading: `collector.py`, `paper_engine.py`, `budget_guard.py`, `common.py`, skema SQLite, 43 unit test | **Selesai**, berjalan live |
| 2 | Skrip asisten harian (`topvolume`, `tiket`, `snapshot`, `ohlcv`, `jejak_grafik`, `psikologi`, `derivatif`, `makro`, `unlock`, `posisi`, `stats_jurnal`), CLAUDE.md profil trader (§6), 4 slash command, memori pasar (§16), referensi buku (§15) | Belum mulai |
| 3 | `pemindai.py` (tanpa LLM) + `agent.py` (Haiku 5.5 saring, Opus 5.5 putuskan) di atas `place_order` + `budget_guard.call`, baseline acak, kriteria lulus §19.7 | Belum mulai |

## Yang sedang berjalan

- Collector + mesin paper berjalan dari sesi Claude Code di laptop (bukan Task Scheduler). Jika sesi ditutup, proses berhenti; data dan posisi aman di `data/*.sqlite` (tidak di-commit).
- Tiga order paper uji dibuat 11 Okt 11:42 WIB: #1 tiket BTC LONG 150x @ 82.915,7 (TP 83.372); #2 tiket ETH LONG 100x @ 2.431,1 (jauh, diharapkan `TIDAK_TERISI` 23:50); #3 swing ETH SHORT 10x @ 2.511,3 (TP 2.305,8 / SL 2.581,5).

## Verifikasi milestone 1

| # | Item | Hasil |
|---|---|---|
| 1 | Unit test T1–T19, B1–B3 | ✅ 43/43 hijau |
| 2 | Collector lewat DoH di Wi-Fi rumah | ✅ 20 simbol × 2.881 bar (48 jam) + mark bar, 19 s, weight 856 |
| 3 | Backfill 24 jam + pacing weight | ✅ (termasuk di #2) |
| 4 | Order manual: terisi / tidak terisi / swing / ditolak | ✅ 3 diterima, 3 ditolak dengan kode benar; hasil isi menunggu bar |
| 5 | Uji tidur laptop → GAP + replay | ⬜ belum (tes unit T15 sudah membuktikan replay == live) |
| 6 | `budget_guard.py harga` / `status` | ✅ |
| 7 | Soak 24 jam (ukuran DB, locking, retensi) | ⬜ sedang berjalan |
| 8 | Bandingkan harga likuidasi dengan kalkulator Binance | ⬜ user: BTC LONG 150x isolated entry 82.915,7 margin $0,5528 → mesin ≈ 82.693,7 |

## Keputusan yang berlaku

- Jaringan rumah memblokir DNS Binance → resolusi DoH di dalam skrip (`common.DohResolver`); **DNS Windows tidak diubah**.
- Budget tiket: `margin + fee masuk ≤ $1` per hari WIB (`tiket_fee_from_budget=True`).
- Order tiket kedaluwarsa dan posisi tiket ditutup paksa 23:50 WIB.
- Ambiguitas intrabar: pesimis (liq → SL → TP), ditandai `ambiguous=1` + `alt_outcome`.
- Budget API Anthropic: $10/hari saat laptop menyala, $190/bulan, $1/panggilan.
- Repo di GitHub (`rafcnzo/ai-trade-assistant`). `data/`, `logs/`, `jurnal/`, `laporan/`, `referensi/buku/` tidak di-commit.

## Langkah berikutnya (urutan usulan)

1. User: daftarkan Task Scheduler (`docs/OPERASI.md`), cek likuidasi vs aplikasi Binance.
2. Amati 2–3 hari: `paper_engine.py laporan`, `collector.py status`, ukuran `pasar.sqlite`.
3. Mulai milestone 2 dari `topvolume.py` dan `tiket.py` (dipakai setiap hari), lalu CLAUDE.md profil trader dan `/briefing`.

## Pertanyaan terbuka

- Belum ada. Jika menambah pertanyaan, tulis di sini beserta tanggalnya.
