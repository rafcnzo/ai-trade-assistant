---
name: psikologi
description: Panel psikologi pasar (Fear & Greed, funding, OI, L/S ratio, taker, likuidasi, premium Coinbase/IDR, stablecoin) untuk BTC/ETH dengan zona takut/serakah dan divergensi. Dipakai saat pemilik ketik /psikologi atau bertanya "sentimen", "psikologi pasar", "siapa yang terjebak".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, psikologi, sentimen]
    category: trading
---

# Skill: psikologi

## Prosedur
1. `mcp_paper_panel_psikologi("BTCUSDT")`; jika pemilik menyebut ETH, panggil juga untuk `ETHUSDT`.
2. Jika `status` = `tidak tersedia` atau `BASI`: katakan itu beserta alasannya (cron `psikologi` tiap jam), jangan menebak angka.
3. Balasan Telegram ≤ 12 baris:
   - baris 1: `umur` data, `takut_ekstrem` vs `serakah_ekstrem` (jumlah indikator), `mode_zona`;
   - 3–5 indikator paling menonjol dengan nilai dan zonanya (funding, OI 24j + harga 24j, L/S akun vs top trader, taker, FNG, premium);
   - `divergensi` apa adanya (ini yang paling penting), atau "tidak ada divergensi";
   - satu kalimat "siapa yang dominan, siapa yang terjebak jika harga berbalik";
   - satu kalimat penutup: ini konteks, bukan sinyal; keputusan uang sungguhan ada di pemilik.

## Jebakan
- **Tidak ada skor gabungan.** Jangan menjumlahkan indikator menjadi satu angka "sentimen".
- Nilai `null`/"tidak tersedia" disebut apa adanya dengan sumbernya; jangan mengisi dari ingatan.
- Likuidasi OKX hanya ±100 order terakhir: sebut "sampel terbatas".
- Premium IDR memakai USDT/IDR Indodax, bukan kurs resmi: pembanding kasar.
