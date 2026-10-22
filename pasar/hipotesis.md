# Hipotesis

_Dibuat agent lewat tool `tulis_hipotesis` (pasar/hipotesis.jsonl); dinilai skrip `uji_hipotesis.py` — file ini di-generate, jangan diedit._

| ID | Dibuat | Pola | Kondisi (terukur) | Prediksi | Batas | Status | Hasil | Baseline |
|---|---|---|---|---|---|---|---|---|
| H-0001 | 2026-10-12 | breakout-gagal | BTC 1h: BREAKOUT_GAGAL atas 83821 (00:00) & 83658 (01:00 WIB 12-10), wick atas 1.3xATR di 84147 (3 sentuhan), RSI14 68.8, close 83921.5 | BTCUSDT 1h menyentuh 83439 (bawah) | 2026-10-14 | benar | low 80985 ≤ target 83439 | 90% |
| H-0002 | 2026-10-13 | kapitulasi | 13 Okt 11:07 WIB: liq short OKX 100/100 serakah_ekstrem, OI 24j -1.3%, funding 0.0036% netral; BREAKOUT_GAGAL bawah 82067 & 81417 1h 08:00; close 1h 83299.9 | BTCUSDT 1h menyentuh 84386 (atas) | 2026-10-16 | salah | high 84134.2 tidak mencapai target 84386 | 68% |
| H-0003 | 2026-10-14 | breakout-gagal | BTC 1h BREAKOUT_GAGAL bawah 83177 (14 Okt 02:00 & 07:00 WIB), KOMPRESI 1.88xATR, close 83376.5, panel 0 ekstrem | BTCUSDT 1h menyentuh 83822 (atas) | 2026-10-16 | benar | high 84117.6 ≥ target 83822 | 82% |
| H-0004 | 2026-10-15 | penumpukan-leverage | 15 Okt 08:39 WIB: ETH 1h close 2417.93, RSI 30, tren turun; L/S akun ETH 2.86 serakah_ekstrem vs top 1.54 (snapshot 14-10 18:08); support 2408 6 sentuhan | ETHUSDT 1h menyentuh 2384 (bawah) | 2026-10-18 | benar | low 2313.39 ≤ target 2384 | 64% |
| H-0005 | 2026-10-15 | kompresi | BTC 1h KOMPRESI range 10 bar 1.65xATR (ATR 446) di atas support 81479 (5 sentuhan), tren turun, EMA20 82207 > close 81624.7, RSI 33 | BTCUSDT 1h bergerak ≥ 2.0×ATR ke bawah dari 81745.6 | 2026-10-17 | benar | low 79732.3 ≤ target 80853.4 | 60% |
| H-0006 | 2026-10-15 | penumpukan-leverage | BTC 1h 20:00 close 80164,5 vol 3,6x lalu mark pulih ~81124; OI +5,6% 24j saat harga -2,6%; funding -0,0005%; RSI1h 31,6 | BTCUSDT 1h menyentuh 81900 (atas) | 2026-10-17 | benar | high 82900.5 ≥ target 81900 | 68% |
| H-0007 | 2026-10-16 | breakout-gagal | BTC 1h BREAKOUT_GAGAL atas 82445 (19:00) & 81993 (20:00 WIB 16-10), VOL 2.16x candle turun, close 81990 < EMA20 82090, support 81538 7 sentuhan | BTCUSDT 1h menyentuh 81538 (bawah) | 2026-10-18 | benar | low 80751 ≤ target 81538 | 70% |
| H-0008 | 2026-10-16 | penumpukan-leverage | 16-10 21:07 WIB: L/S akun ETH 2.52 serakah_ekstrem vs top 1.61; BREAKOUT_GAGAL atas 2470 (19:00), close 2457.51, support 2423.75 4 sentuhan | ETHUSDT 1h menyentuh 2423 (bawah) | 2026-10-18 | benar | low 2355 ≤ target 2423 | 48% |
| H-0009 | 2026-10-20 | breakout-gagal | 20-10 07:00 WIB 1h low 81381.5 tembus support 81477 (7 sentuhan) lalu close 81699.3; RSI 41, tren sideways, panel 19-10 20:07 liq long takut_ekstrem | BTCUSDT 1h menyentuh 82202 (atas) | 2026-10-22 | benar | high 84875.2 ≥ target 82202 | 66% |
| H-0010 | 2026-10-20 | lonjakan-volume | harga 82983.8 (21:3x WIB) sudah tembus resistance 82268 (8 sentuhan) setelah 1h 20:00 VOL 2.75x; liq short 100/100 sampel OKX; funding +0.004% netral; target di atas swing high 83157.9 | BTCUSDT 1h menyentuh 83400 (atas) | 2026-10-22 | terbuka | — | — |
