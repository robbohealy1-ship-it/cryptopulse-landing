-- Run this in your Supabase SQL Editor (https://app.supabase.com/project/_/sql)
-- Adds missing 'name' column to alpha_plays table

-- Add the missing 'name' column
ALTER TABLE alpha_plays
ADD COLUMN IF NOT EXISTS name TEXT;

-- Add comment for documentation
COMMENT ON COLUMN alpha_plays.name IS 'Full token name (e.g., "Prosper", "Solana")';
