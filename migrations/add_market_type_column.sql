-- Migration: Add market_type column to signals table
-- This allows distinguishing between crypto and forex signals

-- Add market_type column (defaults to 'crypto' for backward compatibility)
ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS market_type TEXT DEFAULT 'crypto';

-- Add index for faster filtering by market type
CREATE INDEX IF NOT EXISTS idx_signals_market_type ON signals(market_type);

-- Update existing signals to be 'crypto' (in case default didn't apply)
UPDATE signals 
SET market_type = 'crypto' 
WHERE market_type IS NULL;

-- Add check constraint to ensure only valid market types
ALTER TABLE signals 
ADD CONSTRAINT check_market_type 
CHECK (market_type IN ('crypto', 'forex'));
