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
from src.models.signal import (
    TradingSignal, SignalDirection, SetupType, SignalStatus
)
from src.config import settings
from src.utils.logger import get_logger

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
    def __init__(self):
        self.scanner = MarketScanner()
        self.technical_analyzer = TechnicalAnalyzer()
        self.institutional_analyzer = InstitutionalAnalyzer()
        self.context_engine = ContextEngine()
        self.strategy_factory = TimeframeStrategyFactory()
        
        self.signals_today = []
        self.last_reset = datetime.utcnow().date()
        
        self.min_confidence = settings.MIN_CONFIDENCE_SCORE
        self.max_signals_per_day = settings.MAX_SIGNALS_PER_DAY
        self.min_risk_reward = settings.MIN_RISK_REWARD
        
        # Dynamic threshold adjustment based on rolling win rate
        self._signal_history = deque(maxlen=50)  # Last 50 signal outcomes
        self._setup_performance = {}  # Setup type -> {wins, losses, win_rate}
        self._base_threshold = settings.MIN_CONFIDENCE_SCORE
        self._threshold_adjustment = 0.0  # +/- applied dynamically
        
    async def initialize(self):
        logger.info("Initializing signal engine...")
        await self.scanner.initialize()
        logger.info("Signal engine initialized")
    
    def reset_daily_counter(self):
        today = datetime.utcnow().date()
        if today > self.last_reset:
            self.signals_today = []
            self.last_reset = today
            logger.info("Daily signal counter reset")
    
    def can_generate_signal(self) -> bool:
        """Check if we can generate more signals today"""
        approved_today = len([s for s in self.signals_today if s.status == SignalStatus.APPROVED])
        return approved_today < self.max_signals_per_day
    
    async def scan_for_signals(self, timeframe: str = '15m', min_confidence_override: float = None) -> List[TradingSignal]:
        if not self.can_generate_signal():
            logger.info(f"Max signals ({self.max_signals_per_day}) reached for today")
            return []
        
        # Get timeframe-specific strategy for confidence threshold
        strategy = self.strategy_factory.get_strategy(timeframe)
        
        if min_confidence_override:
            min_confidence = min_confidence_override
        else:
            min_confidence = strategy.min_confidence
        
        logger.info(f"🔍 Scanning {timeframe} timeframe (institutional analysis, min confidence: {min_confidence}%)...")
        
        pairs = await self.scanner.get_liquid_pairs()
        candidates = []
        
        for symbol in pairs[:100]:
            try:
                signal = await self.analyze_pair(symbol, timeframe)
                if signal and signal.confidence >= min_confidence:
                    candidates.append(signal)
                    logger.info(f"🎯 Candidate: {symbol} {timeframe} — Confidence: {signal.confidence:.1f}% | R:R {signal.risk_reward:.1f}")
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue
        
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        # Top 3 candidates above minimum confidence
        # 90%+ = VIP-exclusive routing, 85-89% = dual-channel routing
        top_candidates = candidates[:3]
        
        if top_candidates:
            vip_count = len([c for c in top_candidates if c.confidence >= 90])
            dual_count = len(top_candidates) - vip_count
            logger.info(f"Found {len(top_candidates)} candidates: {vip_count} VIP-only (90%+), {dual_count} dual-channel (85-89%)")
            
            # Filter out duplicates (same symbol already pending/active)
            top_candidates = self._filter_duplicates(top_candidates)
            logger.info(f"After dedup: {len(top_candidates)} unique candidates")
        else:
            logger.info(f"No candidates found above {min_confidence}% confidence")
        
        return top_candidates
    
    def _filter_duplicates(self, candidates):
        """Remove candidates for symbols that already have pending/active signals"""
        # Check in-memory signals (today's signals)
        active_symbols = set()
        for s in self.signals_today:
            if s.status in [SignalStatus.PENDING, SignalStatus.APPROVED, SignalStatus.ACTIVE]:
                active_symbols.add(s.symbol)
        
        filtered = []
        for c in candidates:
            if c.symbol in active_symbols:
                logger.info(f"⏭️  Skipping {c.symbol} - signal already pending/active")
                continue
            filtered.append(c)
        
        return filtered
    
    async def analyze_pair(self, symbol: str, timeframe: str) -> Optional[TradingSignal]:
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
            
            # Dynamic threshold adjustment based on recent performance
            adjusted_min_conf = self._get_dynamic_threshold(strategy.min_confidence)
            if confidence < adjusted_min_conf:
                logger.debug(f"📊 {symbol} {timeframe}: Confidence {confidence:.1f}% < adjusted threshold {adjusted_min_conf:.1f}%")
                return None
            
            # 11. MULTI-TIMEFRAME ALIGNMENT GATE
            if inst_score.multi_tf_score < 60 and timeframe in ['15m', '1h']:
                logger.info(f"🚫 {symbol} {timeframe}: Higher TF not aligned (score: {inst_score.multi_tf_score:.0f})")
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
            
            reasoning = self._generate_reasoning(
                symbol, setup_type, direction, structure,
                inst_score, context_score, timeframe, confluence_tag, regime, perf_tag
            )
            
            from src.models.signal import TechnicalScore, ContextScore
            
            # Determine if this should be a limit order or market entry
            current_price = df['close'].iloc[-1]
            is_limit = False
            
            if direction == SignalDirection.LONG:
                # LONG: If current price is ABOVE entry, it's a limit order (wait for pullback to entry)
                if current_price > entry_price * 1.002:  # 0.2% buffer
                    is_limit = True
            else:
                # SHORT: If current price is BELOW entry, it's a limit order (wait for bounce to entry)
                if current_price < entry_price * 0.998:  # 0.2% buffer
                    is_limit = True
            
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
                reasoning=reasoning,
                risk_reward=risk_reward,
                atr=(df['high'].iloc[-20:] - df['low'].iloc[-20:]).mean(),
                volume_24h=market_info.get('volume_24h', 0),
                market_context=context_summary,
                expires_at=datetime.utcnow() + timedelta(minutes=settings.SIGNAL_EXPIRY_MINUTES)
            )
            
            # Track for performance analysis
            self._track_signal_generated(signal)
            
            logger.info(
                f"🎯 {symbol} {timeframe} signal: {direction.value} | "
                f"Confidence: {confidence:.1f}% | R:R {risk_reward:.1f} | "
                f"Structure: {inst_score.structure_score:.0f} | "
                f"MTF: {inst_score.multi_tf_score:.0f}"
            )
            
            return signal
            
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
        perf_tag: str = ""
    ) -> str:
        reasoning_parts = []
        
        reasoning_parts.append(f"🎯 {setup_type.value.replace('_', ' ').title()} on {symbol} ({timeframe})")
        if confluence_tag:
            reasoning_parts.append(f"   {confluence_tag}")
        if regime:
            reasoning_parts.append(f"   Regime: {regime.title()}")
        reasoning_parts.append(f"📈 Direction: {direction.value}")
        reasoning_parts.append(f"📊 Structure: {structure.get('trend', 'neutral').title()}")
        reasoning_parts.append(f"⚡ Institutional Score: {inst_score.total_score:.1f}/100")
        reasoning_parts.append(f"   • Structure: {inst_score.structure_score:.0f}")
        reasoning_parts.append(f"   • Volume Profile: {inst_score.volume_profile_score:.0f}")
        reasoning_parts.append(f"   • Liquidity: {inst_score.liquidity_score:.0f}")
        reasoning_parts.append(f"   • Session: {inst_score.session_score:.0f}")
        reasoning_parts.append(f"   • Multi-TF: {inst_score.multi_tf_score:.0f}")
        reasoning_parts.append(f"🌍 Context: {context_score.total_score:.1f}/100")
        if perf_tag:
            reasoning_parts.append(f"   {perf_tag}")
        
        if inst_score.structure_details.get('bos'):
            reasoning_parts.append("✅ Break of Structure confirmed")
        
        if inst_score.volume_details.get('quality', '').startswith('Below VAL'):
            reasoning_parts.append("✅ Entry at volume profile discount")
        elif inst_score.volume_details.get('quality', '').startswith('Above VAH'):
            reasoning_parts.append("✅ Entry at volume profile premium")
        
        if inst_score.liquidity_details.get('swept_liquidity'):
            reasoning_parts.append("✅ Liquidity swept before entry")
        
        if context_score.news_score < 50:
            reasoning_parts.append("⚠️ Weak news sentiment")
        
        return '\n'.join(reasoning_parts)
    
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
