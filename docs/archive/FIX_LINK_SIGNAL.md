# 🔧 FIX: LINK Signal Not Showing in Active Trades

## ❌ PROBLEM IDENTIFIED

Your LINK SHORT signal is not showing in the Active Trades tab because:

1. **The signal might not be in the database** (never saved or deleted)
2. **OR the signal has a different status** (pending, rejected, closed)
3. **OR the database query was too restrictive** (only looked for 'active', not 'approved')

---

## ✅ FIX APPLIED

I've updated the database query to include **both** `'active'` and `'approved'` status:

**File:** `src/database/supabase_client.py` line 113-125

```python
async def get_active_signals(self) -> List[TradingSignal]:
    """Get all active/approved signals that are being tracked (not closed or rejected)"""
    try:
        # Include both 'active' and 'approved' status - these are running trades
        result = self.client.table('signals').select('*')\
            .in_('status', ['active', 'approved'])\
            .execute()
        
        return [self._dict_to_signal(data) for data in result.data]
        
    except Exception as e:
        logger.error(f"Error getting active signals: {e}")
        return []
```

---

## 🔍 TO VERIFY IF LINK SIGNAL EXISTS

### **Option 1: Check Supabase Dashboard**

1. Go to your Supabase project dashboard
2. Click "Table Editor"
3. Select `signals` table
4. Look for LINK/USDT or LINKUSDT
5. Check the `status` column

**Expected:**
- Symbol: `LINK/USDT` or `LINKUSDT`
- Direction: `SHORT`
- Status: `approved` or `active`
- Entry: ~$9.78

### **Option 2: Check Through Dashboard**

1. Open `http://localhost:8081/`
2. Go to **History** tab
3. Look for LINK signal there
4. Check what status it has

---

## 🎯 MOST LIKELY SCENARIOS

### **Scenario 1: Signal Was Never Approved**
**Symptom:** Signal is in "Pending" tab
**Solution:** 
1. Go to Signals → Pending
2. Find LINK SHORT
3. Click "Approve"
4. It will appear in Active Trades

### **Scenario 2: Signal Was Rejected**
**Symptom:** Signal not in Pending or Active
**Solution:**
1. Create new manual signal
2. Go to Signals → Create Signal
3. Fill in LINK SHORT details
4. Submit
5. Approve it

### **Scenario 3: Signal Expired**
**Symptom:** Signal disappeared
**Solution:**
1. Signals expire after 30 minutes if not approved
2. Create new manual signal (see Scenario 2)

### **Scenario 4: Database Connection Issue**
**Symptom:** Nothing shows anywhere
**Solution:**
1. Check Supabase credentials in `.env`
2. Restart dashboard
3. Check logs for errors

---

## 🚀 QUICK FIX: Create Manual LINK SHORT Signal

If the original signal is lost, create it manually:

### **Step 1: Open Dashboard**
```
http://localhost:8081/
```

### **Step 2: Go to Create Signal**
- Click **Signals** tab
- Click **Create Signal** button

### **Step 3: Fill in Details**

```
Symbol: LINK/USDT
Direction: SHORT
Timeframe: 4h
Confidence: 96.1
Risk/Reward: 3.0

Entry Price: 9.77865
Stop Loss: 10.82385

Take Profit 1: 6.64305
Take Profit 2: 5.07525
Take Profit 3: 3.50745

Notes: Manual LINK SHORT - 4h timeframe
```

### **Step 4: Submit**
- Click "Create Signal"
- Signal will be auto-approved
- Check Active Trades tab
- Should appear immediately!

---

## ✅ AFTER RESTART

Once you restart the dashboard with the fix:

```bash
# Stop current dashboard (Ctrl+C)
# Restart
start_dashboard.bat
```

**Then:**

1. Open `http://localhost:8081/`
2. Go to **Signals → Active Trades**
3. If LINK signal exists in database with status `approved` or `active`, it will show
4. If not, create it manually (see above)

---

## 🔄 WHAT CHANGED

### **Before:**
```python
# Only looked for status='active'
result = self.client.table('signals').select('*').eq('status', 'active').execute()
```

### **After:**
```python
# Now looks for BOTH 'active' AND 'approved'
result = self.client.table('signals').select('*')\
    .in_('status', ['active', 'approved'])\
    .execute()
```

**Impact:** Any approved signal will now show in Active Trades, not just those explicitly marked as 'active'.

---

## 📊 EXPECTED RESULT

After fix + restart, Active Trades tab should show:

```
🔄 ACTIVE TRADES (Live Tracking)

LINK/USDT SHORT
Entry: $9.7787 | Current: $9.6100 | P&L: 🟢 +1.72%
TP1: ⏳ $6.6431 | TP2: ⏳ $5.0753 | TP3: ⏳ $3.5075
Status: Tracking
```

**Auto-refreshes every 15 seconds!**

---

## 🎯 NEXT STEPS

1. ✅ **Restart Dashboard** - Fix is already applied
2. ✅ **Check Active Trades Tab** - See if LINK appears
3. ❌ **If not showing** - Check Supabase for signal
4. ❌ **If not in database** - Create manual signal
5. ✅ **Verify auto-refresh** - Should update every 15s

---

## 💡 PREVENTION FOR FUTURE

To ensure signals are always saved:

1. **Approve signals quickly** (before 30min expiry)
2. **Check Pending tab regularly**
3. **Monitor logs** for database errors
4. **Verify Supabase connection** in .env

---

**Status:** Fix applied, restart required  
**Next:** Restart dashboard and check Active Trades tab
