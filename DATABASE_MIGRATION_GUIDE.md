# 🗄️ Database Migration Guide - TP/SL Tracking

**Issue:** Missing database columns for TP hit tracking causing errors.

**Error:**
```
Error marking TP1 hit: {'code': 'PGRST204', 'details': None, 'hint': None, 
'message': "Could not find the 'tp1_hit' column of 'signals' in the schema cache"}
```

---

## 🚀 Quick Fix (Run This in Supabase SQL Editor)

### Step 1: Open Supabase Dashboard
1. Go to https://supabase.com/dashboard
2. Select your project
3. Click **SQL Editor** in the left sidebar

### Step 2: Run Migration Script
Copy and paste this SQL:

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

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_tp_hits ON signals(tp1_hit, tp2_hit, tp3_hit) WHERE status = 'active';
```

### Step 3: Click "Run" Button

You should see:
```
Success. No rows returned
```

---

## ✅ Verification

Run this query to verify columns exist:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'signals' 
AND column_name LIKE '%hit%'
ORDER BY column_name;
```

**Expected output:**
```
tp1_hit          | boolean
tp1_hit_at       | timestamp with time zone
tp2_hit          | boolean
tp2_hit_at       | timestamp with time zone
tp3_hit          | boolean
tp3_hit_at       | timestamp with time zone
stop_hit         | boolean
stop_hit_at      | timestamp with time zone
```

---

## 🔄 After Migration

1. **Restart your bot** - The code is already updated to use these fields
2. **Test TP hit detection** - Wait for a signal to hit TP1
3. **Check logs** - Should see "TP1 marked as hit" instead of errors

---

## 📊 What These Columns Do

| Column | Purpose |
|--------|---------|
| `tp1_hit`, `tp2_hit`, `tp3_hit` | Track which TPs have been hit |
| `tp1_hit_at`, `tp2_hit_at`, `tp3_hit_at` | Timestamp when each TP was hit |
| `stop_hit` | Track if stop loss was hit |
| `stop_hit_at` | Timestamp when SL was hit |
| `stop_moved_to_breakeven` | Track if SL was moved to breakeven after TP1 |
| `stop_updated_at` | Timestamp when SL was last updated |
| `expires_at` | When the signal expires (if not entered) |

---

## 🐛 Troubleshooting

### Error: "relation 'signals' does not exist"
**Solution:** You need to create the `signals` table first. Check `SETUP_CHECKLIST.md` for table creation.

### Error: "permission denied"
**Solution:** Make sure you're using the Supabase SQL Editor with admin privileges.

### Still getting errors after migration?
**Solution:** 
1. Clear your browser cache
2. Restart the bot
3. Check Supabase logs for any issues

---

## 📝 Alternative: Use Migration File

If you prefer, you can run the migration file directly:

```bash
# From project root
psql $DATABASE_URL -f database_migration_tp_tracking.sql
```

(Replace `$DATABASE_URL` with your Supabase connection string)

---

**Migration Created:** May 18, 2026  
**Status:** Ready to run  
**Risk:** LOW (uses IF NOT EXISTS, safe to run multiple times)
