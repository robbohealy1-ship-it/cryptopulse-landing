-- Migration: Add missing columns to subscribers table
-- Run this in Supabase SQL Editor

-- Add columns for beta testing and trial management
ALTER TABLE subscribers
ADD COLUMN IF NOT EXISTS notes TEXT,
ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS telegram_user_id TEXT,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'monthly';

-- Add index for faster queries on trial expiry
CREATE INDEX IF NOT EXISTS idx_subscribers_trial_ends 
ON subscribers(trial_ends_at) 
WHERE trial_ends_at IS NOT NULL;

-- Add index for status lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_status 
ON subscribers(status);

-- Verify columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'subscribers' 
ORDER BY ordinal_position;
