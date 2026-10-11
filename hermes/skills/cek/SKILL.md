---
name: cek
description: Cek setup tiket untuk satu simbol dan arah, lalu putuskan pasang order paper atau SKIP. Pintasan skill tiket untuk perintah /cek <SIMBOL> <LONG|SHORT> [entry] [tp], mis. "/cek SOLUSDT LONG" atau "/cek BTC short 82500".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper, tiket]
    category: trading
---

# Skill: cek

Argumen: `<SIMBOL> <LONG|SHORT> [entry] [tp]`. Simbol tanpa akhiran USDT dilengkapi (`BTC` → `BTCUSDT`).
Jika arah tidak disebut, nilai keduanya dan pilih yang lebih masuk akal menurut level dan tren 15m, atau SKIP.

## Prosedur
Ikuti skill `tiket` langkah 1–9 untuk simbol ini (bukan dari pemindai; `kandidat_id` kosong).
Jika pemilik memberi `entry`/`tp`, pakai angka itu di `mcp_paper_tabel_tiket` dan `mcp_paper_pasang_order`, tetapi tetap uji aturannya;
jika melanggar aturan, katakan apa yang melanggar dan **tanyakan** sebelum memasang (pakai `clarify`).

## Format balasan (≤ 12 baris)
**<SIMBOL> <ARAH> — PASANG #id | SKIP**
- Fakta: mark, tren 15m/5m, level terdekat (sentuhan), jejak, funding
- Rencana: pemicu | batal jika | lev → liq (k×ATR5m) | TP → untung bersih, win rate minimum
- Terjebak jika benar / salah
- Risiko utama
Ini paper trading; untuk uang sungguhan keputusan ada di Anda.
