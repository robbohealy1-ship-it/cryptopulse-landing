"""
Social Media Auto-Poster
Posts signal teasers and performance stats to Twitter/X and Reddit
"""

import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SocialMediaPoster:
    """Automated social media posting for signal marketing"""
    
    def __init__(self):
        self.twitter_enabled = False
        self.reddit_enabled = False
        self._init_twitter()
        self._init_reddit()
        
        # Posting schedule (UTC)
        self.optimal_hours = [8, 12, 15, 18, 21]  # Morning, lunch, afternoon, evening
        
        # Hashtag pools for rotation
        self.hashtags = {
            'general': [
                '#CryptoTrading', '#Bitcoin', '#Altcoins', '#TradingSignals',
                '#CryptoSignals', '#DayTrading', '#TechnicalAnalysis'
            ],
            'bullish': [
                '#BullRun', '#CryptoBull', '#ToTheMoon', '#BuySignal',
                '#LongTrade', '#BullishAF'
            ],
            'community': [
                '#CryptoCommunity', '#TradingGroup', '#LearnTrading',
                '#CryptoEducation', '#TradingTips'
            ],
        }
    
    def _init_twitter(self):
        """Initialize Twitter/X API client"""
        try:
            import tweepy
            
            api_key = getattr(settings, 'TWITTER_API_KEY', None)
            api_secret = getattr(settings, 'TWITTER_API_SECRET', None)
            access_token = getattr(settings, 'TWITTER_ACCESS_TOKEN', None)
            access_secret = getattr(settings, 'TWITTER_ACCESS_SECRET', None)
            
            if all([api_key, api_secret, access_token, access_secret]):
                auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
                self.twitter_api = tweepy.API(auth)
                self.twitter_client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_secret
                )
                self.twitter_enabled = True
                logger.info("Twitter/X API initialized")
            else:
                logger.info("Twitter credentials not set - Twitter posting disabled")
        except ImportError:
            logger.info("tweepy not installed - Twitter posting disabled")
        except Exception as e:
            logger.error(f"Twitter init error: {e}")
    
    def _init_reddit(self):
        """Initialize Reddit API client"""
        try:
            import praw
            
            client_id = getattr(settings, 'REDDIT_CLIENT_ID', None)
            client_secret = getattr(settings, 'REDDIT_CLIENT_SECRET', None)
            username = getattr(settings, 'REDDIT_USERNAME', None)
            password = getattr(settings, 'REDDIT_PASSWORD', None)
            
            if all([client_id, client_secret, username, password]):
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    username=username,
                    password=password,
                    user_agent='CryptoPulseSignals/1.0'
                )
                self.reddit_enabled = True
                logger.info("Reddit API initialized")
            else:
                logger.info("Reddit credentials not set - Reddit posting disabled")
        except ImportError:
            logger.info("praw not installed - Reddit posting disabled")
        except Exception as e:
            logger.error(f"Reddit init error: {e}")
    
    def _get_hashtags(self, sentiment='general', count=3) -> str:
        """Get random hashtags"""
        tags = random.sample(self.hashtags.get(sentiment, self.hashtags['general']), count)
        return ' '.join(tags)
    
    def _get_tradingview_link(self, symbol: str, timeframe: str = '15') -> str:
        """Generate a professional TradingView chart link for any symbol"""
        # Convert symbol format: BTC/USDT -> BINANCE:BTCUSDT
        base, quote = symbol.split('/')
        tv_symbol = f"BINANCE:{base}{quote}"
        
        # Map timeframe to TradingView interval
        interval_map = {'1m': '1', '5m': '5', '15m': '15', '1h': '60', '4h': '240', '1d': 'D'}
        interval = interval_map.get(timeframe, '15')
        
        return f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"
    
    async def post_signal_teaser(self, signal, chart_path: Optional[str] = None) -> dict:
        """Post a signal teaser to all enabled platforms"""
        results = {}
        
        # Build teaser text
        direction_emoji = "🟢 LONG" if signal.direction.value == "LONG" else "🔴 SHORT"
        ticker = signal.symbol.replace('/', '')
        hashtags = self._get_hashtags('bullish' if signal.direction.value == 'LONG' else 'general')
        
        # Get professional TradingView chart link
        tv_link = self._get_tradingview_link(signal.symbol, getattr(signal, 'timeframe', '15m'))
        
        text = (
            f"{direction_emoji} SIGNAL ALERT\n\n"
            f"#{ticker} | Confidence: {signal.confidence:.0f}%\n\n"
            f"📊 Chart: {tv_link}\n\n"
            f"Full analysis + entry/SL/TPs:\n"
            f"t.me/cryptopulse_signals_free1\n\n"
            f"💎 VIP gets 3 profit targets + live updates\n\n"
            f"{hashtags}"
        )
        
        # Twitter
        if self.twitter_enabled:
            try:
                # Try with image first (if available)
                if chart_path and os.path.exists(chart_path):
                    try:
                        media = self.twitter_api.media_upload(chart_path)
                        tweet = self.twitter_client.create_tweet(
                            text=text,
                            media_ids=[media.media_id]
                        )
                        results['twitter'] = f"https://twitter.com/user/status/{tweet.data['id']}"
                        logger.info(f"Tweeted signal teaser with image: {tweet.data['id']}")
                    except Exception as img_err:
                        # Image upload failed (e.g., Basic tier no v1.1) — fallback to text-only
                        logger.warning(f"Twitter image upload failed: {img_err} — posting text-only")
                        tweet = self.twitter_client.create_tweet(text=text)
                        results['twitter'] = f"https://twitter.com/user/status/{tweet.data['id']}"
                        logger.info(f"Tweeted signal teaser (text-only fallback): {tweet.data['id']}")
                else:
                    tweet = self.twitter_client.create_tweet(text=text)
                    results['twitter'] = f"https://twitter.com/user/status/{tweet.data['id']}"
                    logger.info(f"Tweeted signal teaser (no image): {tweet.data['id']}")
            except Exception as e:
                logger.error(f"Twitter post failed: {e}")
                results['twitter'] = f"Error: {str(e)[:50]}"
        
        # Reddit
        if self.reddit_enabled:
            try:
                # Post to crypto subreddits
                subreddits = ['cryptocurrency', 'altcoin', 'CryptoMarkets']
                reddit_body = (
                    f"**{direction_emoji} Signal Alert**\n\n"
                    f"**Coin:** {signal.symbol}\n"
                    f"**Confidence:** {signal.confidence:.0f}%\n"
                    f"**Direction:** {signal.direction.value}\n\n"
                    f"**📊 TradingView Chart:** [{tv_link}]({tv_link})\n\n"
                    f"Full trade plan with entry, stop loss and 3 profit targets:\n"
                    f"t.me/cryptopulse_signals_free1\n\n"
                    f"*This is a signal teaser. VIP members get full analysis and live updates.*"
                )
                for sub in subreddits[:1]:  # Only post to 1 to avoid spam
                    post = self.reddit.subreddit(sub).submit(
                        title=f"[{signal.direction.value}] {ticker} - {signal.confidence:.0f}% Confidence Signal",
                        selftext=reddit_body,
                        flair_id=None
                    )
                    results[f'reddit_{sub}'] = f"https://reddit.com{post.permalink}"
                    logger.info(f"Posted to r/{sub}: {post.id}")
                    break  # Only post to one subreddit
            except Exception as e:
                logger.error(f"Reddit post failed: {e}")
                results['reddit'] = f"Error: {str(e)[:50]}"
        
        return results
    
    async def post_performance_stats(self, stats: dict) -> dict:
        """Post weekly/monthly performance to social media"""
        results = {}
        
        text = (
            f"📊 WEEKLY PERFORMANCE\n\n"
            f"Signals: {stats.get('total_signals', 0)}\n"
            f"Win Rate: {stats.get('win_rate', 0):.1f}%\n"
            f"Total P&L: {stats.get('total_pnl', 0):.2f}%\n\n"
            f"Join our FREE channel for the next signal:\n"
            f"t.me/cryptopulse_signals_free1\n\n"
            f"💎 VIP members get full trade plans\n\n"
            f"#CryptoTrading #TradingSignals #Bitcoin"
        )
        
        if self.twitter_enabled:
            try:
                tweet = self.twitter_client.create_tweet(text=text)
                results['twitter'] = f"https://twitter.com/user/status/{tweet.data['id']}"
                logger.info(f"Tweeted performance stats")
            except Exception as e:
                logger.error(f"Twitter stats post failed: {e}")
        
        return results
    
    async def post_marketing_content(self, content_type: str = 'general') -> dict:
        """Post general marketing content"""
        results = {}
        
        templates = {
            'morning_outlook': (
                "🌅 GOOD MORNING TRADERS\n\n"
                "Scanning markets for high-probability setups...\n\n"
                "📈 Join our FREE channel for today's signals:\n"
                "t.me/cryptopulse_signals_free1\n\n"
                "💎 VIP gets 90%+ confidence signals with full plans\n\n"
                "#Bitcoin #CryptoTrading #DayTrading"
            ),
            'evening_recap': (
                "🌙 MARKET WRAP\n\n"
                "Another day of quality signals delivered.\n\n"
                "✅ Free channel got teasers\n"
                "✅ VIP members got full setups\n\n"
                "Don't miss tomorrow's opportunities:\n"
                "t.me/cryptopulse_signals_free1\n\n"
                "#CryptoSignals #TradingGroup"
            ),
            'vip_promo': (
                "💎 WHY GO VIP?\n\n"
                "Free = teaser only\n"
                "VIP = full trade plan\n\n"
                "✅ Entry price\n"
                "✅ Stop loss\n"
                "✅ 3 profit targets\n"
                "✅ Live updates\n\n"
                "DM @CryptoPulseVIPAccessBot\n\n"
                "#CryptoTrading #VIPSignals"
            ),
            'education': (
                "📚 TRADING TIP:\n\n"
                "Never risk more than 2% per trade.\n\n"
                "Even the best systems have losing streaks.\n"
                "Position sizing is what keeps you in the game.\n\n"
                "Join our FREE channel:\n"
                "t.me/cryptopulse_signals_free1\n\n"
                "#CryptoEducation #RiskManagement"
            ),
            'general': (
                "📊 CRYPTO PULSE SIGNALS\n\n"
                "Quality setups. No noise.\n\n"
                "✅ FREE channel: t.me/cryptopulse_signals_free1\n"
                "✅ VIP: Full plans + 3 TPs\n\n"
                "#CryptoSignals #Bitcoin #Trading"
            ),
        }
        
        text = templates.get(content_type, templates['general'])
        
        if self.twitter_enabled:
            try:
                tweet = self.twitter_client.create_tweet(text=text)
                results['twitter'] = f"https://twitter.com/user/status/{tweet.data['id']}"
                logger.info(f"Tweeted marketing content: {content_type}")
            except Exception as e:
                logger.error(f"Twitter marketing post failed: {e}")
        
        return results
    
    async def test_twitter_connection(self) -> dict:
        """
        Diagnostic test to identify exactly why Twitter isn't working.
        Call this from admin bot to debug.
        """
        results = {
            'tweepy_installed': False,
            'credentials_set': False,
            'api_initialized': False,
            'can_read_user': False,
            'can_post_tweet': False,
            'errors': []
        }
        
        # 1. Check tweepy installed
        try:
            import tweepy
            results['tweepy_installed'] = True
            results['tweepy_version'] = tweepy.__version__
        except ImportError:
            results['errors'].append("tweepy not installed. Run: pip install tweepy")
            return results
        
        # 2. Check credentials
        api_key = getattr(settings, 'TWITTER_API_KEY', None)
        api_secret = getattr(settings, 'TWITTER_API_SECRET', None)
        access_token = getattr(settings, 'TWITTER_ACCESS_TOKEN', None)
        access_secret = getattr(settings, 'TWITTER_ACCESS_SECRET', None)
        
        creds_set = all([api_key, api_secret, access_token, access_secret])
        results['credentials_set'] = creds_set
        
        if not creds_set:
            missing = []
            if not api_key: missing.append('TWITTER_API_KEY')
            if not api_secret: missing.append('TWITTER_API_SECRET')
            if not access_token: missing.append('TWITTER_ACCESS_TOKEN')
            if not access_secret: missing.append('TWITTER_ACCESS_SECRET')
            results['errors'].append(f"Missing credentials: {', '.join(missing)}")
            return results
        
        # 3. Try to initialize API
        try:
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
            api = tweepy.API(auth)
            client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_secret
            )
            results['api_initialized'] = True
        except Exception as e:
            results['errors'].append(f"API init failed: {str(e)}")
            return results
        
        # 4. Try to read own user (tests read access)
        try:
            me = client.get_me()
            if me.data:
                results['can_read_user'] = True
                results['username'] = me.data.username
                results['user_id'] = me.data.id
            else:
                results['errors'].append("get_me() returned no data — check app permissions")
        except Exception as e:
            err_str = str(e).lower()
            if '403' in err_str or 'forbidden' in err_str:
                results['errors'].append(f"Read access denied (403): Your API tier may not allow user lookup. Error: {str(e)[:100]}")
            elif '401' in err_str or 'unauthorized' in err_str:
                results['errors'].append(f"Unauthorized (401): Check that your Access Token/Secret are correct. Error: {str(e)[:100]}")
            else:
                results['errors'].append(f"Read test failed: {str(e)[:150]}")
        
        # 5. Try to post a test tweet (tests write access)
        try:
            test_tweet = client.create_tweet(text="Test tweet from CryptoPulse Signals bot 🧪")
            results['can_post_tweet'] = True
            results['test_tweet_id'] = test_tweet.data['id']
            results['test_tweet_url'] = f"https://twitter.com/i/web/status/{test_tweet.data['id']}"
            logger.info(f"✅ Twitter test tweet posted: {results['test_tweet_url']}")
        except Exception as e:
            err_str = str(e).lower()
            if '403' in err_str or 'forbidden' in err_str:
                results['errors'].append(f"Write access denied (403): Your API tier (Free/Basic) may not allow posting. X now requires paid tiers for write access. Error: {str(e)[:150]}")
            elif '401' in err_str or 'unauthorized' in err_str:
                results['errors'].append(f"Write unauthorized (401): Access Token may be expired or wrong. Regenerate at developer.twitter.com. Error: {str(e)[:150]}")
            elif '429' in err_str or 'too many requests' in err_str:
                results['errors'].append(f"Rate limited (429): Too many requests. Wait 15 min and try again.")
            else:
                results['errors'].append(f"Post test failed: {str(e)[:150]}")
        
        return results
    
    def get_next_post_time(self) -> datetime:
        """Get the next optimal posting time"""
        now = datetime.utcnow()
        for hour in self.optimal_hours:
            post_time = now.replace(hour=hour, minute=random.randint(0, 30), second=0)
            if post_time > now:
                return post_time
        # If all hours passed, schedule for tomorrow at first hour
        return (now + timedelta(days=1)).replace(hour=self.optimal_hours[0], minute=0, second=0)
    
    async def run_daily_posting_schedule(self):
        """Run the full daily posting schedule"""
        posts = [
            ('morning_outlook', 8),
            ('education', 12),
            ('vip_promo', 15),
            ('evening_recap', 20),
        ]
        
        for content_type, hour in posts:
            now = datetime.utcnow()
            post_time = now.replace(hour=hour, minute=random.randint(0, 30), second=0)
            if post_time > now:
                wait_seconds = (post_time - now).total_seconds()
                logger.info(f"Scheduling {content_type} post in {wait_seconds/3600:.1f} hours")
                await asyncio.sleep(wait_seconds)
                await self.post_marketing_content(content_type)
            else:
                logger.info(f"Skipping {content_type} - time already passed")


class WebhookPoster:
    """Generic webhook poster for IFTTT, Zapier, custom APIs, etc."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or getattr(settings, 'MARKETING_WEBHOOK_URL', None)
    
    async def post(self, title: str, message: str, image_path: Optional[str] = None) -> bool:
        """Post to a generic webhook"""
        if not self.webhook_url:
            return False
        
        try:
            import aiohttp
            
            payload = {
                'title': title,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'cryptopulse_signals'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"Webhook post successful: {title}")
                        return True
                    else:
                        logger.warning(f"Webhook returned {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Webhook post failed: {e}")
            return False
