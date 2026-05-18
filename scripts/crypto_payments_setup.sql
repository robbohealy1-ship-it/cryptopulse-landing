-- CRYPTO PULSE SIGNALS - Crypto Payments Table Setup
-- Run this in Supabase SQL Editor

-- Create crypto_payments table
CREATE TABLE IF NOT EXISTS crypto_payments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    telegram_username TEXT NOT NULL,
    crypto_symbol TEXT NOT NULL,
    amount_crypto DECIMAL(20, 12) NOT NULL,
    amount_usd DECIMAL(10, 2) NOT NULL,
    wallet_address TEXT NOT NULL,
    network TEXT NOT NULL,
    transaction_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    notes TEXT
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_crypto_payments_user_id ON crypto_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_crypto_payments_status ON crypto_payments(status);
CREATE INDEX IF NOT EXISTS idx_crypto_payments_created_at ON crypto_payments(created_at DESC);

-- Enable Row Level Security
ALTER TABLE crypto_payments ENABLE ROW LEVEL SECURITY;

-- Create policy for admin access
CREATE POLICY "Admins can view all crypto payments"
ON crypto_payments FOR SELECT
USING (true);

CREATE POLICY "Service role can manage crypto payments"
ON crypto_payments FOR ALL
USING (auth.role() = 'service_role');

-- Add payment_method column to subscribers table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'subscribers' AND column_name = 'payment_method'
    ) THEN
        ALTER TABLE subscribers ADD COLUMN payment_method TEXT DEFAULT 'stripe';
    END IF;
END $$;

-- Create view for pending crypto payments
CREATE OR REPLACE VIEW pending_crypto_payments AS
SELECT 
    id,
    user_id,
    telegram_username,
    crypto_symbol,
    amount_crypto,
    amount_usd,
    wallet_address,
    network,
    created_at,
    expires_at,
    EXTRACT(EPOCH FROM (expires_at - NOW())) / 3600 AS hours_until_expiry
FROM crypto_payments
WHERE status = 'pending'
  AND expires_at > NOW()
ORDER BY created_at DESC;

-- Grant access to view
GRANT SELECT ON pending_crypto_payments TO authenticated, anon;

-- ==================== AUTOPILOT SYSTEM MIGRATION ====================
-- Add trial tracking columns to subscribers table
DO $$
BEGIN
    -- Trial tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscribers' AND column_name = 'had_trial') THEN
        ALTER TABLE subscribers ADD COLUMN had_trial BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscribers' AND column_name = 'trial_started_at') THEN
        ALTER TABLE subscribers ADD COLUMN trial_started_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscribers' AND column_name = 'trial_ends_at') THEN
        ALTER TABLE subscribers ADD COLUMN trial_ends_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscribers' AND column_name = 'trial_ended_at') THEN
        ALTER TABLE subscribers ADD COLUMN trial_ended_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Signal result tracking (for AutoPilot performance)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'signals' AND column_name = 'tp_level') THEN
        ALTER TABLE signals ADD COLUMN tp_level INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'signals' AND column_name = 'actual_exit') THEN
        ALTER TABLE signals ADD COLUMN actual_exit DECIMAL(20, 10);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'signals' AND column_name = 'pnl_percent') THEN
        ALTER TABLE signals ADD COLUMN pnl_percent DECIMAL(10, 4);
    END IF;
END $$;

-- Index for fast trial expiry lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_trial_ends ON subscribers(trial_ends_at) WHERE tier = 'trial' AND active = TRUE;

-- Index for signal status + date (performance queries)
CREATE INDEX IF NOT EXISTS idx_signals_status_created ON signals(status, created_at DESC);
