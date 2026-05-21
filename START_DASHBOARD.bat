@echo off
setlocal enabledelayedexpansion
title CRYPTO PULSE - Admin Dashboard Launcher
color 0A

echo.
echo ========================================
echo   CRYPTO PULSE SIGNALS
echo   Dashboard Launcher
echo ========================================
echo.

cd /d "%~dp0"
set PYTHONPATH=%CD%

REM Read port from .env
for /f "tokens=2 delims==" %%a in ('findstr /B "ADMIN_DASHBOARD_PORT=" .env 2^>nul') do set DASH_PORT=%%a
if "%DASH_PORT%"=="" set DASH_PORT=8081

set URL=http://localhost:%DASH_PORT%

REM Check if dashboard is already running
echo Checking if dashboard is already running on %URL% ...
powershell -Command "try { $r=Invoke-WebRequest -Uri '%URL%/health' -TimeoutSec 3 -UseBasicParsing; if($r.StatusCode -eq 200){exit 0}} catch {exit 1}" >nul 2>nul

if %ERRORLEVEL%==0 (
    echo.
    echo Dashboard is already running! Opening browser...
    start %URL%
    echo.
    pause
    exit /b 0
)

echo Dashboard not running. Starting system now...
echo.
echo ========================================
echo   WHAT THIS DOES:
echo ========================================
echo.
echo This opens a LOCAL copy of the admin dashboard.
echo It reads data from the SAME database as Oracle.
echo.
echo It does NOT start any Telegram bots.
echo It does NOT scan markets or generate signals.
echo It does NOT conflict with Oracle.
echo.
echo Oracle Cloud VM (production) still does ALL the work.
echo This is just a viewer connected to the same DB.
echo ========================================
echo.

REM ==== USE PYTHON 3.11 EXPLICITLY ====
REM We know py -3.11 works because py (3.14) is broken on this system
set PYTHON_CMD=py -3.11

%PYTHON_CMD% --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo   CRITICAL ERROR: Python 3.11 not found
    echo ========================================
    echo.
    echo You need Python 3.11 installed.
    echo.
    echo Download from: https://www.python.org/downloads/release/python-3119/
    echo.
    echo IMPORTANT: During installation, CHECK:
    echo   [x] Add Python to PATH
    echo   [x] Install pip
    echo.
    pause
    exit /b 1
)

echo.
echo Using Python: %PYTHON_CMD%
for /f "delims=" %%v in ('%PYTHON_CMD% --version 2^>^&1') do echo Version: %%v
echo.

REM ==== CHECK DEPENDENCIES ====
echo Checking core dependencies...
%PYTHON_CMD% -c "import apscheduler, fastapi, uvicorn, telegram" 2>nul
if %ERRORLEVEL%==0 (
    echo   All dependencies OK.
    goto :deps_ok
)

echo.
echo Some dependencies are missing.
echo Attempting to install (this may take 1-2 minutes)...
echo.

REM Try standard install first
%PYTHON_CMD% -m pip install -r requirements.txt --quiet
if %ERRORLEVEL%==0 (
    echo   Dependencies installed successfully.
    goto :deps_ok
)

REM Retry without cache if first attempt failed
echo   First attempt failed. Retrying without cache...
%PYTHON_CMD% -m pip install -r requirements.txt --no-cache-dir --quiet
if %ERRORLEVEL%==0 (
    echo   Dependencies installed successfully.
    goto :deps_ok
)

REM If we get here, pip is broken
cls
echo.
echo ========================================
echo   DEPENDENCY INSTALLATION FAILED
echo ========================================
echo.
echo Your Python 3.11 pip appears to be broken.
echo.
echo CURRENT PYTHON:
%PYTHON_CMD% --version
for /f "delims=" %%p in ('where %PYTHON_CMD% 2^>nul') do echo Location: %%p
echo.
echo SOLUTION:
echo   Open PowerShell as Administrator and run:
echo   %PYTHON_CMD% -m pip install --upgrade pip --force-reinstall
echo   %PYTHON_CMD% -m pip install -r requirements.txt --no-cache-dir
echo.
pause
exit /b 1

:deps_ok
echo.

REM ==== KILL STALE PROCESSES (Simple) ====
echo Checking for stale instances...
taskkill /F /FI "WINDOWTITLE eq CryptoPulse Dashboard" >nul 2>nul
taskkill /F /FI "WINDOWTITLE eq CryptoPulse System + Dashboard" >nul 2>nul
timeout /t 2 /nobreak >nul
echo Done.
echo.

REM ==== START THE SYSTEM ====
echo Starting dashboard directly in this window...
echo URL: %URL%
echo.
echo NOTE: First startup takes 3-4 minutes (loads market data).
echo DO NOT CLOSE this window. The dashboard runs here.
echo Press Ctrl+C to stop when done.
echo.
echo ========================================

%PYTHON_CMD% src/main.py --dashboard-only
