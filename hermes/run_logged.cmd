@echo off
rem Pelaksana perintah DI LUAR sandbox aplikasi Claude (dibuka lewat Explorer atau dari terminal user).
rem Membaca satu perintah per baris dari logs\hermes_cmd.txt, menjalankannya berurutan, dan mencatat ke logs\hermes_run.log.
rem Dipakai Claude Code untuk `hermes gateway start`, `hermes cron create`, uji `hermes -z`, dll.
setlocal
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set "PATH=%LOCALAPPDATA%\hermes\bin;%PATH%"
set CMDFILE=logs\hermes_cmd.txt
set LOG=logs\hermes_run.log
if not exist logs mkdir logs
echo. >> "%LOG%"
echo ==== %date% %time% run_logged ==== >> "%LOG%"
if not exist "%CMDFILE%" (
  echo tidak ada %CMDFILE% >> "%LOG%"
  goto :selesai
)
for /f "usebackq delims=" %%L in ("%CMDFILE%") do (
  echo --- %%L --- >> "%LOG%"
  call %%L >> "%LOG%" 2>&1
)
:selesai
echo ==== selesai %time% ==== >> "%LOG%"
endlocal
