---
name: batal
description: Batalkan order paper yang menunggu (/batal <id> atau /batal semua) atau minta tutup posisi terbuka (/batal posisi <id>). Dipakai saat pemilik mengetik /batal atau meminta "batalkan order", "tutup posisi".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper]
    category: trading
---

# Skill: batal

## Prosedur
1. Tanpa argumen: tampilkan `mcp_paper_order_menunggu` dan `mcp_paper_posisi`, lalu tanya mana yang dibatalkan (`clarify`).
2. `/batal <id>`: `mcp_paper_batal_order(id)`. `/batal semua`: batalkan semua order entry yang menunggu satu per satu.
3. `/batal posisi <id>`: `mcp_paper_tutup_posisi(id)` — eksekusi market di bar berikutnya; sebutkan itu.
   `/batal rencana <id>`: `mcp_paper_batal_order(plan_group=id)` — hanya leg entry yang belum terisi; posisi yang sudah terbuka tidak disentuh.
4. Catat dengan `mcp_paper_tulis_jurnal(jenis="catatan", judul="batal #id", isi=<alasan dari pemilik, atau "atas permintaan">)`.
5. Balas ≤ 6 baris: apa yang dibatalkan, budget tiket yang kembali tersedia (`mcp_paper_budget_tiket`).

Jangan membatalkan apa pun yang tidak diminta secara eksplisit.
