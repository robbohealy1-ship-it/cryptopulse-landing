# 🚀 PRODUCTION DEPLOYMENT GUIDE

**Complete step-by-step guide to deploy CryptoPulse to production**

---

## ⚠️ PRE-DEPLOYMENT CHECKLIST

Before deploying, complete these steps:

### **1. Run Production Audit**
```bash
python scripts/production_audit.py
```

**Expected Output:**
```
✅ Passed: 30+
⚠️  Warnings: 0-5
❌ Issues: 0

🎉 NO CRITICAL ISSUES FOUND!
✅ SYSTEM IS PRODUCTION READY!
```

**If issues found:** Fix them before proceeding.

---

### **2. Run Conviction Engine Tests**
```bash
python scripts/test_conviction_engine.py
```

**Expected Output:**
```
📊 TEST RESULTS
   Passed: 9/9
   Failed: 0/9
   Success Rate: 100.0%

🎉 ALL TESTS PASSED! Ready for production.
```

**If tests fail:** Debug and fix before proceeding.

---

### **3. Seed Research Centre (Optional)**
```bash
python scripts/seed_research_centre.py
```

**Expected Output:**
```
🎉 Research Centre seeding complete!
   Created: 8
   Skipped: 0
   Total: 8
```

**Note:** Only run once. Skip if already seeded.

---

## 🔧 CONFIGURATION CHECK

### **1. Environment Variables (.env)**

Verify these settings:

```bash
# Signal Mode
SIGNAL_MODE=strict  # strict/balanced/aggressive

# Volume Threshold
MIN_DAILY_VOLUME_USD=5000000  # $5M

# Confidence
MIN_CONFIDENCE_SCORE=85

# Database
SUPABASE_URL=your_url
SUPABASE_KEY=your_key

# Telegram
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
```

### **2. Config.py Settings**

Check `src/config.py`:

```python
SIGNAL_MODE: str = "strict"  # Default mode
MIN_DAILY_VOLUME_USD: float = 5000000  # $5M threshold
MIN_CONFIDENCE_SCORE: int = 85
```

---

## 🧪 LOCAL TESTING

### **Step 1: Start Dashboard**

```bash
START_DASHBOARD.bat
```

**Wait for:**
```
🎯 Conviction Engine initialized - Multi-factor scoring active
🎛️  Admin Dashboard starting on http://localhost:8080
```

### **Step 2: Test API Endpoints**

Open browser or use curl:

```bash
# Test conviction mode
curl http://localhost:8080/api/conviction/mode

# Expected response:
{
  "mode": "strict",
  "thresholds": {...},
  "current_threshold": 85
}
```

```bash
# Test conviction stats
curl http://localhost:8080/api/conviction/stats

# Expected response:
{
  "total_signals_7d": 0,
  "signals_with_conviction": 0,
  "tier_distribution": {...},
  "current_mode": "strict"
}
```

### **Step 3: Wait for Signal Generation**

Monitor logs for:

```
🎯 Calculating conviction for BTC/USDT LONG...
🎯 BTC/USDT Conviction: 92.5/100 (ELITE) | Old Confidence: 88.5%
🧲 BTC/USDT: 1 magnets nearby | Multiplier: 1.15x
✅ BTC/USDT approved for publishing (top 3 signal)
```

### **Step 4: Test Mode Switching**

```bash
# Switch to balanced mode
curl -X POST http://localhost:8080/api/conviction/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "balanced"}'

# Expected response:
{
  "success": true,
  "mode": "balanced",
  "threshold": 75,
  "message": "Signal mode set to BALANCED"
}
```

### **Step 5: Verify Logs**

Check for:
- ✅ No Python errors
- ✅ Conviction scores in logs
- ✅ Magnet detection working
- ✅ Trap detection working
- ✅ Mode switching works

---

## 🚀 PRODUCTION DEPLOYMENT

### **Option A: Deploy to Oracle (Live Bot)**

```bash
DEPLOY_ORACLE.bat
```

**This will:**
1. Commit all changes to git
2. Push to Oracle instance
3. Oracle automatically restarts with new code
4. Conviction engine activates on Oracle

### **Option B: Manual Deployment**

If `DEPLOY_ORACLE.bat` doesn't exist:

```bash
# 1. Commit changes
git add .
git commit -m "Deploy conviction engine v1.0"

# 2. Push to Oracle
git push oracle main

# 3. SSH to Oracle and restart
ssh oracle
cd /path/to/CryptoPulse-Signals
git pull
pm2 restart cryptopulse
```

---

## 📊 POST-DEPLOYMENT MONITORING

### **Step 1: Check Oracle Logs**

```bash
# If using PM2
pm2 logs cryptopulse

# Or check log files
tail -f logs/cryptopulse.log
```

**Look for:**
```
🎯 Conviction Engine initialized - Multi-factor scoring active
🎯 Calculating conviction for BTC/USDT LONG...
🎯 BTC/USDT Conviction: 92.5/100 (ELITE)
```

### **Step 2: Monitor First Signals**

Watch for:
- ✅ Conviction scores appear (0-100)
- ✅ Tier classification (ELITE/VIP/WATCHLIST)
- ✅ Per-engine breakdown in logs
- ✅ Magnet detection messages
- ✅ No Python errors

### **Step 3: Check Dashboard**

Visit dashboard and verify:
- ✅ Signals show conviction scores
- ✅ API endpoints work
- ✅ Mode switching works
- ✅ Stats display correctly

### **Step 4: Monitor for 24-48 Hours**

Track:
- Signal quality (conviction scores)
- Number of signals generated
- User engagement
- Any errors or warnings

---

## 🐛 TROUBLESHOOTING

### **Issue: Conviction engine not initializing**

**Symptoms:**
```
❌ Error: No module named 'src.conviction'
```

**Fix:**
```bash
# Check __init__.py exists
ls src/conviction/__init__.py

# Restart dashboard
START_DASHBOARD.bat
```

---

### **Issue: Conviction scores not appearing**

**Symptoms:**
- Signals generated but no conviction_score
- Logs show old confidence only

**Fix:**
```python
# Check signal_engine.py has conviction integration
grep "conviction_engine" src/engine/signal_engine.py

# Should see:
self.conviction_engine = ConvictionEngine()
```

---

### **Issue: API endpoints return 404**

**Symptoms:**
```
GET /api/conviction/mode → 404 Not Found
```

**Fix:**
```bash
# Check dashboard_server.py has endpoints
grep "get_conviction_mode" src/admin/dashboard_server.py

# Restart dashboard
START_DASHBOARD.bat
```

---

### **Issue: Mode switching doesn't work**

**Symptoms:**
- Mode changes but signals still use old threshold

**Fix:**
```python
# Check signal_engine.py reads signal_mode
grep "self.signal_mode" src/engine/signal_engine.py

# Restart to reload config
```

---

### **Issue: Database errors**

**Symptoms:**
```
❌ Error saving signal: column "conviction_score" does not exist
```

**Fix:**
```sql
-- Add missing columns to signals table
ALTER TABLE signals ADD COLUMN conviction_score FLOAT;
ALTER TABLE signals ADD COLUMN conviction_tier TEXT;
ALTER TABLE signals ADD COLUMN conviction_breakdown JSONB;
```

---

## 📈 PERFORMANCE OPTIMIZATION

### **1. Monitor Conviction Engine Performance**

```python
# Add timing logs
import time

start = time.time()
breakdown = await conviction_engine.calculate_conviction(df, symbol, direction)
elapsed = time.time() - start

logger.info(f"Conviction calculation took {elapsed:.2f}s")
```

**Expected:** < 2 seconds per calculation

---

### **2. Optimize API Calls**

If sentiment/news engines are slow:

```python
# Add timeouts
async with asyncio.timeout(5):
    sentiment_score = await sentiment_engine.calculate(...)
```

---

### **3. Cache Frequently Used Data**

```python
# Cache market data
from functools import lru_cache

@lru_cache(maxsize=100)
def get_market_info(symbol):
    # Cached for 30 seconds
    pass
```

---

## 🔐 SECURITY CHECKLIST

- [ ] API keys not hardcoded
- [ ] .env file not committed to git
- [ ] Database credentials secure
- [ ] Admin endpoints require authentication
- [ ] Rate limiting enabled
- [ ] HTTPS enabled (production)
- [ ] Logs don't expose sensitive data

---

## 📊 SUCCESS METRICS

### **Week 1: Baseline**
- Track conviction score distribution
- Monitor signal count per mode
- Measure win rate
- Track user engagement

### **Week 2-4: Optimization**
- Adjust mode thresholds if needed
- Fine-tune engine weights
- Optimize API performance
- Gather user feedback

### **Month 2+: Scale**
- Add more pairs (100+)
- Implement DEX momentum engine
- Add on-chain data (if APIs available)
- Build dashboard UI

---

## 🎯 ROLLBACK PLAN

If critical issues arise:

### **1. Immediate Rollback**

```bash
# Revert to previous version
git revert HEAD
git push oracle main

# Or restore from backup
git checkout <previous-commit>
git push oracle main --force
```

### **2. Disable Conviction Engine**

```python
# In signal_engine.py, comment out:
# conviction_breakdown = await self.conviction_engine.calculate_conviction(...)

# Use old confidence only
conviction_score = confidence
conviction_tier = 'UNKNOWN'
conviction_breakdown = None
```

### **3. Switch to Safe Mode**

```bash
# Set to strict mode (highest quality)
SIGNAL_MODE=strict

# Increase thresholds
MIN_CONFIDENCE_SCORE=90
```

---

## 📞 SUPPORT

### **Logs Location**
```
logs/cryptopulse.log
logs/conviction_engine.log
```

### **Debug Mode**
```bash
# Enable debug logging
LOG_LEVEL=DEBUG

# Restart
START_DASHBOARD.bat
```

### **Health Check**
```bash
# Quick health check
python scripts/production_audit.py
```

---

## ✅ FINAL CHECKLIST

Before going live:

- [ ] Production audit passed
- [ ] All tests passed
- [ ] Research centre seeded (optional)
- [ ] Local testing complete
- [ ] API endpoints tested
- [ ] Mode switching tested
- [ ] Logs look clean
- [ ] No errors in dashboard
- [ ] Backup created
- [ ] Rollback plan ready
- [ ] Monitoring set up
- [ ] Team notified

---

## 🎉 YOU'RE READY!

Once all checks pass:

1. ✅ Run `DEPLOY_ORACLE.bat`
2. ✅ Monitor logs for 1 hour
3. ✅ Check first signals
4. ✅ Verify conviction scores
5. ✅ Celebrate! 🚀

---

**Questions? Issues? Check logs first, then review troubleshooting section.**

**Good luck with your deployment!** 🎯
