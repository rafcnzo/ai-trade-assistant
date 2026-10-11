# crypto-analyst — konvensi proyek (Milestone 1: mesin paper trading)

Spesifikasi lengkap: `docs/rencana-asisten-crypto.md`. Panduan operasi: `docs/OPERASI.md`.
CLAUDE.md profil trader lengkap (spesifikasi §6) menyusul di milestone 2.

## Memori bersama lintas perangkat (wajib)
Proyek ini dikerjakan dari beberapa perangkat lewat GitHub. Satu-satunya memori yang ikut
berpindah adalah folder `docs/`, bukan memori lokal agent.
- **Saat memulai sesi:** baca `docs/STATUS.md` (keadaan sekarang, langkah berikutnya), lalu
  entri teratas `docs/CHANGELOG.md`. Jangan mengandalkan ingatan sesi lain.
- **Setiap perubahan** kode, skema, konfigurasi, keputusan desain, atau hasil verifikasi:
  tambahkan entri di `docs/CHANGELOG.md` (tanggal WIB, perangkat, apa, kenapa, file terdampak)
  dan perbarui `docs/STATUS.md`, **dalam commit yang sama** dengan perubahannya.
- Keputusan yang mengubah spesifikasi: tambahkan catatan versi di `docs/rencana-asisten-crypto.md`.
- Perubahan cara menjalankan/mengoperasikan: perbarui `docs/OPERASI.md`.
- Sebelum push: `git pull --rebase` dulu; jika `STATUS.md` konflik, gabungkan isinya, jangan pilih salah satu.
- Jangan menaruh data pribadi sensitif di `docs/` (saldo nyata, API key, screenshot akun).

## Bahasa dan gaya
- Dokumen, pesan log, dan output CLI dalam bahasa Indonesia. Identifier kode dalam bahasa Inggris.
- Semua nilai uang dalam USD/USDT. IDR hanya konversi tambahan dalam kurung.

## Menjalankan kode
- Selalu pakai interpreter venv: `.venv/Scripts/python.exe` (Python 3.10). Jangan `pip install` tanpa memperbarui `requirements.txt` (`pip freeze`).
- Konsol Windows wajib UTF-8: `PYTHONIOENCODING=utf-8` sudah diset di `.claude/settings.json` dan `run_collector.cmd`. Beberapa simbol futures non-latin (mis. `龙虾USDT`).
- Tes: `.venv/Scripts/python.exe -m unittest discover -s tests -v` harus hijau sebelum commit.

## Aturan keras
- **Tidak ada API key exchange**, termasuk key read-only. Hanya endpoint publik. Jangan pernah menambahkan, meminta, atau menyimpan key.
- Satu penulis per database:
  - `data/pasar.sqlite` ← hanya `scripts/collector.py`
  - `data/paper.sqlite` ← hanya `scripts/paper_engine.py` (dipanggil collector atau CLI order)
  - `data/budget.sqlite` ← hanya `scripts/budget_guard.py`
  Jangan menulis SQL ke DB ini dari tempat lain. Agent (milestone 3) hanya memakai API `place_order`/`cancel_order`.
- Hasil trade paper hanya ditulis mesin. Tidak ada koreksi manual pada `positions`/`fills`.
- Jaringan rumah memblokir DNS `binance.com` (Kominfo). `common.DohResolver` menanganinya di dalam proses. **Jangan mengubah DNS atau pengaturan sistem**, dan jangan menyimpan data dari halaman blokir.
- Data yang tidak tersedia ditulis "tidak tersedia" beserta alasannya. Jangan mengestimasi.

## Struktur
```
scripts/   common.py, collector.py, paper_engine.py, budget_guard.py, schema_*.sql
tests/     unittest, tanpa jaringan (FixtureMarket)
data/      sqlite (gitignored)        logs/   log UTF-8 (gitignored)
docs/      spesifikasi & operasi      jurnal/ laporan/ pasar/ referensi/  (milestone 2+)
```
