@echo off
setlocal
set PYTHONPATH=%CD%
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8
chcp 65001 >nul

title CryptoPulse Dashboard
color 0A
echo ========================================
echo   CRYPTO PULSE - Dashboard
echo ========================================
echo.

for /f "tokens=2 delims==" %%a in ('findstr /B "ADMIN_DASHBOARD_PORT=" .env 2^>nul') do set PORT=%%a
if "%PORT%"=="" set PORT=8081
set URL=http://localhost:%PORT%

echo Killing old dashboard processes...
taskkill /F /IM python.exe >nul 2>nul
timeout /t 2 /nobreak >nul
echo Done.
echo.

echo Starting dashboard at %URL% ...
echo (Press Ctrl+C to stop)
echo.

py -3.11 src/main.py --dashboard-only

set EXITCODE=%ERRORLEVEL%
if %EXITCODE% NEQ 0 (
    echo.
    echo ========================================
    echo   CRASHED - exit code %EXITCODE%
    echo ========================================
    echo.
    pause
)

echo.
echo Dashboard stopped.
pause
