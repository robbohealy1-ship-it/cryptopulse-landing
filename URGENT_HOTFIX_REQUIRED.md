# 🚨 URGENT HOTFIX REQUIRED - June 14, 2026 20:56 UTC

## **CRITICAL BUG FOUND IN PRODUCTION**

Your Oracle deployment logs show **BNB/USDT SL triggering in an infinite loop**:

```
🛑 SL HIT: BNB/USDT LONG at 602.980000 (SL was 605.230000), P&L: -0.61%
🛑 SL HIT: BNB/USDT LONG at 603.030000 (SL was 605.230000), P&L: -0.60%
🛑 SL HIT: BNB/USDT LONG at 603.140000 (SL was 605.230000), P&L: -0.58%
🛑 SL HIT: BNB/USDT LONG at 603.280000 (SL was 605.230000), P&L: -0.56%
```

---

## **ROOT CAUSE**

The `update_signal_result` function was trying to update **performance tracking columns** that **don't exist** in your Supabase database schema:
- `max_favorable_excursion`
- `max_adverse_excursion`
- `max_drawdown_percent`
- `duration_minutes`
- `entry_slippage_percent`
- `exit_slippage_percent`

**Result:** Database update **FAILED**, signal status remained **"active"**, and the signal was re-tracked every minute, triggering SL repeatedly.

---

## **THE FIX**

Modified `src/database/supabase_client.py` to **only update core fields** that exist in the database:
- ✅ `status` (critical - marks signal as closed)
- ✅ `actual_exit`
- ✅ `pnl_percent`
- ✅ `closed_at`
- ✅ `tp_level` (if applicable)

**Skipped all optional performance tracking fields** until you add them to the database schema.

---

## **DEPLOY HOTFIX NOW**

```bash
# SSH into Oracle
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169

# Navigate to project
cd CryptoPulse-Signals

# Pull latest fix
git pull

# Kill running bot
pkill -f main.py

# Restart bot
nohup python3 src/main.py > bot.log 2>&1 &

# Monitor logs
tail -f bot.log
```

---

## **WHAT TO LOOK FOR**

### **✅ SUCCESS:**
```
✅ Signal d3c64e63-7e42-476a-9803-04d77b873c6e result updated: closed P&L=-0.61%
```

### **❌ BEFORE (BROKEN):**
```
ERROR | Error updating signal result: {'code': 'PGRST204', 'message': "Could not find the 'max_favorable_excursion' column"}
```

---

## **SECOND ISSUE: XAU/USD**

```
⚠️ Scanner returned 0 price for XAU/USD — skipping SL/TP check (signal at risk!)
```

**Problem:** XAU/USD (with slash) is a **forex symbol**, but it's marked as **CRYPTO** in your database.

**Solutions:**

### **Option A: Change Symbol to XAUUSDT (Recommended)**
If you're trading Binance gold perpetual futures:
1. Edit the signal in your dashboard
2. Change symbol from `XAU/USD` to `XAUUSDT` (no slash)
3. This is the Binance futures contract and will track properly

### **Option B: Mark as FOREX**
If it's real forex gold (not Binance):
1. Edit the signal in your dashboard
2. Change `market_type` from `CRYPTO` to `FOREX`
3. The forex client will handle price fetching

**Note:** Real forex XAU/USD won't be tracked by autopilot because Binance scanner doesn't support it. You need to use XAUUSDT for Binance futures.

---

## **SUMMARY OF ALL FIXES**

### **1. Portfolio Summary Frequency** ✅
- **Before:** Once per hour (60 times/day)
- **After:** Once per day at 8:00 AM UTC

### **2. Missing Trades in Summary** ✅
- **Before:** Only 6 of 9 trades tracked
- **After:** All 9 trades tracked (fixed forex detection)

### **3. SL Re-triggering Loop** ✅ (THIS HOTFIX)
- **Before:** BNB/USDT SL triggered every minute in infinite loop
- **After:** Signal properly marked as "closed" after SL hit

### **4. Database Update Failures** ✅ (THIS HOTFIX)
- **Before:** Update failed due to missing columns, signal stayed "active"
- **After:** Only updates core fields, signal properly closed

---

## **NEXT STEPS (OPTIONAL - NOT URGENT)**

To enable full performance tracking, add these columns to your Supabase `signals` table:

```sql
ALTER TABLE signals ADD COLUMN IF NOT EXISTS max_favorable_excursion FLOAT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS max_adverse_excursion FLOAT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS max_drawdown_percent FLOAT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS duration_minutes FLOAT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS entry_slippage_percent FLOAT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS exit_slippage_percent FLOAT;
```

Then uncomment the performance tracking fields in `src/database/supabase_client.py` lines 727-738.

---

## **VERIFICATION**

After deploying the hotfix, verify:

1. ✅ BNB/USDT SL only triggers **once**
2. ✅ Signal status updates to **"closed"** in database
3. ✅ No more duplicate SL notifications
4. ✅ No more `PGRST204` database errors
5. ✅ Portfolio summary sent **once per day** at 8:00 AM UTC

---

**Commit:** `5f6eba1`  
**Status:** ✅ Pushed to GitHub  
**Priority:** 🚨 **CRITICAL - DEPLOY IMMEDIATELY**

The infinite SL loop is costing you money (repeated notifications, database load, potential duplicate trades).
