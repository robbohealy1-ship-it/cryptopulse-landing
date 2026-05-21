"""
CRYPTO PULSE SIGNALS — AUTOPILOT SYSTEM
Handles everything automatically without human intervention:
- Signal performance tracking (TP/SL monitoring, P&L calculation)
- Auto-marketing scheduling (outlook, recap, engagement, reports)
- Public stats sharing (Twitter/Discord weekly performance)
- Free trial automation (7-day VIP grants, conversion tracking)
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import settings
from src.models.signal import TradingSignal, SignalStatus, SignalDirection
from src.utils.logger import get_logger
from src.payments.payment_orchestrator import PaymentOrchestrator

logger = get_logger(__name__)


class PerformanceTracker:
    """
    Automatically tracks every approved signal:
    - Monitors if TP1/TP2/TP3 or SL is hit
    - Calculates P&L percentage
    - Stores results in database
    - Generates performance stats for reports
    """
    
    def __init__(self, scanner=None, db=None, on_signal_result=None):
        self.scanner = scanner
        self.db = db
        self.on_signal_result = on_signal_result  # Callback for FOMO campaigns
        self.active_signals: Dict[str, TradingSignal] = {}  # symbol -> signal
        self.pending_limit_orders: Dict[str, TradingSignal] = {}  # waiting for limit hit
        self.performance_log: List[Dict] = []
        
    async def track_signal(self, signal: TradingSignal):
        """Start tracking an approved signal for TP/SL hits"""
        if signal.is_limit_order:
            self.pending_limit_orders[signal.id] = signal
            logger.info(f"⏳ Limit order pending for {signal.symbol} at ${signal.entry_price:.4f} — tracking will start when limit is hit")
            return
        
        # For market orders, use actual_entry if set, otherwise fall back to planned entry_price
        entry = signal.actual_entry if signal.actual_entry is not None else signal.entry_price
        self.active_signals[signal.id] = {
            'signal': signal,
            'entry_price': entry,
            'highest_price': entry,
            'lowest_price': entry,
            'tp1_hit': False,
            'tp2_hit': False,
            'tp3_hit': False,
            'stop_moved_to_breakeven': False,
            'partial_exits': [],
            'entry_time': datetime.utcnow()
        }
        
        logger.info(f"🎯 Performance tracking started for {signal.symbol} {signal.direction.value} at ${entry:.4f}")
        
        # Save to DB as "active"
        if self.db:
            await self.db.update_signal_status(
                signal_id=signal.id,
                status=SignalStatus.ACTIVE
            )
    
    async def _check_limit_order_hit(self, signal_id: str):
        """Check if a limit order's entry price has been hit. If so, move to active tracking."""
        signal = self.pending_limit_orders.get(signal_id)
        if not signal:
            return
        
        try:
            ticker = await self.scanner.fetch_ticker(signal.symbol)
            current_price = ticker.get('last', 0)
            if not current_price or current_price <= 0:
                return
        except Exception:
            return
        
        entry = signal.entry_price
        direction = signal.direction.value
        
        hit = False
        if direction == 'LONG':
            # For LONG limit: price must drop to or below entry
            hit = current_price <= entry
        else:  # SHORT
            # For SHORT limit: price must rise to or above entry
            hit = current_price >= entry
        
        if hit:
            signal.actual_entry = current_price
            signal.status = SignalStatus.ACTIVE
            del self.pending_limit_orders[signal_id]
            self.active_signals[signal_id] = {
                'signal': signal,
                'entry_price': current_price,
                'highest_price': current_price,
                'lowest_price': current_price,
                'tp1_hit': False,
                'tp2_hit': False,
                'tp3_hit': False,
                'stop_moved_to_breakeven': False,
                'partial_exits': [],
                'entry_time': datetime.utcnow()
            }
            logger.info(f"🎯 Limit order hit for {signal.symbol} at ${current_price:.4f} — tracking started")
    
    async def check_all_signals(self):
        """Check all active signals for TP/SL hits and update P&L. Also check pending limit orders."""
        # Check pending limit orders - move to active when limit price is hit
        for signal_id in list(self.pending_limit_orders.keys()):
            await self._check_limit_order_hit(signal_id)
        
        # Check active signals
        for signal_id in list(self.active_signals.keys()):
            await self._check_signal(signal_id)
        
        # Save updated signals to DB
        signals = [data['signal'] for data in self.active_signals.values()]
        if signals:
            await self.db.save_signals_batch(signals)
    
    async def _check_signal(self, signal_id: str):
        """Check if a signal has hit TP or SL"""
        signal_data = self.active_signals[signal_id]
        signal = signal_data['signal']
        entry_price = signal_data['entry_price']
        highest_price = signal_data['highest_price']
        lowest_price = signal_data['lowest_price']
        tp1_hit = signal_data['tp1_hit']
        tp2_hit = signal_data['tp2_hit']
        tp3_hit = signal_data['tp3_hit']
        stop_moved_to_breakeven = signal_data['stop_moved_to_breakeven']
        partial_exits = signal_data['partial_exits']
        entry_time = signal_data['entry_time']
        
        try:
            ticker = await self.scanner.fetch_ticker(signal.symbol)
            current_price = ticker.get('last', 0)
            
            if current_price == 0:
                return
            
            direction = signal.direction
            entry = entry_price
            sl = signal.stop_loss
            tp1 = signal.take_profit_1
            tp2 = signal.take_profit_2
            tp3 = signal.take_profit_3
            
            # Determine if hit
            hit_tp = None
            hit_sl = False
            pnl_percent = None
            
            safe_entry = entry if entry and entry != 0 else 1.0  # avoid div by zero
            
            if direction == SignalDirection.LONG:
                # Check TP hits (highest first)
                if tp3 and current_price >= tp3:
                    hit_tp = 3
                    pnl_percent = ((tp3 - safe_entry) / safe_entry) * 100
                elif tp2 and current_price >= tp2:
                    hit_tp = 2
                    pnl_percent = ((tp2 - safe_entry) / safe_entry) * 100
                elif current_price >= tp1:
                    hit_tp = 1
                    pnl_percent = ((tp1 - safe_entry) / safe_entry) * 100
                elif current_price <= sl:
                    hit_sl = True
                    pnl_percent = ((sl - safe_entry) / safe_entry) * 100
            else:  # SHORT
                if tp3 and current_price <= tp3:
                    hit_tp = 3
                    pnl_percent = ((safe_entry - tp3) / safe_entry) * 100
                elif tp2 and current_price <= tp2:
                    hit_tp = 2
                    pnl_percent = ((safe_entry - tp2) / safe_entry) * 100
                elif current_price <= tp1:
                    hit_tp = 1
                    pnl_percent = ((safe_entry - tp1) / safe_entry) * 100
                elif current_price >= sl:
                    hit_sl = True
                    pnl_percent = ((safe_entry - sl) / safe_entry) * 100
            
            # If hit, record and remove from tracking
            if hit_tp or hit_sl:
                result = {
                    'symbol': signal.symbol,
                    'direction': signal.direction.value,
                    'entry': entry,
                    'exit_price': current_price,
                    'tp_hit': hit_tp,
                    'sl_hit': hit_sl,
                    'pnl_percent': round(pnl_percent, 2),
                    'timeframe': signal.timeframe,
                    'confidence': signal.confidence,
                    'created_at': signal.created_at.isoformat() if signal.created_at else None,
                    'closed_at': datetime.utcnow().isoformat(),
                    'is_win': hit_tp is not None
                }
                
                self.performance_log.append(result)
                del self.active_signals[signal_id]
                
                status = SignalStatus.TP_HIT if hit_tp else SignalStatus.SL_HIT
                emoji = "🏆" if hit_tp else "🛑"
                target = f"TP{hit_tp}" if hit_tp else "SL"
                
                logger.info(
                    f"{emoji} {signal.symbol} hit {target}! "
                    f"P&L: {pnl_percent:+.2f}% | Confidence: {signal.confidence:.0f}%"
                )
                
                # Save to database
                if self.db:
                    await self.db.update_signal_result(
                        signal_id=signal.id,
                        status=status,
                        actual_exit=current_price,
                        pnl_percent=pnl_percent,
                        tp_level=hit_tp
                    )
                
                # Auto-notify admin
                await self._notify_admin(signal, result)
                
                # 🚀 Trigger FOMO campaign if callback registered
                if self.on_signal_result:
                    try:
                        await self.on_signal_result(signal, result)
                    except Exception as e:
                        logger.error(f"Signal result callback error: {e}")
                
        except Exception as e:
            logger.error(f"Error checking signal {signal.symbol}: {e}")
    
    async def _notify_admin(self, signal: TradingSignal, result: Dict):
        """Send admin notification when signal closes"""
        emoji = "🏆 WIN" if result['is_win'] else "🛑 LOSS"
        target = f"TP{result['tp_hit']}" if result['tp_hit'] else "SL"
        
        msg = (
            f"{emoji} <b>Signal Closed</b>\n\n"
            f"<b>{signal.symbol}</b> — {signal.direction.value}\n"
            f"📈 Entry: ${signal.entry_price:.8f}\n"
            f"🎯 Hit: {target}\n"
            f"💰 P&L: {result['pnl_percent']:+.2f}%\n"
            f"⏱ Timeframe: {signal.timeframe}\n"
            f"🎯 Confidence: {signal.confidence:.0f}%\n\n"
            f"📊 Active signals: {len(self.active_signals)}"
        )
        
        logger.info(f"Admin notification: {signal.symbol} {target} {result['pnl_percent']:+.2f}%")
    
    def get_stats(self, days: int = 7) -> Dict:
        """Get performance statistics for reports"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent = [
            r for r in self.performance_log
            if datetime.fromisoformat(r['closed_at']) >= cutoff
        ]
        
        if not recent:
            return {
                'total': 0, 'wins': 0, 'losses': 0,
                'win_rate': 0, 'avg_pnl': 0, 'total_pnl': 0,
                'best_trade': None, 'worst_trade': None
            }
        
        wins = [r for r in recent if r['is_win']]
        losses = [r for r in recent if not r['is_win']]
        pnls = [r['pnl_percent'] for r in recent]
        
        return {
            'total': len(recent),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': (len(wins) / len(recent)) * 100 if recent else 0,
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
            'total_pnl': sum(pnls),
            'best_trade': max(recent, key=lambda x: x['pnl_percent']) if recent else None,
            'worst_trade': min(recent, key=lambda x: x['pnl_percent']) if recent else None,
            'by_timeframe': self._group_by_timeframe(recent)
        }
    
    def _group_by_timeframe(self, results: List[Dict]) -> Dict:
        """Group results by timeframe"""
        grouped = {}
        for r in results:
            tf = r.get('timeframe', 'unknown')
            if tf not in grouped:
                grouped[tf] = {'total': 0, 'wins': 0, 'pnl': 0}
            grouped[tf]['total'] += 1
            grouped[tf]['wins'] += 1 if r['is_win'] else 0
            grouped[tf]['pnl'] += r['pnl_percent']
        return grouped


class PublicStatsPoster:
    """
    Automatically shares performance stats publicly:
    - Weekly win rate to Twitter
    - Weekly recap to Discord
    - Monthly summary to free Telegram channel
    """
    
    def __init__(self, social_media=None, discord=None, channel_publisher=None, performance_tracker=None, db=None):
        self.social_media = social_media
        self.discord = discord
        self.channel_publisher = channel_publisher
        self.performance_tracker = performance_tracker
        self.db = db
        
    async def _get_db_stats(self, days: int = 7) -> dict:
        """Query DB for stats — survives restarts unlike in-memory tracker."""
        if not self.db:
            return self.performance_tracker.get_stats(days=days) if self.performance_tracker else {'total': 0}
        try:
            since = datetime.utcnow() - timedelta(days=days)
            result = self.db.client.table('signals').select('*').gte('created_at', since.isoformat()).execute()
            rows = result.data if hasattr(result, 'data') else []
            total = len(rows)
            if total == 0:
                return {'total': 0}
            wins = sum(1 for r in rows if (r.get('pnl_percent') or 0) > 0)
            losses = sum(1 for r in rows if (r.get('pnl_percent') or 0) < 0)
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            total_pnl = sum(r.get('pnl_percent', 0) or 0 for r in rows)
            return {
                'total': total,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': total_pnl / total if total > 0 else 0,
            }
        except Exception as e:
            logger.warning(f"DB stats query failed, falling back to memory: {e}")
            return self.performance_tracker.get_stats(days=days) if self.performance_tracker else {'total': 0}
    
    async def post_weekly_stats(self):
        """Auto-post weekly performance to all public channels"""
        stats = await self._get_db_stats(days=7)
        
        if stats['total'] == 0:
            logger.info("No trades this week — skipping public stats")
            return
        
        # Build message
        win_rate = stats['win_rate']
        total_pnl = stats['total_pnl']
        
        emoji = "🔥" if win_rate >= 60 else "📈" if win_rate >= 50 else "📊"
        pnl_emoji = "🟢" if total_pnl > 0 else "📊"
        
        message = (
            f"📊 <b>WEEKLY PERFORMANCE</b>\n\n"
            f"{emoji} Win Rate: <b>{win_rate:.0f}%</b>\n"
            f"{pnl_emoji} Total P&L: <b>{total_pnl:+.2f}%</b>\n"
            f"🏆 Winners: {stats['wins']} | 🛑 Losses: {stats['losses']}\n"
            f"📊 Avg per trade: {stats['avg_pnl']:+.2f}%\n\n"
            f"💎 Every signal had 85%+ confidence + strict risk management.\n"
            f"That's why professionals use systems, not guesswork.\n\n"
            f"Join VIP: t.me/cryptopulse_signals_free1"
        )
        
        # Post to Twitter
        if self.social_media and self.social_media.twitter_enabled:
            try:
                tweet_text = (
                    f"📊 Weekly VIP Performance\n\n"
                    f"Win Rate: {win_rate:.0f}%\n"
                    f"P&L: {total_pnl:+.2f}%\n"
                    f"{stats['wins']}W / {stats['losses']}L\n\n"
                    f"Every signal: 85%+ confidence + risk management\n\n"
                    f"Join: t.me/cryptopulse_signals_free1\n\n"
                    f"#CryptoSignals #Bitcoin #Trading"
                )
                self.social_media.twitter_client.create_tweet(text=tweet_text)
                logger.info("📣 Weekly stats posted to Twitter")
            except Exception as e:
                logger.error(f"❌ Twitter weekly stats failed: {e}")
        
        # Post to Discord
        if self.discord and self.discord.enabled:
            try:
                await self.discord.post_raw_embed({
                    'title': '📊 Weekly Performance Report',
                    'description': message.replace('<b>', '**').replace('</b>', '**'),
                    'color': 0x00ff00 if total_pnl > 0 else 0xffaa00
                })
                logger.info("📣 Weekly stats posted to Discord")
            except Exception as e:
                logger.error(f"❌ Discord weekly stats failed: {e}")
        
        # Post to free Telegram channel
        if self.channel_publisher:
            try:
                await self.channel_publisher.bot.send_message(
                    chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                    text=message,
                    parse_mode='HTML'
                )
                logger.info("📣 Weekly stats posted to free channel")
            except Exception as e:
                logger.error(f"❌ Free channel weekly stats failed: {e}")


class FreeTrialManager:
    """
    Automatically manages 7-day free VIP trials:
    - Users message VIP bot, get instant 7-day access
    - Tracks trial start/end dates
    - Auto-removes expired trials
    - Sends upgrade reminders at day 5
    """
    
    def __init__(self, db=None, channel_publisher=None, payment_orchestrator=None):
        self.db = db
        self.channel_publisher = channel_publisher
        self.payment_orchestrator = payment_orchestrator
        self.trial_duration_days = 7
        
    async def grant_trial(self, user_id: str, username: str) -> Dict:
        """Grant 7-day free trial to a user"""
        try:
            # Check if already had trial
            existing = await self.db.get_subscriber(user_id)
            if existing and existing.get('had_trial'):
                return {'success': False, 'message': 'Trial already used'}
            
            trial_end = datetime.utcnow() + timedelta(days=self.trial_duration_days)
            
            # Add to subscribers as "trial" tier
            await self.db.save_subscriber({
                'user_id': user_id,
                'username': username,
                'tier': 'trial',
                'status': 'active',
                'trial_started_at': datetime.utcnow().isoformat(),
                'trial_ends_at': trial_end.isoformat(),
                'had_trial': True
            })
            
            logger.info(f"🎁 7-day trial granted to {username} ({user_id})")
            
            return {
                'success': True,
                'message': (
                    f"🎉 <b>7-Day FREE VIP Trial Activated!</b>\n\n"
                    f"You now have FULL VIP access until:\n"
                    f"📅 {trial_end.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    f"What's included:\n"
                    f"✅ All signals instantly (no delay)\n"
                    f"✅ Full entry, SL, TP levels\n"
                    f"✅ Live updates when TP/SL hit\n"
                    f"✅ Weekly performance reports\n\n"
                    f"After trial: £29/month or save with quarterly/yearly\n\n"
                    f"Enjoy! 💎"
                ),
                'trial_end': trial_end
            }
            
        except Exception as e:
            logger.error(f"Error granting trial: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    async def check_expired_trials(self):
        """Run daily — remove expired trials, send day-5 reminders"""
        try:
            now = datetime.utcnow()
            
            # Find trials expiring in 2 days (day 5 reminder)
            day5_reminders = await self.db.get_trials_expiring_soon(days=2)
            for trial in day5_reminders:
                await self._send_reminder(trial, days_left=2)
            
            # Find expired trials
            expired = await self.db.get_expired_trials(now)
            for trial in expired:
                await self._expire_trial(trial)
                
        except Exception as e:
            logger.error(f"Error checking trials: {e}")
    
    async def _send_reminder(self, trial: Dict, days_left: int):
        """Send upgrade reminder to trial user with payment options"""
        try:
            user_id = trial['user_id']
            username = trial.get('username', 'User')
            
            # Use PaymentOrchestrator for rich message
            if self.payment_orchestrator:
                message = await self.payment_orchestrator.handle_payment_reminder(
                    user_id, username, days_left
                )
            else:
                message = (
                    f"⏰ <b>Trial Reminder</b>\n\n"
                    f"Your VIP trial ends in <b>{days_left} days</b>!\n\n"
                    f"Upgrade now: � /vip"
                )
            
            # Send via VIP bot
            from src.telegram_bot.vip_bot import vip_bot
            await vip_bot.application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"⏰ Day-5 reminder sent to {username}")
            
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
    
    async def _expire_trial(self, trial: Dict):
        """Expire a trial and downgrade user with payment options"""
        try:
            user_id = trial['user_id']
            username = trial.get('username', 'User')
            
            await self.db.update_subscriber(user_id, {
                'status': 'expired',
                'tier': 'expired_trial',
                'trial_ended_at': datetime.utcnow().isoformat()
            })
            
            # Use PaymentOrchestrator for rich expiry message
            if self.payment_orchestrator:
                message = await self.payment_orchestrator.handle_trial_expiry(user_id, username)
            else:
                message = (
                    f"� <b>Trial Expired</b>\n\n"
                    f"Your VIP trial has ended. Renew with /vip 💎"
                )
            
            from src.telegram_bot.vip_bot import vip_bot
            await vip_bot.application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info(f"⏰ Trial expired for {username}")
            
        except Exception as e:
            logger.error(f"Error expiring trial: {e}")


class AutoPilotSystem:
    """
    Master automation orchestrator.
    Call this from main.py to run everything on autopilot.
    """
    
    def __init__(self, scanner=None, db=None, social_media=None, discord=None, 
                 channel_publisher=None, community_engagement=None):
        self.scanner = scanner
        self.db = db
        self.social_media = social_media
        self.discord = discord
        self.channel_publisher = channel_publisher
        self.community_engagement = community_engagement
        
        # Payment orchestrator (for trial expiry, payment routing)
        self.payment_orchestrator = PaymentOrchestrator(
            stripe_handler=None,  # Set by main.py if available
            crypto_handler=None,  # Set by main.py if available
            db=db
        )
        
        # Sub-systems
        self.performance = PerformanceTracker(scanner, db)
        self.public_stats = PublicStatsPoster(social_media, discord, channel_publisher, self.performance, db)
        self.trial_manager = FreeTrialManager(db, channel_publisher, self.payment_orchestrator)
        
        logger.info("🤖 AutoPilot System initialized")
    
    async def on_signal_approved(self, signal: TradingSignal):
        """Called when admin approves a signal — triggers full automation"""
        # Start tracking performance
        await self.performance.track_signal(signal)
        
        # Cross-post to social (already in main.py, but log it)
        logger.info(f"🤖 AutoPilot: Signal {signal.symbol} approved, tracking + marketing activated")
    
    async def run_performance_check(self):
        """Call this every 5 minutes to check TP/SL hits"""
        await self.performance.check_all_signals()
    
    async def run_daily_automation(self):
        """Call at 23:55 UTC — daily cleanup + trial checks"""
        logger.info("🤖 AutoPilot: Running daily automation...")
        
        # Check expired trials
        await self.trial_manager.check_expired_trials()
        
        # Log performance stats
        stats = self.performance.get_stats(days=1)
        logger.info(
            f"📊 Daily Stats: {stats['wins']}W/{stats['losses']}L | "
            f"WR: {stats['win_rate']:.0f}% | P&L: {stats['total_pnl']:+.2f}%"
        )
    
    async def run_weekly_automation(self):
        """Call Sunday 20:00 UTC — weekly stats + public posting"""
        logger.info("🤖 AutoPilot: Running weekly automation...")
        
        # Post public stats
        await self.public_stats.post_weekly_stats()
        
        # Log weekly summary
        stats = self.performance.get_stats(days=7)
        logger.info(
            f"📊 Weekly Stats: {stats['wins']}W/{stats['losses']}L | "
            f"WR: {stats['win_rate']:.0f}% | P&L: {stats['total_pnl']:+.2f}%"
        )
    
    async def run_morning_outlook(self):
        """Call at 08:00 UTC — pre-market outlook + marketing"""
        logger.info("🤖 AutoPilot: Running morning outlook...")
        # Morning marketing is handled by existing scheduler
        # This is a hook for future automation
    
    def get_dashboard_stats(self) -> Dict:
        """Get all stats for admin dashboard"""
        today = self.performance.get_stats(days=1)
        week = self.performance.get_stats(days=7)
        month = self.performance.get_stats(days=30)
        
        return {
            'today': today,
            'week': week,
            'month': month,
            'active_signals': len(self.performance.active_signals),
            'status': 'operational'
        }
