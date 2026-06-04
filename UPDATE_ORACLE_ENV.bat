@echo off
echo ========================================
echo   UPDATE ORACLE VM .ENV FILE
echo ========================================
echo.
echo INSTRUCTIONS:
echo 1. This will open an SSH session to Oracle VM
echo 2. Run these commands to add Forex API keys:
echo.
echo    cd /home/opc/CryptoPulse-Signals
echo    nano .env
echo.
echo 3. Add these lines at the bottom:
echo.
echo    # Forex APIs
echo    ALPHA_VANTAGE_API_KEY=your_key_from_local_env
echo    TWELVE_DATA_API_KEY=your_key_from_local_env
echo.
echo 4. Save: Ctrl+X, Y, Enter
echo 5. Exit: type 'exit'
echo 6. Then run DEPLOY_ORACLE.bat
echo.
echo ========================================
echo.
echo Opening SSH session to Oracle VM...
echo.
pause

ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169

echo.
echo ========================================
echo   SSH session closed
echo ========================================
echo.
echo If you added the Forex API keys, run DEPLOY_ORACLE.bat now
echo.
pause
