# 🔥 CRITICAL FIX - TP/SL Tracking Database Error

**Date:** May 18, 2026  
**Status:** FIXED - Database migration required

---

## ❌ Error Found

```
2026-05-18 14:50:00 | ERROR | supabase_client:mark_tp_hit:217 - 
Error marking TP1 hit: {'code': 'PGRST204', 'details': None, 'hint': None, 
'message': "Could not find the 'tp1_hit' column of 'signals' in the schema cache"}

2026-05-18 14:50:00 | ERROR | main:check_active_signals:743 - 
Error checking active signals: "TradingSignal" object has no field "tp1_hit"
```

**Impact:** TP hit detection was failing, preventing proper trade tracking.

---

## ✅ What Was Fixed

### 1. **Updated TradingSignal Model** ✅
Added missing fields to `src/models/signal.py`:
- `tp1_hit`, `tp2_hit`, `tp3_hit` (bool)
- `tp1_hit_at`, `tp2_hit_at`, `tp3_hit_at` (datetime)
- `stop_hit`, `stop_hit_at` (bool, datetime)
- `stop_moved_to_breakeven` (bool)

### 2. **Updated Database Client** ✅
Modified `src/database/supabase_client.py`:
- Added TP/SL tracking fields to `_dict_to_signal` method
- Graceful handling of missing columns

### 3. **Created Database Migration** ✅
- `database_migration_tp_tracking.sql` - SQL script to add columns
- `DATABASE_MIGRATION_GUIDE.md` - Step-by-step guide

---

## 🚀 ACTION REQUIRED: Run Database Migration

### **You MUST run this SQL in Supabase before restarting the bot:**

1. Go to https://supabase.com/dashboard
2. Select your project
3. Click **SQL Editor**
4. Copy and paste this:

```sql
-- Add TP hit tracking columns
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tp1_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tp2_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tp3_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tp1_hit_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tp2_hit_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tp3_hit_at TIMESTAMP WITH TIME ZONE;

-- Add stop loss tracking columns
ALTER TABLE signals ADD COLUMN IF NOT EXISTS stop_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS stop_hit_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS stop_moved_to_breakeven BOOLEAN DEFAULT FALSE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS stop_updated_at TIMESTAMP WITH TIME ZONE;

-- Add expires_at column (was missing)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_tp_hits ON signals(tp1_hit, tp2_hit, tp3_hit) WHERE status = 'active';
```

5. Click **Run**
6. You should see: `Success. No rows returned`

---

## ✅ After Migration

1. **Restart the bot** - Code is already updated
2. **Test TP detection** - Wait for a signal to hit TP1
3. **Verify logs** - Should see "TP1 marked as hit" instead of errors

---

## 📊 What This Fixes

| Before | After |
|--------|-------|
| ❌ TP hit detection fails | ✅ TP hits tracked properly |
| ❌ Duplicate TP messages | ✅ One message per TP hit |
| ❌ No breakeven tracking | ✅ SL moved to breakeven after TP1 |
| ❌ Database errors in logs | ✅ Clean operation |

---

## 🎯 Files Changed

1. `src/models/signal.py` - Added TP/SL tracking fields
2. `src/database/supabase_client.py` - Updated data loading
3. `database_migration_tp_tracking.sql` - Migration script
4. `DATABASE_MIGRATION_GUIDE.md` - Detailed guide

---

## 📝 Commit

**Commit:** `8a4cdc2`  
**Message:** "Fix TP/SL tracking: Add missing database columns and model fields"  
**Pushed to GitHub:** ✅

---

## ⚠️ IMPORTANT

**DO NOT restart the bot until you run the database migration!**

The code expects these columns to exist. If you restart without the migration, you'll get the same errors.

---

**Fix Applied:** May 18, 2026  
**Status:** Code updated ✅ | Database migration pending ⏳
