![CRYPTO PULSE SIGNALS Logo](assets/logo.png)

# 🚀 CRYPTO PULSE SIGNALS

**Premium Crypto Day-Trading Signal Platform**

A complete, production-ready crypto signal business that automatically scans markets, detects high-probability setups, sends them for approval via Telegram, and publishes to free and paid communities.

---

## 📋 Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

### Core Functionality
- ✅ **Live Market Scanner** - Scans all liquid Binance USDT pairs 24/7
- ✅ **Advanced Technical Analysis** - Multi-timeframe analysis (5m, 15m, 1h)
- ✅ **Context Engine** - Integrates news, macro events, and sentiment
- ✅ **Quality Filtering** - Only 1-3 elite signals per day (88%+ confidence)
- ✅ **Admin Approval Workflow** - Telegram bot for instant approve/reject
- ✅ **Dual Channel Publishing** - Free + VIP Telegram channels
- ✅ **Subscription Management** - Stripe integration for payments
- ✅ **Performance Tracking** - Real-time analytics and reporting
- ✅ **Admin Dashboard** - Streamlit-based control panel

### Signal Detection
- Market structure analysis (BOS, CHoCH)
- Liquidity sweeps
- Fair value gaps
- Support/resistance retests
- Volume confirmation
- Trend alignment (EMA 20/50/200)
- VWAP analysis
- ATR-based stop loss
- Minimum 1:2 risk/reward

### Risk Management
- Automatic stop loss calculation
- Multiple take profit levels
- Position sizing recommendations
- Trade invalidation logic
- Real-time signal monitoring

---

## 🛠 Tech Stack

- **Python 3.12** - Core language
- **FastAPI** - REST API server
- **Streamlit** - Admin dashboard
- **python-telegram-bot** - Telegram integration
- **ccxt** - Exchange connectivity
- **Supabase** - Database (PostgreSQL)
- **Stripe** - Payment processing
- **Docker** - Containerization
- **pandas/numpy/ta** - Data analysis
- **APScheduler** - Task scheduling
- **Plotly** - Chart generation

---

## 🏗 Architecture

```
SIGNALFORGE AI
│
├── Market Scanner (Binance)
│   └── Liquid pairs (>$10M daily volume)
│
├── Signal Engine
│   ├── Technical Analyzer
│   ├── Context Engine
│   └── Confidence Scorer
│
├── Admin Bot (Telegram)
│   └── Approval workflow
│
├── Channel Publishers
│   ├── Free Channel
│   └── VIP Channel
│
├── Database (Supabase)
│   ├── Signals
│   ├── Subscribers
│   └── Performance
│
├── Payment System (Stripe)
│   └── Subscription management
│
└── Dashboard (Streamlit)
    └── Analytics & Control
```

---

## 📦 Installation

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Telegram Bot Token
- Supabase Account
- Stripe Account
- NewsAPI Key

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd cryptopulse-ai
```

2. **Copy environment file**
```bash
cp .env.example .env
```

3. **Configure environment variables** (see Configuration section)

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Run with Docker**
```bash
docker-compose up -d
```

---

## ⚙️ Configuration

### Environment Variables

Edit `.env` file with your credentials:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
TELEGRAM_FREE_CHANNEL_ID=@your_free_channel
TELEGRAM_VIP_CHANNEL_ID=@your_vip_channel

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_VIP_PRICE_ID=price_...

# News API
NEWS_API_KEY=your_newsapi_key

# Signal Settings
MIN_CONFIDENCE_SCORE=88
MAX_SIGNALS_PER_DAY=3
MIN_RISK_REWARD=2.0
SIGNAL_EXPIRY_MINUTES=30
```

---

## 🚀 Deployment

### Docker Deployment (Recommended)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Deployment

```bash
# Start signal engine
python src/main.py

# Start API server (separate terminal)
uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# Start dashboard (separate terminal)
streamlit run src/dashboard/app.py --server.port=8501
```

### Production Deployment

1. Set `ENVIRONMENT=production` in `.env`
2. Use proper SSL certificates
3. Set up reverse proxy (nginx)
4. Configure firewall rules
5. Set up monitoring and alerts
6. Regular backups of database

---

## 📱 Telegram Setup

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow instructions
4. Copy bot token to `.env`

### 2. Get Admin Chat ID

1. Message your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find your chat ID in the response
4. Add to `.env`

### 3. Create Channels

**Free Channel:**
1. Create public channel
2. Add bot as administrator
3. Get channel username (@your_channel)
4. Add to `.env`

**VIP Channel:**
1. Create private channel
2. Add bot as administrator
3. Get channel ID (use getUpdates method)
4. Add to `.env`

### 4. Test Bot

```bash
# Send test message
python -c "
from telegram import Bot
import asyncio
bot = Bot('YOUR_BOT_TOKEN')
asyncio.run(bot.send_message('YOUR_CHAT_ID', 'Test'))
"
```

---

## 💳 Stripe Setup

### 1. Create Product

1. Go to Stripe Dashboard
2. Products → Add Product
3. Name: "VIP Signals Subscription"
4. Pricing: Recurring (monthly)
5. Copy Price ID to `.env`

### 2. Configure Webhook

1. Developers → Webhooks
2. Add endpoint: `https://your-domain.com/api/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy webhook secret to `.env`

---

## 🗄 Supabase Setup

### 1. Create Project

1. Go to [Supabase](https://supabase.com)
2. Create new project
3. Copy URL and keys to `.env`

### 2. Run SQL Scripts

1. Go to SQL Editor
2. Run `scripts/init.sql`
3. Run `scripts/supabase_setup.sql`

### 3. Configure Storage (Optional)

For chart images:
1. Create bucket: `signal-charts`
2. Set to public
3. Update code to use Supabase storage

---

## 📊 Usage

### Starting the System

```bash
# Using Docker
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f cryptopulse-engine
```

### Accessing Services

- **API**: http://localhost:8000
- **Dashboard**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs

### Admin Workflow

1. System scans markets automatically
2. High-quality signals sent to Telegram
3. Admin reviews signal with chart
4. Click "Approve" or "Reject"
5. Approved signals published instantly
6. Updates sent automatically

### Monitoring

**Dashboard Metrics:**
- Active signals
- Win rate
- Total subscribers
- Revenue
- Performance analytics

**Logs:**
```bash
# View today's logs
tail -f logs/cryptopulse_$(date +%Y-%m-%d).log

# View errors
tail -f logs/errors_$(date +%Y-%m-%d).log
```

---

## 📡 API Documentation

### Endpoints

**Health Check**
```
GET /health
```

**Get Active Signals**
```
GET /api/signals/active
```

**Get Signal History**
```
GET /api/signals/history?days=7
```

**Get Performance Stats**
```
GET /api/performance
```

**Create Subscription**
```
POST /api/subscribe
Body: {
  "user_id": "123456",
  "username": "john_doe"
}
```

**Stripe Webhook**
```
POST /api/webhooks/stripe
Headers: stripe-signature
```

Full API documentation: http://localhost:8000/docs

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_signal_engine.py
```

---

## 🔧 Troubleshooting

### Common Issues

**Bot not receiving messages**
- Check bot token in `.env`
- Verify chat ID is correct
- Ensure bot is started: `/start`

**No signals generated**
- Check `MIN_CONFIDENCE_SCORE` (try lowering to 80)
- Verify Binance API is accessible
- Check logs for errors

**Database connection failed**
- Verify Supabase credentials
- Check network connectivity
- Ensure tables are created

**Stripe webhook not working**
- Verify webhook secret
- Check endpoint URL is accessible
- Review Stripe dashboard logs

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
python src/main.py
```

### Support

For issues and questions:
1. Check logs in `logs/` directory
2. Review error messages
3. Verify all environment variables
4. Test each component individually

---

## 📈 Performance Optimization

### Recommended Settings

**For High Volume:**
- Increase `MAX_SIGNALS_PER_DAY` to 5
- Lower `MIN_CONFIDENCE_SCORE` to 85

**For Quality:**
- Keep `MIN_CONFIDENCE_SCORE` at 88+
- Set `MAX_SIGNALS_PER_DAY` to 2-3

**For Testing:**
- Lower `MIN_CONFIDENCE_SCORE` to 75
- Increase `MAX_SIGNALS_PER_DAY` to 10

---

## 🔐 Security

- Never commit `.env` file
- Use environment variables for secrets
- Enable Supabase Row Level Security
- Use HTTPS in production
- Validate Stripe webhooks
- Implement rate limiting
- Regular security audits

---

## 📝 License

Proprietary - All Rights Reserved

---

## 🤝 Contributing

This is a private commercial project.

---

## 📞 Contact

For business inquiries: [your-email@example.com]

---

**Built with ❤️ for professional crypto traders**
