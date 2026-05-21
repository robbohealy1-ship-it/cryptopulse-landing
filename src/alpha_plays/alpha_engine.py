"""
Alpha Plays Engine

Main engine for managing alpha/degen plays lifecycle:
- Discovery → Approval → Publishing → Tracking → Closing

Isolated from main signal engine to prevent breaking existing functionality.
"""

import uuid
import aiohttp
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from src.utils.logger import get_logger
from src.config import settings
from .alpha_discovery import AlphaDiscovery, AlphaPlayCandidate
from .content_formatter import AlphaContentFormatter

logger = get_logger(__name__)


@dataclass
class ActiveAlphaPlay:
    """An alpha play that has been approved and is being tracked"""
    id: str
    candidate: AlphaPlayCandidate
    status: str = 'active'  # 'active', 'tp1_hit', 'tp2_hit', 'sl_hit', 'closed'
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    position_size: str = "2-5%"
    approved_at: datetime = None
    tp1_hit_at: Optional[datetime] = None
    tp2_hit_at: Optional[datetime] = None
    sl_hit_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    vip_message_id: Optional[int] = None
    free_message_id: Optional[int] = None
    current_price: float = 0.0
    current_pnl: float = 0.0
    notes: str = ""
    
    def __post_init__(self):
        if self.approved_at is None:
            self.approved_at = datetime.utcnow()
        if not self.id:
            self.id = str(uuid.uuid4())


class AlphaPlaysEngine:
    """
    Main engine for alpha/degen plays.
    
    Flow:
    1. discover() - Find candidates via AlphaDiscovery
    2. evaluate() - Score and filter candidates
    3. approve() - Admin approves (or auto-approve if confidence high)
    4. publish() - Send to VIP and/or Free channels
    5. track() - Monitor price and check TP/SL
    6. close() - Mark as closed and send result
    """
    
    def __init__(self, db=None, publisher=None, admin_notification=None):
        self.discovery = AlphaDiscovery()
        self.formatter = AlphaContentFormatter()
        self.db = db
        self.publisher = publisher
        self._notify_admin = admin_notification
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Active plays being tracked
        self.active_plays: Dict[str, ActiveAlphaPlay] = {}
        
        # Pending plays awaiting approval
        self.pending_plays: Dict[str, AlphaPlayCandidate] = {}
        
        # Settings
        self.min_alpha_score = getattr(settings, 'ALPHA_MIN_SCORE', 70.0)
        self.auto_approve = getattr(settings, 'ALPHA_AUTO_APPROVE', False)
        self.vip_daily_limit = getattr(settings, 'ALPHA_VIP_DAILY_LIMIT', 1)
        self.free_weekly_limit = getattr(settings, 'ALPHA_FREE_WEEKLY_LIMIT', 1)
        
        # Track daily/weekly counts
        self.vip_count_today = 0
        self.free_count_this_week = 0
        self.last_vip_reset = datetime.utcnow().date()
        self.last_free_reset = datetime.utcnow().date()
        
        logger.info("🎰 Alpha Plays Engine initialized")
    
    async def initialize(self):
        """Initialize the engine and reload persisted active and pending plays from DB."""
        logger.info("🎰 Initializing Alpha Plays Engine...")
        
        # Create aiohttp session for price fetching
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=5, limit_per_host=3),
                timeout=aiohttp.ClientTimeout(total=15)
            )
        
        if self.db:
            # Load active plays
            try:
                plays = await self.db.get_alpha_plays(status='active')
                logger.info(f"🎰 DB returned {len(plays)} active alpha play rows")
                restored = 0
                for play_data in plays:
                    play = self._reconstruct_active_play(play_data)
                    if play:
                        self.active_plays[play.id] = play
                        restored += 1
                        logger.info(f"🔁 Restored active alpha play from DB: {play.candidate.symbol} (id={play.id[:8]}...)")
                    else:
                        logger.warning(f"⚠️ Failed to reconstruct active play from DB row: {play_data.get('symbol', 'unknown')} (id={play_data.get('id', 'no-id')[:8] if play_data.get('id') else 'no-id'})")
                logger.info(f"🔁 Restored {restored}/{len(plays)} active alpha plays from DB")
            except Exception as e:
                logger.warning(f"Could not load active alpha plays from DB: {e}")
            
            # Load pending plays
            try:
                pending = await self.db.get_alpha_plays(status='pending')
                logger.info(f"🎰 DB returned {len(pending)} pending alpha play rows")
                restored_pending = 0
                for p in pending:
                    candidate = self._reconstruct_pending_candidate(p)
                    if candidate:
                        self.pending_plays[candidate.symbol] = candidate
                        restored_pending += 1
                        logger.info(f"🔁 Restored pending alpha play from DB: {candidate.symbol}")
                    else:
                        logger.warning(f"⚠️ Failed to reconstruct pending play from DB row: {p.get('symbol', 'unknown')}")
                logger.info(f"🔁 Restored {restored_pending}/{len(pending)} pending alpha plays from DB")
            except Exception as e:
                logger.warning(f"Could not load pending alpha plays from DB: {e}")
        else:
            logger.warning("🎰 No DB configured — alpha plays will NOT persist across restarts")
        
        logger.info(f"✅ Alpha Plays Engine ready — {len(self.active_plays)} active, {len(self.pending_plays)} pending")
    
    def _reconstruct_active_play(self, data: dict) -> Optional[ActiveAlphaPlay]:
        """Reconstruct an ActiveAlphaPlay from a DB dict row."""
        try:
            import json
            
            # Build candidate from JSON blob if available, else from individual fields
            candidate_data = data.get('candidate_data')
            if candidate_data:
                if isinstance(candidate_data, str):
                    c = json.loads(candidate_data)
                else:
                    c = candidate_data
            else:
                c = data
            
            candidate = AlphaPlayCandidate(
                symbol=c.get('symbol', 'UNKNOWN'),
                name=c.get('name', c.get('symbol', 'UNKNOWN')),
                chain=c.get('chain', 'sol'),
                token_address=c.get('token_address'),
                pair_address=c.get('pair_address'),
                price_usd=float(c.get('price_usd', 0) or 0),
                market_cap_usd=float(c.get('market_cap', 0) or 0),
                liquidity_usd=float(c.get('liquidity_usd', 0) or 0),
                volume_24h=float(c.get('volume_24h', 0) or 0),
                price_change_24h=float(c.get('price_change_24h', 0) or 0),
                price_change_1h=float(c.get('price_change_1h', 0) or 0),
                holders=int(c.get('holders', 0) or 0),
                transactions_24h=int(c.get('transactions_24h', 0) or 0),
                social_score=float(c.get('social_score', 0) or 0),
                community_score=float(c.get('community_score', 0) or 0),
                technical_score=float(c.get('technical_score', 0) or 0),
                fundamental_score=float(c.get('fundamental_score', 0) or 0),
                overall_score=float(c.get('overall_score', 0) or 0),
                dex_url=c.get('dex_url', ''),
                chart_url=c.get('chart_url', ''),
                buy_url=c.get('buy_url', ''),
                price_change_5min=float(c.get('price_change_5min', 0) or 0),
                buys_24h=int(c.get('buys_24h', 0) or 0),
                sells_24h=int(c.get('sells_24h', 0) or 0),
                description=c.get('description', ''),
                red_flags=c.get('red_flags', []),
                catalyst=c.get('catalyst', ''),
                trade_type=c.get('trade_type', ''),
                time_frame=c.get('time_frame', ''),
                holder_growth_24h=float(c.get('holder_growth_24h', 0) or 0),
                liquidity_growth_24h=float(c.get('liquidity_growth_24h', 0) or 0),
                volume_growth_24h=float(c.get('volume_growth_24h', 0) or 0),
                top_holder_concentration=float(c.get('top_holder_concentration', 0) or 0),
                buy_sell_ratio=float(c.get('buy_sell_ratio', 1) or 1),
                fdv=float(c.get('fdv', 0) or 0),
                circulating_supply=float(c.get('circulating_supply', 0) or 0),
                total_supply=float(c.get('total_supply', 0) or 0),
                narrative=c.get('narrative', ''),
                why_trending=c.get('why_trending', ''),
                short_term_potential=c.get('short_term_potential', ''),
                long_term_potential=c.get('long_term_potential', ''),
                risk_level=c.get('risk_level', 'medium'),
                dex_source=c.get('dex_source', ''),
            )
            
            # Extract embedded play metadata from candidate_data (new schema) or top-level cols (old schema)
            play_meta = c.pop('__play_meta__', {}) if isinstance(c, dict) else {}
            
            def _meta_or_data(field, default=None, cast=None):
                """Get value from __play_meta__ first, then top-level DB row, then default."""
                v = play_meta.get(field)
                if v is None:
                    v = data.get(field, default)
                if v is not None and cast:
                    try:
                        v = cast(v)
                    except (ValueError, TypeError):
                        v = default
                return v
            
            play = ActiveAlphaPlay(
                id=data.get('id', str(uuid.uuid4())),
                candidate=candidate,
                status=data.get('status', 'active'),
                entry_price=_meta_or_data('entry_price', 0.0, float),
                stop_loss=_meta_or_data('stop_loss', 0.0, float),
                take_profit_1=_meta_or_data('take_profit_1', 0.0, float),
                take_profit_2=_meta_or_data('take_profit_2', 0.0, float),
                position_size=_meta_or_data('position_size', '2-5%'),
                current_price=_meta_or_data('current_price', 0.0, float),
                current_pnl=_meta_or_data('current_pnl', 0.0, float),
                vip_message_id=_meta_or_data('vip_message_id'),
                free_message_id=_meta_or_data('free_message_id'),
                notes=_meta_or_data('notes', ''),
            )
            
            # Parse timestamps from __play_meta__ or top-level columns
            for attr in ['approved_at', 'tp1_hit_at', 'tp2_hit_at', 'sl_hit_at', 'closed_at']:
                val = play_meta.get(attr) if play_meta else data.get(attr)
                if val:
                    try:
                        if isinstance(val, datetime):
                            setattr(play, attr, val)
                        elif isinstance(val, str):
                            setattr(play, attr, datetime.fromisoformat(val.replace('Z', '+00:00')))
                    except (ValueError, AttributeError, TypeError):
                        pass
            
            return play
        except Exception as e:
            logger.error(f"Error reconstructing alpha play from DB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _reconstruct_pending_candidate(self, data: dict) -> Optional[AlphaPlayCandidate]:
        """Reconstruct an AlphaPlayCandidate from a DB dict row (status='pending')."""
        try:
            import json
            c = data.get('candidate_data')
            if c:
                if isinstance(c, str):
                    c = json.loads(c)
            else:
                c = data
            return AlphaPlayCandidate(
                symbol=c.get('symbol', data.get('symbol', 'UNKNOWN')),
                name=c.get('name', data.get('name', c.get('symbol', 'UNKNOWN'))),
                chain=c.get('chain', data.get('chain', 'sol')),
                token_address=c.get('token_address', data.get('token_address')),
                pair_address=c.get('pair_address', data.get('pair_address')),
                price_usd=float(c.get('price_usd', data.get('price_usd', 0)) or 0),
                market_cap_usd=float(c.get('market_cap', data.get('market_cap_usd', data.get('market_cap', 0))) or 0),
                liquidity_usd=float(c.get('liquidity_usd', data.get('liquidity_usd', 0)) or 0),
                volume_24h=float(c.get('volume_24h', data.get('volume_24h', 0)) or 0),
                price_change_24h=float(c.get('price_change_24h', data.get('price_change_24h', 0)) or 0),
                price_change_1h=float(c.get('price_change_1h', data.get('price_change_1h', 0)) or 0),
                holders=int(c.get('holders', data.get('holders', 0)) or 0),
                transactions_24h=int(c.get('transactions_24h', data.get('transactions_24h', 0)) or 0),
                social_score=float(c.get('social_score', data.get('social_score', 0)) or 0),
                community_score=float(c.get('community_score', data.get('community_score', 0)) or 0),
                technical_score=float(c.get('technical_score', data.get('technical_score', 0)) or 0),
                fundamental_score=float(c.get('fundamental_score', data.get('fundamental_score', 0)) or 0),
                overall_score=float(c.get('overall_score', data.get('overall_score', 0)) or 0),
                dex_url=c.get('dex_url', data.get('dex_url', '')),
                chart_url=c.get('chart_url', data.get('chart_url', '')),
                buy_url=c.get('buy_url', data.get('buy_url', '')),
                price_change_5min=float(c.get('price_change_5min', data.get('price_change_5min', 0)) or 0),
                buys_24h=int(c.get('buys_24h', data.get('buys_24h', 0)) or 0),
                sells_24h=int(c.get('sells_24h', data.get('sells_24h', 0)) or 0),
                description=c.get('description', data.get('description', '')),
                red_flags=c.get('red_flags', data.get('red_flags')) or [],
                catalyst=c.get('catalyst', data.get('catalyst', '')),
                trade_type=c.get('trade_type', data.get('trade_type', '')),
                time_frame=c.get('time_frame', data.get('time_frame', '')),
                holder_growth_24h=float(c.get('holder_growth_24h', data.get('holder_growth_24h', 0)) or 0),
                liquidity_growth_24h=float(c.get('liquidity_growth_24h', data.get('liquidity_growth_24h', 0)) or 0),
                volume_growth_24h=float(c.get('volume_growth_24h', data.get('volume_growth_24h', 0)) or 0),
                top_holder_concentration=float(c.get('top_holder_concentration', data.get('top_holder_concentration', 0)) or 0),
                buy_sell_ratio=float(c.get('buy_sell_ratio', data.get('buy_sell_ratio', 1)) or 1),
                fdv=float(c.get('fdv', data.get('fdv', 0)) or 0),
                circulating_supply=float(c.get('circulating_supply', data.get('circulating_supply', 0)) or 0),
                total_supply=float(c.get('total_supply', data.get('total_supply', 0)) or 0),
                narrative=c.get('narrative', data.get('narrative', '')),
                why_trending=c.get('why_trending', data.get('why_trending', '')),
                short_term_potential=c.get('short_term_potential', data.get('short_term_potential', '')),
                long_term_potential=c.get('long_term_potential', data.get('long_term_potential', '')),
                risk_level=c.get('risk_level', data.get('risk_level', 'medium')),
                dex_source=c.get('dex_source', data.get('dex_source', '')),
            )
        except Exception as e:
            logger.error(f"Error reconstructing pending candidate from DB: {e}")
            return None
    
    async def discover_and_create(self, chain: str = None, 
                                  limit: int = 3) -> List[AlphaPlayCandidate]:
        """
        Discover alpha plays and prepare them for approval.
        
        Args:
            chain: 'sol', 'eth', 'base' or None for all
            limit: Max candidates to discover
        
        Returns:
            List of candidates ready for admin approval
        """
        logger.info(f"🔍 Alpha discovery started (chain={chain or 'all'})...")
        
        # Check rate limits
        self._reset_counts_if_needed()
        
        # Discover candidates
        candidates = await self.discovery.discover_alpha_plays(
            chain=chain,
            limit=limit
        )
        
        if not candidates:
            logger.info("No alpha candidates found this scan")
            return []
        
        # Add to pending for admin approval
        approved_candidates = []
        
        for candidate in candidates:
            # Auto-approve if score is very high and auto-approve is enabled
            if self.auto_approve and candidate.overall_score >= 85:
                logger.info(f"🤖 Auto-approving high-score alpha: {candidate.symbol} ({candidate.overall_score:.1f})")
                approved_candidates.append(candidate)
            else:
                # Add to pending queue
                self.pending_plays[candidate.symbol] = candidate
                logger.info(f"⏳ Alpha play pending approval: {candidate.symbol} (Score: {candidate.overall_score:.1f})")
                # Notify admin via Telegram
                if self._notify_admin:
                    try:
                        msg = (
                            f"🎰 <b>New Alpha Play Pending Approval</b>\n\n"
                            f"<b>{candidate.symbol}</b> ({candidate.chain.upper()})\n"
                            f"Type: {candidate.trade_type} | Risk: {candidate.risk_level}\n"
                            f"Score: {candidate.overall_score:.1f}/100\n"
                            f"Price: ${candidate.price_usd:.6f}\n"
                            f"Market Cap: ${candidate.market_cap_usd/1e6:.2f}M\n"
                            f"24h Change: {candidate.price_change_24h:+.1f}%\n\n"
                            f"Catalyst: {candidate.catalyst}\n\n"
                            f"👉 Approve from dashboard: /api/alpha/approve\n"
                            f"or go to Admin Dashboard → Alpha Plays"
                        )
                        await self._notify_admin(msg)
                    except Exception as e:
                        logger.warning(f"Could not send admin notification for alpha play: {e}")
                # Persist to DB so it survives restarts
                if self.db:
                    try:
                        await self.db.save_alpha_play({
                            'candidate': candidate,
                            'status': 'pending',
                            'symbol': candidate.symbol,
                        })
                    except Exception as e:
                        logger.warning(f"Could not save pending alpha play to DB: {e}")
        
        return approved_candidates
    
    async def approve_play(self, symbol: str, admin_notes: str = "") -> Optional[ActiveAlphaPlay]:
        """
        Admin approves an alpha play from the pending queue.
        
        Args:
            symbol: Token symbol to approve
            admin_notes: Optional notes from admin
        
        Returns:
            ActiveAlphaPlay if approved, None if not found
        """
        # Find in pending
        candidate = self.pending_plays.pop(symbol, None)
        
        if not candidate:
            logger.warning(f"Alpha play {symbol} not found in pending queue")
            return None
        
        # Generate trade parameters
        entry, sl, tp1, tp2 = self._generate_trade_parameters(candidate)
        
        # Create active play
        active_play = ActiveAlphaPlay(
            id=str(uuid.uuid4()),
            candidate=candidate,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            position_size=self._get_position_size(candidate),
            notes=admin_notes,
            approved_at=datetime.utcnow()
        )
        
        # Add to active tracking
        self.active_plays[active_play.id] = active_play
        
        # Save to database and clean up old pending rows for this symbol
        if self.db:
            try:
                await self.db.save_alpha_play(active_play)
                # Mark any old pending rows for this symbol as approved so they don't show again
                try:
                    self.db.client.table('alpha_plays').update({'status': 'approved'}).eq('symbol', symbol).eq('status', 'pending').execute()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Could not save alpha play to DB: {e}")
        
        logger.info(f"✅ Alpha play approved: {symbol} | Entry: ${entry:.6f} | SL: ${sl:.6f} | TP1: ${tp1:.6f} | TP2: ${tp2:.6f}")
        
        return active_play
    
    async def publish_to_vip(self, play: ActiveAlphaPlay) -> Optional[int]:
        """
        Publish a full alpha play to the VIP channel.
        
        Args:
            play: The active alpha play to publish
        
        Returns:
            Telegram message ID if published, None otherwise
        """
        if not self.publisher:
            logger.warning("No publisher configured for alpha plays")
            return None
        
        # Rate limits disabled — admin has full approve/reject control
        self._reset_counts_if_needed()
        
        try:
            # Format VIP message
            message = self.formatter.format_vip_alpha(
                play.candidate,
                entry_price=play.entry_price,
                stop_loss=play.stop_loss,
                take_profit_1=play.take_profit_1,
                take_profit_2=play.take_profit_2,
                position_size=play.position_size
            )
            
            # Publish
            message_id = await self.publisher.publish_alpha_vip(message)
            
            if message_id:
                play.vip_message_id = message_id
                self.vip_count_today += 1
                logger.info(f"📤 Published alpha play to VIP: {play.candidate.symbol} (Msg ID: {message_id})")
            
            return message_id
            
        except Exception as e:
            logger.error(f"Error publishing alpha to VIP: {e}")
            return None
    
    async def publish_teaser_to_free(self, play: ActiveAlphaPlay) -> Optional[int]:
        """
        Publish a teaser to the free channel.
        Free gets 1 per week.
        
        Args:
            play: The active alpha play
        
        Returns:
            Telegram message ID if published, None otherwise
        """
        if not self.publisher:
            logger.warning("No publisher configured for alpha plays")
            return None
        
        # Rate limits disabled — admin has full approve/reject control
        self._reset_counts_if_needed()
        
        try:
            # Format teaser
            message = self.formatter.format_free_alpha_teaser(play.candidate)
            
            # Publish
            message_id = await self.publisher.publish_alpha_free(message)
            
            if message_id:
                play.free_message_id = message_id
                self.free_count_this_week += 1
                logger.info(f"📤 Published alpha teaser to FREE: {play.candidate.symbol} (Msg ID: {message_id})")
            
            return message_id
            
        except Exception as e:
            logger.error(f"Error publishing alpha teaser to FREE: {e}")
            return None
    
    async def _persist_play(self, play: ActiveAlphaPlay):
        """Save play state to DB."""
        if self.db:
            try:
                await self.db.save_alpha_play(play)
            except Exception as e:
                logger.warning(f"Could not persist alpha play to DB: {e}")
    
    async def track_active_plays(self):
        """
        Check all active alpha plays for TP/SL hits.
        Called periodically (every 5 minutes).
        """
        if not self.active_plays:
            return
        
        logger.info(f"📊 Tracking {len(self.active_plays)} active alpha plays...")
        
        for play_id, play in list(self.active_plays.items()):
            try:
                # Get current price (would use price API)
                current_price = await self._get_current_price(play.candidate)
                
                if not current_price:
                    continue
                
                play.current_price = current_price
                
                # Calculate P&L
                if play.entry_price > 0:
                    play.current_pnl = ((current_price - play.entry_price) / play.entry_price) * 100
                
                # Persist current price/pnl every track cycle
                await self._persist_play(play)
                
                # Check TP1
                if play.status == 'active' and play.take_profit_1 > 0:
                    if current_price >= play.take_profit_1:
                        await self._handle_tp1_hit(play)
                
                # Check TP2
                if play.status == 'tp1_hit' and play.take_profit_2 > 0:
                    if current_price >= play.take_profit_2:
                        await self._handle_tp2_hit(play)
                
                # Check SL
                if play.status in ['active', 'tp1_hit'] and play.stop_loss > 0:
                    if current_price <= play.stop_loss:
                        await self._handle_sl_hit(play)
                
            except Exception as e:
                logger.error(f"Error tracking alpha play {play_id}: {e}")
    
    async def _handle_tp1_hit(self, play: ActiveAlphaPlay):
        """Handle TP1 hit"""
        play.status = 'tp1_hit'
        play.tp1_hit_at = datetime.utcnow()
        
        await self._persist_play(play)
        
        logger.info(f"🎯 Alpha TP1 HIT: {play.candidate.symbol} at ${play.current_price:.6f}")
        
        # Send VIP update
        if self.publisher:
            await self.publisher.send_alpha_update(
                play,
                f"🎯 <b>TP1 HIT!</b>\n\n{play.candidate.symbol} reached ${play.take_profit_1:.6f}\n"
                f"P&L: +{play.current_pnl:.1f}%\n\n💎 Move SL to breakeven?"
            )
    
    async def _handle_tp2_hit(self, play: ActiveAlphaPlay):
        """Handle TP2 hit (max profit)"""
        play.status = 'tp2_hit'
        play.tp2_hit_at = datetime.utcnow()
        play.closed_at = datetime.utcnow()
        
        await self._persist_play(play)
        
        # Move from active to closed
        self.active_plays.pop(play.id, None)
        
        logger.info(f"🎉 Alpha MAX PROFIT: {play.candidate.symbol} at ${play.current_price:.6f} (+{play.current_pnl:.1f}%)")
        
        # Send VIP result
        if self.publisher:
            message = self.formatter.format_alpha_result(
                play.candidate,
                play.current_pnl,
                play.current_price,
                'TP2_HIT'
            )
            await self.publisher.publish_alpha_result_vip(message)
        
        # Send free teaser result
        if self.publisher and play.free_message_id:
            await self.publisher.send_alpha_result_free(
                play,
                f"🎉 <b>{play.candidate.symbol} MAX PROFIT!</b>\n\n"
                f"VIP members banked +{play.current_pnl:.1f}% gains!\n\n"
                f"💎 Want alpha plays like this?\n"
                f"DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP access"
            )
    
    async def _handle_sl_hit(self, play: ActiveAlphaPlay):
        """Handle SL hit"""
        play.status = 'sl_hit'
        play.sl_hit_at = datetime.utcnow()
        play.closed_at = datetime.utcnow()
        
        await self._persist_play(play)
        
        # Move from active
        self.active_plays.pop(play.id, None)
        
        logger.info(f"🛑 Alpha SL HIT: {play.candidate.symbol} at ${play.current_price:.6f} ({play.current_pnl:.1f}%)")
        
        # Send VIP result
        if self.publisher:
            message = self.formatter.format_alpha_result(
                play.candidate,
                play.current_pnl,
                play.current_price,
                'SL_HIT'
            )
            await self.publisher.publish_alpha_result_vip(message)
    
    def _generate_trade_parameters(self, candidate: AlphaPlayCandidate) -> tuple:
        """
        Generate entry, SL, TP1, TP2 for an alpha play.
        More aggressive than standard signals due to high volatility.
        """
        price = candidate.price_usd
        
        # Entry: current price or slight discount
        entry = price * 0.98  # 2% below current for entry
        
        # SL: 15-25% below entry (wider for alpha plays)
        if candidate.market_cap_usd < 5_000_000:
            sl_pct = 0.25  # 25% for micro caps
        elif candidate.market_cap_usd < 20_000_000:
            sl_pct = 0.20  # 20% for small caps
        else:
            sl_pct = 0.15  # 15% for larger caps
        
        sl = entry * (1 - sl_pct)
        
        # TP1: 2x-3x risk (aggressive)
        risk = entry - sl
        tp1 = entry + (risk * 2.5)
        
        # TP2: 5x-10x risk (moonshot)
        tp2 = entry + (risk * 5.0)
        
        return entry, sl, tp1, tp2
    
    def _get_position_size(self, candidate: AlphaPlayCandidate) -> str:
        """Recommend position size based on risk"""
        if candidate.market_cap_usd < 5_000_000:
            return "1-2%"  # Very small for micro caps
        elif candidate.market_cap_usd < 20_000_000:
            return "2-3%"
        else:
            return "3-5%"
    
    async def _get_current_price(self, candidate: AlphaPlayCandidate) -> Optional[float]:
        """Fetch current price from DEXScreener API using token address or pair address."""
        if not self.session or self.session.closed:
            return None
        
        # Try token address first (most reliable)
        token_addr = candidate.token_address
        pair_addr = candidate.pair_address
        chain = candidate.chain
        
        # Endpoint priority: token address > pair address
        urls = []
        if token_addr:
            urls.append(f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}")
        if pair_addr and chain:
            urls.append(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_addr}")
        
        if not urls:
            logger.warning(f"No token/pair address for {candidate.symbol}, cannot fetch price")
            return None
        
        for url in urls:
            try:
                async with self.session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])
                        if pairs:
                            # Get the pair with highest liquidity
                            best = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                            price = float(best.get('priceUsd', 0) or 0)
                            if price > 0:
                                return price
            except Exception as e:
                logger.debug(f"Price fetch failed for {candidate.symbol} via {url}: {e}")
                continue
        
        logger.warning(f"Could not fetch current price for {candidate.symbol} from DEXScreener")
        return None
    
    def _reset_counts_if_needed(self):
        """Reset daily/weekly counters if needed"""
        today = datetime.utcnow().date()
        
        # Reset VIP daily count
        if today != self.last_vip_reset:
            self.vip_count_today = 0
            self.last_vip_reset = today
            logger.info("🔄 Reset VIP daily alpha count")
        
        # Reset free weekly count (on Monday)
        if today.weekday() == 0 and today != self.last_free_reset:
            self.free_count_this_week = 0
            self.last_free_reset = today
            logger.info("🔄 Reset free weekly alpha count")
    
    async def close_play(self, play_id: str, reason: str = "manual") -> bool:
        """Manually close an active alpha play (admin action)."""
        play = self.active_plays.get(play_id)
        if not play:
            logger.warning(f"Cannot close alpha play {play_id}: not found in active plays")
            return False
        
        play.status = 'closed'
        play.closed_at = datetime.utcnow()
        self.active_plays.pop(play_id, None)
        
        # Save to DB
        if self.db:
            try:
                await self.db.save_alpha_play(play)
            except Exception as e:
                logger.error(f"Error saving closed alpha play: {e}")
        
        # Notify VIP
        if self.publisher:
            await self.publisher.publish_alpha_result_vip(
                f"📕 <b>Alpha Play Closed</b>\n\n"
                f"<b>{play.candidate.symbol}</b> manually closed by admin.\n"
                f"Reason: {reason}\n"
                f"Final P&L: {play.current_pnl:+.1f}%\n\n"
                f"Entry: ${play.entry_price:.6f}\n"
                f"Exit:  ${play.current_price:.6f}"
            )
        
        logger.info(f"📕 Alpha play {play.candidate.symbol} manually closed by admin ({reason})")
        return True
    
    async def update_play(self, play_id: str, updates: dict) -> bool:
        """Update an active alpha play's parameters (admin edit)."""
        play = self.active_plays.get(play_id)
        if not play:
            logger.warning(f"Cannot update alpha play {play_id}: not found")
            return False
        
        # Update allowed fields
        allowed_fields = ['entry_price', 'stop_loss', 'take_profit_1', 'take_profit_2', 'position_size']
        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                try:
                    if field == 'position_size':
                        setattr(play, field, str(updates[field]))
                    else:
                        setattr(play, field, float(updates[field]))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid value for {field}: {updates[field]}")
        
        # Save to DB
        if self.db:
            try:
                await self.db.save_alpha_play(play)
            except Exception as e:
                logger.error(f"Error saving updated alpha play: {e}")
        
        logger.info(f"✏️ Alpha play {play.candidate.symbol} updated by admin: {list(updates.keys())}")
        return True
    
    async def close(self):
        """Clean up resources"""
        if self.session and not self.session.closed:
            await self.session.close()
        await self.discovery.close()
        logger.info("🎰 Alpha Plays Engine closed")
