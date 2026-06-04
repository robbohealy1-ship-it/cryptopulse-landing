@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   CryptoPulse Oracle Cloud Deployer
echo ==========================================
echo.

set KEY="c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\ssh-key-2026-05-20 (2).key"
set HOST=opc@141.147.114.169
set PROJECT=/home/opc/CryptoPulse-Signals
set VENV=/home/opc/venv
set SSH_FLAGS=-i %KEY% -o "StrictHostKeyChecking=no" -o "ConnectTimeout=10"

echo [0/5] Checking SSH key...
if not exist %KEY% (
    echo   ERROR: SSH key not found at:
    echo   %KEY%
    echo.
    echo   Fix: Update KEY= variable in this script
    echo   Your key is backed up in: ssh-keys-backup\
    pause
    exit /b 1
)
echo   SSH key found.
echo.

echo [1/5] Stopping bot on Oracle...
ssh %SSH_FLAGS% %HOST% "pkill -9 -f 'python3.*src.main' 2>/dev/null; sleep 3; echo stopped" 2>nul

REM Check process count with ONE ssh call, retry logic
for /l %%i in (1,1,6) do (
    timeout /t 2 /nobreak >nul
    for /f %%j in ('ssh %SSH_FLAGS% %HOST% "ps -ef 2>/dev/null | grep -c '[s]rc.main'" 2^>nul') do set PROC_COUNT=%%j
    if "!PROC_COUNT!"=="0" (
        echo   All bot processes terminated.
        goto :bot_stopped
    )
    echo   Waiting for processes to die... (!PROC_COUNT! remaining)
    ssh %SSH_FLAGS% %HOST% "pkill -9 -f 'src.main' 2>/dev/null" 2>nul
    timeout /t 3 /nobreak >nul
)
echo   WARNING: !PROC_COUNT! process(es) still running. New bot may conflict.
:bot_stopped

timeout /t 3 /nobreak >nul

echo.
echo [2/5] Uploading latest code...
scp %SSH_FLAGS% -r "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\src" %HOST%:%PROJECT%/
if %errorlevel% neq 0 (
    echo   ERROR: scp failed. Check SSH key permissions and VM status.
    pause
    exit /b 1
)
scp %SSH_FLAGS% "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\requirements.txt" %HOST%:%PROJECT%/
scp %SSH_FLAGS% "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\deploy_oracle.sh" %HOST%:%PROJECT%/

timeout /t 2 /nobreak >nul

echo.
echo [3/5] Removing stale files on server...
ssh %SSH_FLAGS% %HOST% "rm -f %PROJECT%/src/telegram_bot/bot_core.py && find %PROJECT% -name '*.pyc' -delete 2>/dev/null; find %PROJECT% -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; echo cleaned"

timeout /t 2 /nobreak >nul

echo.
echo [4/5] Running deploy script on server...
ssh %SSH_FLAGS% %HOST% "chmod +x %PROJECT%/deploy_oracle.sh && %PROJECT%/deploy_oracle.sh"

timeout /t 2 /nobreak >nul

echo.
echo [5/5] Checking bot status...
ssh %SSH_FLAGS% %HOST% "ps -ef | grep '[p]ython3.*src.main' | wc -l"

echo.
echo ==========================================
echo   Deploy attempt complete.
echo   Check logs: ssh -i %KEY% %HOST% "tail -20 %PROJECT%/bot.log"
echo ==========================================
pause
