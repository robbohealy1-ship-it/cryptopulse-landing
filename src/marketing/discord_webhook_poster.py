"""
Discord Webhook Marketing System
Posts AI-generated marketing messages to multiple Discord servers via webhooks
"""
import asyncio
import aiohttp
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DiscordWebhookPoster:
    """Automated marketing posting to Discord servers via webhooks"""

    def __init__(self, db=None):
        self.db = db
        self.webhooks = self._load_webhooks()

        # AI-generated marketing templates (Discord-optimized)
        self.templates = {
            'performance': [
                {
                    "title": "Weekly Performance Update",
                    "description": "Our AI-powered signals continue to deliver results!\n\n"
                                  ":white_check_mark: Consistent win rate\n"
                                  ":white_check_mark: Transparent tracking\n"
                                  ":white_check_mark: Professional risk management\n\n"
                                  ":iphone: Join our FREE Telegram: t.me/cryptopulse_signals_free1\n"
                                  ":star: VIP Access: t.me/CryptoPulseVIPAccessBot",
                    "color": 0x00ff00
                },
                {
                    "title": "Signal Results",
                    "description": "Real signals. Real results. No fake screenshots.\n\n"
                                  "Every trade is tracked and transparent.\n\n"
                                  ":gem: Free Telegram Channel: t.me/cryptopulse_signals_free1\n"
                                  ":rocket: VIP Upgrades: t.me/CryptoPulseVIPAccessBot",
                    "color": 0x3498db
                },
            ],

            'social_proof': [
                {
                    "title": "Another Winning Signal!",
                    "description": "VIP members just banked another profit.\n\n"
                                  "Free members see the teasers.\n"
                                  "VIP members get the full setup.\n\n"
                                  ":point_right: Join FREE: t.me/cryptopulse_signals_free1",
                    "color": 0xff9500
                },
                {
                    "title": "What VIP Members Get",
                    "description": ":white_check_mark: 90%+ confidence signals\n"
                                  ":white_check_mark: Complete trade plans\n"
                                  ":white_check_mark: Real-time updates\n"
                                  ":white_check_mark: Risk management guidance\n\n"
                                  "Free: t.me/cryptopulse_signals_free1\n"
                                  "VIP: t.me/CryptoPulseVIPAccessBot",
                    "color": 0x9b59b6
                },
            ],

            'educational': [
                {
                    "title": "Trading Tip: Use Stop Loss",
                    "description": "Even the best traders lose sometimes.\n"
                                  "The key is controlling your risk.\n\n"
                                  "Our signals include precise SL levels.\n\n"
                                  "Learn more: t.me/cryptopulse_signals_free1",
                    "color": 0x1abc9c
                },
                {
                    "title": "Trading Tip: Follow the Trend",
                    "description": "The market doesn't care about your opinion.\n"
                                  "Trade what you see, not what you think.\n\n"
                                  "Our signals use multi-timeframe analysis.\n\n"
                                  "Free signals: t.me/cryptopulse_signals_free1",
                    "color": 0xe74c3c
                },
            ],

            'urgency': [
                {
                    "title": "Signal Alert Incoming",
                    "description": "Our AI just detected a high-probability setup!\n\n"
                                  "Free channel gets the teaser.\n"
                                  "VIP channel gets the full plan.\n\n"
                                  ":point_right: t.me/cryptopulse_signals_free1",
                    "color": 0xff0000
                },
                {
                    "title": "Limited VIP Spots",
                    "description": "Join elite traders getting professional signals:\n\n"
                                  ":white_check_mark: 3 elite signals/day\n"
                                  ":white_check_mark: 90%+ confidence only\n"
                                  ":white_check_mark: Complete trade management\n\n"
                                  "Free: t.me/cryptopulse_signals_free1\n"
                                  "VIP: t.me/CryptoPulseVIPAccessBot",
                    "color": 0xffd700
                },
            ],

            'value_prop': [
                {
                    "title": "Why CryptoPulse?",
                    "description": ":white_check_mark: AI + Technical Analysis\n"
                                  ":white_check_mark: 90%+ confidence threshold\n"
                                  ":white_check_mark: Entry, SL, 3 TPs every signal\n"
                                  ":white_check_mark: Real-time updates\n"
                                  ":white_check_mark: Transparent, trackable results\n\n"
                                  "Join FREE: t.me/cryptopulse_signals_free1",
                    "color": 0x2ecc71
                },
                {
                    "title": "Free vs VIP",
                    "description": "**Free Channel:**\n"
                                  ":white_check_mark: 1 full signal/day\n"
                                  ":white_check_mark: Unlimited teasers\n"
                                  ":white_check_mark: Performance updates\n\n"
                                  "**VIP Channel:**\n"
                                  ":white_check_mark: 3 elite signals/day\n"
                                  ":white_check_mark: Full analysis & context\n"
                                  ":white_check_mark: Priority support\n\n"
                                  "Free: t.me/cryptopulse_signals_free1\n"
                                  "VIP: t.me/CryptoPulseVIPAccessBot",
                    "color": 0x3498db
                },
            ],
        }

        logger.info(f"Discord Webhook Poster initialized with {len(self.webhooks)} webhooks")

    def _load_webhooks(self) -> List[str]:
        """Load webhook URLs from environment"""
        webhooks_str = getattr(settings, 'DISCORD_WEBHOOK_URLS', None)
        if not webhooks_str:
            logger.warning("No DISCORD_WEBHOOK_URLS configured in .env")
            return []

        # Parse comma-separated webhook URLs
        webhooks = [w.strip() for w in webhooks_str.split(',') if w.strip()]

        # Validate URLs look like Discord webhooks
        valid_webhooks = []
        for webhook in webhooks:
            if 'discord.com/api/webhooks/' in webhook or 'discordapp.com/api/webhooks/' in webhook:
                valid_webhooks.append(webhook)
            else:
                logger.warning(f"Invalid Discord webhook URL: {webhook}")

        return valid_webhooks

    def _get_random_embed(self, category: Optional[str] = None) -> dict:
        """Get a random Discord embed"""
        if category and category in self.templates:
            return random.choice(self.templates[category])

        # Random category
        all_embeds = []
        for embeds in self.templates.values():
            all_embeds.extend(embeds)

        return random.choice(all_embeds)

    def _get_performance_embed(self) -> dict:
        """Generate performance-based embed with real stats"""
        if not self.db:
            return self._get_random_embed('performance')

        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            result = self.db.client.table('signals')\
                .select('*')\
                .eq('status', 'closed')\
                .gte('created_at', week_ago.isoformat())\
                .execute()

            signals = result.data if hasattr(result, 'data') else []

            if not signals:
                return self._get_random_embed('performance')

            wins = [s for s in signals if (s.get('pnl_percent') or 0) > 0]
            total_pnl = sum(s.get('pnl_percent', 0) or 0 for s in signals)
            win_rate = (len(wins) / len(signals) * 100) if signals else 0

            best_signal = max(signals, key=lambda x: x.get('pnl_percent') or 0)

            return {
                "title": "Weekly Performance Report",
                "description": f"**This Week's Results:**\n\n"
                               f":chart_with_upwards_trend: Signals: {len(signals)}\n"
                               f":white_check_mark: Winners: {len(wins)}\n"
                               f":bar_chart: Win Rate: {win_rate:.1f}%\n"
                               f":moneybag: Total P&L: +{total_pnl:.2f}%\n\n"
                               f":fire: Best: {best_signal.get('symbol', 'N/A')} (+{best_signal.get('pnl_percent', 0):.2f}%)\n\n"
                               f"All signals tracked transparently.\n\n"
                               f":gem: Free: t.me/cryptopulse_signals_free1\n"
                               f":star: VIP: t.me/CryptoPulseVIPAccessBot",
                "color": 0x00ff00
            }
        except Exception as e:
            logger.error(f"Error generating performance embed: {e}")
            return self._get_random_embed('performance')

    async def post_to_webhook(self, webhook_url: str, embed: dict, delay: int = 0) -> bool:
        """Post a message to a single Discord webhook"""
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            payload = {
                "embeds": [embed],
                "username": "CryptoPulse Signals",
                "avatar_url": "https://cryptopulse-signals.com/logo.png"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"Posted to Discord webhook")
                        return True
                    else:
                        body = await resp.text()
                        logger.warning(f"Discord webhook failed: HTTP {resp.status} - {body}")
                        return False

        except Exception as e:
            logger.error(f"Discord webhook error: {e}")
            return False

    async def post_to_all_webhooks(self, embed: Optional[dict] = None, category: Optional[str] = None) -> Dict[str, bool]:
        """Post to all configured Discord webhooks with delays"""
        if not self.webhooks:
            logger.warning("No Discord webhooks configured. Add DISCORD_WEBHOOK_URLS to .env")
            return {}

        # Generate embed if not provided
        if not embed:
            if category == 'performance':
                embed = self._get_performance_embed()
            else:
                embed = self._get_random_embed(category)

        logger.info(f"Posting to {len(self.webhooks)} Discord webhooks...")

        results = {}
        for i, webhook_url in enumerate(self.webhooks):
            # Add delay between posts (30-60 seconds) to avoid rate limits
            delay = random.randint(30, 60) if i > 0 else 0
            success = await self.post_to_webhook(webhook_url, embed, delay)
            results[webhook_url] = success

        successful = sum(1 for v in results.values() if v)
        logger.info(f"Posted to {successful}/{len(self.webhooks)} Discord webhooks")

        return results

    async def daily_marketing_post(self):
        """Execute daily automated marketing post to Discord"""
        hour = datetime.utcnow().hour

        # Choose message type based on time of day
        if 8 <= hour < 12:
            category = random.choice(['performance', 'social_proof'])
        elif 12 <= hour < 18:
            category = random.choice(['educational', 'value_prop'])
        else:
            category = random.choice(['urgency', 'social_proof'])

        logger.info(f"Executing Discord daily marketing post ({category})")
        return await self.post_to_all_webhooks(category=category)

    async def weekly_performance_post(self):
        """Post weekly performance report to Discord"""
        logger.info("Executing Discord weekly performance post")
        return await self.post_to_all_webhooks(category='performance')

    async def custom_post(self, title: str, description: str, color: int = 0x3498db):
        """Post a custom message to all Discord webhooks"""
        embed = {
            "title": title,
            "description": description,
            "color": color
        }
        return await self.post_to_all_webhooks(embed=embed)
