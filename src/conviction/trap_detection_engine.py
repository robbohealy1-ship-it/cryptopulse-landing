"""
Trap Detection Engine - Detects market traps and applies penalties

Traps Detected:
- Bull Traps (fake breakout up, then reversal)
- Bear Traps (fake breakout down, then reversal)
- Liquidity Grabs (sweep then reverse)
- Failed Breakouts
- Open Interest Traps (OI spike + price reversal)
- Funding Extremes (>0.1% or <-0.1%)

When a trap is detected, conviction score gets a penalty.

Penalty Range: 0 to -25 points
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from src.utils.logger import get_logger
from src.analysis.enhanced_context_engine import EnhancedContextEngine

logger = get_logger(__name__)


@dataclass
class TrapDetection:
    """Represents a detected trap"""
    type: str  # 'bull_trap', 'bear_trap', 'liquidity_grab', etc.
    severity: str  # 'low', 'medium', 'high'
    penalty: float  # Conviction penalty (0-25)
    explanation: str


class TrapDetectionEngine:
    """
    Detects market traps and calculates conviction penalties.
    
    Returns a penalty (0 to -25 points) based on detected traps.
    """
    
    def __init__(self):
        self.logger = logger
        self.context_engine = EnhancedContextEngine()
    
    async def calculate_penalty(self, df: pd.DataFrame, symbol: str, direction: str) -> Tuple[float, List[TrapDetection]]:
        """
        Calculate conviction penalty based on detected traps
        
        Args:
            df: OHLCV dataframe
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
        
        Returns:
            (penalty, detected_traps)
            penalty: 0 to 25 (points to subtract from conviction)
            detected_traps: List of detected traps
        """
        if len(df) < 20:
            return 0.0, []
        
        traps = []
        
        # ─── 1. BULL/BEAR TRAPS ───
        trap = self._detect_bull_bear_trap(df, direction)
        if trap:
            traps.append(trap)
        
        # ─── 2. FAILED BREAKOUTS ───
        trap = self._detect_failed_breakout(df, direction)
        if trap:
            traps.append(trap)
        
        # ─── 3. LIQUIDITY GRABS ───
        trap = self._detect_liquidity_grab(df, direction)
        if trap:
            traps.append(trap)
        
        # ─── 4. OPEN INTEREST TRAPS ───
        trap = await self._detect_oi_trap(symbol, df, direction)
        if trap:
            traps.append(trap)
        
        # ─── 5. FUNDING EXTREMES ───
        trap = await self._detect_funding_extreme(symbol, direction)
        if trap:
            traps.append(trap)
        
        # Calculate total penalty
        total_penalty = sum(t.penalty for t in traps)
        total_penalty = min(total_penalty, 25.0)  # Cap at 25 points
        
        if traps:
            self.logger.warning(
                f"⚠️ {symbol}: {len(traps)} trap(s) detected | "
                f"Penalty: -{total_penalty:.1f} points | "
                f"Types: {', '.join([t.type for t in traps])}"
            )
        
        return total_penalty, traps
    
    def _detect_bull_bear_trap(self, df: pd.DataFrame, direction: str) -> TrapDetection:
        """Detect bull/bear traps (fake breakouts)"""
        if len(df) < 30:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Find recent swing high/low
        recent_high = df['high'].iloc[-20:-5].max()
        recent_low = df['low'].iloc[-20:-5].min()
        
        # Bull trap: Price broke above resistance, then fell back below
        if direction == 'LONG':
            broke_above = df['high'].iloc[-5:].max() > recent_high * 1.005
            fell_back = current_price < recent_high * 0.998
            
            if broke_above and fell_back:
                return TrapDetection(
                    type='bull_trap',
                    severity='high',
                    penalty=15.0,
                    explanation="Bull trap detected - price broke above resistance then reversed down"
                )
        
        # Bear trap: Price broke below support, then rallied back above
        elif direction == 'SHORT':
            broke_below = df['low'].iloc[-5:].min() < recent_low * 0.995
            rallied_back = current_price > recent_low * 1.002
            
            if broke_below and rallied_back:
                return TrapDetection(
                    type='bear_trap',
                    severity='high',
                    penalty=15.0,
                    explanation="Bear trap detected - price broke below support then reversed up"
                )
        
        return None
    
    def _detect_failed_breakout(self, df: pd.DataFrame, direction: str) -> TrapDetection:
        """Detect failed breakouts"""
        if len(df) < 20:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Look for a breakout that failed to sustain
        for i in range(-10, -2):
            if abs(i) > len(df):
                continue
            
            # Bullish breakout that failed
            if direction == 'LONG':
                breakout_candle = df.iloc[i]
                was_strong_move = breakout_candle['close'] > breakout_candle['open'] * 1.02
                failed_to_hold = current_price < breakout_candle['close'] * 0.98
                
                if was_strong_move and failed_to_hold:
                    return TrapDetection(
                        type='failed_breakout',
                        severity='medium',
                        penalty=10.0,
                        explanation="Failed bullish breakout - strong move up could not sustain"
                    )
            
            # Bearish breakout that failed
            elif direction == 'SHORT':
                breakout_candle = df.iloc[i]
                was_strong_move = breakout_candle['close'] < breakout_candle['open'] * 0.98
                failed_to_hold = current_price > breakout_candle['close'] * 1.02
                
                if was_strong_move and failed_to_hold:
                    return TrapDetection(
                        type='failed_breakout',
                        severity='medium',
                        penalty=10.0,
                        explanation="Failed bearish breakout - strong move down could not sustain"
                    )
        
        return None
    
    def _detect_liquidity_grab(self, df: pd.DataFrame, direction: str) -> TrapDetection:
        """Detect liquidity grabs (sweep then immediate reversal)"""
        if len(df) < 15:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Look for recent sweep + reversal in last 5-10 candles
        recent_high = df['high'].iloc[-10:-1].max()
        recent_low = df['low'].iloc[-10:-1].min()
        
        # Bullish liquidity grab: Swept lows, now reversing up
        if direction == 'LONG':
            swept_low = df['low'].iloc[-5:].min() < recent_low * 0.998
            strong_reversal = current_price > df['close'].iloc[-5] * 1.015
            
            # This is actually GOOD for longs (swept stops, now going up)
            # So we don't penalize, we actually want this
            return None
        
        # Bearish liquidity grab: Swept highs, now reversing down
        elif direction == 'SHORT':
            swept_high = df['high'].iloc[-5:].max() > recent_high * 1.002
            strong_reversal = current_price < df['close'].iloc[-5] * 0.985
            
            # This is actually GOOD for shorts (swept stops, now going down)
            # So we don't penalize
            return None
        
        return None
    
    async def _detect_oi_trap(self, symbol: str, df: pd.DataFrame, direction: str) -> TrapDetection:
        """Detect open interest traps (OI spike + price reversal)"""
        try:
            # Convert symbol format
            futures_symbol = symbol.replace('/', '')
            
            # Get OI data
            oi_data = await self.context_engine.fetch_open_interest(futures_symbol)
            high_oi = oi_data.get('high_oi', False)
            
            if not high_oi:
                return None
            
            # Check if price is reversing despite high OI
            current_price = df['close'].iloc[-1]
            price_5_candles_ago = df['close'].iloc[-5]
            
            # High OI + price reversing = trap
            if direction == 'LONG':
                price_falling = current_price < price_5_candles_ago * 0.98
                if price_falling:
                    return TrapDetection(
                        type='oi_trap',
                        severity='medium',
                        penalty=12.0,
                        explanation="High OI + falling price - potential long squeeze"
                    )
            
            elif direction == 'SHORT':
                price_rising = current_price > price_5_candles_ago * 1.02
                if price_rising:
                    return TrapDetection(
                        type='oi_trap',
                        severity='medium',
                        penalty=12.0,
                        explanation="High OI + rising price - potential short squeeze"
                    )
        
        except Exception as e:
            self.logger.debug(f"OI trap detection failed for {symbol}: {e}")
        
        return None
    
    async def _detect_funding_extreme(self, symbol: str, direction: str) -> TrapDetection:
        """Detect funding rate extremes (overleveraged positions)"""
        try:
            # Convert symbol format
            futures_symbol = symbol.replace('/', '')
            
            # Get funding data
            funding_data = await self.context_engine.fetch_funding_rates(futures_symbol)
            rate = funding_data.get('funding_rate', 0)
            is_extreme = funding_data.get('is_extreme', False)
            
            if not is_extreme:
                return None
            
            # Extreme positive funding + going long = trap (overleveraged longs)
            if direction == 'LONG' and rate > 0.001:
                return TrapDetection(
                    type='funding_extreme',
                    severity='high',
                    penalty=8.0,
                    explanation=f"Extreme positive funding ({rate:.4f}%) - overleveraged longs, high reversal risk"
                )
            
            # Extreme negative funding + going short = trap (overleveraged shorts)
            elif direction == 'SHORT' and rate < -0.001:
                return TrapDetection(
                    type='funding_extreme',
                    severity='high',
                    penalty=8.0,
                    explanation=f"Extreme negative funding ({rate:.4f}%) - overleveraged shorts, high reversal risk"
                )
        
        except Exception as e:
            self.logger.debug(f"Funding extreme detection failed for {symbol}: {e}")
        
        return None
    
    def get_trap_explanation(self, traps: List[TrapDetection]) -> str:
        """Generate human-readable explanation of detected traps"""
        if not traps:
            return "No traps detected"
        
        parts = []
        for trap in traps:
            parts.append(f"{trap.type.replace('_', ' ').title()} ({trap.severity}): {trap.explanation}")
        
        return " | ".join(parts)
