-- Run this in your Supabase SQL Editor (https://app.supabase.com/project/_/sql)
-- Fixes alpha_plays table so plays persist with full details across bot restarts

-- 1. Add the missing JSONB column for full candidate data
ALTER TABLE alpha_plays
ADD COLUMN IF NOT EXISTS candidate_data JSONB;

-- 2. Add the missing play_type column
ALTER TABLE alpha_plays
ADD COLUMN IF NOT EXISTS play_type TEXT DEFAULT 'day_trade';

-- 3. Add price/tracking columns that the save method expects
ALTER TABLE alpha_plays
ADD COLUMN IF NOT EXISTS entry_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS stop_loss NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS take_profit_1 NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS take_profit_2 NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS position_size TEXT DEFAULT '2-5%',
ADD COLUMN IF NOT EXISTS current_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS current_pnl NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS highest_price NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS lowest_price NUMERIC DEFAULT 0;

-- 4. Add timestamp columns
ALTER TABLE alpha_plays
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS tp1_hit_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS tp2_hit_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sl_hit_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 5. Ensure created_at has a default
ALTER TABLE alpha_plays
ALTER COLUMN created_at SET DEFAULT NOW();

-- 6. Add index on status for fast lookups
CREATE INDEX IF NOT EXISTS idx_alpha_plays_status ON alpha_plays(status);

-- 7. Add index on symbol for fast lookups
CREATE INDEX IF NOT EXISTS idx_alpha_plays_symbol ON alpha_plays(symbol);
