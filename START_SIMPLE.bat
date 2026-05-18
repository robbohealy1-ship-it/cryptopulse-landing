@echo off
title CRYPTO PULSE - Simple Start
color 0A
echo.
echo ========================================
echo   CRYPTO PULSE SIGNALS
echo   Simple Start (Debug Mode)
echo ========================================
echo.
echo This window will stay open so you can see errors.
echo.

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
