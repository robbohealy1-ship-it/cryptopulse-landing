"""
Market Structure Engine - Scores market structure quality and trend strength

Scoring Breakdown (0-20 points):
- Trend Strength: 0-8 points
- Structure Quality: 0-6 points
- Regime Alignment: 0-6 points

Inputs:
- Daily/Weekly/Monthly High/Low
- Trend Direction
- ATR (volatility)
- Market Regime (trending/ranging/choppy)
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from .base_engine import BaseConvictionEngine, EngineScore
from src.analysis.institutional_analyzer import InstitutionalAnalyzer


class MarketStructureEngine(BaseConvictionEngine):
    """Analyzes and scores market structure quality"""
    
    def __init__(self):
        super().__init__(name="MarketStructure", max_score=20.0)
        self.analyzer = InstitutionalAnalyzer()
    
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate market structure score (0-20 points)
        
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
        
        # Get structure analysis from existing analyzer
        structure = self.analyzer.analyze_structure(df)
        regime = self.analyzer.detect_volatility_regime(df)
        
        # ─── 1. TREND STRENGTH (0-8 points) ───
        trend = structure.get('trend', 'neutral')
        bos = structure.get('bos', False)
        choch = structure.get('choch', False)
        
        trend_score = self._score_trend_strength(trend, direction, bos, choch, positive, negative)
        factors['trend_strength'] = trend_score
        score += trend_score
        
        # ─── 2. STRUCTURE QUALITY (0-6 points) ───
        structure_score = self._score_structure_quality(structure, bos, choch, positive, negative)
        factors['structure_quality'] = structure_score
        score += structure_score
        
        # ─── 3. REGIME ALIGNMENT (0-6 points) ───
        regime_score = self._score_regime_alignment(regime, trend, positive, negative)
        factors['regime_alignment'] = regime_score
        score += regime_score
        
        # ─── 4. DAILY/WEEKLY/MONTHLY LEVELS (Bonus) ───
        levels_bonus = self._score_key_levels(df, direction, positive)
        factors['key_levels_bonus'] = levels_bonus
        score += levels_bonus
        
        # Clamp to max
        score = self._clamp_score(score)
        
        # Build explanation
        explanation = self._build_explanation(trend, bos, choch, regime, score)
        
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
    
    def _score_trend_strength(self, trend: str, direction: str, bos: bool, choch: bool,
                             positive: List[str], negative: List[str]) -> float:
        """Score trend strength (0-8 points)"""
        score = 0.0
        
        # Check if trend aligns with direction
        if direction == 'LONG':
            if trend == 'uptrend':
                score += 6.0
                positive.append("Strong uptrend aligns with LONG direction")
                if bos:
                    score += 2.0
                    positive.append("Break of Structure (BOS) confirms uptrend")
            elif trend == 'potential_reversal':
                score += 3.0
                positive.append("Potential reversal to upside")
            elif trend == 'downtrend':
                score += 0.0
                negative.append("Downtrend conflicts with LONG direction")
            else:  # neutral
                score += 2.0
                negative.append("Neutral trend - no clear direction")
        
        else:  # SHORT
            if trend == 'downtrend':
                score += 6.0
                positive.append("Strong downtrend aligns with SHORT direction")
                if bos:
                    score += 2.0
                    positive.append("Break of Structure (BOS) confirms downtrend")
            elif trend == 'potential_reversal':
                score += 3.0
                positive.append("Potential reversal to downside")
            elif trend == 'uptrend':
                score += 0.0
                negative.append("Uptrend conflicts with SHORT direction")
            else:  # neutral
                score += 2.0
                negative.append("Neutral trend - no clear direction")
        
        return score
    
    def _score_structure_quality(self, structure: Dict, bos: bool, choch: bool,
                                 positive: List[str], negative: List[str]) -> float:
        """Score structure quality (0-6 points)"""
        score = 0.0
        
        # BOS = clean structure
        if bos:
            score += 4.0
            positive.append("Clean Break of Structure (BOS)")
        
        # CHoCH = structure shift (moderate quality)
        if choch and not bos:
            score += 2.0
            positive.append("Change of Character (CHoCH) detected")
        
        # Inducement = liquidity sweep (good quality)
        if structure.get('inducement', False):
            score += 2.0
            positive.append("Inducement/liquidity sweep detected")
        
        # No clear structure
        if not bos and not choch:
            negative.append("No clear structure break")
        
        return min(score, 6.0)
    
    def _score_regime_alignment(self, regime: Dict, trend: str,
                                positive: List[str], negative: List[str]) -> float:
        """Score market regime alignment (0-6 points)"""
        score = 0.0
        
        current_regime = regime.get('regime', 'unknown')
        
        if current_regime == 'trending':
            if trend in ['uptrend', 'downtrend']:
                score += 6.0
                positive.append("Trending regime aligns with directional trend")
            else:
                score += 3.0
                positive.append("Trending regime but no clear direction yet")
        
        elif current_regime == 'compression':
            score += 4.0
            positive.append("Volatility compression - expansion likely coming")
        
        elif current_regime == 'balanced':
            score += 3.0
            positive.append("Balanced volatility regime")
        
        elif current_regime == 'choppy':
            score += 0.0
            negative.append("Choppy regime - low conviction environment")
        
        elif current_regime == 'expansion':
            if trend in ['uptrend', 'downtrend']:
                score += 5.0
                positive.append("Volatility expansion with clear trend")
            else:
                score += 1.0
                negative.append("Volatility expansion but no clear direction")
        
        return score
    
    def _score_key_levels(self, df: pd.DataFrame, direction: str, positive: List[str]) -> float:
        """Score proximity to daily/weekly/monthly levels (0-2 bonus points)"""
        score = 0.0
        
        if len(df) < 30:
            return 0.0
        
        current_price = df['close'].iloc[-1]
        
        # Daily high/low (last 24 candles for 1h, last 1 candle for 1d)
        daily_high = df['high'].iloc[-24:].max() if len(df) >= 24 else df['high'].max()
        daily_low = df['low'].iloc[-24:].min() if len(df) >= 24 else df['low'].min()
        
        # Weekly high/low (last 168 candles for 1h, last 7 for 1d)
        lookback = min(168, len(df))
        weekly_high = df['high'].iloc[-lookback:].max()
        weekly_low = df['low'].iloc[-lookback:].min()
        
        # Check proximity (within 1%)
        if direction == 'LONG':
            if abs(current_price - daily_low) / daily_low < 0.01:
                score += 1.0
                positive.append("Near daily low - good LONG entry zone")
            if abs(current_price - weekly_low) / weekly_low < 0.01:
                score += 1.0
                positive.append("Near weekly low - strong LONG support")
        else:  # SHORT
            if abs(current_price - daily_high) / daily_high < 0.01:
                score += 1.0
                positive.append("Near daily high - good SHORT entry zone")
            if abs(current_price - weekly_high) / weekly_high < 0.01:
                score += 1.0
                positive.append("Near weekly high - strong SHORT resistance")
        
        return min(score, 2.0)
    
    def _build_explanation(self, trend: str, bos: bool, choch: bool, regime: Dict, score: float) -> str:
        """Build human-readable explanation"""
        parts = []
        
        parts.append(f"Market Structure Score: {score:.1f}/20")
        
        if trend == 'uptrend':
            parts.append("Trend: Confirmed uptrend with higher highs and higher lows")
        elif trend == 'downtrend':
            parts.append("Trend: Confirmed downtrend with lower highs and lower lows")
        elif trend == 'potential_reversal':
            parts.append("Trend: Potential reversal zone - structure shifting")
        else:
            parts.append("Trend: Neutral - no clear directional bias")
        
        if bos:
            parts.append("Structure: Clean Break of Structure (BOS) confirmed")
        elif choch:
            parts.append("Structure: Change of Character (CHoCH) detected")
        
        current_regime = regime.get('regime', 'unknown')
        parts.append(f"Regime: {current_regime.title()}")
        
        return " | ".join(parts)
