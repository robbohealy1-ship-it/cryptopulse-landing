# 🚨 URGENT: Oracle Bot Running OLD CODE

## Critical Discovery

Your EUR/USDT signal shows:
```
� Trade EURUSDT on MEXC (https://paste-any-link-here.com/) 🔷
```

**This placeholder URL does NOT exist in your current codebase!**

Your **Oracle instance is running OUTDATED CODE** from before the affiliate link system was implemented.

---

## Issue 1: MEXC Link Shows Placeholder (CRITICAL)

**Problem:** Signal shows `https://paste-any-link-here.com/` instead of your MEXC referral link.

**Root Cause:** Oracle bot hasn't been updated with latest code changes.

**Fix Required:**
```bash
# On Oracle instance:
cd /path/to/CryptoPulse-Signals
git pull origin main  # Pull latest code
pip install -r requirements.txt  # Update dependencies if needed

# Verify .env has:
AFFILIATE_EXCHANGE=custom
AFFILIATE_CUSTOM_URL=https://promote.mexc.com/r/RMWIMN3p5q

# Restart bot
pkill -f "python.*main.py"
python src/main.py
```

**Current Code (Correct):**
```python
# src/telegram_bot/channel_publisher.py:127-131
if exchange == 'custom':
    custom_url = settings.AFFILIATE_CUSTOM_URL
    if custom_url:
        return custom_url
    # Fallback if custom URL not set
    return "https://www.google.com/search?q=" + symbol.replace('/', '') + "+USDT+price"
```

If `AFFILIATE_CUSTOM_URL` is `None`, it should show Google search, NOT `paste-any-link-here.com`.

---

## Issue 2: Session Time Wrong for Daily Signals

**Problem:** EUR/USDT 1d signal sent at 18:37 UK (17:37 UTC) shows:
```
⏰ SESSION CONTEXT
Current session: Asian (0:00 UTC)
```

Should show: **London (17:00 UTC)**

**Root Cause:** Daily candles open at 00:00 UTC, so the session detector was using the candle's timestamp (midnight) instead of the current time when the signal was generated.

**Fix Applied:**
```python
# src/analysis/institutional_analyzer.py:460-464
# For daily/4h timeframes, use CURRENT time instead of candle timestamp
# (daily candles open at 00:00 UTC, which would always show "Asian" session)
if timeframe in ['1d', '4h']:
    from datetime import datetime as dt
    last_ts = dt.utcnow()
```

**Impact:** Daily and 4h signals will now show the ACTUAL session when the signal was generated, not the candle open time.

---

## Issue 3: OpenAI Usage in Signals

**Your Question:** "is openai being used for all messages to telegram inlcuding signals and apha?"

**Answer:** **NO** - OpenAI is NOT used for live trading signals.

**What Uses OpenAI:**
1. ✅ **Marketing content** (daily recaps, educational posts, engagement messages)
2. ✅ **Alpha play narratives** (fundamental analysis, catalyst descriptions)
3. ✅ **Welcome sequences** (personalized onboarding messages)

**What DOES NOT Use OpenAI:**
1. ❌ **Trading signals** - 100% algorithmic (institutional analyzer, volume profile, liquidity)
2. ❌ **TP/SL calculations** - Pure math based on ATR, structure, risk/reward
3. ❌ **Entry detection** - Code-based pattern recognition (BOS, CHoCH, FVG, etc.)
4. ❌ **Session detection** - Timezone-based logic (now fixed)

**Why the Session Was Wrong:**
- NOT because of AI
- Because the code was using candle timestamp (00:00 UTC for daily candles)
- Now fixed to use current UTC time for 4h/1d signals

---

## Deployment Checklist

### Step 1: Verify Oracle Code Version
```bash
# On Oracle:
cd /path/to/CryptoPulse-Signals
git log --oneline -1  # Should show recent commits
git status  # Should be clean
```

### Step 2: Pull Latest Changes
```bash
git pull origin main
```

### Step 3: Verify .env Configuration
```bash
# Check these are set:
cat .env | grep AFFILIATE
# Should show:
# AFFILIATE_EXCHANGE=custom
# AFFILIATE_CUSTOM_URL=https://promote.mexc.com/r/RMWIMN3p5q
```

### Step 4: Restart Bot
```bash
# Stop old process
pkill -f "python.*main.py"

# Start fresh
nohup python src/main.py > bot.log 2>&1 &

# Verify it started
tail -f bot.log
# Should see: "🚀 CryptoPulse Signals started"
```

### Step 5: Test Immediately
1. **Check next signal** - MEXC link should show your referral
2. **Check session** - Should show correct London/NY/Asian based on CURRENT time
3. **Check logs** - No more "paste-any-link" anywhere

---

## Files Modified (This Session)

1. ✅ `src/main.py` - Fixed SHORT limit fill logic
2. ✅ `src/admin/dashboard_server.py` - Duplicate close prevention
3. ✅ `src/marketing/community_engagement.py` - VIP bot link
4. ✅ `src/exchange/mexc_client.py` - MEXC time sync
5. ✅ `src/analysis/institutional_analyzer.py` - Session detection for 4h/1d

---

## Expected Results After Deployment

✅ **MEXC Link:** `https://promote.mexc.com/r/RMWIMN3p5q` in all signals  
✅ **Session:** Shows London (17:00 UTC) when sent at 17:37 UTC  
✅ **ZEC/USDT:** Pending SHORT limit activates (price way above entry)  
✅ **No duplicate closes:** Only 1 message per trade  
✅ **MEXC API:** No more timestamp errors  

---

## Why This Happened

**Oracle bot was never updated after these features were added:**
- Affiliate link system (replaced placeholder)
- Session detection improvements
- Limit order retrospective fills
- MEXC time sync

**Solution:** Always deploy to Oracle after making changes in this workspace.

---

## Next Steps

1. **Deploy to Oracle NOW** - Your live signals are showing broken links
2. **Set up auto-deploy** - So Oracle stays in sync with your dev workspace
3. **Monitor first signal** - Verify MEXC link and session are correct

---

**Status:** 🔴 URGENT - Oracle needs immediate code update
