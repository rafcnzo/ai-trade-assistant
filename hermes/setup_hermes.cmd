@echo off
rem Setup Hermes untuk crypto-analyst, dijalankan DI LUAR sandbox aplikasi Claude (lewat Task Scheduler
rem "crypto-analyst hermes setup" atau langsung dari terminal user). Idempoten; aman dijalankan berulang.
rem Langkah: salin aset ke HERMES_HOME, gabungkan config.yaml, pasang launcher Startup (proxy + collector),
rem nyalakan proxy & collector, lalu cek Hermes. Log: logs\hermes_setup.log
setlocal
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set "PATH=%LOCALAPPDATA%\hermes\bin;%PATH%"
set LOG=logs\hermes_setup.log
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist logs mkdir logs
echo. >> "%LOG%"
echo ==== %date% %time% setup_hermes (user=%USERNAME%) ==== >> "%LOG%"

echo --- sync --- >> "%LOG%"
".venv\Scripts\python.exe" hermes\sync.py >> "%LOG%" 2>&1

echo --- merge_config --- >> "%LOG%"
".venv\Scripts\python.exe" hermes\merge_config.py >> "%LOG%" 2>&1

echo --- startup launcher --- >> "%LOG%"
copy /Y "hermes\startup\crypto-analyst_proxy.vbs" "%STARTUP%\crypto-analyst_proxy.vbs" >> "%LOG%" 2>&1
copy /Y "hermes\startup\crypto-analyst_collector.vbs" "%STARTUP%\crypto-analyst_collector.vbs" >> "%LOG%" 2>&1
copy /Y "hermes\startup\crypto-analyst_dashboard.vbs" "%STARTUP%\crypto-analyst_dashboard.vbs" >> "%LOG%" 2>&1
dir /b "%STARTUP%" >> "%LOG%" 2>&1

echo --- nyalakan proxy dan collector (instance kedua keluar sendiri karena lock) --- >> "%LOG%"
wscript "%STARTUP%\crypto-analyst_proxy.vbs"
wscript "%STARTUP%\crypto-analyst_collector.vbs"
wscript "%STARTUP%\crypto-analyst_dashboard.vbs"
timeout /t 6 /nobreak > nul
curl -s --max-time 5 http://127.0.0.1:8585/healthz >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- hermes --version --- >> "%LOG%"
call hermes --version >> "%LOG%" 2>&1
echo --- hermes doctor --- >> "%LOG%"
call hermes doctor >> "%LOG%" 2>&1
echo --- hermes mcp test paper --- >> "%LOG%"
call hermes mcp test paper >> "%LOG%" 2>&1
echo --- hermes cron list --- >> "%LOG%"
call hermes cron list >> "%LOG%" 2>&1
echo ==== selesai %time% ==== >> "%LOG%"
endlocal
