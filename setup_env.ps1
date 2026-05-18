# CRYPTO PULSE SIGNALS - Environment Setup Script
# This script copies the template to .env if it doesn't exist

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 59 -ForegroundColor Cyan
Write-Host "CRYPTO PULSE SIGNALS - Environment Setup" -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 59 -ForegroundColor Cyan
Write-Host ""

# Check if .env already exists
if (Test-Path ".env") {
    Write-Host "⚠️  .env file already exists!" -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "Do you want to overwrite it? (yes/no)"
    
    if ($response -ne "yes") {
        Write-Host ""
        Write-Host "✅ Keeping existing .env file" -ForegroundColor Green
        Write-Host ""
        Write-Host "To update manually:" -ForegroundColor Cyan
        Write-Host "1. Open .env.template" -ForegroundColor White
        Write-Host "2. Copy any new settings you need" -ForegroundColor White
        Write-Host "3. Add them to your .env file" -ForegroundColor White
        Write-Host ""
        exit 0
    }
}

# Copy template to .env
try {
    Copy-Item ".env.template" ".env" -Force
    Write-Host "✅ Created .env file from template!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 NEXT STEPS:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Open .env file in your editor" -ForegroundColor White
    Write-Host "2. Replace these values:" -ForegroundColor White
    Write-Host ""
    Write-Host "   REQUIRED:" -ForegroundColor Cyan
    Write-Host "   • TELEGRAM_BOT_TOKEN (already have this)" -ForegroundColor White
    Write-Host "   • SUPABASE_URL" -ForegroundColor White
    Write-Host "   • SUPABASE_KEY" -ForegroundColor White
    Write-Host "   • SUPABASE_SERVICE_KEY" -ForegroundColor White
    Write-Host "   • CRYPTO_WALLET_* (your wallet addresses)" -ForegroundColor White
    Write-Host ""
    Write-Host "   OPTIONAL:" -ForegroundColor Cyan
    Write-Host "   • NEWS_API_KEY (system works without it)" -ForegroundColor White
    Write-Host "   • STRIPE_* (only if you want credit cards)" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Save the file" -ForegroundColor White
    Write-Host "4. Run: python scripts/quick_verify.py" -ForegroundColor White
    Write-Host ""
    Write-Host "=" -NoNewline -ForegroundColor Cyan
    Write-Host "=" * 59 -ForegroundColor Cyan
    Write-Host ""
}
catch {
    Write-Host "❌ Error creating .env file: $_" -ForegroundColor Red
    exit 1
}
