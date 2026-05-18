![CRYPTO PULSE SIGNALS Logo](assets/logo.png)

# ⚡ CRYPTO PULSE SIGNALS - Quick Start Guide

Get up and running in 15 minutes!

---

## 🎯 Prerequisites

- Python 3.12+
- Telegram account
- 15 minutes of your time

---

## 🚀 5-Step Setup

### Step 1: Clone & Install (2 min)

```bash
# Clone repository
git clone <repo-url>
cd cryptopulse-ai

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Create Telegram Bot (3 min)

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send: `/newbot`
3. Name it: `YourSignals Bot`
4. Username: `yoursignals_bot`
5. **Copy the token**

### Step 3: Get Your Chat ID (2 min)

1. Start your bot (send `/start`)
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find your chat ID in the JSON response
4. **Copy the ID**

### Step 4: Create Channels (3 min)

**Free Channel:**
1. Create public channel
2. Add bot as admin
3. Username: `@yourfree_channel`

**VIP Channel:**
1. Create private channel
2. Add bot as admin
3. Get channel ID from getUpdates

### Step 5: Configure & Run (5 min)

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Minimum required:**
```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
TELEGRAM_FREE_CHANNEL_ID=@yourchannel
TELEGRAM_VIP_CHANNEL_ID=-1001234567890

# For testing, use these:
SUPABASE_URL=https://demo.supabase.co
SUPABASE_KEY=demo_key
SUPABASE_SERVICE_KEY=demo_key
NEWS_API_KEY=demo_key
STRIPE_SECRET_KEY=sk_test_demo
STRIPE_PUBLISHABLE_KEY=pk_test_demo
STRIPE_WEBHOOK_SECRET=whsec_demo
STRIPE_VIP_PRICE_ID=price_demo
```

**Start the system:**
```bash
python src/main.py
```

---

## ✅ Verify It's Working

1. **Check logs:**
   ```
   ✅ SIGNALFORGE AI is now running!
   ```

2. **Telegram admin bot:**
   - Should receive startup message
   - Send `/status` to check

3. **Wait for first signal:**
   - System scans every 5/15/60 minutes
   - High-quality signals sent to admin
   - Approve or reject via Telegram

---

## 🎯 Next Steps

### For Testing

Lower the confidence threshold to get more signals:
```env
MIN_CONFIDENCE_SCORE=75
MAX_SIGNALS_PER_DAY=10
```

### For Production

1. **Set up Supabase:**
   - Create account at supabase.com
   - Run SQL scripts
   - Update .env with real credentials

2. **Set up Stripe:**
   - Create account at stripe.com
   - Create product
   - Update .env with real keys

3. **Get News API key:**
   - Register at newsapi.org
   - Get free API key
   - Update .env

4. **Deploy:**
   - See DEPLOYMENT_GUIDE.md
   - Use Docker for production
   - Set up monitoring

---

## 📊 Using the Dashboard

```bash
# In a new terminal
streamlit run src/dashboard/app.py
```

Visit: http://localhost:8501

**Features:**
- View active signals
- Check performance
- Manage subscribers
- Monitor analytics

---

## 🔧 Common Issues

### "No signals generated"

**Solution:** Lower confidence score
```env
MIN_CONFIDENCE_SCORE=70
```

### "Bot not responding"

**Solution:** Check token
```bash
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### "Can't post to channel"

**Solution:** 
1. Make sure bot is admin
2. Grant posting permissions
3. Check channel ID is correct

---

## 📱 Test Signal Flow

1. **Wait for scan** (every 5/15/60 min)
2. **Receive in Telegram** with chart
3. **Click "Approve"**
4. **Signal published** to channels
5. **Updates sent** automatically

---

## 🎨 Customize

### Change Signal Criteria

Edit `src/config.py`:
```python
MIN_CONFIDENCE_SCORE = 88  # Minimum quality
MAX_SIGNALS_PER_DAY = 3    # Maximum per day
MIN_RISK_REWARD = 2.0      # Minimum R:R ratio
```

### Change Scan Frequency

Edit `src/main.py`:
```python
# Scan every 10 minutes instead of 5
CronTrigger(minute='*/10')
```

### Customize Messages

Edit `src/telegram/channel_publisher.py`:
```python
def _format_signal_for_channel(self, signal, vip_only):
    # Customize message format here
```

---

## 📚 Full Documentation

- **README.md** - Complete overview
- **DEPLOYMENT_GUIDE.md** - Production deployment
- **TELEGRAM_SETUP.md** - Detailed Telegram setup
- **API Docs** - http://localhost:8000/docs

---

## 🆘 Need Help?

1. Check logs: `tail -f logs/cryptopulse_*.log`
2. Run tests: `python scripts/test_setup.py`
3. Review documentation
4. Check environment variables

---

## 🎉 You're Ready!

Your crypto signal platform is now running!

**What happens next:**
1. System scans markets 24/7
2. Finds high-quality setups
3. Sends to you for approval
4. Publishes to your channels
5. Tracks performance

**Start building your signal business today!** 🚀
