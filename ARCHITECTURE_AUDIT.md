# 🏗️ CRYPTOPULSE SIGNALS - COMPLETE ARCHITECTURE AUDIT
## AI-Powered Investment Intelligence Engine Transformation

**Audit Date:** 2025-01-XX  
**Objective:** Transform Alpha Plays from signal generation to investment research intelligence  
**Approach:** Extend, not replace. Preserve all existing functionality.

---

## EXECUTIVE SUMMARY

### Current State
CryptoPulse Signals is a **production trading signal platform** with:
- ✅ Multi-timeframe technical analysis
- ✅ Institutional context scoring
- ✅ Telegram VIP/Free channels
- ✅ Admin dashboard with approval workflows
- ✅ Alpha Plays discovery engine
- ✅ Payment/subscription system
- ✅ Marketing automation
- ✅ Database persistence (Supabase)
- ✅ Exchange integrations (MEXC, cTrader)

### Transformation Goal
Evolve Alpha Plays into a **Crypto Investment Intelligence Engine** that:
- 🎯 Discovers future market leaders before recognition
- 📊 Maintains conviction scores with transparent reasoning
- 📚 Generates professional research reports
- 💎 Manages dynamic Alpha Basket watchlists
- 🔄 Tracks narrative evolution and catalyst progress
- 🧠 Provides AI-powered investment thesis analysis
- 📈 Monitors market regimes and adjusts recommendations

### Critical Constraints
- ❌ **DO NOT** break existing signal generation
- ❌ **DO NOT** remove trading signal features
- ❌ **DO NOT** modify working Telegram/Discord/Payment systems
- ✅ **DO** reuse existing infrastructure
- ✅ **DO** preserve database integrity
- ✅ **DO** maintain backward compatibility

---

## 1. EXISTING ARCHITECTURE MAP

### 1.1 Core Systems

#### **Signal Generation Engine** (`src/engine/`)
- **Purpose:** Generate trading signals with technical + institutional analysis
- **Status:** ✅ Production, working
- **Components:**
  - Technical analyzer
  - Institutional analyzer
  - Context engine
  - Stop validator
  - Timeframe strategies
- **Reusability:** HIGH - Can be adapted for investment scoring

#### **Alpha Plays System** (`src/alpha_plays/`)
- **Purpose:** Discover low-cap, high-hype opportunities
- **Status:** ✅ Production, needs evolution
- **Components:**
  - `alpha_discovery.py` - Scans DexScreener, GeckoTerminal
  - `alpha_engine.py` - Manages lifecycle (pending → active → closed)
  - `alpha_publisher.py` - Publishes to Telegram
  - `content_formatter.py` - Formats messages
  - `gem_hunter.py` - Additional discovery logic
- **Current Limitations:**
  - Template-based reports (not AI-generated)
  - No historical tracking of conviction changes
  - No narrative evolution tracking
  - No competitive analysis
  - No 100x framework
  - No market regime awareness
  - Limited scoring (overall_score only)
- **Reusability:** VERY HIGH - Core foundation for transformation

#### **Database Layer** (`src/database/supabase_client.py`)
- **Purpose:** Persist all data to Supabase PostgreSQL
- **Status:** ✅ Production
- **Existing Tables:**
  - `signals` - Trading signals
  - `subscribers` - User subscriptions
  - `payments` - Payment records
  - `alpha_plays` - Alpha play candidates
  - `performance_logs` - Daily performance stats
  - `trade_audit_log` - Audit trail
- **Missing Tables (for transformation):**
  - `research_projects` - Investment research database
  - `conviction_history` - Score changes over time
  - `alpha_basket` - Curated watchlist
  - `narratives` - Sector/narrative tracking
  - `catalysts` - Catalyst calendar
  - `research_reports` - Generated reports
  - `market_regimes` - Market condition tracking
  - `competitive_analysis` - Project comparisons
  - `smart_money_wallets` - Whale tracking
- **Reusability:** VERY HIGH - Extend schema, don't replace

#### **Admin Dashboard** (`src/admin/dashboard_server.py`)
- **Purpose:** Web UI for monitoring and control
- **Status:** ✅ Production (FastAPI + HTML/JS)
- **Existing Endpoints:**
  - `/api/signals/*` - Signal management
  - `/api/alpha/*` - Alpha plays management
  - `/api/portfolio` - Portfolio view
  - `/api/account` - Exchange account data
  - `/api/marketing/*` - Marketing automation
  - `/api/settings/*` - Configuration
- **Missing Endpoints (for transformation):**
  - `/api/research/*` - Research center
  - `/api/conviction/*` - Conviction tracking
  - `/api/basket/*` - Alpha basket management
  - `/api/narratives/*` - Narrative analysis
  - `/api/catalysts/*` - Catalyst calendar
  - `/api/regime/*` - Market regime
  - `/api/reports/*` - Research reports
- **Reusability:** VERY HIGH - Add new routes, preserve existing

#### **Telegram Bot** (`src/telegram_bot/`)
- **Purpose:** Publish signals and alpha plays to channels
- **Status:** ✅ Production
- **Components:**
  - Channel publisher
  - VIP access bot
  - Message formatting
- **Reusability:** HIGH - Extend for research reports

#### **Marketing System** (`src/marketing/`)
- **Purpose:** Automated community engagement
- **Status:** ✅ Production
- **Components:**
  - Campaign engine
  - Community engagement
  - Welcome sequence
  - Social proof generator
- **Reusability:** MEDIUM - Can promote research reports

#### **Payment System** (`src/payments/`)
- **Purpose:** Handle subscriptions and crypto payments
- **Status:** ✅ Production
- **Reusability:** LOW - Not directly relevant to research engine

### 1.2 Data Sources

#### **Existing Integrations**
- ✅ Binance API (price data, volume, OHLCV)
- ✅ DexScreener API (DEX pairs, liquidity, holders)
- ✅ GeckoTerminal API (DEX data, trending tokens)
- ✅ MEXC Exchange API (trading, account data)
- ✅ cTrader API (trading, account data)

#### **Missing Integrations (for transformation)**
- ❌ GitHub API (developer activity)
- ❌ DefiLlama API (TVL, protocol fees, revenue)
- ❌ CoinGecko API (market data, developer stats)
- ❌ Twitter/X API (social sentiment)
- ❌ Discord API (community metrics)
- ❌ Token Terminal (financial metrics)
- ❌ Messari API (research data)
- ❌ Nansen/Arkham (smart money tracking)
- ❌ Etherscan/Solscan (on-chain data)

### 1.3 AI/Content Generation

#### **Existing AI Usage**
- ✅ `content_generator.py` - GPT-4o-mini for marketing content
- ✅ Template-based alpha play formatting
- ✅ Placeholder social sentiment (not implemented)

#### **Missing AI Capabilities**
- ❌ Investment thesis generation
- ❌ Research report writing
- ❌ Competitive analysis
- ❌ Narrative detection
- ❌ Catalyst identification
- ❌ Risk assessment
- ❌ Bull/bear case generation
- ❌ Score explanation
- ❌ Conviction reasoning

---

## 2. GAP ANALYSIS

### 2.1 Database Schema Gaps

| Required Table | Exists? | Purpose | Priority |
|----------------|---------|---------|----------|
| `research_projects` | ❌ | Core project database | CRITICAL |
| `conviction_history` | ❌ | Track score changes | CRITICAL |
| `alpha_basket` | ❌ | Curated watchlist | HIGH |
| `narratives` | ❌ | Sector/theme tracking | HIGH |
| `catalysts` | ❌ | Event calendar | HIGH |
| `research_reports` | ❌ | Generated reports | HIGH |
| `market_regimes` | ❌ | Market conditions | MEDIUM |
| `competitive_analysis` | ❌ | Project comparisons | MEDIUM |
| `smart_money_wallets` | ❌ | Whale tracking | LOW |
| `project_metrics` | ❌ | Time-series metrics | MEDIUM |

### 2.2 API Endpoint Gaps

| Required Endpoint | Exists? | Purpose | Priority |
|-------------------|---------|---------|----------|
| `/api/research/projects` | ❌ | List all projects | CRITICAL |
| `/api/research/project/{id}` | ❌ | Get project details | CRITICAL |
| `/api/research/score/{id}` | ❌ | Get conviction score | CRITICAL |
| `/api/research/history/{id}` | ❌ | Score history | HIGH |
| `/api/basket/current` | ❌ | Get alpha basket | HIGH |
| `/api/basket/add` | ❌ | Add to basket | HIGH |
| `/api/basket/remove` | ❌ | Remove from basket | HIGH |
| `/api/narratives/list` | ❌ | List narratives | MEDIUM |
| `/api/catalysts/upcoming` | ❌ | Catalyst calendar | MEDIUM |
| `/api/reports/generate` | ❌ | Generate report | HIGH |
| `/api/reports/list` | ❌ | List reports | MEDIUM |
| `/api/regime/current` | ❌ | Current market regime | MEDIUM |

### 2.3 Discovery Engine Gaps

| Required Scanner | Exists? | Data Source | Priority |
|------------------|---------|-------------|----------|
| DEX scanner | ✅ | DexScreener | ✅ Working |
| Market cap filter | ✅ | DexScreener | ✅ Working |
| Volume scanner | ✅ | DexScreener | ✅ Working |
| Liquidity scanner | ✅ | DexScreener | ✅ Working |
| TVL scanner | ❌ | DefiLlama | HIGH |
| Revenue scanner | ❌ | Token Terminal | MEDIUM |
| Developer scanner | ❌ | GitHub | MEDIUM |
| Social scanner | ❌ | Twitter/Discord | MEDIUM |
| Smart money scanner | ❌ | Nansen/Arkham | LOW |
| Funding scanner | ❌ | Manual/Messari | LOW |

### 2.4 Scoring System Gaps

| Required Score | Exists? | Components | Priority |
|----------------|---------|------------|----------|
| Overall Score | ✅ | Basic scoring | ✅ Working |
| Conviction Score | ❌ | Multi-factor | CRITICAL |
| Risk Score | ❌ | Risk assessment | HIGH |
| Quality Score | ❌ | Fundamentals | HIGH |
| Valuation Score | ❌ | Relative value | HIGH |
| Narrative Score | ❌ | Theme strength | MEDIUM |
| Momentum Score | ❌ | Price/volume | MEDIUM |
| Accumulation Score | ❌ | Smart money | LOW |
| 100x Potential Score | ❌ | TAM analysis | MEDIUM |

### 2.5 Report Generation Gaps

| Required Report | Exists? | Format | Priority |
|-----------------|---------|--------|----------|
| Alpha Alert | ✅ | Telegram | ✅ Working |
| New Candidate | ❌ | Full research | CRITICAL |
| Conviction Upgrade | ❌ | Update report | HIGH |
| Conviction Downgrade | ❌ | Update report | HIGH |
| Basket Update | ❌ | Weekly digest | MEDIUM |
| Catalyst Alert | ❌ | Event notification | MEDIUM |
| Narrative Shift | ❌ | Theme analysis | LOW |
| Monthly Review | ❌ | Performance | LOW |

### 2.6 UI/Dashboard Gaps

| Required Section | Exists? | Purpose | Priority |
|------------------|---------|---------|----------|
| Alpha Plays Tab | ✅ | Current system | ✅ Working |
| Research Center | ❌ | New main hub | CRITICAL |
| Alpha Basket | ❌ | Watchlist view | HIGH |
| Project Rankings | ❌ | Sorted list | HIGH |
| Conviction History | ❌ | Score charts | MEDIUM |
| Catalyst Calendar | ❌ | Event timeline | MEDIUM |
| Narrative Dashboard | ❌ | Theme tracker | LOW |
| Regime Monitor | ❌ | Market conditions | LOW |

---

## 3. REUSABLE COMPONENTS

### 3.1 Highly Reusable (Extend, Don't Replace)

#### **Alpha Discovery Engine** (`alpha_discovery.py`)
- **Current:** Scans DexScreener, GeckoTerminal for low-cap gems
- **Reuse For:** Project discovery with enhanced filters
- **Modifications Needed:**
  - Add TVL/revenue/developer activity filters
  - Add narrative detection
  - Add competitive positioning
  - Add valuation metrics
- **Risk:** LOW - Additive changes only

#### **Alpha Engine** (`alpha_engine.py`)
- **Current:** Manages pending → active → closed lifecycle
- **Reuse For:** Research project lifecycle management
- **Modifications Needed:**
  - Add conviction score tracking
  - Add basket management
  - Add report generation triggers
  - Add historical archiving
- **Risk:** LOW - Extend existing patterns

#### **Database Client** (`supabase_client.py`)
- **Current:** Handles all database operations
- **Reuse For:** All new tables and queries
- **Modifications Needed:**
  - Add new table methods
  - Add time-series queries
  - Add aggregation functions
- **Risk:** VERY LOW - Just add new methods

#### **Admin Dashboard** (`dashboard_server.py`)
- **Current:** FastAPI server with existing routes
- **Reuse For:** New research center endpoints
- **Modifications Needed:**
  - Add `/api/research/*` routes
  - Add new UI pages
  - Add new data endpoints
- **Risk:** LOW - Add routes, don't modify existing

#### **Content Generator** (`content_generator.py`)
- **Current:** GPT-4o-mini for marketing
- **Reuse For:** Research report generation
- **Modifications Needed:**
  - Add research report prompts
  - Add thesis generation
  - Add competitive analysis
- **Risk:** LOW - Add new methods

### 3.2 Partially Reusable (Adapt Patterns)

#### **Technical Analyzer** (`technical_analyzer.py`)
- **Current:** Price action, indicators, patterns
- **Reuse For:** Momentum scoring component
- **Modifications Needed:**
  - Extract momentum metrics
  - Add to conviction score
- **Risk:** VERY LOW - Read-only usage

#### **Institutional Analyzer** (`institutional_analyzer.py`)
- **Current:** Session scoring, volume analysis
- **Reuse For:** Market regime detection
- **Modifications Needed:**
  - Extract regime indicators
  - Add to market context
- **Risk:** VERY LOW - Read-only usage

### 3.3 Not Directly Reusable (Reference Only)

#### **Payment System** (`payments/`)
- **Relevance:** None for research engine
- **Action:** Leave untouched

#### **Marketing System** (`marketing/`)
- **Relevance:** Could promote research reports
- **Action:** Optional integration later

---

## 4. ARCHITECTURE DESIGN

### 4.1 Proposed System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CRYPTOPULSE SIGNALS                       │
│                   (Existing Production System)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ EXTENDS (not replaces)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           INVESTMENT INTELLIGENCE ENGINE (NEW)               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Discovery   │  │  Conviction  │  │   Research   │     │
│  │   Engine     │─▶│   Scoring    │─▶│   Reports    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Project    │  │    Alpha     │  │   Catalyst   │     │
│  │  Database    │  │    Basket    │  │   Calendar   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                │
│                            ▼                                │
│                  ┌──────────────────┐                       │
│                  │  Admin Dashboard │                       │
│                  │ (Research Center)│                       │
│                  └──────────────────┘                       │
│                            │                                │
│                            ▼                                │
│                  ┌──────────────────┐                       │
│                  │ Telegram/Discord │                       │
│                  │  (Reports)       │                       │
│                  └──────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Module Structure

```
src/
├── alpha_plays/              # EXISTING - Extend
│   ├── alpha_discovery.py    # ✅ Extend with new filters
│   ├── alpha_engine.py       # ✅ Extend with conviction tracking
│   └── ...
├── research/                 # NEW MODULE
│   ├── __init__.py
│   ├── project_database.py   # Core project management
│   ├── conviction_engine.py  # Scoring system
│   ├── report_generator.py   # AI report generation
│   ├── basket_manager.py     # Alpha basket management
│   ├── narrative_tracker.py  # Narrative/sector tracking
│   ├── catalyst_calendar.py  # Event tracking
│   ├── regime_detector.py    # Market regime
│   └── competitive_analyzer.py # Project comparison
├── database/                 # EXISTING - Extend
│   └── supabase_client.py    # ✅ Add new table methods
├── admin/                    # EXISTING - Extend
│   ├── dashboard_server.py   # ✅ Add research endpoints
│   └── static/
│       └── research_center.html  # NEW UI
└── ...
```

---

## 5. IMPLEMENTATION STRATEGY

### 5.1 Phase 1: Foundation (Week 1)
**Goal:** Database schema and core data models

**Tasks:**
1. Create database migration for new tables
2. Extend `supabase_client.py` with new methods
3. Create `src/research/` module structure
4. Define data models (Project, ConvictionScore, Report, etc.)
5. Add basic CRUD operations

**Deliverables:**
- ✅ Migration SQL file
- ✅ Extended database client
- ✅ Research module skeleton
- ✅ Data models

**Risk:** LOW - No changes to existing code

### 5.2 Phase 2: Discovery Enhancement (Week 2)
**Goal:** Enhance discovery with new data sources

**Tasks:**
1. Add DefiLlama integration (TVL, fees, revenue)
2. Add GitHub integration (developer activity)
3. Add CoinGecko integration (market data)
4. Extend `alpha_discovery.py` with new filters
5. Create `project_database.py` for persistence

**Deliverables:**
- ✅ New API integrations
- ✅ Enhanced discovery filters
- ✅ Project database manager

**Risk:** LOW - Additive to existing discovery

### 5.3 Phase 3: Conviction Scoring (Week 3)
**Goal:** Build multi-factor scoring system

**Tasks:**
1. Create `conviction_engine.py`
2. Implement scoring components:
   - Quality score (fundamentals)
   - Valuation score (relative)
   - Narrative score (theme strength)
   - Momentum score (price/volume)
   - Risk score (assessment)
3. Build weighted aggregation
4. Add score explanation logic
5. Create conviction history tracking

**Deliverables:**
- ✅ Conviction scoring engine
- ✅ Score explanation system
- ✅ Historical tracking

**Risk:** MEDIUM - Complex logic, needs validation

### 5.4 Phase 4: Alpha Basket (Week 4)
**Goal:** Dynamic watchlist management

**Tasks:**
1. Create `basket_manager.py`
2. Implement ranking algorithm
3. Add automatic updates
4. Create basket history tracking
5. Build comparison tools

**Deliverables:**
- ✅ Basket management system
- ✅ Ranking algorithm
- ✅ Historical tracking

**Risk:** LOW - Straightforward logic

### 5.5 Phase 5: AI Report Generation (Week 5)
**Goal:** Professional research reports

**Tasks:**
1. Create `report_generator.py`
2. Build GPT-4 prompts for:
   - Investment thesis
   - Bull/bear cases
   - Competitive analysis
   - Risk assessment
3. Implement report templates
4. Add report persistence
5. Create report distribution

**Deliverables:**
- ✅ AI report generator
- ✅ Report templates
- ✅ Distribution system

**Risk:** MEDIUM - AI quality validation needed

### 5.6 Phase 6: Admin Dashboard (Week 6)
**Goal:** Research Center UI

**Tasks:**
1. Add `/api/research/*` endpoints to `dashboard_server.py`
2. Create `research_center.html` UI
3. Build project rankings view
4. Build basket management view
5. Build conviction history charts
6. Build report viewer

**Deliverables:**
- ✅ Research API endpoints
- ✅ Research Center UI
- ✅ Interactive dashboards

**Risk:** LOW - Standard web development

### 5.7 Phase 7: Integration & Testing (Week 7)
**Goal:** End-to-end integration

**Tasks:**
1. Connect all components
2. Create automated workflows
3. Write unit tests
4. Write integration tests
5. Performance testing
6. User acceptance testing

**Deliverables:**
- ✅ Fully integrated system
- ✅ Test suite
- ✅ Performance benchmarks

**Risk:** MEDIUM - Integration complexity

### 5.8 Phase 8: Production Deployment (Week 8)
**Goal:** Live deployment

**Tasks:**
1. Database migration on production
2. Deploy code to Oracle
3. Monitor logs
4. Verify functionality
5. User training
6. Documentation

**Deliverables:**
- ✅ Production deployment
- ✅ Monitoring dashboards
- ✅ User documentation

**Risk:** HIGH - Production deployment always risky

---

## 6. DATABASE SCHEMA DESIGN

### 6.1 New Tables

#### **research_projects**
```sql
CREATE TABLE research_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    chain TEXT NOT NULL,
    token_address TEXT,
    
    -- Classification
    category TEXT, -- DeFi, L1, L2, Gaming, AI, etc.
    narrative TEXT, -- Current primary narrative
    sector TEXT, -- Broader sector
    
    -- Market Data
    market_cap NUMERIC,
    fdv NUMERIC,
    price NUMERIC,
    volume_24h NUMERIC,
    liquidity NUMERIC,
    
    -- Fundamentals
    tvl NUMERIC,
    revenue_24h NUMERIC,
    fees_24h NUMERIC,
    active_users INTEGER,
    transactions_24h INTEGER,
    
    -- Development
    github_stars INTEGER,
    github_commits_30d INTEGER,
    github_contributors INTEGER,
    last_commit_date TIMESTAMPTZ,
    
    -- Social
    twitter_followers INTEGER,
    discord_members INTEGER,
    telegram_members INTEGER,
    
    -- Conviction
    conviction_score NUMERIC DEFAULT 0,
    risk_score NUMERIC DEFAULT 0,
    quality_score NUMERIC DEFAULT 0,
    valuation_score NUMERIC DEFAULT 0,
    narrative_score NUMERIC DEFAULT 0,
    momentum_score NUMERIC DEFAULT 0,
    potential_100x_score NUMERIC DEFAULT 0,
    
    -- Status
    status TEXT DEFAULT 'discovered', -- discovered, researching, basket, archived
    in_basket BOOLEAN DEFAULT FALSE,
    basket_rank INTEGER,
    
    -- Metadata
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    last_scored_at TIMESTAMPTZ,
    
    -- Research
    investment_thesis TEXT,
    bull_case TEXT,
    bear_case TEXT,
    key_risks TEXT[],
    catalysts TEXT[],
    
    -- Links
    website TEXT,
    twitter TEXT,
    discord TEXT,
    telegram TEXT,
    github TEXT,
    docs TEXT,
    
    UNIQUE(symbol, chain)
);
```

#### **conviction_history**
```sql
CREATE TABLE conviction_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id),
    
    -- Scores
    conviction_score NUMERIC NOT NULL,
    risk_score NUMERIC,
    quality_score NUMERIC,
    valuation_score NUMERIC,
    narrative_score NUMERIC,
    momentum_score NUMERIC,
    
    -- Changes
    score_change NUMERIC, -- vs previous
    change_reason TEXT,
    
    -- Metadata
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_conviction_project (project_id),
    INDEX idx_conviction_date (recorded_at DESC)
);
```

#### **alpha_basket**
```sql
CREATE TABLE alpha_basket (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id),
    
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
    status TEXT DEFAULT 'active', -- active, graduated, removed
    removed_at TIMESTAMPTZ,
    removal_reason TEXT,
    
    -- Metadata
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(project_id),
    INDEX idx_basket_rank (rank),
    INDEX idx_basket_status (status)
);
```

#### **research_reports**
```sql
CREATE TABLE research_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id),
    
    -- Report Type
    report_type TEXT NOT NULL, -- new_candidate, conviction_upgrade, etc.
    title TEXT NOT NULL,
    
    -- Content
    executive_summary TEXT,
    investment_thesis TEXT,
    bull_case TEXT,
    bear_case TEXT,
    key_risks TEXT[],
    catalysts TEXT[],
    competitive_analysis TEXT,
    valuation_discussion TEXT,
    accumulation_zones TEXT,
    dca_strategy TEXT,
    time_horizon TEXT,
    
    -- Scores (snapshot)
    conviction_score NUMERIC,
    risk_score NUMERIC,
    quality_score NUMERIC,
    
    -- Metadata
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    generated_by TEXT, -- 'ai', 'manual', 'hybrid'
    published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    telegram_message_id INTEGER,
    
    INDEX idx_reports_project (project_id),
    INDEX idx_reports_type (report_type),
    INDEX idx_reports_date (generated_at DESC)
);
```

#### **narratives**
```sql
CREATE TABLE narratives (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    
    -- Strength
    strength_score NUMERIC DEFAULT 0,
    momentum_score NUMERIC DEFAULT 0,
    
    -- Projects
    project_count INTEGER DEFAULT 0,
    total_market_cap NUMERIC DEFAULT 0,
    
    -- Metadata
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_narratives_strength (strength_score DESC)
);
```

#### **catalysts**
```sql
CREATE TABLE catalysts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES research_projects(id),
    
    -- Event
    event_type TEXT NOT NULL, -- mainnet, listing, partnership, etc.
    title TEXT NOT NULL,
    description TEXT,
    
    -- Timing
    expected_date DATE,
    confirmed BOOLEAN DEFAULT FALSE,
    occurred_at TIMESTAMPTZ,
    
    -- Impact
    impact_score NUMERIC, -- 0-100
    price_impact_percent NUMERIC, -- actual impact if occurred
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_catalysts_project (project_id),
    INDEX idx_catalysts_date (expected_date)
);
```

#### **market_regimes**
```sql
CREATE TABLE market_regimes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Regime
    regime TEXT NOT NULL, -- bull, bear, accumulation, etc.
    confidence NUMERIC NOT NULL, -- 0-100
    
    -- Indicators
    btc_trend TEXT,
    eth_trend TEXT,
    alt_trend TEXT,
    fear_greed_index INTEGER,
    
    -- Metadata
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_regimes_date (detected_at DESC)
);
```

### 6.2 Migration Strategy

**Approach:** Incremental, reversible migrations

1. Create tables in order (no foreign keys first)
2. Add indexes after data population
3. Test on staging before production
4. Keep rollback scripts ready
5. Backup before migration

---

## 7. API DESIGN

### 7.1 Research Endpoints

```python
# Project Management
GET    /api/research/projects              # List all projects
GET    /api/research/projects/{id}         # Get project details
POST   /api/research/projects              # Create project
PUT    /api/research/projects/{id}         # Update project
DELETE /api/research/projects/{id}         # Archive project

# Conviction Scoring
GET    /api/research/score/{id}            # Get current scores
GET    /api/research/score/{id}/history    # Score history
POST   /api/research/score/{id}/update     # Trigger rescore

# Alpha Basket
GET    /api/basket/current                 # Get current basket
POST   /api/basket/add                     # Add to basket
DELETE /api/basket/remove/{id}             # Remove from basket
GET    /api/basket/history                 # Basket changes

# Reports
GET    /api/reports/list                   # List all reports
GET    /api/reports/{id}                   # Get report
POST   /api/reports/generate               # Generate new report
POST   /api/reports/{id}/publish           # Publish to Telegram

# Narratives
GET    /api/narratives/list                # List narratives
GET    /api/narratives/{id}/projects       # Projects in narrative

# Catalysts
GET    /api/catalysts/upcoming             # Upcoming events
POST   /api/catalysts/create               # Add catalyst
PUT    /api/catalysts/{id}/update          # Update catalyst

# Market Regime
GET    /api/regime/current                 # Current regime
GET    /api/regime/history                 # Regime history
```

---

## 8. RISK ASSESSMENT

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing signals | LOW | CRITICAL | Extensive testing, separate modules |
| Database migration failure | MEDIUM | HIGH | Staging tests, rollback scripts |
| API rate limits | HIGH | MEDIUM | Caching, rate limiting, fallbacks |
| AI report quality | MEDIUM | MEDIUM | Human review, templates, validation |
| Performance degradation | LOW | MEDIUM | Profiling, optimization, caching |
| Data inconsistency | MEDIUM | HIGH | Transactions, validation, audits |

### 8.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Deployment downtime | MEDIUM | HIGH | Blue-green deployment, rollback plan |
| User confusion | HIGH | LOW | Documentation, training, UI clarity |
| Cost overruns (API) | MEDIUM | MEDIUM | Budget monitoring, usage limits |
| Incomplete data | HIGH | MEDIUM | Graceful degradation, fallbacks |

---

## 9. SUCCESS CRITERIA

### 9.1 Functional Requirements
- ✅ All existing signal generation works unchanged
- ✅ Alpha plays continue to function
- ✅ New research projects can be discovered
- ✅ Conviction scores are calculated and tracked
- ✅ Alpha basket is maintained and ranked
- ✅ Research reports are generated
- ✅ Admin dashboard shows research center
- ✅ Reports can be published to Telegram

### 9.2 Performance Requirements
- ✅ Discovery scans complete in < 5 minutes
- ✅ Scoring updates complete in < 30 seconds
- ✅ Report generation completes in < 60 seconds
- ✅ Dashboard loads in < 2 seconds
- ✅ API responses < 500ms (p95)

### 9.3 Quality Requirements
- ✅ 90%+ test coverage for new code
- ✅ Zero regressions in existing features
- ✅ All database migrations reversible
- ✅ Complete API documentation
- ✅ User documentation for research center

---

## 10. NEXT STEPS

### Immediate Actions (Before Coding)
1. ✅ Review this audit with stakeholder
2. ⏳ Validate assumptions about data sources
3. ⏳ Confirm API access (DefiLlama, GitHub, etc.)
4. ⏳ Approve database schema design
5. ⏳ Approve implementation timeline
6. ⏳ Set up staging environment

### Phase 1 Kickoff (After Approval)
1. Create database migration SQL
2. Set up `src/research/` module
3. Define data models
4. Extend database client
5. Write initial tests

---

**Status:** 🟡 AWAITING APPROVAL  
**Next Review:** After stakeholder feedback  
**Estimated Timeline:** 8 weeks for full implementation  
**Risk Level:** MEDIUM (manageable with proper planning)
