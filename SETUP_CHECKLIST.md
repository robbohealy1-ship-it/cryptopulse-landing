# CRYPTO PULSE — Complete Setup Checklist

## CRITICAL (Must Have Before Selling)

### 1. Telegram (Required)
| Variable | What It Is | How to Get It |
|----------|-----------|---------------|
| `TELEGRAM_BOT_TOKEN` | Admin bot token | @BotFather → /newbot |
| `TELEGRAM_ADMIN_CHAT_ID` | Your personal Telegram ID | Message @userinfobot |
| `TELEGRAM_FREE_CHANNEL_ID` | Free public channel | Create channel → @channelname or -100... |
| `TELEGRAM_VIP_CHANNEL_ID` | VIP private channel | Create channel → add bot as admin |
| `TELEGRAM_VIP_BOT_TOKEN` | Public signup bot (optional) | @BotFather → /newbot |
| `TELEGRAM_VIP_BOT_USERNAME` | Bot @handle | e.g. `CryptoPulseVIPBot` |
| `TELEGRAM_BOT_USERNAME` | Admin bot @handle | e.g. `cryptopulse_admin_bot` |

**Setup Steps:**
1. Create **Free Channel** (public) — free signals go here
2. Create **VIP Channel** (private) — invite-only, add bot as admin
3. Create **Admin Bot** (@BotFather) — for approving signals
4. Create **VIP Bot** (@BotFather) — for public signup/payments (optional but recommended)
5. Get your Chat ID from @userinfobot

---

### 2. Supabase (Required)
| Variable | What It Is | How to Get It |
|----------|-----------|---------------|
| `SUPABASE_URL` | Your project URL | Supabase dashboard → Settings → API |
| `SUPABASE_KEY` | Anon/public key | Supabase dashboard → Settings → API |
| `SUPABASE_SERVICE_KEY` | Service role key | Supabase dashboard → Settings → API (secret) |

**Tables You Need** (run in Supabase SQL Editor):

```sql
-- Main signals table
CREATE TABLE IF NOT EXISTS signals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol text NOT NULL,
    direction text,
    entry_price numeric,
    stop_loss numeric,
    take_profit numeric,
    take_profit_1 numeric,
    take_profit_2 numeric,
    take_profit_3 numeric,
    confidence numeric,
    status text DEFAULT 'pending',
    timeframe text,
    setup_type text,
    risk_reward numeric,
    atr numeric,
    volume_24h numeric,
    technical_score jsonb,
    context_score jsonb,
    reasoning text,
    market_context text,
    news_context text,
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz,
    approved_at timestamptz,
    published_at timestamptz,
    closed_at timestamptz,
    actual_entry numeric,
    actual_exit numeric,
    pnl_percent numeric,
    tp1_hit boolean DEFAULT false,
    tp2_hit boolean DEFAULT false,
    tp3_hit boolean DEFAULT false,
    admin_approved boolean DEFAULT false,
    vip_channel_posted boolean DEFAULT false,
    free_channel_posted boolean DEFAULT false,
    free_channel_message_id bigint,
    vip_channel_message_id bigint
);

-- Subscribers / VIP members table
CREATE TABLE IF NOT EXISTS subscribers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text UNIQUE,
    telegram_user_id text,
    username text,
    email text,
    tier text DEFAULT 'free',
    active boolean DEFAULT true,
    status text DEFAULT 'active',
    payment_method text,
    subscription_start timestamptz,
    subscription_end timestamptz,
    trial_ends_at timestamptz,
    created_at timestamptz DEFAULT now(),
    cancelled_at timestamptz,
    stripe_customer_id text,
    stripe_subscription_id text
);

-- Crypto payments tracking
CREATE TABLE IF NOT EXISTS crypto_payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text,
    telegram_user_id text,
    plan text,
    amount_usd numeric,
    currency text,
    wallet_address text,
    status text DEFAULT 'pending',
    transaction_hash text,
    created_at timestamptz DEFAULT now(),
    paid_at timestamptz,
    expires_at timestamptz
);

-- Alpha/Degen plays (optional)
CREATE TABLE IF NOT EXISTS alpha_plays (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol text NOT NULL,
    name text,
    chain text,
    direction text,
    entry_price numeric,
    stop_loss numeric,
    take_profit numeric,
    confidence numeric,
    status text DEFAULT 'active',
    created_at timestamptz DEFAULT now(),
    approved_at timestamptz,
    closed_at timestamptz,
    pnl_percent numeric
);

-- Marketing posts tracking
CREATE TABLE IF NOT EXISTS marketing_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text,
    content text,
    channel text,
    message_id bigint,
    status text DEFAULT 'published',
    created_at timestamptz DEFAULT now()
);

-- Scheduled posts
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text,
    content text,
    channel text,
    scheduled_at timestamptz,
    status text DEFAULT 'pending',
    created_at timestamptz DEFAULT now()
);
```

---

### 3. Binance API (Optional — Works Without Keys)
| Variable | What It Is | How to Get It |
|----------|-----------|---------------|
| `BINANCE_API_KEY` | Spot API key | Binance → API Management |
| `BINANCE_API_SECRET` | Spot API secret | Binance → API Management |

**Note:** The system works fine with **public API** (no keys). Keys only help if you hit rate limits.

---

## OPTIONAL (Nice to Have, Not Critical)

### 4. Stripe Payments
| Variable | What It Is | How to Get It |
|----------|-----------|---------------|
| `STRIPE_SECRET_KEY` | Backend key | Stripe Dashboard → Developers → API Keys |
| `STRIPE_PUBLISHABLE_KEY` | Frontend key | Same as above |
| `STRIPE_WEBHOOK_SECRET` | Webhook secret | Stripe → Webhooks → Add endpoint |
| `STRIPE_VIP_PRICE_ID` | Product price ID | Stripe → Products → Create Price |

**Without Stripe:** Crypto payments still work (BTC, ETH, SOL, etc.)

---

### 5. News API (Optional — Enhances Signal Context)
| Variable | What It Is | How to Get It |
|----------|-----------|---------------|
| `NEWS_API_KEY` | News data | newsapi.org → Sign up → API Key |

**Without NewsAPI:** Signals still generate, but without news context scoring.

---

### 6. Twitter/X Posting (Optional)
| Variable | What It Is | How to Get It |
|----------|-----------|---------------|
| `TWITTER_API_KEY` | App key | developer.twitter.com |
| `TWITTER_API_SECRET` | App secret | Same |
| `TWITTER_ACCESS_TOKEN` | User token | Same |
| `TWITTER_ACCESS_SECRET` | User secret | Same |

**Without Twitter:** Signals still publish to Telegram. Twitter is bonus marketing.

---

### 7. Discord (Optional)
| Variable | What It Is |
|----------|-----------|
| `DISCORD_WEBHOOK_URL` | Webhook URL from your Discord server |

---

### 8. Reddit (Optional)
| Variable | What It Is |
|----------|-----------|
| `REDDIT_CLIENT_ID` | Reddit app ID |
| `REDDIT_CLIENT_SECRET` | Reddit app secret |
| `REDDIT_USERNAME` | Your Reddit username |
| `REDDIT_PASSWORD` | Your Reddit password |

---

### 9. Crypto Wallet Addresses (For Payments)
| Variable | Purpose |
|----------|---------|
| `CRYPTO_WALLET_BTC` | Bitcoin wallet |
| `CRYPTO_WALLET_ETH` | Ethereum wallet |
| `CRYPTO_WALLET_SOL` | Solana wallet |
| `CRYPTO_WALLET_LTC` | Litecoin wallet |
| `CRYPTO_WALLET_LINK` | Chainlink wallet |
| `CRYPTO_WALLET_HYPE` | Hyperliquid wallet |

**Note:** These are YOUR wallets where customers send payments. Use a secure wallet.

---

### 10. Alpha/Degen Plays Channels (Optional)
| Variable | What It Is |
|----------|-----------|
| `TELEGRAM_DEGEN_CHANNEL_ID` | Free channel for low-cap plays |
| `TELEGRAM_DEGEN_VIP_CHANNEL_ID` | VIP channel for low-cap plays |

---

## QUICK START CHECKLIST

- [ ] Telegram Free Channel created
- [ ] Telegram VIP Channel created
- [ ] Admin Bot created (@BotFather)
- [ ] Supabase project created
- [ ] Supabase tables created (run SQL above)
- [ ] `.env` file filled with all keys
- [ ] Logo image saved as `assets/logo.png`
- [ ] Test signal created → appears in Active Trades
- [ ] Test signal published to Telegram channels

## LAUNCH CHECKLIST

- [ ] Dashboard running on `localhost:8081`
- [ ] Admin bot responding to commands
- [ ] VIP bot responding to `/start`
- [ ] Auto signals generating (or manual signals working)
- [ ] Payment links ready (Stripe or crypto)
- [ ] Free channel has teaser/content for non-members
- [ ] VIP channel has first signal posted
