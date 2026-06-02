"""
CryptoPulse Conviction Engine - Modular Multi-Factor Scoring System

This package contains the conviction-based signal scoring system that combines
multiple analysis engines into a unified 0-100 conviction score.

Engines:
- Market Structure Engine (0-20 points)
- Liquidity Engine (0-20 points)
- Volume Engine (0-15 points)
- Sentiment Engine (0-15 points)
- News Intelligence Engine (0-15 points)
- On-Chain Engine (0-15 points)
- DEX Momentum Engine (0-20 points)

Additional Systems:
- Market Magnet System (multiplier)
- Trap Detection Engine (penalty)
"""

from .conviction_engine import ConvictionEngine, ConvictionBreakdown
from .base_engine import BaseConvictionEngine, EngineScore
from .market_structure_engine import MarketStructureEngine
from .liquidity_engine import LiquidityEngine
from .volume_engine import VolumeEngine
from .sentiment_engine import SentimentEngine
from .news_intelligence_engine import NewsIntelligenceEngine
from .onchain_engine import OnChainEngine
from .market_magnet_system import MarketMagnetSystem, MagnetLevel
from .trap_detection_engine import TrapDetectionEngine, TrapDetection

__all__ = [
    'ConvictionEngine',
    'ConvictionBreakdown',
    'BaseConvictionEngine',
    'EngineScore',
    'MarketStructureEngine',
    'LiquidityEngine',
    'VolumeEngine',
    'SentimentEngine',
    'NewsIntelligenceEngine',
    'OnChainEngine',
    'MarketMagnetSystem',
    'MagnetLevel',
    'TrapDetectionEngine',
    'TrapDetection',
]
