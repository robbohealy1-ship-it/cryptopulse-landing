@echo off
title CRYPTO PULSE SIGNALS - Starting...
color 0A

echo.
echo ========================================
echo   CRYPTO PULSE SIGNALS
echo   Starting Platform...
echo ========================================
echo.

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
