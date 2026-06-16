"""
CryptoPulse Signals — Forex Signal Engine
Copyright (c) 2026 CryptoPulse Signals. All rights reserved.
Unauthorized copying, distribution, or modification of this software,
via any medium, is strictly prohibited. Proprietary and confidential.

Generates trading signals for major Forex pairs, commodities (XAUUSD), and indices (NAS100).
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
    TradingSignal, SignalDirection, SetupType, SignalStatus, MarketType,
    TechnicalScore, ContextScore
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
        
        # Forex-specific thresholds (different from crypto due to market characteristics)
        self.min_confidence = getattr(settings, 'FOREX_MIN_CONFIDENCE', 75)
        self.min_conviction = getattr(settings, 'FOREX_MIN_CONVICTION', 65)
        self.max_signals_per_day = 3  # Same as crypto: 3 signals/day
        self.min_risk_reward = settings.MIN_RISK_REWARD
        
        # Signal mode
        self.signal_mode = getattr(settings, 'SIGNAL_MODE', 'strict')
        
        # Dynamic threshold adjustment (uses forex-specific base)
        self._signal_history = deque(maxlen=50)
        self._setup_performance = {}
        self._base_threshold = self.min_confidence  # Forex-specific (75 vs crypto 85)
        self._threshold_adjustment = 0.0
        
        # Teaser signals for free channel
        self.teaser_threshold = 60.0
        self.teaser_candidates = []
        self._sent_teasers = set()
        
        # Scan lock to prevent concurrent scans (rate limit protection)
        self._scan_lock = asyncio.Lock()
        self._last_scan_time = None
        self._min_scan_interval = 300  # Minimum 5 MINUTES between scans (was 30s) - saves API calls
        
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
            signals_today_count = len(self.signals_today)
            if signals_today_count >= self.max_signals_per_day:
                logger.info(f"✋ Daily Forex signal limit reached ({signals_today_count}/{self.max_signals_per_day})")
                return []
            
            logger.info(f"🔍 Scanning Forex markets for opportunities... ({len(await self.forex_client.get_all_symbols())} symbols)")
            
            all_candidates = []
            symbols = await self.forex_client.get_all_symbols()
            logger.info(f"🌍 Forex symbols to scan: {', '.join(symbols)}")
            logger.info(f"🎯 Forex thresholds: Conviction ≥ {self.min_conviction}, Confidence ≥ {self.min_confidence}% (vs Crypto: 75/85)")
            
            # Track rejection reasons for analysis
            rejection_stats = {'total_analyzed': 0, 'passed_threshold': 0, 'rejected_conviction': 0, 'rejected_confidence': 0}
            
            # OPTIMIZATION: Only scan 1h and 4h for Forex (skip 15m to save API calls)
            # Forex moves slower than crypto - 1h/4h are sufficient for quality signals
            for symbol in symbols:
                try:
                    # Get timeframe-specific signals (skip 15m to save API calls)
                    for timeframe in ['1h', '4h']:
                        signal = await self.analyze_pair(symbol, timeframe)
                        if signal:
                            all_candidates.append(signal)
                            logger.info(f"📊 Forex candidate: {symbol} {timeframe} (confidence: {signal.confidence:.1f}%)")
                        # Small delay between timeframes to avoid burst requests
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error analyzing Forex pair {symbol}: {e}")
                # Delay between symbols to respect rate limits
                await asyncio.sleep(1)
            
            if not all_candidates:
                logger.info("No Forex signals found this scan")
                return []
            
            # Rank and select best signals
            ranked = self.signal_ranker.rank_signals(all_candidates)
            slots_available = self.max_signals_per_day - signals_today_count
            selected = ranked[:slots_available]
            
            # Filter out correlated pairs
            final_signals = self._filter_correlated_pairs(selected)
            
            # Validate and save
            validated_signals = []
            for signal in final_signals:
                signal.market_type = MarketType.FOREX  # Mark as Forex
                signal.id = str(uuid.uuid4())
                signal.status = SignalStatus.PENDING  # Send to admin for approval (same as crypto)
                
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
            
            # Context analysis (news, sentiment, DXY, risk appetite)
            try:
                context = await self.context_engine.analyze_context(symbol, direction.value, forex_client=self.forex_client)
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
            
            # 1. Session check
            if strategy.session_required:
                session_ok, session_msg = strategy.is_valid_session(df)
                if not session_ok:
                    logger.debug(f"⏰ {symbol} {timeframe}: {session_msg}")
                    return None
            
            # 2. Volatility check
            vol_ok, vol_msg = strategy.analyze_volatility(df)
            if not vol_ok:
                logger.debug(f"📊 {symbol} {timeframe}: {vol_msg}")
                return None
            
            # 3. Find setup using strategy
            setup = strategy.find_setup(df, direction)
            if not setup:
                return None
            
            # 4. Calculate entry/SL/TP using strategy
            entry_price, stop_loss, tp1, tp2, tp3 = strategy.calculate_entry_sl_tp(
                df, setup, direction
            )
            
            # 5. Calculate risk:reward
            risk_reward = abs(tp1 - entry_price) / abs(entry_price - stop_loss)
            if risk_reward < strategy.min_risk_reward:
                logger.debug(f"📊 {symbol} {timeframe}: R:R {risk_reward:.1f} < {strategy.min_risk_reward}")
                return None
            
            # 🌍 FOREX-SPECIFIC ADJUSTMENTS
            
            # Check for news blackout periods (NFP, FOMC, etc.)
            blackout_check = ForexMarketAdjustments.check_news_blackout(symbol)
            if blackout_check['is_blackout']:
                logger.warning(f"🌍 {symbol}: News blackout - {blackout_check['reason']}")
                return None
            
            # Apply session-based confidence boost/penalty
            confidence = inst_analysis.total_score
            original_confidence = confidence
            confidence = ForexMarketAdjustments.apply_session_boost(confidence, symbol)
            if confidence != original_confidence:
                logger.info(f"🌍 {symbol}: Session adjustment {original_confidence:.1f}% -> {confidence:.1f}%")
            
            # Adjust stop loss for Forex volatility (tighter than crypto)
            sl_distance = abs(entry_price - stop_loss) / entry_price
            adjusted_sl_distance = ForexMarketAdjustments.adjust_stop_loss(sl_distance, symbol)
            if direction == SignalDirection.LONG:
                stop_loss = entry_price * (1 - adjusted_sl_distance)
            else:
                stop_loss = entry_price * (1 + adjusted_sl_distance)
            
            # Adjust take profit targets for Forex volatility (smaller than crypto)
            def adjust_tp(tp_value):
                if not tp_value:
                    return tp_value
                tp_distance = abs(tp_value - entry_price) / entry_price
                adjusted_tp_distance = ForexMarketAdjustments.adjust_take_profit(tp_distance, symbol)
                if direction == SignalDirection.LONG:
                    return entry_price * (1 + adjusted_tp_distance)
                else:
                    return entry_price * (1 - adjusted_tp_distance)
            
            tp1 = adjust_tp(tp1)
            tp2 = adjust_tp(tp2)
            tp3 = adjust_tp(tp3)
            
            # Recalculate R:R after adjustments
            risk_reward = abs(tp1 - entry_price) / abs(entry_price - stop_loss)
            
            # Calculate conviction score
            # Build a temporary candidate for conviction engine
            from dataclasses import dataclass
            @dataclass
            class SignalCandidate:
                direction: SignalDirection
                setup_type: SetupType
                entry_price: float
                stop_loss: float
                take_profit_1: float
                take_profit_2: float
                take_profit_3: float
                confidence: float
                technical_score: float
                context_score: float
                risk_reward: float
                reasoning: str
            
            candidate = SignalCandidate(
                direction=direction,
                setup_type=SetupType(setup.get('setup_type', 'breakout')),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                confidence=confidence,
                technical_score=tech_analysis.total_score,
                context_score=context.total_score,
                risk_reward=risk_reward,
                reasoning=setup.get('reasoning', f"{timeframe} {setup.get('setup_type', 'breakout')} setup")
            )
            
            conviction_score = await self.conviction_engine.calculate_conviction(
                signal=candidate,
                technical=tech_analysis,
                institutional=inst_analysis,
                context=context
            )
            
            # Apply FOREX-SPECIFIC confidence thresholds (lower than crypto due to market characteristics)
            # Forex: 65/75 (conviction/confidence) vs Crypto: 75/85
            # This accounts for lower volatility and different context scoring in forex markets
            min_conviction = self.min_conviction  # 65 for forex (vs 75 for crypto)
            adjusted_min_conf = self._base_threshold + self._threshold_adjustment  # 75 for forex (vs 85 for crypto)
            
            if conviction_score < min_conviction or confidence < adjusted_min_conf:
                logger.info(f"❌ {symbol} {timeframe}: Conviction {conviction_score:.1f} < {min_conviction} OR Confidence {confidence:.1f}% < {adjusted_min_conf}% (Forex thresholds)")
                return None
            
            logger.info(f"✅ {symbol} {timeframe}: PASSED forex thresholds - Conviction {conviction_score:.1f} ≥ {min_conviction}, Confidence {confidence:.1f}% ≥ {adjusted_min_conf}%")
            
            # Build TechnicalScore object if needed
            if isinstance(tech_analysis, dict):
                tech_score_obj = TechnicalScore(
                    trend_score=tech_analysis.get('trend_score', 50),
                    volume_score=tech_analysis.get('volume_score', 50),
                    momentum_score=tech_analysis.get('momentum_score', 50),
                    structure_score=tech_analysis.get('structure_score', 50),
                    total_score=tech_analysis.get('total_score', 50)
                )
            else:
                tech_score_obj = tech_analysis
            
            # Build ContextScore object if needed
            if isinstance(context, dict):
                context_score_obj = ContextScore(
                    macro_score=context.get('macro_score', 50),
                    news_score=context.get('news_score', 50),
                    sentiment_score=context.get('sentiment_score', 50),
                    total_score=context.get('total_score', 50)
                )
            else:
                context_score_obj = context
            
            # Create full signal
            signal = TradingSignal(
                symbol=symbol,
                direction=direction,
                setup_type=SetupType(setup.get('setup_type', 'breakout')),
                timeframe=timeframe,
                market_type=MarketType.FOREX,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                technical_score=tech_score_obj,
                context_score=context_score_obj,
                confidence=confidence,
                conviction_score=conviction_score,
                reasoning=candidate.reasoning,
                risk_reward=risk_reward,
                atr=getattr(tech_analysis, 'atr', 0.0) if hasattr(tech_analysis, 'atr') else 0.0,
                volume_24h=volume_24h,
                market_context=getattr(context, 'market_context', '') if hasattr(context, 'market_context') else '',
                news_context=getattr(context, 'news_context', '') if hasattr(context, 'news_context') else ''
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
