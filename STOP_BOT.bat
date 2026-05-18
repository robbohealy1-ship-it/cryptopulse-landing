@echo off
title CRYPTO PULSE SIGNALS - Stopping...
color 0C

echo.
echo ========================================
echo   CRYPTO PULSE SIGNALS
echo   Stopping Platform...
echo ========================================
echo.

taskkill /F /FI "WINDOWTITLE eq CRYPTO PULSE SIGNALS - Running*" /T
taskkill /F /FI "IMAGENAME eq python.exe" /FI "MEMUSAGE gt 50000"

echo.
echo Platform stopped!
echo.
pause
