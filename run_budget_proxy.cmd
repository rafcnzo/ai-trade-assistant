@echo off
rem Menjalankan proxy budget (Hermes -> 127.0.0.1:8585 -> api.anthropic.com) tanpa jendela konsol.
rem Membutuhkan env var user ANTHROPIC_API_KEY (set sendiri lewat `setx`, lihat docs/OPERASI.md).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if not exist logs mkdir logs
".venv\Scripts\pythonw.exe" scripts\budget_proxy.py >> logs\budget_proxy.out.log 2>&1
