@echo off
REM =========================================================
REM  Pro Tred — AI Metal Trader  /  ISHGA TUSHIRISH
REM  Backend + Admin-panel (matnli oyna) ochiladi
REM =========================================================
setlocal
cd /d "%~dp0"

if not exist backend\.env (
  echo backend\.env topilmadi. Avval setup.bat ni ishga tushiring.
  exit /b 1
)
if not exist backend\.venv\Scripts\python.exe (
  echo backend\.venv topilmadi. Avval setup.bat ni ishga tushiring.
  exit /b 1
)

echo Pro Tred boshlanmoqda...
echo Admin panel: http://127.0.0.1:8120/panel/
echo API docs:    http://127.0.0.1:8120/docs
echo.

REM backend'ni qaytadashtma oynasida ochamiz: yangi oyna to'g'ri sozlamalarni oladi
if not "%*"=="--nowait" (
  start "Pro Tred Backend" cmd /k "cd /d "%~dp0" && backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8120"
  echo Backend yangi oynada ishga tushdi. Sekunttan song brauzer ochiladi...
  start http://127.0.0.1:8120/panel/
  exit /b 0
)

backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8120