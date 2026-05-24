@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   CryptoPulse Oracle Cloud Deployer
echo ==========================================
echo.

set KEY="c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\ssh-keys-backup\ssh-key-2026-05-20 (2).key"
set HOST=opc@141.147.114.169
set PROJECT=/home/opc/CryptoPulse-Signals
set VENV=/home/opc/venv

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
ssh -i %KEY% -o StrictHostKeyChecking=no %HOST% "pkill -9 -f 'python3 -m src.main' 2>/dev/null; pkill -9 -f 'python3 src/main.py' 2>/dev/null; pkill -9 -f 'src.main' 2>/dev/null; sleep 3; echo stopped"
for /l %%i in (1,1,6) do (
    for /f %%j in ('ssh -i %KEY% -o StrictHostKeyChecking=no %HOST% "ps aux ^| grep 'src.main' ^| grep -v grep ^| wc -l"') do set PROC_COUNT=%%j
    if "!PROC_COUNT!"=="0" (
        echo   All bot processes terminated.
        goto :bot_stopped
    )
    echo   Waiting for processes to die... (!PROC_COUNT! remaining)
    ssh -i %KEY% -o StrictHostKeyChecking=no %HOST% "pkill -9 -f 'src.main' 2>/dev/null || true"
    timeout /t 2 /nobreak >nul
)
echo   WARNING: !PROC_COUNT! process(es) still running. New bot may conflict.
:bot_stopped

echo.
echo [2/5] Uploading latest code...
scp -i %KEY% -o StrictHostKeyChecking=no -r "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\src" %HOST%:%PROJECT%/
scp -i %KEY% -o StrictHostKeyChecking=no "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\requirements.txt" %HOST%:%PROJECT%/
scp -i %KEY% -o StrictHostKeyChecking=no "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\deploy_oracle.sh" %HOST%:%PROJECT%/

echo.
echo [3/5] Removing stale files on server...
ssh -i %KEY% -o StrictHostKeyChecking=no %HOST% "rm -f %PROJECT%/src/telegram_bot/bot_core.py; find %PROJECT% -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; find %PROJECT% -name '*.pyc' -delete 2>/dev/null; echo cleaned"

echo.
echo [4/5] Running deploy script on server...
ssh -i %KEY% -o StrictHostKeyChecking=no %HOST% "chmod +x %PROJECT%/deploy_oracle.sh && %PROJECT%/deploy_oracle.sh"

echo.
echo [5/5] Checking bot status...
ssh -i %KEY% -o StrictHostKeyChecking=no %HOST% "ps aux | grep 'python3 -m src.main' | grep -v grep | wc -l"

echo.
echo ==========================================
echo   Deploy attempt complete.
echo   Check logs: ssh -i %KEY% %HOST% "tail -20 %PROJECT%/bot.log"
echo ==========================================
pause
