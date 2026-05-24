"""
CRYPTO PULSE SIGNALS — Smart Stop Loss Validator
Context-aware stop validation that respects structure while preventing noise hits.
No arbitrary minimums - everything is based on ATR, recent volatility, and structure.
"""

import pandas as pd
from typing import Tuple, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StopValidator:
    """
    Validates stop loss distances based on:
    1. Timeframe-appropriate minimums (not arbitrary, based on typical noise)
    2. ATR percentage (stop should be meaningful relative to volatility)
    3. Recent range (stop should respect actual price movement)
    4. Structure compression (tight stops OK if structure is genuinely tight)
    """
    
    # Minimum stop distances by timeframe (% of price)
    # These are NOT arbitrary - based on typical noise/spread for each timeframe
    TIMEFRAME_MINIMUMS = {
        '5m': 0.15,   # Scalping - tight is OK
        '15m': 0.25,  # Intraday swing
        '1h': 0.35,   # Hourly structure
        '4h': 0.40,   # 4h structure (NOT 0.5% - respect tight structure)
        '1d': 0.60,   # Daily swings
    }
    
    def __init__(self):
        pass
    
    def validate_stop(
        self,
        entry: float,
        stop: float,
        timeframe: str,
        df: pd.DataFrame,
        direction: str
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Validate stop loss makes sense for the timeframe and market structure.
        
        Args:
            entry: Entry price
            stop: Proposed stop loss price
            timeframe: Trading timeframe (5m, 15m, 1h, 4h, 1d)
            df: Price dataframe (for ATR and range calculation)
            direction: LONG or SHORT
            
        Returns:
            (is_valid, adjusted_stop, warning_message)
            - is_valid: True if stop is acceptable (may have warning)
            - adjusted_stop: Suggested stop if original is invalid, None if valid
            - warning_message: Warning to show user, None if all good
        """
        # Calculate stop distance as percentage
        stop_pct = abs((stop - entry) / entry) * 100
        
        # Get timeframe minimum
        min_stop = self.TIMEFRAME_MINIMUMS.get(timeframe, 0.30)
        
        # Calculate ATR (14-period)
        atr = self._calculate_atr(df)
        atr_pct = (atr / entry) * 100 if atr and entry > 0 else None
        
        # Calculate recent range (last 20 candles)
        recent_range = self._calculate_recent_range(df)
        
        # ==================== VALIDATION CHECKS ====================
        
        # Check 1: Absolute minimum for timeframe
        if stop_pct < min_stop:
            # BUT: Allow if structure is genuinely compressed
            if recent_range and stop_pct > recent_range * 0.25:
                # Stop is >25% of recent range - structure is tight, allow it
                warning = (
                    f"⚠️ Tight stop ({stop_pct:.2f}%) - structure is compressed. "
                    f"Recent {timeframe} range: {recent_range:.2f}%. Monitor closely."
                )
                logger.info(f"Tight stop allowed: {stop_pct:.2f}% < {min_stop}% but {stop_pct/recent_range*100:.0f}% of recent range")
                return (True, None, warning)
            else:
                # Too tight even for compressed structure - reject
                logger.warning(f"Stop too tight: {stop_pct:.2f}% < {min_stop}% minimum for {timeframe}")
                
                # Suggest adjusted stop at minimum distance
                if direction == "LONG":
                    adjusted_stop = entry * (1 - min_stop / 100)
                else:
                    adjusted_stop = entry * (1 + min_stop / 100)
                
                return (
                    False,
                    adjusted_stop,
                    f"Stop too tight ({stop_pct:.2f}% < {min_stop}% minimum for {timeframe}). "
                    f"Suggested: ${adjusted_stop:.8f} ({min_stop}% away)"
                )
        
        # Check 2: Stop vs ATR (should be at least 30% of ATR)
        if atr_pct:
            atr_ratio = stop_pct / atr_pct
            if atr_ratio < 0.30:
                # Stop is less than 30% of ATR - likely to get hit by noise
                warning = (
                    f"⚠️ Stop is only {atr_ratio*100:.0f}% of ATR ({atr_pct:.2f}%). "
                    f"May get hit by normal volatility. Consider widening."
                )
                logger.info(f"Stop vs ATR warning: {stop_pct:.2f}% stop vs {atr_pct:.2f}% ATR")
                return (True, None, warning)
            elif atr_ratio < 0.50:
                # Between 30-50% of ATR - acceptable but flag it
                warning = f"ℹ️ Stop is {atr_ratio*100:.0f}% of ATR - watch for volatility spikes"
                return (True, None, warning)
        
        # Check 3: Stop vs recent volatility
        if recent_range:
            range_ratio = stop_pct / recent_range
            if range_ratio < 0.20:
                # Stop is less than 20% of recent range - too tight for current volatility
                logger.warning(f"Stop too tight for volatility: {stop_pct:.2f}% vs {recent_range:.2f}% recent range")
                
                # Suggest stop at 25% of recent range
                suggested_stop_pct = recent_range * 0.25
                if direction == "LONG":
                    adjusted_stop = entry * (1 - suggested_stop_pct / 100)
                else:
                    adjusted_stop = entry * (1 + suggested_stop_pct / 100)
                
                return (
                    False,
                    adjusted_stop,
                    f"Stop too tight for recent volatility. Recent {timeframe} range: {recent_range:.2f}%. "
                    f"Suggested: ${adjusted_stop:.8f} ({suggested_stop_pct:.2f}% away)"
                )
        
        # Check 4: Extremely wide stops (sanity check)
        max_stop = self._get_max_stop(timeframe)
        if stop_pct > max_stop:
            warning = (
                f"⚠️ Very wide stop ({stop_pct:.2f}%) for {timeframe}. "
                f"Verify structure placement is correct."
            )
            logger.info(f"Wide stop flagged: {stop_pct:.2f}% > {max_stop}% typical for {timeframe}")
            return (True, None, warning)
        
        # All checks passed
        logger.debug(f"Stop validated: {stop_pct:.2f}% for {timeframe} (ATR: {atr_pct:.2f}%, Range: {recent_range:.2f}%)")
        return (True, None, None)
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        try:
            if len(df) < period + 1:
                return None
            
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            
            return float(atr) if not pd.isna(atr) else None
        except Exception as e:
            logger.debug(f"ATR calculation failed: {e}")
            return None
    
    def _calculate_recent_range(self, df: pd.DataFrame, lookback: int = 20) -> Optional[float]:
        """Calculate recent price range as percentage"""
        try:
            if len(df) < lookback:
                lookback = len(df)
            
            recent = df.iloc[-lookback:]
            high = recent['high'].max()
            low = recent['low'].min()
            current = df['close'].iloc[-1]
            
            range_pct = ((high - low) / current) * 100
            return float(range_pct)
        except Exception as e:
            logger.debug(f"Range calculation failed: {e}")
            return None
    
    def _get_max_stop(self, timeframe: str) -> float:
        """Get maximum reasonable stop distance for timeframe (sanity check)"""
        max_stops = {
            '5m': 1.0,    # 1% max for 5m
            '15m': 1.5,   # 1.5% max for 15m
            '1h': 2.5,    # 2.5% max for 1h
            '4h': 4.0,    # 4% max for 4h
            '1d': 6.0,    # 6% max for daily
        }
        return max_stops.get(timeframe, 3.0)
