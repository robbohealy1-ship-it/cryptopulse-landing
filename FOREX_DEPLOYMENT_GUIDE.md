# 🌍 Forex Signal System - Deployment Guide

## ✅ What's Been Added

Your CryptoPulse system now supports **both Crypto AND Forex signals** running in parallel:

### **New Components**
1. **ForexClient** (`src/exchange/forex_client.py`)
   - Free APIs: Alpha Vantage (Forex pairs) + Twelve Data (indices)
   - Supports: EUR/USD, GBP/USD, USD/JPY, AUD/USD, XAUUSD, NAS100, etc.

2. **ForexSignalEngine** (`src/engine/forex_signal_engine.py`)
   - Same technical analysis as crypto
   - Generates 3 Forex signals/day (separate from crypto quota)
   - Auto-approves and publishes to same VIP/Free channels

3. **Database Updates**
   - Added `market_type` column to signals table
   - Migration script: `migrations/add_market_type_column.sql`

4. **Telegram Integration**
   - Forex signals show 🌍 icon
   - Crypto signals show ₿ icon
   - Same channels, clean visual distinction

5. **Dashboard UI**
   - Orange badges for Forex (🌍 FOREX)
   - Blue badges for Crypto (₿ CRYPTO)
   - Market type column in all tables

---

## 📋 Deployment Steps

### **1. Run Database Migration**

Connect to your Supabase dashboard and run this SQL:

```sql
-- Add market_type column
ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS market_type TEXT DEFAULT 'crypto';

-- Add index
CREATE INDEX IF NOT EXISTS idx_signals_market_type ON signals(market_type);

-- Update existing signals
UPDATE signals 
SET market_type = 'crypto' 
WHERE market_type IS NULL;

-- Add constraint
ALTER TABLE signals 
ADD CONSTRAINT check_market_type 
CHECK (market_type IN ('crypto', 'forex'));
```

**Verify:**
```sql
SELECT market_type, COUNT(*) FROM signals GROUP BY market_type;
```

---

### **2. Update Environment Variables**

Your `.env` file should already have these (you added them):

```bash
# Forex Data APIs (free tier)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
TWELVE_DATA_API_KEY=your_twelve_data_key_here
```

**Get Free API Keys:**
- Alpha Vantage: https://www.alphavantage.co/support/#api-key
- Twelve Data: https://twelvedata.com/pricing (free tier: 800 requests/day)

---

### **3. Deploy to Oracle VM**

**SSH into Oracle:**
```bash
ssh -i "ssh-key-2026-05-20 (2).key" ubuntu@141.147.114.169
```

**Pull latest code:**
```bash
cd CryptoPulse-Signals
git pull origin main
```

**Restart the bot:**
```bash
# Stop existing process
pkill -f "python -m src.main"

# Start fresh
nohup python -m src.main > bot.log 2>&1 &

# Check it's running
ps aux | grep python
tail -f bot.log
```

**Look for these log lines:**
```
🌍 Initializing Forex signal engine...
✅ Forex signal engine initialized (11 pairs)
🌍 FOREX: Every 2 hours — Forex pairs, commodities, indices
```

---

### **4. Verify Forex Scanning**

**Check logs for Forex scans (every 2 hours):**
```bash
tail -f bot.log | grep -i forex
```

You should see:
```
🌍 Scanning Forex markets (EUR/USD, XAUUSD, NAS100, etc.)...
✅ Forex scan generated 2 signal(s)
```

**Check dashboard:**
- Go to http://141.147.114.169:8080
- Look for signals with 🌍 FOREX badge (orange)
- Crypto signals will have ₿ CRYPTO badge (blue)

---

### **5. Monitor First Forex Signal**

When the first Forex signal is generated:

1. **Check Telegram VIP channel** - Should show:
   ```
   🌍 ⭐ ELITE SIGNAL ⭐
   EUR/USD 🟢 LONG
   ...
   ```

2. **Check Free channel** - Should show same signal (if confidence < 85%)

3. **Check autopilot tracking** - Forex signals are tracked same as crypto

---

## 🎯 How It Works

### **Signal Generation Schedule**

| Market | Frequency | Timeframes | Max/Day |
|--------|-----------|------------|---------|
| **Crypto** | 15m, 1h, 4h, daily | All | 3 signals |
| **Forex** | Every 2 hours | 15m, 1h, 4h | 3 signals |

**Total possible:** 6 signals/day (3 crypto + 3 forex)

### **Forex Pairs Supported**

**Major Forex:**
- EUR/USD, GBP/USD, USD/JPY
- AUD/USD, USD/CAD, NZD/USD

**Commodities:**
- XAU/USD (Gold)
- XAG/USD (Silver)

**Indices:**
- NAS100 (NASDAQ 100)
- US30 (Dow Jones)
- SPX500 (S&P 500)

### **Telegram Message Format**

**Forex signals show:**
```
🌍 ⭐ ELITE SIGNAL ⭐

EUR/USD 🟢 LONG
Timeframe: 1h

⚡ MARKET ENTRY
💰 Entry: $1.08500
🛑 Stop Loss: $1.08200
🎯 Targets:
TP1: $1.08900
TP2: $1.09200
TP3: $1.09500

📊 Risk/Reward: 1:2.5
⚡ Confidence: 87.5%
```

---

## 🔧 Troubleshooting

### **No Forex signals generated?**

**Check API limits:**
```bash
# Test Alpha Vantage
curl "https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=EUR&to_currency=USD&apikey=YOUR_KEY"

# Test Twelve Data
curl "https://api.twelvedata.com/price?symbol=NAS100&apikey=YOUR_KEY"
```

**Check logs:**
```bash
grep -i "forex\|alpha\|twelve" bot.log
```

### **Forex signals not showing in dashboard?**

1. Hard refresh browser (Ctrl+Shift+R)
2. Check database:
   ```sql
   SELECT symbol, market_type, confidence, created_at 
   FROM signals 
   WHERE market_type = 'forex' 
   ORDER BY created_at DESC 
   LIMIT 5;
   ```

### **API rate limits hit?**

**Free tier limits:**
- Alpha Vantage: 25 requests/day (very limited!)
- Twelve Data: 800 requests/day

**Solution:** Upgrade to paid tier or reduce scan frequency:
```python
# In main.py, change from every 2 hours to every 4 hours:
CronTrigger(hour='*/4', minute='10')  # Instead of hour='*/2'
```

---

## 📊 Expected Behavior

### **First 24 Hours**

- **Crypto scans:** 15m (every 15min), 1h (hourly), 4h (every 4h), daily (once)
- **Forex scans:** Every 2 hours (12 scans/day)
- **Expected signals:** 2-6 total (mix of crypto + forex)

### **Telegram Channels**

- **VIP channel:** All signals (crypto + forex) with 85%+ confidence
- **Free channel:** Signals with <85% confidence OR delayed VIP signals

### **Dashboard**

- **Pending tab:** Shows signals awaiting approval (auto-approved, so usually empty)
- **Active tab:** Shows tracked signals with TP/SL progress
- **History tab:** All signals with market type filter

---

## 🚀 Next Steps

1. **Monitor for 24 hours** - Let it run and generate signals
2. **Check API usage** - Make sure you're not hitting rate limits
3. **Adjust scan frequency** if needed (reduce if API limits hit)
4. **Upgrade API keys** if you want more frequent Forex scans

---

## 📞 Support

If you encounter issues:

1. **Check logs:** `tail -f bot.log | grep -i error`
2. **Check database:** Verify `market_type` column exists
3. **Restart bot:** `pkill -f python && nohup python -m src.main > bot.log 2>&1 &`
4. **Check API keys:** Make sure they're valid and not rate-limited

---

## ✅ Success Checklist

- [ ] Database migration completed
- [ ] API keys added to `.env`
- [ ] Code deployed to Oracle VM
- [ ] Bot restarted successfully
- [ ] Forex engine initialized (check logs)
- [ ] Dashboard shows market type badges
- [ ] First Forex signal generated and published
- [ ] Autopilot tracking Forex signals

**You're all set! The system now generates both Crypto AND Forex signals automatically. 🎉**
