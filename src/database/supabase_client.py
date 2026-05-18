from supabase import create_client, Client
from typing import List, Optional, Dict
from datetime import datetime
import uuid
import re
from src.config import settings
from src.models.signal import TradingSignal, SignalStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
        
    async def save_signal(self, signal: TradingSignal) -> bool:
        try:
            # Generate ID if not set (e.g., manual signals from dashboard)
            if not signal.id:
                signal.id = str(uuid.uuid4())
            
            # Debug: log the actual values being saved
            logger.info(f"DB SAVE: {signal.symbol} | entry={signal.entry_price} | sl={signal.stop_loss} | tp1={signal.take_profit_1} | rr={signal.risk_reward}")
            
            # Build data dict dynamically - only include fields that are set
            data = {
                'id': signal.id,
                'symbol': signal.symbol,
                'direction': signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
                'setup_type': signal.setup_type.value if hasattr(signal.setup_type, 'value') else str(signal.setup_type),
                'timeframe': signal.timeframe,
                'entry_price': signal.entry_price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit_1,     # legacy column name
                'take_profit_1': signal.take_profit_1,
                'confidence': signal.confidence,
                'technical_score': signal.technical_score.dict(),
                'context_score': signal.context_score.dict(),
                'reasoning': signal.reasoning,
                'status': signal.status.value if hasattr(signal.status, 'value') else str(signal.status),
                'risk_reward': signal.risk_reward,
                'atr': signal.atr,
                'volume_24h': signal.volume_24h,
                'created_at': signal.created_at.isoformat(),
            }
            
            # Only add optional fields if they exist
            if signal.take_profit_2 is not None:
                data['take_profit_2'] = signal.take_profit_2
            if signal.take_profit_3 is not None:
                data['take_profit_3'] = signal.take_profit_3
            if signal.market_context:
                data['market_context'] = signal.market_context
            if signal.news_context:
                data['news_context'] = signal.news_context
            if signal.expires_at:
                data['expires_at'] = signal.expires_at.isoformat()
            if signal.approved_at:
                data['approved_at'] = signal.approved_at.isoformat()
            if signal.published_at:
                data['published_at'] = signal.published_at.isoformat()
            if signal.closed_at:
                data['closed_at'] = signal.closed_at.isoformat()
            if signal.free_channel_message_id:
                data['free_channel_message_id'] = signal.free_channel_message_id
            if signal.vip_channel_message_id:
                data['vip_channel_message_id'] = signal.vip_channel_message_id
            if signal.actual_entry is not None:
                data['actual_entry'] = signal.actual_entry
            if signal.actual_exit is not None:
                data['actual_exit'] = signal.actual_exit
            if signal.pnl_percent is not None:
                data['pnl_percent'] = signal.pnl_percent
            
            # Try to save with progressive column stripping
            # If a column doesn't exist in the DB, we extract its name from the error
            # and retry without it — up to 10 times to avoid infinite loops
            data_to_save = data.copy()
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    result = self.client.table('signals').upsert(data_to_save).execute()
                    if attempt > 0:
                        logger.warning(f"Signal {signal.id} saved after stripping {max_retries - 10 + attempt} missing columns. Run migration to add them.")
                    break
                except Exception as save_err:
                    err_str = str(save_err)
                    # Extract missing column name from error like: "Could not find the 'risk_reward' column"
                    match = re.search(r"Could not find the '([^']+)' column", err_str)
                    if match:
                        missing_col = match.group(1)
                        if missing_col in data_to_save:
                            logger.warning(f"DB column '{missing_col}' not found — removing from save data and retrying")
                            del data_to_save[missing_col]
                            continue  # retry
                        else:
                            logger.error(f"DB reports missing column '{missing_col}' but it's already removed. Raw error: {err_str}")
                            return False
                    # Handle type mismatch: JSON sent to numeric column
                    if "invalid input syntax" in err_str and ("technical_score" in data_to_save or "context_score" in data_to_save):
                        if "technical_score" in data_to_save:
                            logger.warning("DB column 'technical_score' expects numeric — stripping JSON and retrying")
                            del data_to_save["technical_score"]
                        if "context_score" in data_to_save:
                            logger.warning("DB column 'context_score' expects numeric — stripping JSON and retrying")
                            del data_to_save["context_score"]
                        continue  # retry
                    # Also handle NOT NULL constraint errors on remaining columns
                    if "violates not-null constraint" in err_str:
                        logger.error(f"DB save failed — required field is null: {err_str}")
                        return False
                    # Any other error is fatal
                    logger.error(f"DB save failed: {err_str}")
                    return False
            else:
                # Exceeded max retries
                logger.error(f"DB save failed after {max_retries} attempts stripping columns. Last attempt had {len(data_to_save)} fields.")
                return False
            
            logger.info(f"Signal {signal.id} saved to database")
            return True
            
        except Exception as e:
            logger.error(f"Error saving signal to database: {e}")
            return False
    
    async def get_signal(self, signal_id: str) -> Optional[TradingSignal]:
        try:
            result = self.client.table('signals').select('*').eq('id', signal_id).execute()
            
            if result.data:
                return self._dict_to_signal(result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting signal from database: {e}")
            return None
    
    async def get_active_signals(self) -> List[TradingSignal]:
        """Get all active/approved signals that are being tracked (not closed or rejected)"""
        try:
            # Include both 'active' and 'approved' status - these are running trades
            result = self.client.table('signals').select('*')\
                .in_('status', ['active', 'approved'])\
                .execute()
            
            signals = []
            for data in result.data:
                try:
                    signals.append(self._dict_to_signal(data))
                except Exception as row_err:
                    logger.warning(f"Skipping signal row {data.get('id', '?')} due to load error: {row_err}")
            return signals
            
        except Exception as e:
            logger.error(f"Error getting active signals: {e}")
            return []
    
    async def get_active_signal_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Check if there's already a pending/active/approved signal for this symbol"""
        try:
            result = self.client.table('signals').select('*')\
                .eq('symbol', symbol)\
                .in_('status', ['pending', 'approved', 'active'])\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error checking active signal for {symbol}: {e}")
            return None
    
    async def get_signals_by_date(self, start_date: datetime, end_date: datetime) -> List[TradingSignal]:
        try:
            result = self.client.table('signals').select('*')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            return [self._dict_to_signal(data) for data in result.data]
            
        except Exception as e:
            logger.error(f"Error getting signals by date: {e}")
            return []
    
    async def update_signal_status(self, signal_id: str, status: SignalStatus) -> bool:
        try:
            self.client.table('signals').update({'status': status.value}).eq('id', signal_id).execute()
            logger.info(f"Signal {signal_id} status updated to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating signal status: {e}")
            return False
    
    async def mark_tp_hit(self, signal_id: str, tp_level: int) -> bool:
        """Mark a TP level as hit"""
        try:
            field_name = f'tp{tp_level}_hit'
            self.client.table('signals').update({
                field_name: True,
                f'tp{tp_level}_hit_at': datetime.utcnow().isoformat()
            }).eq('id', signal_id).execute()
            
            logger.info(f"Signal {signal_id} TP{tp_level} marked as hit")
            return True
            
        except Exception as e:
            logger.error(f"Error marking TP{tp_level} hit: {e}")
            return False
    
    async def update_stop_loss(self, signal_id: str, new_stop_loss: float) -> bool:
        """Update stop loss (e.g., move to breakeven after TP1)"""
        try:
            self.client.table('signals').update({
                'stop_loss': new_stop_loss,
                'stop_updated_at': datetime.utcnow().isoformat()
            }).eq('id', signal_id).execute()
            
            logger.info(f"Signal {signal_id} SL updated to {new_stop_loss}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating stop loss: {e}")
            return False
    
    async def close_signal(self, signal_id: str, actual_exit: float, pnl_percent: float) -> bool:
        try:
            self.client.table('signals').update({
                'status': SignalStatus.CLOSED.value,
                'actual_exit': actual_exit,
                'pnl_percent': pnl_percent,
                'closed_at': datetime.utcnow().isoformat()
            }).eq('id', signal_id).execute()
            
            logger.info(f"Signal {signal_id} closed with PnL: {pnl_percent:.2f}%")
            return True
            
        except Exception as e:
            logger.error(f"Error closing signal: {e}")
            return False
    
    async def get_performance_stats(self) -> Dict:
        try:
            result = self.client.table('signals').select('*').eq('status', 'closed').execute()
            
            signals = result.data
            
            if not signals:
                return {
                    'total_signals': 0,
                    'win_rate': 0,
                    'avg_pnl': 0,
                    'total_pnl': 0,
                    'avg_rr': 0,
                    'best_trade': None,
                    'worst_trade': None
                }
            
            total = len(signals)
            wins = len([s for s in signals if s.get('pnl_percent', 0) > 0])
            win_rate = (wins / total * 100) if total > 0 else 0
            
            pnls = [s.get('pnl_percent', 0) for s in signals]
            avg_pnl = sum(pnls) / len(pnls) if pnls else 0
            total_pnl = sum(pnls)
            
            rr_values = [s.get('risk_reward', 0) for s in signals]
            avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0
            
            best = max(signals, key=lambda s: s.get('pnl_percent', 0))
            worst = min(signals, key=lambda s: s.get('pnl_percent', 0))
            
            return {
                'total_signals': total,
                'wins': wins,
                'losses': total - wins,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'total_pnl': total_pnl,
                'avg_rr': avg_rr,
                'best_trade': {'symbol': best.get('symbol'), 'pnl': best.get('pnl_percent')},
                'worst_trade': {'symbol': worst.get('symbol'), 'pnl': worst.get('pnl_percent')}
            }
            
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {}
    
    async def get_pending_signals(self) -> List[TradingSignal]:
        """Get signals awaiting admin approval"""
        try:
            result = self.client.table('signals').select('*').eq('status', 'pending').execute()
            return [self._dict_to_signal(data) for data in result.data]
        except Exception as e:
            logger.error(f"Error getting pending signals: {e}")
            return []
    
    async def get_rejected_signals(self, days: int = 7) -> List[TradingSignal]:
        """Get recently rejected signals"""
        try:
            from datetime import datetime, timedelta
            start_date = datetime.utcnow() - timedelta(days=days)
            result = self.client.table('signals').select('*')\
                .eq('status', 'rejected')\
                .gte('created_at', start_date.isoformat())\
                .execute()
            return [self._dict_to_signal(data) for data in result.data]
        except Exception as e:
            logger.error(f"Error getting rejected signals: {e}")
            return []
    
    async def get_daily_stats(self, date: datetime = None) -> Dict:
        """Get statistics for a specific day"""
        try:
            from datetime import datetime, timedelta
            if date is None:
                date = datetime.utcnow()
            
            start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            
            result = self.client.table('signals').select('*')\
                .gte('created_at', start.isoformat())\
                .lt('created_at', end.isoformat())\
                .execute()
            
            signals = result.data
            
            approved = [s for s in signals if s.get('admin_approved')]
            rejected = [s for s in signals if s.get('admin_rejected')]
            closed = [s for s in signals if s.get('status') == 'closed']
            
            wins = len([s for s in closed if s.get('pnl_percent', 0) > 0])
            
            return {
                'date': start.strftime('%Y-%m-%d'),
                'total_scanned': len(signals),
                'approved': len(approved),
                'rejected': len(rejected),
                'closed': len(closed),
                'wins': wins,
                'losses': len(closed) - wins,
                'win_rate': (wins / len(closed) * 100) if closed else 0,
                'total_pnl': sum(s.get('pnl_percent', 0) for s in closed),
                'avg_confidence': sum(s.get('confidence', 0) for s in approved) / len(approved) if approved else 0
            }
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return {}
    
    async def get_weekly_stats(self) -> Dict:
        """Get statistics for the current week"""
        try:
            from datetime import datetime, timedelta
            today = datetime.utcnow()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            result = self.client.table('signals').select('*')\
                .gte('created_at', start_of_week.isoformat())\
                .execute()
            
            signals = result.data
            
            approved = [s for s in signals if s.get('admin_approved')]
            rejected = [s for s in signals if s.get('admin_rejected')]
            closed = [s for s in signals if s.get('status') == 'closed']
            
            wins = len([s for s in closed if s.get('pnl_percent', 0) > 0])
            
            # Most traded asset
            symbols = {}
            for s in approved:
                sym = s.get('symbol', 'Unknown')
                symbols[sym] = symbols.get(sym, 0) + 1
            most_traded = max(symbols, key=symbols.get) if symbols else 'None'
            
            return {
                'week_start': start_of_week.strftime('%Y-%m-%d'),
                'total_signals': len(approved),
                'wins': wins,
                'losses': len(closed) - wins,
                'win_rate': (wins / len(closed) * 100) if closed else 0,
                'total_pnl': sum(s.get('pnl_percent', 0) for s in closed),
                'avg_rr': sum(s.get('risk_reward', 0) for s in approved) / len(approved) if approved else 0,
                'most_traded': most_traded,
                'rejected_count': len(rejected),
                'approval_ratio': len(approved) / (len(approved) + len(rejected)) * 100 if (approved or rejected) else 0
            }
        except Exception as e:
            logger.error(f"Error getting weekly stats: {e}")
            return {}
    
    async def save_subscriber(self, user_id: str = None, username: str = None, tier: str = None,
                               stripe_customer_id: str = None, extra_data: Dict = None) -> bool:
        """Save or update a subscriber. Supports trial tracking via extra_data dict."""
        try:
            data = extra_data or {}
            
            # Merge provided args into data
            if user_id:
                data['user_id'] = user_id
            if username:
                data['username'] = username
            if tier:
                data['tier'] = tier
            if stripe_customer_id:
                data['stripe_customer_id'] = stripe_customer_id
            
            # Default fields
            if 'subscribed_at' not in data:
                data['subscribed_at'] = datetime.utcnow().isoformat()
            if 'active' not in data:
                data['active'] = True
            
            self.client.table('subscribers').upsert(data).execute()
            logger.info(f"Subscriber {data.get('username', user_id)} saved/updated")
            return True
            
        except Exception as e:
            logger.error(f"Error saving subscriber: {e}")
            return False
    
    async def get_active_subscribers(self, tier: str = None) -> List[Dict]:
        try:
            query = self.client.table('subscribers').select('*').eq('active', True)
            
            if tier:
                query = query.eq('tier', tier)
            
            result = query.execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting subscribers: {e}")
            return []
    
    async def get_subscriber(self, user_id: str) -> Optional[Dict]:
        """Get subscriber by user_id"""
        try:
            result = self.client.table('subscribers').select('*').eq('user_id', user_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting subscriber {user_id}: {e}")
            return None
    
    async def deactivate_subscriber(self, user_id: str) -> bool:
        try:
            self.client.table('subscribers').update({
                'active': False,
                'cancelled_at': datetime.utcnow().isoformat()
            }).eq('user_id', user_id).execute()
            
            logger.info(f"Subscriber {user_id} deactivated")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating subscriber: {e}")
            return False
    
    async def update_subscriber(self, user_id: str, data: Dict) -> bool:
        """Update subscriber fields (for trial management)"""
        try:
            self.client.table('subscribers').update(data).eq('user_id', user_id).execute()
            logger.info(f"Subscriber {user_id} updated")
            return True
        except Exception as e:
            logger.error(f"Error updating subscriber: {e}")
            return False
    
    async def update_signal_result(self, signal_id: str, status: SignalStatus,
                                   actual_exit: float, pnl_percent: float,
                                   tp_level: int = None) -> bool:
        """Update signal when TP/SL is hit (AutoPilot performance tracking)"""
        try:
            data = {
                'status': status.value,
                'actual_exit': actual_exit,
                'pnl_percent': pnl_percent,
                'closed_at': datetime.utcnow().isoformat()
            }
            if tp_level is not None:
                data['tp_level'] = tp_level
            
            self.client.table('signals').update(data).eq('id', signal_id).execute()
            logger.info(f"Signal {signal_id} result updated: {status.value} P&L={pnl_percent:+.2f}%")
            return True
        except Exception as e:
            logger.error(f"Error updating signal result: {e}")
            return False
    
    async def get_trials_expiring_soon(self, days: int = 2) -> List[Dict]:
        """Get trials that expire in N days (for reminder)"""
        try:
            from datetime import timedelta
            now = datetime.utcnow()
            expiry_window = now + timedelta(days=days)
            
            result = self.client.table('subscribers').select('*')\
                .eq('tier', 'trial')\
                .eq('active', True)\
                .gte('trial_ends_at', now.isoformat())\
                .lte('trial_ends_at', expiry_window.isoformat())\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Error getting expiring trials: {e}")
            return []
    
    async def get_expired_trials(self, now: datetime = None) -> List[Dict]:
        """Get trials that have expired"""
        try:
            if now is None:
                now = datetime.utcnow()
            
            result = self.client.table('subscribers').select('*')\
                .eq('tier', 'trial')\
                .eq('active', True)\
                .lt('trial_ends_at', now.isoformat())\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Error getting expired trials: {e}")
            return []
    
    def _dict_to_signal(self, data: Dict) -> TradingSignal:
        from src.models.signal import TechnicalScore, ContextScore, SignalDirection, SetupType
        
        def _parse_dt(key):
            val = data.get(key)
            return datetime.fromisoformat(val) if val else None
        
        def _safe(val, default):
            return val if val is not None else default
        
        # Safe defaults for potentially missing/null fields
        entry_price = _safe(data.get('entry_price'), 0.0)
        stop_loss = _safe(data.get('stop_loss'), entry_price * 0.95 if entry_price else 0.0)
        take_profit_1 = _safe(data.get('take_profit_1'), data.get('take_profit'))  # fallback to legacy
        if take_profit_1 is None:
            take_profit_1 = entry_price * 1.05 if entry_price else 0.0
        
        technical_raw = data.get('technical_score')
        if isinstance(technical_raw, dict):
            technical_score = TechnicalScore(**technical_raw)
        else:
            conf = _safe(data.get('confidence'), 50.0)
            technical_score = TechnicalScore(trend_score=conf, volume_score=conf, momentum_score=conf, structure_score=conf, total_score=conf)
        
        context_raw = data.get('context_score')
        if isinstance(context_raw, dict):
            context_score = ContextScore(**context_raw)
        else:
            conf = _safe(data.get('confidence'), 50.0)
            context_score = ContextScore(macro_score=conf, news_score=conf, sentiment_score=conf, total_score=conf)
        
        return TradingSignal(
            id=_safe(data.get('id'), str(uuid.uuid4())),
            symbol=_safe(data.get('symbol'), 'UNKNOWN'),
            direction=SignalDirection(_safe(data.get('direction'), 'LONG')),
            setup_type=SetupType(_safe(data.get('setup_type'), 'support_resistance')),
            timeframe=_safe(data.get('timeframe'), '1h'),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=data.get('take_profit_2'),
            take_profit_3=data.get('take_profit_3'),
            confidence=_safe(data.get('confidence'), 50.0),
            technical_score=technical_score,
            context_score=context_score,
            reasoning=_safe(data.get('reasoning'), 'No analysis provided'),
            status=SignalStatus(_safe(data.get('status'), 'pending')),
            risk_reward=_safe(data.get('risk_reward'), 2.0),
            atr=_safe(data.get('atr'), 0.0),
            volume_24h=_safe(data.get('volume_24h'), 0.0),
            market_context=data.get('market_context'),
            news_context=data.get('news_context'),
            created_at=_parse_dt('created_at') or datetime.utcnow(),
            expires_at=_parse_dt('expires_at'),
            approved_at=_parse_dt('approved_at'),
            published_at=_parse_dt('published_at'),
            closed_at=_parse_dt('closed_at'),
            free_channel_message_id=data.get('free_channel_message_id'),
            vip_channel_message_id=data.get('vip_channel_message_id'),
            actual_entry=data.get('actual_entry'),
            actual_exit=data.get('actual_exit'),
            pnl_percent=data.get('pnl_percent'),
            tp1_hit=data.get('tp1_hit', False),
            tp2_hit=data.get('tp2_hit', False),
            tp3_hit=data.get('tp3_hit', False),
            tp1_hit_at=_parse_dt('tp1_hit_at'),
            tp2_hit_at=_parse_dt('tp2_hit_at'),
            tp3_hit_at=_parse_dt('tp3_hit_at'),
            stop_hit=data.get('stop_hit', False),
            stop_hit_at=_parse_dt('stop_hit_at'),
            stop_moved_to_breakeven=data.get('stop_moved_to_breakeven', False),
            admin_approved=data.get('admin_approved', False),
            admin_rejected=data.get('admin_rejected', False),
            rejection_reason=data.get('rejection_reason'),
            free_channel_posted=data.get('free_channel_posted', False),
            vip_channel_posted=data.get('vip_channel_posted', False),
            cancelled=data.get('cancelled', False),
            cancellation_reason=data.get('cancellation_reason'),
            free_channel_delayed=data.get('free_channel_delayed', False),
            free_channel_scheduled_at=_parse_dt('free_channel_scheduled_at'),
        )

    # ==================== ALPHA/DEGEN PLAYS ====================

    async def save_alpha_play(self, play_data: dict) -> bool:
        """Save an alpha play to the database"""
        try:
            data = {
                'id': play_data.get('id', str(uuid.uuid4())),
                'symbol': play_data.get('symbol'),
                'name': play_data.get('name'),
                'chain': play_data.get('chain'),
                'token_address': play_data.get('token_address'),
                'play_type': 'alpha',
                'status': play_data.get('status', 'active'),
                'entry_price': play_data.get('entry_price'),
                'stop_loss': play_data.get('stop_loss'),
                'take_profit_1': play_data.get('take_profit_1'),
                'take_profit_2': play_data.get('take_profit_2'),
                'current_price': play_data.get('current_price'),
                'current_pnl': play_data.get('current_pnl'),
                'market_cap': play_data.get('market_cap'),
                'volume_24h': play_data.get('volume_24h'),
                'price_change_24h': play_data.get('price_change_24h'),
                'overall_score': play_data.get('overall_score'),
                'catalyst': play_data.get('catalyst'),
                'dex_url': play_data.get('dex_url'),
                'chart_url': play_data.get('chart_url'),
                'buy_url': play_data.get('buy_url'),
                'position_size': play_data.get('position_size'),
                'red_flags': play_data.get('red_flags'),
                'created_at': datetime.utcnow().isoformat(),
                'approved_at': play_data.get('approved_at'),
                'closed_at': play_data.get('closed_at'),
            }
            
            self.client.table('alpha_plays').upsert(data).execute()
            logger.info(f"Alpha play {data['symbol']} saved to database")
            return True
            
        except Exception as e:
            logger.error(f"Error saving alpha play: {e}")
            return False

    async def get_alpha_plays(self, status: str = None, limit: int = 50) -> List[Dict]:
        """Get alpha plays from database"""
        try:
            query = self.client.table('alpha_plays').select('*').order('created_at', desc=True).limit(limit)
            
            if status:
                query = query.eq('status', status)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting alpha plays: {e}")
            return []

    async def update_alpha_play(self, play_id: str, updates: dict) -> bool:
        """Update an alpha play"""
        try:
            self.client.table('alpha_plays').update(updates).eq('id', play_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating alpha play: {e}")
            return False
