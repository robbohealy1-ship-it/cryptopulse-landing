"""
Alpha Plays Engine

Main engine for managing alpha/degen plays lifecycle:
- Discovery → Approval → Publishing → Tracking → Closing

Isolated from main signal engine to prevent breaking existing functionality.

ENHANCED: Now creates research projects for investment intelligence tracking.
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
    is_limit_order: bool = False  # market vs limit entry
    actual_entry: float = 0.0  # filled price for limit orders
    notes: str = ""
    
    # Degen strategy fields
    entry_liquidity: float = 0.0  # Snapshot of liquidity at entry (for rug protection)
    highest_price: float = 0.0  # Track peak for trailing stop
    trailing_stop_pct: float = 20.0  # % below peak to trigger trailing stop
    time_stop_hours: float = 48.0  # Close if no momentum after X hours
    partial_sell_1_done: bool = False  # Sold 50% at 2x
    partial_sell_2_done: bool = False  # Sold 25% at 5x
    is_degen: bool = False  # Use degen strategy (no hard SL, trailing stop, partial sells)
    _dirty: bool = False  # True when structural change requires DB persistence

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
    
    def __init__(self, db=None, publisher=None, admin_notification=None, admin_bot=None):
        self.discovery = AlphaDiscovery()
        self.formatter = AlphaContentFormatter()
        self.db = db
        self.publisher = publisher
        self._notify_admin = admin_notification
        self._admin_bot = admin_bot
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Research Engine Integration (lazy init to avoid circular imports)
        self.research_project_db = None
        self.conviction_engine = None
        self.basket_manager = None
        self.report_generator = None
        
        # Active plays being tracked
        self.active_plays: Dict[str, ActiveAlphaPlay] = {}
        
        # Pending plays awaiting approval
        self.pending_plays: Dict[str, AlphaPlayCandidate] = {}
        
        # Pending alpha limit orders (waiting for entry price hit)
        self.pending_alpha_limits: Dict[str, ActiveAlphaPlay] = {}
        # Track price extremes for pending alpha limits so brief touches aren't missed
        self.pending_alpha_extremes: Dict[str, dict] = {}  # play_id -> {'lowest': float, 'highest': float}
        
        # Portfolio holds (long-term 1-4 week alpha positions, no auto-close on TP/SL)
        self.portfolio_holds: Dict[str, ActiveAlphaPlay] = {}
        
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
    
    def _looks_like_address_fragment(self, symbol: str) -> bool:
        """Detect if a symbol is actually an address prefix (e.g. '0X829F', 'AV8TVX')."""
        if not symbol or symbol == 'UNKNOWN':
            return True
        # Address fragments are typically 5-7 chars, all uppercase, with numbers
        if len(symbol) >= 5 and len(symbol) <= 7 and symbol.isupper():
            # Check if it contains digits (real token symbols rarely do)
            has_digits = any(c.isdigit() for c in symbol)
            if has_digits:
                return True
        # Very short all-caps with digits is likely an address
        return False
    
    async def _enrich_token_info(self, candidate: AlphaPlayCandidate) -> bool:
        """Try to fetch real token name/symbol from DEXScreener by token_address."""
        if not candidate.token_address or not self.session:
            return False
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{candidate.token_address}"
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        best = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                        base = best.get('baseToken', {})
                        quote = best.get('quoteToken', {})
                        # Update symbol/name from live data
                        new_symbol = (base.get('symbol', '') or quote.get('symbol', '') or '').strip()
                        new_name = (base.get('name', '') or quote.get('name', '') or '').strip()
                        if new_symbol and new_symbol != candidate.symbol:
                            candidate.symbol = new_symbol
                            logger.info(f"🔄 Enriched symbol for {candidate.token_address[:8]}... -> {new_symbol}")
                        if new_name and new_name != candidate.name:
                            candidate.name = new_name
                            logger.info(f"🔄 Enriched name for {candidate.token_address[:8]}... -> {new_name}")
                        # Also refresh pair_address
                        if best.get('pairAddress') and not candidate.pair_address:
                            candidate.pair_address = best.get('pairAddress')
                        return True
        except Exception as e:
            logger.debug(f"Token enrichment failed for {candidate.token_address[:8]}...: {e}")
        return False
    
    async def initialize(self):
        """Initialize the engine and reload persisted active and pending plays from DB."""
        logger.info("🎰 Initializing Alpha Plays Engine...")
        
        # Initialize Research Engine components
        if self.db and not self.research_project_db:
            try:
                from src.research.conviction_engine import ConvictionEngine
                from src.research.project_database import ProjectDatabase
                from src.research.basket_manager import BasketManager
                from src.research.report_generator import ReportGenerator
                
                self.conviction_engine = ConvictionEngine(self.db)
                self.research_project_db = ProjectDatabase(self.db, self.conviction_engine)
                self.basket_manager = BasketManager(self.db)
                self.report_generator = ReportGenerator(self.db)
                logger.info("✅ Research Engine initialized")
            except Exception as e:
                logger.warning(f"Research Engine init failed (non-critical): {e}")
        
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
                seen_symbols = set()
                for play_data in plays:
                    play = self._reconstruct_active_play(play_data)
                    if not play:
                        logger.warning(f"⚠️ Failed to reconstruct active play from DB row: {play_data.get('symbol', 'unknown')}")
                        continue
                    # Skip corrupted plays with no valid entry/SL
                    if play.entry_price <= 0 and play.stop_loss <= 0 and play.take_profit_1 <= 0:
                        logger.warning(f"⚠️ Skipping corrupted alpha play from DB: {play.candidate.symbol} (entry={play.entry_price}, sl={play.stop_loss}) — missing trade parameters")
                        continue
                    # Deduplicate by symbol
                    if play.candidate.symbol in seen_symbols:
                        logger.warning(f"⚠️ Skipping duplicate alpha play from DB: {play.candidate.symbol} (id={play.id[:8]}...)")
                        continue
                    seen_symbols.add(play.candidate.symbol)
                    self.active_plays[play.id] = play
                    restored += 1
                    logger.info(f"🔁 Restored active alpha play from DB: {play.candidate.symbol} (id={play.id[:8]}...)")
                logger.info(f"🔁 Restored {restored}/{len(plays)} active alpha plays from DB")
                
                # Re-enrich token info for plays with address-fragment symbols
                enriched_count = 0
                for play in self.active_plays.values():
                    if self._looks_like_address_fragment(play.candidate.symbol) and play.candidate.token_address:
                        if await self._enrich_token_info(play.candidate):
                            enriched_count += 1
                            # Save updated play to DB
                            try:
                                await self._persist_play(play)
                            except Exception:
                                pass
                if enriched_count > 0:
                    logger.info(f"🔄 Re-enriched {enriched_count} alpha play symbol(s) from live data")
                
                # Clean up corrupted legacy plays that have no real data
                cleaned = 0
                for play_id, play in list(self.active_plays.items()):
                    is_bad_symbol = self._looks_like_address_fragment(play.candidate.symbol)
                    has_no_token = not play.candidate.token_address
                    has_no_entry = play.entry_price == 0
                    has_no_prices = play.entry_price == 0 and play.stop_loss == 0 and play.take_profit_1 == 0
                    
                    if (is_bad_symbol and has_no_token) or (has_no_entry and has_no_token) or has_no_prices:
                        logger.warning(f"🗑️ Removing corrupted legacy play {play.candidate.symbol} (no token/entry data) — discovered before fixes")
                        del self.active_plays[play_id]
                        cleaned += 1
                        # Mark as corrupted in DB
                        if self.db:
                            try:
                                await self.db.save_alpha_play({
                                    'id': play_id,
                                    'status': 'corrupted',
                                    'symbol': play.candidate.symbol,
                                    'candidate_data': None,
                                    'candidate': play.candidate,
                                })
                            except Exception:
                                pass
                if cleaned > 0:
                    logger.info(f"🗑️ Cleaned up {cleaned} corrupted legacy alpha play(s)")
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
            
            # Load portfolio holds
            try:
                portfolio = await self.db.get_alpha_plays(status='portfolio_hold', limit=50)
                restored_portfolio = 0
                for p in portfolio:
                    play = self._reconstruct_active_play(p)
                    if play:
                        self.portfolio_holds[play.id] = play
                        restored_portfolio += 1
                logger.info(f"🔁 Restored {restored_portfolio} portfolio holds from DB")
            except Exception as e:
                logger.warning(f"Could not load portfolio holds from DB: {e}")
        else:
            logger.warning("🎰 No DB configured — alpha plays will NOT persist across restarts")
        
        logger.info(f"✅ Alpha Plays Engine ready — {len(self.active_plays)} active, {len(self.pending_plays)} pending, {len(self.portfolio_holds)} portfolio")
    
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
                    v = data.get(field)
                if v is None:
                    v = default
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
                is_limit_order=_meta_or_data('is_limit_order', False, bool),
                actual_entry=_meta_or_data('actual_entry', 0.0, float),
                entry_liquidity=_meta_or_data('entry_liquidity', 0.0, float),
                highest_price=_meta_or_data('highest_price', 0.0, float),
                trailing_stop_pct=_meta_or_data('trailing_stop_pct', 20.0, float),
                time_stop_hours=_meta_or_data('time_stop_hours', 48.0, float),
                partial_sell_1_done=_meta_or_data('partial_sell_1_done', False, bool),
                partial_sell_2_done=_meta_or_data('partial_sell_2_done', False, bool),
                is_degen=_meta_or_data('is_degen', False, bool),
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
            # Create research project for investment tracking
            if self.research_project_db:
                try:
                    project = await self.research_project_db.create_from_alpha_candidate(candidate)
                    if project:
                        logger.info(f"📊 Research project created: {candidate.symbol} (Conviction: {project.conviction_score:.1f}/100)")
                except Exception as e:
                    logger.warning(f"Could not create research project for {candidate.symbol}: {e}")
            
            # Auto-approve if score is very high and auto-approve is enabled
            if self.auto_approve and candidate.overall_score >= 85:
                logger.info(f"🤖 Auto-approving high-score alpha: {candidate.symbol} ({candidate.overall_score:.1f})")
                approved_candidates.append(candidate)
            else:
                # Add to pending queue
                self.pending_plays[candidate.symbol] = candidate
                logger.info(f"⏳ Alpha play pending approval: {candidate.symbol} (Score: {candidate.overall_score:.1f})")
                # Notify admin via Telegram with interactive buttons when possible
                if self._admin_bot and hasattr(self._admin_bot, 'send_alpha_for_approval'):
                    try:
                        await self._admin_bot.send_alpha_for_approval(candidate)
                    except Exception as e:
                        logger.warning(f"Could not send alpha approval UI: {e}")
                elif self._notify_admin:
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
    
    async def approve_alpha_play(self, symbol: str, admin_notes: str = "", is_limit_order: bool = False) -> Optional[ActiveAlphaPlay]:
        """Alias for approve_play for backward compatibility."""
        return await self.approve_play(symbol, admin_notes, is_limit_order)
    
    async def approve_play(self, symbol: str, admin_notes: str = "", is_limit_order: bool = False) -> Optional[ActiveAlphaPlay]:
        """
        Admin approves an alpha play from the pending queue.
        
        Args:
            symbol: Token symbol to approve
            admin_notes: Optional notes from admin
            is_limit_order: If True, track as limit order and wait for entry price hit
        
        Returns:
            ActiveAlphaPlay if approved, None if not found
        """
        # Find in pending
        candidate = self.pending_plays.pop(symbol, None)
        
        if not candidate:
            logger.warning(f"Alpha play {symbol} not found in pending queue")
            return None
        
        # Refresh price BEFORE generating trade parameters to avoid stale prices
        fresh_data = await self._get_price_and_liquidity(candidate)
        if fresh_data and fresh_data.get('price'):
            candidate.price_usd = fresh_data['price']
            candidate.liquidity_usd = fresh_data.get('liquidity', candidate.liquidity_usd)
            logger.info(f"🔄 Refreshed price for {symbol}: ${candidate.price_usd:.6f}")
        
        # Generate trade parameters
        entry, sl, tp1, tp2 = self._generate_trade_parameters(candidate)
        
        # Determine strategy
        is_degen = candidate.risk_level == 'degen'
        
        # Create active play
        active_play = ActiveAlphaPlay(
            id=str(uuid.uuid4()),
            candidate=candidate,
            entry_price=entry,
            stop_loss=sl if not is_degen else 0.0,  # No hard SL for degen
            take_profit_1=tp1 if not is_degen else entry * 2.0,  # Degen: 2x for 50% sell
            take_profit_2=tp2 if not is_degen else entry * 5.0,  # Degen: 5x for 25% sell
            position_size=self._get_position_size(candidate),
            notes=admin_notes,
            approved_at=datetime.utcnow(),
            is_degen=is_degen,
            is_limit_order=is_limit_order,
            entry_liquidity=candidate.liquidity_usd,
            highest_price=entry,  # Start tracking from entry
            trailing_stop_pct=20.0 if is_degen else 0.0,
            time_stop_hours=48.0 if is_degen else 0.0
        )
        
        if is_limit_order:
            # For limit orders: add to pending, not active. Wait for price hit.
            self.pending_alpha_limits[active_play.id] = active_play
            self.pending_alpha_extremes[active_play.id] = {'lowest': float('inf'), 'highest': 0.0}
            logger.info(f"⏳ Alpha limit order pending for {symbol} at ${entry:.6f} — will track when limit is hit")
            
            # Save to DB as pending limit
            if self.db:
                try:
                    active_play.status = 'pending_limit'
                    await self.db.save_alpha_play(active_play)
                except Exception as e:
                    logger.warning(f"Could not save pending alpha limit to DB: {e}")
            
            return active_play
        
        # Route to appropriate tracking bucket
        if candidate.trade_type == 'portfolio':
            self.portfolio_holds[active_play.id] = active_play
            active_play.status = 'portfolio_hold'
            logger.info(f"💼 Portfolio hold approved: {symbol} | Entry: ${entry:.6f} | 1-4 week hold")
        else:
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
        
        strategy_label = "DEGEN" if is_degen else "STANDARD"
        logger.info(f"✅ Alpha {strategy_label} approved: {symbol} | Entry: ${entry:.6f} | TP1: ${active_play.take_profit_1:.6f} | TP2: ${active_play.take_profit_2:.6f} | SL: {f'${sl:.6f}' if sl > 0 else 'NONE (rug protect)'}")
        
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
                position_size=play.position_size,
                is_limit_order=play.is_limit_order,
                is_degen=play.is_degen
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
        """Save play state to DB only if it has structural changes (_dirty=True)."""
        if not self.db:
            return
        if not getattr(play, '_dirty', False):
            return
        try:
            await self.db.save_alpha_play(play)
            play._dirty = False
        except Exception as e:
            logger.warning(f"Could not persist alpha play to DB: {e}")
    
    async def _check_alpha_limit_hit(self, play_id: str):
        """Check if an alpha limit order's entry price has been hit."""
        play = self.pending_alpha_limits.get(play_id)
        if not play:
            return
        
        try:
            data = await self._get_price_and_liquidity(play.candidate)
            if not data:
                return
            current_price = data['price']
        except Exception:
            return
        
        entry = play.entry_price
        
        # Update extremes tracking
        extremes = self.pending_alpha_extremes.get(play_id, {'lowest': float('inf'), 'highest': 0.0})
        extremes['lowest'] = min(extremes['lowest'], current_price)
        extremes['highest'] = max(extremes['highest'], current_price)
        self.pending_alpha_extremes[play_id] = extremes
        
        # Alpha plays are always LONG (buy low, sell high)
        # For limit order: price must drop to or below entry
        hit = (current_price <= entry) or (extremes['lowest'] <= entry)
        
        if hit:
            del self.pending_alpha_limits[play_id]
            self.pending_alpha_extremes.pop(play_id, None)
            play.actual_entry = current_price
            
            if play.candidate.trade_type == 'portfolio':
                play.status = 'portfolio_hold'
                self.portfolio_holds[play_id] = play
                logger.info(f"💼 Portfolio limit filled for {play.candidate.symbol} at ${current_price:.6f}")
            else:
                play.status = 'active'
                self.active_plays[play_id] = play
            
            if current_price > entry:
                logger.info(f"🎯 Alpha limit hit for {play.candidate.symbol} at ${current_price:.6f} (was briefly at ${extremes['lowest']:.6f} ≤ entry ${entry:.6f}) — tracking started")
            else:
                logger.info(f"🎯 Alpha limit hit for {play.candidate.symbol} at ${current_price:.6f} — tracking started")
            
            # Notify VIP channel
            if self.publisher and hasattr(self.publisher, 'bot') and self.publisher.bot:
                try:
                    from src.config import settings
                    msg = (
                        f"🎯 <b>ALPHA LIMIT ORDER FILLED</b>\n\n"
                        f"{play.candidate.symbol} ({play.candidate.chain.upper()})\n"
                        f"Entry: ${current_price:.6f}\n"
                        f"TP1: ${play.take_profit_1:.6f}\n"
                        f"TP2: ${play.take_profit_2:.6f}\n\n"
                        f"📊 Now tracking TP/SL automatically"
                    )
                    await self.publisher.bot.send_message(
                        chat_id=self.publisher.vip_channel_id,
                        text=msg,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.warning(f"Could not send alpha limit fill VIP notification: {e}")
            
            # Save to DB
            play._dirty = True
            if self.db:
                try:
                    await self.db.save_alpha_play(play)
                except Exception as e:
                    logger.warning(f"Could not save limit-hit alpha play to DB: {e}")
    
    async def track_active_plays(self):
        """
        Check all active alpha plays for TP/SL/rug/time hits.
        Also checks pending alpha limit orders for entry hits.
        Called periodically (every 5 minutes).
        """
        # Check pending alpha limit orders first
        if self.pending_alpha_limits:
            for play_id in list(self.pending_alpha_limits.keys()):
                await self._check_alpha_limit_hit(play_id)
        
        if not self.active_plays:
            return
        
        logger.info(f"📊 Tracking {len(self.active_plays)} active alpha plays...")
        
        for play_id, play in list(self.active_plays.items()):
            try:
                # Fetch price + liquidity + volume from DEXScreener
                data = await self._get_price_and_liquidity(play.candidate)
                if not data:
                    continue
                
                current_price = data.get('price')
                current_liquidity = data.get('liquidity')
                current_volume = data.get('volume_24h', 0)
                current_market_cap = data.get('market_cap', 0)
                
                if current_price is None or current_price <= 0:
                    logger.warning(f"Skipping {play.candidate.symbol}: invalid price {current_price}")
                    continue
                
                # Update ALL live data (not just price)
                play.current_price = current_price
                play.candidate.liquidity_usd = current_liquidity if current_liquidity else play.candidate.liquidity_usd
                play.candidate.volume_24h = current_volume if current_volume else play.candidate.volume_24h
                play.candidate.market_cap_usd = current_market_cap if current_market_cap else play.candidate.market_cap_usd
                
                # Calculate P&L
                if play.entry_price and play.entry_price > 0:
                    play.current_pnl = ((current_price - play.entry_price) / play.entry_price) * 100
                
                # Track highest price for trailing stop
                if play.highest_price is None or current_price > play.highest_price:
                    play.highest_price = current_price
                
                # ─── RUG PROTECTION (all plays) ───
                entry_liq = play.entry_liquidity or 0
                curr_liq = current_liquidity or 0
                if entry_liq > 0 and curr_liq > 0:
                    liquidity_ratio = curr_liq / entry_liq
                    if liquidity_ratio < 0.5:
                        await self._close_play(play, 'RUG_PULL',
                            f"🚨 <b>RUG PROTECTION TRIGGERED</b>\n\n"
                            f"<b>{play.candidate.symbol}</b> liquidity dropped {((1-liquidity_ratio)*100):.0f}%\n"
                            f"Entry liq: ${entry_liq:,.0f}\n"
                            f"Current liq: ${curr_liq:,.0f}\n"
                            f"Position closed to protect capital.")
                        continue
                
                # ─── TIME STOP (degen only) ───
                time_stop = play.time_stop_hours or 0
                if play.is_degen and time_stop > 0 and play.approved_at:
                    hours_elapsed = (datetime.utcnow() - play.approved_at).total_seconds() / 3600
                    if hours_elapsed >= time_stop:
                        await self._close_play(play, 'TIME_STOP',
                            f"⏰ <b>TIME STOP</b>\n\n"
                            f"<b>{play.candidate.symbol}</b> held for {hours_elapsed:.0f}h with no breakout.\n"
                            f"Final P&L: {play.current_pnl:+.1f}%\n"
                            f"Position closed.")
                        continue
                
                if play.is_degen:
                    # ─── DEGEN STRATEGY ───
                    # TP1: +100% (2x) → sell 50%
                    tp1 = play.take_profit_1 or 0
                    if not play.partial_sell_1_done and tp1 > 0:
                        if current_price >= tp1:
                            play.partial_sell_1_done = True
                            play._dirty = True
                            await self._persist_play(play)
                            await self._notify_partial_sell(play, 1, 50, "2x")
                    
                    # TP2: +400% (5x) → sell 25%
                    tp2 = play.take_profit_2 or 0
                    if not play.partial_sell_2_done and play.partial_sell_1_done and tp2 > 0:
                        if current_price >= tp2:
                            play.partial_sell_2_done = True
                            play._dirty = True
                            await self._persist_play(play)
                            await self._notify_partial_sell(play, 2, 25, "5x")
                    
                    # Trailing stop: after TP2, if price drops trailing_stop_pct% from peak
                    trailing_pct = play.trailing_stop_pct or 0
                    hp = play.highest_price or 0
                    if play.partial_sell_2_done and hp > 0 and trailing_pct > 0:
                        trailing_level = hp * (1 - trailing_pct / 100)
                        if current_price <= trailing_level:
                            await self._close_play(play, 'TRAILING_STOP',
                                f"🎯 <b>TRAILING STOP HIT</b>\n\n"
                                f"<b>{play.candidate.symbol}</b> pulled back {play.trailing_stop_pct:.0f}% from peak\n"
                                f"Peak: ${play.highest_price:.6f}\n"
                                f"Exit: ${current_price:.6f}\n"
                                f"Final P&L: {play.current_pnl:+.1f}%\n"
                                f"Remaining 25% position closed. Let the runners run!")
                            continue
                else:
                    # ─── STANDARD STRATEGY (non-degen) ───
                    tp1_std = play.take_profit_1 or 0
                    if play.status == 'active' and tp1_std > 0:
                        if current_price >= tp1_std:
                            await self._handle_tp1_hit(play)
                    
                    tp2_std = play.take_profit_2 or 0
                    if play.status == 'tp1_hit' and tp2_std > 0:
                        if current_price >= tp2_std:
                            await self._handle_tp2_hit(play)
                    
                    sl = play.stop_loss or 0
                    if play.status in ['active', 'tp1_hit'] and sl > 0:
                        if current_price <= sl:
                            await self._handle_sl_hit(play)
                
            except Exception as e:
                logger.error(f"Error tracking alpha play {play_id}: {e}")
    
    async def track_portfolio_holds(self):
        """
        Track portfolio holds (long-term 1-4 week positions).
        Updates price and P&L but does NOT auto-close on TP/SL.
        Called periodically (every 5 minutes alongside track_active_plays).
        """
        if not self.portfolio_holds:
            return
        
        logger.info(f"💼 Tracking {len(self.portfolio_holds)} portfolio holds...")
        
        for play_id, play in list(self.portfolio_holds.items()):
            try:
                data = await self._get_price_and_liquidity(play.candidate)
                if not data:
                    continue
                
                current_price = data.get('price')
                if current_price is None or current_price <= 0:
                    continue
                
                # Update ALL live data
                play.current_price = current_price
                play.candidate.liquidity_usd = data.get('liquidity', play.candidate.liquidity_usd)
                play.candidate.volume_24h = data.get('volume_24h', play.candidate.volume_24h)
                play.candidate.market_cap_usd = data.get('market_cap', play.candidate.market_cap_usd)
                
                # Calculate P&L
                entry = play.actual_entry or play.entry_price
                if entry and entry > 0:
                    play.current_pnl = ((current_price - entry) / entry) * 100
                
                # Track highest price for peak reference
                if play.highest_price is None or current_price > play.highest_price:
                    play.highest_price = current_price
                
                # Persist every cycle
                await self._persist_play(play)
                
            except Exception as e:
                logger.error(f"Error tracking portfolio hold {play_id}: {e}")
    
    async def _notify_partial_sell(self, play: ActiveAlphaPlay, tp_num: int, pct_sold: int, multiplier: str):
        """Notify VIP about a partial sell on a degen play."""
        logger.info(f"🎯 Alpha DEGEN TP{tp_num} ({multiplier}): {play.candidate.symbol} — sold {pct_sold}% at +{play.current_pnl:.1f}%")
        if self.publisher:
            await self.publisher.send_alpha_update(
                play,
                f"🎯 <b>DEGEN TP{tp_num} HIT ({multiplier})</b>\n\n"
                f"<b>{play.candidate.symbol}</b> at ${play.current_price:.6f}\n"
                f"P&L: +{play.current_pnl:.1f}%\n\n"
                f"� <b>Sold {pct_sold}% of position</b>\n"
                f"Remaining: {100 - (50 if tp_num == 1 else 75)}% riding\n\n"
                f"{'Next: 5x target for 25% sell' if tp_num == 1 else 'Trailing stop active on final 25%'}")
    
    async def _close_play(self, play: ActiveAlphaPlay, reason_code: str, vip_message: str):
        """Generic close with VIP notification."""
        play.status = reason_code.lower()
        play.closed_at = datetime.utcnow()
        play._dirty = True
        await self._persist_play(play)
        self.active_plays.pop(play.id, None)
        
        logger.info(f"📕 Alpha {reason_code}: {play.candidate.symbol} at ${play.current_price:.6f} ({play.current_pnl:.1f}%)")
        
        if self.publisher:
            await self.publisher.publish_alpha_result_vip(vip_message)
    
    async def _handle_tp1_hit(self, play: ActiveAlphaPlay):
        """Handle TP1 hit (standard non-degen plays only)"""
        play.status = 'tp1_hit'
        play.tp1_hit_at = datetime.utcnow()
        play._dirty = True
        await self._persist_play(play)
        
        logger.info(f"🎯 Alpha TP1 HIT: {play.candidate.symbol} at ${play.current_price:.6f}")
        
        if self.publisher:
            await self.publisher.send_alpha_update(
                play,
                f"🎯 <b>TP1 HIT!</b>\n\n{play.candidate.symbol} reached ${play.take_profit_1:.6f}\n"
                f"P&L: +{play.current_pnl:.1f}%\n\n💎 Move SL to breakeven?"
            )
    
    async def _handle_tp2_hit(self, play: ActiveAlphaPlay):
        """Handle TP2 hit (standard non-degen plays only)"""
        await self._close_play(play, 'TP2_HIT',
            f"🎉 <b>MAX PROFIT</b>\n\n"
            f"<b>{play.candidate.symbol}</b> hit TP2 at ${play.take_profit_2:.6f}\n"
            f"Final P&L: {play.current_pnl:+.1f}%\n\n"
            f"🎯 Full position closed.")
        
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
        """Handle SL hit (standard non-degen plays only)"""
        await self._close_play(play, 'SL_HIT',
            f"🛑 <b>STOP LOSS HIT</b>\n\n"
            f"<b>{play.candidate.symbol}</b> hit SL at ${play.stop_loss:.6f}\n"
            f"Final P&L: {play.current_pnl:+.1f}%\n\n"
            f"Position closed. On to the next alpha.")
    
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
    
    async def _get_price_and_liquidity(self, candidate: AlphaPlayCandidate) -> Optional[dict]:
        """Fetch current price AND liquidity from DEXScreener API."""
        # Recreate session if closed/missing
        if not self.session or self.session.closed:
            try:
                self.session = aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(limit=5, limit_per_host=3),
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                logger.info("🔄 AlphaPlays: recreated aiohttp session")
            except Exception as e:
                logger.error(f"Failed to recreate alpha session: {e}")
                return None
        
        token_addr = candidate.token_address
        pair_addr = candidate.pair_address
        chain = candidate.chain
        symbol = candidate.symbol
        
        urls = []
        if token_addr:
            urls.append(f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}")
        if pair_addr and chain:
            urls.append(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_addr}")
        
        # Fallback: search by symbol if no addresses available
        if not urls and symbol and symbol != 'UNKNOWN':
            urls.append(f"https://api.dexscreener.com/latest/dex/search?q={symbol}")
        
        if not urls:
            logger.warning(f"No token/pair address or symbol for candidate, cannot fetch price")
            return None
        
        for url in urls:
            try:
                async with self.session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])
                        if pairs:
                            best = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                            price = float(best.get('priceUsd', 0) or 0)
                            liquidity = float(best.get('liquidity', {}).get('usd', 0) or 0)
                            volume_24h = float(best.get('volume', {}).get('h24', 0) or 0)
                            fdv = float(best.get('fdv', 0) or 0)
                            market_cap = float(best.get('marketCap', 0) or 0)
                            
                            # If market cap not provided, use FDV as fallback
                            if market_cap == 0 and fdv > 0:
                                market_cap = fdv
                            
                            if price > 0:
                                # If we searched by symbol, verify the symbol matches
                                if 'search?q=' in url:
                                    base_sym = (best.get('baseToken', {}).get('symbol', '') or '').upper()
                                    quote_sym = (best.get('quoteToken', {}).get('symbol', '') or '').upper()
                                    if symbol.upper() not in [base_sym, quote_sym]:
                                        logger.debug(f"Symbol mismatch: searched {symbol}, got {base_sym}/{quote_sym}")
                                        continue
                                return {
                                    'price': price,
                                    'liquidity': liquidity,
                                    'volume_24h': volume_24h,
                                    'market_cap': market_cap,
                                    'fdv': fdv,
                                    'dex_id': best.get('dexId', ''),
                                    'pair_address': best.get('pairAddress', '')
                                }
                    else:
                        logger.debug(f"DEXScreener returned {resp.status} for {candidate.symbol}")
            except Exception as e:
                logger.debug(f"Price fetch failed for {candidate.symbol} via {url}: {e}")
                continue
        
        logger.warning(f"Could not fetch current price for {candidate.symbol} from DEXScreener")
        return None
    
    async def _get_current_price(self, candidate: AlphaPlayCandidate) -> Optional[float]:
        """Legacy convenience method - returns just price."""
        result = await self._get_price_and_liquidity(candidate)
        return result['price'] if result else None
    
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
            pnl = play.current_pnl if play.current_pnl is not None else 0.0
            entry_price = play.entry_price if play.entry_price is not None else 0.0
            exit_price = play.current_price if play.current_price is not None else entry_price
            await self.publisher.publish_alpha_result_vip(
                f"📕 <b>Alpha Play Closed</b>\n\n"
                f"<b>{play.candidate.symbol}</b> manually closed by admin.\n"
                f"Reason: {reason}\n"
                f"Final P&L: {pnl:+.1f}%\n\n"
                f"Entry: ${entry_price:.6f}\n"
                f"Exit:  ${exit_price:.6f}"
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
        allowed_fields = ['entry_price', 'stop_loss', 'take_profit_1', 'take_profit_2', 'position_size', 'is_limit_order']
        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                try:
                    if field == 'position_size':
                        setattr(play, field, str(updates[field]))
                    elif field == 'is_limit_order':
                        setattr(play, field, bool(updates[field]))
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
