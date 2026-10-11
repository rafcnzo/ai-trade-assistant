---
name: budget
description: Sisa budget tiket hari ini, status akun swing, dan biaya API hari ini vs cap. Dipakai saat pemilik mengetik /budget atau bertanya "budget", "sisa tiket", "biaya".
version: 1.0.0
metadata:
  hermes:
    tags: [trading, paper, budget]
    category: trading
---

# Skill: budget

## Prosedur
1. `mcp_paper_budget_tiket` dan `mcp_paper_biaya_api`.
2. Jawab dalam ≤ 8 baris:

**Tiket hari ini**: sisa **$x** dari $1 (terpakai $a, tertahan order $b)
**Swing**: n posisi terbuka, m order menunggu (maks 2)
**Biaya API**: hari ini $c / $10, bulan ini $d / $190; blokir: -/jam; kill switch: ya/tidak

Jika `biaya_api` tidak tersedia, tulis "biaya API: tidak tersedia (proxy?)".
