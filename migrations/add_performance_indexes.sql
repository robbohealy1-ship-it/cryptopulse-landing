-- ============================================================
-- CryptoPulse Performance Indexes Migration
-- Run this in your Supabase SQL Editor
-- ============================================================
-- NOTE: Only creates indexes on columns confirmed to exist.
-- If a table doesn't exist yet, the IF NOT EXISTS handles it gracefully.

-- Signals table indexes (core columns only)
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_status_created ON signals(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_timeframe ON signals(timeframe);
CREATE INDEX IF NOT EXISTS idx_signals_setup_type ON signals(setup_type);
CREATE INDEX IF NOT EXISTS idx_signals_closed_at ON signals(closed_at DESC);

-- Composite index for active signal lookups (used by autopilot + dashboard)
CREATE INDEX IF NOT EXISTS idx_signals_active_lookup ON signals(status, symbol, created_at DESC);

-- Subscribers indexes
CREATE INDEX IF NOT EXISTS idx_subscribers_tier ON subscribers(tier);
CREATE INDEX IF NOT EXISTS idx_subscribers_user_id ON subscribers(user_id);

-- ============================================================
-- OPTIONAL: Add these ONLY after the respective tables/columns are created
-- ============================================================

-- Uncomment after adding 'grade' column to signals table:
-- CREATE INDEX IF NOT EXISTS idx_signals_grade ON signals(grade);

-- Uncomment after setup_performance table exists:
-- CREATE INDEX IF NOT EXISTS idx_setup_perf_setup_type ON setup_performance(setup_type);
-- CREATE INDEX IF NOT EXISTS idx_setup_perf_timeframe ON setup_performance(timeframe);
-- CREATE INDEX IF NOT EXISTS idx_setup_perf_created ON setup_performance(created_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_setup_perf_signal ON setup_performance(signal_id);

-- Uncomment after trade_audit_log table exists:
-- CREATE INDEX IF NOT EXISTS idx_audit_signal_id ON trade_audit_log(signal_id);
-- CREATE INDEX IF NOT EXISTS idx_audit_event_type ON trade_audit_log(event_type);
-- CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON trade_audit_log(timestamp DESC);

-- Uncomment after alpha_plays table exists:
-- CREATE INDEX IF NOT EXISTS idx_alpha_plays_status ON alpha_plays(status);
-- CREATE INDEX IF NOT EXISTS idx_alpha_plays_symbol ON alpha_plays(symbol);
-- CREATE INDEX IF NOT EXISTS idx_alpha_plays_created ON alpha_plays(created_at DESC);
