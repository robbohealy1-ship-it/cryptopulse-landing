@echo off
REM Push CryptoPulse Landing Page to GitHub for Vercel deployment

cd "%~dp0"

if not exist .git (
    git init
    echo Initialized git repo
)

echo.
echo === GitHub Setup ===
echo 1. Go to https://github.com/new
echo 2. Create a NEW repository (e.g., "cryptopulse-landing")
echo 3. DON'T initialize with README (we have one)
echo.
pause

echo.
set /p repo_url="Paste your GitHub repo HTTPS URL: "

git remote remove origin 2>nul
git remote add origin %repo_url%

git add .
git commit -m "Initial landing page"
git branch -M main
git push -u origin main

echo.
echo === Done! ===
echo Now go to https://vercel.com/new
echo 1. Import your GitHub repo
echo 2. Vercel auto-detects it's a static site
echo 3. Click Deploy
echo.
pause
