"""
Volume Engine - Scores volume confirmation and buying/selling pressure

Scoring Breakdown (0-15 points):
- Relative Volume: 0-6 points
- Volume Spikes: 0-4 points
- Delta/CVD (Buy/Sell Pressure): 0-5 points

Inputs:
- Relative volume (vs 20-period average)
- Volume spikes
- Delta (estimated from candle wicks)
- CVD (Cumulative Volume Delta)
- Buy/sell imbalance
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from .base_engine import BaseConvictionEngine, EngineScore


class VolumeEngine(BaseConvictionEngine):
    """Analyzes and scores volume confirmation"""
    
    def __init__(self):
        super().__init__(name="Volume", max_score=15.0)
    
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate volume score (0-15 points)
        
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
        
        if len(df) < 20:
            # Not enough data
            return EngineScore(
                score=7.5,  # Neutral score
                max_score=self.max_score,
                factors={'insufficient_data': 7.5},
                positive_factors=["Insufficient data for volume analysis"],
                negative_factors=[],
                explanation="Volume Score: 7.5/15 (neutral - insufficient data)"
            )
        
        # ─── 1. RELATIVE VOLUME (0-6 points) ───
        rel_vol_score = self._score_relative_volume(df, positive, negative)
        factors['relative_volume'] = rel_vol_score
        score += rel_vol_score
        
        # ─── 2. VOLUME SPIKES (0-4 points) ───
        spike_score = self._score_volume_spikes(df, positive, negative)
        factors['volume_spikes'] = spike_score
        score += spike_score
        
        # ─── 3. DELTA/CVD (0-5 points) ───
        delta_score = self._score_delta_cvd(df, direction, positive, negative)
        factors['delta_cvd'] = delta_score
        score += delta_score
        
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
    
    def _score_relative_volume(self, df: pd.DataFrame, positive: List[str], negative: List[str]) -> float:
        """Score relative volume vs average (0-6 points)"""
        score = 0.0
        
        # Calculate 20-period average volume
        avg_volume = df['volume'].iloc[-20:].mean()
        current_volume = df['volume'].iloc[-1]
        
        if avg_volume == 0:
            return 3.0  # Neutral if no volume data
        
        # Calculate relative volume
        rel_volume = current_volume / avg_volume
        
        if rel_volume > 2.0:
            score = 6.0
            positive.append(f"Very high volume: {rel_volume:.1f}x average")
        elif rel_volume > 1.5:
            score = 4.0
            positive.append(f"High volume: {rel_volume:.1f}x average")
        elif rel_volume > 1.2:
            score = 2.0
            positive.append(f"Above-average volume: {rel_volume:.1f}x average")
        elif rel_volume > 0.8:
            score = 1.0
            negative.append(f"Average volume: {rel_volume:.1f}x average")
        else:
            score = 0.0
            negative.append(f"Low volume: {rel_volume:.1f}x average - weak confirmation")
        
        return score
    
    def _score_volume_spikes(self, df: pd.DataFrame, positive: List[str], negative: List[str]) -> float:
        """Score recent volume spikes (0-4 points)"""
        score = 0.0
        
        # Look for volume spikes in last 5 candles
        recent_volumes = df['volume'].iloc[-5:].values
        avg_volume = df['volume'].iloc[-20:-5].mean()
        
        if avg_volume == 0:
            return 2.0  # Neutral
        
        # Find max spike in recent candles
        max_spike = np.max(recent_volumes) / avg_volume if avg_volume > 0 else 1.0
        
        if max_spike > 3.0:
            score = 4.0
            positive.append(f"Extreme volume spike: {max_spike:.1f}x average")
        elif max_spike > 2.0:
            score = 3.0
            positive.append(f"Strong volume spike: {max_spike:.1f}x average")
        elif max_spike > 1.5:
            score = 2.0
            positive.append(f"Moderate volume spike: {max_spike:.1f}x average")
        else:
            score = 1.0
            negative.append("No significant volume spike")
        
        return score
    
    def _score_delta_cvd(self, df: pd.DataFrame, direction: str, positive: List[str], negative: List[str]) -> float:
        """
        Score delta and CVD (0-5 points)
        
        Delta = Buy Volume - Sell Volume (estimated from candle wicks)
        CVD = Cumulative Volume Delta
        
        Since we don't have tick data, we estimate:
        - Bullish candle (close > open) = more buying
        - Bearish candle (close < open) = more selling
        - Wick size indicates rejection
        """
        score = 0.0
        
        if len(df) < 10:
            return 2.5  # Neutral
        
        # Estimate delta for recent candles
        deltas = []
        for i in range(-10, 0):
            candle = df.iloc[i]
            
            # Bullish candle
            if candle['close'] > candle['open']:
                body_pct = (candle['close'] - candle['open']) / (candle['high'] - candle['low']) if (candle['high'] - candle['low']) > 0 else 0.5
                delta = candle['volume'] * body_pct  # Estimate buy volume
            # Bearish candle
            else:
                body_pct = (candle['open'] - candle['close']) / (candle['high'] - candle['low']) if (candle['high'] - candle['low']) > 0 else 0.5
                delta = -candle['volume'] * body_pct  # Estimate sell volume
            
            deltas.append(delta)
        
        # Calculate CVD (cumulative)
        cvd = np.cumsum(deltas)
        
        # Check if CVD is trending in the right direction
        cvd_trend = cvd[-1] - cvd[0]  # Positive = buying, Negative = selling
        
        if direction == 'LONG':
            if cvd_trend > 0:
                # Buying pressure aligns with LONG
                if cvd_trend > np.abs(cvd).mean():
                    score = 5.0
                    positive.append("Strong buying pressure (CVD rising)")
                else:
                    score = 3.0
                    positive.append("Moderate buying pressure")
            else:
                score = 1.0
                negative.append("Selling pressure conflicts with LONG direction")
        
        elif direction == 'SHORT':
            if cvd_trend < 0:
                # Selling pressure aligns with SHORT
                if abs(cvd_trend) > np.abs(cvd).mean():
                    score = 5.0
                    positive.append("Strong selling pressure (CVD falling)")
                else:
                    score = 3.0
                    positive.append("Moderate selling pressure")
            else:
                score = 1.0
                negative.append("Buying pressure conflicts with SHORT direction")
        
        return score
    
    def _build_explanation(self, score: float, factors: Dict[str, float]) -> str:
        """Build human-readable explanation"""
        parts = []
        
        parts.append(f"Volume Score: {score:.1f}/15")
        
        if 'relative_volume' in factors:
            parts.append(f"Rel Vol: {factors['relative_volume']:.1f}/6")
        
        if 'volume_spikes' in factors:
            parts.append(f"Spikes: {factors['volume_spikes']:.1f}/4")
        
        if 'delta_cvd' in factors:
            parts.append(f"Delta: {factors['delta_cvd']:.1f}/5")
        
        return " | ".join(parts)
