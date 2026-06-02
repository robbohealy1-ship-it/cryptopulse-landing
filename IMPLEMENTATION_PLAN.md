# 📋 IMPLEMENTATION PLAN
## AI-Powered Crypto Investment Intelligence Engine

**Project:** CryptoPulse Signals - Research Engine Transformation  
**Timeline:** 8 weeks  
**Approach:** Incremental, non-breaking, fully tested

---

## OVERVIEW

This plan transforms Alpha Plays from a signal generator into a comprehensive Investment Intelligence Engine while preserving all existing functionality.

### Core Principles
1. **Non-Breaking:** All existing features continue to work
2. **Incremental:** Deploy in phases, validate each step
3. **Reversible:** Every change can be rolled back
4. **Tested:** Comprehensive testing at each phase
5. **Observable:** Full logging and monitoring

---

## PHASE 1: FOUNDATION (Week 1)
**Goal:** Database schema and core infrastructure

### Tasks

#### 1.1 Database Schema Design
**File:** `migrations/create_research_tables.sql`

```sql
-- Create all new tables:
-- research_projects, conviction_history, alpha_basket,
-- research_reports, narratives, catalysts, market_regimes

-- Add indexes for performance
-- Add foreign key constraints
-- Add triggers for updated_at timestamps
```

**Validation:**
- Run on local Supabase instance
- Test all CRUD operations
- Verify indexes work
- Check foreign key constraints

#### 1.2 Extend Database Client
**File:** `src/database/supabase_client.py`

**New Methods:**
```python
# Research Projects
async def save_research_project(self, project: Dict) -> bool
async def get_research_project(self, project_id: str) -> Optional[Dict]
async def get_all_research_projects(self, status: str = None) -> List[Dict]
async def update_research_project(self, project_id: str, updates: Dict) -> bool

# Conviction History
async def save_conviction_score(self, project_id: str, scores: Dict) -> bool
async def get_conviction_history(self, project_id: str, days: int = 30) -> List[Dict]

# Alpha Basket
async def get_alpha_basket(self) -> List[Dict]
async def add_to_basket(self, project_id: str, rank: int) -> bool
async def remove_from_basket(self, project_id: str) -> bool
async def update_basket_ranks(self, rankings: List[Dict]) -> bool

# Research Reports
async def save_research_report(self, report: Dict) -> bool
async def get_research_reports(self, project_id: str = None) -> List[Dict]
async def publish_report(self, report_id: str) -> bool

# Narratives
async def save_narrative(self, narrative: Dict) -> bool
async def get_narratives(self) -> List[Dict]
async def update_narrative_strength(self, narrative_id: str, strength: float) -> bool

# Catalysts
async def save_catalyst(self, catalyst: Dict) -> bool
async def get_upcoming_catalysts(self, days: int = 30) -> List[Dict]
async def mark_catalyst_occurred(self, catalyst_id: str) -> bool

# Market Regimes
async def save_market_regime(self, regime: Dict) -> bool
async def get_current_regime(self) -> Optional[Dict]
async def get_regime_history(self, days: int = 90) -> List[Dict]
```

**Testing:**
- Unit tests for each method
- Integration tests with Supabase
- Error handling tests
- Transaction tests

#### 1.3 Create Research Module Structure
**Directory:** `src/research/`

```
src/research/
├── __init__.py
├── models.py                  # Data models
├── project_database.py        # Project CRUD
├── conviction_engine.py       # Scoring system
├── report_generator.py        # AI reports
├── basket_manager.py          # Basket management
├── narrative_tracker.py       # Narrative tracking
├── catalyst_calendar.py       # Event tracking
├── regime_detector.py         # Market regime
└── competitive_analyzer.py    # Comparisons
```

#### 1.4 Define Data Models
**File:** `src/research/models.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict

@dataclass
class ResearchProject:
    id: str
    symbol: str
    name: str
    chain: str
    token_address: Optional[str]
    
    # Classification
    category: Optional[str]
    narrative: Optional[str]
    sector: Optional[str]
    
    # Market Data
    market_cap: float
    fdv: float
    price: float
    volume_24h: float
    liquidity: float
    
    # Fundamentals
    tvl: Optional[float]
    revenue_24h: Optional[float]
    fees_24h: Optional[float]
    active_users: Optional[int]
    transactions_24h: Optional[int]
    
    # Development
    github_stars: Optional[int]
    github_commits_30d: Optional[int]
    github_contributors: Optional[int]
    last_commit_date: Optional[datetime]
    
    # Social
    twitter_followers: Optional[int]
    discord_members: Optional[int]
    telegram_members: Optional[int]
    
    # Conviction Scores
    conviction_score: float = 0.0
    risk_score: float = 0.0
    quality_score: float = 0.0
    valuation_score: float = 0.0
    narrative_score: float = 0.0
    momentum_score: float = 0.0
    potential_100x_score: float = 0.0
    
    # Status
    status: str = 'discovered'
    in_basket: bool = False
    basket_rank: Optional[int] = None
    
    # Metadata
    discovered_at: datetime
    last_updated: datetime
    last_scored_at: Optional[datetime]
    
    # Research
    investment_thesis: Optional[str]
    bull_case: Optional[str]
    bear_case: Optional[str]
    key_risks: List[str]
    catalysts: List[str]
    
    # Links
    website: Optional[str]
    twitter: Optional[str]
    discord: Optional[str]
    telegram: Optional[str]
    github: Optional[str]
    docs: Optional[str]

@dataclass
class ConvictionScore:
    project_id: str
    conviction_score: float
    risk_score: float
    quality_score: float
    valuation_score: float
    narrative_score: float
    momentum_score: float
    score_change: Optional[float]
    change_reason: Optional[str]
    recorded_at: datetime
    
    # Explanation
    positive_factors: List[str]
    negative_factors: List[str]
    weightings: Dict[str, float]

@dataclass
class AlphaBasketEntry:
    id: str
    project_id: str
    rank: int
    previous_rank: Optional[int]
    added_at: datetime
    added_reason: str
    entry_price: float
    entry_market_cap: float
    current_price: float
    current_market_cap: float
    pnl_percent: float
    status: str
    removed_at: Optional[datetime]
    removal_reason: Optional[str]

@dataclass
class ResearchReport:
    id: str
    project_id: str
    report_type: str
    title: str
    executive_summary: str
    investment_thesis: str
    bull_case: str
    bear_case: str
    key_risks: List[str]
    catalysts: List[str]
    competitive_analysis: str
    valuation_discussion: str
    accumulation_zones: str
    dca_strategy: str
    time_horizon: str
    conviction_score: float
    risk_score: float
    quality_score: float
    generated_at: datetime
    generated_by: str
    published: bool
    published_at: Optional[datetime]
    telegram_message_id: Optional[int]

@dataclass
class Narrative:
    id: str
    name: str
    description: str
    strength_score: float
    momentum_score: float
    project_count: int
    total_market_cap: float
    discovered_at: datetime
    last_updated: datetime

@dataclass
class Catalyst:
    id: str
    project_id: str
    event_type: str
    title: str
    description: str
    expected_date: datetime
    confirmed: bool
    occurred_at: Optional[datetime]
    impact_score: float
    price_impact_percent: Optional[float]
    created_at: datetime
    updated_at: datetime

@dataclass
class MarketRegime:
    id: str
    regime: str  # bull, bear, accumulation, expansion, euphoria, fear
    confidence: float
    btc_trend: str
    eth_trend: str
    alt_trend: str
    fear_greed_index: Optional[int]
    detected_at: datetime
```

### Deliverables
- ✅ Database migration SQL
- ✅ Extended database client with tests
- ✅ Research module structure
- ✅ Data models defined
- ✅ Unit tests passing

### Success Criteria
- All tests pass
- No impact on existing functionality
- Database can be rolled back
- Code review approved

---

## PHASE 2: DISCOVERY ENHANCEMENT (Week 2)
**Goal:** Enhance discovery with new data sources

### Tasks

#### 2.1 Add DefiLlama Integration
**File:** `src/research/integrations/defillama.py`

```python
class DefiLlamaClient:
    """Fetch TVL, fees, revenue data"""
    
    async def get_protocol_tvl(self, protocol: str) -> Optional[float]
    async def get_protocol_fees(self, protocol: str) -> Optional[Dict]
    async def get_protocol_revenue(self, protocol: str) -> Optional[Dict]
    async def get_chain_tvl(self, chain: str) -> Optional[float]
    async def search_protocols(self, query: str) -> List[Dict]
```

**API Endpoints:**
- `https://api.llama.fi/protocol/{protocol}`
- `https://api.llama.fi/summary/fees/{protocol}`
- `https://api.llama.fi/summary/revenue/{protocol}`

**Rate Limits:** None (free API)

#### 2.2 Add GitHub Integration
**File:** `src/research/integrations/github.py`

```python
class GitHubClient:
    """Fetch developer activity data"""
    
    async def get_repo_stats(self, repo: str) -> Optional[Dict]
    async def get_commit_activity(self, repo: str, days: int = 30) -> List[Dict]
    async def get_contributors(self, repo: str) -> List[Dict]
    async def get_latest_release(self, repo: str) -> Optional[Dict]
```

**API Endpoints:**
- `https://api.github.com/repos/{owner}/{repo}`
- `https://api.github.com/repos/{owner}/{repo}/commits`
- `https://api.github.com/repos/{owner}/{repo}/contributors`

**Rate Limits:** 5000/hour (authenticated)

#### 2.3 Add CoinGecko Integration
**File:** `src/research/integrations/coingecko.py`

```python
class CoinGeckoClient:
    """Fetch market data and developer stats"""
    
    async def get_coin_data(self, coin_id: str) -> Optional[Dict]
    async def get_market_data(self, coin_id: str) -> Optional[Dict]
    async def search_coins(self, query: str) -> List[Dict]
    async def get_trending(self) -> List[Dict]
```

**API Endpoints:**
- `https://api.coingecko.com/api/v3/coins/{id}`
- `https://api.coingecko.com/api/v3/search`
- `https://api.coingecko.com/api/v3/search/trending`

**Rate Limits:** 10-50 calls/minute (free tier)

#### 2.4 Extend Alpha Discovery
**File:** `src/alpha_plays/alpha_discovery.py`

**New Methods:**
```python
async def enrich_with_fundamentals(self, candidate: AlphaPlayCandidate) -> AlphaPlayCandidate:
    """Add TVL, fees, revenue data"""
    
async def enrich_with_development(self, candidate: AlphaPlayCandidate) -> AlphaPlayCandidate:
    """Add GitHub stats"""
    
async def enrich_with_market_data(self, candidate: AlphaPlayCandidate) -> AlphaPlayCandidate:
    """Add CoinGecko data"""
    
async def detect_narrative(self, candidate: AlphaPlayCandidate) -> str:
    """Identify primary narrative"""
    
async def find_competitors(self, candidate: AlphaPlayCandidate) -> List[str]:
    """Find similar projects"""
```

#### 2.5 Create Project Database Manager
**File:** `src/research/project_database.py`

```python
class ProjectDatabase:
    """Manage research projects"""
    
    def __init__(self, db_client: SupabaseClient):
        self.db = db_client
    
    async def create_project(self, candidate: AlphaPlayCandidate) -> ResearchProject:
        """Convert candidate to research project"""
        
    async def update_project(self, project_id: str, updates: Dict) -> bool:
        """Update project data"""
        
    async def get_project(self, project_id: str) -> Optional[ResearchProject]:
        """Get project by ID"""
        
    async def get_all_projects(self, filters: Dict = None) -> List[ResearchProject]:
        """Get all projects with optional filters"""
        
    async def archive_project(self, project_id: str, reason: str) -> bool:
        """Archive a project"""
        
    async def enrich_project(self, project_id: str) -> bool:
        """Refresh all data sources"""
```

### Deliverables
- ✅ DefiLlama integration
- ✅ GitHub integration
- ✅ CoinGecko integration
- ✅ Enhanced discovery filters
- ✅ Project database manager
- ✅ Integration tests

### Success Criteria
- All API integrations work
- Data enrichment successful
- No impact on existing discovery
- Rate limits respected
- Error handling robust

---

## PHASE 3: CONVICTION SCORING (Week 3)
**Goal:** Build multi-factor scoring system

### Tasks

#### 3.1 Create Conviction Engine
**File:** `src/research/conviction_engine.py`

```python
class ConvictionEngine:
    """Calculate and track conviction scores"""
    
    def __init__(self, db_client: SupabaseClient):
        self.db = db_client
        self.weights = {
            'quality': 0.25,
            'valuation': 0.20,
            'narrative': 0.15,
            'momentum': 0.15,
            'risk': 0.15,
            'development': 0.10
        }
    
    async def calculate_conviction(self, project: ResearchProject) -> ConvictionScore:
        """Calculate overall conviction score"""
        
        quality = await self._calculate_quality_score(project)
        valuation = await self._calculate_valuation_score(project)
        narrative = await self._calculate_narrative_score(project)
        momentum = await self._calculate_momentum_score(project)
        risk = await self._calculate_risk_score(project)
        
        # Weighted average
        conviction = (
            quality * self.weights['quality'] +
            valuation * self.weights['valuation'] +
            narrative * self.weights['narrative'] +
            momentum * self.weights['momentum'] +
            (100 - risk) * self.weights['risk']
        )
        
        return ConvictionScore(
            project_id=project.id,
            conviction_score=conviction,
            quality_score=quality,
            valuation_score=valuation,
            narrative_score=narrative,
            momentum_score=momentum,
            risk_score=risk,
            recorded_at=datetime.utcnow(),
            positive_factors=self._get_positive_factors(project),
            negative_factors=self._get_negative_factors(project),
            weightings=self.weights
        )
    
    async def _calculate_quality_score(self, project: ResearchProject) -> float:
        """Score based on fundamentals"""
        score = 0.0
        
        # TVL (if applicable)
        if project.tvl:
            if project.tvl > 100_000_000:
                score += 30
            elif project.tvl > 10_000_000:
                score += 20
            elif project.tvl > 1_000_000:
                score += 10
        
        # Revenue/Fees
        if project.revenue_24h and project.revenue_24h > 0:
            score += 20
        
        # Active Users
        if project.active_users:
            if project.active_users > 10_000:
                score += 20
            elif project.active_users > 1_000:
                score += 10
        
        # Development Activity
        if project.github_commits_30d:
            if project.github_commits_30d > 100:
                score += 15
            elif project.github_commits_30d > 30:
                score += 10
            elif project.github_commits_30d > 10:
                score += 5
        
        # Social Following
        if project.twitter_followers:
            if project.twitter_followers > 100_000:
                score += 15
            elif project.twitter_followers > 10_000:
                score += 10
            elif project.twitter_followers > 1_000:
                score += 5
        
        return min(score, 100)
    
    async def _calculate_valuation_score(self, project: ResearchProject) -> float:
        """Score based on relative valuation"""
        # Compare to sector averages
        # Lower market cap = higher score (more upside)
        # But must have fundamentals to back it
        
    async def _calculate_narrative_score(self, project: ResearchProject) -> float:
        """Score based on narrative strength"""
        # Check narrative momentum
        # Check sector growth
        # Check social mentions
        
    async def _calculate_momentum_score(self, project: ResearchProject) -> float:
        """Score based on price/volume momentum"""
        # Use existing technical analyzer
        
    async def _calculate_risk_score(self, project: ResearchProject) -> float:
        """Score based on risk factors"""
        # Liquidity risk
        # Concentration risk
        # Smart contract risk
        # Team risk
        
    async def track_score_change(self, project_id: str, new_score: ConvictionScore) -> bool:
        """Save score and calculate change"""
        
    async def get_score_history(self, project_id: str, days: int = 30) -> List[ConvictionScore]:
        """Get historical scores"""
        
    def _get_positive_factors(self, project: ResearchProject) -> List[str]:
        """Extract positive factors for explanation"""
        
    def _get_negative_factors(self, project: ResearchProject) -> List[str]:
        """Extract negative factors for explanation"""
```

### Deliverables
- ✅ Conviction scoring engine
- ✅ Quality score calculator
- ✅ Valuation score calculator
- ✅ Narrative score calculator
- ✅ Momentum score calculator
- ✅ Risk score calculator
- ✅ Score explanation logic
- ✅ Historical tracking
- ✅ Unit tests

### Success Criteria
- Scores are calculated correctly
- Explanations are clear
- History is tracked
- Performance is acceptable (<30s per project)

---

## PHASE 4: ALPHA BASKET (Week 4)
**Goal:** Dynamic watchlist management

### Tasks

#### 4.1 Create Basket Manager
**File:** `src/research/basket_manager.py`

```python
class BasketManager:
    """Manage Alpha Basket watchlist"""
    
    def __init__(self, db_client: SupabaseClient, conviction_engine: ConvictionEngine):
        self.db = db_client
        self.conviction = conviction_engine
        self.max_basket_size = 20
    
    async def update_basket(self) -> List[AlphaBasketEntry]:
        """Recalculate and update basket rankings"""
        
        # Get all projects
        projects = await self.db.get_all_research_projects(status='active')
        
        # Score all projects
        scored = []
        for project in projects:
            score = await self.conviction.calculate_conviction(project)
            scored.append((project, score))
        
        # Sort by conviction score
        scored.sort(key=lambda x: x[1].conviction_score, reverse=True)
        
        # Take top N
        top_projects = scored[:self.max_basket_size]
        
        # Update basket
        current_basket = await self.db.get_alpha_basket()
        new_basket = []
        
        for rank, (project, score) in enumerate(top_projects, 1):
            # Check if already in basket
            existing = next((b for b in current_basket if b['project_id'] == project.id), None)
            
            if existing:
                # Update rank
                await self.db.update_basket_ranks([{
                    'id': existing['id'],
                    'rank': rank,
                    'previous_rank': existing['rank']
                }])
            else:
                # Add new entry
                await self.db.add_to_basket(project.id, rank)
            
            new_basket.append({
                'project': project,
                'score': score,
                'rank': rank
            })
        
        # Remove projects that fell out
        for entry in current_basket:
            if entry['project_id'] not in [p.id for p, _ in top_projects]:
                await self.db.remove_from_basket(entry['project_id'])
        
        return new_basket
    
    async def get_basket(self) -> List[Dict]:
        """Get current basket with full details"""
        
    async def add_to_basket_manual(self, project_id: str, reason: str) -> bool:
        """Manually add project to basket"""
        
    async def remove_from_basket_manual(self, project_id: str, reason: str) -> bool:
        """Manually remove project from basket"""
        
    async def get_basket_history(self, days: int = 30) -> List[Dict]:
        """Get basket changes over time"""
        
    async def calculate_basket_performance(self) -> Dict:
        """Calculate overall basket P&L"""
```

### Deliverables
- ✅ Basket manager
- ✅ Ranking algorithm
- ✅ Automatic updates
- ✅ Manual overrides
- ✅ Performance tracking
- ✅ Unit tests

### Success Criteria
- Basket updates correctly
- Rankings are logical
- Performance calculations accurate
- Manual overrides work

---

## PHASE 5: AI REPORT GENERATION (Week 5)
**Goal:** Professional research reports

### Tasks

#### 5.1 Create Report Generator
**File:** `src/research/report_generator.py`

```python
class ReportGenerator:
    """Generate AI-powered research reports"""
    
    def __init__(self, db_client: SupabaseClient, content_generator):
        self.db = db_client
        self.ai = content_generator
    
    async def generate_new_candidate_report(self, project: ResearchProject, score: ConvictionScore) -> ResearchReport:
        """Generate report for new discovery"""
        
        prompt = f"""
        You are a professional crypto investment analyst. Generate a comprehensive research report for:
        
        PROJECT: {project.name} ({project.symbol})
        CHAIN: {project.chain}
        MARKET CAP: ${project.market_cap:,.0f}
        CONVICTION SCORE: {score.conviction_score:.1f}/100
        
        DATA:
        - TVL: ${project.tvl:,.0f} if project.tvl else 'N/A'}
        - Revenue 24h: ${project.revenue_24h:,.0f} if project.revenue_24h else 'N/A'}
        - Active Users: {project.active_users:,} if project.active_users else 'N/A'}
        - GitHub Commits (30d): {project.github_commits_30d}
        - Twitter Followers: {project.twitter_followers:,} if project.twitter_followers else 'N/A'}
        
        POSITIVE FACTORS:
        {chr(10).join(f'- {f}' for f in score.positive_factors)}
        
        NEGATIVE FACTORS:
        {chr(10).join(f'- {f}' for f in score.negative_factors)}
        
        Generate:
        1. Executive Summary (2-3 sentences)
        2. Investment Thesis (1 paragraph)
        3. Bull Case (3-5 bullet points)
        4. Bear Case (3-5 bullet points)
        5. Key Risks (3-5 bullet points)
        6. Catalysts (3-5 upcoming events)
        7. Valuation Discussion (1 paragraph)
        8. Accumulation Zones (price levels)
        9. DCA Strategy (how to build position)
        10. Time Horizon (short/medium/long term)
        
        Be specific, data-driven, and professional. No hype, no guarantees.
        """
        
        content = await self.ai.generate_content(prompt)
        
        # Parse AI response into structured report
        report = self._parse_report(content, project, score)
        
        # Save to database
        await self.db.save_research_report(report)
        
        return report
    
    async def generate_conviction_upgrade_report(self, project: ResearchProject, old_score: float, new_score: ConvictionScore) -> ResearchReport:
        """Generate report for conviction increase"""
        
    async def generate_conviction_downgrade_report(self, project: ResearchProject, old_score: float, new_score: ConvictionScore) -> ResearchReport:
        """Generate report for conviction decrease"""
        
    async def generate_basket_update_report(self, basket: List[Dict], changes: List[Dict]) -> ResearchReport:
        """Generate weekly basket update"""
        
    async def generate_catalyst_alert(self, project: ResearchProject, catalyst: Catalyst) -> ResearchReport:
        """Generate alert for major catalyst"""
        
    def _parse_report(self, ai_content: str, project: ResearchProject, score: ConvictionScore) -> ResearchReport:
        """Parse AI response into structured report"""
```

### Deliverables
- ✅ Report generator
- ✅ AI prompts for each report type
- ✅ Report parsing logic
- ✅ Report persistence
- ✅ Quality validation
- ✅ Unit tests

### Success Criteria
- Reports are well-structured
- AI quality is high
- Reports are saved correctly
- Generation time < 60s

---

## PHASE 6: ADMIN DASHBOARD (Week 6)
**Goal:** Research Center UI

### Tasks

#### 6.1 Add Research API Endpoints
**File:** `src/admin/dashboard_server.py`

```python
# Research Projects
@app.get("/api/research/projects")
async def get_research_projects(status: str = None):
    """List all research projects"""
    
@app.get("/api/research/projects/{project_id}")
async def get_research_project(project_id: str):
    """Get project details"""
    
@app.post("/api/research/projects")
async def create_research_project(data: Dict):
    """Create new project"""
    
@app.put("/api/research/projects/{project_id}")
async def update_research_project(project_id: str, updates: Dict):
    """Update project"""
    
# Conviction Scoring
@app.get("/api/research/score/{project_id}")
async def get_conviction_score(project_id: str):
    """Get current scores"""
    
@app.get("/api/research/score/{project_id}/history")
async def get_score_history(project_id: str, days: int = 30):
    """Get score history"""
    
@app.post("/api/research/score/{project_id}/update")
async def update_conviction_score(project_id: str):
    """Trigger rescore"""
    
# Alpha Basket
@app.get("/api/basket/current")
async def get_alpha_basket():
    """Get current basket"""
    
@app.post("/api/basket/add")
async def add_to_basket(project_id: str, reason: str):
    """Add to basket"""
    
@app.delete("/api/basket/remove/{project_id}")
async def remove_from_basket(project_id: str, reason: str):
    """Remove from basket"""
    
# Reports
@app.get("/api/reports/list")
async def list_reports(project_id: str = None):
    """List all reports"""
    
@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    """Get report details"""
    
@app.post("/api/reports/generate")
async def generate_report(project_id: str, report_type: str):
    """Generate new report"""
    
@app.post("/api/reports/{report_id}/publish")
async def publish_report(report_id: str):
    """Publish to Telegram"""
```

#### 6.2 Create Research Center UI
**File:** `src/admin/static/research_center.html`

**Sections:**
1. **Project Rankings** - Sortable table of all projects
2. **Alpha Basket** - Top 20 projects with scores
3. **Conviction History** - Charts showing score changes
4. **Report Generator** - Generate and view reports
5. **Catalyst Calendar** - Upcoming events
6. **Narrative Dashboard** - Theme tracker

**Features:**
- Real-time updates
- Interactive charts (Chart.js)
- Filtering and sorting
- Export to CSV
- Dark theme

### Deliverables
- ✅ Research API endpoints
- ✅ Research Center HTML
- ✅ Interactive dashboards
- ✅ Charts and visualizations
- ✅ Integration tests

### Success Criteria
- All endpoints work
- UI is responsive
- Data loads quickly
- Charts render correctly

---

## PHASE 7: INTEGRATION & TESTING (Week 7)
**Goal:** End-to-end integration

### Tasks

#### 7.1 Connect All Components
- Wire discovery → scoring → basket → reports
- Set up automated workflows
- Configure schedulers
- Add error handling
- Add retry logic

#### 7.2 Write Tests
- Unit tests for all new modules
- Integration tests for workflows
- API endpoint tests
- UI tests (Playwright)
- Performance tests
- Load tests

#### 7.3 Documentation
- API documentation
- User guide
- Admin guide
- Developer guide
- Deployment guide

### Deliverables
- ✅ Fully integrated system
- ✅ Comprehensive test suite
- ✅ Complete documentation
- ✅ Performance benchmarks

### Success Criteria
- 90%+ test coverage
- All tests pass
- Performance meets requirements
- Documentation complete

---

## PHASE 8: PRODUCTION DEPLOYMENT (Week 8)
**Goal:** Live deployment

### Tasks

#### 8.1 Pre-Deployment
- Run database migration on staging
- Test on staging environment
- Performance testing
- Security audit
- Backup production database

#### 8.2 Deployment
- Run database migration on production
- Deploy code to Oracle
- Monitor logs
- Verify functionality
- Smoke tests

#### 8.3 Post-Deployment
- Monitor for 24 hours
- User training
- Gather feedback
- Bug fixes
- Performance tuning

### Deliverables
- ✅ Production deployment
- ✅ Monitoring dashboards
- ✅ User training materials
- ✅ Support documentation

### Success Criteria
- Zero downtime
- All features work
- No regressions
- Users trained

---

## ROLLBACK PLAN

### If Deployment Fails

1. **Stop New Services**
```bash
ssh oracle "pkill -f 'research'"
```

2. **Rollback Database**
```sql
-- Run rollback migration
-- Restore from backup if needed
```

3. **Restore Previous Code**
```bash
ssh oracle "cd /home/ubuntu/cryptopulse && git checkout HEAD~1"
```

4. **Restart Bot**
```bash
ssh oracle "cd /home/ubuntu/cryptopulse && nohup python3 -m src.main > bot.log 2>&1 &"
```

---

## MONITORING & OBSERVABILITY

### Key Metrics
- Discovery scan duration
- Scoring calculation time
- Report generation time
- API response times
- Database query performance
- Error rates
- API rate limit usage

### Logging
- All API calls
- All database operations
- All AI generations
- All errors and exceptions
- All user actions

### Alerts
- Discovery failures
- Scoring errors
- Report generation failures
- API rate limit warnings
- Database connection issues
- Performance degradation

---

## TIMELINE SUMMARY

| Phase | Duration | Key Deliverable |
|-------|----------|-----------------|
| 1. Foundation | Week 1 | Database schema + models |
| 2. Discovery | Week 2 | Enhanced data sources |
| 3. Scoring | Week 3 | Conviction engine |
| 4. Basket | Week 4 | Watchlist management |
| 5. Reports | Week 5 | AI report generation |
| 6. Dashboard | Week 6 | Research Center UI |
| 7. Testing | Week 7 | Full integration |
| 8. Deployment | Week 8 | Production launch |

**Total:** 8 weeks

---

## RESOURCE REQUIREMENTS

### Development
- 1 Senior Developer (full-time)
- 1 QA Engineer (part-time)
- 1 DevOps Engineer (part-time)

### Infrastructure
- Supabase (existing)
- OpenAI API (existing)
- DefiLlama API (free)
- GitHub API (free with auth)
- CoinGecko API (free tier)

### Budget
- OpenAI API: ~$100/month (reports)
- Additional Supabase storage: ~$25/month
- Total: ~$125/month additional

---

## NEXT STEPS

1. ✅ Review this plan
2. ⏳ Approve architecture
3. ⏳ Confirm API access
4. ⏳ Set up staging environment
5. ⏳ Begin Phase 1

**Status:** 🟡 AWAITING APPROVAL  
**Ready to Start:** Yes, pending approval
