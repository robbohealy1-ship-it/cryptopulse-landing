# CRYPTO PULSE SIGNALS - API Signup Helper
# Opens all API signup pages in your browser

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "🔑 CRYPTO PULSE SIGNALS - API Signup Helper" -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "This will open signup pages for all data sources." -ForegroundColor White
Write-Host "You'll need to sign up manually, but this makes it faster!" -ForegroundColor White
Write-Host ""

$apis = @(
    @{
        Name = "NewsAPI"
        URL = "https://newsapi.org/register"
        Priority = "HIGH"
        Time = "2 min"
    },
    @{
        Name = "CryptoPanic"
        URL = "https://cryptopanic.com/developers/api/"
        Priority = "HIGH"
        Time = "3 min"
    },
    @{
        Name = "Glassnode"
        URL = "https://studio.glassnode.com/signup"
        Priority = "CRITICAL"
        Time = "5 min"
    },
    @{
        Name = "LunarCrush"
        URL = "https://lunarcrush.com/developers/api"
        Priority = "HIGH"
        Time = "3 min"
    },
    @{
        Name = "Messari"
        URL = "https://messari.io/api"
        Priority = "MEDIUM"
        Time = "3 min"
    },
    @{
        Name = "CoinMarketCap"
        URL = "https://coinmarketcap.com/api/"
        Priority = "MEDIUM"
        Time = "3 min"
    },
    @{
        Name = "Santiment"
        URL = "https://app.santiment.net/sign-up"
        Priority = "HIGH"
        Time = "4 min"
    },
    @{
        Name = "The Graph"
        URL = "https://thegraph.com/studio/"
        Priority = "LOW"
        Time = "3 min"
    },
    @{
        Name = "Dune Analytics"
        URL = "https://dune.com/auth/register"
        Priority = "LOW"
        Time = "3 min"
    }
)

Write-Host "📋 APIs to sign up for:" -ForegroundColor Cyan
Write-Host ""

foreach ($api in $apis) {
    $color = switch ($api.Priority) {
        "CRITICAL" { "Red" }
        "HIGH" { "Yellow" }
        "MEDIUM" { "White" }
        "LOW" { "Gray" }
    }
    
    Write-Host "  [$($api.Priority)]" -ForegroundColor $color -NoNewline
    Write-Host " $($api.Name) - $($api.Time)" -ForegroundColor White
}

Write-Host ""
Write-Host "Total time: ~30 minutes for all" -ForegroundColor Cyan
Write-Host ""

$response = Read-Host "Open signup pages? (yes/no)"

if ($response -eq "yes" -or $response -eq "y") {
    Write-Host ""
    Write-Host "🌐 Opening signup pages..." -ForegroundColor Green
    Write-Host ""
    
    foreach ($api in $apis) {
        Write-Host "Opening: $($api.Name)..." -ForegroundColor Cyan
        Start-Process $api.URL
        Start-Sleep -Seconds 2
    }
    
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "✅ All pages opened!" -ForegroundColor Green
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📝 For each site:" -ForegroundColor Yellow
    Write-Host "  1. Sign up with your email" -ForegroundColor White
    Write-Host "  2. Verify email" -ForegroundColor White
    Write-Host "  3. Get API key" -ForegroundColor White
    Write-Host "  4. Copy to .env file" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 TIP: Start with these 3 first:" -ForegroundColor Cyan
    Write-Host "  • Glassnode (most important!)" -ForegroundColor Yellow
    Write-Host "  • NewsAPI" -ForegroundColor White
    Write-Host "  • CryptoPanic" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Cancelled. Run this script again when ready!" -ForegroundColor Yellow
    Write-Host ""
}
