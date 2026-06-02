"""
Market Magnet System - Detects key liquidity magnets and applies multipliers

Magnets are price levels that attract liquidity:
- Daily High/Low
- Weekly High/Low
- Monthly High/Low
- Round numbers ($100, $1000, $10000, etc.)
- VWAP zones
- Previous session high/low

When price is near a magnet, conviction score gets a multiplier boost.

Multiplier Range: 1.0 to 1.5x
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MagnetLevel:
    """Represents a liquidity magnet level"""
    price: float
    type: str  # 'daily_high', 'daily_low', 'weekly_high', etc.
    strength: float  # 0.05 to 0.20 (multiplier contribution)
    distance_pct: float  # Distance from current price (%)


class MarketMagnetSystem:
    """
    Detects and scores proximity to key liquidity magnets.
    
    Returns a multiplier (1.0 to 1.5x) based on how many magnets
    are nearby and their strength.
    """
    
    def __init__(self):
        self.logger = logger
        self.proximity_threshold = 0.01  # Within 1% = "near" a magnet
    
    def calculate_multiplier(self, df: pd.DataFrame, symbol: str, direction: str) -> Tuple[float, List[MagnetLevel]]:
        """
        Calculate conviction multiplier based on magnet proximity
        
        Args:
            df: OHLCV dataframe
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
        
        Returns:
            (multiplier, detected_magnets)
            multiplier: 1.0 to 1.5
            detected_magnets: List of nearby magnets
        """
        if len(df) < 30:
            return 1.0, []
        
        current_price = df['close'].iloc[-1]
        magnets = []
        
        # ─── 1. DAILY HIGH/LOW ───
        magnets.extend(self._detect_daily_levels(df, current_price))
        
        # ─── 2. WEEKLY HIGH/LOW ───
        magnets.extend(self._detect_weekly_levels(df, current_price))
        
        # ─── 3. MONTHLY HIGH/LOW ───
        magnets.extend(self._detect_monthly_levels(df, current_price))
        
        # ─── 4. ROUND NUMBERS ───
        magnets.extend(self._detect_round_numbers(current_price))
        
        # ─── 5. VWAP ───
        vwap_magnet = self._detect_vwap(df, current_price)
        if vwap_magnet:
            magnets.append(vwap_magnet)
        
        # ─── 6. PREVIOUS SESSION HIGH/LOW ───
        magnets.extend(self._detect_session_levels(df, current_price))
        
        # Calculate total multiplier
        multiplier = 1.0
        nearby_magnets = []
        
        for magnet in magnets:
            if magnet.distance_pct <= self.proximity_threshold:
                multiplier += magnet.strength
                nearby_magnets.append(magnet)
        
        # Cap multiplier at 1.5x
        multiplier = min(multiplier, 1.5)
        
        if nearby_magnets:
            self.logger.info(
                f"🧲 {symbol}: {len(nearby_magnets)} magnets nearby | "
                f"Multiplier: {multiplier:.2f}x | "
                f"Magnets: {', '.join([m.type for m in nearby_magnets])}"
            )
        
        return multiplier, nearby_magnets
    
    def _detect_daily_levels(self, df: pd.DataFrame, current_price: float) -> List[MagnetLevel]:
        """Detect daily high/low magnets"""
        magnets = []
        
        # Last 24 candles (1h) or 1 candle (1d)
        lookback = min(24, len(df))
        daily_high = df['high'].iloc[-lookback:].max()
        daily_low = df['low'].iloc[-lookback:].min()
        
        # Daily high magnet
        distance_high = abs(current_price - daily_high) / daily_high
        if distance_high <= 0.02:  # Within 2%
            magnets.append(MagnetLevel(
                price=daily_high,
                type='daily_high',
                strength=0.10,
                distance_pct=distance_high
            ))
        
        # Daily low magnet
        distance_low = abs(current_price - daily_low) / daily_low
        if distance_low <= 0.02:
            magnets.append(MagnetLevel(
                price=daily_low,
                type='daily_low',
                strength=0.10,
                distance_pct=distance_low
            ))
        
        return magnets
    
    def _detect_weekly_levels(self, df: pd.DataFrame, current_price: float) -> List[MagnetLevel]:
        """Detect weekly high/low magnets"""
        magnets = []
        
        # Last 168 candles (1h) or 7 candles (1d)
        lookback = min(168, len(df))
        weekly_high = df['high'].iloc[-lookback:].max()
        weekly_low = df['low'].iloc[-lookback:].min()
        
        # Weekly high magnet
        distance_high = abs(current_price - weekly_high) / weekly_high
        if distance_high <= 0.02:
            magnets.append(MagnetLevel(
                price=weekly_high,
                type='weekly_high',
                strength=0.15,  # Stronger than daily
                distance_pct=distance_high
            ))
        
        # Weekly low magnet
        distance_low = abs(current_price - weekly_low) / weekly_low
        if distance_low <= 0.02:
            magnets.append(MagnetLevel(
                price=weekly_low,
                type='weekly_low',
                strength=0.15,
                distance_pct=distance_low
            ))
        
        return magnets
    
    def _detect_monthly_levels(self, df: pd.DataFrame, current_price: float) -> List[MagnetLevel]:
        """Detect monthly high/low magnets"""
        magnets = []
        
        # Last 720 candles (1h) or 30 candles (1d)
        lookback = min(720, len(df))
        if lookback < 30:
            return []  # Not enough data
        
        monthly_high = df['high'].iloc[-lookback:].max()
        monthly_low = df['low'].iloc[-lookback:].min()
        
        # Monthly high magnet
        distance_high = abs(current_price - monthly_high) / monthly_high
        if distance_high <= 0.02:
            magnets.append(MagnetLevel(
                price=monthly_high,
                type='monthly_high',
                strength=0.20,  # Strongest magnet
                distance_pct=distance_high
            ))
        
        # Monthly low magnet
        distance_low = abs(current_price - monthly_low) / monthly_low
        if distance_low <= 0.02:
            magnets.append(MagnetLevel(
                price=monthly_low,
                type='monthly_low',
                strength=0.20,
                distance_pct=distance_low
            ))
        
        return magnets
    
    def _detect_round_numbers(self, current_price: float) -> List[MagnetLevel]:
        """Detect round number magnets"""
        magnets = []
        
        # Determine round number scale based on price
        if current_price >= 10000:
            scale = 1000  # $10k, $11k, $12k, etc.
        elif current_price >= 1000:
            scale = 100   # $1000, $1100, $1200, etc.
        elif current_price >= 100:
            scale = 10    # $100, $110, $120, etc.
        elif current_price >= 10:
            scale = 1     # $10, $11, $12, etc.
        elif current_price >= 1:
            scale = 0.1   # $1.0, $1.1, $1.2, etc.
        else:
            scale = 0.01  # $0.10, $0.11, $0.12, etc.
        
        # Find nearest round number
        nearest_round = round(current_price / scale) * scale
        distance = abs(current_price - nearest_round) / current_price
        
        if distance <= 0.01:  # Within 1%
            magnets.append(MagnetLevel(
                price=nearest_round,
                type='round_number',
                strength=0.10,
                distance_pct=distance
            ))
        
        return magnets
    
    def _detect_vwap(self, df: pd.DataFrame, current_price: float) -> MagnetLevel:
        """Detect VWAP magnet"""
        if len(df) < 20:
            return None
        
        # Calculate VWAP (Volume Weighted Average Price)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).sum() / df['volume'].sum()
        
        distance = abs(current_price - vwap) / vwap
        
        if distance <= 0.015:  # Within 1.5%
            return MagnetLevel(
                price=vwap,
                type='vwap',
                strength=0.05,
                distance_pct=distance
            )
        
        return None
    
    def _detect_session_levels(self, df: pd.DataFrame, current_price: float) -> List[MagnetLevel]:
        """Detect previous session high/low magnets"""
        magnets = []
        
        if len(df) < 48:  # Need at least 2 sessions (24h each for 1h chart)
            return []
        
        # Previous session = candles from -48 to -24
        prev_session_high = df['high'].iloc[-48:-24].max()
        prev_session_low = df['low'].iloc[-48:-24].min()
        
        # Previous session high
        distance_high = abs(current_price - prev_session_high) / prev_session_high
        if distance_high <= 0.015:
            magnets.append(MagnetLevel(
                price=prev_session_high,
                type='prev_session_high',
                strength=0.08,
                distance_pct=distance_high
            ))
        
        # Previous session low
        distance_low = abs(current_price - prev_session_low) / prev_session_low
        if distance_low <= 0.015:
            magnets.append(MagnetLevel(
                price=prev_session_low,
                type='prev_session_low',
                strength=0.08,
                distance_pct=distance_low
            ))
        
        return magnets
    
    def get_magnet_explanation(self, magnets: List[MagnetLevel]) -> str:
        """Generate human-readable explanation of detected magnets"""
        if not magnets:
            return "No magnets nearby"
        
        parts = []
        for magnet in magnets:
            parts.append(
                f"{magnet.type.replace('_', ' ').title()} at ${magnet.price:,.4f} "
                f"({magnet.distance_pct*100:.2f}% away)"
            )
        
        return " | ".join(parts)
