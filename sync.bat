@echo off
setlocal
cd /d "%~dp0"
python tools\sync.py %*
if errorlevel 1 (
  echo.
  echo 同步失败，请查看 .local\logs\ 下的日志。
  pause
  exit /b 1
)
echo.
echo 同步完成。
pause
