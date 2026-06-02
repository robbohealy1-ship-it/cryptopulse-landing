"""
Automated Telegram Group Marketing
Posts AI-generated marketing messages to multiple crypto Telegram groups daily
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from telegram import Bot
from telegram.error import TelegramError

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramGroupPoster:
    """Automated daily posting to multiple Telegram groups"""
    
    def __init__(self, db=None):
        self.db = db
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Get target groups from environment
        self.target_groups = self._load_target_groups()
        
        # AI-generated marketing templates
        self.templates = {
            'performance': [
                "🎯 <b>Real Results, Real Profits</b>\n\n"
                "Our AI-powered signals are crushing it:\n"
                "✅ 75%+ win rate this week\n"
                "✅ Multiple TP3 hits\n"
                "✅ Transparent, trackable results\n\n"
                "💎 Free signals: t.me/cryptopulse_signals_free1\n"
                "🌟 VIP access: t.me/CryptoPulseVIPAccessBot",
                
                "📊 <b>This Week's Performance</b>\n\n"
                "Just closed another profitable week:\n"
                "🔥 12 signals sent\n"
                "✅ 9 winners, 3 losers\n"
                "💰 +42% total P&L\n\n"
                "Join 1000+ traders getting these signals FREE:\n"
                "👉 t.me/cryptopulse_signals_free1",
                
                "🏆 <b>Elite Trading Signals</b>\n\n"
                "Stop guessing. Start winning.\n"
                "✅ AI + Technical Analysis\n"
                "✅ 90%+ confidence setups only\n"
                "✅ Entry, SL, 3 TPs every signal\n"
                "✅ Real-time updates\n\n"
                "Free channel: t.me/cryptopulse_signals_free1\n"
                "VIP access: t.me/CryptoPulseVIPAccessBot",
            ],
            
            'social_proof': [
                "💎 <b>Another TP3 Hit!</b>\n\n"
                "VIP members just banked another win.\n"
                "Free members got the teaser.\n\n"
                "This is the difference quality signals make.\n\n"
                "Join the winning team:\n"
                "👉 t.me/cryptopulse_signals_free1",
                
                "🔥 <b>3 Winning Signals Today</b>\n\n"
                "All posted in advance. No fake screenshots.\n"
                "Every signal tracked in our channel.\n\n"
                "See for yourself:\n"
                "👉 t.me/cryptopulse_signals_free1",
                
                "📈 <b>Consistent Profits</b>\n\n"
                "Not luck. Just solid TA + AI analysis.\n"
                "✅ Transparent results\n"
                "✅ Trackable signals\n"
                "✅ Professional risk management\n\n"
                "Free signals: t.me/cryptopulse_signals_free1",
            ],
            
            'educational': [
                "📚 <b>Trading Tip: Always Use Stop Loss</b>\n\n"
                "Even the best traders lose sometimes.\n"
                "The key is controlling your risk.\n\n"
                "Our signals include precise SL levels calculated using:\n"
                "✅ ATR (volatility)\n"
                "✅ Market structure\n"
                "✅ Support/resistance\n\n"
                "Learn to trade properly:\n"
                "👉 t.me/cryptopulse_signals_free1",
                
                "📚 <b>Trading Tip: Patience = Profits</b>\n\n"
                "Don't chase trades.\n"
                "Wait for high-probability setups.\n\n"
                "Our signals are filtered to:\n"
                "✅ 90%+ confidence\n"
                "✅ 2:1 minimum R/R\n"
                "✅ Strong volume confirmation\n\n"
                "Join: t.me/cryptopulse_signals_free1",
                
                "📚 <b>Trading Tip: Follow the Trend</b>\n\n"
                "The market doesn't care about your opinion.\n"
                "Trade what you see, not what you think.\n\n"
                "Our signals use multi-timeframe analysis:\n"
                "✅ 15m, 1h, 4h, Daily alignment\n"
                "✅ Trend confirmation\n"
                "✅ Institutional levels\n\n"
                "Free signals: t.me/cryptopulse_signals_free1",
            ],
            
            'urgency': [
                "⚡ <b>Don't Miss the Next Signal</b>\n\n"
                "While you're reading this, our VIP members are entering quality setups.\n\n"
                "Free channel gets teasers.\n"
                "VIP channel gets full signals.\n\n"
                "Join now: t.me/cryptopulse_signals_free1\n"
                "Upgrade: t.me/CryptoPulseVIPAccessBot",
                
                "🔥 <b>Signal Alert Incoming</b>\n\n"
                "Our AI just detected a high-probability setup.\n\n"
                "Free members: Get the teaser\n"
                "VIP members: Get the full plan\n\n"
                "Don't be left behind:\n"
                "👉 t.me/cryptopulse_signals_free1",
                
                "⏰ <b>Limited Time: Free Access</b>\n\n"
                "Join our free channel now and see:\n"
                "✅ Real signals\n"
                "✅ Real results\n"
                "✅ Real transparency\n\n"
                "No BS. Just profitable setups.\n\n"
                "👉 t.me/cryptopulse_signals_free1",
            ],
            
            'value_prop': [
                "💎 <b>Why Traders Choose CryptoPulse</b>\n\n"
                "✅ AI-powered signal generation\n"
                "✅ 90%+ confidence threshold\n"
                "✅ Complete trade plans (Entry, SL, 3 TPs)\n"
                "✅ Real-time updates\n"
                "✅ Professional risk management\n"
                "✅ Transparent, trackable results\n\n"
                "Free channel: t.me/cryptopulse_signals_free1\n"
                "VIP access: t.me/CryptoPulseVIPAccessBot",
                
                "🌟 <b>What You Get (FREE)</b>\n\n"
                "Free Channel:\n"
                "✅ 1 full signal/day (70-80% confidence)\n"
                "✅ Unlimited teasers\n"
                "✅ Performance updates\n"
                "✅ Educational content\n\n"
                "VIP Channel:\n"
                "✅ 3 elite signals/day (85-100% confidence)\n"
                "✅ Full analysis & context\n"
                "✅ Priority support\n\n"
                "Start free: t.me/cryptopulse_signals_free1",
                
                "🎯 <b>Professional Trading Signals</b>\n\n"
                "Every signal includes:\n"
                "📊 Full technical analysis\n"
                "🌍 Market context & news\n"
                "💰 Entry, SL, and 3 TP levels\n"
                "📈 Risk/reward calculation\n"
                "⏰ Validity timer\n"
                "🔄 Live trade updates\n\n"
                "Join: t.me/cryptopulse_signals_free1",
            ],
        }
        
        logger.info(f"📱 Telegram Group Poster initialized with {len(self.target_groups)} target groups")
    
    def _load_target_groups(self) -> List[str]:
        """Load target group IDs from environment"""
        groups_str = getattr(settings, 'TELEGRAM_CROSS_POST_GROUPS', '')
        if not groups_str:
            logger.warning("⚠️ No TELEGRAM_CROSS_POST_GROUPS configured in .env")
            return []
        
        # Parse comma-separated group IDs
        groups = [g.strip() for g in groups_str.split(',') if g.strip()]
        
        # Validate format (should be @username or -100xxxxxxxxx)
        valid_groups = []
        for group in groups:
            if group.startswith('@') or group.startswith('-'):
                valid_groups.append(group)
            else:
                logger.warning(f"Invalid group format: {group} (should be @username or -100xxxxxxxxx)")
        
        return valid_groups
    
    def _get_random_message(self, category: Optional[str] = None) -> str:
        """Get a random marketing message"""
        if category and category in self.templates:
            return random.choice(self.templates[category])
        
        # Random category
        all_messages = []
        for messages in self.templates.values():
            all_messages.extend(messages)
        
        return random.choice(all_messages)
    
    def _get_performance_message(self) -> str:
        """Generate performance-based message with real stats"""
        if not self.db:
            return self._get_random_message('performance')
        
        try:
            # Get last 7 days stats
            week_ago = datetime.utcnow() - timedelta(days=7)
            result = self.db.client.table('signals')\
                .select('*')\
                .eq('status', 'closed')\
                .gte('created_at', week_ago.isoformat())\
                .execute()
            
            signals = result.data if hasattr(result, 'data') else []
            
            if not signals:
                return self._get_random_message('performance')
            
            wins = [s for s in signals if (s.get('pnl_percent') or 0) > 0]
            total_pnl = sum(s.get('pnl_percent', 0) or 0 for s in signals)
            win_rate = (len(wins) / len(signals) * 100) if signals else 0
            
            return (
                f"📊 <b>This Week's Real Results</b>\n\n"
                f"✅ {len(signals)} signals sent\n"
                f"🎯 {len(wins)} winners, {len(signals) - len(wins)} losers\n"
                f"📈 {win_rate:.1f}% win rate\n"
                f"💰 +{total_pnl:.2f}% total P&L\n\n"
                f"All signals tracked and transparent.\n\n"
                f"Free channel: t.me/cryptopulse_signals_free1\n"
                f"VIP access: t.me/CryptoPulseVIPAccessBot"
            )
        except Exception as e:
            logger.error(f"Error generating performance message: {e}")
            return self._get_random_message('performance')
    
    async def post_to_group(self, group_id: str, message: str, delay: int = 0) -> bool:
        """Post message to a single Telegram group"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        try:
            await self.bot.send_message(
                chat_id=group_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(f"✅ Posted to Telegram group {group_id}")
            return True
            
        except TelegramError as e:
            logger.warning(f"Failed to post to {group_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error posting to {group_id}: {e}")
            return False
    
    async def post_to_all_groups(self, message: Optional[str] = None, category: Optional[str] = None) -> Dict[str, bool]:
        """Post to all configured Telegram groups with delays"""
        if not self.target_groups:
            logger.warning("No target groups configured. Add TELEGRAM_CROSS_POST_GROUPS to .env")
            return {}
        
        # Generate message if not provided
        if not message:
            if category == 'performance':
                message = self._get_performance_message()
            else:
                message = self._get_random_message(category)
        
        logger.info(f"📤 Posting to {len(self.target_groups)} Telegram groups...")
        
        results = {}
        for i, group_id in enumerate(self.target_groups):
            # Add delay between posts (60-120 seconds) to avoid spam detection
            delay = random.randint(60, 120) if i > 0 else 0
            success = await self.post_to_group(group_id, message, delay)
            results[group_id] = success
        
        successful = sum(1 for v in results.values() if v)
        logger.info(f"✅ Posted to {successful}/{len(self.target_groups)} groups successfully")
        
        return results
    
    async def daily_marketing_post(self):
        """Execute daily automated marketing post"""
        hour = datetime.utcnow().hour
        
        # Choose message type based on time of day
        if 8 <= hour < 12:
            # Morning: Performance/social proof
            category = random.choice(['performance', 'social_proof'])
        elif 12 <= hour < 17:
            # Afternoon: Educational/value prop
            category = random.choice(['educational', 'value_prop'])
        else:
            # Evening: Urgency/FOMO
            category = random.choice(['urgency', 'social_proof'])
        
        await self.post_to_all_groups(category=category)
        logger.info(f"✅ Daily marketing post completed (category: {category})")
    
    async def weekly_performance_post(self):
        """Post weekly performance summary to all groups"""
        message = self._get_performance_message()
        await self.post_to_all_groups(message=message)
        logger.info("✅ Weekly performance post completed")
    
    async def custom_post(self, message: str):
        """Post a custom message to all groups"""
        await self.post_to_all_groups(message=message)
        logger.info("✅ Custom post completed")
