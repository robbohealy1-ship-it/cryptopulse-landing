"""
Test script for Telegram Group Marketing
Run this to verify your setup before deploying
"""
import asyncio
import sys
from src.marketing.telegram_group_poster import TelegramGroupPoster
from src.database.supabase_client import SupabaseClient
from src.config import settings

async def test_telegram_groups():
    print("=" * 60)
    print("  Telegram Group Marketing - Test Script")
    print("=" * 60)
    print()
    
    # Initialize
    print("📱 Initializing Telegram Group Poster...")
    db = SupabaseClient()
    poster = TelegramGroupPoster(db=db)
    
    # Check configuration
    if not poster.target_groups:
        print("❌ ERROR: No target groups configured!")
        print()
        print("Add TELEGRAM_CROSS_POST_GROUPS to your .env file:")
        print("TELEGRAM_CROSS_POST_GROUPS=-1001234567890,-1009876543210")
        print()
        return
    
    print(f"✅ Found {len(poster.target_groups)} target groups:")
    for group in poster.target_groups:
        print(f"   - {group}")
    print()
    
    # Ask for confirmation
    print("⚠️  This will send a TEST message to all configured groups.")
    response = input("Continue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("❌ Test cancelled")
        return
    
    # Create test message
    test_message = """
🎯 <b>Test Message from CryptoPulse</b>

This is a test of our automated marketing system.

If you see this, the bot is working correctly!

✅ Automated posts will go live soon
📊 Real performance updates
💎 Educational content
🚀 Growth marketing

Free signals: t.me/cryptopulse_signals_free1
VIP access: t.me/CryptoPulseVIPAccessBot
"""
    
    print()
    print("📤 Sending test message to all groups...")
    print("(This may take a few minutes with delays between posts)")
    print()
    
    # Send to all groups
    results = await poster.post_to_all_groups(message=test_message)
    
    # Show results
    print()
    print("=" * 60)
    print("  Test Results")
    print("=" * 60)
    print()
    
    successful = sum(1 for v in results.values() if v)
    failed = len(results) - successful
    
    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    print()
    
    if successful > 0:
        print("✅ SUCCESS! Groups that received the message:")
        for group, success in results.items():
            if success:
                print(f"   ✅ {group}")
    
    if failed > 0:
        print()
        print("❌ FAILED! Groups that did NOT receive the message:")
        for group, success in results.items():
            if not success:
                print(f"   ❌ {group}")
        print()
        print("Common reasons for failure:")
        print("  - Bot not added to the group")
        print("  - Bot doesn't have 'Send Messages' permission")
        print("  - Incorrect group ID")
        print("  - Bot was removed/banned from group")
    
    print()
    print("=" * 60)
    
    if successful == len(results):
        print("🎉 ALL TESTS PASSED!")
        print()
        print("Next steps:")
        print("1. Deploy to Oracle: .\\DEPLOY_ORACLE.bat")
        print("2. Bot will auto-post 3x/day (09:00, 14:00, 20:00 UTC)")
        print("3. Monitor logs for errors")
    else:
        print("⚠️  SOME TESTS FAILED")
        print()
        print("Fix the failed groups before deploying:")
        print("1. Verify bot is member of each group")
        print("2. Check group IDs are correct")
        print("3. Ensure bot has posting permissions")
        print("4. Re-run this test script")
    
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(test_telegram_groups())
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
