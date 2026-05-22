from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: Optional[str] = "cryptopulse_admin_bot"  # Admin bot @username
    TELEGRAM_ADMIN_CHAT_ID: str
    TELEGRAM_FREE_CHANNEL_ID: str
    TELEGRAM_VIP_CHANNEL_ID: str
    
    # VIP Bot (separate public bot for signup/payments)
    TELEGRAM_VIP_BOT_TOKEN: Optional[str] = None
    TELEGRAM_VIP_BOT_USERNAME: Optional[str] = "CryptoPulseVIPBot"
    
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str
    
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_VIP_PRICE_ID: Optional[str] = None
    
    # Crypto Payment Wallets
    CRYPTO_WALLET_BTC: Optional[str] = None
    CRYPTO_WALLET_ETH: Optional[str] = None
    CRYPTO_WALLET_SOL: Optional[str] = None
    CRYPTO_WALLET_LTC: Optional[str] = None
    CRYPTO_WALLET_ZEC: Optional[str] = None
    CRYPTO_WALLET_XMR: Optional[str] = None
    CRYPTO_WALLET_HYPE: Optional[str] = None
    CRYPTO_WALLET_LINK: Optional[str] = None
    
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    
    NEWS_API_KEY: Optional[str] = None
    
    # Fundamental Data Sources (all optional)
    CRYPTOPANIC_API_KEY: Optional[str] = None
    GLASSNODE_API_KEY: Optional[str] = None
    SANTIMENT_API_KEY: Optional[str] = None
    LUNARCRUSH_API_KEY: Optional[str] = None
    MESSARI_API_KEY: Optional[str] = None
    COINMARKETCAP_API_KEY: Optional[str] = None
    THEGRAPH_API_KEY: Optional[str] = None
    DUNE_API_KEY: Optional[str] = None
    TRADINGVIEW_WEBHOOK_SECRET: Optional[str] = None
    
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"
    MIN_CONFIDENCE_SCORE: int = 85
    MAX_SIGNALS_PER_DAY: int = 5
    MIN_DAILY_VOLUME_USD: float = 10000000
    
    # VIP-exclusive signals (higher quality)
    VIP_MIN_CONFIDENCE: int = 90
    FREE_MAX_SIGNALS_PER_DAY: int = 2
    
    SIGNAL_EXPIRY_MINUTES: int = 30
    MIN_RISK_REWARD: float = 2.0
    
    # Free channel delay after VIP (minutes)
    FREE_CHANNEL_DELAY_MINUTES: int = 10
    
    # VIP Pricing (USD)
    VIP_MONTHLY_PRICE: float = 49.0
    VIP_QUARTERLY_PRICE: float = 129.0
    VIP_LIFETIME_PRICE: float = 299.0
    
    # Affiliate Exchange Link
    # Built-in options: binance, bybit, okx, bitget, mexc, kucoin
    # If ALL exchanges block UK referrals, use 'custom' and set your own URL below
    AFFILIATE_EXCHANGE: str = "custom"  # Use 'custom' for any URL you want
    AFFILIATE_EXCHANGE_REF: Optional[str] = None  # Ref code (used with built-in exchanges)
    
    # Custom affiliate URL (overrides everything above when AFFILIATE_EXCHANGE=custom)
    # Paste ANY link you want here - Coinbase, Kraken, Luno, a blog, anything
    AFFILIATE_CUSTOM_URL: Optional[str] = None  # e.g. "https://kraken.com/?ref=XYZ"
    
    # Marketing automation settings
    MARKETING_POSTS_PER_DAY: int = 4  # Posts per day to free channel
    MARKETING_POST_HOUR_START: int = 8
    MARKETING_POST_HOUR_END: int = 22
    
    # ==================== SOCIAL MEDIA INTEGRATION ====================
    # Twitter/X API (optional - for auto-posting signals)
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_SECRET: Optional[str] = None
    
    # Reddit API (optional - for posting to crypto subreddits)
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USERNAME: Optional[str] = None
    REDDIT_PASSWORD: Optional[str] = None
    
    # Discord Webhooks (optional - for cross-posting to Discord servers)
    DISCORD_WEBHOOK_URL: Optional[str] = None        # Main signals channel
    DISCORD_VIP_WEBHOOK_URL: Optional[str] = None    # VIP lounge channel
    DISCORD_ALPHA_WEBHOOK_URL: Optional[str] = None  # Alpha plays channel
    
    # Generic webhook for IFTTT/Zapier/custom integrations
    MARKETING_WEBHOOK_URL: Optional[str] = None
    
    # Admin Dashboard
    ADMIN_DASHBOARD_PORT: int = 8080
    
    # Viral content generation
    ENABLE_VIRAL_CONTENT: bool = True  # Generate shareable images for signals
    
    # Community engagement
    ENABLE_ENGAGEMENT_LOOP: bool = True  # Auto-post polls, questions, CTAs
    ENABLE_WELCOME_MESSAGES: bool = True  # Auto-welcome new members
    
    # Invite contest
    ENABLE_REFERRAL_CONTEST: bool = True
    
    # ==================== SIGNAL QUALITY ====================
    # Ultra-strict 5m mode: requires 2+ confluence factors, volume spike, fresh candle
    ULTRA_STRICT_5M: bool = True
    STRICT_5M_CONFLUENCE_MIN: int = 2  # Minimum setup types aligning for 5m
    STRICT_5M_VOLUME_MULTIPLIER: float = 2.0  # Volume must be >2x average for 5m
    STRICT_5M_RSI_LONG_MAX: float = 68.0  # LONG: RSI must be below this
    STRICT_5M_RSI_SHORT_MIN: float = 32.0  # SHORT: RSI must be above this
    STRICT_5M_CANDLE_FRESHNESS: float = 0.6  # Price must be within this % of candle range from open
    STRICT_5M_CONTEXT_MIN: float = 55.0  # Context score minimum for 5m
    STRICT_5M_NEWS_MIN: float = 45.0  # News score minimum for 5m
    
    # Report settings
    DAILY_REPORT_HOUR: int = 23
    DAILY_REPORT_MINUTE: int = 55
    WEEKLY_REPORT_DAY: str = "sun"  # mon, tue, wed, thu, fri, sat, sun
    WEEKLY_REPORT_HOUR: int = 20
    
    DATABASE_URL: Optional[str] = None
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    STREAMLIT_PORT: int = 8501
    
    # ==================== ALPHA/DEGEN PLAYS ====================
    # Telegram channels for alpha plays (low-cap degen plays)
    TELEGRAM_DEGEN_CHANNEL_ID: Optional[str] = None      # Free alpha channel
    TELEGRAM_DEGEN_VIP_CHANNEL_ID: Optional[str] = None  # VIP alpha channel
    
    # Alpha play settings
    ALPHA_MIN_SCORE: float = 70.0          # Minimum score for alpha discovery
    ALPHA_AUTO_APPROVE: bool = False        # Auto-approve high-score plays
    ALPHA_VIP_DAILY_LIMIT: int = 1        # Max alpha plays per day for VIP
    ALPHA_FREE_WEEKLY_LIMIT: int = 1      # Max alpha plays per week for FREE
    
    # DEX APIs for low-cap scanning
    DEXSCREENER_API_KEY: Optional[str] = None
    BIRDEYE_API_KEY: Optional[str] = None  # For SOL token analytics
    MORALIS_API_KEY: Optional[str] = None  # For ETH on-chain data
    
    # DEX Referral Codes (earn % of swap fees when users trade through your links)
    # Jupiter (Solana): Create at referral.jup.ag - your code = your Solana wallet address
    # NOTE: Uniswap and 1inch have NO swap referral programs. Only Jupiter works.
    JUPITER_REFERRAL_CODE: Optional[str] = None
    
    # ==================== EXCHANGE ACCOUNT MONITORING (READ-ONLY) ====================
    # cTrader (BEM Funding) — OAuth2 access token + account ID
    CTRADER_ACCESS_TOKEN: Optional[str] = None
    CTRADER_ACCOUNT_ID: Optional[str] = None
    CTRADER_SERVER: str = "live"  # "live" or "demo"
    
    # MEXC Personal — API key + secret (READ-ONLY permissions recommended)
    MEXC_API_KEY: Optional[str] = None
    MEXC_API_SECRET: Optional[str] = None
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }


settings = Settings()
