@echo off
rem Menjalankan collector (data pasar + mesin paper) tanpa jendela konsol.
rem Didaftarkan ke Task Scheduler oleh pengguna (lihat docs/OPERASI.md).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if not exist logs mkdir logs
".venv\Scripts\pythonw.exe" scripts\collector.py run >> logs\collector.out.log 2>&1
