@echo off
title CRYPTO PULSE - Simple Start
color 0C
echo.
echo ========================================
echo   WARNING: FULL BOT START
echo ========================================
echo.
echo This starts the COMPLETE bot including:
echo   - Telegram bots (admin, VIP)
echo   - Market scanning
echo   - Signal generation
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

REM Use Python 3.11 explicitly (py defaults to broken 3.14 on this system)
set PYTHON_CMD=py -3.11

%PYTHON_CMD% --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Python 3.11 not found!
    echo Install Python 3.11 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo Found Python: 
%PYTHON_CMD% --version
echo.
echo Starting system now...
echo If this fails, the error will show below.
echo ========================================
echo.
%PYTHON_CMD% src/main.py
echo.
echo ========================================
echo Process exited with code: %ERRORLEVEL%
echo.
pause
exit /b %ERRORLEVEL%
