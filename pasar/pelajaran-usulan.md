# Usulan pelajaran (status uji; perlu persetujuan user)

| ID | Tanggal | Pola | Ringkasan | Bukti | Sampel | Status |
|---|---|---|---|---|---|---|
| U-001 | 2026-10-12 | wick-penolakan | [ATURAN R:R MINIMUM TIKET] Setup wick-penolakan/tiket apa pun hanya dipasang bila untung_bersih di TP >= 0,5x rugi hangus (margin + fee masuk), yaitu win rate minimum <= ~67%. Jika tidak terpenuhi pada leverage manapun di tabel_tiket -> SKIP. Catat R:R tiap kandidat di jurnal agar bisa dinilai. | 2026-10-11 K3 SOL SHORT 75x (wick+breakout gagal di resistance): untung rencana ~$0.15 vs hangus $0.99 (R:R 0.15) -> HANGUS -$0.992. 2026-10-12 K8 LUMIA SHORT 10x (wick+breakout gagal di resistance): R:R 0.32 -> TP +$0.319. K4 LUMIA LONG (R:R ~0.13) ditolak LIMIT_CROSSES. Net 2 tiket terisi: -$0.67; 1 hangus menghapus >3 TP. Sumber: mcp_paper_riwayat 11 & 12 Okt, jurnal agent. | 3 | uji |
