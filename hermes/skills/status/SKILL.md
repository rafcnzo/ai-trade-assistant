---
name: status
description: Kesehatan sistem paper trading: umur data collector, proxy budget, pemindai, kill switch, jam dan sisa waktu ke tutup tiket. Dipakai saat pemilik mengetik /status atau bertanya "sistem jalan?", "data segar?".
version: 1.0.0
metadata:
  hermes:
    tags: [sistem, paper]
    category: trading
---

# Skill: status

## Prosedur
1. `mcp_paper_waktu_sekarang` dan `mcp_paper_status_sistem`.
2. Jawab ≤ 8 baris:

**Status <jam WIB>**
- Collector: tick x detik lalu — OK / **BASI**
- Proxy budget: ok / tidak tersedia; hari ini $a / $10
- Pemindai: run terakhir HH:MM, bangun n× hari ini / belum jalan
- Kill switch: ya / tidak
- Tutup tiket 23:50 WIB (m menit lagi)

Jika ada yang BASI/tidak tersedia, tambahkan satu baris apa yang perlu dicek (`collector.py status`, `/healthz`).
