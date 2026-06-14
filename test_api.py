import requests
import json

# Test the local dashboard API
response = requests.get('http://localhost:8081/api/signals/active')
data = response.json()

print(f"Total signals: {data['count']}")
print("\nSignals:")
for signal in data['signals']:
    print(f"\n{signal['symbol']} {signal['direction']}:")
    print(f"  ID: {signal['id']}")
    print(f"  Status: {signal['status']}")
    print(f"  P&L: {signal['pnl_percent']}%")
    if 'metadata' in signal and signal['metadata']:
        print(f"  ✅ METADATA FOUND: {json.dumps(signal['metadata'], indent=4)}")
    else:
        print(f"  ❌ NO METADATA")
