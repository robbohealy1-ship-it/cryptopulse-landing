-- CRYPTO INVESTMENT INTELLIGENCE ENGINE - Database Migration
-- Run this in Supabase SQL Editor
-- MVP Version - Core tables only

-- 1. RESEARCH PROJECTS TABLE
CREATE TABLE IF NOT EXISTS research_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    chain TEXT NOT NULL,
    token_address TEXT,
    
    -- Classification
    category TEXT,
    narrative TEXT,
    sector TEXT,
    
    -- Market Data (from existing discovery)
    market_cap NUMERIC DEFAULT 0,
    fdv NUMERIC DEFAULT 0,
    price NUMERIC DEFAULT 0,
    volume_24h NUMERIC DEFAULT 0,
    liquidity NUMERIC DEFAULT 0,
    
    -- Fundamentals (optional for MVP)
    tvl NUMERIC,
    revenue_24h NUMERIC,
    active_users INTEGER,
    transactions_24h INTEGER,
    
    -- Social (from existing discovery)
    twitter_followers INTEGER,
    discord_members INTEGER,
    
    -- Conviction Scores
    conviction_score NUMERIC DEFAULT 0,
    risk_score NUMERIC DEFAULT 0,
    quality_score NUMERIC DEFAULT 0,
    valuation_score NUMERIC DEFAULT 0,
    momentum_score NUMERIC DEFAULT 0,
    
    -- Status
    status TEXT DEFAULT 'discovered',
    in_basket BOOLEAN DEFAULT FALSE,
    basket_rank INTEGER,
    
    -- Research
    investment_thesis TEXT,
    bull_case TEXT,
    bear_case TEXT,
    key_risks TEXT[],
    
    -- Links
    website TEXT,
    twitter TEXT,
    dex_url TEXT,
    
    -- Metadata
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    last_scored_at TIMESTAMPTZ,
    
    UNIQUE(symbol, chain)
);

-- 2. CONVICTION HISTORY TABLE
CREATE TABLE IF NOT EXISTS conviction_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id) ON DELETE CASCADE,
    
    -- Scores
    conviction_score NUMERIC NOT NULL,
    risk_score NUMERIC DEFAULT 0,
    quality_score NUMERIC DEFAULT 0,
    valuation_score NUMERIC DEFAULT 0,
    momentum_score NUMERIC DEFAULT 0,
    
    -- Change tracking
    score_change NUMERIC,
    change_reason TEXT,
    
    -- Metadata
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. ALPHA BASKET TABLE
CREATE TABLE IF NOT EXISTS alpha_basket (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id) ON DELETE CASCADE,
    
    -- Ranking
    rank INTEGER NOT NULL,
    previous_rank INTEGER,
    
    -- Entry
    added_at TIMESTAMPTZ DEFAULT NOW(),
    added_reason TEXT,
    entry_price NUMERIC,
    entry_market_cap NUMERIC,
    
    -- Performance
    current_price NUMERIC,
    current_market_cap NUMERIC,
    pnl_percent NUMERIC,
    
    -- Status
    status TEXT DEFAULT 'active',
    removed_at TIMESTAMPTZ,
    removal_reason TEXT,
    
    -- Metadata
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(project_id)
);

-- 4. RESEARCH REPORTS TABLE (Simplified)
CREATE TABLE IF NOT EXISTS research_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id) ON DELETE CASCADE,
    
    -- Report Type
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    
    -- Content
    executive_summary TEXT,
    investment_thesis TEXT,
    bull_case TEXT,
    bear_case TEXT,
    key_risks TEXT[],
    
    -- Scores (snapshot)
    conviction_score NUMERIC,
    risk_score NUMERIC,
    
    -- Metadata
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    telegram_message_id INTEGER
);

-- 5. INDEXES FOR PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_research_projects_status ON research_projects(status);
CREATE INDEX IF NOT EXISTS idx_research_projects_conviction ON research_projects(conviction_score DESC);
CREATE INDEX IF NOT EXISTS idx_research_projects_basket ON research_projects(in_basket) WHERE in_basket = TRUE;
CREATE INDEX IF NOT EXISTS idx_conviction_history_project ON conviction_history(project_id);
CREATE INDEX IF NOT EXISTS idx_conviction_history_date ON conviction_history(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_alpha_basket_rank ON alpha_basket(rank) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_research_reports_project ON research_reports(project_id);
CREATE INDEX IF NOT EXISTS idx_research_reports_date ON research_reports(generated_at DESC);

-- 6. TRIGGERS FOR UPDATED_AT
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_research_projects_updated_at
    BEFORE UPDATE ON research_projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alpha_basket_updated_at
    BEFORE UPDATE ON alpha_basket
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 7. ROW LEVEL SECURITY (Optional - enable if needed)
-- ALTER TABLE research_projects ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE conviction_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE alpha_basket ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE research_reports ENABLE ROW LEVEL SECURITY;

-- CREATE POLICY "Service role can do everything on research_projects"
-- ON research_projects FOR ALL
-- USING (auth.role() = 'service_role');

-- (Repeat for other tables)

-- SUCCESS MESSAGE
DO $$
BEGIN
    RAISE NOTICE '✅ Research Engine tables created successfully!';
    RAISE NOTICE 'Tables: research_projects, conviction_history, alpha_basket, research_reports';
    RAISE NOTICE 'Indexes: 8 indexes created for performance';
    RAISE NOTICE 'Triggers: updated_at triggers enabled';
END $$;
