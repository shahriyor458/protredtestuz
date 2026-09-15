@echo off
REM =========================================================
REM  Pro Tred — AI Metal Trader  /  O'RNATISH (birinchi marta)
REM =========================================================
setlocal
cd /d "%~dp0"

echo [1/4] Python venv yaratilmoqda...
where python >nul 2>nul
if %errorlevel%==0 (
  python -m venv backend\.venv
) else (
  echo Python topilmadi! Ushbu saytdan ornating: https://www.python.org/downloads/
  echo Omatilgan joy: C:\Python312 (masalan), keyin ushbu skriptni qayta ishga tushiring.
  exit /b 1
)
if exist backend\.venv\Scripts\python.exe (
  echo  venv OK
) else (
  echo  venv yaratilmadi — Python PATH da bolishi shart.
  exit /b 1
)

echo [2/4] Python paketlar ornatilmoqda...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip >nul
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if %errorlevel% neq 0 ( echo pip xato & exit /b 1 )

echo [3/4] Admin panel (Vite + React) build...
pushd frontend
call npm install
if %errorlevel% neq 0 ( popd & echo npm xato & exit /b 1 )
call npm run build
if %errorlevel% neq 0 ( popd & echo build xato & exit /b 1 )
popd

echo [4/4] .env fayl tekshirish...
if not exist backend\.env (
  copy backend\.env.example backend\.env >nul
  echo  backend\.env yaratildi — ichiga MT5 va TELEGRAM malumotlarini kiriting!
)

echo.
echo =========================================================
echo  Ornatish tugadi!
echo  Endi backend\.env faylida sozlamalarni kiriting:
echo    MT5_LOGIN / MT5_PASSWORD / MT5_SERVER
echo    TELEGRAM_BOT_TOKEN (BotFather dan)
echo  Keyin start.bat ni ishga tushiring.
echo =========================================================
pause