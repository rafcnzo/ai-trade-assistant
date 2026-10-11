@echo off
rem Menjalankan dashboard lokal (http://127.0.0.1:8586) tanpa jendela konsol. Baca saja; tidak menulis DB.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if not exist logs mkdir logs
".venv\Scripts\pythonw.exe" scripts\dashboard.py >> logs\dashboard.out.log 2>&1
