-- Add metadata column to signals table for partial close tracking
-- Run this in your Supabase SQL Editor

ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN signals.metadata IS 'Stores partial close history and remaining position percentage';

-- Example metadata structure:
-- {
--   "partial_closes": [
--     {
--       "percent": 75,
--       "price": 1.1589,
--       "pnl": 1.04,
--       "timestamp": "2026-06-12T00:24:56",
--       "reason": "Take profit"
--     }
--   ],
--   "remaining_position": 25.0
-- }
