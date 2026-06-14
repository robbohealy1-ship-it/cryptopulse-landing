"""
CryptoPulse Signals — Active Trade Management Engine
Copyright (c) 2026 CryptoPulse Signals. All rights reserved.

Monitors active/running trades and generates real-time management
recommendations (scale out, close early, move stop, add, trail)
based on live technicals, news, structure, and momentum.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

import pandas as pd

from src.models.signal import TradingSignal, SignalStatus, SignalDirection, MarketType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradeAction(str, Enum):
    HOLD = "hold"
    SCALE_OUT_PARTIAL = "scale_out_partial"  # Close 25-50%
    SCALE_OUT_MAJOR = "scale_out_major"  # Close 50-75%
    CLOSE_FULL = "close_full"  # Close 100%
    ADD = "add"
    MOVE_STOP = "move_stop"
    TRAILING_STOP = "trailing_stop"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TradeRecommendation:
    signal_id: str
    symbol: str
    action: TradeAction
    confidence: float  # 0-100
    urgency: Urgency
    reasoning: str
    current_pnl_percent: float
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    distance_to_tp1_percent: float
    distance_to_sl_percent: float
    rsi: Optional[float] = None
    trend_direction: Optional[str] = None
    trend_strength: Optional[float] = None
    news_sentiment: Optional[str] = None
    structure_note: Optional[str] = None
    suggested_stop_price: Optional[float] = None
    suggested_scale_percent: Optional[float] = None  # e.g. 50 for scale out 50%
    
    # Enhanced reasoning fields
    reversal_signals: List[str] = field(default_factory=list)
    momentum_analysis: Optional[str] = None
    volume_analysis: Optional[str] = None
    resistance_support_note: Optional[str] = None
    risk_reward_note: Optional[str] = None
    action_description: Optional[str] = None  # Clear description of what to do
    
    # Futures-specific fields (perpetual contracts)
    funding_rate_pct: Optional[float] = None
    oi_trend: Optional[str] = None
    liquidation_note: Optional[str] = None
    is_futures: bool = True  # All crypto trades on Binance are perpetual futures
    
    created_at: datetime = field(default_factory=datetime.utcnow)


class TradeManagementEngine:
    """
    Analyzes active trades in real-time and generates management recommendations.

    Uses live price data, technical indicators (RSI, MACD divergence, EMAs),
    market structure (higher highs/lows), news sentiment, and momentum
    to suggest when to scale out, close, trail, or add to a position.
    """

    def __init__(self, scanner, technical_analyzer, context_engine=None):
        self.scanner = scanner
        self.technical_analyzer = technical_analyzer
        self.context_engine = context_engine
        self._cache: Dict[str, Tuple[datetime, TradeRecommendation]] = {}
        self._cache_ttl = timedelta(seconds=30)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze_trade(self, signal: TradingSignal) -> Optional[TradeRecommendation]:
        """Generate a management recommendation for a single active trade."""
        try:
            # Cache hit?
            cached = self._cache.get(signal.id)
            if cached and (datetime.utcnow() - cached[0]) < self._cache_ttl:
                return cached[1]

            rec = await self._build_recommendation(signal)
            if rec:
                self._cache[signal.id] = (datetime.utcnow(), rec)
            return rec
        except Exception as e:
            logger.error(f"Trade management analysis failed for {signal.symbol}: {e}")
            return None

    async def analyze_all(self, signals: List[TradingSignal]) -> List[TradeRecommendation]:
        """Batch analyze multiple active trades."""
        tasks = [self.analyze_trade(s) for s in signals]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, TradeRecommendation)]

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    async def _build_recommendation(self, signal: TradingSignal) -> Optional[TradeRecommendation]:
        # Skip if partial close already executed
        if hasattr(signal, 'metadata') and signal.metadata:
            remaining = signal.metadata.get('remaining_position', 100)
            if remaining < 100:
                logger.info(f"Skipping trade management for {signal.symbol} — partial close already executed ({remaining}% remaining)")
                return None
        
        # Skip Forex symbols (Binance scanner doesn't support them)
        # DEFENSE: Also detect by exact symbol in case market_type was incorrectly saved as CRYPTO
        KNOWN_FOREX = {'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD', 'XAU/USD'}
        is_forex_symbol = (
            (hasattr(signal, 'market_type') and signal.market_type == MarketType.FOREX) or
            signal.symbol in KNOWN_FOREX or
            signal.symbol.startswith('XAU/')
        )
        if is_forex_symbol:
            logger.debug(f"Skipping trade management for Forex symbol {signal.symbol} (not supported by Binance scanner)")
            return None
        
        # Fetch live price
        ticker = await self.scanner.fetch_ticker(signal.symbol)
        current_price = ticker.get("last", 0) if ticker else 0
        if not current_price or current_price <= 0:
            logger.warning(f"No price for {signal.symbol}, skipping trade management")
            return None

        entry = signal.actual_entry or signal.entry_price
        direction = signal.direction
        is_long = direction.value == "LONG"

        # P&L
        if is_long:
            pnl = ((current_price - entry) / entry) * 100
        else:
            pnl = ((entry - current_price) / entry) * 100

        # Distance to targets
        dist_tp1 = abs((signal.take_profit_1 - current_price) / current_price) * 100
        dist_sl = abs((signal.stop_loss - current_price) / current_price) * 100

        # Technicals
        tech = await self._fetch_technicals(signal.symbol, signal.timeframe)
        rsi = tech.get("rsi")
        macd_bullish = tech.get("macd_bullish")
        macd_bearish = tech.get("macd_bearish")
        above_ema20 = tech.get("above_ema20")
        above_ema50 = tech.get("above_ema50")
        volume_spike = tech.get("volume_spike")
        bb_position = tech.get("bb_position")

        # Structure
        structure = await self._analyze_structure(signal.symbol, signal.timeframe, is_long)
        higher_highs = structure.get("higher_highs", False)
        higher_lows = structure.get("higher_lows", False)
        lower_highs = structure.get("lower_highs", False)
        lower_lows = structure.get("lower_lows", False)

        # Context (news + sentiment) — optional, don't fail if missing
        context = await self._fetch_context(signal.symbol)
        news_sentiment = context.get("sentiment", "neutral")
        funding_bias = context.get("funding_bias", "neutral")
        whale_pressure = context.get("whale_pressure", "neutral")

        # -------------------- Decision logic --------------------
        action = TradeAction.HOLD
        confidence = 50.0
        urgency = Urgency.LOW
        reasoning_parts: List[str] = []
        suggested_stop: Optional[float] = None
        suggested_scale: Optional[float] = None

        # 1. CRITICAL — close early if reversal structure + bad context
        reversal_score = 0
        if is_long:
            if lower_highs and lower_lows:
                reversal_score += 40
            if macd_bearish:
                reversal_score += 20
            if rsi and rsi > 70:
                reversal_score += 15
            if not above_ema20:
                reversal_score += 15
            if news_sentiment == "negative":
                reversal_score += 10
        else:  # SHORT
            if higher_highs and higher_lows:
                reversal_score += 40
            if macd_bullish:
                reversal_score += 20
            if rsi and rsi < 30:
                reversal_score += 15
            if above_ema20:
                reversal_score += 15
            if news_sentiment == "positive":
                reversal_score += 10

        reversal_signals = []
        momentum_note = ""
        volume_note = ""
        
        if reversal_score >= 80:
            # FULL CLOSE — strong reversal confirmed
            action = TradeAction.CLOSE_FULL
            suggested_scale = 100.0
            confidence = min(reversal_score, 95)
            urgency = Urgency.CRITICAL
            
            if is_long:
                if lower_highs and lower_lows:
                    reversal_signals.append("Lower highs AND lower lows forming — clear downtrend")
                if macd_bearish:
                    reversal_signals.append("MACD bearish crossover — momentum reversing")
                if rsi and rsi > 70:
                    reversal_signals.append(f"RSI overbought at {rsi:.1f} — exhaustion signal")
                if not above_ema20:
                    reversal_signals.append("Price broke below EMA20 — trend broken")
            else:
                if higher_highs and higher_lows:
                    reversal_signals.append("Higher highs AND higher lows forming — clear uptrend")
                if macd_bullish:
                    reversal_signals.append("MACD bullish crossover — momentum reversing")
                if rsi and rsi < 30:
                    reversal_signals.append(f"RSI oversold at {rsi:.1f} — bounce imminent")
                if above_ema20:
                    reversal_signals.append("Price broke above EMA20 — trend broken")
            
            reasoning_parts.append(f"FULL CLOSE RECOMMENDED (100% position)")
            reasoning_parts.append(f"Reversal score: {reversal_score}/100 — Strong reversal confirmed")
            
        elif reversal_score >= 60:
            # MAJOR SCALE OUT — reversal likely, reduce exposure
            action = TradeAction.SCALE_OUT_MAJOR
            suggested_scale = 75.0
            confidence = min(reversal_score, 90)
            urgency = Urgency.HIGH
            
            if is_long and lower_highs:
                reversal_signals.append("Lower highs forming — uptrend weakening")
            elif not is_long and higher_lows:
                reversal_signals.append("Higher lows forming — downtrend weakening")
            if macd_bearish if is_long else macd_bullish:
                reversal_signals.append("MACD divergence detected — early reversal warning")
            
            reasoning_parts.append(f"PARTIAL CLOSE RECOMMENDED (75% position)")
            reasoning_parts.append(f"Reversal score: {reversal_score}/100 — Reversal probable, reduce risk")

        # 2. SCALE OUT — approaching TP with weakening momentum
        elif dist_tp1 < 1.5 and pnl > 0:
            scale_score = 0
            if is_long:
                if rsi and rsi > 65:
                    scale_score += 25
                if not volume_spike:
                    scale_score += 20
                if lower_highs:
                    scale_score += 20
                if bb_position == "upper":
                    scale_score += 15
            else:
                if rsi and rsi < 35:
                    scale_score += 25
                if not volume_spike:
                    scale_score += 20
                if higher_lows:
                    scale_score += 20
                if bb_position == "lower":
                    scale_score += 15

            if scale_score >= 60:
                # MAJOR SCALE OUT — near target with weak momentum
                action = TradeAction.SCALE_OUT_MAJOR
                suggested_scale = 70.0
                confidence = min(50 + scale_score / 2, 90)
                urgency = Urgency.HIGH
                reasoning_parts.append(f"PARTIAL CLOSE RECOMMENDED (70% position)")
                reasoning_parts.append(f"Within {dist_tp1:.1f}% of TP1 — lock in most profits")
            elif scale_score >= 40:
                # PARTIAL SCALE OUT — take some profit
                action = TradeAction.SCALE_OUT_PARTIAL
                suggested_scale = 50.0
                confidence = min(50 + scale_score / 2, 85)
                urgency = Urgency.MEDIUM
                reasoning_parts.append(f"PARTIAL CLOSE RECOMMENDED (50% position)")
                reasoning_parts.append(f"Within {dist_tp1:.1f}% of TP1 — secure partial profits")
            
            if scale_score >= 40:
                if rsi:
                    if is_long and rsi > 65:
                        momentum_note = f"RSI overbought at {rsi:.1f} — upside momentum fading"
                    elif not is_long and rsi < 35:
                        momentum_note = f"RSI oversold at {rsi:.1f} — downside momentum fading"
                if not volume_spike:
                    volume_note = "Volume declining — momentum weakening"
                if is_long and lower_highs:
                    reasoning_parts.append("Lower highs appearing — trend losing strength")
                elif not is_long and higher_lows:
                    reasoning_parts.append("Higher lows appearing — trend losing strength")

        # 3. MOVE STOP TO BREAKEVEN — price has moved favorably 1.5x risk or more
        elif not signal.stop_moved_to_breakeven and pnl > 0:
            risk = abs(entry - signal.stop_loss)
            reward_so_far = abs(current_price - entry)
            if risk > 0 and reward_so_far >= risk * 1.5:
                action = TradeAction.MOVE_STOP
                suggested_stop = entry
                confidence = 85.0
                urgency = Urgency.MEDIUM
                reasoning_parts.append(f"Price moved {reward_so_far / risk:.1f}x risk in favor — lock in breakeven")
                if is_long and higher_lows:
                    reasoning_parts.append("Higher lows intact — trend healthy but protect capital")
                elif not is_long and lower_highs:
                    reasoning_parts.append("Lower highs intact — trend healthy but protect capital")

        # 4. TRAILING STOP — strong trend, let winners run after TP1 hit
        elif signal.tp1_hit and not signal.tp2_hit and pnl > 0:
            trail_score = 0
            if is_long:
                if higher_highs and higher_lows:
                    trail_score += 30
                if volume_spike:
                    trail_score += 20
                if macd_bullish:
                    trail_score += 15
                if above_ema50:
                    trail_score += 15
                if news_sentiment == "positive":
                    trail_score += 10
            else:
                if lower_highs and lower_lows:
                    trail_score += 30
                if volume_spike:
                    trail_score += 20
                if macd_bearish:
                    trail_score += 15
                if not above_ema50:
                    trail_score += 15
                if news_sentiment == "negative":
                    trail_score += 10

            if trail_score >= 50:
                action = TradeAction.TRAILING_STOP
                # Suggest trailing at last swing low/high — simplified to ATR-based
                atr = tech.get("atr", entry * 0.02)
                if is_long:
                    suggested_stop = current_price - (atr * 2)
                else:
                    suggested_stop = current_price + (atr * 2)
                confidence = min(50 + trail_score / 2, 90)
                urgency = Urgency.MEDIUM
                reasoning_parts.append(f"Strong trend continuation after TP1 (score {trail_score})")
                reasoning_parts.append(f"Trail stop at ~{atr * 2 / current_price * 100:.1f}% ATR buffer")

        # 5. ADD TO POSITION — pullback to key support/resistance with confirmation
        elif pnl < -0.5 and pnl > -2.0:
            add_score = 0
            if is_long:
                if above_ema20 and above_ema50:
                    add_score += 25
                if higher_lows:
                    add_score += 25
                if volume_spike:
                    add_score += 20
                if macd_bullish:
                    add_score += 15
                if news_sentiment == "positive":
                    add_score += 10
            else:
                if not above_ema20 and not above_ema50:
                    add_score += 25
                if lower_highs:
                    add_score += 25
                if volume_spike:
                    add_score += 20
                if macd_bearish:
                    add_score += 15
                if news_sentiment == "negative":
                    add_score += 10

            if add_score >= 60:
                action = TradeAction.ADD
                confidence = min(add_score, 85)
                urgency = Urgency.LOW
                reasoning_parts.append(f"Pullback to support with confirmation (score {add_score})")
                reasoning_parts.append("Consider DCA at current level — trend structure intact")

        # 6. Default HOLD with context
        else:
            if pnl > 0:
                reasoning_parts.append(f"Trade in profit (+{pnl:.1f}%) — no action needed")
                if is_long and higher_highs:
                    reasoning_parts.append("Higher highs intact — bullish structure")
                elif not is_long and lower_lows:
                    reasoning_parts.append("Lower lows intact — bearish structure")
            else:
                reasoning_parts.append(f"Trade underwater ({pnl:.1f}%) — within normal fluctuation")
                if dist_sl < 2.0:
                    urgency = Urgency.HIGH
                    reasoning_parts.append(f"⚠️ Only {dist_sl:.1f}% from stop loss — monitor closely")

            confidence = 60.0
            if tech.get("trend_strength"):
                confidence = min(60 + tech["trend_strength"] / 5, 90)

        # Funding / whale / futures context
        funding_rate_pct = context.get("funding_rate_pct")
        oi_trend = context.get("oi_trend")
        liquidation_note = context.get("liquidation_note")
        
        if funding_bias != "neutral":
            reasoning_parts.append(f"Funding: {funding_bias}")
        if whale_pressure != "neutral":
            reasoning_parts.append(f"Whales: {whale_pressure}")
        if funding_rate_pct is not None:
            reasoning_parts.append(f"Funding rate: {funding_rate_pct:.4f}% (perpetual futures)")
        if oi_trend:
            oi_label = {"rising_oi": "Open Interest rising — fresh money entering", "falling_oi": "Open Interest falling — positions closing", "stable_oi": "Open Interest stable"}
            reasoning_parts.append(oi_label.get(oi_trend, oi_trend))
        if liquidation_note:
            reasoning_parts.append(liquidation_note)

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "No significant signals — hold position"
        
        # Build action description
        action_desc = self._build_action_description(action, suggested_scale, pnl, current_price, entry, signal.stop_loss)
        
        # Build resistance/support note
        resistance_note = None
        if dist_tp1 < 3.0:
            resistance_note = f"Approaching TP1 resistance at ${signal.take_profit_1:.6f} ({dist_tp1:.1f}% away)"
        elif dist_sl < 3.0:
            resistance_note = f"⚠️ Near stop loss support at ${signal.stop_loss:.6f} ({dist_sl:.1f}% away)"
        
        # Build risk/reward note
        rr_note = None
        if suggested_scale and suggested_scale < 100:
            locked_profit = pnl * (suggested_scale / 100)
            rr_note = f"Locking in +{locked_profit:.1f}% profit on {suggested_scale:.0f}% of position"
        elif action == TradeAction.CLOSE_FULL:
            rr_note = f"Closing full position at +{pnl:.1f}% profit"

        return TradeRecommendation(
            signal_id=signal.id,
            symbol=signal.symbol,
            action=action,
            confidence=round(confidence, 1),
            urgency=urgency,
            reasoning=reasoning,
            current_pnl_percent=round(pnl, 2),
            current_price=round(current_price, 6),
            entry_price=round(entry, 6),
            stop_loss=round(signal.stop_loss, 6),
            take_profit_1=round(signal.take_profit_1, 6),
            take_profit_2=round(signal.take_profit_2, 6) if signal.take_profit_2 else None,
            take_profit_3=round(signal.take_profit_3, 6) if signal.take_profit_3 else None,
            distance_to_tp1_percent=round(dist_tp1, 2),
            distance_to_sl_percent=round(dist_sl, 2),
            rsi=round(rsi, 1) if rsi else None,
            trend_direction=tech.get("trend_direction"),
            trend_strength=round(tech.get("trend_strength", 0), 1) if tech.get("trend_strength") else None,
            news_sentiment=news_sentiment,
            structure_note=structure.get("note"),
            suggested_stop_price=round(suggested_stop, 6) if suggested_stop else None,
            suggested_scale_percent=suggested_scale,
            reversal_signals=reversal_signals,
            momentum_analysis=momentum_note if momentum_note else None,
            volume_analysis=volume_note if volume_note else None,
            resistance_support_note=resistance_note,
            risk_reward_note=rr_note,
            action_description=action_desc,
            funding_rate_pct=funding_rate_pct,
            oi_trend=oi_trend,
            liquidation_note=liquidation_note,
            is_futures=not is_forex_symbol,
        )

    # ------------------------------------------------------------------
    # Data fetching helpers
    # ------------------------------------------------------------------

    async def _fetch_technicals(self, symbol: str, timeframe: str) -> Dict:
        """Fetch and compute technical indicators for a symbol."""
        result = {
            "rsi": None,
            "macd_bullish": False,
            "macd_bearish": False,
            "above_ema20": False,
            "above_ema50": False,
            "volume_spike": False,
            "bb_position": "middle",
            "atr": None,
            "trend_direction": "neutral",
            "trend_strength": 0,
        }
        try:
            df = await self.scanner.fetch_ohlcv(symbol, timeframe, limit=100)
            if df is None or len(df) < 30:
                return result

            df = self.technical_analyzer.add_indicators(df)
            if len(df) < 5:
                return result

            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last

            result["rsi"] = last.get("rsi")
            result["atr"] = last.get("atr")

            # MACD divergence / crossover
            if "macd" in df.columns and "macd_signal" in df.columns:
                result["macd_bullish"] = last["macd"] > last["macd_signal"] and prev.get("macd", 0) <= prev.get("macd_signal", 0)
                result["macd_bearish"] = last["macd"] < last["macd_signal"] and prev.get("macd", 0) >= prev.get("macd_signal", 0)

            # EMA positioning
            price = last["close"]
            result["above_ema20"] = price > last.get("ema_20", price)
            result["above_ema50"] = price > last.get("ema_50", price)

            # Volume spike (>1.5x average)
            if "volume_ratio" in df.columns:
                result["volume_spike"] = last.get("volume_ratio", 1) > 1.5

            # Bollinger position
            if "bb_upper" in df.columns and "bb_lower" in df.columns:
                upper = last["bb_upper"]
                lower = last["bb_lower"]
                if price >= upper * 0.995:
                    result["bb_position"] = "upper"
                elif price <= lower * 1.005:
                    result["bb_position"] = "lower"
                else:
                    result["bb_position"] = "middle"

            # Trend detection
            trend = self.technical_analyzer.detect_trend(df)
            result["trend_direction"] = trend.get("direction", "neutral")
            result["trend_strength"] = trend.get("strength", 0)

        except Exception as e:
            logger.warning(f"Technical fetch failed for {symbol}: {e}")
        return result

    async def _analyze_structure(self, symbol: str, timeframe: str, is_long: bool) -> Dict:
        """Detect market structure (higher highs/lows or lower highs/lows)."""
        result = {"higher_highs": False, "higher_lows": False, "lower_highs": False, "lower_lows": False, "note": None}
        try:
            df = await self.scanner.fetch_ohlcv(symbol, timeframe, limit=50)
            if df is None or len(df) < 20:
                return result

            highs = df["high"].values
            lows = df["low"].values

            # Simple swing detection using last 10 candles
            recent_highs = highs[-10:]
            recent_lows = lows[-10:]

            hh = recent_highs[-1] > max(recent_highs[:-1])
            hl = recent_lows[-1] > min(recent_lows[:-1])
            lh = recent_highs[-1] < max(recent_highs[:-1])
            ll = recent_lows[-1] < min(recent_lows[:-1])

            result["higher_highs"] = hh
            result["higher_lows"] = hl
            result["lower_highs"] = lh
            result["lower_lows"] = ll

            if hh and hl:
                result["note"] = "Bullish structure: HH + HL"
            elif lh and ll:
                result["note"] = "Bearish structure: LH + LL"
            elif hh and ll:
                result["note"] = "Consolidation: mixed structure"
            else:
                result["note"] = "No clear structure"

        except Exception as e:
            logger.warning(f"Structure analysis failed for {symbol}: {e}")
        return result

    async def _fetch_context(self, symbol: str) -> Dict:
        """Fetch news sentiment, funding bias, whale pressure, open interest, and liquidations."""
        result = {
            "sentiment": "neutral",
            "funding_bias": "neutral",
            "whale_pressure": "neutral",
            "funding_rate_pct": None,
            "oi_trend": None,
            "liquidation_note": None,
        }
        if not self.context_engine:
            return result

        try:
            # News / sentiment
            ctx = await self.context_engine.analyze_context(symbol, "1h")
            if ctx:
                score = getattr(ctx, "total_score", 50)
                if score > 60:
                    result["sentiment"] = "positive"
                elif score < 40:
                    result["sentiment"] = "negative"
                else:
                    result["sentiment"] = "neutral"

            # Funding rate (perpetual futures)
            try:
                # Normalize symbol for Binance futures API
                base_symbol = symbol.replace('/', '')
                if not base_symbol.endswith('USDT'):
                    base_symbol += 'USDT'
                
                funding = await self.context_engine.fetch_funding_rates(base_symbol)
                if funding:
                    rate = funding.get("funding_rate", 0)
                    result["funding_rate_pct"] = rate * 100
                    if rate > 0.001:
                        result["funding_bias"] = "expensive_longs"
                    elif rate < -0.001:
                        result["funding_bias"] = "expensive_shorts"
                    else:
                        result["funding_bias"] = "neutral"
            except Exception:
                pass

            # Open Interest (perpetual futures)
            try:
                base_symbol = symbol.replace('/', '')
                if not base_symbol.endswith('USDT'):
                    base_symbol += 'USDT'
                oi = await self.context_engine.fetch_open_interest(base_symbol)
                if oi:
                    oi_change = oi.get('oi_change_24h', 0)
                    high_oi = oi.get('high_oi', False)
                    if oi_change > 5:
                        result["oi_trend"] = "rising_oi"
                    elif oi_change < -5:
                        result["oi_trend"] = "falling_oi"
                    else:
                        result["oi_trend"] = "stable_oi"
                    result["high_oi"] = high_oi
            except Exception:
                pass

            # Liquidations (perpetual futures)
            try:
                base_symbol = symbol.replace('/', '')
                if not base_symbol.endswith('USDT'):
                    base_symbol += 'USDT'
                liq = await self.context_engine.fetch_liquidations(base_symbol)
                if liq:
                    bias = liq.get("bias", "neutral")
                    if bias in ["bullish", "long_liquidation_dominant"]:
                        result["liquidation_note"] = "High long liquidations — potential short-term bottom"
                    elif bias in ["bearish", "short_liquidation_dominant"]:
                        result["liquidation_note"] = "High short liquidations — potential short-term top"
            except Exception:
                pass

            # Whale activity
            try:
                whale = await self.context_engine.whale_monitor.check_symbol(symbol)
                if whale and whale.alerts:
                    buy_pressure = sum(1 for a in whale.alerts if getattr(a, "side", "") == "buy")
                    sell_pressure = sum(1 for a in whale.alerts if getattr(a, "side", "") == "sell")
                    if buy_pressure > sell_pressure * 1.5:
                        result["whale_pressure"] = "accumulating"
                    elif sell_pressure > buy_pressure * 1.5:
                        result["whale_pressure"] = "distributing"
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Context fetch failed for {symbol}: {e}")
        return result

    def _build_action_description(
        self, action: TradeAction, scale_percent: Optional[float], pnl: float, 
        current_price: float, entry: float, sl: float
    ) -> str:
        """Build clear, actionable description for the recommended action."""
        if action == TradeAction.CLOSE_FULL:
            return (
                f"CLOSE 100% OF POSITION NOW at ${current_price:.6f}. "
                f"Lock in +{pnl:.1f}% profit. Strong reversal signals detected — exit immediately to protect gains."
            )
        elif action == TradeAction.SCALE_OUT_MAJOR:
            remaining = 100 - (scale_percent or 75)
            locked = pnl * ((scale_percent or 75) / 100)
            return (
                f"CLOSE {scale_percent:.0f}% OF POSITION at ${current_price:.6f}. "
                f"Lock in +{locked:.1f}% profit. Keep {remaining:.0f}% running with stop at breakeven. "
                f"Reversal probable — reduce risk while maintaining upside exposure."
            )
        elif action == TradeAction.SCALE_OUT_PARTIAL:
            remaining = 100 - (scale_percent or 50)
            locked = pnl * ((scale_percent or 50) / 100)
            return (
                f"CLOSE {scale_percent:.0f}% OF POSITION at ${current_price:.6f}. "
                f"Secure +{locked:.1f}% profit. Keep {remaining:.0f}% for TP2/TP3. "
                f"Near target with weakening momentum — take partial profits."
            )
        elif action == TradeAction.MOVE_STOP:
            return (
                f"MOVE STOP LOSS TO BREAKEVEN at ${entry:.6f}. "
                f"Trade is +{pnl:.1f}% in profit. Lock in risk-free position while allowing further upside."
            )
        elif action == TradeAction.TRAILING_STOP:
            return (
                f"IMPLEMENT TRAILING STOP at ${sl:.6f} (2x ATR buffer). "
                f"Strong trend continuation — let winners run while protecting gains."
            )
        elif action == TradeAction.ADD:
            return (
                f"CONSIDER ADDING TO POSITION at ${current_price:.6f}. "
                f"Healthy pullback to support with confirmation. DCA opportunity — trend structure intact."
            )
        else:  # HOLD
            if pnl > 0:
                return f"HOLD POSITION. Trade +{pnl:.1f}% in profit. No action needed — trend intact."
            else:
                return f"HOLD POSITION. Trade {pnl:.1f}% underwater. Within normal fluctuation — wait for setup."
