"""
Pre-start verification script for CryptoPulse Signals
Run this before starting the bot to catch config issues

Copyright (c) 2026 CryptoPulse Signals. All rights reserved.
Unauthorized copying, distribution, or modification of this software,
via any medium, is strictly prohibited. Proprietary and confidential.
"""
import os
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def check_env():
    """Check all required environment variables"""
    print("=" * 50)
    print("CHECKING ENVIRONMENT CONFIGURATION")
    print("=" * 50)
    
    errors = []
    warnings = []
    
    # Required tokens
    admin_token = os.getenv('TELEGRAM_BOT_TOKEN')
    vip_token = os.getenv('TELEGRAM_VIP_BOT_TOKEN')
    
    if not admin_token or admin_token == 'your_bot_token_from_botfather':
        errors.append("❌ TELEGRAM_BOT_TOKEN not set or is placeholder")
    else:
        print("✅ Admin bot token: configured (masked for security)")
    
    if not vip_token or vip_token == 'your_vip_bot_token_here':
        warnings.append("⚠️ TELEGRAM_VIP_BOT_TOKEN not set - VIP bot will use admin token")
    else:
        print("✅ VIP bot token: configured (masked for security)")
    
    # Bot usernames
    admin_user = os.getenv('TELEGRAM_BOT_USERNAME', 'cryptopulse_admin_bot')
    vip_user = os.getenv('TELEGRAM_VIP_BOT_USERNAME', 'CryptoPulseVIPBot')
    print(f"✅ Admin bot username: @{admin_user}")
    print(f"✅ VIP bot username: @{vip_user}")
    
    # Channel IDs
    free_ch = os.getenv('TELEGRAM_FREE_CHANNEL_ID', '')
    vip_ch = os.getenv('TELEGRAM_VIP_CHANNEL_ID', '')
    admin_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '')
    
    if not free_ch or free_ch == '-1003965675544':
        warnings.append("⚠️ TELEGRAM_FREE_CHANNEL_ID might be placeholder")
    else:
        print(f"✅ Free channel: {free_ch}")
    
    if not vip_ch or vip_ch == '-1003771790853':
        warnings.append("⚠️ TELEGRAM_VIP_CHANNEL_ID might be placeholder")
    else:
        print(f"✅ VIP channel: {vip_ch}")
    
    if not admin_id or admin_id == '7726574032':
        warnings.append("⚠️ TELEGRAM_ADMIN_CHAT_ID might be placeholder")
    else:
        print(f"✅ Admin chat ID: {admin_id}")
    
    return errors, warnings

def check_pricing():
    """Check VIP pricing configuration"""
    print("\n" + "=" * 50)
    print("CHECKING VIP PRICING")
    print("=" * 50)
    
    try:
        from src.config import settings
        
        print(f"✅ Monthly: ${settings.VIP_MONTHLY_PRICE}")
        print(f"✅ Quarterly: ${settings.VIP_QUARTERLY_PRICE}")
        print(f"✅ Lifetime: ${settings.VIP_LIFETIME_PRICE}")
        
        if settings.VIP_MONTHLY_PRICE == 49.0:
            print("ℹ️  Using default $49/month pricing")
        
        return [], []
    except Exception as e:
        return [f"❌ Error loading pricing config: {e}"], []

def check_wallets():
    """Check crypto wallet addresses"""
    print("\n" + "=" * 50)
    print("CHECKING CRYPTO WALLETS")
    print("=" * 50)
    
    wallets = {
        'BTC': os.getenv('CRYPTO_WALLET_BTC'),
        'ETH': os.getenv('CRYPTO_WALLET_ETH'),
        'SOL': os.getenv('CRYPTO_WALLET_SOL'),
        'LTC': os.getenv('CRYPTO_WALLET_LTC'),
    }
    
    warnings = []
    active = []
    
    for coin, address in wallets.items():
        if address and not address.startswith('your_'):
            print(f"✅ {coin}: configured (masked for security)")
            active.append(coin)
        else:
            print(f"⚠️  {coin}: Not configured")
            warnings.append(f"{coin} wallet not set")
    
    if not active:
        warnings.append("❌ NO crypto wallets configured - payments won't work!")
    
    return [], warnings

def check_supabase():
    """Check Supabase config"""
    print("\n" + "=" * 50)
    print("CHECKING SUPABASE")
    print("=" * 50)
    
    url = os.getenv('SUPABASE_URL', '')
    key = os.getenv('SUPABASE_KEY', '')
    
    if not url or 'your-project-id' in url:
        return ["❌ SUPABASE_URL not configured"], []
    
    if not key or 'your_' in key:
        return ["❌ SUPABASE_KEY not configured"], []
    
    print("✅ Supabase URL: configured (masked for security)")
    print("✅ Supabase Key: configured (masked for security)")
    return [], []

def check_syntax():
    """Check all Python files compile"""
    print("\n" + "=" * 50)
    print("CHECKING FILE SYNTAX")
    print("=" * 50)
    
    import py_compile
    
    files = [
        'src/main.py',
        'src/telegram_bot/vip_bot.py',
        'src/telegram_bot/admin_bot.py',
        'src/telegram_bot/channel_publisher.py',
        'src/engine/signal_engine.py',
        'src/payments/crypto_payment_handler.py',
        'src/database/supabase_client.py',
    ]
    
    errors = []
    for file in files:
        try:
            py_compile.compile(file, doraise=True)
            print(f"✅ {file}")
        except py_compile.PyCompileError as e:
            print(f"❌ {file}: {e}")
            errors.append(f"Syntax error in {file}")
    
    return errors, []

def main():
    print("\n" + "=" * 50)
    print("CRYPTOPULSE SIGNALS - PRE-START VERIFICATION")
    print("=" * 50 + "\n")
    
    all_errors = []
    all_warnings = []
    
    checks = [
        ("Environment", check_env),
        ("Pricing", check_pricing),
        ("Wallets", check_wallets),
        ("Supabase", check_supabase),
        ("Syntax", check_syntax),
    ]
    
    for name, check_func in checks:
        try:
            errors, warnings = check_func()
            all_errors.extend(errors)
            all_warnings.extend(warnings)
        except Exception as e:
            all_errors.append(f"❌ {name} check failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    if all_errors:
        print(f"\n❌ {len(all_errors)} ERRORS FOUND:")
        for e in all_errors:
            print(f"  {e}")
        print("\n⚠️  Fix these before starting!")
        return False
    
    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} Warnings (non-critical):")
        for w in all_warnings:
            print(f"  {w}")
    
    print("\n✅ ALL CHECKS PASSED - Ready to start!")
    print("\nRun: START_BOT.bat")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
