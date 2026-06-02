"""
News Intelligence Engine - Wrapper around existing news analysis

Scoring: 0-15 points (normalized from existing context engine)

This engine wraps the existing EnhancedContextEngine's news analysis
to fit into the modular conviction engine framework.

Inputs:
- NewsAPI articles
- Sentiment analysis
- High-impact event detection
- Direction-aware scoring
"""

import pandas as pd
from typing import Dict, List
from .base_engine import BaseConvictionEngine, EngineScore
from src.analysis.enhanced_context_engine import EnhancedContextEngine


class NewsIntelligenceEngine(BaseConvictionEngine):
    """Analyzes and scores news impact (wrapper around existing system)"""
    
    def __init__(self):
        super().__init__(name="NewsIntelligence", max_score=15.0)
        self.context_engine = EnhancedContextEngine()
    
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate news intelligence score (0-15 points)
        
        Args:
            df: OHLCV dataframe (not used, but required by interface)
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
        
        Returns:
            EngineScore with breakdown
        """
        score = 0.0
        factors = {}
        positive = []
        negative = []
        
        try:
            # Use existing context engine to analyze news
            context_score = await self.context_engine.analyze_context(symbol, direction)
            
            # Extract news score (already 0-100, normalize to 0-15)
            raw_news_score = context_score.news_score
            score = (raw_news_score / 100) * self.max_score
            
            # Extract factors
            factors['raw_news_score'] = raw_news_score
            factors['sentiment_score'] = context_score.sentiment_score
            
            # Build positive/negative factors from context
            # Use news_score as proxy for news quality
            if context_score.news_score > 70:
                positive.append("Strong positive news detected")
            elif context_score.news_score < 30:
                negative.append("Negative news detected")
            
            # Use sentiment_score to determine alignment
            if context_score.sentiment_score > 60:
                positive.append(f"Positive sentiment aligns with {direction} direction")
            elif context_score.sentiment_score < 40:
                negative.append(f"Negative sentiment conflicts with {direction} direction")
            else:
                positive.append("Neutral news sentiment")
            
            # Clamp to max
            score = self._clamp_score(score)
            
        except Exception as e:
            self.logger.warning(f"News analysis failed for {symbol}: {e}")
            # Neutral score if news unavailable
            score = 7.5
            factors['error'] = str(e)
            positive.append("News data unavailable (neutral score)")
        
        # Build explanation
        explanation = self._build_explanation(score, factors, context_score if 'context_score' in locals() else None)
        
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
    
    def _build_explanation(self, score: float, factors: Dict[str, float], context_score) -> str:
        """Build human-readable explanation"""
        parts = []
        
        parts.append(f"News Score: {score:.1f}/15")
        
        if context_score:
            parts.append(f"Sentiment: {context_score.sentiment_score:.0f}/100")
            parts.append(f"News: {context_score.news_score:.0f}/100")
        
        return " | ".join(parts)
