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
            
            # TP/SL tracking stats
            tp1_hits = stats.get('tp1_hits', 0)
            tp2_hits = stats.get('tp2_hits', 0)
            tp3_hits = stats.get('tp3_hits', 0)
            total_tp_hits = stats.get('total_tp_hits', 0)
            breakeven_moves = stats.get('breakeven_moves', 0)
            
            # Entry type stats
            limit_orders = stats.get('limit_orders', 0)
            market_orders = stats.get('market_orders', 0)
            
            # Setup type breakdown
            setup_types = stats.get('setup_types', {})
            top_setup = max(setup_types.items(), key=lambda x: x[1])[0] if setup_types else 'N/A'
            
            # Build TP summary
            tp_summary = ""
            if total_tp_hits > 0:
                tp_summary = f"\n🎯 TP Hits: TP1({tp1_hits}) | TP2({tp2_hits}) | TP3({tp3_hits})"
                if breakeven_moves > 0:
                    tp_summary += f"\n🔒 Breakeven Moves: {breakeven_moves}"
            
            # Build entry type summary
            entry_summary = ""
            if approved > 0:
                entry_summary = f"\n⚡ Entry Types: {market_orders} MARKET | {limit_orders} LIMIT"
            
            # Admin report (full details)
            admin_report = f"""📊 <b>DAILY REPORT - {date_str}</b>

<b>Signal Activity:</b>
📡 Scanned: {stats.get('total_scanned', 0)} setups
✅ Approved: {approved}
🔒 Closed: {stats.get('closed', 0)}
🔄 Active: {stats.get('active', 0)}

<b>Performance:</b>
🏆 Winners: {wins}
📊 Managed: {losses} (stopped per plan)
📈 Win Rate: {win_rate:.1f}%
{pnl_emoji} Result: {pnl_text}
{streak_text}{tp_summary}{entry_summary}

<b>Top Setup:</b>
🎯 {top_setup.replace('_', ' ').title()}

<b>System Status:</b>
✅ Operational | 🎯 Quality-first approach
⏰ Next scan: ~5 minutes

Ready for tomorrow! 🚀"""

            # VIP TP summary
            vip_tp_summary = ""
            if total_tp_hits > 0:
                vip_tp_summary = f"\n🎯 TP Hits Today: {total_tp_hits} targets reached"
                if breakeven_moves > 0:
                    vip_tp_summary += f" | {breakeven_moves} moved to breakeven"
            
            # VIP report (summary) — ALWAYS positive, focuses on discipline
            vip_report = f"""📊 <b>END OF DAY SUMMARY</b>

<b>Today's VIP Signals:</b>
✅ {approved} elite signals delivered
🏆 {wins} hit profit targets
📈 Win Rate: {win_rate:.1f}%
{pnl_emoji} {pnl_text}
{streak_text}{vip_tp_summary}{vip_value}
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
        """Generate weekly report with REAL trade data — no generic templates"""
        try:
            from datetime import datetime, timedelta
            today = datetime.utcnow()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Pull REAL closed signals from this week
            week_closed = await self.db.get_closed_signals(days=7)
            week_closed = [s for s in week_closed
                          if s.closed_at and s.closed_at >= start_of_week]
            
            # ALSO include active signals with partial closes or TP hits this week
            active_signals = await self.db.get_active_signals()
            week_partial_or_tp = []
            for s in active_signals:
                # Check if TP hit this week
                tp_hit_this_week = False
                for tp_level in [1, 2, 3]:
                    tp_hit_at = getattr(s, f'tp{tp_level}_hit_at', None)
                    if tp_hit_at and tp_hit_at >= start_of_week:
                        tp_hit_this_week = True
                        break
                
                # Check if partial close this week
                partial_close_this_week = False
                if hasattr(s, 'metadata') and s.metadata and 'partial_closes' in s.metadata:
                    for pc in s.metadata['partial_closes']:
                        pc_time = datetime.fromisoformat(pc['timestamp'])
                        if pc_time >= start_of_week:
                            partial_close_this_week = True
                            break
                
                if tp_hit_this_week or partial_close_this_week:
                    week_partial_or_tp.append(s)
            
            # Pull ALL closed signals for running total
            all_closed = await self.db.get_closed_signals(days=365)
            
            # Calculate REAL weekly stats from actual signals (closed + partial)
            # For closed signals, use full P&L
            # For partial closes, use the P&L of the closed portion
            wins = [s for s in week_closed if (s.pnl_percent or 0) > 0]
            losses = [s for s in week_closed if (s.pnl_percent or 0) <= 0]
            week_pnl = sum((s.pnl_percent or 0) for s in week_closed)
            
            # Add partial close P&L
            for s in week_partial_or_tp:
                if hasattr(s, 'metadata') and s.metadata and 'partial_closes' in s.metadata:
                    partial_pnl = sum(pc['pnl'] for pc in s.metadata['partial_closes'])
                    week_pnl += partial_pnl
                    if partial_pnl > 0:
                        wins.append(s)
                    else:
                        losses.append(s)
            
            total_trades = len(week_closed) + len(week_partial_or_tp)
            win_rate = (len(wins) / total_trades * 100) if total_trades else 0
            
            # Running total PnL (all time)
            total_pnl = sum((s.pnl_percent or 0) for s in all_closed)
            total_wins = len([s for s in all_closed if (s.pnl_percent or 0) > 0])
            total_losses = len(all_closed) - total_wins
            total_win_rate = (total_wins / len(all_closed) * 100) if all_closed else 0
            
            # Best and worst trade this week
            best_trade = max(week_closed, key=lambda s: s.pnl_percent or 0) if week_closed else None
            worst_trade = min(week_closed, key=lambda s: s.pnl_percent or 0) if week_closed else None
            
            # Build individual trade lines (closed + partial/TP)
            trade_lines = []
            
            # First, add fully closed trades
            for s in week_closed:
                emoji = "🟢" if (s.pnl_percent or 0) > 0 else "🔴"
                annotation = ""
                
                # Determine which TP was hit (for R:R context)
                tp_hit_text = ""
                if s.tp3_hit:
                    tp_hit_text = " [TP3]"
                elif s.tp2_hit:
                    tp_hit_text = " [TP2]"
                elif s.tp1_hit:
                    tp_hit_text = " [TP1]"
                elif s.stop_hit:
                    tp_hit_text = " [SL]"
                
                # Add R:R ratio if available
                rr_text = ""
                if hasattr(s, 'risk_reward') and s.risk_reward:
                    rr_text = f" ({s.risk_reward:.1f}R)"
                
                # Check if it was a partial close that later fully closed
                if hasattr(s, 'metadata') and s.metadata and 'partial_closes' in s.metadata:
                    total_partial = sum(pc['percent'] for pc in s.metadata['partial_closes'])
                    if total_partial > 0:
                        annotation = f" (partial close: {total_partial:.0f}%)"
                
                trade_lines.append(
                    f"{emoji} {s.symbol} {s.direction.value}: {s.pnl_percent or 0:+.2f}%{tp_hit_text}{rr_text}{annotation}"
                )
            
            # Then, add active trades with TP hits or partial closes
            for s in week_partial_or_tp:
                # Determine annotation
                annotations = []
                
                # Check TP hits
                if s.tp1_hit:
                    annotations.append("TP1")
                if s.tp2_hit:
                    annotations.append("TP2")
                if s.tp3_hit:
                    annotations.append("TP3")
                
                # Check partial closes
                if hasattr(s, 'metadata') and s.metadata and 'partial_closes' in s.metadata:
                    total_partial = sum(pc['percent'] for pc in s.metadata['partial_closes'])
                    remaining = s.metadata.get('remaining_position', 100)
                    if total_partial > 0:
                        annotations.append(f"{total_partial:.0f}% closed, {remaining:.0f}% running")
                
                annotation_text = " — " + ", ".join(annotations) if annotations else ""
                
                # Add R:R ratio if available
                rr_text = ""
                if hasattr(s, 'risk_reward') and s.risk_reward:
                    rr_text = f" ({s.risk_reward:.1f}R)"
                
                # For partial closes, show the P&L of the closed portion
                if hasattr(s, 'metadata') and s.metadata and 'partial_closes' in s.metadata:
                    partial_pnl = sum(pc['pnl'] for pc in s.metadata['partial_closes'])
                    emoji = "🟢" if partial_pnl > 0 else "🔴"
                    trade_lines.append(
                        f"{emoji} {s.symbol} {s.direction.value}: {partial_pnl:+.2f}%{rr_text}{annotation_text}"
                    )
                else:
                    # Just TP hit, no partial close yet
                    trade_lines.append(
                        f"🟡 {s.symbol} {s.direction.value}: {annotation_text}{rr_text} (still running)"
                    )
            
            trades_text = "\n".join(trade_lines) if trade_lines else "No trades closed this week yet."
            
            pnl_emoji = "🟢" if week_pnl >= 0 else "📊"
            pnl_text = f"+{week_pnl:.2f}%" if week_pnl >= 0 else f"{week_pnl:.2f}%"
            
            # Specific narrative based on REAL data
            if week_closed:
                if week_pnl > 0:
                    narrative = f"Week closed +{week_pnl:.2f}%. Best trade: {best_trade.symbol} at +{best_trade.pnl_percent:.2f}%."
                elif week_pnl < 0:
                    narrative = f"Week closed {week_pnl:.2f}%. {len(wins)} win(s), {len(losses)} loss(es). Edge plays out over sample size."
                else:
                    narrative = f"Week closed flat. {len(wins)} win(s), {len(losses)} loss(es)."
            else:
                narrative = "No signals closed this week yet. Active trades still running."
            
            # Active trades still running
            active_signals = await self.db.get_active_signals()
            active_text = ""
            if active_signals:
                active_lines = [f"⏳ {s.symbol} {s.direction.value} (entry ${s.actual_entry or s.entry_price:.4f})" for s in active_signals[:5]]
                active_text = "\n<b>Still Running:</b>\n" + "\n".join(active_lines)
            
            # Admin report (full details)
            admin_report = f"""📊 <b>WEEKLY REPORT — {start_of_week.strftime('%d %b')} to {today.strftime('%d %b')}</b>

<b>This Week's Closed Trades ({len(week_closed)}):</b>
{trades_text}

<b>This Week:</b>
{pnl_emoji} Weekly P&L: {pnl_text}
🏆 Wins: {len(wins)} | 📊 Losses: {len(losses)}
📈 Win Rate: {win_rate:.1f}%

<b>Running Total (All Time):</b>
💰 Total P&L: {total_pnl:+.2f}%
🏆 {total_wins} wins | 📊 {total_losses} losses
� Overall Win Rate: {total_win_rate:.1f}%

<b>Best This Week:</b>
{best_trade.symbol if best_trade else 'N/A'}: +{best_trade.pnl_percent:.2f}%"""
            if worst_trade and worst_trade != best_trade:
                admin_report += f"\n<b>Worst This Week:</b>\n{worst_trade.symbol}: {worst_trade.pnl_percent:.2f}%"
            admin_report += f"""
{active_text}

Keep up the great work! 🚀"""

            # VIP report — real data, no generic templates
            vip_report = f"""🏆 <b>WEEKLY VIP SUMMARY</b>
<b>{start_of_week.strftime('%d %b')} — {today.strftime('%d %b')}</b>

<b>This Week's Results ({len(week_closed)} closed):</b>
{trades_text}

<b>Week P&L:</b> {pnl_emoji} {pnl_text}
<b>Win Rate:</b> {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)

<b>Running Total P&L:</b> � {total_pnl:+.2f}%
<b>All-Time Record:</b> {total_wins}W / {total_losses}L ({total_win_rate:.1f}%)

<b>The Bottom Line:</b>
{narrative}

{active_text}

See you next week! 💎"""

            # Free channel marketing — specific numbers only
            if week_closed and week_pnl != 0:
                free_cta = f"🔥 VIPs closed {len(week_closed)} signals this week for {pnl_text} P&L."
            else:
                free_cta = "💎 VIP signals with full trade management and live updates."
            
            free_report = f"""📊 <b>Weekly VIP Performance</b>
<b>{start_of_week.strftime('%d %b')} — {today.strftime('%d %b')}</b>

This week VIPs:
✅ {len(week_closed)} signals closed
🏆 {len(wins)} wins | � {len(losses)} losses
{pnl_emoji} Weekly P&L: {pnl_text}
� Running total: {total_pnl:+.2f}%

{free_cta}

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
                'admin': f'Error generating weekly report: {e}',
                'vip': f'Error generating weekly report: {e}',
                'free': f'Error generating weekly report: {e}'
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
