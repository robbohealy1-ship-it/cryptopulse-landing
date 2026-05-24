# CRYPTO PULSE SIGNALS - Comprehensive Architectural Audit

**Date:** 2026-05-22  
**Auditor:** Principal Software Architect  
**Scope:** Full platform audit — backend, signal generation, trade tracking, analytics, security, performance, scalability

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Component Map

```
CryptoPulseOrchestrator (main.py, 1824 lines)
├── SignalEngine (src/engine/signal_engine.py, 628 lines)
│   ├── MarketScanner (src/scanner/market_scanner.py)
│   ├── TechnicalAnalyzer (src/analysis/technical_analyzer.py)
│   ├── InstitutionalAnalyzer (src/analysis/institutional_analyzer.py)
│   ├── TimeframeStrategyFactory (src/analysis/timeframe_strategies.py)
│   └── EnhancedContextEngine (src/analysis/enhanced_context_engine.py)
├── AdminBot (src/telegram_bot/admin_bot.py, 785 lines)
├── VIPBot (src/telegram_bot/vip_bot.py)
├── ChannelPublisher (src/telegram_bot/channel_publisher.py, 505 lines)
├── SupabaseClient (src/database/supabase_client.py, 994 lines)
├── AutoPilotSystem (src/marketing/autopilot_system.py, 713 lines)
│   └── PerformanceTracker (in-memory TP/SL monitoring)
├── CampaignEngine (src/marketing/campaign_engine.py)
├── MarketingAutomation (src/telegram_bot/marketing_automation.py)
├── ReportingEngine (src/telegram_bot/reporting.py)
├── SocialMediaPoster (src/marketing/social_media_poster.py)
├── DiscordPublisher (src/marketing/discord_integration.py)
├── ViralGrowthEngine (src/marketing/viral_growth_engine.py)
├── AlphaPlaysEngine (src/alpha_plays/alpha_engine.py)
├── Pro Features (whale alerts, education, custom alerts, giveaways)
├── Exchange Clients (src/exchange/ctrader_client.py, mexc_client.py)
└── Admin Dashboard (src/admin/dashboard_server.py, 2343 lines)
    └── Static HTML (index.html, portfolio.html, marketing.html)
```

### 1.2 Data Flow

```
Scan (15m/1h/4h/1d) → Analyze Pair → Validate → Duplicate Check → Admin Approval → VIP Publish → Free Teaser → TP/SL Tracking → Close
```

### 1.3 Scheduled Jobs (APScheduler)

| Job | Interval | Purpose |
|-----|----------|---------|
| scan_15m | Every 15 min | Intraday swing signals |
| scan_1h | Every hour | Swing trade signals |
| scan_4h | Every 4 hours | Position trade signals |
| scan_daily | 00:05 UTC | Macro position signals |
| check_signals | Every 2 min | Active signal TP/SL monitoring |
| check_expired | Every 1 min | Pending signal expiry |
| autopilot_performance | Every 5 min | Autopilot TP/SL check |
| autopilot_daily | 23:55 UTC | Daily automation |
| autopilot_weekly | Sun 20:00 | Weekly stats posting |
| daily_report | 23:55 UTC | Daily report to admin |
| weekly_report | Sun 20:00 | Weekly report |
| morning_outlook | 08:30 UTC | Morning market overview |
| evening_recap | 21:00 UTC | Evening summary |
| social_media | 10,14,18 UTC | Twitter/X posts |
| monthly_giveaway | 1st, 12:00 UTC | VIP giveaway |
| custom_alerts | Every 5 min | Price alert checks |
| viral_daily | 09:00 UTC | Daily marketing blitz |
| viral_weekly | Sun 10:00 | Weekly Reddit/Discord |
| alpha_discovery | Every 6 hours | Low-cap play discovery |
| alpha_tracking | Every 5 min | Alpha TP/SL tracking |
| daily_reset | 00:00 UTC | Daily counter reset |
| daily_cleanup | 02:00 UTC | Database cleanup |

---

## 2. CRITICAL BUGS IDENTIFIED

### CRITICAL-1: Status Flickering on Limit Orders (FIXED in session)
**Severity:** HIGH  
**Location:** `src/telegram_bot/channel_publisher.py:77` + `src/main.py:on_signal_approved`  
**Issue:** `publish_to_vip()` unconditionally set `signal.status = SignalStatus.ACTIVE` for ALL signals, including limit orders. This caused limit orders to be treated as "filled" before the price actually hit the entry. The autopilot's `track_signal()` then saw `status='active'` and moved the signal to `active_signals` instead of `pending_limit_orders`, triggering premature TP/SL tracking. The frontend showed "Limit filled" when the entry hadn't been hit.  
**Fix Applied:** Removed status override from `publish_to_vip()`. `on_signal_approved()` now sets `ACTIVE` only for market orders, keeping `APPROVED` for limit orders until actual fill detection.

### CRITICAL-2: Portfolio Showing False P&L for Untriggered Limit Orders (FIXED in session)
**Severity:** HIGH  
**Location:** `src/admin/dashboard_server.py:284`  
**Issue:** The `/api/portfolio` endpoint calculated P&L for signals with BOTH `active` and `approved` status. Approved limit orders that hadn't been filled yet were showing fake P&L and being counted as "active trades".  
**Fix Applied:** Portfolio now only calculates P&L for `status='active'`. `approved` signals show as "Pending Entry" with zero P&L.

### CRITICAL-3: Missing `save_signals_batch` Method
**Severity:** MEDIUM  
**Location:** `src/marketing/autopilot_system.py:195` calling non-existent method  
**Issue:** `autopilot_system.py` calls `await self.db.save_signals_batch(signals)` at the end of `check_all_signals()`, but `SupabaseClient` has no such method. This raises `AttributeError` every 5 minutes when active signals exist.  
**Fix Applied:** Added `save_signals_batch()` method to `SupabaseClient` that loops through `save_signal()`.

### CRITICAL-4: Dual TP/SL Tracking Race Conditions
**Severity:** HIGH  
**Location:** `src/main.py:check_active_signals` + `src/marketing/autopilot_system.py:check_all_signals`  
**Issue:** Two independent systems check TP/SL on different schedules:
- `check_active_signals` (main.py): every 2 minutes, loads from DB, sends Telegram notifications
- `autopilot.check_all_signals`: every 5 minutes, in-memory tracking, handles FOMO campaigns

Both can detect the SAME TP/SL hit independently. If `check_active_signals` handles a hit first, it calls `handle_tp_hit()` which updates DB. Then autopilot might still detect it in-memory and try to process it again. The `update_signal_result()` in autopilot could overwrite the DB state.

**Impact:** Duplicate notifications, potential race conditions on status updates, inconsistent P&L tracking.

### CRITICAL-5: In-Memory State Not Synchronized with DB
**Severity:** HIGH  
**Location:** `src/marketing/autopilot_system.py`  
**Issue:** Autopilot maintains `pending_limit_orders` and `active_signals` as in-memory dictionaries. When the app restarts (e.g., Oracle redeploy), this state is lost. Signals are restored from DB via `get_active_signals()`, but:
1. `pending_limit_orders` is NOT restored for limit orders
2. `active_signals` is NOT restored for active trades
3. The `_pending_limit_extremes` in `main.py` is also lost on restart

**Impact:** After restart, limit orders that were being tracked lose their price extreme history. Brief entry touches between checks might be missed. The signal status in DB is correct, but the in-memory tracking state is inconsistent.

### CRITICAL-6: No Comprehensive Signal Grade System
**Severity:** MEDIUM  
**Location:** Signal generation pipeline  
**Issue:** Signals are scored on a 0-100 confidence scale, but there's no institutional-grade letter grading (A+/A/B/C/Rejected). The current `check_signal_quality()` method only checks basic thresholds (confidence >= 90 = "elite", R:R >= 2.0, volume >= $10M). It does NOT validate:
- Trend alignment quality
- Market structure integrity
- Volume profile positioning quality
- Liquidity context strength
- Multi-timeframe alignment depth
- Market regime suitability

**Impact:** Low-quality signals can slip through if they barely meet numeric thresholds but lack true confluence.

### CRITICAL-7: No Trade Analytics Collection
**Severity:** HIGH  
**Location:** Database schema + tracking code  
**Issue:** The system does NOT track critical trade analytics:
- **Maximum Drawdown (MDD)**: Peak-to-trough decline during the trade
- **Maximum Favorable Excursion (MFE)**: Best price reached before close
- **Trade Duration**: How long the trade was open
- **Market Regime at Entry**: Was the market trending, ranging, or volatile?
- **Signal Grade**: What was the signal's letter grade?
- **Setup Type Performance**: Which setups win/lose over time?
- **Timeframe Performance**: Which timeframes perform best?
- **Entry Slippage**: Difference between planned and actual entry
- **Partial Fill Tracking**: For limit orders, was it fully or partially filled?

The `TradingSignal` model has fields for `actual_entry`, `actual_exit`, `pnl_percent`, and TP/SL hit booleans, but no `mdd`, `mfe`, `duration`, `market_regime`, `signal_grade`, or `slippage` fields.

**Impact:** Cannot calculate Sharpe Ratio, Sortino Ratio, Profit Factor, Expectancy, or perform meaningful statistical analysis. Cannot identify which setups, timeframes, or market regimes produce the best results.

### CRITICAL-8: No Performance Metrics Calculation
**Severity:** HIGH  
**Location:** Portfolio + reporting  
**Issue:** The system tracks basic win/loss counts and average P&L, but does NOT calculate:
- Sharpe Ratio
- Sortino Ratio
- Profit Factor
- Expectancy
- Max Drawdown
- Average Trade Duration
- Performance by Setup Type
- Performance by Timeframe
- Performance by Market Regime
- Performance by Signal Grade
- Consecutive Win/Loss Streaks
- Recovery Factor

The portfolio page shows: total P&L, active P&L, closed P&L, win rate, wins, losses. This is insufficient for institutional-grade reporting.

### CRITICAL-9: Signal Expiry Logic Inconsistency
**Severity:** MEDIUM  
**Location:** `src/main.py:793-818` + `src/config.py:62`  
**Issue:**
1. `check_expired_signals()` runs every 1 minute checking ALL pending signals
2. `SIGNAL_EXPIRY_MINUTES` is set to 120 (recently changed from 30)
3. `on_signal_approved()` has special handling for expired signals (extends expiry by 30 min if admin approves past expiry)
4. BUT: there's no mechanism to clean up signals that are `APPROVED` (limit orders waiting for fill) but have been waiting too long. A limit order could be `APPROVED` for days if the price never hits entry.

**Impact:** Stale limit orders accumulate in the `approved` state. They show up in the dashboard as "Pending Entry" indefinitely. No auto-cancellation for limit orders that never fill.

### CRITICAL-10: Alpha Plays Price Lookup Failures
**Severity:** MEDIUM  
**Location:** `src/alpha_plays/alpha_engine.py`  
**Issue:** Alpha plays for tokens like SOL and PROS fail with "No token/pair address for SOL, cannot fetch price". The alpha engine cannot look up prices for many tokens because it lacks DEX pair address mappings.

**Impact:** Alpha plays cannot be tracked for TP/SL. The dashboard shows warnings every 5 minutes.

---

## 3. SECURITY AUDIT

### SEC-1: No API Authentication on Dashboard
**Severity:** CRITICAL  
**Location:** `src/admin/dashboard_server.py`  
**Issue:** The FastAPI dashboard has ZERO authentication. Anyone who knows the port can access:
- `/api/signals/active` — all active trades
- `/api/portfolio` — full trade history with P&L
- `/api/account` — live exchange balances and positions
- `/api/marketing/...` — marketing controls
- Manual triggers for scheduled jobs (reports, scans, etc.)

**Impact:** Complete data exposure. An attacker could view sensitive trading data, trigger unwanted reports, or manipulate marketing campaigns.

### SEC-2: Secrets in Environment Variables (Acceptable with caveats)
**Severity:** LOW  
**Location:** `.env` file  
**Issue:** API keys, tokens, and secrets are loaded from `.env` via pydantic-settings. This is standard practice, but:
- No validation that secrets meet minimum length/complexity
- No rotation warnings or expiry tracking
- `extra = "ignore"` in model_config means unknown env vars are silently ignored (could mask misconfigurations)

### SEC-3: No Input Validation on Dashboard APIs
**Severity:** HIGH  
**Location:** `src/admin/dashboard_server.py`  
**Issue:** Most dashboard endpoints accept query parameters and request bodies without:
- Type validation beyond FastAPI's automatic parsing
- Rate limiting
- Request size limits
- SQL injection protection (Supabase client uses parameterized queries, which is good)
- XSS protection on rendered HTML

### SEC-4: SSH Key Exposure Risk
**Severity:** MEDIUM  
**Location:** Project root  
**Issue:** SSH private keys (`ssh-key-2026-05-20.key`, etc.) are stored in the project directory and could be accidentally committed to git. The `.gitignore` does not explicitly exclude `.key` files.

### SEC-5: No Audit Logging for Admin Actions
**Severity:** MEDIUM  
**Location:** Dashboard + admin bot  
**Issue:** When admin approves/rejects signals via Telegram or dashboard, the action is logged to the console but NOT to a persistent audit log. There's no record of:
- WHO approved/rejected a signal
- WHEN the action was taken
- WHAT the signal parameters were at the time
- Any manual overrides (e.g., approving past expiry)

---

## 4. PERFORMANCE AUDIT

### PERF-1: Synchronous DB Calls in Loops
**Severity:** MEDIUM  
**Location:** `src/admin/dashboard_server.py:/api/portfolio`  
**Issue:** The portfolio endpoint loops through ALL signals and makes a `get_current_price()` call for EACH active/approved signal. For 50 active signals, that's 50 API calls to Binance.

```python
for s in all_signals:
    if status_val == 'active':
        current_price = await orch._get_current_price(s.symbol)  # HTTP call per signal
```

**Impact:** Portfolio page load time increases linearly with signal count. Could timeout with many signals.

### PERF-2: No Caching Layer
**Severity:** MEDIUM  
**Location:** Throughout  
**Issue:** No Redis, in-memory cache, or any caching strategy. Every API call:
- Fetches prices fresh from Binance
- Loads signals fresh from Supabase
- Re-generates charts on every approval request

### PERF-3: Inefficient Signal Scanning
**Severity:** LOW  
**Location:** `src/engine/signal_engine.py:91-102`  
**Issue:** `analyze_pair()` is called sequentially for up to 100 symbols with a 0.2s sleep between each. For 100 symbols, this takes ~20 seconds minimum.

```python
for symbol in pairs[:100]:
    signal = await self.analyze_pair(symbol, timeframe)
    await asyncio.sleep(0.2)  # Rate limiting
```

**Impact:** Scan jobs take longer than necessary. No parallelization of symbol analysis.

### PERF-4: Chart Regeneration on Every Approval
**Severity:** LOW  
**Location:** `src/telegram_bot/admin_bot.py:301`  
**Issue:** `send_signal_for_approval()` generates a chart EVERY time it's called. On restart, all pending signals are resent for approval, regenerating all charts.

### PERF-5: Missing Database Indexes
**Severity:** MEDIUM  
**Location:** Supabase schema  
**Issue:** Common queries lack optimal indexing:
- `get_active_signals()` queries by `status` — needs index on `status`
- `get_pending_signals()` queries by `status` — same
- `get_signal_by_symbol()` queries by `symbol` — needs index on `symbol`
- `get_closed_signals()` queries by `status` and date — needs composite index

---

## 5. SCALABILITY CONCERNS

### SCALE-1: Single-Process Architecture
**Severity:** MEDIUM  
**Issue:** The entire system runs in a single Python process. Signal scanning, trade tracking, marketing, reporting, and dashboard serving all share the same event loop. Under high load, one slow component blocks everything.

### SCALE-2: In-Memory State is Not Distributed
**Severity:** MEDIUM  
**Issue:** Critical state lives in memory:
- `admin_bot.pending_signals` dict
- `autopilot.pending_limit_orders` dict
- `autopilot.active_signals` dict
- `autopilot.pending_limit_extremes` dict
- `orchestrator._pending_limit_extremes` dict
- `orchestrator.tp_hit_cache` dict

If the process crashes or is restarted, all this state is lost. The DB is the only persistent source of truth.

### SCALE-3: No Horizontal Scaling Path
**Severity:** LOW  
**Issue:** The system cannot run multiple instances simultaneously because:
- APScheduler jobs would duplicate (each instance would run scans)
- In-memory state would diverge between instances
- Telegram bot polling can only run on one instance

---

## 6. TECHNICAL DEBT

### DEBT-1: Massive `main.py` (1824 lines)
**Issue:** The orchestrator handles initialization, scheduling, scanning, signal lifecycle, reporting, marketing, alpha plays, AND dashboard integration. It violates the Single Responsibility Principle.

### DEBT-2: Hardcoded Thresholds Scattered Throughout
**Issue:** Confidence thresholds, R:R thresholds, volume thresholds, and session requirements are scattered across:
- `src/config.py` (some)
- `src/analysis/timeframe_strategies.py` (timeframe-specific)
- `src/utils/signal_validator.py` (validation thresholds)
- `src/engine/signal_engine.py` (confluence scoring)
- `src/marketing/autopilot_system.py` (tracking thresholds)

There's no central "Signal Quality Policy" that governs all thresholds.

### DEBT-3: DB Column Stripping on Save
**Issue:** `save_signal()` has a retry loop that strips columns that don't exist in the DB. This is a workaround for schema drift, but it masks real migration needs and can cause data loss if critical fields are stripped.

### DEBT-4: Alpha Plays UNKNOWN Symbols
**Issue:** Alpha plays sometimes have `symbol = "UNKNOWN"` in the DB (visible in logs: "Restored pending alpha play from DB: UNKNOWN"). This indicates incomplete data handling during alpha discovery.

### DEBT-5: Correlation Groups are Static
**Issue:** `CORRELATION_GROUPS` in `signal_engine.py` is a hardcoded dictionary. As new correlated pairs emerge (e.g., AI coins, L2 tokens), this list becomes stale.

### DEBT-6: No Unit Tests for Critical Paths
**Issue:** The `tests/` directory has minimal coverage. Critical paths like signal generation, trade tracking, and status transitions have no automated tests.

---

## 7. MISSING FEATURES (Required by Objective)

### MISSING-1: Signal Validation Pipeline (8-Stage)
**Status:** NOT IMPLEMENTED  
**Required:** Stage-by-stage validation with automatic rejection

### MISSING-2: Signal Grade System (A+/A/B/C/Rejected)
**Status:** NOT IMPLEMENTED  
**Required:** Weighted scoring across categories with explainable grades

### MISSING-3: Trade Analytics (MDD, MAE, Duration, Slippage)
**Status:** NOT IMPLEMENTED  
**Required:** Comprehensive trade-level analytics

### MISSING-4: Performance Metrics (Sharpe, Sortino, Profit Factor, Expectancy)
**Status:** NOT IMPLEMENTED  
**Required:** Institutional-grade performance reporting

### MISSING-5: AI Assistance Layer
**Status:** PARTIALLY IMPLEMENTED  
**Current:** `signal.reasoning` contains institutional-grade trade plans  
**Missing:** AI-generated market summaries, educational content, report generation

### MISSING-6: Audit Logs for Admin Actions
**Status:** NOT IMPLEMENTED

### MISSING-7: Rate Limiting on Dashboard APIs
**Status:** NOT IMPLEMENTED

### MISSING-8: Dashboard Authentication
**Status:** NOT IMPLEMENTED

---

## 8. POSITIVE FINDINGS

### GOOD-1: Well-Structured Signal Generation Pipeline
The `analyze_pair()` method follows a clear 13-stage institutional analysis flow with proper gating at each stage.

### GOOD-2: Execution Strategy Logic
The limit vs market order determination is sophisticated, considering setup type, price distance, and volatility.

### GOOD-3: Comprehensive Telegram Integration
Multiple bots (admin, VIP, channel publisher), rich message formatting, and approval workflows.

### GOOD-4: Marketing Automation
Extensive marketing engine with social media, Discord, viral content, community engagement, and referral tracking.

### GOOD-5: Pro Features
Whale alerts, educational content, custom price alerts, giveaways, bonus reports.

### GOOD-6: Exchange Account Monitoring
Read-only cTrader and MEXC clients for live portfolio tracking.

### GOOD-7: Signal Persistence
All signals are saved to Supabase, surviving restarts. Active trades are restored on startup.

---

## 9. PRIORITIZED CHANGE PLAN

### TIER 0: CRITICAL BUG FIXES (Do First — Production Stability)
| # | Task | Impact |
|---|------|--------|
| 0.1 | ~~Fix limit order status flickering~~ | ✅ DONE |
| 0.2 | ~~Fix portfolio false P&L~~ | ✅ DONE |
| 0.3 | ~~Add missing save_signals_batch~~ | ✅ DONE |
| 0.4 | Add dashboard authentication | 🔒 Security |
| 0.5 | Fix dual TP/SL tracking race condition | 🎯 Accuracy |
| 0.6 | Add limit order auto-cancellation (stale orders) | 🧹 Cleanup |
| 0.7 | Add SSH keys to .gitignore | 🔒 Security |
| 0.8 | Fix alpha plays price lookup | 🎰 Alpha |

### TIER 1: SIGNAL QUALITY INFRASTRUCTURE
| # | Task | Impact |
|---|------|--------|
| 1.1 | Build 8-Stage Signal Validation Pipeline | 🎯 Quality |
| 1.2 | Implement Signal Grade System (A+/A/B/C/Rejected) | 🎯 Quality |
| 1.3 | Centralize all thresholds in config | 🔧 Maintainability |
| 1.4 | Add setup performance tracking to DB | 📊 Analytics |

### TIER 2: TRADE DATA & ANALYTICS
| # | Task | Impact |
|---|------|--------|
| 2.1 | Add MDD, MAE, Duration, Slippage to TradingSignal model | 📊 Analytics |
| 2.2 | Calculate Sharpe, Sortino, Profit Factor, Expectancy | 📊 Analytics |
| 2.3 | Track performance by Setup, Timeframe, Regime, Grade | 📊 Analytics |
| 2.4 | Build trade audit log | 🔍 Transparency |

### TIER 3: ADMIN DASHBOARD
| # | Task | Impact |
|---|------|--------|
| 3.1 | Add dashboard login/auth | 🔒 Security |
| 3.2 | Add signal review/audit tools | 🔍 Transparency |
| 3.3 | Add performance analytics charts | 📊 Analytics |
| 3.4 | Add system health monitoring | 🔧 Ops |
| 3.5 | Add rate limiting to APIs | 🔒 Security |

### TIER 4: PERFORMANCE & SCALABILITY
| # | Task | Impact |
|---|------|--------|
| 4.1 | Add price caching (TTL 30s) | ⚡ Speed |
| 4.2 | Parallelize signal scanning | ⚡ Speed |
| 4.3 | Add DB indexes | ⚡ Speed |
| 4.4 | Add request caching for dashboard | ⚡ Speed |

### TIER 5: AI ASSISTANCE LAYER
| # | Task | Impact |
|---|------|--------|
| 5.1 | AI-generated daily market summary | 🤖 AI |
| 5.2 | AI-generated educational content | 🤖 AI |
| 5.3 | AI signal explanation enhancement | 🤖 AI |

---

## 10. ROLLBACK STRATEGY

Every change must follow this pattern:
1. **Feature branch** — never commit directly to main without testing
2. **Database migrations** — always backwards-compatible (add columns, don't drop)
3. **Feature flags** — new logic should be toggleable via config
4. **Staged deployment** — deploy to Oracle, monitor logs for 24h before declaring stable
5. **Rollback plan** — each change has a documented rollback procedure

---

*End of Audit Report*
