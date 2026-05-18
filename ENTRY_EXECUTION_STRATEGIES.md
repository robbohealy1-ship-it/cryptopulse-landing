# 📊 Entry Execution Strategies - MARKET vs LIMIT

**Purpose:** Provide variety in execution types to keep traders engaged and match different market conditions.

---

## 🎯 Execution Strategy Logic

The system automatically determines whether a signal should be **MARKET** or **LIMIT** based on:
1. **Setup Type** - Different setups have different execution styles
2. **Price Distance** - How far current price is from entry
3. **Volatility** - High volatility may require immediate execution
4. **Market Conditions** - Trending vs ranging markets

---

## ⚡ MARKET ENTRY Signals

**When to use:**
- Price is AT or very close to entry (<0.3% away)
- High volatility (>3% ATR) and price near entry
- Breakout/momentum setups where waiting may miss the move
- Liquidity sweep or FVG fill happening NOW

**Setup Types that favor MARKET:**
- `liquidity_sweep` - Enter as sweep occurs
- `fair_value_gap` - Enter as FVG fills
- `order_block` - If price is at the block NOW
- `pullback_continuation` - Enter on pullback completion

**Example:**
```
⚡ MARKET ENTRY
💰 ENTRY: $0.04504
🔹 Enter now at current price

Current Price: $0.04502 (0.04% from entry)
→ Price is AT entry, enter immediately
```

---

## ⏳ LIMIT ORDER Signals

**When to use:**
- Price has moved away from entry (>0.5%)
- Retest setups where you're waiting for pullback
- Price is far from entry (>1%)
- Lower volatility, patient entry

**Setup Types that favor LIMIT:**
- `breakout_retest` - Wait for price to retest breakout
- `bos_retest` - Wait for break of structure retest
- `choch_retest` - Wait for change of character retest
- `support_resistance` - Wait for price to reach level

**Example:**
```
⏳ LIMIT ORDER
💰 ENTRY: $0.04504
🔹 Price moved away - wait for pullback

Current Price: $0.04650 (3.2% above entry)
→ Set limit order, wait for retest
```

---

## 📋 Decision Matrix

| Condition | Entry Type | Reason |
|-----------|-----------|--------|
| **Setup is retest** | ⏳ LIMIT | Waiting for pullback by definition |
| **Price >1% from entry** | ⏳ LIMIT | Too far, wait for retest |
| **Price <0.3% from entry** | ⚡ MARKET | At entry, execute now |
| **High volatility + close** | ⚡ MARKET | May not get retest |
| **Sweep/FVG at entry** | ⚡ MARKET | Enter on fill |
| **Price 0.5-1% away** | ⏳ LIMIT | Moved away, wait |

---

## 🎯 Examples by Setup Type

### 1. Liquidity Sweep (MARKET if at entry)
```
Setup: Liquidity Sweep
Current: $100 | Entry: $100.20
Distance: 0.2%
→ ⚡ MARKET (sweep happening now)
```

### 2. Breakout Retest (LIMIT - always)
```
Setup: Breakout Retest
Current: $105 | Entry: $100
Distance: 5%
→ ⏳ LIMIT (wait for retest)
```

### 3. Order Block (depends on distance)
```
Setup: Order Block
Current: $100 | Entry: $99.50
Distance: 0.5%
→ ⚡ MARKET (close enough, enter now)

Current: $102 | Entry: $99.50
Distance: 2.5%
→ ⏳ LIMIT (too far, wait for retest)
```

### 4. Fair Value Gap (MARKET if filling)
```
Setup: Fair Value Gap
Current: $100 | Entry: $100.10
Distance: 0.1%
→ ⚡ MARKET (FVG filling now)
```

---

## 📊 Expected Distribution

**Target Mix:**
- **60% LIMIT orders** - Patient, high-probability entries
- **40% MARKET orders** - Immediate execution, momentum plays

This provides variety and keeps traders engaged with different execution styles.

---

## 🔧 Technical Implementation

**Code Location:** `src/engine/signal_engine.py`

**Logic Flow:**
```python
1. Check setup type (retest → LIMIT)
2. Calculate price distance from entry
3. Check volatility (ATR %)
4. Apply decision matrix
5. Set is_limit_order flag
```

**Thresholds:**
- Close to entry: <0.3%
- Far from entry: >1.0%
- High volatility: >3% ATR
- Default buffer: 0.5%

---

## 💡 Trader Benefits

### MARKET Orders:
✅ Immediate execution  
✅ No risk of missing the move  
✅ Good for momentum/breakouts  
✅ Simpler execution  

### LIMIT Orders:
✅ Better entry price  
✅ Lower risk (wait for confirmation)  
✅ Good for retests/pullbacks  
✅ More patient, professional approach  

---

## 📈 VIP Signal Card Format

**MARKET Example:**
```
⚡ MARKET ENTRY
💰 Entry: $0.04504000
🔹 Enter now at current price
```

**LIMIT Example:**
```
⏳ LIMIT ORDER
💰 Entry: $0.04504000
🔹 Wait for retest
```

---

**Created:** May 18, 2026  
**Status:** Active in production  
**Next Review:** Monitor distribution and adjust thresholds if needed
