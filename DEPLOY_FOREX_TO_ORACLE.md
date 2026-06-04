# 🚀 Deploy Forex System to Oracle VM

## Quick 3-Step Deployment

### ✅ Step 1: Add Forex API Keys to Oracle VM
```bash
# Run this script:
ADD_FOREX_KEYS_TO_ORACLE.bat
```

**What it does:**
- Reads your local `.env` file
- Extracts `ALPHA_VANTAGE_API_KEY` and `TWELVE_DATA_API_KEY`
- Adds them to Oracle VM's `.env` file
- Verifies they were added correctly

**Expected output:**
```
Found API keys:
  ALPHA_VANTAGE: 110e7893da...
  TWELVE_DATA: 110e7893da...

Connecting to Oracle VM...
ALPHA_VANTAGE_API_KEY=***HIDDEN***
TWELVE_DATA_API_KEY=***HIDDEN***

✅ Forex API keys added to Oracle VM!
```

---

### ✅ Step 2: Deploy Code to Oracle VM
```bash
# Run this script:
DEPLOY_ORACLE.bat
```

**What it does:**
- Stops old bot
- Uploads latest code (including Forex engine)
- Installs dependencies
- Starts new bot
- Shows bot status

**Expected output:**
```
[1/5] Stopping bot on Oracle...
[2/5] Uploading latest code...
[3/5] Removing stale files on server...
[4/5] Running deploy script on server...
[5/5] Checking bot status...

✅ Deploy attempt complete.
```

---

### ✅ Step 3: Verify Forex System is Running
```bash
# Check logs on Oracle VM
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "tail -50 /home/opc/CryptoPulse-Signals/bot.log | grep -i forex"
```

**Expected output:**
```
Forex API Keys - Alpha Vantage: ✅ SET, Twelve Data: ✅ SET
✅ Twelve Data API key validated successfully
✅ Forex client initialized with 11 symbols
✅ Forex signal engine initialized (11 pairs)
```

---

## 📊 What Happens After Deployment

### Automatic Forex Scans (Every 2 Hours)
```
00:10 UTC - Forex scan
02:10 UTC - Forex scan
04:10 UTC - Forex scan
06:10 UTC - Forex scan (London open - HIGH QUALITY)
08:10 UTC - Forex scan
10:10 UTC - Forex scan
12:10 UTC - Forex scan (London-NY overlap - HIGHEST QUALITY)
14:10 UTC - Forex scan
16:10 UTC - Forex scan
18:10 UTC - Forex scan
20:10 UTC - Forex scan
22:10 UTC - Forex scan
```

### Signal Flow
```
1. Forex scan finds EUR/USD LONG (87% confidence)
2. Auto-approved (Forex signals auto-approve like crypto)
3. Published to VIP Telegram channel
4. Teaser sent to Free channel (10 min delay)
5. Autopilot tracking started
6. TP/SL notifications sent when hit
```

---

## 🔍 Monitoring & Troubleshooting

### View Live Logs
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169
cd /home/opc/CryptoPulse-Signals
tail -f bot.log
```

### Check Forex Scan Logs
```bash
tail -f bot.log | grep -i forex
```

### Manually Trigger Forex Scan (via Dashboard)
1. Open dashboard: http://141.147.114.169:8080
2. Login with admin credentials
3. Click "🌍 Scan Forex"
4. Check Telegram for signals

### Check Bot Status
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "ps aux | grep 'src.main'"
```

---

## ⚠️ Common Issues

### Issue 1: API Keys Not Found
**Symptom:**
```
Forex API Keys - Alpha Vantage: ❌ DEMO/MISSING, Twelve Data: ❌ DEMO/MISSING
```

**Fix:**
```bash
# Re-run Step 1
ADD_FOREX_KEYS_TO_ORACLE.bat
```

### Issue 2: HTTP 401 Errors
**Symptom:**
```
ERROR: Forex API HTTP 401 for EUR/USD
```

**Fix:**
- API key is invalid or not activated
- Get new key at https://twelvedata.com/pricing
- Update local `.env` file
- Re-run Step 1

### Issue 3: HTTP 429 Errors
**Symptom:**
```
ERROR: Forex API HTTP 429 for USD/JPY
```

**Fix:**
- Rate limit exceeded (normal if scanning too frequently)
- Wait 1 minute
- Try manual scan again
- Automatic scans every 2 hours avoid this

### Issue 4: No Signals Generated
**Symptom:**
```
No Forex signals found this scan
```

**Fix:**
- This is NORMAL! Forex signals require 85%+ confidence
- Not every scan will find setups
- Best times: London open (06:00-08:00 UTC), London-NY overlap (12:00-14:00 UTC)
- Try manual scan during high-volatility sessions

---

## 📈 Expected Performance

### Signal Frequency
- **Crypto:** 1-3 signals/day (existing)
- **Forex:** 1-2 signals/day (new)
- **Total:** 2-5 signals/day (combined)

### Best Forex Scan Times
1. **06:00-08:00 UTC** - London open (highest volatility)
2. **12:00-14:00 UTC** - London-NY overlap (best setups)
3. **13:30-15:00 UTC** - NY session (good volatility)

### Forex Pairs Coverage
- **Major Pairs:** EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, NZD/USD
- **Commodities:** XAU/USD (Gold), XAG/USD (Silver)
- **Indices:** NAS100 (NASDAQ), US30 (Dow), SPX500 (S&P 500)

---

## ✅ Deployment Checklist

- [ ] Run `ADD_FOREX_KEYS_TO_ORACLE.bat`
- [ ] Verify API keys added (see "***HIDDEN***" in output)
- [ ] Run `DEPLOY_ORACLE.bat`
- [ ] Wait for deployment to complete
- [ ] SSH into Oracle VM and check logs
- [ ] Verify Forex engine initialized
- [ ] Wait for next 2-hour scan OR trigger manual scan
- [ ] Check Telegram for Forex signals

---

## 🎯 Quick Commands Reference

```bash
# Add API keys
ADD_FOREX_KEYS_TO_ORACLE.bat

# Deploy code
DEPLOY_ORACLE.bat

# Check logs
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "tail -50 /home/opc/CryptoPulse-Signals/bot.log"

# Monitor Forex scans
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "tail -f /home/opc/CryptoPulse-Signals/bot.log | grep -i forex"

# Restart bot manually
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "pkill -f 'src.main' && cd /home/opc/CryptoPulse-Signals && nohup python3 -m src.main > bot.log 2>&1 &"
```

---

**Ready to deploy? Run `ADD_FOREX_KEYS_TO_ORACLE.bat` now! 🚀**
