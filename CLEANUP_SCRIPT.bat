@echo off
REM ============================================
REM CRYPTO PULSE SIGNALS - CLEANUP SCRIPT
REM Safely removes duplicate/unused files
REM ============================================

echo.
echo ========================================
echo   CRYPTO PULSE SIGNALS - CLEANUP
echo ========================================
echo.
echo This script will:
echo   1. Backup current state
echo   2. Delete duplicate landing-page folder (NOT your dashboard!)
echo   3. Delete SSH keys from repo (copy to ~/.ssh first if needed!)
echo   4. Delete large binaries (ProtonVPN.exe)
echo   5. Delete unused test files
echo   6. Update .gitignore
echo.
echo IMPORTANT NOTES:
echo   - Your dashboard (src/admin/static/) will NOT be deleted
echo   - SSH keys will be deleted from repo only (copy them first!)
echo   - All changes are committed, you can undo with git reset
echo.
echo Make sure you have committed recent changes!
echo.
pause

REM Create backup
echo.
echo [1/6] Creating backup...
git add -A
git commit -m "Pre-cleanup backup - %date% %time%"
if errorlevel 1 (
    echo Warning: Git commit failed. Continue anyway? 
    pause
)

REM Delete landing-page folder (DUPLICATE)
echo.
echo [2/6] Deleting landing-page folder (duplicate code)...
if exist "landing-page" (
    rmdir /s /q "landing-page"
    echo    ✓ Deleted landing-page/
) else (
    echo    - landing-page/ not found
)

REM Backup and delete SSH keys
echo.
echo [3/6] Handling SSH keys...
echo.
echo ⚠️  SSH keys found in repo (SECURITY RISK!)
echo.
echo Do you need these keys for Oracle? 
echo If YES: They will be copied to ssh-keys-backup/ folder first
echo If NO: They will be deleted immediately
echo.
set /p backup_keys="Backup SSH keys before deleting? (y/n): "

if /i "%backup_keys%"=="y" (
    echo.
    echo Creating backup in ssh-keys-backup/...
    mkdir ssh-keys-backup 2>nul
    if exist "ssh-key-2026-05-20.key" copy "ssh-key-2026-05-20.key" "ssh-keys-backup\" >nul && echo    ✓ Backed up ssh-key-2026-05-20.key
    if exist "ssh-key-2026-05-20 (1).key" copy "ssh-key-2026-05-20 (1).key" "ssh-keys-backup\" >nul && echo    ✓ Backed up ssh-key-2026-05-20 (1).key
    if exist "ssh-key-2026-05-20 (2).key" copy "ssh-key-2026-05-20 (2).key" "ssh-keys-backup\" >nul && echo    ✓ Backed up ssh-key-2026-05-20 (2).key
    echo.
    echo ✅ Keys backed up to: ssh-keys-backup/
    echo    Copy them to C:\Users\%USERNAME%\.ssh\ for Oracle access
    echo.
    pause
)

echo.
echo Deleting SSH keys from repo...
if exist "ssh-key-2026-05-20.key" del /q "ssh-key-2026-05-20.key" && echo    ✓ Deleted ssh-key-2026-05-20.key
if exist "ssh-key-2026-05-20 (1).key" del /q "ssh-key-2026-05-20 (1).key" && echo    ✓ Deleted ssh-key-2026-05-20 (1).key
if exist "ssh-key-2026-05-20 (2).key" del /q "ssh-key-2026-05-20 (2).key" && echo    ✓ Deleted ssh-key-2026-05-20 (2).key

REM Delete large binaries
echo.
echo [4/6] Deleting large binaries...
if exist "ProtonVPN_v4.4.0_x64.exe" del /q "ProtonVPN_v4.4.0_x64.exe" && echo    ✓ Deleted ProtonVPN_v4.4.0_x64.exe (126MB)
if exist "backdrop.png" del /q "backdrop.png" && echo    ✓ Deleted backdrop.png (1.3MB)

REM Delete unused test files
echo.
echo [5/6] Deleting unused test files...
if exist "test_signal.py" del /q "test_signal.py" && echo    ✓ Deleted test_signal.py
if exist "test_startup.py" del /q "test_startup.py" && echo    ✓ Deleted test_startup.py
if exist "get_ctradertoken.py" del /q "get_ctradertoken.py" && echo    ✓ Deleted get_ctradertoken.py

REM Delete duplicate HTML/CSS/JS (dashboard uses its own)
if exist "index.html" del /q "index.html" && echo    ✓ Deleted index.html (duplicate)
if exist "index-updated.html" del /q "index-updated.html" && echo    ✓ Deleted index-updated.html (old)
if exist "script.js" del /q "script.js" && echo    ✓ Deleted script.js (duplicate)
if exist "styles.css" del /q "styles.css" && echo    ✓ Deleted styles.css (duplicate)

REM Update .gitignore
echo.
echo [6/6] Updating .gitignore...
echo. >> .gitignore
echo # Security - never commit keys >> .gitignore
echo *.key >> .gitignore
echo *.pem >> .gitignore
echo. >> .gitignore
echo # Large binaries >> .gitignore
echo *.exe >> .gitignore
echo. >> .gitignore
echo # Duplicates >> .gitignore
echo landing-page/ >> .gitignore
echo    ✓ Updated .gitignore

REM Commit cleanup
echo.
echo [FINAL] Committing cleanup...
git add -A
git commit -m "Project cleanup: removed duplicates, SSH keys, and large binaries"
if errorlevel 1 (
    echo Warning: Git commit failed
) else (
    echo    ✓ Cleanup committed
)

echo.
echo ========================================
echo   CLEANUP COMPLETE!
echo ========================================
echo.
echo Summary:
echo   ✓ Deleted landing-page/ folder (duplicate)
echo   ✓ Deleted SSH keys (security)
echo   ✓ Deleted large binaries (~130MB saved)
echo   ✓ Deleted unused test files
echo   ✓ Updated .gitignore
echo.
echo Next steps:
echo   1. Review changes: git log -1
echo   2. Test bot: START_BOT.bat
echo   3. Deploy to Oracle: git push origin main
echo.
pause
