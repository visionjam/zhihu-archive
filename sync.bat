@echo off
setlocal
cd /d "%~dp0"
python tools\sync.py %*
set code=%errorlevel%
if not "%~1"=="--scheduled" pause
exit /b %code%
