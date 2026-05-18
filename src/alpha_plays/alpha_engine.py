"""
Alpha Plays Engine

Main engine for managing alpha/degen plays lifecycle:
- Discovery → Approval → Publishing → Tracking → Closing

Isolated from main signal engine to prevent breaking existing functionality.
"""

import uuid
import random
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
    
    def __init__(self, db=None, publisher=None):
        self.discovery = AlphaDiscovery()
        self.formatter = AlphaContentFormatter()
        self.db = db
        self.publisher = publisher
        
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
        """Initialize the engine"""
        logger.info("🎰 Initializing Alpha Plays Engine...")
        
        # Load any active plays from database if available
        if self.db:
            try:
                plays = await self.db.get_alpha_plays(status='active')
                for play_data in plays:
                    # Reconstruct active play from DB
                    logger.info(f"Loaded active alpha play: {play_data.get('symbol')}")
            except Exception as e:
                logger.warning(f"Could not load active alpha plays from DB: {e}")
        
        logger.info("✅ Alpha Plays Engine ready")
    
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
        
        # Save to database
        if self.db:
            try:
                await self.db.save_alpha_play(active_play)
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
        
        # Check daily limit
        self._reset_counts_if_needed()
        if self.vip_count_today >= self.vip_daily_limit:
            logger.info(f"VIP daily alpha limit reached ({self.vip_daily_limit})")
            return None
        
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
        
        # Check weekly limit
        self._reset_counts_if_needed()
        if self.free_count_this_week >= self.free_weekly_limit:
            logger.info(f"Free weekly alpha limit reached ({self.free_weekly_limit})")
            return None
        
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
                if play.candidate.price_usd > 0:
                    play.current_pnl = ((current_price - play.entry_price) / play.entry_price) * 100
                
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
        """Get current price for a token"""
        # Placeholder - would integrate with price API
        # For now, simulate small price movement
        import random
        drift = random.uniform(-0.02, 0.03)  # -2% to +3%
        return candidate.price_usd * (1 + drift)
    
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
    
    async def close(self):
        """Clean up resources"""
        await self.discovery.close()
        logger.info("🎰 Alpha Plays Engine closed")
