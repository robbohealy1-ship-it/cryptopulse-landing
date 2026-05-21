@echo off
title CRYPTO PULSE SIGNALS - Starting...
color 0C

echo.
echo ========================================
echo   WARNING: FULL BOT START
echo ========================================
echo.
echo This starts the COMPLETE bot including:
echo   - Telegram bots (admin, VIP)
echo   - Market scanning and signal generation
echo   - Dashboard
echo.
echo If the Oracle Cloud bot is already running,
echo THIS WILL CONFLICT and kick it offline!
echo.
echo For local dashboard viewing ONLY, use:
echo   START_DASHBOARD.bat
echo.
echo Are you sure you want to start the FULL bot? (y/n)
set /p CONFIRM=
if /I not "%CONFIRM%"=="y" (
    echo Cancelled.
    pause
    exit /b 0
)

color 0A
cd /d "%~dp0"

set PYTHONPATH=%CD%

REM Detect dashboard port from .env
for /f "tokens=2 delims==" %%a in ('findstr /B "ADMIN_DASHBOARD_PORT=" .env 2^>nul') do set DASH_PORT=%%a
if "%DASH_PORT%"=="" set DASH_PORT=8081

echo.
echo NOTE: This starts BOTH the bot AND the dashboard.
echo Dashboard will be available at: http://localhost:%DASH_PORT%
echo.

py -3.11 src/main.py

pause
