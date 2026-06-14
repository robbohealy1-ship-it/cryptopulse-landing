"""
CryptoPulse Signals — Supabase Database Client
Copyright (c) 2026 CryptoPulse Signals. All rights reserved.
Unauthorized copying, distribution, or modification of this software,
via any medium, is strictly prohibited. Proprietary and confidential.
"""
from supabase import create_client, Client
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from decimal import Decimal
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
                'market_type': signal.market_type.value if hasattr(signal, 'market_type') and hasattr(signal.market_type, 'value') else 'crypto',
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
            
            # Admin workflow fields (critical for reporting accuracy)
            data['admin_approved'] = signal.admin_approved
            data['admin_rejected'] = signal.admin_rejected
            if signal.rejection_reason:
                data['rejection_reason'] = signal.rejection_reason
            
            # TP/SL hit tracking
            data['tp1_hit'] = signal.tp1_hit
            data['tp2_hit'] = signal.tp2_hit
            data['tp3_hit'] = signal.tp3_hit
            data['stop_hit'] = signal.stop_hit
            data['stop_moved_to_breakeven'] = signal.stop_moved_to_breakeven
            
            # Channel posting tracking
            data['free_channel_posted'] = signal.free_channel_posted
            data['vip_channel_posted'] = signal.vip_channel_posted
            data['is_limit_order'] = signal.is_limit_order
            data['cancelled'] = signal.cancelled
            if signal.cancellation_reason:
                data['cancellation_reason'] = signal.cancellation_reason
            
            # Chart assets
            if signal.chart_url:
                data['chart_url'] = signal.chart_url
            if signal.chart_path:
                data['chart_path'] = signal.chart_path
            
            # Partial close metadata
            if hasattr(signal, 'metadata') and signal.metadata is not None:
                data['metadata'] = signal.metadata
            
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
    
    async def get_active_signals(self, limit: int = 100) -> List[TradingSignal]:
        """Get all active/approved signals that are being tracked (not closed or rejected).
        Deduplicates by symbol, keeping only the most recently created signal per symbol."""
        try:
            # Include both 'active' and 'approved' status - these are running trades
            result = self.client.table('signals').select('*')\
                .in_('status', ['active', 'approved'])\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            # Deduplicate by symbol, keeping the most recent
            seen_symbols = set()
            signals = []
            for data in result.data:
                try:
                    sym = data.get('symbol', '')
                    if sym in seen_symbols:
                        continue
                    seen_symbols.add(sym)
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
    
    async def get_signal_by_id(self, signal_id: str):
        """Get a single signal by ID"""
        try:
            response = self.client.table('signals').select('*').eq('id', signal_id).execute()
            if response.data and len(response.data) > 0:
                return self._dict_to_signal(response.data[0])
            return None
        except Exception as e:
            logger.error(f"Error getting signal by ID: {e}")
            return None
    
    async def get_closed_signals(self, days: int = 30) -> List[TradingSignal]:
        """Get signals that have closed with P&L in the last N days."""
        try:
            start = datetime.utcnow() - timedelta(days=days)
            result = self.client.table('signals').select('*')\
                .eq('status', 'closed')\
                .gte('closed_at', start.isoformat())\
                .order('closed_at', desc=True)\
                .limit(200)\
                .execute()
            signals = [self._dict_to_signal(data) for data in result.data]
            # Filter to only those with a P&L result
            return [s for s in signals if getattr(s, 'pnl_percent', None) is not None]
        except Exception as e:
            logger.error(f"Error getting closed signals: {e}")
            return []
    
    async def get_all_signals(self, limit: int = 500) -> List[TradingSignal]:
        """Get all signals (active + closed + pending + rejected) for portfolio view."""
        try:
            result = self.client.table('signals').select('*')\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            return [self._dict_to_signal(data) for data in result.data]
        except Exception as e:
            logger.error(f"Error getting all signals: {e}")
            return []
    
    async def update_signal(self, signal_id: str, updates: dict) -> bool:
        """Update signal fields (generic update method)"""
        try:
            self.client.table('signals').update(updates).eq('id', signal_id).execute()
            logger.info(f"Signal {signal_id} updated: {list(updates.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error updating signal: {e}")
            return False
    
    async def update_signal_status(self, signal_id: str, status: SignalStatus) -> bool:
        try:
            self.client.table('signals').update({'status': status.value}).eq('id', signal_id).execute()
            logger.info(f"Signal {signal_id} status updated to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating signal status: {e}")
            return False
    
    async def save_signals_batch(self, signals: List[TradingSignal]) -> bool:
        """Save multiple signals to DB (used by autopilot performance tracker)."""
        try:
            for signal in signals:
                await self.save_signal(signal)
            return True
        except Exception as e:
            logger.error(f"Error saving signals batch: {e}")
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
        """Get statistics for a specific day — includes signals CLOSED today,
        regardless of when they were created."""
        try:
            from datetime import datetime, timedelta
            if date is None:
                date = datetime.utcnow()

            start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

            # Fetch signals created today (for scan/approval metrics)
            created_result = self.client.table('signals').select('*')\
                .gte('created_at', start.isoformat())\
                .lt('created_at', end.isoformat())\
                .execute()
            created_signals = created_result.data or []

            # Fetch signals closed today (for P&L and win/loss metrics)
            closed_result = self.client.table('signals').select('*')\
                .eq('status', 'closed')\
                .gte('closed_at', start.isoformat())\
                .lt('closed_at', end.isoformat())\
                .execute()
            closed_signals = closed_result.data or []

            # Merge: created_signals for scan counts, closed_signals for P&L
            signals = created_signals
            approved = [s for s in signals if s.get('admin_approved')]
            rejected = [s for s in signals if s.get('admin_rejected')]
            active = [s for s in signals if s.get('status') == 'active']

            closed = closed_signals
            wins = len([s for s in closed if (s.get('pnl_percent') or 0) > 0])
            
            # TP Hit tracking
            tp1_hits = sum(1 for s in signals if s.get('tp1_hit'))
            tp2_hits = sum(1 for s in signals if s.get('tp2_hit'))
            tp3_hits = sum(1 for s in signals if s.get('tp3_hit'))
            breakeven_moves = sum(1 for s in signals if s.get('stop_moved_to_breakeven'))
            
            # Entry type breakdown
            limit_count = sum(1 for s in approved if s.get('is_limit_order'))
            market_count = len(approved) - limit_count
            
            # Setup type breakdown
            setup_types = {}
            for s in approved:
                st = s.get('setup_type', 'unknown')
                setup_types[st] = setup_types.get(st, 0) + 1
            
            # Close reason breakdown
            manual_closes = sum(1 for s in closed if 'manual' in (s.get('cancellation_reason') or ''))
            tp_closes = sum(1 for s in closed if 'tp' in (s.get('cancellation_reason') or ''))
            sl_closes = sum(1 for s in closed if 'sl' in (s.get('cancellation_reason') or ''))
            
            return {
                'date': start.strftime('%Y-%m-%d'),
                'total_scanned': len(signals),
                'approved': len(approved),
                'rejected': len(rejected),
                'active': len(active),
                'closed': len(closed),
                'wins': wins,
                'losses': len(closed) - wins,
                'win_rate': (wins / len(closed) * 100) if closed else 0,
                'total_pnl': sum((s.get('pnl_percent') or 0) for s in closed),
                'avg_confidence': sum((s.get('confidence') or 0) for s in approved) / len(approved) if approved else 0,
                # TP/SL tracking
                'tp1_hits': tp1_hits,
                'tp2_hits': tp2_hits,
                'tp3_hits': tp3_hits,
                'total_tp_hits': tp1_hits + tp2_hits + tp3_hits,
                'breakeven_moves': breakeven_moves,
                # Entry types
                'limit_orders': limit_count,
                'market_orders': market_count,
                # Setup types
                'setup_types': setup_types,
                # Close reasons
                'manual_closes': manual_closes,
                'tp_closes': tp_closes,
                'sl_closes': sl_closes
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
            
            # Build minimal data with only guaranteed columns
            minimal_data = {
                'user_id': data.get('user_id') or user_id,
                'username': data.get('username') or username,
                'tier': data.get('tier') or tier or 'monthly'
            }
            
            # Try to add optional fields if they exist
            for field in ['subscribed_at', 'status', 'notes', 'trial_ends_at', 
                          'telegram_user_id', 'created_at', 'stripe_customer_id']:
                if field in data and data[field] is not None:
                    minimal_data[field] = data[field]
            
            # Add defaults
            if 'subscribed_at' not in minimal_data:
                minimal_data['subscribed_at'] = datetime.utcnow().isoformat()
            if 'status' not in minimal_data:
                minimal_data['status'] = 'active'
            
            # Remove legacy field if present
            minimal_data.pop('active', None)
            
            # Try to save - if columns missing, Supabase will ignore unknown fields if we use the right approach
            try:
                self.client.table('subscribers').upsert(minimal_data).execute()
                logger.info(f"Subscriber {minimal_data.get('username', user_id)} saved/updated")
                return True
            except Exception as schema_error:
                # Fallback: save with only guaranteed columns
                if 'PGRST204' in str(schema_error):
                    logger.warning(f"Column missing, saving with core fields only")
                    core_data = {
                        'user_id': minimal_data.get('user_id'),
                        'username': minimal_data.get('username'),
                        'tier': minimal_data.get('tier', 'monthly')
                    }
                    if minimal_data.get('subscribed_at'):
                        core_data['subscribed_at'] = minimal_data['subscribed_at']
                    
                    self.client.table('subscribers').upsert(core_data).execute()
                    logger.info(f"Subscriber saved with core fields")
                    return True
                raise
            
        except Exception as e:
            error_msg = str(e)
            if 'PGRST204' in error_msg or 'does not exist' in error_msg:
                logger.error(f"❌ SUBSCRIBERS TABLE BROKEN: {error_msg}")
                logger.error("👉 Run this SQL in Supabase to fix: migrations/create_subscribers_table.sql")
            else:
                logger.error(f"Error saving subscriber: {e}")
            return False
    
    async def get_active_subscribers(self, tier: str = None) -> List[Dict]:
        try:
            query = self.client.table('subscribers').select('*')
            
            # Try filtering by status, fall back to all if column missing
            try:
                query = query.eq('status', 'active')
            except Exception:
                pass  # status column may not exist
            
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
            update_data = {}
            
            # Try to update status if column exists
            try:
                self.client.table('subscribers').update({'status': 'cancelled'}).eq('user_id', user_id).execute()
                update_data['status'] = 'cancelled'
            except Exception:
                # status column may not exist, try deleting instead
                try:
                    self.client.table('subscribers').delete().eq('user_id', user_id).execute()
                    logger.info(f"Subscriber {user_id} deleted (no status column)")
                    return True
                except Exception:
                    pass
            
            # Try to add cancelled_at
            if update_data:
                update_data['cancelled_at'] = datetime.utcnow().isoformat()
                self.client.table('subscribers').update(update_data).eq('user_id', user_id).execute()
            
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
                                   tp_level: int = None,
                                   max_drawdown: float = None,
                                   max_adverse: float = None,
                                   max_favorable: float = None,
                                   duration_minutes: float = None,
                                   entry_slippage: float = None,
                                   exit_slippage: float = None) -> bool:
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
            if max_drawdown is not None:
                data['max_drawdown_percent'] = max_drawdown
            if max_adverse is not None:
                data['max_adverse_excursion'] = max_adverse
            if max_favorable is not None:
                data['max_favorable_excursion'] = max_favorable
            if duration_minutes is not None:
                data['duration_minutes'] = duration_minutes
            if entry_slippage is not None:
                data['entry_slippage_percent'] = entry_slippage
            if exit_slippage is not None:
                data['exit_slippage_percent'] = exit_slippage
            
            self.client.table('signals').update(data).eq('id', signal_id).execute()
            logger.info(f"Signal {signal_id} result updated: {status.value} P&L={pnl_percent:+.2f}%")
            return True
        except Exception as e:
            error_str = str(e)
            # Handle missing columns by stripping them and retrying in a loop
            max_retries = 5
            retry_count = 0
            while "Could not find" in error_str and "column" in error_str and retry_count < max_retries:
                import re
                col_match = re.search(r"'([^']+)'\s+column", error_str)
                if col_match:
                    missing_col = col_match.group(1)
                    if missing_col in data:
                        logger.warning(f"DB column '{missing_col}' not found — removing from update data and retrying")
                        data.pop(missing_col)
                        try:
                            self.client.table('signals').update(data).eq('id', signal_id).execute()
                            logger.info(f"Signal {signal_id} result updated after stripping missing columns")
                            return True
                        except Exception as e2:
                            error_str = str(e2)
                            retry_count += 1
                            continue
                    else:
                        logger.warning(f"DB reports missing column '{missing_col}' but it's not in our update data")
                        break
                else:
                    logger.warning(f"Could not parse missing column from error: {error_str}")
                    break
            logger.error(f"Error updating signal result: {error_str}")
            return False
    
    async def get_trials_expiring_soon(self, days: int = 2) -> List[Dict]:
        """Get trials that expire in N days (for reminder)"""
        try:
            from datetime import timedelta
            now = datetime.utcnow()
            expiry_window = now + timedelta(days=days)
            
            result = self.client.table('subscribers').select('*')\
                .eq('tier', 'trial')\
                .eq('status', 'active')\
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
                .eq('status', 'active')\
                .lt('trial_ends_at', now.isoformat())\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Error getting expired trials: {e}")
            return []
    
    def _dict_to_signal(self, data: Dict) -> TradingSignal:
        from src.models.signal import TechnicalScore, ContextScore, SignalDirection, SetupType, MarketType
        
        def _parse_dt(key):
            val = data.get(key)
            if not val:
                return None
            try:
                # Handle timestamps with varying microsecond precision
                if isinstance(val, str):
                    # Remove timezone info and standardize format
                    val = val.replace('+00:00', '').replace('Z', '')
                    # Handle fractional seconds with any precision
                    if '.' in val:
                        parts = val.split('.')
                        # Pad or truncate to 6 digits
                        microseconds = parts[1][:6].ljust(6, '0')
                        val = f"{parts[0]}.{microseconds}"
                return datetime.fromisoformat(val)
            except Exception as e:
                logger.warning(f"Could not parse datetime for key '{key}': {val} - {e}")
                return None
        
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
        
        # Parse market_type, default to CRYPTO for backward compatibility
        market_type_str = data.get('market_type', 'crypto')
        try:
            market_type = MarketType(market_type_str)
        except ValueError:
            market_type = MarketType.CRYPTO
        
        return TradingSignal(
            id=_safe(data.get('id'), str(uuid.uuid4())),
            symbol=_safe(data.get('symbol'), 'UNKNOWN'),
            direction=SignalDirection(_safe(data.get('direction'), 'LONG')),
            setup_type=SetupType(_safe(data.get('setup_type'), 'support_resistance')),
            timeframe=_safe(data.get('timeframe'), '1h'),
            market_type=market_type,
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
            is_limit_order=data.get('is_limit_order', False),
            chart_url=data.get('chart_url'),
            chart_path=data.get('chart_path'),
            metadata=data.get('metadata'),
        )

    # ==================== ALPHA/DEGEN PLAYS ====================

    def _serialize_for_json(self, obj):
        """Helper to serialize dataclasses/datetimes/Decimals for JSON storage."""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for k in obj.__dataclass_fields__:
                v = getattr(obj, k)
                result[k] = self._serialize_for_json(v)
            return result
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, list):
            return [self._serialize_for_json(i) for i in obj]
        if isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        return obj
    
    def _json_default(self, obj):
        """Fallback JSON serializer for edge cases."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    async def save_alpha_play(self, play_data) -> bool:
        """Save an alpha play to the database. Accepts dict or ActiveAlphaPlay dataclass."""
        try:
            # Helper to safely get value from dict or dataclass (with nested candidate fallback)
            def _get(field, default=None):
                if isinstance(play_data, dict):
                    return play_data.get(field, default)
                val = getattr(play_data, field, None)
                if val is not None:
                    return val
                candidate = getattr(play_data, 'candidate', None)
                if candidate is not None:
                    return getattr(candidate, field, default)
                return default

            # VALIDATION: reject corrupted plays before writing to DB
            entry_price = _get('entry_price')
            stop_loss = _get('stop_loss')
            symbol = _get('symbol')
            if not symbol:
                logger.warning("⚠️ Skipping save_alpha_play: missing symbol")
                return False
            if (entry_price is None or entry_price <= 0) and (stop_loss is None or stop_loss <= 0):
                logger.warning(f"⚠️ Skipping save_alpha_play for {symbol}: entry_price={entry_price}, stop_loss={stop_loss} — corrupted data")
                return False
            
            # Serialize full candidate as JSON for reconstruction on restart
            # Also embed play-level metadata (approved_at, closed_at, etc.) since
            # some DB schemas don't have these as top-level columns
            import json
            candidate = _get('candidate')
            candidate_dict = None
            if candidate is not None:
                candidate_dict = self._serialize_for_json(candidate)
            elif isinstance(play_data, dict) and 'candidate_data' in play_data:
                cd = play_data['candidate_data']
                candidate_dict = json.loads(cd) if isinstance(cd, str) else cd
            
            # Embed play metadata into candidate_data so we don't need extra DB columns
            if candidate_dict is not None:
                play_meta = {}
                for meta_field in ['approved_at', 'closed_at', 'tp1_hit_at', 'tp2_hit_at', 'sl_hit_at',
                                    'entry_price', 'stop_loss', 'take_profit_1', 'take_profit_2',
                                    'position_size', 'current_price', 'current_pnl',
                                    'vip_message_id', 'free_message_id', 'notes', 'is_limit_order', 'actual_entry',
                                    'entry_liquidity', 'highest_price', 'trailing_stop_pct',
                                    'time_stop_hours', 'partial_sell_1_done', 'partial_sell_2_done',
                                    'is_degen']:
                    mv = _get(meta_field)
                    if mv is not None:
                        if isinstance(mv, datetime):
                            play_meta[meta_field] = mv.isoformat()
                        elif isinstance(mv, Decimal):
                            play_meta[meta_field] = float(mv)
                        else:
                            play_meta[meta_field] = mv
                if play_meta:
                    candidate_dict['__play_meta__'] = play_meta
                candidate_data = json.dumps(candidate_dict, default=self._json_default)
            else:
                candidate_data = None
            
            # Only use top-level columns that exist in the DB schema.
            # Everything else lives inside candidate_data JSONB.
            raw_data = {
                'id': _get('id', str(uuid.uuid4())),
                'symbol': _get('symbol'),
                'name': _get('name'),
                'chain': _get('chain'),
                'play_type': 'alpha',
                'status': _get('status', 'active'),
                'entry_price': _get('entry_price'),
                'stop_loss': _get('stop_loss'),
                'take_profit_1': _get('take_profit_1'),
                'take_profit_2': _get('take_profit_2'),
                'current_price': _get('current_price'),
                'current_pnl': _get('current_pnl'),
                'position_size': _get('position_size'),
                'approved_at': _get('approved_at'),
                'tp1_hit_at': _get('tp1_hit_at'),
                'tp2_hit_at': _get('tp2_hit_at'),
                'sl_hit_at': _get('sl_hit_at'),
                'closed_at': _get('closed_at'),
                'created_at': _get('created_at') or datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
            }
            
            # Deep serialize and strip None values
            def _deep_serialize(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, Decimal):
                    return float(obj)
                if isinstance(obj, list):
                    return [_deep_serialize(i) for i in obj]
                if isinstance(obj, dict):
                    return {k: _deep_serialize(v) for k, v in obj.items()}
                return obj
            
            data = {}
            for k, v in raw_data.items():
                sv = _deep_serialize(v)
                if sv is not None:
                    data[k] = sv
            
            # Always include candidate_data (JSONB) — holds ALL extra fields
            if candidate_data:
                data['candidate_data'] = candidate_data
            
            logger.info(f"💾 Saving alpha play {data.get('symbol')} (id={data.get('id', 'no-id')[:8]}...) status={data.get('status')}")
            self.client.table('alpha_plays').upsert(data).execute()
            logger.info(f"✅ Alpha play {data.get('symbol')} saved to database")
            return True
            
        except Exception as e:
            err_str = str(e).lower()
            # If ANY column is missing, fallback to minimal safe fields
            if 'column' in err_str or 'pgrst204' in err_str:
                logger.warning(f"DB column error ({e}) — retrying with minimal fields")
                # Retry 1: safe fields only, but ALWAYS include candidate_data so __play_meta__ survives
                try:
                    minimal = {
                        'id': data.get('id', str(uuid.uuid4())),
                        'symbol': data.get('symbol'),
                        'name': data.get('name'),
                        'status': data.get('status', 'active'),
                        'created_at': data.get('created_at', datetime.utcnow().isoformat()),
                    }
                    # Strip None values, but keep candidate_data (JSONB blob with embedded metadata)
                    minimal = {k: v for k, v in minimal.items() if v is not None}
                    if candidate_data:
                        minimal['candidate_data'] = candidate_data
                    self.client.table('alpha_plays').upsert(minimal).execute()
                    logger.info(f"✅ Alpha play {minimal.get('symbol')} saved with safe fields + candidate_data")
                    return True
                except Exception as e2:
                    err2 = str(e2).lower()
                    # Retry 2: ultra-minimal — only guaranteed columns, but still preserve candidate_data
                    if 'column' in err2 or 'pgrst204' in err2:
                        try:
                            ultra = {
                                'id': data.get('id', str(uuid.uuid4())),
                                'symbol': data.get('symbol'),
                                'status': data.get('status', 'active'),
                            }
                            ultra = {k: v for k, v in ultra.items() if v is not None}
                            if candidate_data:
                                ultra['candidate_data'] = candidate_data
                            self.client.table('alpha_plays').upsert(ultra).execute()
                            logger.info(f"✅ Alpha play {ultra.get('symbol')} saved with ultra-minimal fields + candidate_data")
                            return True
                        except Exception as e3:
                            logger.error(f"Error saving alpha play (ultra-minimal retry): {e3}")
                    else:
                        logger.error(f"Error saving alpha play (minimal retry): {e2}")
            else:
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

    # ============== TRADE AUDIT LOG ==============

    async def log_trade_event(self, signal_id: str, event_type: str, details: dict,
                               price: float = None, pnl: float = None) -> bool:
        """Write an immutable audit entry for a signal lifecycle event."""
        try:
            data = {
                'signal_id': signal_id,
                'event_type': event_type,
                'details': details,
                'price': price,
                'pnl': pnl,
                'timestamp': datetime.utcnow().isoformat(),
            }
            self.client.table('trade_audit_log').insert(data).execute()
            return True
        except Exception as e:
            logger.debug(f"Audit log failed: {e}")
            return False

    # ============== RESEARCH ENGINE ==============
    
    async def save_research_project(self, project: dict) -> bool:
        """Save or update a research project"""
        try:
            self.client.table('research_projects').upsert(project).execute()
            logger.info(f"✅ Research project {project.get('symbol')} saved")
            return True
        except Exception as e:
            logger.error(f"Error saving research project: {e}")
            return False
    
    async def get_research_project(self, project_id: str) -> Optional[Dict]:
        """Get a single research project by ID"""
        try:
            result = self.client.table('research_projects').select('*').eq('id', project_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting research project: {e}")
            return None
    
    async def get_all_research_projects(self, status: str = None, limit: int = 100) -> List[Dict]:
        """Get all research projects with optional status filter"""
        try:
            query = self.client.table('research_projects').select('*').order('conviction_score', desc=True).limit(limit)
            if status:
                query = query.eq('status', status)
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting research projects: {e}")
            return []
    
    async def update_research_project(self, project_id: str, updates: dict) -> bool:
        """Update a research project"""
        try:
            self.client.table('research_projects').update(updates).eq('id', project_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating research project: {e}")
            return False
    
    async def save_conviction_score(self, score: dict) -> bool:
        """Save conviction score history"""
        try:
            self.client.table('conviction_history').insert(score).execute()
            return True
        except Exception as e:
            logger.error(f"Error saving conviction score: {e}")
            return False
    
    async def get_conviction_history(self, project_id: str, days: int = 30) -> List[Dict]:
        """Get conviction score history for a project"""
        try:
            from datetime import timedelta
            start_date = datetime.utcnow() - timedelta(days=days)
            result = self.client.table('conviction_history').select('*')\
                .eq('project_id', project_id)\
                .gte('recorded_at', start_date.isoformat())\
                .order('recorded_at', desc=True)\
                .execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting conviction history: {e}")
            return []
    
    async def get_alpha_basket(self) -> List[Dict]:
        """Get current alpha basket"""
        try:
            result = self.client.table('alpha_basket').select('*')\
                .eq('status', 'active')\
                .order('rank')\
                .execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting alpha basket: {e}")
            return []
    
    async def add_to_basket(self, basket_entry: dict) -> bool:
        """Add project to alpha basket"""
        try:
            self.client.table('alpha_basket').upsert(basket_entry).execute()
            return True
        except Exception as e:
            logger.error(f"Error adding to basket: {e}")
            return False
    
    async def remove_from_basket(self, project_id: str, reason: str = "") -> bool:
        """Remove project from alpha basket"""
        try:
            self.client.table('alpha_basket').update({
                'status': 'removed',
                'removed_at': datetime.utcnow().isoformat(),
                'removal_reason': reason
            }).eq('project_id', project_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error removing from basket: {e}")
            return False
    
    async def save_research_report(self, report: dict) -> bool:
        """Save a research report"""
        try:
            self.client.table('research_reports').insert(report).execute()
            logger.info(f"✅ Research report saved: {report.get('title')}")
            return True
        except Exception as e:
            logger.error(f"Error saving research report: {e}")
            return False
    
    async def get_research_reports(self, project_id: str = None, limit: int = 50) -> List[Dict]:
        """Get research reports"""
        try:
            query = self.client.table('research_reports').select('*').order('generated_at', desc=True).limit(limit)
            if project_id:
                query = query.eq('project_id', project_id)
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting research reports: {e}")
            return []

    async def get_signal_audit(self, signal_id: str) -> List[Dict]:
        """Get full audit trail for a single signal."""
        try:
            result = self.client.table('trade_audit_log').select('*')\
                .eq('signal_id', signal_id)\
                .order('timestamp')\
                .execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Could not get audit trail: {e}")
            return []

    async def get_recent_audit(self, event_type: str = None, limit: int = 100) -> List[Dict]:
        """Get recent audit entries, optionally filtered by event type."""
        try:
            query = self.client.table('trade_audit_log').select('*')\
                .order('timestamp', desc=True)\
                .limit(limit)
            if event_type:
                query = query.eq('event_type', event_type)
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Could not get recent audit: {e}")
            return []

    # ============== SETUP PERFORMANCE TRACKING ==============

    async def get_closed_signals_for_analytics(self, days: int = 30) -> List[Dict]:
        """Get closed signals with analytics fields for portfolio metrics."""
        try:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()
            result = self.client.table('signals').select('*')\
                .in_('status', ['closed', 'stopped', 'target_hit'])\
                .gte('closed_at', since)\
                .execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Could not get closed signals for analytics: {e}")
            return []

    async def record_setup_performance(self, signal: TradingSignal) -> bool:
        """Record a signal's outcome for setup type performance tracking."""
        try:
            data = {
                'signal_id': signal.id,
                'setup_type': signal.setup_type.value if hasattr(signal.setup_type, 'value') else str(signal.setup_type),
                'timeframe': signal.timeframe,
                'grade': signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade),
                'direction': signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
                'confidence': signal.confidence,
                'risk_reward': signal.risk_reward,
                'entry_price': signal.entry_price,
                'actual_entry': signal.actual_entry,
                'actual_exit': signal.actual_exit,
                'pnl_percent': signal.pnl_percent,
                'tp1_hit': signal.tp1_hit,
                'tp2_hit': signal.tp2_hit,
                'tp3_hit': signal.tp3_hit,
                'stop_hit': signal.stop_hit,
                'created_at': signal.created_at.isoformat() if signal.created_at else datetime.utcnow().isoformat(),
                'closed_at': signal.closed_at.isoformat() if signal.closed_at else None,
            }
            self.client.table('setup_performance').insert(data).execute()
            return True
        except Exception as e:
            logger.warning(f"Could not record setup performance: {e}")
            return False

    async def get_setup_performance(self, setup_type: str, timeframe: str = None, days: int = 30) -> Dict:
        """Get performance stats for a specific setup type."""
        try:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()
            query = self.client.table('setup_performance').select('*')\
                .eq('setup_type', setup_type)\
                .gte('created_at', since)

            if timeframe:
                query = query.eq('timeframe', timeframe)

            result = query.execute()
            rows = result.data or []

            if not rows:
                return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'avg_pnl': 0}

            total = len(rows)
            wins = sum(1 for r in rows if (r.get('pnl_percent') or 0) > 0)
            losses = total - wins
            pnls = [r.get('pnl_percent', 0) or 0 for r in rows]
            avg_pnl = sum(pnls) / len(pnls) if pnls else 0

            return {
                'total': total,
                'wins': wins,
                'losses': losses,
                'win_rate': (wins / total) * 100 if total > 0 else 0,
                'avg_pnl': avg_pnl,
                'best': max(pnls) if pnls else 0,
                'worst': min(pnls) if pnls else 0,
            }
        except Exception as e:
            logger.warning(f"Could not get setup performance: {e}")
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'avg_pnl': 0}
