import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import uuid
from collections import deque
from src.scanner.market_scanner import MarketScanner
from src.analysis.technical_analyzer import TechnicalAnalyzer
from src.analysis.institutional_analyzer import InstitutionalAnalyzer
from src.analysis.timeframe_strategies import TimeframeStrategyFactory
from src.analysis.enhanced_context_engine import EnhancedContextEngine as ContextEngine
from src.engine.signal_ranker import SignalRanker
from src.models.signal import (
    TradingSignal, SignalDirection, SetupType, SignalStatus
)
from src.config import settings
from src.utils.logger import get_logger
from src.utils.signal_validation_pipeline import SignalValidationPipeline
from src.conviction.conviction_engine import ConvictionEngine

logger = get_logger(__name__)

# Correlated pairs — skip duplicates to avoid double risk exposure
CORRELATION_GROUPS = {
    'BTCUSDT': ['ETHUSDT', 'BCHUSDT', 'LTCUSDT', 'ETCUSDT'],
    'ETHUSDT': ['BTCUSDT', 'SOLUSDT', 'AVAXUSDT', 'MATICUSDT', 'ARBUSDT'],
    'SOLUSDT': ['ETHUSDT', 'AVAXUSDT', 'FTMUSDT', 'NEARUSDT'],
    'AVAXUSDT': ['ETHUSDT', 'SOLUSDT', 'FTMUSDT', 'MATICUSDT'],
    'MATICUSDT': ['ETHUSDT', 'AVAXUSDT', 'ARBUSDT', 'OPUSDT'],
    'ARBUSDT': ['ETHUSDT', 'MATICUSDT', 'OPUSDT'],
    'DOGEUSDT': ['SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT'],
    'SHIBUSDT': ['DOGEUSDT', 'PEPEUSDT', 'FLOKIUSDT'],
    'XRPUSDT': ['XLMUSDT', 'ADAUSDT'],
    'ADAUSDT': ['XRPUSDT', 'DOTUSDT'],
    'DOTUSDT': ['ADAUSDT', 'KSMUSDT'],
}


class SignalEngine:
    def __init__(self, db=None):
        self.scanner = MarketScanner()
        self.technical_analyzer = TechnicalAnalyzer()
        self.institutional_analyzer = InstitutionalAnalyzer()
        self.context_engine = ContextEngine()
        self.strategy_factory = TimeframeStrategyFactory()
        self.signal_ranker = SignalRanker()  # NEW: Ranks signals, selects best 3/day
        self.conviction_engine = ConvictionEngine()  # NEW: Multi-factor conviction scoring
        self.db = db
        self.validation_pipeline = SignalValidationPipeline(db=db)
        
        self.signals_today = []
        self.last_reset = datetime.utcnow().date()
        
        self.min_confidence = settings.MIN_CONFIDENCE_SCORE
        self.max_signals_per_day = 3  # CHANGED: Always 3 signals per day
        self.min_risk_reward = settings.MIN_RISK_REWARD
        
        # Signal mode (Strict/Balanced/Aggressive)
        self.signal_mode = getattr(settings, 'SIGNAL_MODE', 'strict')  # Default: strict
        
        # Dynamic threshold adjustment based on rolling win rate
        self._signal_history = deque(maxlen=50)  # Last 50 signal outcomes
        self._setup_performance = {}  # Setup type -> {wins, losses, win_rate}
        self._base_threshold = settings.MIN_CONFIDENCE_SCORE
        self._threshold_adjustment = 0.0  # +/- applied dynamically
        
        # Teaser signals: lower-confidence candidates sent to free channel as teasers
        self.teaser_threshold = 60.0
        self.teaser_candidates = []
        self._sent_teasers = set()  # (symbol, timeframe) dedup
        
    async def initialize(self):
        logger.info("Initializing signal engine...")
        await self.scanner.initialize()
        # Reload today's active/pending signals from DB to prevent duplicates after restart
        if self.db:
            try:
                from datetime import datetime, timedelta
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                db_signals = await self.db.get_signals_by_date(today_start, datetime.utcnow())
                loaded = 0
                for s in db_signals:
                    if s.status in [SignalStatus.PENDING, SignalStatus.APPROVED, SignalStatus.ACTIVE]:
                        self.signals_today.append(s)
                        loaded += 1
                if loaded:
                    logger.info(f"🔄 Reloaded {loaded} active/pending signals from DB into memory")
            except Exception as e:
                logger.warning(f"Could not reload signals from DB: {e}")
        logger.info("Signal engine initialized")
    
    def _reset_daily_counter(self):
        today = datetime.utcnow().date()
        if today > self.last_reset:
            self.signals_today = []
            self.last_reset = today
            logger.info("Daily signal counter reset")
    
    def can_generate_signal(self) -> bool:
        """Check if we can generate more signals today (VIP or free real)"""
        self._reset_daily_counter()
        vip_today = len([s for s in self.signals_today if s.status == SignalStatus.APPROVED and s.confidence >= 85])
        free_today = len([s for s in self.signals_today if s.status == SignalStatus.APPROVED and 70 <= s.confidence < 85])
        return vip_today < self.max_signals_per_day or free_today < 1
    
    def can_generate_vip_signal(self) -> bool:
        """Check if we can generate more VIP signals today (85%+, max 3)"""
        self._reset_daily_counter()
        vip_today = len([s for s in self.signals_today if s.status == SignalStatus.APPROVED and s.confidence >= 85])
        return vip_today < self.max_signals_per_day
    
    def can_generate_free_signal(self) -> bool:
        """Check if we can generate more free real signals today (70-80%, max 1)"""
        self._reset_daily_counter()
        free_today = len([s for s in self.signals_today if s.status == SignalStatus.APPROVED and 70 <= s.confidence < 85])
        return free_today < 1
    
    async def scan_for_signals(self, timeframe: str = '15m', min_confidence_override: float = None) -> List[TradingSignal]:
        if not self.can_generate_signal():
            logger.info(f"Max signals ({self.max_signals_per_day}) reached for today")
            return []
        
        # Get timeframe-specific strategy for confidence threshold
        strategy = self.strategy_factory.get_strategy(timeframe)
        
        # Collect all signals ≥ 60% for tiered routing (VIP 85%+, Free 70-80%, Teasers <70%)
        scan_threshold = min_confidence_override if min_confidence_override is not None else 60
        strategy_min = strategy.min_confidence
        min_confidence = scan_threshold
        
        logger.info(f"🔍 Scanning {timeframe} timeframe (institutional analysis, collecting signals ≥ {min_confidence}%)...")
        
        pairs = await self.scanner.get_liquid_pairs()
        
        # Parallel scan with semaphore to avoid rate limits
        semaphore = asyncio.Semaphore(8)
        
        async def _analyze_with_limit(symbol: str) -> Optional[TradingSignal]:
            async with semaphore:
                try:
                    # Small delay to avoid hammering the exchange
                    await asyncio.sleep(0.05)
                    return await self.analyze_pair(symbol, timeframe, min_confidence_override=min_confidence)
                except Exception as e:
                    logger.debug(f"Error analyzing {symbol}: {e}")
                    return None
        
        # Run all analyses concurrently
        tasks = [_analyze_with_limit(symbol) for symbol in pairs[:100]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_signals = []
        for signal in results:
            if isinstance(signal, Exception):
                continue
            if signal and signal.confidence >= min_confidence:
                all_signals.append(signal)
                if signal.confidence >= 85:
                    logger.info(f"🎯 Candidate: {signal.symbol} {timeframe} — Confidence: {signal.confidence:.1f}% | R:R {signal.risk_reward:.1f}")
                else:
                    logger.info(f"📢 Warm-up: {signal.symbol} {timeframe} — Confidence: {signal.confidence:.1f}% | R:R {signal.risk_reward:.1f}")
        
        all_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        # Categorize into tiers
        vip_candidates = [s for s in all_signals if s.confidence >= 85][:3]
        free_real = [s for s in all_signals if 70 <= s.confidence < 85][:1]
        
        # Teasers: everything else (below 70, or extra 70-80 beyond the 1 free real)
        used_symbols = {s.symbol for s in vip_candidates + free_real}
        teasers = [s for s in all_signals if s.symbol not in used_symbols][:2]
        
        self.free_real_candidates = free_real
        self.teaser_candidates = teasers
        
        if vip_candidates:
            logger.info(f"Found {len(vip_candidates)} VIP candidates (85%+), {len(free_real)} free real (70-80%), {len(teasers)} teasers")
        else:
            logger.info(f"No VIP candidates. {len(free_real)} free real, {len(teasers)} teasers collected.")
        
        # Filter out duplicates for VIP candidates only
        if vip_candidates:
            vip_candidates = await self._filter_duplicates(vip_candidates)
            logger.info(f"After dedup: {len(vip_candidates)} unique VIP candidates")
        
        return vip_candidates
    
    async def _filter_duplicates(self, candidates):
        """Remove candidates for symbols that already have pending/active signals in memory AND DB."""
        active_symbols = set()
        # Check in-memory signals
        for s in self.signals_today:
            if s.status in [SignalStatus.PENDING, SignalStatus.APPROVED, SignalStatus.ACTIVE]:
                active_symbols.add(s.symbol)
        
        # Check DB for active signals (catches duplicates after restarts)
        if self.db:
            try:
                db_active = await self.db.get_active_signals(limit=100)
                for row in db_active:
                    sym = getattr(row, 'symbol', '') or getattr(row, 'trading_pair', '')
                    if sym:
                        active_symbols.add(sym)
            except Exception as e:
                logger.debug(f"DB duplicate check failed: {e}")
        
        filtered = []
        for c in candidates:
            if c.symbol in active_symbols:
                logger.info(f"⏭️  Skipping {c.symbol} - signal already pending/active (in DB or memory)")
                continue
            filtered.append(c)
        
        return filtered
    
    async def analyze_pair(self, symbol: str, timeframe: str, min_confidence_override: float = None) -> Optional[TradingSignal]:
        """
        Institutional-grade signal analysis per timeframe.
        Uses timeframe-specific strategy + institutional tools + multi-TF alignment.
        """
        try:
            # Fetch current timeframe data
            df = await self.scanner.fetch_ohlcv(symbol, timeframe, limit=500)
            if len(df) < 100:
                return None
            
            # Get timeframe-specific strategy
            strategy = self.strategy_factory.get_strategy(timeframe)
            
            # 1. SESSION CHECK: Only trade active sessions
            if strategy.session_required:
                session_ok, session_msg = strategy.is_valid_session(df)
                if not session_ok:
                    logger.debug(f"⏰ {symbol} {timeframe}: {session_msg}")
                    return None
            
            # 2. VOLATILITY CHECK: Avoid bad regimes
            vol_ok, vol_msg = strategy.analyze_volatility(df)
            if not vol_ok:
                logger.debug(f"📊 {symbol} {timeframe}: {vol_msg}")
                return None
            
            # 3. FETCH HIGHER TIMEFRAME for alignment
            higher_tf = self._get_higher_timeframe(timeframe)
            df_higher = None
            if higher_tf:
                try:
                    df_higher = await self.scanner.fetch_ohlcv(symbol, higher_tf, limit=200)
                except Exception:
                    pass  # Higher TF optional
            
            # 4. STRUCTURE ANALYSIS (institutional)
            structure = self.institutional_analyzer.analyze_structure(df)
            if structure['trend'] == 'neutral':
                return None
            
            # 5. FIND SETUP using timeframe strategy
            direction = self._determine_direction(structure['trend'])
            if not direction:
                return None
            
            setup = strategy.find_setup(df, direction)
            if not setup:
                return None
            
            # 6. CALCULATE ENTRY/SL/TP using strategy
            entry_price, stop_loss, tp1, tp2, tp3 = strategy.calculate_entry_sl_tp(
                df, setup, direction
            )
            
            risk_reward = abs(tp1 - entry_price) / abs(entry_price - stop_loss)
            if risk_reward < strategy.min_risk_reward:
                logger.debug(f"� {symbol} {timeframe}: R:R {risk_reward:.1f} < {strategy.min_risk_reward}")
                return None
            
            # 7. INSTITUTIONAL SCORING
            inst_score = self.institutional_analyzer.calculate_institutional_score(
                df, direction, entry_price, stop_loss, timeframe, df_higher
            )
            
            # 8. CONTEXT ANALYSIS (news, macro)
            context_score = await self.context_engine.analyze_context(symbol, direction.value)
            
            # 9. MARKET REGIME CHECK — skip signals in choppy/volatile regimes
            regime = self.institutional_analyzer.detect_market_regime(df)
            if regime == 'choppy':
                logger.info(f"🚫 {symbol} {timeframe}: Market regime is CHOPPY — skipping to avoid false signals")
                return None
            
            # 10. CONFLUENCE SCORING — bonus/penalty based on factor agreement
            strong_factors = [
                inst_score.structure_score >= 70,
                inst_score.volume_profile_score >= 70,
                inst_score.liquidity_score >= 70,
                inst_score.session_score >= 60,
                inst_score.multi_tf_score >= 70,
                context_score.total_score >= 60,
            ]
            strong_count = sum(strong_factors)
            
            if strong_count >= 5:
                confluence_bonus = 12  # High confluence — exceptional setup
                confluence_tag = "🔥 High Confluence"
            elif strong_count >= 4:
                confluence_bonus = 8   # Good confluence
                confluence_tag = "✨ Good Confluence"
            elif strong_count >= 3:
                confluence_bonus = 3   # Moderate confluence
                confluence_tag = "⚡ Moderate Confluence"
            elif strong_count <= 1:
                confluence_bonus = -8  # Low confluence — penalize
                confluence_tag = "⚠️ Low Confluence"
            else:
                confluence_bonus = 0
                confluence_tag = ""
            
            # FINAL CONFIDENCE: Institutional + Context + Strategy minimum + Confluence
            confidence = (
                inst_score.total_score * 0.65 +  # Institutional tools dominate
                context_score.total_score * 0.35  # Context/news secondary
            ) + confluence_bonus
            confidence = max(0, min(confidence, 100))
            
            # NEW: Calculate conviction score using multi-factor engine
            try:
                conviction_breakdown = await self.conviction_engine.calculate_conviction(
                    df, symbol, direction.value
                )
                conviction_score = conviction_breakdown.conviction_score
                conviction_tier = conviction_breakdown.tier
                
                logger.info(
                    f"🎯 {symbol} Conviction: {conviction_score:.1f}/100 ({conviction_tier}) | "
                    f"Old Confidence: {confidence:.1f}% | "
                    f"Struct: {conviction_breakdown.market_structure_score:.1f}/20 | "
                    f"Liq: {conviction_breakdown.liquidity_score:.1f}/20 | "
                    f"Vol: {conviction_breakdown.volume_score:.1f}/15"
                )
            except Exception as e:
                logger.warning(f"Conviction engine failed for {symbol}, using old confidence: {e}")
                conviction_score = confidence
                conviction_tier = 'UNKNOWN'
                conviction_breakdown = None
            
            # Use conviction score for filtering (replaces old confidence threshold)
            # Allow override for warm-up signal collection
            if min_confidence_override is not None:
                min_conviction = min_confidence_override
                adjusted_min_conf = min_confidence_override
                filter_reason = f"override={min_confidence_override}"
            else:
                mode_thresholds = {
                    'strict': 85,      # 0-5 signals/day, elite quality
                    'balanced': 75,    # 5-15 signals/day, high quality
                    'aggressive': 65   # 15-40 signals/day, moderate quality
                }
                min_conviction = mode_thresholds.get(self.signal_mode, 85)
                adjusted_min_conf = self._get_dynamic_threshold(strategy.min_confidence)
                filter_reason = f"{self.signal_mode} mode"
            
            if conviction_score < min_conviction:
                logger.debug(
                    f"📊 {symbol} {timeframe}: Conviction {conviction_score:.1f} < "
                    f"threshold {min_conviction} ({filter_reason})"
                )
                return None
            
            # Dynamic threshold adjustment based on recent performance (legacy)
            if confidence < adjusted_min_conf:
                logger.debug(f"📊 {symbol} {timeframe}: Confidence {confidence:.1f}% < adjusted threshold {adjusted_min_conf:.1f}% ({filter_reason})")
                return None
            
            # 11. MULTI-TIMEFRAME ALIGNMENT GATE
            # 15m: lower threshold (50) since short-term setups don't need perfect HTF alignment
            # 1h: standard threshold (60) for swing trades
            mtf_threshold = 50 if timeframe == '15m' else 60
            if inst_score.multi_tf_score < mtf_threshold and timeframe in ['15m', '1h']:
                logger.info(f"🚫 {symbol} {timeframe}: Higher TF not aligned (score: {inst_score.multi_tf_score:.0f} < {mtf_threshold})")
                return None
            
            # 12. CORRELATION FILTER — avoid double exposure on correlated pairs
            if self._has_correlated_active_signal(symbol):
                logger.info(f"⏭️  Skipping {symbol} — correlated pair already has active/pending signal")
                return None
            
            market_info = await self.scanner.get_market_info(symbol)
            
            context_summary = await self.context_engine.get_context_summary(symbol)
            
            # 13. SETUP PERFORMANCE BOOST — bonus for historically winning setup types
            setup_type = setup.get('type', SetupType.ORDER_BLOCK)
            setup_perf = self._get_setup_performance(setup_type)
            if setup_perf and setup_perf['win_rate'] > 70:
                confidence = min(100, confidence + 3)
                perf_tag = f" 📈 Setup win rate: {setup_perf['win_rate']:.0f}%"
            else:
                perf_tag = ""
            
            # Extract stop warning if present
            stop_warning = setup.get('stop_warning', None)
            
            reasoning = self._generate_reasoning(
                symbol, setup_type, direction, structure,
                inst_score, context_score, timeframe, confluence_tag, regime, perf_tag, stop_warning
            )
            
            from src.models.signal import TechnicalScore, ContextScore
            
            # Determine entry execution type based on setup, price distance, and volatility
            current_price = df['close'].iloc[-1]
            is_limit = False
            
            # Calculate distance from entry (%)
            price_distance = abs(current_price - entry_price) / entry_price * 100
            
            # Get volatility (ATR as % of price)
            atr = (df['high'].iloc[-20:] - df['low'].iloc[-20:]).mean()
            volatility_pct = (atr / current_price) * 100
            
            # EXECUTION STRATEGY LOGIC:
            # 1. BREAKOUT setups → MARKET (enter on momentum)
            # 2. RETEST setups → LIMIT (wait for pullback)
            # 3. Price far from entry (>1%) → LIMIT (wait for retest)
            # 4. Price at entry (<0.3%) → MARKET (enter now)
            # 5. High volatility (>3%) + close to entry → MARKET (may not get retest)
            
            if setup_type.value in ['breakout_retest', 'bos_retest', 'choch_retest']:
                # Retest setups: Wait for price to come back to entry zone
                is_limit = True
            elif setup_type.value in ['liquidity_sweep', 'fair_value_gap']:
                # Sweep/FVG: If price already moved away, wait for retest
                if direction == SignalDirection.LONG:
                    is_limit = current_price > entry_price * 1.003  # >0.3% above
                else:
                    is_limit = current_price < entry_price * 0.997  # >0.3% below
            elif price_distance > 1.0:
                # Price is far from entry (>1%) → LIMIT order
                is_limit = True
            elif price_distance < 0.3:
                # Price is very close to entry (<0.3%) → MARKET order
                is_limit = False
            elif volatility_pct > 3.0 and price_distance < 0.8:
                # High volatility + close to entry → MARKET (may not get retest)
                is_limit = False
            else:
                # Default: Check if price moved away from entry
                if direction == SignalDirection.LONG:
                    is_limit = current_price > entry_price * 1.005  # >0.5% above
                else:
                    is_limit = current_price < entry_price * 0.995  # >0.5% below
            
            signal = TradingSignal(
                id=str(uuid.uuid4()),
                symbol=symbol,
                direction=direction,
                setup_type=setup_type,
                timeframe=timeframe,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                is_limit_order=is_limit,
                technical_score=TechnicalScore(
                    trend_score=inst_score.structure_score,
                    volume_score=inst_score.volume_profile_score,
                    momentum_score=inst_score.liquidity_score,
                    structure_score=inst_score.structure_score,
                    total_score=inst_score.total_score
                ),
                context_score=ContextScore(
                    macro_score=context_score.macro_score,
                    news_score=context_score.news_score,
                    sentiment_score=context_score.sentiment_score,
                    total_score=context_score.total_score
                ),
                confidence=confidence,
                conviction_score=conviction_score if conviction_breakdown else None,
                conviction_tier=conviction_tier if conviction_breakdown else None,
                conviction_breakdown=conviction_breakdown.to_dict() if conviction_breakdown else None,
                reasoning=reasoning,
                risk_reward=risk_reward,
                atr=(df['high'].iloc[-20:] - df['low'].iloc[-20:]).mean(),
                volume_24h=market_info.get('volume_24h', 0),
                market_context=context_summary,
                expires_at=datetime.utcnow() + timedelta(minutes=settings.SIGNAL_EXPIRY_MINUTES)
            )
            
            # Run 8-stage validation pipeline
            val_result = await self.validation_pipeline.validate(signal)
            
            if not val_result.passed:
                logger.warning(
                    f"🚫 {symbol} {timeframe} signal REJECTED by pipeline: "
                    f"Grade={signal.grade.value}, Score={signal.validation_score:.1f} | "
                    f"Reasons: {', '.join(val_result.rejection_reasons[:3])}"
                )
                return None
            
            # Track for performance analysis
            self._track_signal_generated(signal)
            
            logger.info(
                f"🎯 {symbol} {timeframe} signal: {direction.value} | "
                f"Confidence: {confidence:.1f}% | R:R {risk_reward:.1f} | "
                f"Grade: {signal.grade.value} | Score: {signal.validation_score:.1f} | "
                f"Structure: {inst_score.structure_score:.0f} | "
                f"MTF: {inst_score.multi_tf_score:.0f}"
            )
            
            # RANKING: Add to ranker - only return if approved for top 3
            should_publish = self.signal_ranker.add_candidate(signal, inst_score, context_score)
            
            if should_publish:
                logger.info(f"✅ {symbol} approved for publishing (top 3 signal)")
                return signal
            else:
                logger.info(f"⏸️  {symbol} held for ranking - not in top 3 yet")
                return None  # Signal found but not published yet
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def _get_higher_timeframe(self, timeframe: str) -> Optional[str]:
        """Map current TF to higher TF for alignment check"""
        mapping = {
            '15m': '1h',
            '1h': '4h',
            '4h': '1d',
            '1d': '1w'
        }
        return mapping.get(timeframe)
    
    def _determine_direction(self, trend: str) -> Optional[SignalDirection]:
        """Convert trend string to SignalDirection"""
        if trend == 'uptrend':
            return SignalDirection.LONG
        elif trend == 'downtrend':
            return SignalDirection.SHORT
        return None
    
    def _generate_reasoning(
        self,
        symbol: str,
        setup_type: SetupType,
        direction: SignalDirection,
        structure: dict,
        inst_score,
        context_score,
        timeframe: str,
        confluence_tag: str = "",
        regime: str = "",
        perf_tag: str = "",
        stop_warning: str = None
    ) -> str:
        """Generate institutional-grade trade entry analysis."""
        parts = []
        d = direction.value
        st = structure
        vol = inst_score.volume_details
        liq = inst_score.liquidity_details
        sess = inst_score.session_details

        # ─── EXECUTIVE SUMMARY ───
        setup_name = setup_type.value.replace('_', ' ').title()
        parts.append(f"<b>📋 TRADE PLAN: {symbol} {d} — {setup_name} ({timeframe})</b>")

        # ─── MARKET STRUCTURE NARRATIVE ───
        trend = st.get('trend', 'neutral')
        bos = st.get('bos', False)
        choch = st.get('choch', False)
        inducement = st.get('inducement', False)
        swing_high = st.get('recent_swing_high')
        swing_low = st.get('recent_swing_low')

        structure_lines = []
        if trend == 'uptrend':
            structure_lines.append(f"Price is in a confirmed uptrend with Higher Highs + Higher Lows.")
        elif trend == 'downtrend':
            structure_lines.append(f"Price is in a confirmed downtrend with Lower Highs + Lower Lows.")
        elif trend == 'potential_reversal':
            structure_lines.append(f"Potential reversal zone — price showing early signs of structure shift.")

        if bos:
            structure_lines.append(f"✅ <b>Break of Structure (BOS)</b> confirmed — trend continuation is valid.")
        if choch:
            structure_lines.append(f"⚠️ <b>Change of Character (CHoCH)</b> detected — prior structure may be breaking.")
        if inducement:
            structure_lines.append(f"🎣 <b>Inducement</b> identified — liquidity was swept before this setup formed.")

        if swing_high and swing_low:
            structure_lines.append(f"� Recent swing high: ${swing_high:,.4f} | swing low: ${swing_low:,.4f}")

        if structure_lines:
            parts.append(f"\n<b>🏗️ MARKET STRUCTURE</b>")
            parts.extend(structure_lines)

        # ─── VOLUME PROFILE POSITIONING ───
        poc = vol.get('poc')
        vah = vol.get('vah')
        val = vol.get('val')
        entry = vol.get('entry')
        vquality = vol.get('quality', '')

        if poc and vah and val:
            parts.append(f"\n<b>📊 VOLUME PROFILE</b>")
            parts.append(f"POC (most traded): ${poc:,.4f} | VAH: ${vah:,.4f} | VAL: ${val:,.4f}")
            if entry:
                if 'discount' in vquality.lower():
                    parts.append(f"🟢 Entry at <b>discount</b> below VAL — high-probability buy zone where institutions accumulate.")
                elif 'premium' in vquality.lower():
                    parts.append(f"🔴 Entry at <b>premium</b> above VAH — high-probability sell zone where institutions distribute.")
                elif 'fair value' in vquality.lower():
                    parts.append(f"🟡 Entry near <b>POC fair value</b> — acceptable but not at an extreme.")
                else:
                    parts.append(f"Entry relative to volume profile: {vquality}")

        # ─── LIQUIDITY CONTEXT ───
        zones_found = liq.get('liquidity_zones_found', 0)
        swept = liq.get('swept_liquidity', False)
        swept_level = liq.get('swept_level')
        stop_beyond = liq.get('stop_beyond_liquidity', False)

        if zones_found > 0 or swept or stop_beyond:
            parts.append(f"\n<b>💧 LIQUIDITY ANALYSIS</b>")
            if swept and swept_level:
                parts.append(f"🎯 <b>Liquidity swept</b> at ${swept_level:,.4f} before entry — Smart Money trap confirmed.")
            elif stop_beyond:
                parts.append(f"🛡️ Stop loss sits <b>beyond liquidity</b> — protected from stop-hunts.")
            if zones_found:
                parts.append(f"{zones_found} liquidity zone(s) identified in recent price action.")

        # ─── SESSION & TIMING ───
        session = sess.get('session', 'unknown')
        hour_utc = sess.get('hour_utc')
        if session != 'unknown':
            parts.append(f"\n<b>⏰ SESSION CONTEXT</b>")
            parts.append(f"Current session: <b>{session}</b> ({hour_utc}:00 UTC)")
            if 'Overlap' in session:
                parts.append(f"🔥 Prime time — highest volume and liquidity of the day.")
            elif 'New York' in session:
                parts.append(f"🗽 NY session active — strong directional moves likely.")
            elif 'London' in session:
                parts.append(f"🇬🇧 London session active — good liquidity, momentum building.")

        # ─── MULTI-TIMEFRAME ALIGNMENT ───
        mtf = inst_score.multi_tf_score
        parts.append(f"\n<b>🔭 MULTI-TIMEFRAME ALIGNMENT</b>")
        if mtf >= 80:
            parts.append(f"✅ HTF strongly aligned (score: {mtf:.0f}/100) — top-down confluence is excellent.")
        elif mtf >= 60:
            parts.append(f"✅ HTF aligned (score: {mtf:.0f}/100) — higher timeframe supports this direction.")
        elif mtf >= 40:
            parts.append(f"⚠️ HTF neutral (score: {mtf:.0f}/100) — trade valid but watch for HTF rejection.")
        else:
            parts.append(f"⚠️ HTF weak (score: {mtf:.0f}/100) — counter-trend on higher timeframe; use tight risk.")

        # ─── CONFLUENCE & CONTEXT ───
        parts.append(f"\n<b>⚡ CONFLUENCE SCORECARD</b>")
        parts.append(f"Structure: {inst_score.structure_score:.0f}/100 | Volume: {inst_score.volume_profile_score:.0f}/100 | Liquidity: {inst_score.liquidity_score:.0f}/100")
        parts.append(f"Session: {inst_score.session_score:.0f}/100 | Multi-TF: {inst_score.multi_tf_score:.0f}/100 | Context: {context_score.total_score:.1f}/100")
        if confluence_tag:
            parts.append(f"{confluence_tag}")
        if regime:
            parts.append(f"Market regime: {regime.title()}")
        if perf_tag:
            parts.append(f"{perf_tag}")

        # ─── CONTEXT OVERLAY ───
        if context_score.total_score >= 70:
            parts.append(f"\n<b>🌍 MACRO CONTEXT</b>")
            parts.append(f"Context score: {context_score.total_score:.0f}/100 — fundamentals support this direction.")
        elif context_score.total_score < 50:
            parts.append(f"\n<b>🌍 MACRO CONTEXT</b>")
            parts.append(f"⚠️ Context score: {context_score.total_score:.0f}/100 — weak macro/news support; rely on technicals only.")

        # ─── WHAT TO WATCH (INVALIDATION) ───
        parts.append(f"\n<b>👁️ WHAT TO WATCH</b>")
        
        # Add stop warning if present (tight structure, etc.)
        if stop_warning:
            parts.append(f"• {stop_warning}")
        
        if bos and trend in ['uptrend', 'downtrend']:
            parts.append(f"• Invalidation: If price reclaims the broken structure level, the setup is void.")
        if choch:
            parts.append(f"• Confirmation needed: Wait for the next candle close to confirm CHoCH holds.")
        if inducement:
            parts.append(f"• Trap risk: Inducement setups can re-sweep — don't add to a losing position.")
        parts.append(f"• Session end: If the trade hasn't moved by session close, consider reducing size or exiting.")

        return '\n'.join(parts)
    
    def _has_correlated_active_signal(self, symbol: str) -> bool:
        """Check if a correlated pair already has an active/pending signal"""
        correlated = CORRELATION_GROUPS.get(symbol, [])
        active_symbols = set()
        for s in self.signals_today:
            if s.status in [SignalStatus.PENDING, SignalStatus.APPROVED, SignalStatus.ACTIVE]:
                active_symbols.add(s.symbol)
        
        for corr_symbol in correlated:
            if corr_symbol in active_symbols:
                return True
        return False
    
    def _get_dynamic_threshold(self, base_threshold: float) -> float:
        """Adjust confidence threshold based on recent signal performance"""
        if not self._signal_history:
            return base_threshold
        
        # Calculate 30-signal rolling win rate
        recent = list(self._signal_history)[-30:]
        if len(recent) < 10:
            return base_threshold
        
        wins = sum(1 for r in recent if r.get('pnl', 0) > 0)
        win_rate = wins / len(recent)
        
        # Adjust threshold: poor performance = raise bar, strong performance = lower slightly
        if win_rate < 0.35:
            adjustment = 5.0  # Raise threshold when struggling
            logger.info(f"📊 Dynamic threshold: win rate {win_rate:.0%} — RAISING threshold by {adjustment}")
        elif win_rate < 0.50:
            adjustment = 3.0
            logger.info(f"📊 Dynamic threshold: win rate {win_rate:.0%} — RAISING threshold by {adjustment}")
        elif win_rate > 0.70:
            adjustment = -2.0  # Slightly lower when hot
            logger.info(f"📊 Dynamic threshold: win rate {win_rate:.0%} — lowering threshold by {abs(adjustment)}")
        else:
            adjustment = 0.0
        
        return max(80, base_threshold + adjustment)
    
    def _track_signal_generated(self, signal: TradingSignal):
        """Track signal for performance analysis"""
        self._signal_history.append({
            'id': signal.id,
            'symbol': signal.symbol,
            'setup_type': signal.setup_type.value,
            'direction': signal.direction.value,
            'confidence': signal.confidence,
            'timeframe': signal.timeframe,
            'timestamp': datetime.utcnow(),
            'pnl': None,  # Will be updated when signal closes
        })
    
    def _get_setup_performance(self, setup_type: SetupType) -> Optional[Dict]:
        """Get historical performance stats for a setup type"""
        key = setup_type.value
        return self._setup_performance.get(key)
    
    def update_signal_result(self, signal_id: str, pnl: float, setup_type: str = None):
        """Update signal history with actual PnL result"""
        for record in self._signal_history:
            if record['id'] == signal_id:
                record['pnl'] = pnl
                break
        
        # Update setup type performance
        if setup_type:
            key = setup_type
            perf = self._setup_performance.setdefault(key, {'wins': 0, 'losses': 0, 'total': 0, 'win_rate': 0})
            if pnl > 0:
                perf['wins'] += 1
            else:
                perf['losses'] += 1
            perf['total'] += 1
            perf['win_rate'] = (perf['wins'] / perf['total']) * 100
            logger.info(f"📊 Setup '{key}' performance: {perf['win_rate']:.0f}% ({perf['wins']}/{perf['total']})")
    
    def add_signal(self, signal: TradingSignal):
        self.signals_today.append(signal)
    
    async def close(self):
        await self.scanner.close()
        logger.info("Signal engine closed")
