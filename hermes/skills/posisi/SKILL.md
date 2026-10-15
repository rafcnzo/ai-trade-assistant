---
name: posisi
description: Ringkasan cepat posisi paper terbuka dan order yang menunggu, dengan unrealized dan jarak likuidasi. Dipakai saat pemilik mengetik /posisi atau bertanya "posisi", "order saya".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper, ringkasan]
    category: trading
---

# Skill: posisi

## Prosedur
1. `mcp_paper_waktu_sekarang` (sebut jam dan status data dalam satu baris).
2. `mcp_paper_posisi` dan `mcp_paper_order_menunggu`.
3. Jawab ringkas, format Telegram:

**Posisi terbuka (n)**
- `#id akun PAIR SISI lev×` entry → mark, **unrealized ±$x**, liq jarak y%, TP/SL
- posisi rencana swing (`plan_group` terisi): tambahkan `sisa x% · TP1 ✓ · n leg · SL BE/trailing` dari `persen_sisa`, `tp_list`, `legs_n`, `trail_on`
**Order menunggu (n)**
- `#id akun PAIR SISI` limit harga, lev×, margin $x, TP, kedaluwarsa HH:MM

Jika kosong tulis "tidak ada". Jangan menambah analisis kecuali diminta. Maksimal 12 baris.
