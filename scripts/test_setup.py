#!/usr/bin/env python3
"""
CRYPTO PULSE SIGNALS - Setup Test Script
Tests all configurations and connections
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_telegram():
    """Test Telegram bot connection"""
    try:
        from telegram import Bot
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        
        logger.info(f"✅ Telegram bot connected: @{me.username}")
        
        await bot.send_message(
            chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
            text="✅ CRYPTO PULSE SIGNALS - Test message from setup script"
        )
        
        logger.info("✅ Test message sent to admin chat")
        return True
        
    except Exception as e:
        logger.error(f"❌ Telegram test failed: {e}")
        return False


async def test_supabase():
    """Test Supabase connection"""
    try:
        from src.database.supabase_client import SupabaseClient
        
        db = SupabaseClient()
        
        result = db.client.table('signals').select('id').limit(1).execute()
        
        logger.info("✅ Supabase connected successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Supabase test failed: {e}")
        return False


async def test_binance():
    """Test Binance connection"""
    try:
        from src.scanner.market_scanner import MarketScanner
        
        scanner = MarketScanner()
        await scanner.initialize()
        
        pairs = await scanner.get_liquid_pairs()
        
        logger.info(f"✅ Binance connected - Found {len(pairs)} liquid pairs")
        
        await scanner.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Binance test failed: {e}")
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
        
        logger.info("✅ News API connected successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ News API test failed: {e}")
        return False


async def test_stripe():
    """Test Stripe connection"""
    try:
        import stripe
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        products = stripe.Product.list(limit=1)
        
        logger.info("✅ Stripe connected successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Stripe test failed: {e}")
        return False


async def main():
    print("=" * 60)
    print("CRYPTO PULSE SIGNALS - Setup Test")
    print("=" * 60)
    print()
    
    results = {}
    
    print("Testing Telegram...")
    results['telegram'] = await test_telegram()
    print()
    
    print("Testing Supabase...")
    results['supabase'] = await test_supabase()
    print()
    
    print("Testing Binance...")
    results['binance'] = await test_binance()
    print()
    
    print("Testing News API...")
    results['news_api'] = await test_news_api()
    print()
    
    print("Testing Stripe...")
    results['stripe'] = await test_stripe()
    print()
    
    print("=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    for service, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {service.upper()}: {'PASS' if status else 'FAIL'}")
    
    print()
    
    all_passed = all(results.values())
    
    if all_passed:
        print("🎉 All tests passed! System is ready to run.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check configuration.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
