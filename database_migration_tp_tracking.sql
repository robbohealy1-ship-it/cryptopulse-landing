-- ============================================
-- CryptoPulse Signals - TP/SL Tracking Migration
-- Add columns for tracking TP hits and stop loss
-- ============================================

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

-- Add comment
COMMENT ON TABLE signals IS 'Trading signals with TP/SL tracking - Updated May 18, 2026';
