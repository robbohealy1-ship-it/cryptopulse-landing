"""
CAMPAIGN ENGINE — Automated Signal & Landing Page Marketing
Orchestrates all marketing channels for maximum reach and conversion.

Campaign types:
- signal_approved: New signal blast to all channels
- signal_result: TP/SL hit = instant FOMO campaign
- daily_content: Scheduled educational/promotional posts
- landing_push: Drive traffic to landing page
- social_proof: Performance stats & testimonials
"""

import asyncio
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import settings
from src.models.signal import TradingSignal, SignalStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CampaignEngine:
    """
    Unified marketing campaign engine.
    Every signal, every win, every milestone becomes a campaign.
    """

    def __init__(
        self,
        social_media=None,
        discord=None,
        channel_publisher=None,
        community_engagement=None,
        viral_generator=None,
        admin_notification=None
    ):
        self.social_media = social_media
        self.discord = discord
        self.channel_publisher = channel_publisher
        self.community_engagement = community_engagement
        self.viral_generator = viral_generator
        self._notify_admin = admin_notification

        # Landing page URL (configured in .env or fallback)
        self.landing_url = getattr(settings, 'LANDING_PAGE_URL', 'https://t.me/CryptoPulseVIPAccessBot')
        self.free_channel = getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None)
        self.vip_channel = getattr(settings, 'TELEGRAM_VIP_CHANNEL_ID', None)

        # Campaign stats
        self.campaigns_sent = 0
        self.last_campaigns = {}  # campaign_type -> datetime

        # Templates
        self._load_templates()

    # ==================== CAMPAIGN: SIGNAL APPROVED ====================

    async def signal_approved_campaign(self, signal: TradingSignal):
        """
        When admin approves a signal, blast it everywhere:
        - VIP channel (full signal)
        - Free channel (teaser with landing page link)
        - Discord (embed)
        - Twitter (if enabled)
        """
        logger.info(f"📢 Campaign: Signal approved — {signal.symbol} {signal.direction.value}")

        # 1. VIP channel — full signal (already handled by channel_publisher, but we log)
        # This is the primary delivery, already done in on_signal_approved

        # 2. Free channel — TEASER CAMPAIGN (drives to VIP)
        await self._free_channel_teaser(signal)

        # 3. Discord — rich embed
        await self._discord_signal_embed(signal)

        # 4. Twitter/X — if available
        await self._twitter_signal_teaser(signal)

        # 5. Viral card DISABLED - user wants only ONE card in free channel
        # await self._viral_signal_card(signal)

        self._track_campaign('signal_approved')

    async def _free_channel_teaser(self, signal: TradingSignal):
        """Post teaser to free channel with strong CTA"""
        if not self.channel_publisher or not self.free_channel:
            return

        direction_emoji = "🟢 LONG" if signal.direction.value == "LONG" else "🔴 SHORT"
        ticker = signal.symbol.replace('/', '')
        tv_link = self._tradingview_link(signal.symbol, getattr(signal, 'timeframe', '15m'))
        
        # Exchange links for ticker
        binance_link = f"https://www.binance.com/en/trade/{ticker}?type=spot"
        bybit_link = f"https://www.bybit.com/trade/spot/{ticker}"

        text = (
            f"🔥 <b>{direction_emoji} SIGNAL ALERT</b>\n\n"
            f"📊 <b><a href='{binance_link}'>{ticker}</a></b> | Confidence: {signal.confidence:.0f}%\n"
            f"⏱ Timeframe: {signal.timeframe}\n\n"
            f"💡 <b>Free channel gets the teaser.</b>\n"
            f"💎 <b>VIP gets the full plan:</b>\n"
            f"   ✅ Exact entry price\n"
            f"   ✅ Stop loss level\n"
            f"   ✅ 3 profit targets\n"
            f"   ✅ Live updates\n\n"
            f"📈 Chart: {tv_link}\n\n"
            f"🔐 <a href='https://t.me/CryptoPulseVIPAccessBot'>Join VIP Instantly</a>\n"
            f"or DM @CryptoPulseVIPAccessBot"
        )

        try:
            await self.channel_publisher.bot.send_message(
                chat_id=self.free_channel,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            logger.info(f"📢 Free channel teaser sent: {signal.symbol}")
        except Exception as e:
            logger.error(f"Free channel teaser failed: {e}")

    async def _discord_signal_embed(self, signal: TradingSignal):
        """Post free teaser to Discord (same format as Telegram Free — no prices)"""
        if not self.discord or not self.discord.enabled:
            return

        try:
            await self.discord.post_free_teaser(signal)
            logger.info(f"📢 Discord free teaser sent: {signal.symbol}")
        except Exception as e:
            logger.error(f"Discord free teaser failed: {e}")

    async def _twitter_signal_teaser(self, signal: TradingSignal):
        """Post signal teaser to Twitter/X if enabled"""
        if not self.social_media or not self.social_media.twitter_enabled:
            return

        try:
            await self.social_media.post_signal_teaser(signal)
            logger.info(f"📢 Twitter signal teaser sent: {signal.symbol}")
        except Exception as e:
            logger.warning(f"Twitter signal teaser failed: {e}")

    async def _viral_signal_card(self, signal: TradingSignal):
        """Generate and post viral card to free channel"""
        if not self.viral_generator or not self.channel_publisher or not self.free_channel:
            return

        try:
            card_path = self.viral_generator.create_signal_card(signal)
            if card_path and os.path.exists(card_path):
                await self.channel_publisher.bot.send_photo(
                    chat_id=self.free_channel,
                    photo=open(card_path, 'rb'),
                    caption=(
                        f"🔥 {signal.symbol} {signal.direction.value} signal!\n\n"
                        f"💎 Get the full plan at {self.landing_url}"
                    ),
                    parse_mode='HTML'
                )
                logger.info(f"📢 Viral card posted: {signal.symbol}")
        except Exception as e:
            logger.error(f"Viral card post failed: {e}")

    # ==================== CAMPAIGN: SIGNAL RESULT (FOMO) ====================

    async def signal_result_campaign(self, signal: TradingSignal, result: dict, pnl: float = None):
        """
        When a signal hits TP or SL, run result marketing:
        - FOMO post to free channel (if TP hit)
        - Transparent SL report (if SL hit)
        """
        # Defensive: only send result campaigns if signal was actually published to VIP
        if not getattr(signal, 'vip_channel_posted', False):
            logger.warning(f"Signal {signal.symbol} result campaign skipped — VIP publish not confirmed")
            return

        hit_tp = result.get('tp_hit')
        hit_sl = result.get('sl_hit')
        pnl = result.get('pnl_percent', 0)

        if hit_tp:
            logger.info(f"🏆 Campaign: TP{hit_tp} hit — FOMO blast for {signal.symbol}")
            await self._fomo_tp_campaign(signal, hit_tp, pnl)
        elif hit_sl:
            logger.info(f"🛑 Campaign: SL hit — transparent report for {signal.symbol}")
            await self._transparent_sl_campaign(signal, pnl)

        self._track_campaign('signal_result')

    async def _fomo_tp_campaign(self, signal: TradingSignal, tp_level: int, pnl: float):
        """FOMO campaign when TP is hit — drives VIP signups"""
        emoji = "🚀" if pnl > 15 else "🔥" if pnl > 8 else "✅"

        # 1. Free channel FOMO post
        if self.channel_publisher and self.free_channel:
            text = (
                f"{emoji} <b>VIP JUST BANKED IT!</b>\n\n"
                f"📊 <b>{signal.symbol}</b> hit <b>TP{tp_level}</b>\n"
                f"💰 P&L: <b>+{pnl:.1f}%</b>\n"
                f"⏱ Timeframe: {signal.timeframe}\n\n"
                f"While free channel watched the teaser...\n"
                f"VIP members executed the full plan.\n\n"
                f"💎 <a href='{self.landing_url}'>Join VIP for the next one</a>\n"
                f"📩 DM @CryptoPulseVIPAccessBot"
            )
            try:
                await self.channel_publisher.bot.send_message(
                    chat_id=self.free_channel,
                    text=text,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            except Exception as e:
                logger.error(f"FOMO free channel failed: {e}")

        # 2. Discord FOMO
        if self.discord and self.discord.enabled:
            try:
                await self.discord.post_marketing(
                    title=f"{emoji} TP{tp_level} Hit: {signal.symbol} +{pnl:.1f}%",
                    message=(
                        f"VIP members just locked in **+{pnl:.1f}%** on {signal.symbol}!\n\n"
                        f"Stop watching from the sidelines.\n"
                        f"🔗 {self.landing_url}"
                    ),
                    color=0x00ff00
                )
            except Exception as e:
                logger.error(f"FOMO Discord failed: {e}")

        # 3. Twitter win tweet
        if self.social_media and self.social_media.twitter_enabled:
            try:
                tweet = (
                    f"{emoji} TP{tp_level} HIT! {signal.symbol}\n\n"
                    f"P&L: +{pnl:.1f}%\n"
                    f"Confidence: {signal.confidence:.0f}%\n\n"
                    f"Every signal: 85%+ confidence + strict risk management\n\n"
                    f"Join VIP: {self.landing_url}\n\n"
                    f"#CryptoSignals #Bitcoin #{signal.symbol.replace('/', '')}"
                )
                self.social_media.twitter_client.create_tweet(text=tweet)
                logger.info(f"📢 Twitter FOMO tweet sent: {signal.symbol}")
            except Exception as e:
                logger.warning(f"Twitter FOMO failed: {e}")

    async def _transparent_sl_campaign(self, signal: TradingSignal, pnl: float):
        """Transparent SL hit — builds trust by showing losses too"""
        if not self.channel_publisher or not self.free_channel:
            return

        text = (
            f"🛑 <b>SL Hit: {signal.symbol}</b>\n\n"
            f"P&L: {pnl:.1f}%\n"
            f"Timeframe: {signal.timeframe}\n\n"
            f"Losses happen. That's trading.\n"
            f"Our system manages risk so one loss doesn't wipe you out.\n\n"
            f"📊 Full transparency — wins AND losses reported.\n\n"
            f"💎 <a href='{self.landing_url}'>See our track record</a>"
        )
        try:
            await self.channel_publisher.bot.send_message(
                chat_id=self.free_channel,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
        except Exception as e:
            logger.error(f"SL campaign failed: {e}")

    # ==================== CAMPAIGN: SCHEDULED CONTENT ====================

    async def run_daily_campaigns(self):
        """Run all scheduled marketing campaigns for the day"""
        logger.info("🤖 Running daily marketing campaigns...")

        campaigns = [
            ('morning_outlook', self._morning_campaign),
            ('midday_engagement', self._midday_campaign),
            ('evening_recap', self._evening_campaign),
        ]

        for name, method in campaigns:
            try:
                await method()
            except Exception as e:
                logger.error(f"Daily campaign [{name}] failed: {e}")

    async def _morning_campaign(self):
        """Morning outlook + landing page push"""
        text = (
            "🌅 <b>Good Morning Traders</b>\n\n"
            "Markets are scanning for high-probability setups...\n\n"
            "📊 Today's focus:\n"
            "• London-NY overlap (13:00-16:00 UTC)\n"
            "• Volume profile discount entries\n"
            "• Liquidity sweep setups\n\n"
            "💎 VIP gets signals instantly + full plans\n"
            "🔓 Free channel gets teasers (10 min delay)\n\n"
            f"🔗 <a href='{self.landing_url}'>Learn More</a>\n"
            "📩 @CryptoPulseVIPAccessBot"
        )
        await self._broadcast(text, 'morning_outlook')

    async def _midday_campaign(self):
        """Midday engagement + VIP promo"""
        if self.community_engagement:
            try:
                await self.community_engagement.post_engagement('fomo_triggers')
            except Exception as e:
                logger.error(f"Midday engagement failed: {e}")

    async def _evening_campaign(self):
        """Evening recap + landing page push"""
        text = (
            "🌙 <b>Market Wrap</b>\n\n"
            "Another day of quality analysis delivered.\n\n"
            "✅ Free channel got market context\n"
            "✅ VIP members got full trade plans\n\n"
            "🎯 Tomorrow: Same institutional-grade analysis.\n"
            "Same strict criteria. Same risk management.\n\n"
            f"🔗 <a href='{self.landing_url}'>See Our Methodology</a>\n"
            "📩 @CryptoPulseVIPAccessBot"
        )
        await self._broadcast(text, 'evening_recap')

    # ==================== CAMPAIGN: SOCIAL PROOF ====================

    async def run_social_proof_campaign(self, stats: dict):
        """Post performance stats as social proof to all channels"""
        if stats.get('total', 0) == 0:
            return

        win_rate = stats.get('win_rate', 0)
        total_pnl = stats.get('total_pnl', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)

        emoji = "🔥" if win_rate >= 60 else "📈" if win_rate >= 50 else "📊"

        text = (
            f"📊 <b>PERFORMANCE UPDATE</b>\n\n"
            f"{emoji} Win Rate: <b>{win_rate:.0f}%</b>\n"
            f"🏆 Winners: {wins} | 🛑 Losses: {losses}\n"
            f"💰 Total P&L: <b>{total_pnl:+.1f}%</b>\n\n"
            f"Every signal: 85%+ confidence + strict risk management.\n"
            f"That's why professionals use systems, not guesswork.\n\n"
            f"� <a href='{self.landing_url}'>Join VIP</a> for full signals with entry, SL & 3 TPs\n"
        )
        
        # Add referral CTA if configured
        custom_url = getattr(settings, 'AFFILIATE_CUSTOM_URL', None)
        if custom_url:
            text += f"🔷 <a href='{custom_url}'>Trade on MEXC</a> — low fees, deep liquidity\n"
        
        text += f"📩 @CryptoPulseVIPAccessBot"

        await self._broadcast(text, 'social_proof')

    # ==================== CAMPAIGN: LANDING PAGE PUSH ====================

    async def landing_page_push(self):
        """Direct campaign to drive traffic to landing page"""
        templates = [
            (
                "🚀 <b>Ready to Trade Like the Pros?</b>\n\n"
                "We don't use RSI. We don't use MACD.\n"
                "We use what institutions actually use:\n"
                "• Volume Profile\n"
                "• Liquidity Analysis\n"
                "• Market Structure\n"
                "• Multi-Timeframe Alignment\n\n"
                f"🔗 <a href='{self.landing_url}'>See How It Works</a>"
            ),
            (
                "💎 <b>Why Traders Choose CryptoPulse</b>\n\n"
                "✅ 1-3 quality signals/day (not spam)\n"
                "✅ 85%+ confidence threshold\n"
                "✅ Entry, SL, 3 TPs on every signal\n"
                "✅ Live TP/SL alerts\n"
                "✅ Weekly performance reports\n\n"
                f"🔗 <a href='{self.landing_url}'>Join VIP</a>"
            ),
            (
                "🎯 <b>Tired of Generic Indicators?</b>\n\n"
                "RSI oversold? MACD cross? EMA bounce?\n"
                "Retail tools = retail results.\n\n"
                "We read the market like professionals do.\n"
                "Volume. Structure. Liquidity.\n\n"
                f"🔗 <a href='{self.landing_url}'>Learn Our Method</a>"
            ),
        ]

        text = random.choice(templates)
        await self._broadcast(text, 'landing_push')

    # ==================== UTILITIES ====================

    async def _broadcast(self, text: str, campaign_type: str):
        """Send text to all available channels"""
        # Telegram free channel
        if self.channel_publisher and self.free_channel:
            try:
                await self.channel_publisher.bot.send_message(
                    chat_id=self.free_channel,
                    text=text,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                logger.info(f"📢 Telegram broadcast [{campaign_type}]")
            except Exception as e:
                logger.error(f"Telegram broadcast failed: {e}")

        # Discord
        if self.discord and self.discord.enabled:
            try:
                title = campaign_type.replace('_', ' ').title()
                await self.discord.post_marketing(title=title, message=text.replace('<b>', '**').replace('</b>', '**'))
                logger.info(f"📢 Discord broadcast [{campaign_type}]")
            except Exception as e:
                logger.error(f"Discord broadcast failed: {e}")

        # Twitter (shortened)
        if self.social_media and self.social_media.twitter_enabled:
            try:
                short_text = text.split('\n')[0][:200] + f"\n\n{self.landing_url}"
                self.social_media.twitter_client.create_tweet(text=short_text)
                logger.info(f"📢 Twitter broadcast [{campaign_type}]")
            except Exception as e:
                logger.warning(f"Twitter broadcast failed: {e}")

        self._track_campaign(campaign_type)

    def _tradingview_link(self, symbol: str, timeframe: str = '15m') -> str:
        """Generate TradingView chart link"""
        base, quote = symbol.split('/')
        tv_symbol = f"BINANCE:{base}{quote}"
        interval_map = {'15m': '15', '1h': '60', '4h': '240', '1d': 'D'}
        interval = interval_map.get(timeframe, '15')
        return f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"

    def _track_campaign(self, campaign_type: str):
        self.campaigns_sent += 1
        self.last_campaigns[campaign_type] = datetime.utcnow()

    def get_stats(self) -> Dict:
        return {
            'campaigns_sent': self.campaigns_sent,
            'last_campaigns': {k: v.isoformat() for k, v in self.last_campaigns.items()}
        }

    def _load_templates(self):
        """Load any custom templates from file if exists"""
        pass  # Templates are inline for now
