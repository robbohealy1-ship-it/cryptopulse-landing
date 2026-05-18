-- CRYPTO PULSE SIGNALS - Database Initialization Script

-- Create signals table
CREATE TABLE IF NOT EXISTS signals (
    id VARCHAR(255) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    setup_type VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    stop_loss DECIMAL(20, 8) NOT NULL,
    take_profit_1 DECIMAL(20, 8) NOT NULL,
    take_profit_2 DECIMAL(20, 8),
    take_profit_3 DECIMAL(20, 8),
    confidence DECIMAL(5, 2) NOT NULL,
    technical_score JSONB NOT NULL,
    context_score JSONB NOT NULL,
    reasoning TEXT,
    status VARCHAR(20) NOT NULL,
    risk_reward DECIMAL(10, 2),
    atr DECIMAL(20, 8),
    volume_24h DECIMAL(20, 2),
    market_context TEXT,
    news_context TEXT,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    approved_at TIMESTAMP,
    published_at TIMESTAMP,
    closed_at TIMESTAMP,
    free_channel_message_id INTEGER,
    vip_channel_message_id INTEGER,
    actual_entry DECIMAL(20, 8),
    actual_exit DECIMAL(20, 8),
    pnl_percent DECIMAL(10, 2),
    chart_url TEXT
);

-- Create indexes for signals table
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);

-- Create subscribers table
CREATE TABLE IF NOT EXISTS subscribers (
    user_id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255),
    tier VARCHAR(20) NOT NULL,
    stripe_customer_id VARCHAR(255),
    subscribed_at TIMESTAMP NOT NULL,
    cancelled_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB
);

-- Create indexes for subscribers table
CREATE INDEX IF NOT EXISTS idx_subscribers_tier ON subscribers(tier);
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(active);

-- Create payments table
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    stripe_payment_id VARCHAR(255),
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES subscribers(user_id)
);

-- Create performance_logs table
CREATE TABLE IF NOT EXISTS performance_logs (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    total_signals INTEGER DEFAULT 0,
    approved_signals INTEGER DEFAULT 0,
    rejected_signals INTEGER DEFAULT 0,
    closed_signals INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_pnl DECIMAL(10, 2) DEFAULT 0,
    avg_pnl DECIMAL(10, 2) DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unique index on date
CREATE UNIQUE INDEX IF NOT EXISTS idx_performance_logs_date ON performance_logs(date);

-- Create system_logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    module VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for system logs
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
