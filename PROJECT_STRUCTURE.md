# CryptoPulse Signals — Project Structure Map

> **Purpose**: This document provides a complete, non-developer-friendly map of the entire CryptoPulse Signals project. It explains what every folder and file does, how the pieces connect, and which parts are critical to keep the system running.
> 
> **Last Updated**: 2026-05-23
> **Total Files Analyzed**: ~90+ files
> **Project Type**: Live Production Trading Signal Bot + Dashboard

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Directory Structure](#directory-structure)
3. [Core Systems](#core-systems)
4. [Services & APIs](#services--apis)
5. [Database & Models](#database--models)
6. [Admin Systems](#admin-systems)
7. [Signal Systems](#signal-systems)
8. [Telegram Systems](#telegram-systems)
9. [Marketing Systems](#marketing-systems)
10. [Payment Systems](#payment-systems)
11. [Analysis & Scanner](#analysis--scanner)
12. [Alpha Plays System](#alpha-plays-system)
13. [Landing Page](#landing-page)
14. [Utilities & Helpers](#utilities--helpers)
15. [Scripts & Batch Files](#scripts--batch-files)
16. [Documentation Files](#documentation-files)
17. [Dependency Map](#dependency-map)

---

## Project Overview

**CryptoPulse Signals** is a fully automated cryptocurrency trading signal platform that:

- **Scans** the market for high-probability trade setups
- **Analyzes** signals using technical, fundamental, and sentiment analysis
- **Publishes** signals to VIP (paid) and Free Telegram channels
- **Tracks** active trades and sends TP/SL hit notifications
- **Manages** VIP subscriptions via Stripe and crypto payments
- **Markets** the service through social media and viral campaigns
- **Provides** an Admin Dashboard for monitoring and control

**The system runs in two modes:**
1. **Full Bot Mode** (`START_BOT.bat`) — Runs all Telegram bots, schedulers, and background jobs (Oracle live instance)
2. **Dashboard-Only Mode** (`START_DASHBOARD.bat`) — Runs only the admin web dashboard (local development)

---

## Directory Structure

```
CryptoPulse-Signals/
│
├── src/                          ← Main application code (Python)
│   ├── admin/                    ← Admin dashboard server
│   ├── alpha_plays/              ← Alpha/Degen plays system (SOL/ETH low-caps)
│   ├── analysis/                 ← Market analysis engines
│   ├── database/                 ← Database client and migrations
│   ├── engine/                   ← Core signal generation engine
│   ├── exchange/                 ← Exchange integrations (MEXC, Binance, etc.)
│   ├── marketing/                ← Marketing automation & viral growth
│   ├── models/                   ← Data models (Signal, Trade, etc.)
│   ├── payments/                 ← Payment processing (Stripe, Crypto)
│   ├── scanner/                  ← Market scanning & discovery
│   ├── telegram_bot/             ← Telegram bot implementations
│   ├── utils/                    ← Utility functions & helpers
│   ├── config.py                 ← Configuration & settings loader
│   └── main.py                   ← Application entry point (2081 lines)
│
├── landing-page/                 ← Public marketing website
│   ├── index.html                ← Main landing page
│   ├── style.css                 ← Stylesheet
│   └── images/                   ← Landing page images
│
├── tests/                        ← Test files (minimal coverage)
│   ├── __init__.py
│   ├── test_alpha_plays.py
│   ├── test_telegram.py
│   └── test_technical_analyzer.py
│
├── charts/                       ← Generated chart images (runtime)
├── generated_content/            ← Generated viral content images (runtime)
├── data/                         ← Data storage (runtime)
├── logs/                         ← Log files (runtime)
│
├── scripts/                      ← Setup and utility scripts
│   ├── setup_database.py         ← Database initialization
│   ├── setup_bot.py              ← Bot setup helper
│   ├── quick_deploy.py           ← Quick deployment script
│   └── backup_database.py        ← Database backup utility
│
├── docs/                         ← Project documentation
│   ├── API_INTEGRATION_GUIDE.md
│   ├── AUTOPILOT_SETUP.md
│   ├── DEPLOY_ORACLE.md
│   ├── MEXC_INTEGRATION.md
│   ├── SETUP_ENVIRONMENT.md
│   ├── SIGNALS_README.md
│   ├── SUPABASE_SETUP.md
│   ├── TELEGRAM_BOT_GUIDE.md
│   ├── TWITTER_DMS.md
│   ├── USER_GUIDE.md
│   ├── VIRAL_MARKETING_SETUP.md
│   └── WALLET_SETUP_GUIDE.md
│
├── .env                          ← Environment variables (API keys, tokens)
├── requirements.txt              ← Python dependencies
├── config.json                   ← App configuration (JSON format)
├── vercel.json                   ← Vercel deployment config
│
├── START_BOT.bat                 ← Start full bot (production)
├── START_DASHBOARD.bat           ← Start dashboard only (development)
├── DEPLOY_ORACLE.bat             ← Deploy to Oracle VPS
├── test.bat                      ← Run tests
├── setup.bat                     ← Initial setup
│
├── verify_setup.py               ← Setup verification script
├── requirements-vercel.txt       ← Vercel-specific dependencies
└── PROJECT_STRUCTURE.md          ← This file
```

---

## Core Systems

### Main Application Entry Point

**File**: `src/main.py` (2081 lines, ~97KB)
**Category**: CATEGORY A — Critical Production File
**Purpose**: The brain of the entire system. Initializes all components, starts the scheduler, and manages the application lifecycle.

**What it does:**
- Loads configuration from environment variables
- Initializes the Signal Engine, Admin Bot, VIP Bot, and all marketing systems
- Sets up APScheduler jobs (runs every 5 minutes):
  - Scan markets for new signals
  - Track active plays (check TP/SL hits)
  - Run viral marketing campaigns
  - Send social proof messages
- Starts the Admin Dashboard server
- Handles graceful shutdown

**Key Components Initialized:**
- `SignalEngine` — Core signal generation and tracking
- `AdminBot` — Admin Telegram bot for approving/rejecting signals
- `VIPBot` — Public VIP signup and payment bot
- `ChannelPublisher` — Publishes signals to Telegram channels
- `AlphaPlaysEngine` — Alpha/Degen plays system
- `CampaignEngine` — Marketing campaigns
- `AutoPilotSystem` — Automated marketing
- `ViralGrowthEngine` — Viral marketing
- `TrafficTracker` & `ReferralTracker` — Analytics
- `PaymentOrchestrator` — Payment processing
- `SupabaseClient` — Database operations

---

### Configuration System

**File**: `src/config.py` (~8.5KB)
**Category**: CATEGORY A — Critical Production File
**Purpose**: Centralized settings management using Pydantic. Loads from environment variables.

**Key Settings Groups:**
- Telegram tokens and channel IDs
- Database credentials (Supabase)
- Exchange API keys (MEXC, Binance)
- Payment keys (Stripe, NOWPayments)
- OpenAI API key (for AI content generation)
- Feature flags (enable/disable systems)

---

## Services & APIs

### Database Service

**File**: `src/database/supabase_client.py` (~50KB+)
**Category**: CATEGORY A — Critical Production File
**Purpose**: All database operations. Connects to Supabase (PostgreSQL).

**Key Methods:**
- `save_signal()` — Store new trading signals
- `update_signal_status()` — Update signal state (pending → approved → closed)
- `save_alpha_play()` — Store alpha/degen plays
- `get_active_signals()` — Retrieve active trades
- `get_signal_history()` — Retrieve historical trades
- `get_active_plays()` — Retrieve active alpha plays
- `save_payment()` — Record payment transactions

**Database Tables Used:**
- `signals` — Main trading signals
- `alpha_plays` — Alpha/Degen plays
- `payments` — Payment records
- `analytics` — Marketing analytics
- `users` — VIP user management

---

### Exchange Integration

**Files**: `src/exchange/mexc_client.py`, `src/exchange/binance_client.py`
**Category**: CATEGORY B — Required Dependencies
**Purpose**: Connect to cryptocurrency exchanges for price data and order info.

**MEXC Client:**
- Fetches real-time prices
- Gets order book data
- Retrieves kline/candlestick data
- Used for signal generation and tracking

**Binance Client:**
- Alternative price source
- Used for whale monitoring and institutional analysis

---

## Database & Models

### Signal Models

**File**: `src/models/signal.py`
**Category**: CATEGORY A — Critical Production File
**Purpose**: Defines the data structures for trading signals.

**Key Classes:**
- `TradingSignal` — Main signal with entry, SL, TP1-3, symbol, direction
- `SignalCandidate` — Raw candidate before validation
- `SignalStatus` — Enum: pending, approved, rejected, active, closed
- `SignalGrade` — Enum: A+, A, B, C, REJECTED
- `SignalDirection` — Enum: LONG, SHORT
- `SetupType` — Enum: liquidity_sweep, breakout_retest, fair_value_gap, etc.

### Alpha Play Models

**Files**: `src/alpha_plays/alpha_discovery.py`, `src/alpha_plays/alpha_engine.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Models for alpha/degen plays (SOL/ETH low-cap tokens).

**Key Classes:**
- `AlphaPlayCandidate` — Discovered low-cap opportunity
- `ActiveAlphaPlay` — Approved play being tracked
- `AlphaPlaysEngine` — Main engine for discovery → approval → tracking → closing

---

## Admin Systems

### Admin Dashboard Server

**File**: `src/admin/dashboard_server.py` (~30KB+)
**Category**: CATEGORY A — Critical Production File
**Purpose**: Web-based admin panel accessible at `http://localhost:8081`

**What it does:**
- Provides REST API endpoints for the dashboard frontend
- Serves static HTML/CSS/JS files
- Handles signal approval/rejection via web UI
- Shows active trades, portfolio, and analytics
- Manages alpha plays
- Displays system health and logs

**Key Endpoints:**
- `/` — Dashboard home
- `/api/signals` — List signals
- `/api/signals/approve` — Approve a signal
- `/api/signals/reject` — Reject a signal
- `/api/alpha/plays` — List alpha plays
- `/api/stats` — System statistics

---

## Signal Systems

### Signal Engine

**File**: `src/engine/signal_engine.py`
**Category**: CATEGORY A — Critical Production File
**Purpose**: Core signal generation, validation, and lifecycle management.

**What it does:**
1. **Discovery**: Scans markets for potential setups
2. **Validation**: Checks signal quality (grades A+ to C)
3. **Approval**: Admin approval via bot or dashboard
4. **Publishing**: Sends to VIP and Free Telegram channels
5. **Tracking**: Monitors active trades for TP/SL hits
6. **Closing**: Sends close notifications and archives

**Key Classes:**
- `SignalEngine` — Main orchestrator
- Handles signal lifecycle from discovery to close

---

### Market Scanner

**File**: `src/scanner/market_scanner.py`
**Category**: CATEGORY B — Required Dependency
**Purpose**: Scans cryptocurrency markets for trading opportunities.

**What it does:**
- Fetches price data from exchanges
- Identifies technical patterns (breakouts, liquidity sweeps)
- Filters by volume, volatility, and trend
- Returns `SignalCandidate` objects

---

### Technical Analysis

**Files**: `src/analysis/technical_analyzer.py`, `src/analysis/timeframe_strategies.py`
**Category**: CATEGORY B — Required Dependency
**Purpose**: Calculates technical indicators and scores.

**Key Indicators:**
- RSI, MACD, EMA, Bollinger Bands
- Support/Resistance levels
- Trend strength
- Volume analysis

---

## Telegram Systems

### Channel Publisher

**File**: `src/telegram_bot/channel_publisher.py`
**Category**: CATEGORY A — Critical Production File
**Purpose**: Publishes signals and updates to Telegram channels.

**Key Methods:**
- `publish_to_vip()` — Send signal to VIP channel (with chart)
- `publish_to_free()` — Send teaser to Free channel
- `send_tp_hit()` — Notify when Take Profit is hit
- `send_sl_hit()` — Notify when Stop Loss is hit
- `send_trade_closed()` — Final close notification

**VIP vs Free Difference:**
- **VIP**: Full signal with entry price, SL, TP1-3, chart image
- **Free**: Teaser with symbol, direction, and VIP signup CTA

---

### Admin Bot

**File**: `src/telegram_bot/admin_bot.py`
**Category**: CATEGORY A — Critical Production File
**Purpose**: Admin-facing Telegram bot for signal management.

**What it does:**
- Receives signal alerts for approval/rejection
- Sends admin commands (/start, /stats, /approve, /reject)
- Forwards approved signals to ChannelPublisher

---

### VIP Bot

**File**: `src/telegram_bot/vip_bot.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Public-facing bot for VIP signups and payments.

**What it does:**
- Handles /start and /subscribe commands
- Processes payment links (Stripe/Crypto)
- Manages user subscriptions

---

### Marketing Automation

**File**: `src/telegram_bot/marketing_automation.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Generates marketing content for the Free channel.

**What it does:**
- Creates viral-style posts
- Runs engagement campaigns
- Schedules social proof messages

---

### Chart Generator

**File**: `src/telegram_bot/chart_generator.py`
**Category**: CATEGORY B — Required Dependency
**Purpose**: Generates trading chart images for signals.

**What it does:**
- Creates candlestick charts with entry/SL/TP levels
- Saves images to `charts/` directory
- Attaches charts to Telegram messages

---

### Reporting Engine

**File**: `src/telegram_bot/reporting.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Generates performance reports.

**What it does:**
- Calculates win rate, profit factor, average R:R
- Creates weekly/monthly summary reports
- Formats reports for Telegram

---

## Marketing Systems

### Campaign Engine

**File**: `src/marketing/campaign_engine.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Orchestrates marketing campaigns.

**Key Campaigns:**
- `signal_approved_campaign()` — Promotes newly approved signals
- `tp_hit_campaign()` — Celebrates winning trades
- `social_proof_campaign()` — Shows track record and drives signups
- `urgency_campaign()` — Creates FOMO for limited spots

---

### AutoPilot System

**File**: `src/marketing/autopilot_system.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Fully automated marketing that runs without manual intervention.

**What it does:**
- Automatically detects winning trades
- Generates and sends marketing messages
- Schedules posts across channels
- Manages referral CTAs

---

### Viral Growth Engine

**File**: `src/marketing/viral_growth_engine.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Pushes signals to multiple platforms for free exposure.

**Platforms:**
- Twitter/X
- Discord
- Reddit
- Other social channels

---

### Traffic Tracker

**File**: `src/marketing/traffic_tracker.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Tracks where users come from and conversion rates.

**Key Classes:**
- `TrafficTracker` — Attribution and funnel analysis
- `ReferralTracker` — Invite referral tracking

---

### Pro Features

**File**: `src/marketing/pro_features.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Premium features for Pro+ members.

**Features:**
- `WhaleAlertSystem` — Large order notifications
- `EducationalContentEngine` — Trading education posts
- `CustomAlertSystem` — User-defined price alerts
- `GiveawayEngine` — VIP giveaways
- `BonusReportEngine` — Exclusive reports

---

## Payment Systems

### Payment Orchestrator

**File**: `src/payments/payment_orchestrator.py`
**Category**: CATEGORY A — Critical Production File
**Purpose**: Central payment routing and management.

**What it does:**
- Routes users to Stripe (card) or NOWPayments (crypto)
- Manages subscription tiers (Monthly, Lifetime, Pro+)
- Handles webhook callbacks
- Tracks payment status

---

### Stripe Handler

**File**: `src/payments/stripe_handler.py`
**Category**: CATEGORY B — Required Dependency
**Purpose**: Processes card payments via Stripe.

**What it does:**
- Creates checkout sessions
- Handles subscription renewals
- Processes webhook events
- Manages customer records

---

### Crypto Payment Handler

**File**: `src/payments/crypto_payment_handler.py`
**Category**: CATEGORY C — Feature File
**Purpose**: Processes cryptocurrency payments via NOWPayments.

**What it does:**
- Creates crypto payment invoices
- Supports BTC, ETH, USDT, SOL
- Handles payment confirmations

---

## Alpha Plays System

### Overview
The Alpha Plays system is a separate, isolated module for high-risk, high-reward low-cap cryptocurrency plays (primarily SOL and ETH chain tokens). It does NOT interfere with the main signal engine.

### Files:
- `src/alpha_plays/__init__.py` — Module exports
- `src/alpha_plays/alpha_discovery.py` — Discovers low-cap opportunities
- `src/alpha_plays/alpha_engine.py` — Manages play lifecycle
- `src/alpha_plays/alpha_publisher.py` — Publishes to Telegram
- `src/alpha_plays/content_formatter.py` — Formats messages

**Category**: CATEGORY C — Feature File

---

## Landing Page

### Public Marketing Website

**Location**: `landing-page/`
**Category**: CATEGORY C — Feature File
**Purpose**: Sells the VIP subscription to visitors.

**Files:**
- `index.html` — Main landing page
- `style.css` — Styling
- `images/` — Hero images and logos

**What it shows:**
- Track record and performance stats
- Pricing tiers (Monthly, Lifetime, Pro+)
- Testimonials and social proof
- Payment CTA buttons

---

## Utilities & Helpers

### AI Content Generator

**File**: `src/utils/ai_content_generator.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Generates marketing copy using OpenAI GPT-4o-mini.

**Note**: Gracefully degrades if OpenAI package is missing or API key is not set.

---

### Signal Validator

**File**: `src/utils/signal_validator.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Validates signal quality before processing.

---

### Signal Validation Pipeline

**File**: `src/utils/signal_validation_pipeline.py`
**Category**: CATEGORY D — Utility File
**Purpose**: 8-stage validation scoring system for signals.

---

### Portfolio Analytics

**File**: `src/utils/portfolio_analytics.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Calculates portfolio-level trading metrics (win rate, profit factor, Sharpe ratio).

---

### Logger

**File**: `src/utils/logger.py`
**Category**: CATEGORY A — Critical Production File
**Purpose**: Centralized logging using Loguru. All modules use this.

---

### Validators

**File**: `src/utils/validators.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Input validation helpers.

---

### Retry Helper

**File**: `src/utils/retry_helper.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Retry logic with exponential backoff for API calls.

---

### Cleanup Manager

**File**: `src/utils/cleanup.py`
**Category**: CATEGORY D — Utility File
**Purpose**: Cleans up old chart images and log files to prevent disk space issues.

---

## Scripts & Batch Files

### Production Scripts

| File | Purpose | When to Use |
|------|---------|-------------|
| `START_BOT.bat` | Starts full bot (all Telegram bots, scheduler, dashboard) | Production — Oracle VPS |
| `START_DASHBOARD.bat` | Starts dashboard only | Local development/testing |
| `DEPLOY_ORACLE.bat` | Deploys to Oracle cloud VPS | Production deployments |

### Setup Scripts

| File | Purpose |
|------|---------|
| `setup.bat` | Initial project setup |
| `test.bat` | Run test suite |
| `verify_setup.py` | Verify environment is correctly configured |
| `scripts/setup_database.py` | Initialize database tables |
| `scripts/setup_bot.py` | Configure Telegram bots |
| `scripts/quick_deploy.py` | Quick deployment helper |
| `scripts/backup_database.py` | Backup database |

---

## Documentation Files

All docs are in the `docs/` directory:

| File | Purpose |
|------|---------|
| `API_INTEGRATION_GUIDE.md` | How to integrate with external APIs |
| `AUTOPILOT_SETUP.md` | Setting up autopilot marketing |
| `DEPLOY_ORACLE.md` | Deploying to Oracle VPS |
| `MEXC_INTEGRATION.md` | MEXC exchange setup |
| `SETUP_ENVIRONMENT.md` | Environment setup instructions |
| `SIGNALS_README.md` | How signals work |
| `SUPABASE_SETUP.md` | Database configuration |
| `TELEGRAM_BOT_GUIDE.md` | Telegram bot setup |
| `TWITTER_DMS.md` | Twitter DM automation |
| `USER_GUIDE.md` | End-user guide |
| `VIRAL_MARKETING_SETUP.md` | Viral growth setup |
| `WALLET_SETUP_GUIDE.md` | Crypto wallet setup |

---

## Dependency Map

### What Imports What

```
main.py
├── engine/signal_engine.py
│   ├── analysis/technical_analyzer.py
│   ├── scanner/market_scanner.py
│   └── models/signal.py
├── telegram_bot/channel_publisher.py
│   ├── telegram_bot/chart_generator.py
│   └── models/signal.py
├── telegram_bot/admin_bot.py
├── telegram_bot/vip_bot.py
├── telegram_bot/marketing_automation.py
├── telegram_bot/reporting.py
├── marketing/campaign_engine.py
├── marketing/autopilot_system.py
├── marketing/viral_growth_engine.py
├── marketing/pro_features.py
├── marketing/social_media_poster.py
├── marketing/traffic_tracker.py
├── alpha_plays/alpha_engine.py
│   ├── alpha_plays/alpha_discovery.py
│   ├── alpha_plays/alpha_publisher.py
│   └── alpha_plays/content_formatter.py
├── payments/payment_orchestrator.py
│   ├── payments/stripe_handler.py
│   └── payments/crypto_payment_handler.py
├── database/supabase_client.py
├── utils/ai_content_generator.py
├── utils/signal_validator.py
├── utils/cleanup.py
├── utils/logger.py
├── utils/validators.py
└── config.py
    └── .env (environment variables)

admin/dashboard_server.py
├── database/supabase_client.py
├── engine/signal_engine.py
└── config.py
```

### Critical Dependencies (If Removed, System Breaks)

1. `src/main.py` — Entry point
2. `src/config.py` — Settings loader
3. `src/database/supabase_client.py` — Database
4. `src/engine/signal_engine.py` — Signal core
5. `src/telegram_bot/channel_publisher.py` — Telegram publishing
6. `src/telegram_bot/admin_bot.py` — Admin control
7. `src/models/signal.py` — Data models
8. `src/utils/logger.py` — Logging

---

## Quick Reference for Non-Developers

### If you need to...

| Task | File/Location |
|------|---------------|
| Change API keys or tokens | `.env` file |
| Change Telegram channel IDs | `.env` file |
| Adjust signal settings | `src/config.py` or `config.json` |
| View active trades | Admin Dashboard (`http://localhost:8081`) |
| Approve a signal | Admin Bot (Telegram) or Dashboard |
| Check system logs | `logs/` directory |
| View generated charts | `charts/` directory |
| Update landing page | `landing-page/index.html` |
| Change pricing | `landing-page/index.html` or `src/payments/` |
| Add a new exchange | `src/exchange/` |
| Modify signal messages | `src/telegram_bot/channel_publisher.py` |
| Change marketing text | `src/marketing/campaign_engine.py` |

---

## File Size Summary

| Category | Total Files | Approx Size |
|----------|-------------|-------------|
| Core (src/) | ~50 Python files | ~500KB |
| Tests | 4 files | ~20KB |
| Landing Page | 3+ files | ~50KB |
| Documentation | 12 files | ~100KB |
| Scripts | 4 files | ~30KB |
| Config/Batch | 8 files | ~10KB |
| **Total** | **~90 files** | **~710KB** |

---

*This document is maintained as part of the codebase audit. Update when adding new features or restructuring.*
