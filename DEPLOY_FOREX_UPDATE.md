# 🚀 Deploy Forex Update to Oracle VM

## Quick Deploy Steps

### 1. SSH into Oracle VM
```bash
ssh -i "ssh-key-2026-05-20 (2).key" ubuntu@141.147.114.169
```

### 2. Pull Latest Code
```bash
cd CryptoPulse-Signals
git pull origin main
```

**You should see:**
```
Updating...
 src/main.py                           | 3 ++-
 src/engine/forex_signal_engine.py     | 45 +++++++++++++++++++++++++++++++++
 src/analysis/forex_adjustments.py     | 290 ++++++++++++++++++++++++++++++++++
 src/admin/dashboard_server.py         | 2 ++
 src/admin/static/index.html           | 8 +++++-
 5 files changed, 346 insertions(+), 2 deletions(-)
 create mode 100644 src/analysis/forex_adjustments.py
```

### 3. Restart Bot
```bash
# Stop existing bot
pkill -f "python -m src.main"

# Wait 2 seconds
sleep 2

# Start fresh
nohup python -m src.main > bot.log 2>&1 &

# Verify it's running
ps aux | grep python
```

### 4. Check Logs
```bash
tail -f bot.log
```

**Look for these lines:**
```
🚀 Initializing CRYPTO PULSE SIGNALS...
✅ Signal engine initialized
🌍 Initializing Forex signal engine...
✅ Forex signal engine initialized (11 pairs)
✅ Admin bot initialized
✅ Channel publisher initialized
🎯 Autopilot initialized
✅ CRYPTO PULSE SIGNALS is now running!

Scheduled jobs:
- scan_15m: Every 15 minutes
- scan_1h: Every hour
- scan_4h: Every 4 hours
- scan_daily: Daily at 00:05 UTC
- scan_forex: Every 2 hours ← NEW!
- check_signals: Every 2 minutes
```

### 5. Verify Forex Engine
```bash
grep -i "forex" bot.log | tail -20
```

**Expected output:**
```
🌍 Initializing Forex signal engine...
✅ Forex signal engine initialized (11 pairs)
🌍 FOREX: Every 2 hours — Forex pairs, commodities, indices
```

### 6. Wait for First Forex Scan
```bash
# Watch logs for Forex scan
tail -f bot.log | grep -i forex
```

**Next scan will happen at:**
- 00:10, 02:10, 04:10, 06:10, 08:10, 10:10, 12:10, 14:10, 16:10, 18:10, 20:10, 22:10 UTC

**When scan runs, you'll see:**
```
🌍 Scanning Forex markets (EUR/USD, XAUUSD, NAS100, etc.)...
🌍 EUR/USD: London session boost +3%
🌍 Forex SL adjustment: 0.0200 -> 0.0120 (EUR/USD)
🌍 Forex TP adjustment: 0.0300 -> 0.0210 (EUR/USD)
✅ Forex scan generated 2 signal(s)
💾 Forex signal saved: EUR/USD 1h
[APPROVE] on_signal_approved START for EUR/USD (status=approved, source=telegram)
[APPROVE] Signal EUR/USD is VIP-tier (≥85%) — publishing to VIP + teaser to FREE
✅ VIP publish OK for EUR/USD
✅ VIP teaser sent to free channel for EUR/USD
🎯 Starting autopilot tracking for EUR/USD
```

### 7. Check Telegram Channels

**VIP Channel:**
```
🌍 ⭐ ELITE SIGNAL ⭐

EUR/USD 🟢 LONG
Timeframe: 1h

⚡ MARKET ENTRY
💰 Entry: $1.08500
🛑 Stop Loss: $1.08200
🎯 Targets:
TP1: $1.08900
TP2: $1.09200
TP3: $1.09500

📊 Risk/Reward: 1:2.5
⚡ Confidence: 87.5%
```

**Free Channel:**
```
🌍 🔥 VIP SIGNAL ALERT 🔥

Our VIP members just received:
EUR/USD 🟢 LONG

⏰ Join VIP for instant access to all signals!
👉 /start
```

---

## ✅ Verification Checklist

After deploying, verify:

- [ ] Bot is running (`ps aux | grep python`)
- [ ] Logs show Forex engine initialized
- [ ] Forex scan scheduled every 2 hours
- [ ] No errors in logs (`grep -i error bot.log`)
- [ ] Dashboard accessible (http://141.147.114.169:8080)
- [ ] Telegram admin bot responding
- [ ] VIP channel active
- [ ] Free channel active

---

## 🧪 Manual Test (Optional)

If you want to test immediately without waiting for auto-scan:

### Via SSH (Command Line):
```bash
# Trigger manual Forex scan
curl -X POST http://localhost:8081/api/schedule/trigger \
  -H "Content-Type: application/json" \
  -d '{"job_type":"scan_forex"}'
```

### Via Dashboard (Browser):
1. Open: http://141.147.114.169:8080
2. Login with admin credentials
3. Go to: Signals tab
4. Click: "🌍 Scan Forex" button
5. Check Telegram channels for signals

---

## 🔍 Troubleshooting

### Issue: "Forex engine not initialized"
**Solution:**
```bash
# Check if forex_signal_engine exists
grep -i "forex_signal_engine" src/main.py

# Restart bot
pkill -f "python -m src.main"
nohup python -m src.main > bot.log 2>&1 &
```

### Issue: "API rate limit exceeded"
**Solution:**
```bash
# Check API usage
grep -i "rate limit\|api.*error" bot.log

# Reduce scan frequency if needed (edit src/main.py)
# Change: CronTrigger(hour='*/2') to CronTrigger(hour='*/4')
```

### Issue: "No Forex signals generated"
**Reasons:**
- Asian session (low liquidity for USD pairs)
- Weekend (Forex markets closed)
- No setups meeting 85% confidence threshold
- News blackout period (NFP, FOMC)

**Check:**
```bash
tail -f bot.log | grep -i "forex\|session"
```

### Issue: "Telegram not sending"
**Check:**
```bash
# Verify bot is NOT in dashboard-only mode
grep "dashboard-only\|DASHBOARD.*ONLY" bot.log

# Should see: "✅ Admin bot initialized" (NOT "Dashboard-only mode")
```

---

## 📊 Expected Behavior (First 24 Hours)

**Auto Scans:**
- 12 Forex scans (every 2 hours)
- 96 Crypto scans (15m, 1h, 4h, daily)

**Expected Signals:**
- 2-3 Crypto signals
- 1-2 Forex signals
- **Total: 3-5 signals/day**

**Telegram Activity:**
- VIP channel: 3-5 signals
- Free channel: 3-5 teasers
- Admin notifications: Approval confirmations, TP/SL hits

**API Usage:**
- Crypto: ~500 calls/day (CCXT)
- Forex: ~132 calls/day (Twelve Data)
- **Total: ~632 calls/day** (within limits)

---

## ✅ Success Indicators

**Within 2 Hours:**
- [ ] First Forex scan completed
- [ ] Logs show session adjustments
- [ ] No API errors

**Within 24 Hours:**
- [ ] 1-2 Forex signals generated
- [ ] Telegram notifications sent
- [ ] Autopilot tracking Forex signals
- [ ] Dashboard shows Forex badges (🌍 orange)

**Within 7 Days:**
- [ ] 10-15 Forex signals total
- [ ] Mix of EUR/USD, GBP/USD, XAUUSD, NAS100
- [ ] TP hits tracked and notified
- [ ] No API rate limit issues

---

## 🎯 Next Steps After Deploy

1. **Monitor for 2 hours** - Wait for first Forex scan
2. **Check Telegram** - Verify signals appear
3. **Test manual scan** - Click dashboard button
4. **Review logs daily** - Check for errors
5. **Adjust if needed** - Reduce scan frequency if API limits hit

**Your Forex signal system is now LIVE! 🚀**
