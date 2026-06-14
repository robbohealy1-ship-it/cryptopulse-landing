"""
CryptoPulse Signals — Sniper Signal Engine (Pine Script Implementation)
Copyright (c) 2026 CryptoPulse Signals. All rights reserved.

Based on OMAR NASR sniper strategy:
- EMA21 crossover for entry signals
- Pivot structure detection (HH/HL/LH/LL)
- ATR-based TP/SL calculation
- High-volume zone confirmation
- Focus on 1H, 4H, Daily (15m only if score >95)
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from src.models.signal import (
    TradingSignal, SignalDirection, SetupType, TechnicalScore,
    ContextScore, SignalStatus, MarketType
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PivotPoint:
    """Represents a pivot high or low with structure label"""
    bar_index: int
    price: float
    is_high: bool  # True for pivot high, False for pivot low
    label: str  # HH, HL, LH, LL
    volume_confirmed: bool


@dataclass
class StructureZone:
    """Supply/demand zone from pivot points"""
    top: float
    bottom: float
    is_supply: bool  # True for supply (resistance), False for demand (support)
    created_at: int  # bar index


class SniperSignalEngine:
    """
    Pine Script-based signal engine using EMA21 crossovers and structure.
    
    Strategy:
    - BUY: Price crosses above EMA21 + bullish structure (HL/HH)
    - SELL: Price crosses below EMA21 + bearish structure (LH/LL)
    - TP/SL calculated using ATR multiples
    - Only high-volume pivots create zones
    """

    def __init__(self, scanner, technical_analyzer, context_engine=None, db=None):
        self.scanner = scanner
        self.technical_analyzer = technical_analyzer
        self.context_engine = context_engine
        self.db = db

        # Pine Script parameters
        self.left_bars = 10
        self.right_bars = 10
        self.ema_period = 21
        self.atr_length = 14
        self.max_zones = 2

        # TP/SL ATR multipliers (from Pine Script)
        self.tp1_mult = 1.5
        self.tp2_mult = 2.5
        self.tp3_mult = 4.0
        self.sl_mult = 2.0

        # Timeframe priorities (focus on higher TFs)
        self.timeframe_priority = {
            "1d": {"min_score": 80, "max_daily": 1},
            "4h": {"min_score": 82, "max_daily": 2},
            "1h": {"min_score": 85, "max_daily": 3},
            "15m": {"min_score": 95, "max_daily": 1},  # Only perfect setups
        }

    async def scan_for_signals(
        self, symbols: List[str], timeframe: str, market_type: MarketType = MarketType.CRYPTO
    ) -> List[TradingSignal]:
        """Scan symbols for sniper signals on given timeframe."""
        signals = []

        # Check daily limit for this timeframe
        tf_config = self.timeframe_priority.get(timeframe)
        if not tf_config:
            logger.warning(f"Timeframe {timeframe} not in priority list, skipping")
            return signals

        # Get today's signal count for this TF
        if self.db:
            today_count = await self._get_today_signal_count(timeframe, market_type)
            if today_count >= tf_config["max_daily"]:
                logger.info(f"Daily limit reached for {timeframe} ({today_count}/{tf_config['max_daily']})")
                return signals

        for symbol in symbols:
            try:
                signal = await self._analyze_symbol(symbol, timeframe, market_type, tf_config["min_score"])
                if signal:
                    signals.append(signal)
                    # Stop if we hit daily limit
                    if len(signals) >= tf_config["max_daily"]:
                        break
            except Exception as e:
                logger.warning(f"Sniper scan failed for {symbol} {timeframe}: {e}")

        logger.info(f"Sniper engine found {len(signals)} signals on {timeframe}")
        return signals

    async def _analyze_symbol(
        self, symbol: str, timeframe: str, market_type: MarketType, min_score: float
    ) -> Optional[TradingSignal]:
        """Analyze a single symbol for sniper setup."""
        # Fetch OHLCV data (need enough bars for pivots + EMA)
        limit = 100 + self.left_bars + self.right_bars
        
        # Use appropriate data source based on market type
        if market_type == MarketType.FOREX:
            # Forex symbols need ForexClient, not Binance scanner
            # Skip sniper analysis for Forex (let forex_signal_engine handle it)
            return None
        
        df = await self.scanner.fetch_ohlcv(symbol, timeframe, limit=limit)
        if df is None or len(df) < limit:
            return None

        # Add EMA21 and ATR
        df = self._add_indicators(df)
        if len(df) < 50:
            return None

        # Detect pivot points and structure
        pivots = self._detect_pivots(df)
        if not pivots:
            return None

        # Create supply/demand zones from high-volume pivots
        zones = self._create_zones(df, pivots)

        # Check for EMA crossover signal
        signal_type, entry_bar = self._check_crossover(df)
        if not signal_type:
            return None

        # Validate structure alignment
        if not self._validate_structure(signal_type, pivots, df, entry_bar):
            return None

        # Calculate TP/SL using ATR
        entry_price = df.iloc[entry_bar]["close"]
        atr = df.iloc[entry_bar]["atr"]
        tp1, tp2, tp3, sl = self._calculate_levels(entry_price, atr, signal_type)

        # Score the setup
        tech_score, context_score, confidence = await self._score_setup(
            symbol, df, entry_bar, signal_type, pivots, zones, market_type
        )

        # Filter by minimum score
        if confidence < min_score:
            logger.debug(f"{symbol} {timeframe} score {confidence:.1f} < {min_score}, skipping")
            return None

        # Determine setup type from structure
        setup_type = self._determine_setup_type(signal_type, pivots, zones, df, entry_bar)

        # Build reasoning
        reasoning = self._build_reasoning(symbol, timeframe, signal_type, pivots, zones, df, entry_bar, confidence)

        # Determine if LIMIT or MARKET order based on price distance from entry
        current_price = df['close'].iloc[-1]
        price_distance_pct = abs(current_price - entry_price) / entry_price * 100
        
        # SMART ORDER TYPE LOGIC:
        # - Price within 0.5% of entry → MARKET (enter now)
        # - Price > 1% away from entry → LIMIT (wait for retest)
        # - Between 0.5-1% → Check direction
        if price_distance_pct < 0.5:
            is_limit = False  # Price is at entry, execute now
        elif price_distance_pct > 1.0:
            is_limit = True  # Price far from entry, wait for retest
        else:
            # Check if price already moved away from entry
            if signal_type == "BUY":
                is_limit = current_price > entry_price * 1.005  # >0.5% above entry
            else:
                is_limit = current_price < entry_price * 0.995  # >0.5% below entry

        # Create signal
        signal = TradingSignal(
            symbol=symbol,
            direction=SignalDirection.LONG if signal_type == "BUY" else SignalDirection.SHORT,
            setup_type=setup_type,
            timeframe=timeframe,
            market_type=market_type,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            is_limit_order=is_limit,
            technical_score=tech_score,
            context_score=context_score,
            confidence=confidence,
            reasoning=reasoning,
            risk_reward=abs((tp1 - entry_price) / (entry_price - sl)) if sl != entry_price else 0,
            atr=atr,
            volume_24h=df["volume"].tail(24).sum() if len(df) >= 24 else df["volume"].sum(),
            status=SignalStatus.PENDING,
        )

        logger.info(f"🎯 Sniper signal: {symbol} {signal_type} on {timeframe} (confidence: {confidence:.1f}%)")
        return signal

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add EMA21, ATR, and volume SMA."""
        df = df.copy()
        df["ema21"] = df["close"].ewm(span=self.ema_period, adjust=False).mean()
        
        # ATR calculation
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df["atr"] = true_range.rolling(self.atr_length).mean()
        
        # Volume SMA for high-volume detection
        df["volume_sma"] = df["volume"].rolling(20).mean()
        df["is_high_volume"] = df["volume"] > df["volume_sma"]
        
        return df

    def _detect_pivots(self, df: pd.DataFrame) -> List[PivotPoint]:
        """Detect pivot highs and lows with structure labels (HH/HL/LH/LL)."""
        pivots = []
        last_pivot_high = None
        last_pivot_low = None

        for i in range(self.left_bars, len(df) - self.right_bars):
            # Pivot High
            window_high = df["high"].iloc[i - self.left_bars : i + self.right_bars + 1]
            if df["high"].iloc[i] == window_high.max():
                label = "HH" if last_pivot_high is None or df["high"].iloc[i] > last_pivot_high else "LH"
                pivots.append(
                    PivotPoint(
                        bar_index=i,
                        price=df["high"].iloc[i],
                        is_high=True,
                        label=label,
                        volume_confirmed=df["is_high_volume"].iloc[i],
                    )
                )
                last_pivot_high = df["high"].iloc[i]

            # Pivot Low
            window_low = df["low"].iloc[i - self.left_bars : i + self.right_bars + 1]
            if df["low"].iloc[i] == window_low.min():
                label = "LL" if last_pivot_low is None or df["low"].iloc[i] < last_pivot_low else "HL"
                pivots.append(
                    PivotPoint(
                        bar_index=i,
                        price=df["low"].iloc[i],
                        is_high=False,
                        label=label,
                        volume_confirmed=df["is_high_volume"].iloc[i],
                    )
                )
                last_pivot_low = df["low"].iloc[i]

        return pivots

    def _create_zones(self, df: pd.DataFrame, pivots: List[PivotPoint]) -> List[StructureZone]:
        """Create supply/demand zones from high-volume pivots."""
        zones = []
        recent_highs = [p for p in pivots if p.is_high and p.volume_confirmed][-self.max_zones :]
        recent_lows = [p for p in pivots if not p.is_high and p.volume_confirmed][-self.max_zones :]

        for p in recent_highs:
            atr = df.iloc[p.bar_index]["atr"]
            zones.append(
                StructureZone(
                    top=p.price,
                    bottom=p.price - (atr * 0.2),
                    is_supply=True,
                    created_at=p.bar_index,
                )
            )

        for p in recent_lows:
            atr = df.iloc[p.bar_index]["atr"]
            zones.append(
                StructureZone(
                    top=p.price + (atr * 0.2),
                    bottom=p.price,
                    is_supply=False,
                    created_at=p.bar_index,
                )
            )

        return zones

    def _check_crossover(self, df: pd.DataFrame) -> Tuple[Optional[str], int]:
        """Check for EMA21 crossover on most recent completed bar."""
        if len(df) < 3:
            return None, -1

        # Check last completed bar (not current bar)
        i = len(df) - 2
        curr_close = df.iloc[i]["close"]
        prev_close = df.iloc[i - 1]["close"]
        curr_ema = df.iloc[i]["ema21"]
        prev_ema = df.iloc[i - 1]["ema21"]

        # BUY: price crosses above EMA21
        if prev_close <= prev_ema and curr_close > curr_ema:
            return "BUY", i

        # SELL: price crosses below EMA21
        if prev_close >= prev_ema and curr_close < curr_ema:
            return "SELL", i

        return None, -1

    def _validate_structure(
        self, signal_type: str, pivots: List[PivotPoint], df: pd.DataFrame, entry_bar: int
    ) -> bool:
        """Validate that structure aligns with signal direction."""
        # Get recent pivots before entry
        recent_pivots = [p for p in pivots if p.bar_index < entry_bar][-4:]
        if len(recent_pivots) < 2:
            return False

        if signal_type == "BUY":
            # Look for bullish structure: HL (higher lows) or HH (higher highs)
            bullish_count = sum(1 for p in recent_pivots if p.label in ("HL", "HH"))
            return bullish_count >= 1

        else:  # SELL
            # Look for bearish structure: LH (lower highs) or LL (lower lows)
            bearish_count = sum(1 for p in recent_pivots if p.label in ("LH", "LL"))
            return bearish_count >= 1

    def _calculate_levels(
        self, entry: float, atr: float, signal_type: str
    ) -> Tuple[float, float, float, float]:
        """Calculate TP1, TP2, TP3, SL using ATR multiples."""
        if signal_type == "BUY":
            tp1 = entry + (atr * self.tp1_mult)
            tp2 = entry + (atr * self.tp2_mult)
            tp3 = entry + (atr * self.tp3_mult)
            sl = entry - (atr * self.sl_mult)
        else:  # SELL
            tp1 = entry - (atr * self.tp1_mult)
            tp2 = entry - (atr * self.tp2_mult)
            tp3 = entry - (atr * self.tp3_mult)
            sl = entry + (atr * self.sl_mult)

        return tp1, tp2, tp3, sl

    async def _score_setup(
        self,
        symbol: str,
        df: pd.DataFrame,
        entry_bar: int,
        signal_type: str,
        pivots: List[PivotPoint],
        zones: List[StructureZone],
        market_type: MarketType,
    ) -> Tuple[TechnicalScore, ContextScore, float]:
        """Score the setup based on technicals, structure, and context."""
        # Technical scoring
        trend_score = self._score_trend(df, entry_bar, signal_type)
        volume_score = self._score_volume(df, entry_bar)
        momentum_score = self._score_momentum(df, entry_bar, signal_type)
        structure_score = self._score_structure(pivots, signal_type, entry_bar)

        tech_total = (trend_score + volume_score + momentum_score + structure_score) / 4

        tech_score = TechnicalScore(
            trend_score=trend_score,
            volume_score=volume_score,
            momentum_score=momentum_score,
            structure_score=structure_score,
            total_score=tech_total,
        )

        # Context scoring (news, sentiment, macro)
        context_score = ContextScore(macro_score=50, news_score=50, sentiment_score=50, total_score=50)
        if self.context_engine:
            try:
                ctx = await self.context_engine.analyze_context(symbol, df.iloc[entry_bar]["timeframe"] if "timeframe" in df.columns else "1h")
                if ctx:
                    context_score = ctx
            except Exception as e:
                logger.warning(f"Context scoring failed for {symbol}: {e}")

        # Final confidence (70% technical, 30% context)
        confidence = (tech_total * 0.7) + (context_score.total_score * 0.3)

        return tech_score, context_score, round(confidence, 2)

    def _score_trend(self, df: pd.DataFrame, entry_bar: int, signal_type: str) -> float:
        """Score trend alignment (0-100)."""
        score = 50.0
        close = df.iloc[entry_bar]["close"]
        ema21 = df.iloc[entry_bar]["ema21"]

        if signal_type == "BUY":
            # Price above EMA = bullish
            if close > ema21:
                score += 30
            # EMA slope upward
            ema_prev = df.iloc[entry_bar - 5]["ema21"] if entry_bar >= 5 else ema21
            if ema21 > ema_prev:
                score += 20
        else:  # SELL
            if close < ema21:
                score += 30
            ema_prev = df.iloc[entry_bar - 5]["ema21"] if entry_bar >= 5 else ema21
            if ema21 < ema_prev:
                score += 20

        return min(score, 100)

    def _score_volume(self, df: pd.DataFrame, entry_bar: int) -> float:
        """Score volume confirmation (0-100)."""
        if df.iloc[entry_bar]["is_high_volume"]:
            return 90.0
        return 50.0

    def _score_momentum(self, df: pd.DataFrame, entry_bar: int, signal_type: str) -> float:
        """Score momentum (0-100)."""
        score = 50.0
        # Check if price is accelerating in signal direction
        close_curr = df.iloc[entry_bar]["close"]
        close_prev = df.iloc[entry_bar - 1]["close"] if entry_bar >= 1 else close_curr
        close_prev2 = df.iloc[entry_bar - 2]["close"] if entry_bar >= 2 else close_prev

        if signal_type == "BUY":
            if close_curr > close_prev > close_prev2:
                score += 40
        else:
            if close_curr < close_prev < close_prev2:
                score += 40

        return min(score, 100)

    def _score_structure(self, pivots: List[PivotPoint], signal_type: str, entry_bar: int) -> float:
        """Score structure quality (0-100)."""
        recent = [p for p in pivots if p.bar_index < entry_bar][-3:]
        if not recent:
            return 50.0

        score = 50.0
        if signal_type == "BUY":
            # Count HL/HH
            bullish = sum(1 for p in recent if p.label in ("HL", "HH"))
            score += bullish * 15
        else:
            # Count LH/LL
            bearish = sum(1 for p in recent if p.label in ("LH", "LL"))
            score += bearish * 15

        # Bonus for volume-confirmed pivots
        vol_confirmed = sum(1 for p in recent if p.volume_confirmed)
        score += vol_confirmed * 5

        return min(score, 100)

    def _determine_setup_type(
        self, signal_type: str, pivots: List[PivotPoint], zones: List[StructureZone], df: pd.DataFrame, entry_bar: int
    ) -> SetupType:
        """Determine setup type based on structure and zones."""
        recent_pivots = [p for p in pivots if p.bar_index < entry_bar][-2:]
        
        # Check if entry is near a zone (support/resistance)
        entry_price = df.iloc[entry_bar]["close"]
        near_zone = any(
            z.bottom <= entry_price <= z.top
            for z in zones
            if abs(entry_bar - z.created_at) < 20
        )

        if near_zone:
            return SetupType.SUPPORT_RESISTANCE

        # Check for breakout/retest
        if recent_pivots and len(recent_pivots) >= 2:
            if signal_type == "BUY" and recent_pivots[-1].label == "HL":
                return SetupType.BREAKOUT_RETEST
            elif signal_type == "SELL" and recent_pivots[-1].label == "LH":
                return SetupType.BREAKOUT_RETEST

        return SetupType.PULLBACK_CONTINUATION

    def _build_reasoning(
        self,
        symbol: str,
        timeframe: str,
        signal_type: str,
        pivots: List[PivotPoint],
        zones: List[StructureZone],
        df: pd.DataFrame,
        entry_bar: int,
        confidence: float,
    ) -> str:
        """Build detailed reasoning for the signal."""
        recent_pivots = [p for p in pivots if p.bar_index < entry_bar][-3:]
        structure_labels = [p.label for p in recent_pivots]
        
        reasoning = f"Sniper {signal_type} on {timeframe} (confidence: {confidence:.0f}%). "
        reasoning += f"EMA21 crossover confirmed. "
        
        if signal_type == "BUY":
            reasoning += f"Bullish structure: {', '.join(structure_labels)}. "
            reasoning += f"Price crossed above EMA21 at ${df.iloc[entry_bar]['close']:.6f}. "
        else:
            reasoning += f"Bearish structure: {', '.join(structure_labels)}. "
            reasoning += f"Price crossed below EMA21 at ${df.iloc[entry_bar]['close']:.6f}. "
        
        if df.iloc[entry_bar]["is_high_volume"]:
            reasoning += "High volume confirmation. "
        
        vol_pivots = sum(1 for p in recent_pivots if p.volume_confirmed)
        if vol_pivots > 0:
            reasoning += f"{vol_pivots} volume-confirmed pivot(s). "
        
        reasoning += f"ATR-based TP/SL: {self.tp1_mult}x/{self.tp2_mult}x/{self.tp3_mult}x TPs, {self.sl_mult}x SL."
        
        return reasoning

    async def _get_today_signal_count(self, timeframe: str, market_type: MarketType) -> int:
        """Get count of signals generated today for this timeframe."""
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            result = (
                self.db.client.table("signals")
                .select("id", count="exact")
                .eq("timeframe", timeframe)
                .eq("market_type", market_type.value)
                .gte("created_at", today_start.isoformat())
                .execute()
            )
            return result.count if hasattr(result, "count") else 0
        except Exception as e:
            logger.warning(f"Could not get today's signal count: {e}")
            return 0
