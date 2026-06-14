# 🚨 URGENT: Finnhub API Key Issue

## ❌ **Critical Error Found**

```
⚠️ Finnhub returned status 403 for XAU/USD
```

**This means**: Your Finnhub API key is **INVALID** or **NOT SET** in the Oracle `.env` file.

---

## 🔧 **IMMEDIATE FIX REQUIRED**

### **Step 1: Verify Your Finnhub API Key**

1. Go to https://finnhub.io/dashboard
2. Login with your account
3. Copy your **API Key** from the dashboard
4. It should look like: `c1234567890abcdef1234567890abcd`

### **Step 2: Update Oracle .env File**

SSH into Oracle and edit the `.env` file:

```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169
cd /home/opc/CryptoPulse-Signals
nano .env
```

**Add this line** (replace with your actual key):
```
FINNHUB_API_KEY=your_actual_api_key_here
```

**Save**: `Ctrl+O`, `Enter`, `Ctrl+X`

### **Step 3: Restart Bot**

```bash
pkill -f "python.*main.py"
nohup /home/opc/CryptoPulse-Signals/venv/bin/python -u /home/opc/CryptoPulse-Signals/src/main.py > /home/opc/CryptoPulse-Signals/bot.log 2>&1 &
```

---

## 🔍 **Alternative: Disable Forex Temporarily**

If you don't want to use Finnhub right now, you can **temporarily disable Forex signals**:

### **Option 1: Remove XAU/USD from Forex Symbols**

Edit `src/exchange/forex_client.py` on Oracle:

```bash
nano /home/opc/CryptoPulse-Signals/src/exchange/forex_client.py
```

**Change line 19-23** from:
```python
FOREX_SYMBOLS = [
    # Major Forex pairs
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'NZD/USD',
    # Commodities
    'XAU/USD',  # Gold
```

**To** (comment out all Forex):
```python
FOREX_SYMBOLS = [
    # Temporarily disabled due to API issues
    # 'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'NZD/USD',
    # 'XAU/USD',  # Gold
```

**Save and restart bot**.

---

## 📊 **Current Status**

### **What's Working** ✅
- Crypto signals (BTC, ETH, BNB, etc.)
- Trade management for crypto
- AutoPilot system
- Admin dashboard

### **What's Broken** ❌
- Finnhub API (403 Forbidden)
- Forex price fetching
- XAU/USD signals

### **Root Causes**:
1. **Finnhub API key not set** in Oracle `.env`
2. **Twelve Data rate limited** (429 errors)
3. **Alpha Vantage rate limited** (25/day exceeded)

---

## 💡 **RECOMMENDED SOLUTION**

### **Best Fix** (5 minutes):
1. **Get your Finnhub API key** from dashboard
2. **Add to Oracle `.env`**: `FINNHUB_API_KEY=your_key`
3. **Restart bot**
4. **Forex signals will work** with 60 requests/min (free!)

### **Quick Fix** (1 minute):
1. **Disable Forex symbols** (comment out in `forex_client.py`)
2. **Restart bot**
3. **Focus on crypto signals only**

---

## 🚀 **After Fix - Expected Logs**

### **Good Signs** ✅:
```
Forex API Keys - Finnhub: ✅ SET, Twelve Data: ✅ SET
✅ Finnhub: EUR/USD = $1.0845
✅ Finnhub: XAU/USD = $2654.32
```

### **Bad Signs** ❌ (current):
```
⚠️ Finnhub returned status 403 for XAU/USD
🌍 Rate limited (429) getting price for XAU/USD
❌ All APIs failed to fetch price for XAU/USD
```

---

## 📝 **Dashboard Updates**

I also need to update the dashboards with the new features. Let me know when the Finnhub issue is fixed and I'll:

1. ✅ Update **admin dashboard** (local + Oracle)
2. ✅ Add **mobile-responsive** design
3. ✅ Display **advanced technical analysis** data
4. ✅ Show **Forex signals** (when API is fixed)
5. ✅ Update **signal cards** with new metadata

---

## ⚡ **QUICK COMMANDS**

### **Check if Finnhub key is set on Oracle**:
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "grep FINNHUB /home/opc/CryptoPulse-Signals/.env"
```

### **Check current bot logs**:
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "tail -50 /home/opc/CryptoPulse-Signals/bot.log | grep -i finnhub"
```

### **Restart bot**:
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "pkill -f 'python.*main.py' && cd /home/opc/CryptoPulse-Signals && nohup ./venv/bin/python -u src/main.py > bot.log 2>&1 &"
```

---

## 🎯 **NEXT STEPS**

1. **Fix Finnhub API key** (add to Oracle `.env`)
2. **Restart bot**
3. **Verify Forex signals working**
4. **Update dashboards** (I'll do this after API fix)

---

**Status**: ⚠️ **ACTION REQUIRED**  
**Priority**: **HIGH** - Forex signals completely broken  
**Time to Fix**: **5 minutes**  
**Impact**: Enables 24/7 Forex signal generation

Let me know once you've added the Finnhub API key to Oracle's `.env` file!
