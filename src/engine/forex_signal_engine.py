"""
Forex Signal Engine - mirrors crypto signal engine but for Forex markets
Generates trading signals for major Forex pairs, commodities (XAUUSD), and indices (NAS100)
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import uuid
from collections import deque

from src.exchange.forex_client import ForexClient
from src.analysis.technical_analyzer import TechnicalAnalyzer
from src.analysis.institutional_analyzer import InstitutionalAnalyzer
from src.analysis.timeframe_strategies import TimeframeStrategyFactory
from src.analysis.enhanced_context_engine import EnhancedContextEngine as ContextEngine
from src.analysis.forex_adjustments import ForexMarketAdjustments
from src.engine.signal_ranker import SignalRanker
from src.models.signal import (
    TradingSignal, SignalDirection, SetupType, SignalStatus, MarketType
)
from src.config import settings
from src.utils.logger import get_logger
from src.utils.signal_validation_pipeline import SignalValidationPipeline
from src.conviction.conviction_engine import ConvictionEngine

logger = get_logger(__name__)

# Correlated Forex pairs — avoid double exposure
FOREX_CORRELATION_GROUPS = {
    'EUR/USD': ['GBP/USD', 'AUD/USD'],  # USD-based pairs move together
    'GBP/USD': ['EUR/USD', 'AUD/USD'],
    'AUD/USD': ['EUR/USD', 'NZD/USD'],
    'NZD/USD': ['AUD/USD'],
    'XAU/USD': ['XAG/USD'],  # Gold and Silver correlate
    'NAS100': ['SPX500', 'US30'],  # US indices correlate
}


class ForexSignalEngine:
    """
    Forex signal generation engine - same logic as crypto but for Forex markets
    """
    
    def __init__(self, db=None):
        self.forex_client = ForexClient()
        self.technical_analyzer = TechnicalAnalyzer()
        self.institutional_analyzer = InstitutionalAnalyzer()
        self.context_engine = ContextEngine()
        self.strategy_factory = TimeframeStrategyFactory()
        self.signal_ranker = SignalRanker()
        self.conviction_engine = ConvictionEngine()
        self.db = db
        self.validation_pipeline = SignalValidationPipeline(db=db)
        
        self.signals_today = []
        self.last_reset = datetime.utcnow().date()
        
        self.min_confidence = settings.MIN_CONFIDENCE_SCORE
        self.max_signals_per_day = 3  # Same as crypto: 3 signals/day
        self.min_risk_reward = settings.MIN_RISK_REWARD
        
        # Signal mode
        self.signal_mode = getattr(settings, 'SIGNAL_MODE', 'strict')
        
        # Dynamic threshold adjustment
        self._signal_history = deque(maxlen=50)
        self._setup_performance = {}
        self._base_threshold = settings.MIN_CONFIDENCE_SCORE
        self._threshold_adjustment = 0.0
        
        # Teaser signals for free channel
        self.teaser_threshold = 60.0
        self.teaser_candidates = []
        self._sent_teasers = set()
        
        # Scan lock to prevent concurrent scans (rate limit protection)
        self._scan_lock = asyncio.Lock()
        self._last_scan_time = None
        self._min_scan_interval = 30  # Minimum 30 seconds between scans
        
    async def initialize(self):
        """Initialize Forex client and load today's signals"""
        logger.info("🌍 Initializing Forex signal engine...")
        await self.forex_client.initialize()
        
        # Reload today's Forex signals from DB
        if self.db:
            try:
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                db_signals = await self.db.get_signals_by_date(today_start, datetime.utcnow())
                loaded = 0
                for sig in db_signals:
                    # Only load Forex signals
                    if getattr(sig, 'market_type', MarketType.CRYPTO) == MarketType.FOREX:
                        if sig.status.value in ['pending', 'approved', 'active']:
                            self.signals_today.append(sig)
                            loaded += 1
                logger.info(f"📊 Loaded {loaded} Forex signals from today")
            except Exception as e:
                logger.warning(f"Could not load today's Forex signals: {e}")
        
        logger.info(f"✅ Forex signal engine initialized ({len(self.forex_client.FOREX_SYMBOLS)} pairs)")
    
    async def close(self):
        """Close Forex client"""
        await self.forex_client.close()
    
    async def scan_and_generate(self) -> List[TradingSignal]:
        """
        Scan Forex markets and generate trading signals
        Same flow as crypto engine but for Forex pairs
        """
        # Prevent concurrent scans (protects API rate limits)
        if self._scan_lock.locked():
            logger.warning("🌍 Forex scan already in progress, skipping concurrent request")
            return []
        
        async with self._scan_lock:
            # Check minimum interval between scans
            if self._last_scan_time:
                elapsed = (datetime.utcnow() - self._last_scan_time).total_seconds()
                if elapsed < self._min_scan_interval:
                    logger.warning(f"🌍 Forex scan too recent ({elapsed:.0f}s ago), minimum interval is {self._min_scan_interval}s")
                    return []
            self._last_scan_time = datetime.utcnow()
            
            # Reset daily counter
            today = datetime.utcnow().date()
            if today != self.last_reset:
                self.signals_today = []
                self.last_reset = today
                logger.info("🔄 Daily Forex signal counter reset")
            
            # Check if we've hit daily limit
            approved_today = len([s for s in self.signals_today if s.status.value == 'approved'])
            if approved_today >= self.max_signals_per_day:
                logger.info(f"✋ Daily Forex signal limit reached ({approved_today}/{self.max_signals_per_day})")
                return []
            
            logger.info("🔍 Scanning Forex markets for opportunities...")
            
            all_candidates = []
            symbols = await self.forex_client.get_all_symbols()
            
            # Analyze each Forex pair
            for symbol in symbols:
                try:
                    # Get timeframe-specific signals
                    for timeframe in ['15m', '1h', '4h']:
                        signal = await self.analyze_pair(symbol, timeframe)
                        if signal:
                            all_candidates.append(signal)
                            logger.info(f"📊 Forex candidate: {symbol} {timeframe} (confidence: {signal.confidence:.1f}%)")
                except Exception as e:
                    logger.error(f"Error analyzing Forex pair {symbol}: {e}")
            
            if not all_candidates:
                logger.info("No Forex signals found this scan")
                return []
            
            # Rank and select best signals
            ranked = self.signal_ranker.rank_signals(all_candidates)
            slots_available = self.max_signals_per_day - approved_today
            selected = ranked[:slots_available]
            
            # Filter out correlated pairs
            final_signals = self._filter_correlated_pairs(selected)
            
            # Validate and save
            validated_signals = []
            for signal in final_signals:
                signal.market_type = MarketType.FOREX  # Mark as Forex
                signal.id = str(uuid.uuid4())
                signal.status = SignalStatus.APPROVED  # Auto-approve like crypto
            signal.approved_at = datetime.utcnow()
            
            # Validate
            is_valid, validation_result = await self.validation_pipeline.validate(signal)
            if is_valid:
                signal.grade = validation_result['grade']
                signal.validation_score = validation_result['validation_score']
                signal.validation_breakdown = validation_result['breakdown']
                
                # Save to DB
                if self.db:
                    try:
                        await self.db.save_signal(signal)
                        logger.info(f"💾 Forex signal saved: {signal.symbol} {signal.timeframe}")
                    except Exception as e:
                        logger.error(f"Failed to save Forex signal: {e}")
                
                validated_signals.append(signal)
                self.signals_today.append(signal)
            
            logger.info(f"✅ Generated {len(validated_signals)} Forex signals")
            return validated_signals
    
    async def analyze_pair(self, symbol: str, timeframe: str) -> Optional[TradingSignal]:
        """
        Analyze a Forex pair on a specific timeframe
        Same logic as crypto analysis
        """
        try:
            # Get historical data
            klines = await self.forex_client.get_historical_klines(symbol, timeframe, limit=200)
            if len(klines) < 100:
                return None
            
            current_price = await self.forex_client.get_price(symbol)
            if not current_price:
                return None
            
            # Convert klines to DataFrame for analysis
            import pandas as pd
            df = pd.DataFrame(klines)
            
            # Add technical indicators first (required before scoring)
            df = self.technical_analyzer.add_indicators(df)
            
            # Technical analysis - detect trend first to get direction
            trend = self.technical_analyzer.detect_trend(df)
            if trend['direction'] == 'neutral':
                return None
            direction = SignalDirection.LONG if trend['direction'] == 'bullish' else SignalDirection.SHORT
            
            tech_analysis = self.technical_analyzer.calculate_technical_score(df)
            if not tech_analysis or tech_analysis.total_score < 50:
                return None
            
            # Institutional analysis (calculate score for entry quality)
            entry = df['close'].iloc[-1]
            stop_loss = self.technical_analyzer.calculate_stop_loss(df, direction, entry)
            inst_analysis = self.institutional_analyzer.calculate_institutional_score(df, direction, entry, stop_loss, timeframe)
            
            # Context analysis (news, sentiment) - Forex uses context engine but with basic fallback
            try:
                context = await self.context_engine.analyze_context(symbol, direction.value)
            except Exception as ctx_err:
                logger.warning(f"Context analysis failed for {symbol}: {ctx_err}, using neutral context")
                from src.models.signal import ContextScore
                context = ContextScore(
                    macro_score=50, news_score=50, sentiment_score=50, total_score=50
                )
            
            # Get timeframe strategy
            strategy = self.strategy_factory.get_strategy(timeframe)
            if not strategy:
                return None
            
            # Generate signal candidate
            candidate = await strategy.generate_signal(
                symbol=symbol,
                timeframe=timeframe,
                current_price=current_price,
                technical=tech_analysis,
                institutional=inst_analysis,
                context=context
            )
            
            if not candidate:
                return None
            
            # Calculate conviction score
            conviction_score = await self.conviction_engine.calculate_conviction(
                signal=candidate,
                technical=tech_analysis,
                institutional=inst_analysis,
                context=context
            )
            
            # 🌍 FOREX-SPECIFIC ADJUSTMENTS
            
            # 1. Check for news blackout periods (NFP, FOMC, etc.)
            blackout_check = ForexMarketAdjustments.check_news_blackout(symbol)
            if blackout_check['is_blackout']:
                logger.warning(f"🌍 {symbol}: News blackout - {blackout_check['reason']}")
                return None
            
            # 2. Apply session-based confidence boost/penalty
            original_confidence = candidate.confidence
            candidate.confidence = ForexMarketAdjustments.apply_session_boost(
                candidate.confidence, symbol
            )
            if candidate.confidence != original_confidence:
                logger.info(f"🌍 {symbol}: Session adjustment {original_confidence:.1f}% -> {candidate.confidence:.1f}%")
            
            # 3. Adjust stop loss for Forex volatility (tighter than crypto)
            sl_distance = abs(candidate.entry_price - candidate.stop_loss) / candidate.entry_price
            adjusted_sl_distance = ForexMarketAdjustments.adjust_stop_loss(sl_distance, symbol)
            if candidate.direction == SignalDirection.LONG:
                candidate.stop_loss = candidate.entry_price * (1 - adjusted_sl_distance)
            else:
                candidate.stop_loss = candidate.entry_price * (1 + adjusted_sl_distance)
            
            # 4. Adjust take profit targets for Forex volatility (smaller than crypto)
            for tp_level in ['take_profit_1', 'take_profit_2', 'take_profit_3']:
                tp_value = getattr(candidate, tp_level, None)
                if tp_value:
                    tp_distance = abs(tp_value - candidate.entry_price) / candidate.entry_price
                    adjusted_tp_distance = ForexMarketAdjustments.adjust_take_profit(tp_distance, symbol)
                    if candidate.direction == SignalDirection.LONG:
                        setattr(candidate, tp_level, candidate.entry_price * (1 + adjusted_tp_distance))
                    else:
                        setattr(candidate, tp_level, candidate.entry_price * (1 - adjusted_tp_distance))
            
            # Apply confidence thresholds based on signal mode
            min_conviction = 70 if self.signal_mode == 'aggressive' else 75 if self.signal_mode == 'balanced' else 80
            adjusted_min_conf = self._base_threshold + self._threshold_adjustment
            
            if conviction_score < min_conviction or candidate.confidence < adjusted_min_conf:
                return None
            
            # Create full signal
            signal = TradingSignal(
                symbol=symbol,
                direction=candidate.direction,
                setup_type=candidate.setup_type,
                timeframe=timeframe,
                market_type=MarketType.FOREX,
                entry_price=candidate.entry_price,
                stop_loss=candidate.stop_loss,
                take_profit_1=candidate.take_profit_1,
                take_profit_2=candidate.take_profit_2,
                take_profit_3=candidate.take_profit_3,
                technical_score=candidate.technical_score,
                context_score=candidate.context_score,
                confidence=candidate.confidence,
                conviction_score=conviction_score,
                reasoning=candidate.reasoning,
                risk_reward=candidate.risk_reward,
                atr=tech_analysis.get('atr', 0.0),
                volume_24h=volume_24h,
                market_context=context.get('market_context', ''),
                news_context=context.get('news_context', '')
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing Forex pair {symbol} {timeframe}: {e}")
            return None
    
    def _filter_correlated_pairs(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Filter out correlated Forex pairs to avoid double exposure"""
        if not signals:
            return []
        
        filtered = [signals[0]]  # Always take the best signal
        
        for signal in signals[1:]:
            is_correlated = False
            for existing in filtered:
                if signal.symbol in FOREX_CORRELATION_GROUPS.get(existing.symbol, []):
                    is_correlated = True
                    logger.info(f"⚠️ Skipping {signal.symbol} — correlated with {existing.symbol}")
                    break
            
            if not is_correlated:
                filtered.append(signal)
        
        return filtered
