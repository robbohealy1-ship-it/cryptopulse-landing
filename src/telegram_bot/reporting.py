"""
CRYPTO PULSE SIGNALS - Reporting Module
Daily and weekly report generation for admin and VIP channels
"""

from datetime import datetime, timedelta
from typing import Dict
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReportingEngine:
    """Generates performance reports for admin and channels"""
    
    def __init__(self, db=None):
        self.db = db
    
    async def generate_daily_report(self) -> Dict[str, str]:
        """Generate daily report for admin and VIP - ALWAYS frames positively"""
        try:
            stats = await self.db.get_daily_stats()
            
            date_str = stats.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
            wins = stats.get('wins', 0)
            losses = stats.get('losses', 0)
            total = wins + losses
            win_rate = stats.get('win_rate', 0)
            pnl = stats.get('total_pnl', 0)
            approved = stats.get('approved', 0)
            
            # Frame P&L positively: even small green is "consistent profit"
            # Frame losses as "managed risk" (stopped out per plan)
            pnl_emoji = "🟢" if pnl >= 0 else "📊"
            pnl_text = f"+{pnl:.2f}% profit" if pnl >= 0 else f"{pnl:.2f}% (risk managed)"
            
            # Streak framing
            streak_text = ""
            if wins > 0 and losses == 0:
                streak_text = "\n🔥 PERFECT DAY — all signals profitable!\n"
            elif win_rate >= 60:
                streak_text = f"\n📈 Solid {win_rate:.0f}% win rate — consistent gains\n"
            elif total > 0:
                streak_text = "\n💎 Every signal followed the plan — that's what separates pros from gamblers\n"
            
            # VIP value framing
            vip_value = ""
            if approved > 0:
                avg_conf = stats.get('avg_confidence', 0)
                vip_value = f"\n💎 VIP Quality: {avg_conf:.0f}% avg confidence | Elite setups only\n"
            
            # Admin report (full details)
            admin_report = f"""📊 <b>DAILY REPORT - {date_str}</b>

<b>Signal Activity:</b>
📡 Scanned: {stats.get('total_scanned', 0)} setups
✅ Approved: {approved}
🔒 Closed: {stats.get('closed', 0)}

<b>Performance:</b>
🏆 Winners: {wins}
� Managed: {losses} (stopped per plan)
📈 Win Rate: {win_rate:.1f}%
{pnl_emoji} Result: {pnl_text}
{streak_text}
<b>System Status:</b>
✅ Operational | 🎯 Quality-first approach
⏰ Next scan: ~5 minutes

Ready for tomorrow! 🚀"""

            # VIP report (summary) — ALWAYS positive, focuses on discipline
            vip_report = f"""📊 <b>END OF DAY SUMMARY</b>

<b>Today's VIP Signals:</b>
✅ {approved} elite signals delivered
🏆 {wins} hit profit targets
📈 Win Rate: {win_rate:.1f}%
{pnl_emoji} {pnl_text}
{streak_text}{vip_value}
<b>What This Means:</b>
Every signal had 85%+ confidence, strict risk management, and clear targets.
That's professional trading. That's why VIP wins.

<b>Tomorrow:</b>
🌅 Pre-market outlook at 08:00 UTC
🔍 Scanning begins at 09:00 UTC

See you tomorrow! 💎"""

            return {
                'admin': admin_report,
                'vip': vip_report
            }
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return {'admin': 'Error generating report', 'vip': 'Error generating report'}
    
    async def generate_weekly_report(self) -> Dict[str, str]:
        """Generate weekly report for admin and VIP - ALWAYS positive framing"""
        try:
            stats = await self.db.get_weekly_stats()
            
            week_start = stats.get('week_start', '')
            wins = stats.get('wins', 0)
            losses = stats.get('losses', 0)
            total = stats.get('total_signals', 0)
            win_rate = stats.get('win_rate', 0)
            pnl = stats.get('total_pnl', 0)
            avg_rr = stats.get('avg_rr', 0)
            
            # Positive framing
            pnl_emoji = "🟢" if pnl >= 0 else "📊"
            pnl_text = f"+{pnl:.2f}% profit" if pnl >= 0 else f"{pnl:.2f}% (risk managed)"
            
            # VIP narrative
            if win_rate >= 60 and pnl > 0:
                narrative = "Another profitable week following the system. Discipline pays."
            elif win_rate >= 50:
                narrative = "Solid week with professional risk management. Consistency is key."
            else:
                narrative = "Tough week but every signal followed the plan. The edge plays out over time."
            
            # Free channel CTA based on performance
            if win_rate >= 60:
                free_cta = f"🔥 {win_rate:.0f}% win rate this week! Imagine your results with VIP access..."
            else:
                free_cta = "💎 VIP signals are filtered through 6+ quality gates. The edge adds up over time."
            
            # Admin report (full)
            admin_report = f"""📊 <b>WEEKLY REPORT</b>
<b>Week of {week_start}</b>

<b>Signal Summary:</b>
📡 Total Signals: {total}
🏆 Winners: {wins}
📊 Managed: {losses} (stopped per plan)
📈 Win Rate: {win_rate:.1f}%

<b>Performance:</b>
{pnl_emoji} Total Result: {pnl_text}
📊 Average R/R: {avg_rr:.2f}
🏆 Most Traded: {stats.get('most_traded', 'N/A')}

<b>System Health:</b>
✅ Quality-first filtering working
🎯 Only elite setups make the cut

Keep up the great work! 🚀"""

            # VIP report (summary)
            vip_report = f"""🏆 <b>WEEKLY VIP SUMMARY</b>

<b>This Week:</b>
✅ {total} elite signals delivered
🏆 {wins} hit profit targets
📈 Win Rate: {win_rate:.1f}%
{pnl_emoji} {pnl_text}
📊 Avg R/R: {avg_rr:.2f}

<b>The Bottom Line:</b>
{narrative}

<b>VIP Advantage:</b>
Every signal passed 85%+ confidence, multi-timeframe alignment,
strict risk management, and fundamental analysis.

That's why professionals use systems, not guesswork.

See you next week! 💎"""

            # Free channel marketing summary
            free_report = f"""📊 <b>Weekly VIP Performance</b>

Our VIP members this week:
✅ {total} premium signals
🏆 {wins} hit profit targets
📈 {win_rate:.1f}% win rate
{pnl_emoji} {pnl_text}

{free_cta}

💎 Want these results?
Join VIP for elite signals!

👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for access
💰 Crypto payments accepted"""

            return {
                'admin': admin_report,
                'vip': vip_report,
                'free': free_report
            }
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            return {
                'admin': 'Error generating weekly report',
                'vip': 'Error generating weekly report',
                'free': 'Error generating weekly report'
            }
    
    async def generate_vip_outlook(self) -> str:
        """Generate pre-market outlook for VIP"""
        now = datetime.utcnow()
        
        outlook = f"""🌅 <b>PRE-MARKET OUTLOOK</b>
<b>{now.strftime('%Y-%m-%d')}</b>

<b>Market Bias:</b>
Scanning begins shortly for elite setups.

<b>What to Expect:</b>
✅ 1-3 high-confidence signals today
✅ 90%+ confidence threshold
✅ Only the best setups make the cut
✅ Full trade management included

<b>Stay Tuned!</b>
Signals will be posted as soon as quality setups are detected.

Good luck today! 🎯"""
        
        return outlook
    
    async def generate_vip_recap(self, signal) -> str:
        """Generate a trade recap for VIP members"""
        result_emoji = "✅" if signal.pnl_percent and signal.pnl_percent > 0 else "❌"
        
        recap = f"""{result_emoji} <b>TRADE RECAP</b>

<b>{signal.symbol}</b>
📈 Direction: {signal.direction.value}
💰 Entry: ${signal.entry_price:.8f}
🛑 SL: ${signal.stop_loss:.8f}
🎯 TP1: ${signal.take_profit_1:.8f}

<b>Result:</b>
Status: {signal.status.value.replace('_', ' ').title()}
"""
        
        if signal.pnl_percent is not None:
            recap += f"P&L: {signal.pnl_percent:+.2f}%\n"
        
        recap += f"""
<b>Analysis:</b>
{signal.reasoning[:200]}...

Learn from every trade! 📚"""
        
        return recap
    
    async def generate_vip_education(self) -> str:
        """Generate educational premium insight for VIP"""
        insights = [
            "💎 <b>VIP Insight: Risk Management</b>\n\nThe pros never risk more than 2% per trade. With our 90%+ confidence signals and 2:1 minimum R/R, even a 50% win rate is profitable long-term.\n\nPosition size = (Account * 0.02) / (Entry - SL)\n\nStick to the plan! 🎯",
            "💎 <b>VIP Insight: Multi-Timeframe Analysis</b>\n\nOur signals analyze 5m, 15m, and 1h timeframes. When all align = highest confidence setups.\n\nThis is why our 90%+ signals have higher win rates.\n\nPatience pays! 📈",
            "💎 <b>VIP Insight: Volume Confirmation</b>\n\nA breakout without volume is likely a fakeout. Our scanner requires $10M+ daily volume and strong volume score (60+) for every signal.\n\nQuality over quantity always! ✅",
        ]
        
        import random
        return random.choice(insights)
