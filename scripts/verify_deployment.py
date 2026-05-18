#!/usr/bin/env python3
"""
CRYPTO PULSE SIGNALS - Deployment Verification Script
Comprehensive checks before going live
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils.logger import get_logger
from src.utils.validators import run_all_validations

logger = get_logger(__name__)


async def test_telegram_bot():
    """Test Telegram bot connection and permissions"""
    try:
        from telegram import Bot
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        
        logger.info(f"✅ Bot connected: @{me.username}")
        
        # Test admin chat
        try:
            await bot.send_message(
                chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
                text="✅ CRYPTO PULSE SIGNALS - Deployment verification test"
            )
            logger.info("✅ Admin chat accessible")
        except Exception as e:
            logger.error(f"❌ Cannot send to admin chat: {e}")
            return False
        
        # Test free channel
        try:
            test_msg = await bot.send_message(
                chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                text="✅ Test - Free channel verification"
            )
            await bot.delete_message(
                chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                message_id=test_msg.message_id
            )
            logger.info("✅ Free channel accessible and bot has permissions")
        except Exception as e:
            logger.error(f"❌ Free channel issue: {e}")
            return False
        
        # Test VIP channel
        try:
            test_msg = await bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text="✅ Test - VIP channel verification"
            )
            await bot.delete_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                message_id=test_msg.message_id
            )
            logger.info("✅ VIP channel accessible and bot has permissions")
        except Exception as e:
            logger.error(f"❌ VIP channel issue: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Telegram test failed: {e}")
        return False


async def test_binance():
    """Test Binance connection"""
    try:
        from src.scanner.market_scanner import MarketScanner
        
        scanner = MarketScanner()
        await scanner.initialize()
        
        # Test fetching pairs
        pairs = await scanner.get_liquid_pairs()
        logger.info(f"✅ Binance connected - {len(pairs)} liquid pairs found")
        
        # Test fetching data
        if pairs:
            test_symbol = pairs[0]
            df = await scanner.fetch_ohlcv(test_symbol, '15m', limit=100)
            logger.info(f"✅ Can fetch OHLCV data for {test_symbol}")
        
        await scanner.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Binance test failed: {e}")
        return False


async def test_supabase():
    """Test Supabase connection"""
    try:
        from src.database.supabase_client import SupabaseClient
        
        db = SupabaseClient()
        
        # Test query
        result = db.client.table('signals').select('id').limit(1).execute()
        logger.info("✅ Supabase connected and accessible")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Supabase test failed: {e}")
        logger.error("Make sure you've run the SQL setup scripts!")
        return False


async def test_stripe():
    """Test Stripe connection"""
    try:
        import stripe
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Test API connection
        products = stripe.Product.list(limit=1)
        logger.info("✅ Stripe connected")
        
        # Verify price ID exists
        try:
            price = stripe.Price.retrieve(settings.STRIPE_VIP_PRICE_ID)
            logger.info(f"✅ VIP price found: {price.unit_amount/100} {price.currency.upper()}/{price.recurring.interval}")
        except Exception as e:
            logger.warning(f"⚠️  VIP price ID may be invalid: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Stripe test failed: {e}")
        return False


async def test_news_api():
    """Test News API connection"""
    try:
        from newsapi import NewsApiClient
        
        newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)
        
        news = newsapi.get_top_headlines(
            q='bitcoin',
            language='en',
            page_size=1
        )
        
        logger.info("✅ News API connected")
        return True
        
    except Exception as e:
        logger.error(f"❌ News API test failed: {e}")
        return False


def check_directories():
    """Check required directories exist"""
    try:
        required_dirs = ['logs', 'data', 'charts', 'assets']
        
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Created directory: {dir_name}")
            else:
                logger.info(f"✅ Directory exists: {dir_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Directory check failed: {e}")
        return False


def check_files():
    """Check required files exist"""
    try:
        required_files = [
            '.env',
            'requirements.txt',
            'docker-compose.yml',
            'Dockerfile',
        ]
        
        missing = []
        for file_name in required_files:
            if not Path(file_name).exists():
                missing.append(file_name)
        
        if missing:
            logger.error(f"❌ Missing files: {', '.join(missing)}")
            return False
        
        logger.info("✅ All required files present")
        return True
        
    except Exception as e:
        logger.error(f"❌ File check failed: {e}")
        return False


async def test_signal_generation():
    """Test signal generation workflow (dry run)"""
    try:
        from src.engine.signal_engine import SignalEngine
        
        logger.info("Testing signal generation (this may take a minute)...")
        
        engine = SignalEngine()
        await engine.initialize()
        
        # Try to scan for signals
        candidates = await engine.scan_for_signals('15m')
        
        logger.info(f"✅ Signal engine working - Found {len(candidates)} candidates")
        
        await engine.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Signal generation test failed: {e}")
        return False


async def main():
    print("=" * 70)
    print("CRYPTO PULSE SIGNALS - DEPLOYMENT VERIFICATION")
    print("=" * 70)
    print()
    
    results = {}
    
    # Environment validation
    print("🔍 Validating environment...")
    results['environment'] = run_all_validations()
    print()
    
    # File system checks
    print("🔍 Checking file system...")
    results['directories'] = check_directories()
    results['files'] = check_files()
    print()
    
    # External service tests
    print("🔍 Testing Telegram...")
    results['telegram'] = await test_telegram_bot()
    print()
    
    print("🔍 Testing Binance...")
    results['binance'] = await test_binance()
    print()
    
    print("🔍 Testing Supabase...")
    results['supabase'] = await test_supabase()
    print()
    
    print("🔍 Testing Stripe...")
    results['stripe'] = await test_stripe()
    print()
    
    print("🔍 Testing News API...")
    results['news_api'] = await test_news_api()
    print()
    
    # Signal generation test
    print("🔍 Testing signal generation...")
    results['signal_engine'] = await test_signal_generation()
    print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION RESULTS")
    print("=" * 70)
    
    for service, status in results.items():
        emoji = "✅" if status else "❌"
        status_text = "PASS" if status else "FAIL"
        print(f"{emoji} {service.upper().replace('_', ' ')}: {status_text}")
    
    print()
    
    all_passed = all(results.values())
    
    if all_passed:
        print("=" * 70)
        print("🎉 ALL CHECKS PASSED!")
        print("=" * 70)
        print()
        print("Your CRYPTO PULSE SIGNALS platform is ready to deploy!")
        print()
        print("Next steps:")
        print("1. Review all settings in .env")
        print("2. Start the system: docker-compose up -d")
        print("3. Monitor logs: docker-compose logs -f")
        print("4. Check dashboard: http://localhost:8501")
        print()
        return 0
    else:
        print("=" * 70)
        print("⚠️  SOME CHECKS FAILED")
        print("=" * 70)
        print()
        print("Please fix the failed checks before deploying.")
        print("Review the error messages above for details.")
        print()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
