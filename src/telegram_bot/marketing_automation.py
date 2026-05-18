"""
CRYPTO PULSE SIGNALS - Marketing Automation
Automated posts for free channel to drive VIP conversions
"""

import random
from datetime import datetime, timedelta
from typing import List
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MarketingAutomation:
    """Generates marketing content for free Telegram channel"""
    
    def __init__(self, db=None):
        self.db = db
        
        self.templates = {
            'recent_win': [
                "🎉 <b>Recent VIP Win!</b>\n\nOur VIP members just banked profits on {symbol}!\n\n💎 While free members got the teaser, VIPs got:\n✅ Full entry details\n✅ 3 profit targets\n✅ Real-time updates\n✅ Risk management guidance\n\n👉 Don't miss the next one. DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP access!",
                "🏆 <b>VIP Trade Success!</b>\n\n{VipSymbol} delivered for our premium members!\n\n📊 This is the quality of signals you get with VIP:\n✅ 90%+ confidence setups\n✅ Complete trade plans\n✅ Live management updates\n✅ Professional risk guidance\n\n🔥 Ready to upgrade?\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} now!",
            ],
            'weekly_stats': [
                "📊 <b>Weekly Performance Update</b>\n\nOur VIP members enjoyed:\n🎯 {signals} premium signals\n✅ {wins} winners\n📈 {win_rate}% win rate\n💰 Total P&L: {pnl}%\n\n💎 Want these results?\nJoin VIP for elite signals!\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for access",
                "🏆 <b>This Week's VIP Results</b>\n\n✅ Signals: {signals}\n✅ Wins: {wins}\n✅ Win Rate: {win_rate}%\n💰 P&L: {pnl}%\n\nThis is what professional trading signals look like.\n\n👉 Upgrade to VIP - DM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
            ],
            'educational': [
                "📚 <b>Crypto Trading Tip #1</b>\n\n<b>Always use a stop loss!</b>\n\nEven the best traders lose sometimes. The key is controlling your risk so one bad trade doesn't wipe you out.\n\n💎 VIP members get precise SL levels calculated using ATR and market structure.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} to learn more",
                "📚 <b>Crypto Trading Tip #2</b>\n\n<b>Patience = Profits</b>\n\nDon't chase trades. Wait for high-probability setups with proper risk/reward.\n\n💎 VIP signals are filtered to 90%+ confidence with 2:1 minimum R/R.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for access",
                "📚 <b>Crypto Trading Tip #3</b>\n\n<b>Risk only 1-2% per trade</b>\n\nProfessional traders survive bad streaks by sizing positions correctly.\n\n💎 VIP signals include position sizing guidance based on your account.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} to join",
                "📚 <b>Crypto Trading Tip #4</b>\n\n<b>Follow the trend, not your feelings</b>\n\nThe market doesn't care about your opinion. Trade what you see, not what you think.\n\n💎 VIP signals use multi-timeframe trend analysis for directional bias.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
                "📚 <b>Crypto Trading Tip #5</b>\n\n<b>Move SL to breakeven after TP1</b>\n\nThis is how pros trade - lock in risk-free profits and let winners run.\n\n💎 VIP members get live SL adjustment alerts.\n\n👉 Upgrade to VIP - DM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
                "📚 <b>Crypto Trading Tip #6</b>\n\n<b>Volume confirms everything</b>\n\nA breakout without volume is a fakeout. Always check volume before entering.\n\n💎 VIP signals require strong volume confirmation (60+ score).\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP access",
                "📚 <b>Crypto Trading Tip #7</b>\n\n<b>Don't trade during major news</b>\n\nFOMC, CPI, and other high-impact events create volatility that stops you out.\n\n💎 VIP signals check macro conditions before every trade.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
                "📚 <b>Crypto Trading Tip #8</b>\n\n<b>Keep a trading journal</b>\n\nTrack every trade, review weekly, and improve systematically.\n\n💎 VIP members get automated trade tracking and performance reports.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} to join",
            ],
            'vip_promotion': [
                "💎 <b>Why Traders Choose VIP</b>\n\n✅ 90%+ confidence signals only\n✅ 3 profit targets per trade\n✅ Full market analysis included\n✅ Real-time trade updates\n✅ Risk management guidance\n✅ Weekly performance reports\n✅ Pre-market outlook\n\n🚀 Stop missing elite setups!\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for instant VIP access\n💰 Crypto payments accepted",
                "🔥 <b>Limited VIP Spots Available</b>\n\nOur signal quality speaks for itself:\n✅ Only 1-3 elite signals per day\n✅ 90%+ confidence threshold\n✅ Complete trade management\n✅ Professional risk guidance\n\n💎 Join the elite traders who follow our signals.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} now!",
                "🌟 <b>What You Get With VIP</b>\n\nEvery signal includes:\n📊 Full technical analysis\n🌍 Market context & news\n💰 Entry, SL, and 3 TP levels\n📈 Risk/reward calculation\n⏰ Validity timer\n🔄 Live trade updates\n\nFree channel = teaser only\nVIP channel = complete setup\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} to upgrade!",
            ],
            'performance': [
                "🏆 <b>Performance Highlight</b>\n\nOur signal system delivers:\n✅ Quality over quantity\n✅ 90%+ confidence threshold\n✅ Professional risk management\n✅ Real-time trade updates\n\n💎 See the difference with VIP signals.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for access",
                "📈 <b>Track Record Matters</b>\n\nEvery signal is:\n✅ Screened for 90%+ confidence\n✅ Validated with technical analysis\n✅ Confirmed with market context\n✅ Monitored until close\n\n💎 Professional signals for serious traders.\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
            ],
            'trade_recap': [
                "📊 <b>Trade Recap</b>\n\nRecent signal on {symbol}:\n📈 Direction: {direction}\n💰 Result: {result}\n\nThis is the quality and transparency VIP members enjoy.\n\n👉 Want detailed trade breakdowns?\nDM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP!",
                "🎯 <b>Signal Breakdown</b>\n\nSymbol: {symbol}\nSetup: {setup_type}\nConfidence: {confidence}%\n\nFree members saw the teaser.\nVIP members got the full plan.\n\n👉 Don't miss the next one!\nDM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
            ],
            'fomo': [
                "⚡ <b>Missed Another Signal?</b>\n\nWhile you were watching, VIP members entered another quality setup.\n\n💎 Join VIP and never miss:\n✅ 90%+ confidence signals\n✅ Complete trade plans\n✅ Live updates\n\n👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for instant access!",
                "🔥 <b>Another VIP Signal Fired!</b>\n\nFree channel got the teaser.\nVIP channel got the full setup.\n\nThe difference is clear.\n\n👉 Upgrade now - DM @{settings.TELEGRAM_VIP_BOT_USERNAME}",
            ],
        }
    
    def get_random_template(self, category: str) -> str:
        """Get a random template from a category"""
        if category not in self.templates:
            category = 'vip_promotion'
        return random.choice(self.templates[category])
    
    def get_marketing_post(self) -> str:
        """Generate a random marketing post for free channel"""
        category = random.choice(list(self.templates.keys()))
        template = self.get_random_template(category)
        return template
    
    def get_stats_post(self, stats: dict) -> str:
        """Generate a stats-based marketing post"""
        template = random.choice(self.templates['weekly_stats'])
        return template.format(
            signals=stats.get('total_signals', 0),
            wins=stats.get('wins', 0),
            win_rate=f"{stats.get('win_rate', 0):.1f}",
            pnl=f"{stats.get('total_pnl', 0):.2f}"
        )
    
    def get_educational_post(self) -> str:
        """Get an educational tip post"""
        return random.choice(self.templates['educational'])
    
    def should_post_now(self) -> bool:
        """Check if it's time to post marketing content"""
        now = datetime.utcnow()
        hour = now.hour
        
        # Only post during active hours
        start = settings.MARKETING_POST_HOUR_START
        end = settings.MARKETING_POST_HOUR_END
        
        return start <= hour <= end
    
    def get_post_times(self) -> List[datetime]:
        """Generate randomized post times for today"""
        now = datetime.utcnow()
        posts_per_day = settings.MARKETING_POSTS_PER_DAY
        start_hour = settings.MARKETING_POST_HOUR_START
        end_hour = settings.MARKETING_POST_HOUR_END
        
        times = []
        for _ in range(posts_per_day):
            hour = random.randint(start_hour, end_hour - 1)
            minute = random.randint(0, 59)
            post_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if post_time < now:
                post_time += timedelta(days=1)
            times.append(post_time)
        
        return sorted(times)
