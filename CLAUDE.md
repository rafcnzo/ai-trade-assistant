# crypto-analyst — konvensi proyek

Spesifikasi lengkap: `docs/rencana-asisten-crypto.md`. Panduan operasi: `docs/OPERASI.md`.
**Otak asisten adalah Hermes Agent** (native Windows, `%LOCALAPPDATA%\hermes`), bukan Claude Code. Claude Code hanya
membangun dan menguji proyek ini. Persona dan aturan trader ada di `hermes/SOUL.md` + `hermes/skills/*`; semua tool
untuk agent dibuat sebagai tool MCP di `scripts/mcp_server.py`, bukan slash command Claude Code.

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
- Satu penulis per database/berkas:
  - `data/pasar.sqlite` ← hanya `scripts/collector.py`
  - `data/paper.sqlite` ← hanya `scripts/paper_engine.py` (dipanggil collector, CLI, atau `mcp_server.py`); akun `acak`
    (bayangan acak per order tiket) hanya dibuat mesin, tidak pernah lewat CLI/MCP
  - `data/budget.sqlite` ← hanya `scripts/budget_guard.py` (dipanggil `budget_proxy.py`)
  - `data/kandidat.sqlite` ← hanya `scripts/pemindai.py`
  - `data/notif.json` ← hanya `scripts/notifikasi.py` (kursor kejadian yang sudah dikirim ke Telegram)
  - `data/psikologi.sqlite` ← hanya `scripts/psikologi.py` (panel psikologi pasar, cron tiap jam)
  - `jurnal/agent/`, `pasar/harian/`, `pasar/hipotesis.jsonl` (append), `pasar/pelajaran-usulan.md` ← hanya `scripts/mcp_server.py`
  - `pasar/hipotesis-hasil.jsonl`, `pasar/hipotesis.md`, `pasar/pelajaran.jsonl`, `pasar/pelajaran.md` ← hanya `scripts/uji_hipotesis.py`
    (skrip yang menilai; agent dan manusia tidak mengedit view ini — pemilik memutuskan usulan di `pelajaran-usulan.md`)
  Jangan menulis SQL ke DB ini dari tempat lain. Agent hanya memakai tool MCP (`place_order`/`cancel_order`/…).
- Agent (Hermes) tidak diberi toolset terminal/file/browser; integritas mesin bergantung pada itu. Jangan melonggarkan
  `platform_toolsets`/`disabled_toolsets` di `hermes/config.snippet.yaml` tanpa alasan tertulis di CHANGELOG.
- Hasil trade paper hanya ditulis mesin. Tidak ada koreksi manual pada `positions`/`fills`.
- API key Anthropic hanya di env var user (dibaca `budget_proxy.py`); token Telegram hanya di `HERMES_HOME\.env`.
  Keduanya tidak pernah masuk repo, CLAUDE.md, docs, atau chat.
- `scripts/mcp_server.py` tidak boleh `print()` (stdout = kanal MCP); log ke `logs/mcp_server.log`.
- Jaringan rumah memblokir DNS `binance.com`, `okx.com`, `coinbase.com` (Kominfo). `common.DohResolver` menanganinya di dalam proses
  (daftar host di `common.BINANCE_HOSTS`). **Jangan mengubah DNS atau pengaturan sistem**, dan jangan menyimpan data dari halaman blokir.
- Data yang tidak tersedia ditulis "tidak tersedia" beserta alasannya. Jangan mengestimasi.
- Isi buku di `referensi/buku/` hanya untuk pemakaian pribadi pemilik: jangan menyalin bab ke chat, docs, atau repo;
  agent memakai cuplikan ≤ 320 karakter lewat `cari_referensi` dan kutipan ≤ 15 kata. `referensi/playbook.md` diubah
  statusnya (uji/aktif/pensiun) hanya oleh pemilik.

## Struktur
```
scripts/   common.py, collector.py, paper_engine.py, budget_guard.py, budget_proxy.py, analisis.py,
           mcp_server.py, pemindai.py, notifikasi.py, evaluasi.py, hipotesis.py, uji_hipotesis.py, psikologi.py,
           referensi.py, konversi_buku.py,
           schema_{pasar,paper,budget,kandidat,psikologi}.sql
hermes/    SOUL.md, skills/<nama>/SKILL.md, scripts/{pemindai_cron,notif_cron,uji_cron,psikologi_cron}.py, config.snippet.yaml, cron.cmd, sync.py
tests/     unittest, tanpa jaringan (FixtureMarket, upstream palsu untuk proxy)
data/      sqlite (gitignored)        logs/   log UTF-8 (gitignored)
docs/      spesifikasi, operasi, STATUS, CHANGELOG      jurnal/ laporan/ pasar/ (gitignored sebagian)
referensi/ indeks.md + playbook.md (di-commit); buku/ = ebook asli + hasil konversi <slug>/bab-NN.md (gitignored, pribadi)
```
