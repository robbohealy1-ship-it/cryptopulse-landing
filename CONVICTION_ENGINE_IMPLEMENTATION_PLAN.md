# 🎯 CRYPTOPULSE CONVICTION ENGINE - IMPLEMENTATION PLAN

**Vision:** Transform CryptoPulse into an elite conviction-based trading intelligence platform  
**Goal:** 1-3 brand-worthy signals per day across 100+ pairs  
**Quality Standard:** "CryptoPulse Signal Strat" - professional-grade, explainable, auditable

---

## 📊 AUDIT SUMMARY

### ✅ What We Have (70% Complete)
- ✅ Signal Engine with ranking system (already selects top 3/day!)
- ✅ Institutional Analysis (structure, liquidity, volume profile)
- ✅ News Intelligence Engine (NewsAPI, sentiment analysis)
- ✅ DEX Momentum Engine (DexScreener, GeckoTerminal)
- ✅ Multi-timeframe alignment
- ✅ Validation pipeline
- ✅ Admin dashboard
- ✅ ~50 liquid pairs (Binance)

### ⚠️ What's Missing (30% to Build)
- ❌ Modular conviction engine (0-100 scoring)
- ❌ Volume Engine (delta, CVD, imbalance)
- ❌ Sentiment Engine (long/short ratios, liquidations)
- ❌ On-Chain Engine (whale tracking, flows)
- ❌ Market Magnet System
- ❌ Trap Detection Engine
- ❌ Signal Mode Selector
- ❌ Self-learning analytics
- ❌ Pair expansion (100+ pairs)

---

## 🏗️ IMPLEMENTATION PHASES

### **PHASE 2A: CORE CONVICTION ENGINE** (This Response)

Build the modular conviction engine system that combines all factors into a 0-100 score.

#### New File Structure:
```
src/conviction/
├── __init__.py
├── conviction_engine.py          # Main orchestrator (0-100 score)
├── market_structure_engine.py    # Engine 1 (0-20 points)
├── liquidity_engine.py            # Engine 2 (0-20 points)
├── volume_engine.py               # Engine 3 (0-15 points)
├── sentiment_engine.py            # Engine 4 (0-15 points)
├── news_intelligence_engine.py   # Engine 5 (0-15 points) - wrapper
├── onchain_engine.py              # Engine 6 (0-15 points)
├── dex_momentum_engine.py         # Engine 7 (0-20 points) - wrapper
├── market_magnet_system.py       # Magnet detection & multipliers
└── trap_detection_engine.py      # Trap filters & penalties
```

#### Integration Points:
1. **Signal Engine** - Replace current scoring with conviction engine
2. **Signal Ranker** - Use conviction score for ranking
3. **Dashboard** - Display per-engine breakdown
4. **Database** - Store conviction scores per engine

---

### **PHASE 2B: DASHBOARD EXTENSIONS** (Next Response)

Add controls and analytics to the admin dashboard.

#### Features:
1. **Mode Selector** - Strict/Balanced/Aggressive
2. **Weight Tuning** - Sliders for each engine (0-20, 0-15)
3. **Conviction Breakdown** - Visual per-engine scores
4. **Engine Performance** - Win rate per engine
5. **Market Regime Display** - Current regime + stats
6. **Magnet Levels** - Show detected magnets on chart

---

### **PHASE 2C: SELF-LEARNING** (Future)

Track performance and auto-optimize weights.

#### Features:
1. **Performance Tracking** - Win/loss per engine, asset, regime
2. **Auto-Optimization** - Adjust weights based on results
3. **Regime Detection** - Adapt to market conditions
4. **Setup Performance** - Track which setups work best

---

### **PHASE 2D: PAIR EXPANSION** (Future)

Expand from 50 to 100+ pairs.

#### Features:
1. **Bybit Integration** - Add Bybit spot + futures
2. **OKX Integration** - Add OKX spot + futures
3. **Binance Futures** - Add futures pairs
4. **Volume Threshold** - Lower to $5M for more pairs
5. **Multi-Exchange** - Scan all exchanges in parallel

---

## 🎯 PHASE 2A: DETAILED IMPLEMENTATION

### **1. Market Structure Engine** (0-20 points)

**Purpose:** Score market structure quality and trend strength

**Inputs:**
- Daily/Weekly/Monthly High/Low
- Trend Direction (uptrend/downtrend/neutral)
- ATR (volatility)
- VWAP
- Market Regime (trending/ranging/choppy)

**Scoring Logic:**
```python
score = 0

# Trend strength (0-8 points)
if strong_trend:
    score += 8
elif moderate_trend:
    score += 5
elif weak_trend:
    score += 2

# Structure quality (0-6 points)
if clean_structure (BOS/CHoCH):
    score += 6
elif moderate_structure:
    score += 3

# Regime alignment (0-6 points)
if trending_regime:
    score += 6
elif ranging_regime:
    score += 3
elif choppy_regime:
    score += 0  # Penalty

# Total: 0-20
```

**Implementation:**
- Extend `institutional_analyzer.py` with daily/weekly/monthly tracking
- Add VWAP calculation
- Add regime scoring (already has detection)

---

### **2. Liquidity Engine** (0-20 points)

**Purpose:** Score liquidity setup quality

**Inputs:**
- Liquidity sweeps
- Equal highs/lows
- Fair value gaps
- Order blocks
- Key levels (support/resistance)

**Scoring Logic:**
```python
score = 0

# Liquidity sweep (0-8 points)
if liquidity_swept:
    score += 8

# Equal highs/lows (0-6 points)
if equal_levels_detected:
    score += 6

# Fair value gap (0-3 points)
if fvg_present:
    score += 3

# Order block (0-3 points)
if order_block_present:
    score += 3

# Total: 0-20
```

**Implementation:**
- Extend `institutional_analyzer.py` with equal highs/lows detection
- Add FVG scoring
- Add key level tracking

---

### **3. Volume Engine** (0-15 points)

**Purpose:** Score volume confirmation

**Inputs:**
- Relative volume (vs 20-period average)
- Volume spikes
- Delta (buy volume - sell volume)
- CVD (Cumulative Volume Delta)
- Buy/sell imbalance

**Scoring Logic:**
```python
score = 0

# Relative volume (0-6 points)
if volume > 2x_average:
    score += 6
elif volume > 1.5x_average:
    score += 4
elif volume > 1.2x_average:
    score += 2

# Volume spike (0-4 points)
if recent_spike:
    score += 4

# Delta/CVD (0-5 points)
if strong_buy_pressure:
    score += 5
elif moderate_buy_pressure:
    score += 3

# Total: 0-15
```

**Implementation:**
- NEW: Create `volume_engine.py`
- Calculate relative volume
- Estimate delta from candle wicks
- Track CVD

---

### **4. Sentiment Engine** (0-15 points)

**Purpose:** Score market sentiment

**Inputs:**
- Funding rates (already have)
- Long/short ratios
- Liquidation data (real, not estimated)
- Fear & Greed Index (already have)

**Scoring Logic:**
```python
score = 0

# Funding rate alignment (0-5 points)
if funding_aligns_with_direction:
    score += 5
elif funding_neutral:
    score += 3
elif funding_extreme_opposite:
    score += 0  # Penalty

# Long/short ratio (0-5 points)
if ratio_aligns:
    score += 5

# Liquidations (0-3 points)
if recent_liquidations_support_direction:
    score += 3

# Fear & Greed (0-2 points)
if sentiment_aligns:
    score += 2

# Total: 0-15
```

**Implementation:**
- Extend `enhanced_context_engine.py`
- Add long/short ratio API (Binance futures)
- Add real liquidation data (Binance futures)

---

### **5. News Intelligence Engine** (0-15 points)

**Purpose:** Score news impact

**Already Implemented!** Just need to wrap it.

**Scoring Logic:**
```python
# Use existing context_score.news_score
# Already direction-aware
# Already detects high-impact events

score = context_score.news_score * 0.15  # Normalize to 0-15
```

**Implementation:**
- Wrapper around existing `enhanced_context_engine.py`

---

### **6. On-Chain Engine** (0-15 points)

**Purpose:** Score on-chain activity

**Inputs:**
- Whale accumulation/distribution
- Exchange inflows/outflows
- Stablecoin flows
- Dormant wallet activity

**Scoring Logic:**
```python
score = 0

# Whale activity (0-6 points)
if whale_accumulation:
    score += 6
elif whale_distribution:
    score += 0  # Penalty

# Exchange flows (0-5 points)
if exchange_outflow (bullish):
    score += 5
elif exchange_inflow (bearish):
    score += 0

# Stablecoin flows (0-4 points)
if stablecoin_inflow:
    score += 4

# Total: 0-15
```

**Implementation:**
- NEW: Create `onchain_engine.py`
- Use free APIs: Glassnode, CryptoQuant, Nansen (if available)
- Start with BTC/ETH only, expand later

**Note:** On-chain data is OPTIONAL for now. Can start with score = 7.5 (neutral) if no data.

---

### **7. DEX Momentum Engine** (0-20 points)

**Purpose:** Score DEX activity (for tokens with DEX presence)

**Already Implemented!** Just need to wrap it.

**Scoring Logic:**
```python
# Use existing alpha_discovery logic
# Volume growth, liquidity growth, holder growth

score = 0

# Volume growth (0-8 points)
if volume_growing:
    score += 8

# Liquidity growth (0-6 points)
if liquidity_growing:
    score += 6

# Holder growth (0-6 points)
if holders_growing:
    score += 6

# Total: 0-20
```

**Implementation:**
- Wrapper around existing `alpha_discovery.py`
- Only applies to tokens with DEX data
- For CEX-only pairs, score = 10 (neutral)

---

### **8. Market Magnet System**

**Purpose:** Detect key liquidity magnets and apply multipliers

**Magnets:**
- Daily High/Low
- Weekly High/Low
- Monthly High/Low
- Round numbers ($100, $1000, $10000, etc.)
- VWAP zones
- Previous session high/low

**Multiplier Logic:**
```python
multiplier = 1.0

# Price near magnet (within 0.5%)
if near_daily_high_low:
    multiplier += 0.10
if near_weekly_high_low:
    multiplier += 0.15
if near_monthly_high_low:
    multiplier += 0.20
if near_round_number:
    multiplier += 0.10
if near_vwap:
    multiplier += 0.05

# Apply to conviction score
conviction_score *= multiplier
```

**Implementation:**
- NEW: Create `market_magnet_system.py`
- Track daily/weekly/monthly highs/lows
- Detect round numbers
- Calculate VWAP

---

### **9. Trap Detection Engine**

**Purpose:** Detect traps and apply penalties

**Traps:**
- Bull traps (fake breakout up)
- Bear traps (fake breakout down)
- Liquidity grabs (sweep then reverse)
- Failed breakouts
- Open interest traps (OI spike + price reversal)
- Funding extremes (>0.1% or <-0.1%)

**Penalty Logic:**
```python
penalty = 0

# Bull trap detected
if bull_trap:
    penalty += 15  # -15 points

# Bear trap detected
if bear_trap:
    penalty += 15

# Failed breakout
if failed_breakout:
    penalty += 10

# OI trap
if oi_trap:
    penalty += 12

# Funding extreme
if funding_extreme:
    penalty += 8

# Apply penalty
conviction_score -= penalty
conviction_score = max(0, conviction_score)
```

**Implementation:**
- NEW: Create `trap_detection_engine.py`
- Detect fake breakouts (price breaks level, then reverses)
- Detect OI spikes without follow-through
- Detect funding extremes

---

## 🎯 FINAL CONVICTION SCORE CALCULATION

```python
# Step 1: Calculate sub-engine scores
market_structure_score = MarketStructureEngine.calculate()  # 0-20
liquidity_score = LiquidityEngine.calculate()               # 0-20
volume_score = VolumeEngine.calculate()                     # 0-15
sentiment_score = SentimentEngine.calculate()               # 0-15
news_score = NewsIntelligenceEngine.calculate()             # 0-15
onchain_score = OnChainEngine.calculate()                   # 0-15
dex_score = DEXMomentumEngine.calculate()                   # 0-20

# Step 2: Sum to get base conviction (0-120)
base_conviction = (
    market_structure_score +
    liquidity_score +
    volume_score +
    sentiment_score +
    news_score +
    onchain_score +
    dex_score
)

# Step 3: Normalize to 0-100
conviction_score = (base_conviction / 120) * 100

# Step 4: Apply Market Magnet multiplier
conviction_score *= MarketMagnetSystem.get_multiplier()

# Step 5: Apply Trap Detection penalty
conviction_score -= TrapDetectionEngine.get_penalty()

# Step 6: Clamp to 0-100
conviction_score = max(0, min(100, conviction_score))
```

---

## 🎯 SIGNAL TIER CLASSIFICATION

```python
if conviction_score >= 90:
    tier = "ELITE"
    rr_min = 3.0
    expected_per_day = 0-3
elif conviction_score >= 80:
    tier = "VIP"
    rr_min = 2.5
    expected_per_day = 3-10
elif conviction_score >= 70:
    tier = "WATCHLIST"
    rr_min = 2.0
    expected_per_day = 5-20
else:
    tier = "REJECTED"
```

---

## 🎯 SIGNAL MODES

### **Strict Mode** (Default)
- Min Conviction: 85
- Min RR: 2.5
- Expected: 0-5 signals/day
- Quality: Elite

### **Balanced Mode**
- Min Conviction: 75
- Min RR: 2.0
- Expected: 5-15 signals/day
- Quality: High

### **Aggressive Mode**
- Min Conviction: 65
- Min RR: 1.8
- Expected: 15-40 signals/day
- Quality: Moderate

**Implementation:**
- Add mode selector to dashboard
- Store mode in database (settings table)
- Apply mode thresholds in signal engine

---

## 📊 EXPLAINABILITY & AUDITABILITY

Every signal must include:

```python
{
    "symbol": "BTC/USDT",
    "conviction_score": 92,
    "tier": "ELITE",
    "breakdown": {
        "market_structure": 18,  # /20
        "liquidity": 19,         # /20
        "volume": 13,            # /15
        "sentiment": 12,         # /15
        "news": 14,              # /15
        "onchain": 11,           # /15
        "dex_momentum": 15       # /20
    },
    "magnets": {
        "near_weekly_high": true,
        "multiplier": 1.15
    },
    "traps": {
        "detected": false,
        "penalty": 0
    },
    "reasoning": "Full text explanation..."
}
```

---

## 🚀 IMPLEMENTATION ORDER (This Session)

1. ✅ Create `src/conviction/` folder
2. ✅ Implement `market_structure_engine.py`
3. ✅ Implement `liquidity_engine.py`
4. ✅ Implement `volume_engine.py`
5. ✅ Implement `sentiment_engine.py`
6. ✅ Implement `onchain_engine.py` (basic/optional)
7. ✅ Implement `market_magnet_system.py`
8. ✅ Implement `trap_detection_engine.py`
9. ✅ Implement `conviction_engine.py` (orchestrator)
10. ✅ Integrate with `signal_engine.py`
11. ✅ Test locally
12. ✅ Deploy to Oracle

---

## ✅ SUCCESS CRITERIA

After implementation:
- ✅ Conviction score 0-100 calculated
- ✅ Per-engine breakdown visible
- ✅ Magnet system active
- ✅ Trap detection active
- ✅ Signal quality improved
- ✅ Explainability complete
- ✅ Dashboard shows breakdown
- ✅ Oracle deployment successful

---

**Ready to start implementation?**

I'll begin with creating the modular conviction engine system, starting with the folder structure and core engines.
