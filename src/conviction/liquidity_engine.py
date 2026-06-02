"""
Liquidity Engine - Scores liquidity setup quality

Scoring Breakdown (0-20 points):
- Liquidity Sweeps: 0-8 points
- Equal Highs/Lows: 0-6 points
- Fair Value Gaps: 0-3 points
- Order Blocks: 0-3 points

Inputs:
- Liquidity sweeps
- Equal highs/lows
- Fair value gaps (FVG)
- Order blocks
- Key levels
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .base_engine import BaseConvictionEngine, EngineScore
from src.analysis.institutional_analyzer import InstitutionalAnalyzer


class LiquidityEngine(BaseConvictionEngine):
    """Analyzes and scores liquidity setups"""
    
    def __init__(self):
        super().__init__(name="Liquidity", max_score=20.0)
        self.analyzer = InstitutionalAnalyzer()
    
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate liquidity score (0-20 points)
        
        Args:
            df: OHLCV dataframe
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
        
        Returns:
            EngineScore with breakdown
        """
        score = 0.0
        factors = {}
        positive = []
        negative = []
        
        # Get current price
        current_price = df['close'].iloc[-1]
        
        # ─── 1. LIQUIDITY SWEEPS (0-8 points) ───
        sweep_score = self._score_liquidity_sweeps(df, direction, current_price, positive, negative)
        factors['liquidity_sweeps'] = sweep_score
        score += sweep_score
        
        # ─── 2. EQUAL HIGHS/LOWS (0-6 points) ───
        equal_levels_score = self._score_equal_levels(df, direction, current_price, positive, negative)
        factors['equal_levels'] = equal_levels_score
        score += equal_levels_score
        
        # ─── 3. FAIR VALUE GAPS (0-3 points) ───
        fvg_score = self._score_fair_value_gaps(df, direction, current_price, positive, negative)
        factors['fair_value_gaps'] = fvg_score
        score += fvg_score
        
        # ─── 4. ORDER BLOCKS (0-3 points) ───
        ob_score = self._score_order_blocks(df, direction, current_price, positive, negative)
        factors['order_blocks'] = ob_score
        score += ob_score
        
        # Clamp to max
        score = self._clamp_score(score)
        
        # Build explanation
        explanation = self._build_explanation(score, factors)
        
        result = EngineScore(
            score=score,
            max_score=self.max_score,
            factors=factors,
            positive_factors=positive,
            negative_factors=negative,
            explanation=explanation
        )
        
        self._log_score(symbol, result)
        return result
    
    def _score_liquidity_sweeps(self, df: pd.DataFrame, direction: str, current_price: float,
                                positive: List[str], negative: List[str]) -> float:
        """Score liquidity sweeps (0-8 points)"""
        score = 0.0
        
        if len(df) < 20:
            return 0.0
        
        # Look for liquidity sweeps in last 10-20 candles
        recent_highs = df['high'].iloc[-20:-1].values
        recent_lows = df['low'].iloc[-20:-1].values
        
        # Find swing highs and lows
        swing_high = np.max(recent_highs)
        swing_low = np.min(recent_lows)
        
        # Check if price swept above swing high then reversed (bearish sweep)
        if direction == 'SHORT':
            swept_high = df['high'].iloc[-10:].max() > swing_high * 1.001
            reversed_down = current_price < swing_high * 0.998
            
            if swept_high and reversed_down:
                score += 8.0
                positive.append("Liquidity sweep above highs - bearish reversal setup")
            elif swept_high:
                score += 4.0
                positive.append("Highs swept but no clear reversal yet")
        
        # Check if price swept below swing low then reversed (bullish sweep)
        elif direction == 'LONG':
            swept_low = df['low'].iloc[-10:].min() < swing_low * 0.999
            reversed_up = current_price > swing_low * 1.002
            
            if swept_low and reversed_up:
                score += 8.0
                positive.append("Liquidity sweep below lows - bullish reversal setup")
            elif swept_low:
                score += 4.0
                positive.append("Lows swept but no clear reversal yet")
        
        return score
    
    def _score_equal_levels(self, df: pd.DataFrame, direction: str, current_price: float,
                           positive: List[str], negative: List[str]) -> float:
        """Score equal highs/lows (0-6 points)"""
        score = 0.0
        
        if len(df) < 30:
            return 0.0
        
        # Find equal highs (resistance) - within 0.3% of each other
        highs = df['high'].iloc[-30:].values
        equal_highs = self._find_equal_levels(highs, tolerance=0.003)
        
        # Find equal lows (support) - within 0.3% of each other
        lows = df['low'].iloc[-30:].values
        equal_lows = self._find_equal_levels(lows, tolerance=0.003)
        
        if direction == 'SHORT' and equal_highs:
            # Price near equal highs = resistance zone
            nearest_high = min(equal_highs, key=lambda x: abs(x - current_price))
            if abs(current_price - nearest_high) / nearest_high < 0.01:
                score += 6.0
                positive.append(f"Price at equal highs resistance (${nearest_high:.4f})")
            elif abs(current_price - nearest_high) / nearest_high < 0.02:
                score += 3.0
                positive.append(f"Price approaching equal highs (${nearest_high:.4f})")
        
        elif direction == 'LONG' and equal_lows:
            # Price near equal lows = support zone
            nearest_low = min(equal_lows, key=lambda x: abs(x - current_price))
            if abs(current_price - nearest_low) / nearest_low < 0.01:
                score += 6.0
                positive.append(f"Price at equal lows support (${nearest_low:.4f})")
            elif abs(current_price - nearest_low) / nearest_low < 0.02:
                score += 3.0
                positive.append(f"Price approaching equal lows (${nearest_low:.4f})")
        
        return score
    
    def _find_equal_levels(self, prices: np.ndarray, tolerance: float = 0.003) -> List[float]:
        """Find equal price levels (within tolerance)"""
        equal_levels = []
        
        # Find local extrema
        for i in range(2, len(prices) - 2):
            # Check if this is a local high or low
            is_high = prices[i] > prices[i-1] and prices[i] > prices[i+1]
            is_low = prices[i] < prices[i-1] and prices[i] < prices[i+1]
            
            if is_high or is_low:
                # Check if there's another similar level
                for j in range(i+3, len(prices) - 2):
                    if abs(prices[i] - prices[j]) / prices[i] < tolerance:
                        equal_levels.append(prices[i])
                        break
        
        return list(set(equal_levels))  # Remove duplicates
    
    def _score_fair_value_gaps(self, df: pd.DataFrame, direction: str, current_price: float,
                               positive: List[str], negative: List[str]) -> float:
        """Score fair value gaps (0-3 points)"""
        score = 0.0
        
        if len(df) < 10:
            return 0.0
        
        # Look for FVGs in last 10 candles
        for i in range(-10, -2):
            if abs(i) > len(df):
                continue
            
            # Bullish FVG: gap between candle[i-1] high and candle[i+1] low
            if direction == 'LONG':
                gap_low = df['high'].iloc[i-1]
                gap_high = df['low'].iloc[i+1]
                
                if gap_high > gap_low:  # There's a gap
                    # Check if price is in the gap
                    if gap_low <= current_price <= gap_high:
                        score += 3.0
                        positive.append(f"Price in bullish FVG (${gap_low:.4f}-${gap_high:.4f})")
                        break
            
            # Bearish FVG: gap between candle[i-1] low and candle[i+1] high
            elif direction == 'SHORT':
                gap_high = df['low'].iloc[i-1]
                gap_low = df['high'].iloc[i+1]
                
                if gap_high > gap_low:  # There's a gap
                    # Check if price is in the gap
                    if gap_low <= current_price <= gap_high:
                        score += 3.0
                        positive.append(f"Price in bearish FVG (${gap_low:.4f}-${gap_high:.4f})")
                        break
        
        return score
    
    def _score_order_blocks(self, df: pd.DataFrame, direction: str, current_price: float,
                           positive: List[str], negative: List[str]) -> float:
        """Score order blocks (0-3 points)"""
        score = 0.0
        
        if len(df) < 20:
            return 0.0
        
        # Look for order blocks in last 15 candles
        for i in range(-15, -3):
            if abs(i) > len(df):
                continue
            
            # Bullish OB: last bearish candle before strong up move
            if direction == 'LONG':
                is_bearish = df['close'].iloc[i] < df['open'].iloc[i]
                strong_move_up = df['close'].iloc[-1] > df['close'].iloc[i] * 1.02
                
                if is_bearish and strong_move_up:
                    ob_low = df['low'].iloc[i]
                    ob_high = df['high'].iloc[i]
                    
                    # Check if price is in OB zone
                    if ob_low <= current_price <= ob_high:
                        score += 3.0
                        positive.append(f"Price in bullish order block (${ob_low:.4f}-${ob_high:.4f})")
                        break
            
            # Bearish OB: last bullish candle before strong down move
            elif direction == 'SHORT':
                is_bullish = df['close'].iloc[i] > df['open'].iloc[i]
                strong_move_down = df['close'].iloc[-1] < df['close'].iloc[i] * 0.98
                
                if is_bullish and strong_move_down:
                    ob_low = df['low'].iloc[i]
                    ob_high = df['high'].iloc[i]
                    
                    # Check if price is in OB zone
                    if ob_low <= current_price <= ob_high:
                        score += 3.0
                        positive.append(f"Price in bearish order block (${ob_low:.4f}-${ob_high:.4f})")
                        break
        
        return score
    
    def _build_explanation(self, score: float, factors: Dict[str, float]) -> str:
        """Build human-readable explanation"""
        parts = []
        
        parts.append(f"Liquidity Score: {score:.1f}/20")
        
        if factors.get('liquidity_sweeps', 0) > 0:
            parts.append(f"Sweeps: {factors['liquidity_sweeps']:.1f}/8")
        
        if factors.get('equal_levels', 0) > 0:
            parts.append(f"Equal Levels: {factors['equal_levels']:.1f}/6")
        
        if factors.get('fair_value_gaps', 0) > 0:
            parts.append("FVG Present")
        
        if factors.get('order_blocks', 0) > 0:
            parts.append("Order Block Present")
        
        return " | ".join(parts)
