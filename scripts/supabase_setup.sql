-- CRYPTO PULSE SIGNALS - Supabase Setup Script
-- Run this in your Supabase SQL Editor

-- Enable Row Level Security
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Create policies for signals table (public read for active signals)
CREATE POLICY "Public can view active signals"
ON signals FOR SELECT
USING (status = 'active' OR status = 'closed');

CREATE POLICY "Service role can do everything on signals"
ON signals FOR ALL
USING (auth.role() = 'service_role');

-- Create policies for subscribers table
CREATE POLICY "Users can view their own subscription"
ON subscribers FOR SELECT
USING (auth.uid()::text = user_id);

CREATE POLICY "Service role can do everything on subscribers"
ON subscribers FOR ALL
USING (auth.role() = 'service_role');

-- Create policies for payments table
CREATE POLICY "Users can view their own payments"
ON payments FOR SELECT
USING (auth.uid()::text = user_id);

CREATE POLICY "Service role can do everything on payments"
ON payments FOR ALL
USING (auth.role() = 'service_role');

-- Create function to update performance logs
CREATE OR REPLACE FUNCTION update_daily_performance()
RETURNS void AS $$
DECLARE
    today DATE := CURRENT_DATE;
    signal_stats RECORD;
BEGIN
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE status = 'approved') as approved,
        COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
        COUNT(*) FILTER (WHERE status = 'closed') as closed,
        COUNT(*) FILTER (WHERE status = 'closed' AND pnl_percent > 0) as wins,
        COUNT(*) FILTER (WHERE status = 'closed' AND pnl_percent <= 0) as losses,
        COALESCE(SUM(pnl_percent) FILTER (WHERE status = 'closed'), 0) as total_pnl,
        COALESCE(AVG(pnl_percent) FILTER (WHERE status = 'closed'), 0) as avg_pnl
    INTO signal_stats
    FROM signals
    WHERE DATE(created_at) = today;
    
    INSERT INTO performance_logs (
        date, total_signals, approved_signals, rejected_signals,
        closed_signals, wins, losses, total_pnl, avg_pnl, win_rate
    ) VALUES (
        today,
        signal_stats.total,
        signal_stats.approved,
        signal_stats.rejected,
        signal_stats.closed,
        signal_stats.wins,
        signal_stats.losses,
        signal_stats.total_pnl,
        signal_stats.avg_pnl,
        CASE WHEN signal_stats.closed > 0 
             THEN (signal_stats.wins::DECIMAL / signal_stats.closed * 100)
             ELSE 0 
        END
    )
    ON CONFLICT (date) DO UPDATE SET
        total_signals = EXCLUDED.total_signals,
        approved_signals = EXCLUDED.approved_signals,
        rejected_signals = EXCLUDED.rejected_signals,
        closed_signals = EXCLUDED.closed_signals,
        wins = EXCLUDED.wins,
        losses = EXCLUDED.losses,
        total_pnl = EXCLUDED.total_pnl,
        avg_pnl = EXCLUDED.avg_pnl,
        win_rate = EXCLUDED.win_rate;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to automatically update performance logs
CREATE OR REPLACE FUNCTION trigger_update_performance()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM update_daily_performance();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_performance_on_signal_change
AFTER INSERT OR UPDATE ON signals
FOR EACH ROW
EXECUTE FUNCTION trigger_update_performance();
