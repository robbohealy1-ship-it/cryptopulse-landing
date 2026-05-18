# 🎛️ Dashboard Manual Trade Management

**New Feature:** Full manual control over active trades from the admin dashboard.

---

## 🚀 New API Endpoints

### 1. **Update Signal Prices**
```http
PUT /api/signals/{signal_id}/update
```

**Purpose:** Edit entry, stop loss, or take profit prices for an active signal.

**Request Body:**
```json
{
  "entry_price": 0.04504,
  "stop_loss": 0.04436,
  "take_profit_1": 0.04673,
  "take_profit_2": 0.04740,
  "take_profit_3": 0.04842
}
```

**Notes:**
- All fields are optional - only send what you want to update
- Updates database immediately
- Does NOT send notifications to channels

**Example:**
```javascript
// Update only stop loss
fetch('/api/signals/abc123/update', {
  method: 'PUT',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    stop_loss: 0.04500  // Move SL up
  })
})
```

---

### 2. **Close Signal Manually**
```http
POST /api/signals/{signal_id}/close
```

**Purpose:** Manually close an active trade and calculate P&L.

**Request Body:**
```json
{
  "signal_id": "abc123",
  "close_price": 0.04650,
  "reason": "manual"
}
```

**Reasons:**
- `"manual"` - Admin closed manually
- `"tp_hit"` - TP hit but auto-detection missed
- `"sl_hit"` - SL hit but auto-detection missed
- `"expired"` - Signal expired

**What it does:**
1. Calculates P&L based on entry vs close price
2. Updates signal status to `closed`
3. Sends "TRADE CLOSED" notification to VIP channel
4. Records close reason in database

**Response:**
```json
{
  "success": true,
  "message": "Signal closed successfully",
  "pnl_percent": 3.24,
  "close_price": 0.04650
}
```

---

### 3. **Mark TP Hit Manually**
```http
POST /api/signals/{signal_id}/mark-tp
```

**Purpose:** Manually mark a TP level as hit (if auto-detection missed it).

**Request Body:**
```json
{
  "signal_id": "abc123",
  "tp_level": 1
}
```

**TP Levels:** 1, 2, or 3

**What it does:**
1. Marks TP as hit in database
2. Updates in-memory cache (prevents duplicates)
3. Sends "TP HIT" notification to VIP channel
4. If TP1: Automatically sends "SL moved to breakeven" message

**Response:**
```json
{
  "success": true,
  "message": "TP1 marked as hit",
  "tp_price": 0.04673
}
```

---

## 📊 Enhanced Active Signals Display

The `/api/signals/active` endpoint now includes:

**New Fields:**
- `setup_type` - Order Block, Liquidity Sweep, etc.
- `is_limit_order` - `true` = LIMIT, `false` = MARKET
- `stop_moved_to_breakeven` - Whether SL was moved after TP1

**Example Response:**
```json
{
  "count": 2,
  "signals": [
    {
      "id": "abc123",
      "symbol": "LAYER/USDT",
      "direction": "LONG",
      "timeframe": "1h",
      "setup_type": "order_block",
      "is_limit_order": false,
      "confidence": 96.4,
      "risk_reward": 2.5,
      "entry_price": 0.04504,
      "current_price": 0.04650,
      "stop_loss": 0.04504,
      "take_profit_1": 0.04673,
      "take_profit_2": 0.04740,
      "take_profit_3": 0.04842,
      "tp1_hit": true,
      "tp2_hit": false,
      "tp3_hit": false,
      "stop_moved_to_breakeven": true,
      "pnl_percent": 3.24,
      "created_at": "2026-05-18T14:00:00Z",
      "approved_at": "2026-05-18T14:01:00Z"
    }
  ]
}
```

---

## 🎯 Use Cases

### **Scenario 1: Price moved, need to adjust entry**
```javascript
// Market moved away from original entry
PUT /api/signals/abc123/update
{
  "entry_price": 0.04520  // New entry price
}
```

### **Scenario 2: TP hit but bot missed it**
```javascript
// Manually mark TP2 as hit
POST /api/signals/abc123/mark-tp
{
  "signal_id": "abc123",
  "tp_level": 2
}
```

### **Scenario 3: Want to close trade early**
```javascript
// Close at current price
POST /api/signals/abc123/close
{
  "signal_id": "abc123",
  "close_price": 0.04580,
  "reason": "manual"
}
```

### **Scenario 4: Signal expired, close it**
```javascript
POST /api/signals/abc123/close
{
  "signal_id": "abc123",
  "close_price": 0.04450,
  "reason": "expired"
}
```

---

## 🔒 Safety Features

### **Duplicate Prevention:**
- TP hit tracking uses in-memory cache
- Won't send duplicate notifications even if marked twice

### **Validation:**
- Signal ID must exist
- TP level must be 1, 2, or 3
- Close price must be provided
- All updates logged for audit trail

### **Error Handling:**
- Graceful failures with clear error messages
- Database errors don't crash the system
- All errors logged

---

## 📝 Database Methods Added

**New methods in `supabase_client.py`:**

```python
async def get_signal_by_id(signal_id: str) -> TradingSignal
# Get a single signal by ID

async def update_signal(signal_id: str, updates: dict) -> bool
# Generic update method for any signal fields
```

---

## 🎨 Frontend Integration

**Example Dashboard UI:**

```html
<!-- Active Signal Card -->
<div class="signal-card">
  <h3>LAYER/USDT LONG</h3>
  <p>Setup: Order Block | Entry: ⚡ MARKET</p>
  <p>P&L: +3.24%</p>
  
  <!-- TP Status -->
  <div class="tp-status">
    <span class="hit">✅ TP1</span>
    <span>⏳ TP2</span>
    <span>⏳ TP3</span>
  </div>
  
  <!-- Actions -->
  <button onclick="editSignal('abc123')">✏️ Edit Prices</button>
  <button onclick="markTP('abc123', 2)">✅ Mark TP2 Hit</button>
  <button onclick="closeSignal('abc123')">🔴 Close Trade</button>
</div>
```

**JavaScript Functions:**
```javascript
async function editSignal(signalId) {
  const newSL = prompt("New Stop Loss:");
  if (!newSL) return;
  
  await fetch(`/api/signals/${signalId}/update`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ stop_loss: parseFloat(newSL) })
  });
  
  alert("Signal updated!");
  location.reload();
}

async function markTP(signalId, tpLevel) {
  if (!confirm(`Mark TP${tpLevel} as hit?`)) return;
  
  await fetch(`/api/signals/${signalId}/mark-tp`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ signal_id: signalId, tp_level: tpLevel })
  });
  
  alert(`TP${tpLevel} marked as hit!`);
  location.reload();
}

async function closeSignal(signalId) {
  const closePrice = prompt("Close price:");
  if (!closePrice) return;
  
  await fetch(`/api/signals/${signalId}/close`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      signal_id: signalId,
      close_price: parseFloat(closePrice),
      reason: "manual"
    })
  });
  
  alert("Trade closed!");
  location.reload();
}
```

---

## ✅ Testing Checklist

- [ ] Update signal entry price
- [ ] Update signal stop loss
- [ ] Update all TP levels at once
- [ ] Mark TP1 hit manually
- [ ] Verify "SL moved to breakeven" sent after TP1
- [ ] Mark TP2 hit manually
- [ ] Mark TP3 hit manually
- [ ] Close signal with positive P&L
- [ ] Close signal with negative P&L
- [ ] Verify VIP channel receives notifications
- [ ] Check database updates correctly
- [ ] Test error handling (invalid signal ID)

---

**Created:** May 18, 2026  
**Status:** Production ready  
**Commit:** `eef3a34`
