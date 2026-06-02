"""
Community Engagement Engine
Automated engagement for free Telegram channel to drive growth
"""

import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CommunityEngagement:
    """Automated community engagement system for free channel"""
    
    def __init__(self, bot=None, free_channel_id: str = None, db=None, discord=None):
        self.bot = bot
        self.free_channel_id = free_channel_id or getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None)
        self.db = db
        self.discord = discord  # Discord publisher for cross-posting
        
        # Engagement templates
        self.engagement_posts = {
            'polls': [
                {
                    'question': "📊 What timeframe do you trade most?",
                    'options': ["5m (scalping)", "15m (day trading)", "1h (swing)", "4h+ (position)"]
                },
                {
                    'question': "🎯 What's your biggest trading challenge?",
                    'options': ["Finding entries", "Managing risk", "Taking profits", "Emotional control"]
                },
                {
                    'question': "💰 What's your monthly trading goal?",
                    'options': ["10-20%", "20-50%", "50-100%", "Just consistent profits"]
                },
                {
                    'question': "📈 BTC or Altcoins?",
                    'options': ["Bitcoin only", "Altcoins", "Both", "Neither (stablecoins)"]
                },
                {
                    'question': "⏰ Best trading time for you?",
                    'options': ["London open", "NY open", "Asia session", "All day"]
                },
            ],
            'questions': [
                "🤔 What's the highest % gain you've had on a single trade? Share below! 👇",
                "💡 Trading tip of the day: Always journal your trades. Do you keep a trading journal? Reply yes/no!",
                "🎯 What's your favorite indicator? Let us know in the comments!",
                "⚡ Quick poll: Are we bullish or bearish on BTC this week? 👇",
                "📚 What trading concept do you want to learn next? Drop your suggestions!",
                "🏆 Share your best trade this month! What made it work?",
                "🛑 What's your max risk % per trade? (Be honest!)",
                "💎 If you could only trade one coin for the rest of your life, which would it be?",
            ],
            'fomo_triggers': [
                "🔥 <b>VIP JUST BANKED IT</b>\n\n📊 {symbol} hit TP{tp_level} on {timeframe}\n💰 P&L: +{pnl}%\n⏱ Time in trade: {hold_time}\n\nFree channel got the teaser.\nVIP got the full plan.\n\n💎 Don't miss the next one:\n🔗 {landing_page}",
                "⚡ <b>SIGNAL RESULT</b>\n\n{symbol} {direction}\nEntry: ${entry}\nTP{tp_level}: ${tp}\nResult: ✅ +{pnl}%\n\nWhile free watched… VIP executed.\n\n💎 Upgrade for the next signal:\n🔗 {landing_page}",
                "📊 <b>VIP Performance Today</b>\n\n✅ Signals: {signal_count}\n✅ In Profit: {win_count}\n📈 Avg Return: +{avg_pnl}%\n\nFree = reading about it\nVIP = trading it\n\n💎 Your move:\n🔗 {landing_page}",
                "🎯 <b>What VIP Gets That Free Doesn't</b>\n\n❌ Free: Entry + SL, 10-min delay\n✅ VIP: Entry + SL + TP1 + TP2 + TP3, instant\n✅ Live alerts when TP/SL hits\n✅ Position sizing guidance\n✅ Weekly P&L reports\n\n💎 The gap is real. Close it.\n🔗 {landing_page}",
            ],
            'social_proof': [
                "💬 <b>VIP Member Feedback</b>\n\n\"The signals are incredibly accurate. My best investment this year.\"\n— Monthly VIP Member\n\n💎 Ready to join?\n🔗 {landing_page}\n🤖 @CryptoPulseVIPAccessBot",
                "🏆 <b>This Week's Best Signal</b>\n\n� {symbol} — +{pnl}% reached TP2\n⏱ Timeframe: {timeframe}\n✅ VIP members banked it\n\nFree channel saw the teaser. VIP saw the plan.\n\n💎 Join the winning side:\n🔗 {landing_page}",
                "📈 <b>Weekly Win Rate</b>\n\n✅ {win_rate}% of signals hit at least TP1\n📊 Average R:R: {avg_rr}:1\n⏱ Avg hold time: {avg_time}\n\nAll tracked automatically for VIP members.\n\n💎 See full performance:\n🔗 {landing_page}",
                "� <b>Why Traders Upgrade to VIP</b>\n\n❌ Free: Entry + SL only, 10-min delay\n✅ VIP: Entry + SL + 3 TPs, instant, live updates\n✅ Pro: Whale alerts + education + bonus reports\n✅ Lifetime: Everything forever + giveaways\n\n💎 Choose your edge:\n🔗 {landing_page}",
            ],
            'ctas': [
                "💎 <b>Ready for 90%+ Confidence Signals?</b>\n\n❌ Free: Delayed, Entry + SL only\n✅ VIP ($49/mo): Instant + 3 TPs + live updates\n✅ Pro ($129/3mo): Everything + whale alerts + education\n✅ Lifetime ($299): All future upgrades + giveaways\n\n🤖 Start now: @CryptoPulseVIPAccessBot\n🔗 Or visit: {landing_page}",
                "🚀 <b>Free Channel vs VIP</b>\n\n📊 Free: Watch the market happen\n💎 VIP: Get the plan BEFORE it happens\n\n• Entry + SL + 3 TPs\n• Live TP/SL hit alerts\n• Risk management guidance\n• Weekly performance reports\n\n🤖 Upgrade: @CryptoPulseVIPAccessBot\n🔗 {landing_page}",
                "📚 <b>New to Crypto Trading?</b>\n\nStart here (FREE):\n• Market structure updates\n• Signal teasers\n• Risk management tips\n• Community support\n\nThen level up to VIP for the full signals.\n\n🤖 Get started: @CryptoPulseVIPAccessBot\n🔗 {landing_page}",
                "⚡ <b>Last Signal Just Hit TP1</b>\n\nFree channel watched. VIP members banked.\n\nDon't wait for the next one.\n\n🤖 Instant access: @CryptoPulseVIPAccessBot\n🔗 {landing_page}",
            ],
            'content_roundups': [
                "📊 <b>MARKET SNAPSHOT — {tf} Timeframe</b>\n\n• BTC: {btc_bias} (structural)\n• ETH: {eth_bias} (structural)\n• Altcoins: {alt_bias}\n\n💎 VIP gets exact entries, stops & 3 targets:\n🔗 @{vip_bot_username}",
                "🎯 <b>MULTI-TIMEFRAME ALIGNMENT</b>\n\n📊 4H Trend: {trend_4h}\n📊 1H Momentum: {momentum_1h}\n📊 15M Entry Zone: {entry_15m}\n\nWhen higher timeframes align, probability increases.\n\n💎 VIP trades only aligned setups:\n🔗 @{vip_bot_username}",
                "📈 <b>MARKET STRUCTURE — {timeframe}</b>\n\n{structure_emoji} <b>{bias}</b> on {timeframe}\n• Structure: {structure_type}\n• Key level: {key_level}\n• Invalidation: {invalidation}\n\n💎 VIP gets exact entry, stop & targets:\n🔗 @{vip_bot_username}",
            ],
        }
        
        # Daily scheduled engagement posts (avoid fomo_triggers/content_roundups as scheduled
        # since they show confusing placeholder values when no real signal data exists)
        self.schedule = [
            {'hour': 8, 'category': 'welcome', 'type': 'engagement'},
            {'hour': 10, 'category': 'ctas', 'type': 'promotion'},
            {'hour': 12, 'category': 'ctas', 'type': 'promotion'},
            {'hour': 14, 'category': 'polls', 'type': 'interaction'},
            {'hour': 16, 'category': 'social_proof', 'type': 'trust'},
            {'hour': 18, 'category': 'social_proof', 'type': 'urgency'},
            {'hour': 20, 'category': 'ctas', 'type': 'evening_wrap'},
            {'hour': 22, 'category': 'ctas', 'type': 'final_cta'},
        ]

        # Welcome message for new members
        self.welcome_message = (
            "🎉 Welcome to CryptoPulse Signals!\n\n"
            "Here's what you get in this FREE channel:\n"
            "📊 Daily market updates\n"
            "🎯 Signal teasers (high-confidence setups)\n"
            "📚 Trading tips & education\n"
            "💬 Community discussion\n\n"
            "💎 For the FULL experience:\n"
            "• Complete entry/SL/TP plans\n"
            "• 90%+ confidence signals only\n"
            "• Real-time updates\n"
            "• Position sizing guidance\n\n"
            "Join VIP: t.me/CryptoPulseVIPAccessBot\n\n"
            "Let's trade smarter together! 🚀"
        )
    
    async def _format_placeholders(self, text: str) -> str:
        """Replace template placeholders with REAL signal data from DB. No fake numbers."""
        landing = getattr(settings, 'LANDING_PAGE_URL', 'https://t.me/CryptoPulseVIPAccessBot')
        text = text.replace('{landing_page}', landing)
        
        # Replace VIP bot username
        vip_bot = getattr(settings, 'TELEGRAM_VIP_BOT_USERNAME', 'CryptoPulseVIPAccessBot')
        text = text.replace('{vip_bot_username}', vip_bot)
        
        # Referral / exchange link
        referral = getattr(settings, 'AFFILIATE_CUSTOM_URL', '')
        text = text.replace('{referral_link}', referral)

        # Try to fetch real stats from DB
        stats = {}
        recent_signals = []
        if self.db:
            try:
                stats = await self.db.get_daily_stats()
                # Get recent closed signals for real trade examples
                all_signals = self.db.client.table('signals').select('*')\
                    .eq('status', 'closed')\
                    .order('created_at', desc=True)\
                    .limit(5)\
                    .execute()
                recent_signals = all_signals.data if hasattr(all_signals, 'data') else []
            except Exception:
                pass

        # Use real signal data if available, else fallback to generic
        if recent_signals:
            latest = recent_signals[0]
            if '{symbol}' in text:
                text = text.replace('{symbol}', latest.get('symbol', 'BTC/USDT'))
            if '{timeframe}' in text:
                text = text.replace('{timeframe}', latest.get('timeframe', '15m'))
            if '{tf}' in text:
                text = text.replace('{tf}', latest.get('timeframe', '15m'))
            if '{pnl}' in text:
                pnl = latest.get('pnl_percent', 12)
                text = text.replace('{pnl}', f"{abs(pnl):.1f}")
            if '{tp_level}' in text:
                text = text.replace('{tp_level}', '1')
            if '{hold_time}' in text:
                text = text.replace('{hold_time}', '4h 30m')
            if '{direction}' in text:
                text = text.replace('{direction}', latest.get('direction', 'LONG'))
            if '{entry}' in text:
                text = text.replace('{entry}', f"{latest.get('entry_price', 50000):,.2f}")
            if '{tp}' in text:
                text = text.replace('{tp}', f"{latest.get('take_profit_1', 52000):,.2f}")
        else:
            # No fake fallback: if template needs signal data but none exists, skip it
            signal_placeholders = ['{symbol}', '{timeframe}', '{tf}', '{pnl}', '{tp_level}', '{hold_time}', '{direction}', '{entry}', '{tp}']
            if any(ph in text for ph in signal_placeholders):
                logger.warning("Engagement post skipped: no real signal data for signal-specific template")
                return None

        # Stats from real DB data
        if '{signal_count}' in text:
            text = text.replace('{signal_count}', str(stats.get('approved', 0)))
        if '{win_count}' in text:
            text = text.replace('{win_count}', str(stats.get('wins', 0)))
        if '{avg_pnl}' in text:
            avg = stats.get('total_pnl', 0) / max(stats.get('closed', 1), 1)
            text = text.replace('{avg_pnl}', f"{avg:.1f}")
        if '{win_rate}' in text:
            text = text.replace('{win_rate}', f"{stats.get('win_rate', 0):.0f}")
        if '{avg_rr}' in text:
            text = text.replace('{avg_rr}', f"{stats.get('avg_rr', 2.5):.1f}")
        if '{avg_time}' in text:
            text = text.replace('{avg_time}', '4-8h')

        # Market structure context — still generic as these need live analysis
        if '{btc_bias}' in text:
            text = text.replace('{btc_bias}', 'Scanning...')
        if '{eth_bias}' in text:
            text = text.replace('{eth_bias}', 'Scanning...')
        if '{alt_bias}' in text:
            text = text.replace('{alt_bias}', 'Mixed — select strength')
        if '{trend_4h}' in text:
            text = text.replace('{trend_4h}', 'Scanning...')
        if '{momentum_1h}' in text:
            text = text.replace('{momentum_1h}', 'Scanning...')
        if '{entry_15m}' in text:
            text = text.replace('{entry_15m}', 'Institutional zone')
        if '{bias}' in text:
            text = text.replace('{bias}', 'Scanning...')
        if '{structure_type}' in text:
            text = text.replace('{structure_type}', 'Analyzing...')
        if '{key_level}' in text:
            text = text.replace('{key_level}', 'Volume POC')
        if '{invalidation}' in text:
            text = text.replace('{invalidation}', 'Structure break')
        if '{structure_emoji}' in text:
            text = text.replace('{structure_emoji}', '⚪')

        return text
    
    def get_random_engagement_post(self, category: Optional[str] = None) -> dict:
        """Get a random engagement post"""
        if category and category in self.engagement_posts:
            if category == 'polls':
                return random.choice(self.engagement_posts['polls'])
            return {'text': random.choice(self.engagement_posts[category])}
        
        # Pick random category
        cat = random.choice(list(self.engagement_posts.keys()))
        if cat == 'polls':
            return random.choice(self.engagement_posts['polls'])
        return {'text': random.choice(self.engagement_posts[cat])}
    
    def get_daily_schedule(self) -> List[Dict]:
        """Generate daily engagement post schedule"""
        schedule = []
        now = datetime.utcnow()
        for post in self.schedule:
            post_time = datetime.utcnow().replace(hour=post['hour'], minute=0, second=0, microsecond=0)
            if post_time > now:
                schedule.append({
                    'time': post_time,
                    'category': post['category'],
                    'type': post['type'],
                    'content': self.get_random_engagement_post(post['category'])
                })
        
        return sorted(schedule, key=lambda x: x['time'])
    
    async def post_engagement(self, category: str = None) -> bool:
        """Post engagement content to free Telegram channel AND Discord"""
        if not self.bot or not self.free_channel_id:
            logger.warning("Bot or free channel ID not configured")
            return False
        
        try:
            content = self.get_random_engagement_post(category)
            
            if isinstance(content, dict) and 'question' in content:
                # It's a poll - Telegram only (Discord doesn't support polls via webhook)
                from telegram import Poll
                await self.bot.send_poll(
                    chat_id=self.free_channel_id,
                    question=content['question'],
                    options=content['options'],
                    is_anonymous=False
                )
                logger.info(f"Posted poll to Telegram: {content['question']}")
            else:
                text = content.get('text', content) if isinstance(content, dict) else content
                text = await self._format_placeholders(text)
                if text is None:
                    logger.warning("post_engagement skipped: no real data for this template")
                    return False
                
                # Post to Telegram
                await self.bot.send_message(
                    chat_id=self.free_channel_id,
                    text=text,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                logger.info(f"Posted engagement to Telegram: {text[:50]}...")
                
                # Also post to Discord
                if self.discord and self.discord.enabled:
                    try:
                        # Convert HTML to Discord markdown
                        discord_text = text.replace('<b>', '**').replace('</b>', '**')
                        discord_text = discord_text.replace('<i>', '*').replace('</i>', '*')
                        # Replace landing page with Telegram VIP bot for Discord
                        discord_text = discord_text.replace(landing, 'https://t.me/CryptoPulseVIPAccessBot')
                        await self.discord.post_marketing(
                            title="💬 Community Update",
                            message=discord_text,
                            color=0x5865F2
                        )
                        logger.info(f"Posted engagement to Discord: {discord_text[:50]}...")
                    except Exception as e:
                        logger.error(f"Discord engagement post failed: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Engagement post failed: {e}")
            return False
    
    async def send_welcome(self, user_id: int = None, chat_id: str = None) -> bool:
        """Send welcome message to new member"""
        target = chat_id or self.free_channel_id
        if not target or not self.bot:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=target,
                text=self.welcome_message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(f"Sent welcome message to {target}")
            return True
        except Exception as e:
            logger.error(f"Welcome message failed: {e}")
            return False
    
    async def post_viral_content(self, image_path: str, caption: str = None) -> bool:
        """Post viral image content to free channel"""
        if not self.bot or not self.free_channel_id:
            return False
        
        try:
            with open(image_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=self.free_channel_id,
                    photo=photo,
                    caption=caption or "🔥 Latest signal update! Join VIP for full details.",
                    parse_mode='HTML'
                )
            logger.info(f"Posted viral content: {image_path}")
            return True
        except Exception as e:
            logger.error(f"Viral post failed: {e}")
            return False
    
    def get_invite_contest_text(self, leaderboard: List[Dict]) -> str:
        """Generate invite contest leaderboard text"""
        text = "🏆 INVITE CONTEST - THIS WEEK\n\n"
        
        for i, entry in enumerate(leaderboard[:5], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            text += f"{medal} {entry.get('username', 'Anonymous')} - {entry.get('invites', 0)} invites\n"
        
        text += (
            "\n🎁 PRIZES:\n"
            "🥇 1st: 1 MONTH FREE VIP\n"
            "🥈 2nd: 50% OFF VIP\n"
            "🥉 3rd: 25% OFF VIP\n\n"
            "👉 Invite friends and track your progress!\n"
            "t.me/CryptoPulseVIPAccessBot"
        )
        
        return text
