![CRYPTO PULSE SIGNALS Logo](assets/logo.png)

# 🚀 CRYPTO PULSE SIGNALS - Deployment Guide

Complete step-by-step deployment guide for production.

---

## 📋 Pre-Deployment Checklist

- [ ] Python 3.12+ installed
- [ ] Docker & Docker Compose installed
- [ ] Domain name configured
- [ ] SSL certificate ready
- [ ] Telegram bot created
- [ ] Telegram channels created
- [ ] Supabase project created
- [ ] Stripe account configured
- [ ] NewsAPI key obtained
- [ ] Server with minimum 2GB RAM

---

## 🔧 Step 1: Server Setup

### Option A: VPS (Recommended)

**Providers:**
- DigitalOcean (Droplet)
- AWS (EC2)
- Google Cloud (Compute Engine)
- Linode
- Vultr

**Minimum Specs:**
- 2 CPU cores
- 2GB RAM
- 20GB SSD
- Ubuntu 22.04 LTS

### Initial Server Configuration

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose -y

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install git
sudo apt install git -y
```

---

## 📥 Step 2: Clone and Configure

```bash
# Clone repository
git clone <your-repo-url>
cd cryptopulse-ai

# Create .env file
cp .env.example .env

# Edit configuration
nano .env
```

### Configure .env

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ADMIN_CHAT_ID=123456789
TELEGRAM_FREE_CHANNEL_ID=@yourfreechannel
TELEGRAM_VIP_CHANNEL_ID=-1001234567890

# Supabase Configuration
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...

# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_VIP_PRICE_ID=price_...

# News API
NEWS_API_KEY=your_newsapi_key_here

# Production Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## 🗄 Step 3: Database Setup

### Supabase Configuration

1. **Create Project**
   - Go to https://supabase.com
   - Click "New Project"
   - Choose region closest to your users
   - Set strong database password

2. **Run SQL Scripts**
   ```sql
   -- In Supabase SQL Editor, run:
   -- 1. scripts/init.sql
   -- 2. scripts/supabase_setup.sql
   ```

3. **Get API Keys**
   - Settings → API
   - Copy `anon/public` key → `SUPABASE_KEY`
   - Copy `service_role` key → `SUPABASE_SERVICE_KEY`
   - Copy Project URL → `SUPABASE_URL`

---

## 📱 Step 4: Telegram Setup

### Create Bot

1. Message [@BotFather](https://t.me/BotFather)
2. Send: `/newbot`
3. Choose name: `YourSignals Bot`
4. Choose username: `yoursignals_bot`
5. Copy token → `TELEGRAM_BOT_TOKEN`

### Get Admin Chat ID

```bash
# Start conversation with your bot
# Then run:
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates

# Find your chat ID in the response
# Copy to TELEGRAM_ADMIN_CHAT_ID
```

### Create Free Channel

1. Create public channel
2. Add bot as administrator
3. Give bot posting permissions
4. Channel username → `TELEGRAM_FREE_CHANNEL_ID`

### Create VIP Channel

1. Create private channel
2. Add bot as administrator
3. Give bot posting permissions
4. Get channel ID:
   ```bash
   # Post in channel, then:
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   # Find channel ID (starts with -100)
   ```
5. Copy to `TELEGRAM_VIP_CHANNEL_ID`

---

## 💳 Step 5: Stripe Setup

### Create Product

1. Go to Stripe Dashboard
2. Products → Create Product
3. **Name:** VIP Crypto Signals
4. **Description:** Premium crypto trading signals
5. **Pricing:**
   - Type: Recurring
   - Billing period: Monthly
   - Price: $99 (or your price)
6. Copy Price ID → `STRIPE_VIP_PRICE_ID`

### Configure Webhook

1. Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/api/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy signing secret → `STRIPE_WEBHOOK_SECRET`

---

## 🌐 Step 6: Domain & SSL

### Configure Domain

```bash
# Point your domain to server IP
# A record: api.yourdomain.com → YOUR_SERVER_IP
# A record: dashboard.yourdomain.com → YOUR_SERVER_IP
```

### Install Nginx

```bash
sudo apt install nginx -y

# Create config
sudo nano /etc/nginx/sites-available/cryptopulse
```

**Nginx Configuration:**

```nginx
# API Server
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Dashboard
server {
    listen 80;
    server_name dashboard.yourdomain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/cryptopulse /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Install SSL (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificates
sudo certbot --nginx -d api.yourdomain.com -d dashboard.yourdomain.com

# Auto-renewal is configured automatically
```

---

## 🐳 Step 7: Deploy with Docker

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Verify all services running
docker-compose ps | grep Up
```

---

## ✅ Step 8: Verification

### Test API

```bash
curl https://api.yourdomain.com/health
# Should return: {"status":"healthy","timestamp":"..."}
```

### Test Dashboard

Visit: `https://dashboard.yourdomain.com`

### Test Telegram Bot

1. Send `/start` to your bot
2. Should receive welcome message

### Test Signal Flow

1. Wait for market scan (every 5/15/60 minutes)
2. Check admin chat for signal approval
3. Approve a signal
4. Verify it appears in channels

---

## 📊 Step 9: Monitoring

### View Logs

```bash
# Real-time logs
docker-compose logs -f cryptopulse-engine

# Error logs
tail -f logs/errors_$(date +%Y-%m-%d).log

# All logs
tail -f logs/cryptopulse_$(date +%Y-%m-%d).log
```

### Set Up Alerts

Create monitoring script:

```bash
# monitor.sh
#!/bin/bash

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    # Send alert (configure your notification method)
    echo "ALERT: Service down!" | mail -s "CryptoPulse Alert" your@email.com
fi
```

```bash
# Add to crontab
crontab -e
# Add: */5 * * * * /path/to/monitor.sh
```

---

## 🔄 Step 10: Maintenance

### Update Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Backup Database

```bash
# Supabase has automatic backups
# For local backup:
docker-compose exec postgres pg_dump -U postgres cryptopulse > backup.sql
```

### View Performance

```bash
# Dashboard: https://dashboard.yourdomain.com
# Check: Overview → Performance metrics
```

---

## 🚨 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Bot Not Responding

```bash
# Check bot logs
docker-compose logs cryptopulse-engine | grep telegram

# Verify token
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### Database Connection Issues

```bash
# Check Supabase status
# Verify credentials in .env
# Test connection:
docker-compose exec cryptopulse-engine python -c "from src.database.supabase_client import SupabaseClient; SupabaseClient()"
```

---

## 🔐 Security Hardening

### Firewall

```bash
# Install UFW
sudo apt install ufw -y

# Configure
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Fail2Ban

```bash
# Install
sudo apt install fail2ban -y

# Configure
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Regular Updates

```bash
# Create update script
cat > update.sh << 'EOF'
#!/bin/bash
sudo apt update
sudo apt upgrade -y
docker-compose pull
docker-compose up -d
EOF

chmod +x update.sh

# Run weekly
crontab -e
# Add: 0 3 * * 0 /path/to/update.sh
```

---

## 📈 Scaling

### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  cryptopulse-engine:
    deploy:
      replicas: 3
```

### Load Balancing

Use nginx upstream for multiple instances.

### Database Optimization

- Enable connection pooling
- Add indexes for frequent queries
- Regular VACUUM on PostgreSQL

---

## ✅ Post-Deployment Checklist

- [ ] All services running
- [ ] API accessible via HTTPS
- [ ] Dashboard accessible via HTTPS
- [ ] Telegram bot responding
- [ ] Signals being generated
- [ ] Database connected
- [ ] Stripe webhooks working
- [ ] Logs being written
- [ ] Monitoring configured
- [ ] Backups scheduled
- [ ] SSL certificates valid
- [ ] Firewall configured

---

## 🎉 Go Live!

Your SIGNALFORGE AI platform is now live and ready to generate premium crypto signals!

**Next Steps:**
1. Monitor first 24 hours closely
2. Verify signal quality
3. Test subscription flow
4. Promote to users
5. Scale as needed

---

**Support:** For deployment issues, check logs and documentation.
