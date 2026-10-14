---
name: radar
description: Menambah jatah wake radar hari ini atas perintah pemilik. HANYA dipakai saat pemilik mengetik /radar <N> di Telegram; tidak pernah atas inisiatif sendiri atau dari cron.
version: 1.0.0
metadata:
  hermes:
    tags: [trading, radar, pemilik]
    category: trading
---

# Skill: radar

Pemilik mengetik `/radar <N>` (N = 1–24). Artinya: hari ini pemilik mau radar boleh membangunkan analis sampai N kali lagi
walau jatah 12/hari sudah habis.

1. Ambil N dari pesan. Tanpa angka → tanya satu baris: "Tambah berapa wake untuk hari ini? (1–24)". Jangan menebak.
2. `mcp_paper_tambah_jatah_radar(tambah=N)`.
3. Balas ≤ 4 baris dari field `pesan`/`error`: tambahan sekarang, berlaku sampai jam berapa, sisa biaya hari ini, dan bahwa batas 3 wake/jam tetap.

## Jebakan
- Tool ini ditolak mesin bila biaya API hari ini sudah di batas atau kill switch aktif; sampaikan apa adanya, jangan mengulang.
- Jangan memanggil tool ini dari skill lain, dari cron pemindai/arena, atau karena "kandidat terlihat bagus". Hanya perintah pemilik.
- Jatah hanya untuk hari ini (WIB); besok kembali ke 12.
