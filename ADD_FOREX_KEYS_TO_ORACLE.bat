@echo off
chcp 65001 >nul
echo ========================================
echo   ADD FOREX API KEYS TO ORACLE VM
echo ========================================
echo.
echo This will copy your Forex API keys from local .env to Oracle VM
echo.

REM Extract keys from local .env
echo Reading local .env file...
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /r "^ALPHA_VANTAGE_API_KEY=" .env`) do set ALPHA_KEY=%%b
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /r "^TWELVE_DATA_API_KEY=" .env`) do set TWELVE_KEY=%%b

if "%ALPHA_KEY%"=="" (
    echo ERROR: ALPHA_VANTAGE_API_KEY not found in local .env
    pause
    exit /b 1
)

if "%TWELVE_KEY%"=="" (
    echo ERROR: TWELVE_DATA_API_KEY not found in local .env
    pause
    exit /b 1
)

echo.
echo Found API keys:
echo   ALPHA_VANTAGE: %ALPHA_KEY:~0,10%...
echo   TWELVE_DATA: %TWELVE_KEY:~0,10%...
echo.

set KEY="ssh-key-2026-05-20 (2).key"
set HOST=opc@141.147.114.169
set PROJECT=/home/opc/CryptoPulse-Signals

echo Connecting to Oracle VM...
echo.

REM Check if keys already exist in Oracle .env
ssh -i %KEY% %HOST% "cd %PROJECT% && grep -q '^ALPHA_VANTAGE_API_KEY=' .env && echo 'ALPHA_VANTAGE_API_KEY already exists in Oracle .env' || echo 'ALPHA_VANTAGE_API_KEY=%ALPHA_KEY%' >> .env"

ssh -i %KEY% %HOST% "cd %PROJECT% && grep -q '^TWELVE_DATA_API_KEY=' .env && echo 'TWELVE_DATA_API_KEY already exists in Oracle .env' || echo 'TWELVE_DATA_API_KEY=%TWELVE_KEY%' >> .env"

echo.
echo Verifying keys were added...
ssh -i %KEY% %HOST% "cd %PROJECT% && grep 'ALPHA_VANTAGE_API_KEY\|TWELVE_DATA_API_KEY' .env | sed 's/=.*/=***HIDDEN***/'"

echo.
echo ========================================
echo   Forex API keys added to Oracle VM!
echo ========================================
echo.
echo Next step: Run DEPLOY_ORACLE.bat to restart the bot
echo.
pause
