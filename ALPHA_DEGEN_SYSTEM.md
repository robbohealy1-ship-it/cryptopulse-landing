# 🎰 ALPHA/DEGEN PLAYS SYSTEM - IMPLEMENTATION COMPLETE

**Date:** May 18, 2026  
**Status:** ✅ IMPLEMENTED

---

## 🎯 WHAT WAS BUILT

A complete **Alpha/Degen Plays System** for finding and publishing low-cap, high-reward plays on SOL and ETH chains.

---

## 🏗️ SYSTEM ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────┐
│              ALPHA DISCOVERY ENGINE                          │
│  (src/alpha_plays/alpha_discovery.py)                        │
├──────────────────────────────────────────────────────────────┤
│ • DexScreener API integration                                 │
│ • Social sentiment scanning                                   │
│ • On-chain activity analysis                                  │
│ • Community growth metrics                                    │
│ • Volume/momentum anomalies                                   │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│              ALPHA PLAYS ENGINE                              │
│  (src/alpha_plays/alpha_engine.py)                          │
├──────────────────────────────────────────────────────────────┤
│ • Discovery → Approval → Publishing → Tracking → Closing    │
│ • Rate limiting (VIP: 1/day, FREE: 1/week)                  │
│ • Auto-approval for high-score plays (85+)                   │
│ • TP/SL monitoring every 5 minutes                          │
│ • P&L tracking in real-time                                 │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         ▼                            ▼
┌─────────────────────┐     ┌────────────────────────────┐
│   VIP DEGEN CHANNEL │     │    FREE DEGEN CHANNEL      │
│                     │     │                            │
│ • 1 play per day    │     │ • 1 play per week          │
│ • Full signal       │     │ • Teaser only              │
│ • Entry/SL/TP1/TP2  │     │ • Drives VIP signups       │
│ • DEX buy links     │     │ • Marketing content        │
│ • Position sizing   │     │                            │
└─────────────────────┘     └────────────────────────────┘
```

---

## 📁 NEW FILES CREATED

### Core Alpha Module (`src/alpha_plays/`)

1. **`__init__.py`**
   - Module exports
   - Clean imports

2. **`alpha_discovery.py`**
   - `AlphaPlayCandidate` dataclass
   - `AlphaDiscovery` class
   - DexScreener API integration
   - Social sentiment scanning
   - Score calculation (technical + community + social + fundamental)
   - Red flag detection
   - DEX link generation (Jupiter, Uniswap, Raydium)

3. **`alpha_engine.py`**
   - `ActiveAlphaPlay` dataclass
   - `AlphaPlaysEngine` class
   - Discovery and creation workflow
   - Approval system
   - Publishing to VIP/Free channels
   - TP/SL tracking
   - Rate limiting
   - Trade parameter generation

4. **`alpha_publisher.py`**
   - `AlphaPublisher` class
   - VIP channel publishing
   - Free channel teaser publishing
   - Result notifications
   - Update messages

5. **`content_formatter.py`**
   - `AlphaContentFormatter` class
   - VIP full signal formatting
   - Free teaser formatting
   - Result/closed play formatting
   - Chain emoji mapping
   - Risk level indicators

---

## 📝 MODIFIED FILES

### 1. `src/config.py`
**Added Settings:**
```python
TELEGRAM_DEGEN_CHANNEL_ID: Optional[str] = None      # Free alpha channel
TELEGRAM_DEGEN_VIP_CHANNEL_ID: Optional[str] = None  # VIP alpha channel

ALPHA_MIN_SCORE: float = 70.0          # Minimum score for discovery
ALPHA_AUTO_APPROVE: bool = False        # Auto-approve high-score plays
ALPHA_VIP_DAILY_LIMIT: int = 1        # Max alpha plays per day for VIP
ALPHA_FREE_WEEKLY_LIMIT: int = 1      # Max alpha plays per week for FREE

DEXSCREENER_API_KEY: Optional[str] = None
BIRDEYE_API_KEY: Optional[str] = None
MORALIS_API_KEY: Optional[str] = None
```

### 2. `src/main.py`
**Added:**
- Import: `AlphaPlaysEngine`, `AlphaPublisher`
- Instance variables: `alpha_engine`, `alpha_publisher`
- Initialization in `initialize()`
- Scheduler jobs: `alpha_discovery` (every 6h), `alpha_tracking` (every 5m)
- Methods: `_scan_alpha_plays()`, `_track_alpha_plays()`

### 3. `src/admin/dashboard_server.py`
**Added Endpoints:**
- `GET /api/alpha/plays` - Get active and pending alpha plays
- `POST /api/alpha/approve` - Approve a pending alpha play
- `POST /api/alpha/trigger` - Manually trigger alpha scan
- `GET /api/alpha/stats` - Get alpha play statistics

**Fixed:**
- `POST /api/signals/create` - Added missing required fields for TradingSignal

### 4. `src/admin/static/index.html`
**Added:**
- New tab: "🎰 Alpha" in main navigation
- Sub-tabs: Active Plays, Pending Discovery, Stats
- Alpha plays tables with live data
- Manual scan trigger button
- Approval buttons for pending plays
- Statistics cards

### 5. `src/database/supabase_client.py`
**Added Methods:**
- `save_alpha_play()` - Save alpha play to DB
- `get_alpha_plays()` - Retrieve alpha plays
- `update_alpha_play()` - Update alpha play status

---

## 🎯 HOW IT WORKS

### Discovery Flow
1. **Scan** (every 6 hours): Queries DexScreener for trending low-cap pairs
2. **Score**: Calculates technical + community + social + fundamental scores
3. **Filter**: Only passes plays with score ≥ 70 and good liquidity
4. **Queue**: Adds to pending queue for admin approval

### Approval Flow
1. Admin clicks "Approve" in dashboard OR auto-approve if score ≥ 85
2. System generates trade parameters:
   - Entry: 2% below current price
   - SL: 15-25% below entry (based on market cap)
   - TP1: 2.5x risk
   - TP2: 5x risk (moonshot)
3. Publishes to VIP channel immediately
4. Publishes teaser to FREE channel (if weekly limit allows)

### Tracking Flow
1. Every 5 minutes: Checks all active alpha plays
2. Compares current price to TP1/TP2/SL
3. Sends VIP updates when TPs hit
4. Closes play when TP2 or SL hit
5. Sends result notifications to both channels

---

## 📊 FREQUENCY & LIMITS

| Channel | Frequency | Limit | Content |
|---------|-----------|-------|---------|
| **VIP Degen** | 1 per day | Configurable (default: 1) | Full signal + DEX links |
| **Free Degen** | 1 per week | Configurable (default: 1) | Teaser + VIP upsell |
| **Discovery Scan** | Every 6 hours | N/A | Finds candidates |
| **Price Tracking** | Every 5 minutes | N/A | Monitors TP/SL |

---

## 🔗 DEX LINKS GENERATED

### SOL Chain
- `https://jup.ag/swap/USDC-{token_address}` - Jupiter swap
- `https://dexscreener.com/solana/{pair}` - Chart

### ETH Chain
- `https://app.uniswap.org/#/swap?outputCurrency={token}` - Uniswap
- `https://dexscreener.com/ethereum/{pair}` - Chart

### BASE Chain
- `https://app.uniswap.org/?chain=base` - Base swap
- `https://basescan.org/token/{token}` - Explorer

---

## 🎮 CONTENT STRUCTURE

### VIP Full Signal Example:
```
🎰 ALPHA PLAY ALERT 🎰

☀️ SOL BONK - Bonk Token
💀 DEGEN MODE

📊 Metrics:
• Price: $0.00001234
• Market Cap: $12.5M
• Liquidity: $850K
• Volume 24h: $2.1M
• 24h Change: +45.2%

🎯 Trade Setup:
• Entry: $0.00001210
• Stop Loss: $0.00000908
• Take Profit 1: $0.00001815 (+50%)
• Take Profit 2: $0.00002420 (+100%)

💰 Position Size: 2-3% of portfolio

🔥 Catalyst:
🚀 Strong daily trend: +45% in 24h

📈 Technical Score: 78/100
👥 Community Score: 85/100
📣 Social Score: 72/100
⭐ Overall: 78/100

🔗 Quick Links:
📊 Chart | 💱 Buy on DEX | 📋 Token Info

⚡ Act fast - alpha plays move quickly!
⏰ Posted: 14:30 UTC
```

### Free Teaser Example:
```
🎰 ALPHA PLAY TEASER 🎰

☀️ BONK
🚀 Already up 45% in 24h!

📊 What we know:
• Market Cap: $12.5M
• Volume 24h: $2.1M
• Chain: SOL

💎 VIP Members just got:
✅ Exact entry price
✅ Stop loss level
✅ 2 take profit targets
✅ Position size recommendation
✅ Risk warnings & red flags
✅ Direct DEX buy link

🔒 This alpha play is VIP EXCLUSIVE!

👉 Want the full signal?
DM @CryptoPulseVIPBot for instant access

💰 VIP gets 1 alpha play per day
🆓 Free gets 1 alpha play per week

⏰ Next free alpha: Coming this Sunday!
```

---

## 🛡️ ZERO BREAKING CHANGES

### ✅ What Was Protected:
1. **Existing Signals** → Still use standard flow
2. **Existing Channels** → VIP/Free channels unchanged
3. **Existing Database** → New `alpha_plays` table (separate from `signals`)
4. **Existing Scheduler** → New jobs are separate
5. **Existing Dashboard** → New tab is additive
6. **Existing Bots** → No handler changes needed

### ✅ Isolation Strategy:
- Separate engine (`AlphaPlaysEngine` vs `SignalEngine`)
- Separate publisher (`AlphaPublisher` vs `ChannelPublisher`)
- Separate database table (`alpha_plays`)
- Separate scheduler jobs
- Separate Telegram channels
- Separate dashboard tab

---

## 🚀 TO ACTIVATE

### Step 1: Add to `.env`
```bash
# Alpha/Degen Channels
TELEGRAM_DEGEN_CHANNEL_ID=-100YOUR_FREE_DEGEN_CHANNEL_ID
TELEGRAM_DEGEN_VIP_CHANNEL_ID=-100YOUR_VIP_DEGEN_CHANNEL_ID

# Optional: DEX APIs for better scanning
DEXSCREENER_API_KEY=your_key
BIRDEYE_API_KEY=your_key
MORALIS_API_KEY=your_key
```

### Step 2: Create Database Table
```sql
CREATE TABLE alpha_plays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    name TEXT,
    chain TEXT,
    token_address TEXT,
    play_type TEXT DEFAULT 'alpha',
    status TEXT DEFAULT 'active',
    entry_price NUMERIC,
    stop_loss NUMERIC,
    take_profit_1 NUMERIC,
    take_profit_2 NUMERIC,
    current_price NUMERIC,
    current_pnl NUMERIC,
    market_cap NUMERIC,
    volume_24h NUMERIC,
    price_change_24h NUMERIC,
    overall_score NUMERIC,
    catalyst TEXT,
    dex_url TEXT,
    chart_url TEXT,
    buy_url TEXT,
    position_size TEXT,
    red_flags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    approved_at TIMESTAMP,
    closed_at TIMESTAMP
);
```

### Step 3: Restart Dashboard
```bash
# Stop current dashboard
Ctrl+C

# Restart
start_dashboard.bat
```

### Step 4: Access Alpha Tab
```
http://localhost:8081/
```
- Click "🎰 Alpha" tab
- Click "🔍 Scan Now" to find plays
- Approve pending plays
- Monitor active plays

---

## 📈 EXPECTED BEHAVIOR

### Discovery Phase
- Scans every 6 hours automatically
- Finds 0-3 candidates per scan
- Displays in "Pending Discovery" tab
- Shows score, market cap, catalyst

### Approval Phase
- Admin clicks "Approve" button
- Auto-generates entry/SL/TP1/TP2
- Publishes to VIP channel
- Publishes teaser to FREE channel
- Shows in "Active Plays" tab

### Tracking Phase
- Updates every 5 minutes
- Shows live P&L
- Color-coded (green profit, red loss)
- Alerts on TP/SL hits
- Moves to results when closed

---

## 🎯 FEATURES SUMMARY

### ✅ Implemented:
- [x] DexScreener integration for low-cap discovery
- [x] Multi-chain support (SOL, ETH, BASE)
- [x] Score-based filtering (technical + social + community)
- [x] Red flag detection
- [x] Admin approval workflow
- [x] Auto-approval for high scores
- [x] VIP channel publishing (full signal)
- [x] Free channel publishing (teaser)
- [x] DEX link generation (Jupiter, Uniswap)
- [x] TP/SL tracking every 5 minutes
- [x] P&L calculation
- [x] Rate limiting (1/day VIP, 1/week Free)
- [x] Dashboard integration (tab + endpoints)
- [x] Manual scan trigger
- [x] Statistics tracking
- [x] Result notifications

---

## 🏆 STATUS

**✅ ALPHA/DEGEN PLAYS SYSTEM FULLY IMPLEMENTED**

- All core components built
- Dashboard integrated
- No breaking changes
- Ready for testing

**Next Step:** Add channel IDs to `.env` and test!
