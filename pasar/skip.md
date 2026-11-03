# Penilaian SKIP

_Ditulis skrip `uji_hipotesis.py` (modul `kontrafaktual.py`). Setiap kandidat pemindai dinilai dengan order bayangan mekanis (limit di level, leverage layak terendah, TP 1,5×ATR15m, breakeven P-18, tutup 23:50). SKIP **benar** = bayangan rugi, **salah** = bayangan untung (peluang terlewat), **netral** = tidak terisi. Jangan diedit manual._

Jendela 30 hari: 307 kandidat dinilai — HANGUS 143, STOP_BE 15, TIDAK_TERISI 9, TP 132, ambigu 8.
Baseline (akurasi bila SKIP acak): 54%.

## Per analis

| Analis | SKIP | Benar | Salah | Netral | Akurasi |
|---|---|---|---|---|---|
| breakout | 252 | 136 | 107 | 9 | 56% |
| fade | 280 | 151 | 120 | 9 | 56% |
| rentang | 266 | 139 | 118 | 9 | 54% |
| tiket | 201 | 110 | 86 | 5 | 56% |

## Per alasan (semua analis)

| Alasan | n | Akurasi | Arti |
|---|---|---|---|
| RR_P19 | 268 | 57% | untung di TP < 0,5× risiko hangus (P-19) |
| NO_VOL_TEMBUS | 236 | 56% | tidak ada VOL / tidak tembus (breakout) |
| PANEL_FADE | 227 | 56% | panel psikologi tidak ekstrem/tanpa divergensi (fade) |
| NO_SIDEWAYS | 121 | 53% | tidak sideways / tanpa kompresi (rentang) |
| BASI | 43 | 56% | data atau panel basi |
| LIMIT_CROSSES | 20 | 45% | limit memotong mark |
| TREN_15M | 14 | 64% | melawan tren 15m / tidak searah |
| LAIN | 13 | 38% | lainnya |
| SUDAH_LARI | 10 | 90% | harga sudah lari / mengejar |
| BUDGET | 9 | 44% | saldo/jatah tidak cukup |
| SENTUHAN | 5 | 20% | level kurang sentuhan / penolakan belum jelas |
| LIQ_ATR5 | 1 | 100% | jarak likuidasi < 2×ATR 5m |

## Peluang terbesar yang terlewat (7 hari)

| Kandidat | Hari | Simbol | Arah | Hasil bayangan | Net | Di-SKIP oleh |
|---|---|---|---|---|---|---|
| K291 | 2026-11-02 | APRUSDT | SHORT | TP | +0.7840 | breakout, fade, rentang |
| K298 | 2026-11-02 | UNIUSDT | LONG | TP | +0.6510 | breakout, fade, rentang, tiket |
| K277 | 2026-10-29 | XRPUSDT | SHORT | TP | +0.5483 | breakout, fade, rentang |
| K273 | 2026-10-29 | DOGEUSDT | LONG | TP | +0.4929 | breakout, fade, rentang |
| K248 | 2026-10-28 | XRPUSDT | LONG | TP | +0.4913 | breakout, fade, rentang, tiket |
