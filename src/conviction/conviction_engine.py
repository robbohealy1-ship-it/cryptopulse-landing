"""
Conviction Engine - Main Orchestrator for Multi-Factor Signal Scoring

This is the core conviction engine that combines all sub-engines into a unified
0-100 conviction score with full explainability.

Architecture:
1. Calculate scores from 7 sub-engines (0-120 total)
2. Normalize to 0-100
3. Apply Market Magnet multiplier (1.0-1.5x)
4. Apply Trap Detection penalty (0-25 points)
5. Clamp final score to 0-100

Sub-Engines:
- Market Structure (0-20)
- Liquidity (0-20)
- Volume (0-15)
- Sentiment (0-15)
- News Intelligence (0-15)
- On-Chain (0-15)
- DEX Momentum (0-20) - Future

Total: 120 points → normalized to 100
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from src.utils.logger import get_logger

from .market_structure_engine import MarketStructureEngine
from .liquidity_engine import LiquidityEngine
from .volume_engine import VolumeEngine
from .sentiment_engine import SentimentEngine
from .news_intelligence_engine import NewsIntelligenceEngine
from .onchain_engine import OnChainEngine
from .market_magnet_system import MarketMagnetSystem, MagnetLevel
from .trap_detection_engine import TrapDetectionEngine, TrapDetection

logger = get_logger(__name__)


@dataclass
class ConvictionBreakdown:
    """Complete conviction score breakdown"""
    # Final scores
    conviction_score: float  # 0-100
    tier: str  # 'ELITE', 'VIP', 'WATCHLIST', 'REJECTED'
    
    # Sub-engine scores
    market_structure_score: float  # 0-20
    liquidity_score: float  # 0-20
    volume_score: float  # 0-15
    sentiment_score: float  # 0-15
    news_score: float  # 0-15
    onchain_score: float  # 0-15
    dex_score: float  # 0-20 (future)
    
    # Modifiers
    base_score: float  # Before multipliers/penalties
    magnet_multiplier: float  # 1.0-1.5
    trap_penalty: float  # 0-25
    
    # Explainability
    positive_factors: List[str]
    negative_factors: List[str]
    detected_magnets: List[Dict]
    detected_traps: List[Dict]
    
    # Per-engine details
    engine_details: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/display"""
        return asdict(self)


class ConvictionEngine:
    """
    Main conviction engine orchestrator.
    
    Combines all sub-engines, magnets, and trap detection into a single
    0-100 conviction score with full explainability.
    """
    
    def __init__(self):
        self.logger = logger
        
        # Initialize all sub-engines
        self.market_structure = MarketStructureEngine()
        self.liquidity = LiquidityEngine()
        self.volume = VolumeEngine()
        self.sentiment = SentimentEngine()
        self.news = NewsIntelligenceEngine()
        self.onchain = OnChainEngine()
        
        # Initialize magnet and trap systems
        self.magnet_system = MarketMagnetSystem()
        self.trap_detection = TrapDetectionEngine()
        
        self.logger.info("🎯 Conviction Engine initialized - Multi-factor scoring active")
    
    async def calculate_conviction(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> ConvictionBreakdown:
        """
        Calculate complete conviction score (0-100)
        
        Args:
            df: OHLCV dataframe
            symbol: Trading pair (e.g., 'BTC/USDT')
            direction: 'LONG' or 'SHORT'
            **kwargs: Additional parameters
        
        Returns:
            ConvictionBreakdown with full score breakdown
        """
        self.logger.info(f"🎯 Calculating conviction for {symbol} {direction}...")
        
        # ─── STEP 1: Calculate all sub-engine scores ───
        market_structure_result = await self.market_structure.calculate(df, symbol, direction, **kwargs)
        liquidity_result = await self.liquidity.calculate(df, symbol, direction, **kwargs)
        volume_result = await self.volume.calculate(df, symbol, direction, **kwargs)
        sentiment_result = await self.sentiment.calculate(df, symbol, direction, **kwargs)
        news_result = await self.news.calculate(df, symbol, direction, **kwargs)
        onchain_result = await self.onchain.calculate(df, symbol, direction, **kwargs)
        
        # DEX score (future - for now, neutral 10/20)
        dex_score = 10.0
        
        # ─── STEP 2: Sum to get base score (0-120) ───
        base_total = (
            market_structure_result.score +
            liquidity_result.score +
            volume_result.score +
            sentiment_result.score +
            news_result.score +
            onchain_result.score +
            dex_score
        )
        
        # ─── STEP 3: Normalize to 0-100 ───
        base_score = (base_total / 120.0) * 100.0
        
        # ─── STEP 4: Apply Market Magnet multiplier ───
        magnet_multiplier, detected_magnets = self.magnet_system.calculate_multiplier(df, symbol, direction)
        score_after_magnets = base_score * magnet_multiplier
        
        # ─── STEP 5: Apply Trap Detection penalty ───
        trap_penalty, detected_traps = await self.trap_detection.calculate_penalty(df, symbol, direction)
        final_score = score_after_magnets - trap_penalty
        
        # ─── STEP 6: Clamp to 0-100 ───
        final_score = max(0, min(100, final_score))
        
        # ─── STEP 7: Determine tier ───
        tier = self._determine_tier(final_score)
        
        # ─── STEP 8: Collect all positive/negative factors ───
        positive_factors = []
        negative_factors = []
        
        for result in [market_structure_result, liquidity_result, volume_result, 
                      sentiment_result, news_result, onchain_result]:
            positive_factors.extend(result.positive_factors)
            negative_factors.extend(result.negative_factors)
        
        # Add magnet factors
        if detected_magnets:
            for magnet in detected_magnets:
                positive_factors.append(f"Near {magnet.type.replace('_', ' ')}: ${magnet.price:,.4f}")
        
        # Add trap factors
        if detected_traps:
            for trap in detected_traps:
                negative_factors.append(f"{trap.type.replace('_', ' ').title()}: {trap.explanation}")
        
        # ─── STEP 9: Build engine details ───
        engine_details = {
            'market_structure': market_structure_result.to_dict(),
            'liquidity': liquidity_result.to_dict(),
            'volume': volume_result.to_dict(),
            'sentiment': sentiment_result.to_dict(),
            'news': news_result.to_dict(),
            'onchain': onchain_result.to_dict(),
        }
        
        # ─── STEP 10: Create breakdown ───
        breakdown = ConvictionBreakdown(
            conviction_score=final_score,
            tier=tier,
            market_structure_score=market_structure_result.score,
            liquidity_score=liquidity_result.score,
            volume_score=volume_result.score,
            sentiment_score=sentiment_result.score,
            news_score=news_result.score,
            onchain_score=onchain_result.score,
            dex_score=dex_score,
            base_score=base_score,
            magnet_multiplier=magnet_multiplier,
            trap_penalty=trap_penalty,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            detected_magnets=[asdict(m) for m in detected_magnets],
            detected_traps=[asdict(t) for t in detected_traps],
            engine_details=engine_details
        )
        
        # ─── STEP 11: Log summary ───
        self.logger.info(
            f"🎯 {symbol} {direction} Conviction: {final_score:.1f}/100 ({tier}) | "
            f"Base: {base_score:.1f} | Magnet: {magnet_multiplier:.2f}x | Trap: -{trap_penalty:.1f} | "
            f"Struct: {market_structure_result.score:.1f}/20 | "
            f"Liq: {liquidity_result.score:.1f}/20 | "
            f"Vol: {volume_result.score:.1f}/15 | "
            f"Sent: {sentiment_result.score:.1f}/15 | "
            f"News: {news_result.score:.1f}/15"
        )
        
        return breakdown
    
    def _determine_tier(self, score: float) -> str:
        """Determine signal tier based on conviction score"""
        if score >= 90:
            return 'ELITE'
        elif score >= 80:
            return 'VIP'
        elif score >= 70:
            return 'WATCHLIST'
        else:
            return 'REJECTED'
    
    def get_explanation(self, breakdown: ConvictionBreakdown) -> str:
        """Generate human-readable explanation"""
        lines = []
        
        lines.append(f"═══ CONVICTION SCORE: {breakdown.conviction_score:.1f}/100 ({breakdown.tier}) ═══")
        lines.append("")
        
        lines.append("📊 ENGINE BREAKDOWN:")
        lines.append(f"  Market Structure: {breakdown.market_structure_score:.1f}/20")
        lines.append(f"  Liquidity: {breakdown.liquidity_score:.1f}/20")
        lines.append(f"  Volume: {breakdown.volume_score:.1f}/15")
        lines.append(f"  Sentiment: {breakdown.sentiment_score:.1f}/15")
        lines.append(f"  News: {breakdown.news_score:.1f}/15")
        lines.append(f"  On-Chain: {breakdown.onchain_score:.1f}/15")
        lines.append(f"  DEX Momentum: {breakdown.dex_score:.1f}/20 (future)")
        lines.append("")
        
        lines.append(f"🎯 SCORING FLOW:")
        lines.append(f"  Base Score: {breakdown.base_score:.1f}/100")
        lines.append(f"  × Magnet Multiplier: {breakdown.magnet_multiplier:.2f}x")
        lines.append(f"  − Trap Penalty: {breakdown.trap_penalty:.1f}")
        lines.append(f"  = Final Score: {breakdown.conviction_score:.1f}/100")
        lines.append("")
        
        if breakdown.detected_magnets:
            lines.append(f"🧲 MAGNETS DETECTED ({len(breakdown.detected_magnets)}):")
            for magnet in breakdown.detected_magnets[:3]:
                lines.append(f"  • {magnet['type'].replace('_', ' ').title()} at ${magnet['price']:,.4f}")
            lines.append("")
        
        if breakdown.detected_traps:
            lines.append(f"⚠️ TRAPS DETECTED ({len(breakdown.detected_traps)}):")
            for trap in breakdown.detected_traps:
                lines.append(f"  • {trap['type'].replace('_', ' ').title()}: {trap['explanation']}")
            lines.append("")
        
        if breakdown.positive_factors:
            lines.append(f"✅ POSITIVE FACTORS ({len(breakdown.positive_factors)}):")
            for factor in breakdown.positive_factors[:5]:
                lines.append(f"  • {factor}")
            lines.append("")
        
        if breakdown.negative_factors:
            lines.append(f"❌ NEGATIVE FACTORS ({len(breakdown.negative_factors)}):")
            for factor in breakdown.negative_factors[:5]:
                lines.append(f"  • {factor}")
        
        return "\n".join(lines)
