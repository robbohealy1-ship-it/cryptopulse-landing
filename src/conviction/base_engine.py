"""
Base Engine Class for Conviction Scoring

All conviction engines inherit from this base class to ensure consistent
scoring, logging, and explainability.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EngineScore:
    """Standard score output from any conviction engine"""
    score: float  # 0-20 or 0-15 depending on engine
    max_score: float  # Maximum possible score for this engine
    factors: Dict[str, float]  # Individual factor scores
    positive_factors: List[str]  # What contributed positively
    negative_factors: List[str]  # What contributed negatively
    explanation: str  # Human-readable explanation
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/display"""
        return {
            'score': round(self.score, 2),
            'max_score': self.max_score,
            'percentage': round((self.score / self.max_score) * 100, 1) if self.max_score > 0 else 0,
            'factors': {k: round(v, 2) for k, v in self.factors.items()},
            'positive_factors': self.positive_factors,
            'negative_factors': self.negative_factors,
            'explanation': self.explanation
        }


class BaseConvictionEngine(ABC):
    """
    Base class for all conviction engines.
    
    Each engine must:
    1. Define its max_score (0-20 or 0-15)
    2. Implement calculate() method
    3. Return EngineScore with breakdown
    """
    
    def __init__(self, name: str, max_score: float):
        self.name = name
        self.max_score = max_score
        self.logger = get_logger(f"conviction.{name}")
    
    @abstractmethod
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate conviction score for this engine.
        
        Args:
            df: OHLCV dataframe for the symbol
            symbol: Trading pair (e.g., 'BTC/USDT')
            direction: 'LONG' or 'SHORT'
            **kwargs: Additional engine-specific parameters
        
        Returns:
            EngineScore with breakdown
        """
        pass
    
    def _clamp_score(self, score: float) -> float:
        """Ensure score is within 0 to max_score range"""
        return max(0, min(score, self.max_score))
    
    def _log_score(self, symbol: str, score: EngineScore):
        """Log the score calculation"""
        pct = (score.score / score.max_score) * 100 if score.max_score > 0 else 0
        self.logger.debug(
            f"{self.name} | {symbol}: {score.score:.1f}/{score.max_score} ({pct:.0f}%) | "
            f"Positive: {len(score.positive_factors)} | Negative: {len(score.negative_factors)}"
        )
