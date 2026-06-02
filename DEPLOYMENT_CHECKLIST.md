# 🚀 Oracle Deployment Checklist

## Pre-Deployment Steps

### 1. Database Migration
**CRITICAL: Run this SQL in Supabase SQL Editor BEFORE deploying:**

```sql
-- Add missing columns to alpha_plays table
ALTER TABLE alpha_plays
ADD COLUMN IF NOT EXISTS candidate_data JSONB,
ADD COLUMN IF NOT EXISTS play_type TEXT DEFAULT 'day_trade',
ADD COLUMN IF NOT EXISTS chain TEXT DEFAULT 'sol',
ADD COLUMN IF NOT EXISTS entry_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS stop_loss NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS take_profit_1 NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS take_profit_2 NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS position_size TEXT DEFAULT '2-5%',
ADD COLUMN IF NOT EXISTS current_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS current_pnl NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS highest_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS lowest_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS tp1_hit_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS tp2_hit_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sl_hit_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Ensure created_at has a default
ALTER TABLE alpha_plays
ALTER COLUMN created_at SET DEFAULT NOW();

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_alpha_plays_status ON alpha_plays(status);
CREATE INDEX IF NOT EXISTS idx_alpha_plays_symbol ON alpha_plays(symbol);
```

### 2. Environment Variables Check
Verify these are set in Oracle `.env`:

```bash
# VIP Bot Username (replaces generic landing page links)
TELEGRAM_VIP_BOT_USERNAME=YourVIPBotUsername

# MEXC Affiliate Link
AFFILIATE_EXCHANGE=custom
AFFILIATE_CUSTOM_URL=https://promote.mexc.com/r/RMWIMN3p5q

# Multi-Wallet Portfolio Tracking
ETH_WALLET_ADDRESS=0x...
SOL_WALLET_ADDRESS=...
BTC_WALLET_ADDRESS=...

# Portfolio Visibility Toggle
SHOW_PORTFOLIO_IN_ALPHA=true
ENABLE_PUBLIC_PORTFOLIO=false
```

### 3. Code Changes Summary

#### ✅ Fixed Issues:
1. **SSH Deploy Script** - Fixed malformed `StrictHostKeyChecking` argument
2. **UNKNOWN Symbols** - Added token enrichment BEFORE publishing to Telegram
3. **Generic URLs** - Replaced landing page links with VIP bot username
4. **-95% P&L Bug** - Refresh price before generating trade parameters
5. **Database Schema** - Added missing `chain` column migration
6. **Portfolio Multi-Wallet** - Support for ETH, SOL, BTC addresses
7. **Portfolio Toggle** - Hide/unhide portfolio section in admin dashboard

#### 📝 Modified Files:
- `DEPLOY_ORACLE.bat` - Fixed SSH argument quoting
- `src/admin/dashboard_server.py` - Added enrichment before publish
- `src/alpha_plays/alpha_engine.py` - Refresh price on approval
- `src/marketing/community_engagement.py` - Use VIP bot username
- `migrations/fix_alpha_plays_columns.sql` - Added chain column

## Deployment Execution

### Step 1: Run Database Migration
```bash
# Login to Supabase Dashboard
# Navigate to SQL Editor
# Paste and run the migration SQL from above
# Verify no errors
```

### Step 2: Deploy Code to Oracle
```bash
# From Windows local machine:
cd c:\CascadeProjects\windsurf-project\CryptoPulse-Signals
.\DEPLOY_ORACLE.bat
```

### Step 3: Monitor Deployment
Watch for these success indicators:
```
[1/5] Stopping bot on Oracle...
  All bot processes terminated.
[2/5] Uploading latest code...
[3/5] Removing stale files on server...
[4/5] Running deploy script on server...
[5/5] Checking bot status...
  1  <-- Bot is running
```

### Step 4: Verify Bot Logs
```bash
ssh -i "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\ssh-key-2026-05-20 (2).key" ubuntu@141.147.114.169 "tail -50 /home/ubuntu/cryptopulse/bot.log"
```

**Look for:**
- ✅ No "UNKNOWN" symbols in alpha plays
- ✅ No generic "cryptopulsesignals.com" URLs
- ✅ Correct VIP bot username in messages
- ✅ No database schema errors for 'chain' column
- ✅ Correct P&L calculations (not -95%)

## Post-Deployment Verification

### 1. Test Alpha Plays Engine
```bash
# Check alpha discovery is working
# Look for: "🔍 Alpha discovery started"
# Verify: Token enrichment happens before publish
# Confirm: No "UNKNOWN" symbols in Telegram messages
```

### 2. Test Signal Engine
```bash
# Verify daily signals are generated
# Check session time is correct (not always "Asian")
# Confirm limit order fills are detected
```

### 3. Test Admin Dashboard
```bash
# Access: http://141.147.114.169:8000
# Login with credentials
# Navigate to Settings tab
# Verify portfolio toggle controls are present
# Test toggling portfolio visibility
```

### 4. Test Telegram Messages
**VIP Channel:**
- Alpha plays show real token symbols (not UNKNOWN)
- VIP bot username link is present (not generic URL)
- MEXC affiliate link is correct
- P&L calculations are accurate

**Free Channel:**
- Teasers show VIP bot username
- No generic landing page links
- Marketing messages use VIP bot username

## Rollback Procedure

If deployment fails:

### 1. Stop New Bot
```bash
ssh -i "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\ssh-key-2026-05-20 (2).key" ubuntu@141.147.114.169 "pkill -9 -f 'python3 -m src.main'"
```

### 2. Restore Previous Code
```bash
ssh -i "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\ssh-key-2026-05-20 (2).key" ubuntu@141.147.114.169 "cd /home/ubuntu/cryptopulse && git checkout HEAD~1"
```

### 3. Restart Bot
```bash
ssh -i "c:\CascadeProjects\windsurf-project\CryptoPulse-Signals\ssh-key-2026-05-20 (2).key" ubuntu@141.147.114.169 "cd /home/ubuntu/cryptopulse && nohup python3 -m src.main > bot.log 2>&1 &"
```

## Known Issues & Workarounds

### Issue: API Rate Limits
**Symptom:** DexScreener/GeckoTerminal API errors
**Workaround:** Reduce scan frequency or implement caching

### Issue: cTrader/MEXC API Errors
**Symptom:** 400 Bad Request errors in logs
**Workaround:** Update API credentials in `.env` or disable unused exchanges

### Issue: Telegram Rate Limits
**Symptom:** "Too Many Requests" errors
**Workaround:** Reduce message frequency or implement message queuing

## Success Criteria

Deployment is successful when:

- ✅ Bot starts without errors
- ✅ No database schema errors in logs
- ✅ Alpha plays show real token symbols
- ✅ VIP bot username appears in all messages
- ✅ MEXC affiliate link is correct
- ✅ P&L calculations are accurate
- ✅ Portfolio toggle works in admin dashboard
- ✅ No generic placeholder URLs in Telegram
- ✅ Signal engine generates daily signals
- ✅ Alpha engine discovers and tracks plays

## Next Steps After Deployment

1. **Monitor for 24 hours** - Watch logs for errors
2. **Test alpha approval flow** - Approve a pending play and verify Telegram message
3. **Verify portfolio tracking** - Check multi-wallet support
4. **Test public portfolio page** - Enable and verify read-only access
5. **Plan AI enhancements** - Review FIXES_APPLIED.md for next iteration

---

**Last Updated:** 2025-01-XX
**Deployment Version:** v2.1.0
**Critical Fixes:** SSH args, UNKNOWN symbols, -95% P&L, chain column, generic URLs
