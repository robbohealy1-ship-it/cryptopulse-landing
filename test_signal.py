"""
Test Signal Sender
After restarting the bot, run this to send a test signal:
    python test_signal.py

Or use PowerShell:
    Invoke-WebRequest -Uri "http://localhost:8081/api/test/send-signal" -Method POST
"""
import requests

print("🚀 Sending TEST signal to VIP and Free channels...")
print()

try:
    response = requests.post("http://localhost:8081/api/test/send-signal")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS!")
        print(f"   Signal ID: {data['signal_id']}")
        print(f"   Symbol: {data['symbol']}")
        print(f"   Confidence: {data['confidence']}%")
        print()
        print("📱 Check your Telegram channels:")
        print("   - VIP channel: Full signal with chart")
        print("   - Free channel: Teaser card")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to dashboard")
    print("   Make sure the bot is running and dashboard is on port 8081")
    print()
    print("   To restart bot with new endpoint:")
    print("   1. Stop current bot (Ctrl+C in terminal)")
    print("   2. Run: python main.py")
    print("   3. Wait for dashboard to start")
    print("   4. Run this script again")
except Exception as e:
    print(f"❌ Error: {e}")
