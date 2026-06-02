"""
Sentiment Engine - Scores market sentiment and positioning

Scoring Breakdown (0-15 points):
- Funding Rate Alignment: 0-5 points
- Long/Short Ratio: 0-5 points
- Liquidations: 0-3 points
- Fear & Greed: 0-2 points

Inputs:
- Funding rates (from Binance futures)
- Long/short ratios (from Binance futures)
- Liquidation data
- Fear & Greed Index
"""

import pandas as pd
from typing import Dict, List
from .base_engine import BaseConvictionEngine, EngineScore
from src.analysis.enhanced_context_engine import EnhancedContextEngine


class SentimentEngine(BaseConvictionEngine):
    """Analyzes and scores market sentiment"""
    
    def __init__(self):
        super().__init__(name="Sentiment", max_score=15.0)
        self.context_engine = EnhancedContextEngine()
    
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate sentiment score (0-15 points)
        
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
        
        # Convert symbol format (BTC/USDT -> BTCUSDT)
        futures_symbol = symbol.replace('/', '')
        
        # ─── 1. FUNDING RATE ALIGNMENT (0-5 points) ───
        funding_score = await self._score_funding_rate(futures_symbol, direction, positive, negative)
        factors['funding_rate'] = funding_score
        score += funding_score
        
        # ─── 2. LONG/SHORT RATIO (0-5 points) ───
        ratio_score = await self._score_long_short_ratio(futures_symbol, direction, positive, negative)
        factors['long_short_ratio'] = ratio_score
        score += ratio_score
        
        # ─── 3. LIQUIDATIONS (0-3 points) ───
        liq_score = await self._score_liquidations(futures_symbol, direction, positive, negative)
        factors['liquidations'] = liq_score
        score += liq_score
        
        # ─── 4. FEAR & GREED (0-2 points) ───
        fg_score = await self._score_fear_greed(direction, positive, negative)
        factors['fear_greed'] = fg_score
        score += fg_score
        
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
    
    async def _score_funding_rate(self, symbol: str, direction: str,
                                  positive: List[str], negative: List[str]) -> float:
        """Score funding rate alignment (0-5 points)"""
        score = 0.0
        
        try:
            funding_data = await self.context_engine.fetch_funding_rates(symbol)
            rate = funding_data.get('funding_rate', 0)
            bias = funding_data.get('bias', 'neutral')
            is_extreme = funding_data.get('is_extreme', False)
            
            # Positive funding = longs pay shorts (crowded longs)
            # Negative funding = shorts pay longs (crowded shorts)
            
            if direction == 'LONG':
                if rate < -0.0005:  # Negative funding = shorts paying = good for longs
                    score = 5.0
                    positive.append(f"Negative funding ({rate:.4f}%) - shorts paying, good for LONG")
                elif rate < 0:
                    score = 3.0
                    positive.append(f"Slightly negative funding ({rate:.4f}%)")
                elif rate < 0.0005:
                    score = 2.5
                    positive.append("Neutral funding")
                else:
                    if is_extreme:
                        score = 0.0
                        negative.append(f"Extreme positive funding ({rate:.4f}%) - overleveraged longs, reversal risk")
                    else:
                        score = 1.0
                        negative.append(f"Positive funding ({rate:.4f}%) - longs paying")
            
            elif direction == 'SHORT':
                if rate > 0.0005:  # Positive funding = longs paying = good for shorts
                    score = 5.0
                    positive.append(f"Positive funding ({rate:.4f}%) - longs paying, good for SHORT")
                elif rate > 0:
                    score = 3.0
                    positive.append(f"Slightly positive funding ({rate:.4f}%)")
                elif rate > -0.0005:
                    score = 2.5
                    positive.append("Neutral funding")
                else:
                    if is_extreme:
                        score = 0.0
                        negative.append(f"Extreme negative funding ({rate:.4f}%) - overleveraged shorts, reversal risk")
                    else:
                        score = 1.0
                        negative.append(f"Negative funding ({rate:.4f}%) - shorts paying")
        
        except Exception as e:
            self.logger.debug(f"Funding rate fetch failed for {symbol}: {e}")
            score = 2.5  # Neutral if data unavailable
            positive.append("Funding rate data unavailable (neutral score)")
        
        return score
    
    async def _score_long_short_ratio(self, symbol: str, direction: str,
                                     positive: List[str], negative: List[str]) -> float:
        """
        Score long/short ratio (0-5 points)
        
        Note: Binance provides long/short ratio via:
        - Top Trader Long/Short Ratio (Accounts)
        - Top Trader Long/Short Ratio (Positions)
        - Global Long/Short Ratio
        
        We'll use a simple heuristic based on funding + OI for now.
        """
        score = 0.0
        
        try:
            # Get open interest as proxy
            oi_data = await self.context_engine.fetch_open_interest(symbol)
            oi = oi_data.get('open_interest', 0)
            high_oi = oi_data.get('high_oi', False)
            
            # Get funding to infer ratio
            funding_data = await self.context_engine.fetch_funding_rates(symbol)
            rate = funding_data.get('funding_rate', 0)
            
            # High OI + positive funding = crowded longs
            # High OI + negative funding = crowded shorts
            
            if direction == 'SHORT' and high_oi and rate > 0.0003:
                score = 5.0
                positive.append("High OI + positive funding = crowded longs, good for SHORT")
            elif direction == 'LONG' and high_oi and rate < -0.0003:
                score = 5.0
                positive.append("High OI + negative funding = crowded shorts, good for LONG")
            elif high_oi:
                score = 3.0
                positive.append("High open interest - active market")
            else:
                score = 2.5
                positive.append("Moderate open interest")
        
        except Exception as e:
            self.logger.debug(f"Long/short ratio fetch failed for {symbol}: {e}")
            score = 2.5  # Neutral
            positive.append("Long/short ratio data unavailable (neutral score)")
        
        return score
    
    async def _score_liquidations(self, symbol: str, direction: str,
                                  positive: List[str], negative: List[str]) -> float:
        """Score recent liquidations (0-3 points)"""
        score = 0.0
        
        try:
            liq_data = await self.context_engine.fetch_liquidations(symbol)
            liq_estimate = liq_data.get('liquidation_estimate', 'unknown')
            bias = liq_data.get('bias', 'neutral')
            
            # High liquidations = potential reversal zone
            if liq_estimate == 'high':
                if direction == 'LONG' and 'reversal_up' in bias:
                    score = 3.0
                    positive.append("High liquidations + reversal up bias - good for LONG")
                elif direction == 'SHORT' and 'reversal_down' in bias:
                    score = 3.0
                    positive.append("High liquidations + reversal down bias - good for SHORT")
                else:
                    score = 1.5
                    positive.append("High liquidations detected")
            elif liq_estimate == 'moderate':
                score = 2.0
                positive.append("Moderate liquidations")
            else:
                score = 1.5
                positive.append("Low liquidations")
        
        except Exception as e:
            self.logger.debug(f"Liquidation fetch failed for {symbol}: {e}")
            score = 1.5  # Neutral
            positive.append("Liquidation data unavailable (neutral score)")
        
        return score
    
    async def _score_fear_greed(self, direction: str, positive: List[str], negative: List[str]) -> float:
        """Score Fear & Greed Index alignment (0-2 points)"""
        score = 0.0
        
        try:
            fg_data = await self.context_engine.fetch_fear_greed_index()
            value = fg_data.get('value', 50)
            classification = fg_data.get('classification', 'Neutral')
            
            # Extreme Fear (<25) = good for LONG (buy the fear)
            # Extreme Greed (>75) = good for SHORT (sell the greed)
            
            if direction == 'LONG':
                if value < 25:
                    score = 2.0
                    positive.append(f"Extreme Fear ({value}) - good contrarian LONG setup")
                elif value < 40:
                    score = 1.5
                    positive.append(f"Fear ({value}) - moderate LONG opportunity")
                elif value < 60:
                    score = 1.0
                    positive.append(f"Neutral sentiment ({value})")
                else:
                    score = 0.5
                    negative.append(f"Greed ({value}) - not ideal for LONG")
            
            elif direction == 'SHORT':
                if value > 75:
                    score = 2.0
                    positive.append(f"Extreme Greed ({value}) - good contrarian SHORT setup")
                elif value > 60:
                    score = 1.5
                    positive.append(f"Greed ({value}) - moderate SHORT opportunity")
                elif value > 40:
                    score = 1.0
                    positive.append(f"Neutral sentiment ({value})")
                else:
                    score = 0.5
                    negative.append(f"Fear ({value}) - not ideal for SHORT")
        
        except Exception as e:
            self.logger.debug(f"Fear & Greed fetch failed: {e}")
            score = 1.0  # Neutral
            positive.append("Fear & Greed data unavailable (neutral score)")
        
        return score
    
    def _build_explanation(self, score: float, factors: Dict[str, float]) -> str:
        """Build human-readable explanation"""
        parts = []
        
        parts.append(f"Sentiment Score: {score:.1f}/15")
        
        if 'funding_rate' in factors:
            parts.append(f"Funding: {factors['funding_rate']:.1f}/5")
        
        if 'long_short_ratio' in factors:
            parts.append(f"Ratio: {factors['long_short_ratio']:.1f}/5")
        
        if 'liquidations' in factors:
            parts.append(f"Liq: {factors['liquidations']:.1f}/3")
        
        if 'fear_greed' in factors:
            parts.append(f"F&G: {factors['fear_greed']:.1f}/2")
        
        return " | ".join(parts)
