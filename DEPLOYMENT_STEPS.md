# 🚀 Deployment Steps - Quick Reference

## ✅ What's Already Done:
- ✅ Cleanup complete (180MB saved)
- ✅ SSH keys secured (never pushed to GitHub)
- ✅ DB migration done (Supabase SQL Editor)
- ✅ Git committed (2 commits)
- ✅ **Pushed to GitHub** ✅

---

## 📋 Next Steps:

### **Step 1: Test Locally (Optional but Recommended)**

```bash
START_DASHBOARD.bat
```

**What to check:**
- ✓ Dashboard loads at http://localhost:8081
- ✓ No errors in console
- ✓ Can view signals page
- ✓ Marketing pages load

**Press Ctrl+C to stop when done**

---

### **Step 2: Deploy to Oracle** ⭐

```bash
DEPLOY_ORACLE.bat
```

**What it does:**
1. SSH to Oracle server
2. `git pull origin main` (gets your changes)
3. Stops old bot: `pkill -f "python.*main.py"`
4. Starts new bot: `python src/main.py`

**Expected output:**
```
Connecting to Oracle...
Pulling latest changes...
Stopping old bot...
Starting new bot...
✓ Deployment complete!
```

---

### **Step 3: Verify on Oracle**

**SSH to Oracle and check logs:**
```bash
ssh user@oracle-server
cd /path/to/CryptoPulse-Signals
tail -f dashboard.log
```

**Look for these lines:**
```
✅ Signal engine initialized
✅ Signal ranker initialized (max 3 signals/day)
✅ Smart stop validation active (all timeframes)
📊 Scanning for signals...
🎯 Found signal candidate: BTC/USDT 4h
📊 Signal candidate added: BTC/USDT (rank: 87.3/100)
```

**If you see errors:**
- Check `.env` file exists on Oracle
- Check Supabase connection
- Check Telegram bot tokens

---

### **Step 4: Monitor First Signals**

**Watch for new signals:**
```bash
# On Oracle:
tail -f dashboard.log | grep -E "Signal|ranking|published"
```

**Expected behavior:**
- Bot scans every 15 minutes
- Finds multiple signals throughout the day
- Ranks them by quality
- **Only publishes top 3** to Telegram

**Example day:**
```
09:00 - EUR/USDT 1h (rank: 87.3) → Published #1
11:30 - BTC/USDT 4h (rank: 89.1) → Published #2
14:00 - ETH/USDT 15m (rank: 78.5) → Published #3
16:30 - SOL/USDT 1h (rank: 88.7) → Held (already sent 3)
18:00 - AVAX/USDT 4h (rank: 82.1) → Held
```

---

## 🔍 Verification Checklist

### On Oracle Server:

- [ ] Bot is running: `ps aux | grep python.*main.py`
- [ ] No errors in logs: `tail -100 dashboard.log`
- [ ] Signal ranker active: `grep "ranker" dashboard.log`
- [ ] Stop validator active: `grep "stop validation" dashboard.log`
- [ ] Telegram bots connected: `grep "Telegram" dashboard.log`

### In Telegram:

- [ ] VIP channel receiving signals
- [ ] Free channel receiving signals (30min delay)
- [ ] Admin bot responding to commands
- [ ] VIP bot accepting signups

### In Dashboard:

- [ ] Navigate to: http://your-oracle-ip:8081
- [ ] Active signals showing
- [ ] Can manually close signals
- [ ] Marketing pages accessible

---

## 🚨 If Something Goes Wrong

### Bot Won't Start on Oracle

**Check:**
```bash
# 1. Python version
python --version  # Should be 3.10+

# 2. Dependencies installed
pip list | grep supabase

# 3. .env file exists
cat .env | head -5

# 4. Port not in use
netstat -tulpn | grep 8081
```

**Fix:**
```bash
# Install dependencies
pip install -r requirements.txt

# Check .env
nano .env  # Verify all tokens present

# Kill old process
pkill -f "python.*main.py"

# Restart
python src/main.py
```

---

### Signals Not Publishing

**Check:**
```bash
# 1. Signal ranker logs
grep "ranker" dashboard.log | tail -20

# 2. Telegram connection
grep "Telegram" dashboard.log | tail -20

# 3. Channel IDs
grep "CHANNEL_ID" .env
```

**Expected:**
```
Signal ranker initialized (max 3/day)
Signal candidate added: BTC/USDT (rank: 87.3)
✅ BTC/USDT approved for publishing (top 3)
📤 Publishing to VIP channel...
✓ Published to VIP channel
```

---

### Dashboard Not Loading

**Check:**
```bash
# 1. Dashboard server running
ps aux | grep dashboard_server

# 2. Port accessible
curl http://localhost:8081

# 3. Firewall rules
sudo ufw status
```

**Fix:**
```bash
# Restart dashboard
pkill -f dashboard_server
python src/admin/dashboard_server.py
```

---

## 📊 What Changed on Oracle

### New Features Active:

1. **Smart Stop Validation**
   - All timeframes: 15m, 1h, 4h, 1d
   - Validates against ATR, range, structure
   - Allows tight stops if structure supports

2. **Best 3 Signals Per Day**
   - Scans all day, ranks all signals
   - Only top 3 published
   - Quality over quantity

3. **Bug Fixes**
   - Limit order fill detection fixed
   - Duplicate messages prevented
   - Session detection fixed for daily signals
   - MEXC API timestamp sync fixed

### Files Changed:
- `src/analysis/timeframe_strategies.py` - Stop validation
- `src/engine/signal_engine.py` - Signal ranking
- `src/analysis/stop_validator.py` - NEW
- `src/engine/signal_ranker.py` - NEW
- Plus 50+ other improvements

---

## 🎯 Success Indicators

### First Hour After Deployment:

- ✅ Bot starts without errors
- ✅ Connects to Supabase
- ✅ Connects to Telegram
- ✅ Starts scanning symbols

### First Day:

- ✅ Finds 5-10+ signal candidates
- ✅ Publishes exactly 3 signals
- ✅ All stops validated
- ✅ Telegram messages sent
- ✅ Dashboard shows signals

### First Week:

- ✅ 21 signals sent (3/day × 7 days)
- ✅ 70%+ win rate
- ✅ No crashes or errors
- ✅ Users receiving signals
- ✅ Ready to market!

---

## 📞 Quick Commands Reference

### On Your Local Machine:

```bash
# Test dashboard
START_DASHBOARD.bat

# Deploy to Oracle
DEPLOY_ORACLE.bat

# Push changes
git push origin main
```

### On Oracle Server:

```bash
# Check bot status
ps aux | grep python.*main.py

# View logs
tail -f dashboard.log

# Restart bot
pkill -f "python.*main.py"
python src/main.py

# Check signals today
grep "Signal candidate" dashboard.log | grep $(date +%Y-%m-%d)
```

---

## ✅ Final Checklist

Before deploying:
- [x] Cleanup complete
- [x] Git committed
- [x] Pushed to GitHub
- [ ] Test dashboard locally (optional)
- [ ] Run DEPLOY_ORACLE.bat
- [ ] Verify logs on Oracle
- [ ] Check first signal published
- [ ] Monitor for 24 hours
- [ ] Start marketing!

---

## 🚀 You're Ready!

**Current Status:** ✅ Pushed to GitHub

**Next Command:** `DEPLOY_ORACLE.bat`

**After Deployment:** Monitor logs for 1 hour, then start marketing!

**Good luck with your launch! 🎉**
