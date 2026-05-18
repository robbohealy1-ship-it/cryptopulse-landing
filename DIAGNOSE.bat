@echo off
title CRYPTO PULSE - System Diagnostics
color 0E
echo.
echo ========================================
echo   CRYPTO PULSE - SYSTEM DIAGNOSTICS
echo ========================================
echo.

cd /d "%~dp0"

echo [1] Checking Python installations...
echo.

REM Check common Python commands
set FOUND_PY=0

for %%C in (py python python3 py -3) do (
    echo   Trying: %%C
    %%C --version >nul 2>nul
    if !ERRORLEVEL!==0 (
        echo      ^>^> FOUND:
        for /f "delims=" %%v in ('%%C --version 2^>^&1') do echo      %%v
        echo      Location:
        for /f "delims=" %%p in ('where %%C 2^>nul') do echo      %%p
        echo.
        set FOUND_PY=1
    ) else (
        echo      ^>^> NOT FOUND
        echo.
    )
)

if %FOUND_PY%==0 (
    echo.
    echo ERROR: No Python found on this system!
    echo.
    echo Please install Python 3.10, 3.11, or 3.12 from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo.
echo [2] Checking installed packages...
echo.

set WORKING_PY=
for %%C in (py python python3) do (
    if "%WORKING_PY%"=="" (
        %%C -c "import apscheduler, fastapi, uvicorn, telegram" >nul 2>nul
        if !ERRORLEVEL!==0 (
            echo   %%C: All packages OK
            set WORKING_PY=%%C
        ) else (
            echo   %%C: MISSING packages ^(apscheduler, fastapi, uvicorn, or telegram^)
        )
    )
)

echo.
if "%WORKING_PY%"=="" (
    echo [3] Attempting to install missing packages...
    echo.
    
    REM Try each Python until one works
    for %%C in (py python python3) do (
        if "%WORKING_PY%"=="" (
            echo   Trying pip install with %%C...
            %%C -m pip install -r requirements.txt --quiet
            if !ERRORLEVEL!==0 (
                echo   ^>^> FAILED with %%C
            ) else (
                echo   ^>^> SUCCESS with %%C
                set WORKING_PY=%%C
            )
        )
    )
)

if "%WORKING_PY%"=="" (
    echo.
    echo ========================================
    echo   CRITICAL ERROR
    echo ========================================
    echo.
    echo Could not install required packages.
    echo This usually means your Python installation is broken.
    echo.
    echo SOLUTIONS:
    echo 1. Uninstall ALL Python versions from Control Panel
    echo 2. Download and install Python 3.11 from:
    echo    https://www.python.org/downloads/release/python-3119/
    echo 3. During install, CHECK "Add Python to PATH"
    echo 4. Also CHECK "Install pip"
    echo 5. Re-run START_DASHBOARD.bat
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   DIAGNOSTICS COMPLETE
echo ========================================
echo.
echo Working Python: %WORKING_PY%
echo.
echo You can now run START_DASHBOARD.bat
echo.
pause
