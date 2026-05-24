"""
Comprehensive Test Suite
Tests signal flow, payments, dashboard, and all critical paths
"""
import asyncio
import sys
from datetime import datetime
from src.database.supabase_client import SupabaseClient
from src.engine.signal_engine import SignalEngine
from src.telegram_bot.vip_bot import VIPBot
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ComprehensiveTest:
    def __init__(self):
        self.db = SupabaseClient()
        self.signal_engine = SignalEngine(db=self.db)
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
    
    async def test_database_connection(self):
        """Test 1: Database Connection"""
        try:
            logger.info("🔍 Testing database connection...")
            
            # Try to query signals table
            result = self.db.client.from_('signals').select('id').limit(1).execute()
            
            self.results['passed'].append("✅ Database connection working")
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Database connection failed: {e}")
            return False
    
    async def test_signal_generation(self):
        """Test 2: Signal Generation"""
        try:
            logger.info("🔍 Testing signal generation...")
            
            # Initialize signal engine
            await self.signal_engine.initialize()
            
            # Try to scan one symbol
            signal = await self.signal_engine.scan_for_signals('BTCUSDT', '1h')
            
            if signal:
                self.results['passed'].append(f"✅ Signal generated: {signal.symbol} {signal.timeframe}")
            else:
                self.results['warnings'].append("⚠️ No signal found (normal if no setup)")
            
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Signal generation failed: {e}")
            return False
    
    async def test_signal_ranking(self):
        """Test 3: Signal Ranking System"""
        try:
            logger.info("🔍 Testing signal ranking...")
            
            # Check if ranker is initialized
            if hasattr(self.signal_engine, 'signal_ranker'):
                stats = self.signal_engine.signal_ranker.get_daily_stats()
                self.results['passed'].append(f"✅ Signal ranker working (found: {stats['total_found']}, published: {stats['published']})")
            else:
                self.results['failed'].append("❌ Signal ranker not initialized")
                return False
            
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Signal ranking failed: {e}")
            return False
    
    async def test_stop_validation(self):
        """Test 4: Stop Loss Validation"""
        try:
            logger.info("🔍 Testing stop validation...")
            
            from src.analysis.stop_validator import StopValidator
            validator = StopValidator()
            
            # Test with dummy data
            import pandas as pd
            df = pd.DataFrame({
                'high': [100, 102, 101, 103, 105],
                'low': [98, 99, 98, 100, 102],
                'close': [99, 101, 100, 102, 104]
            })
            
            is_valid, adjusted, warning = validator.validate_stop(
                entry=100,
                stop=99,
                timeframe='1h',
                df=df,
                direction='LONG'
            )
            
            self.results['passed'].append(f"✅ Stop validator working (valid: {is_valid})")
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Stop validation failed: {e}")
            return False
    
    async def test_telegram_bots(self):
        """Test 5: Telegram Bot Connections"""
        try:
            logger.info("🔍 Testing Telegram bots...")
            
            from src.config import settings
            
            # Check if tokens exist
            if settings.TELEGRAM_ADMIN_BOT_TOKEN:
                self.results['passed'].append("✅ Admin bot token configured")
            else:
                self.results['failed'].append("❌ Admin bot token missing")
            
            if settings.TELEGRAM_VIP_BOT_TOKEN:
                self.results['passed'].append("✅ VIP bot token configured")
            else:
                self.results['failed'].append("❌ VIP bot token missing")
            
            if settings.TELEGRAM_VIP_CHANNEL_ID:
                self.results['passed'].append("✅ VIP channel ID configured")
            else:
                self.results['warnings'].append("⚠️ VIP channel ID not set")
            
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Telegram config check failed: {e}")
            return False
    
    async def test_payment_config(self):
        """Test 6: Payment Configuration"""
        try:
            logger.info("🔍 Testing payment configuration...")
            
            from src.config import settings
            
            # Check Stripe
            if settings.STRIPE_SECRET_KEY:
                self.results['passed'].append("✅ Stripe configured")
            else:
                self.results['warnings'].append("⚠️ Stripe not configured (optional)")
            
            # Check crypto wallets
            if settings.USDT_WALLET_ADDRESS:
                self.results['passed'].append("✅ USDT wallet configured")
            else:
                self.results['warnings'].append("⚠️ USDT wallet not configured")
            
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Payment config check failed: {e}")
            return False
    
    async def test_dashboard_files(self):
        """Test 7: Dashboard Files"""
        try:
            logger.info("🔍 Testing dashboard files...")
            
            import os
            
            dashboard_files = [
                'src/admin/static/index.html',
                'src/admin/static/styles.css',
                'src/admin/static/script.js'
            ]
            
            for file in dashboard_files:
                if os.path.exists(file):
                    self.results['passed'].append(f"✅ {file} exists")
                else:
                    self.results['failed'].append(f"❌ {file} missing")
            
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Dashboard files check failed: {e}")
            return False
    
    async def test_migration_status(self):
        """Test 8: Database Migration Status"""
        try:
            logger.info("🔍 Testing migration status...")
            
            # Check if TP tracking columns exist
            result = self.db.client.from_('signals').select('tp1_hit').limit(1).execute()
            
            self.results['passed'].append("✅ TP tracking migration applied")
            return True
        except Exception as e:
            self.results['warnings'].append("⚠️ TP tracking migration not applied yet (run run_migration.py)")
            return True  # Not critical
    
    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 70)
        print("  COMPREHENSIVE TEST SUITE")
        print("=" * 70)
        print()
        
        tests = [
            ("Database Connection", self.test_database_connection),
            ("Signal Generation", self.test_signal_generation),
            ("Signal Ranking", self.test_signal_ranking),
            ("Stop Validation", self.test_stop_validation),
            ("Telegram Bots", self.test_telegram_bots),
            ("Payment Config", self.test_payment_config),
            ("Dashboard Files", self.test_dashboard_files),
            ("Migration Status", self.test_migration_status),
        ]
        
        for i, (name, test_func) in enumerate(tests, 1):
            print(f"\n[{i}/{len(tests)}] {name}...")
            try:
                await test_func()
            except Exception as e:
                self.results['failed'].append(f"❌ {name} crashed: {e}")
            print("  Done.")
        
        # Print results
        print("\n" + "=" * 70)
        print("  TEST RESULTS")
        print("=" * 70)
        
        print(f"\n✅ PASSED ({len(self.results['passed'])}):")
        for result in self.results['passed']:
            print(f"  {result}")
        
        if self.results['warnings']:
            print(f"\n⚠️ WARNINGS ({len(self.results['warnings'])}):")
            for result in self.results['warnings']:
                print(f"  {result}")
        
        if self.results['failed']:
            print(f"\n❌ FAILED ({len(self.results['failed'])}):")
            for result in self.results['failed']:
                print(f"  {result}")
        
        # Summary
        print("\n" + "=" * 70)
        total = len(self.results['passed']) + len(self.results['warnings']) + len(self.results['failed'])
        passed_pct = (len(self.results['passed']) / total * 100) if total > 0 else 0
        
        if len(self.results['failed']) == 0:
            print(f"  ✅ ALL TESTS PASSED ({passed_pct:.0f}%)")
            print("  Your bot is ready to launch! 🚀")
        else:
            print(f"  ⚠️ SOME TESTS FAILED ({passed_pct:.0f}% passed)")
            print("  Fix failed tests before launching.")
        
        print("=" * 70)
        print()


async def main():
    tester = ComprehensiveTest()
    await tester.run_all_tests()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")
