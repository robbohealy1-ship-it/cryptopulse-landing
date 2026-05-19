-- CRITICAL: Create subscribers table with all required columns
-- Run this IMMEDIATELY in Supabase SQL Editor

-- Drop and recreate if exists (to fix broken schema)
DROP TABLE IF EXISTS subscribers CASCADE;

CREATE TABLE subscribers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT UNIQUE NOT NULL,
    telegram_user_id TEXT,
    username TEXT,
    tier TEXT DEFAULT 'monthly',
    plan TEXT DEFAULT 'monthly',
    status TEXT DEFAULT 'active',
    subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    cancelled_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    trial_started_at TIMESTAMP WITH TIME ZONE,
    trial_ended_at TIMESTAMP WITH TIME ZONE,
    had_trial BOOLEAN DEFAULT FALSE,
    notes TEXT,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    payment_method TEXT DEFAULT 'stripe',
    total_paid NUMERIC DEFAULT 0,
    last_payment_at TIMESTAMP WITH TIME ZONE,
    referral_code TEXT,
    referred_by TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for common queries
CREATE INDEX idx_subscribers_user_id ON subscribers(user_id);
CREATE INDEX idx_subscribers_status ON subscribers(status);
CREATE INDEX idx_subscribers_tier ON subscribers(tier);
CREATE INDEX idx_subscribers_trial_ends ON subscribers(trial_ends_at) WHERE trial_ends_at IS NOT NULL;

-- Enable RLS
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role full access" ON subscribers
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Verify table was created
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'subscribers' 
ORDER BY ordinal_position;
