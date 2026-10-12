---
name: arena-papan
description: Papan peringkat arena persona trading (tiket, fade, breakout, rentang) vs pembanding acak. Dipakai saat pemilik ketik /arena atau bertanya "siapa yang menang", "persona mana yang terbaik", "status arena".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, arena, statistik]
    category: trading
---

# Skill: arena-papan

1. `mcp_paper_papan_arena`.
2. Balas ≤ 12 baris: juara sementara (atau "belum ada, butuh ≥ 30 trade"), lalu satu baris per persona:
   `nama (status) · n trade · expectancy · win rate · total · vs acak (selisih, p)` — angka `null`/"tidak tersedia" ditulis apa adanya.
3. Satu kalimat penutup: apa yang membedakan juara (jika ada) dan persona mana yang berisiko pensiun (≥ 30 trade, kalah dari acak).

## Jebakan
- Jangan menyimpulkan "strategi terbaik" dari < 30 trade; sebut jumlah sampel.
- Status pensiun hanya diputuskan skrip mingguan (`evaluasi.py --nilai-arena`) dan pemilik; saya tidak mengubahnya.
