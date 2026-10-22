# Penilaian SKIP

_Ditulis skrip `uji_hipotesis.py` (modul `kontrafaktual.py`). Setiap kandidat pemindai dinilai dengan order bayangan mekanis (limit di level, leverage layak terendah, TP 1,5×ATR15m, breakeven P-18, tutup 23:50). SKIP **benar** = bayangan rugi, **salah** = bayangan untung (peluang terlewat), **netral** = tidak terisi. Jangan diedit manual._

Jendela 30 hari: 200 kandidat dinilai — HANGUS 92, STOP_BE 10, TIDAK_TERISI 7, TP 86, ambigu 5.
Baseline (akurasi bila SKIP acak): 54%.

## Per analis

| Analis | SKIP | Benar | Salah | Netral | Akurasi |
|---|---|---|---|---|---|
| breakout | 148 | 80 | 61 | 7 | 57% |
| fade | 176 | 95 | 74 | 7 | 56% |
| rentang | 164 | 84 | 73 | 7 | 54% |
| tiket | 129 | 70 | 54 | 5 | 56% |

## Per alasan (semua analis)

| Alasan | n | Akurasi | Arti |
|---|---|---|---|
| RR_P19 | 152 | 58% | untung di TP < 0,5× risiko hangus (P-19) |
| NO_VOL_TEMBUS | 138 | 57% | tidak ada VOL / tidak tembus (breakout) |
| PANEL_FADE | 129 | 57% | panel psikologi tidak ekstrem/tanpa divergensi (fade) |
| NO_SIDEWAYS | 82 | 52% | tidak sideways / tanpa kompresi (rentang) |
| BASI | 40 | 55% | data atau panel basi |
| LIMIT_CROSSES | 15 | 40% | limit memotong mark |
| TREN_15M | 10 | 60% | melawan tren 15m / tidak searah |
| BUDGET | 9 | 44% | saldo/jatah tidak cukup |
| LAIN | 7 | 14% | lainnya |
| SUDAH_LARI | 7 | 100% | harga sudah lari / mengejar |
| LIQ_ATR5 | 1 | 100% | jarak likuidasi < 2×ATR 5m |
| SENTUHAN | 1 | 0% | level kurang sentuhan / penolakan belum jelas |

## Peluang terbesar yang terlewat (7 hari)

| Kandidat | Hari | Simbol | Arah | Hasil bayangan | Net | Di-SKIP oleh |
|---|---|---|---|---|---|---|
| K155 | 2026-10-19 | ARIAUSDT | SHORT | TP | +0.6991 | breakout, fade, rentang, tiket |
| K143 | 2026-10-19 | SOLUSDT | LONG | TP | +0.5838 | breakout, fade, rentang |
| K141 | 2026-10-19 | XRPUSDT | LONG | TP | +0.5824 | breakout, fade, rentang |
| K110 | 2026-10-16 | 1000PEPEUSDT | LONG | TP | +0.5703 | breakout, fade, rentang |
| K198 | 2026-10-21 | QUSDT | LONG | TP | +0.5554 | breakout, fade, rentang, tiket |
