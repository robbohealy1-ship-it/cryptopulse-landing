"""
CRYPTO PULSE SIGNALS — Timeframe-Specific Trading Strategies
Each timeframe has its own personality, entry logic, and risk parameters.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime

from src.models.signal import SignalDirection, SetupType
from src.analysis.institutional_analyzer import InstitutionalAnalyzer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseTimeframeStrategy:
    """Base class for all timeframe strategies"""
    
    def __init__(self, timeframe: str):
        self.timeframe = timeframe
        self.analyzer = InstitutionalAnalyzer()
        self.min_confidence = 85
        self.min_risk_reward = 2.0
        self.session_required = True
        
    def is_valid_session(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check if current session is suitable for this timeframe"""
        score, details = self.analyzer.get_session_score(df, self.timeframe)
        min_session_score = self._get_min_session_score()
        
        if score < min_session_score:
            return False, f"Session score {score:.0f} < {min_session_score} ({details.get('session', 'unknown')})"
        
        return True, f"Session score {score:.0f} — {details.get('session', 'unknown')}"
    
    def _get_min_session_score(self) -> float:
        """Minimum session score for this timeframe"""
        return 50  # Default
    
    def analyze_volatility(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check volatility regime suitability"""
        regime = self.analyzer.detect_volatility_regime(df)
        
        # Most timeframes want either compression (about to expand) or balanced
        current_regime = regime.get('regime', 'unknown')
        
        if current_regime == 'compression':
            return True, "Volatility compression — expansion coming"
        elif current_regime == 'balanced':
            return True, "Balanced volatility"
        elif current_regime == 'expansion':
            # For higher timeframes, expansion can be good
            if self.timeframe in ['4h', '1d']:
                return True, "Volatility expansion — trend forming"
            return False, "Volatility expansion too chaotic for this timeframe"
        
        return True, "Volatility acceptable"
    
    def find_setup(self, df: pd.DataFrame, direction: SignalDirection) -> Optional[Dict]:
        """Find a valid setup for this timeframe. Override in subclass."""
        raise NotImplementedError
    
    def calculate_entry_sl_tp(self, df: pd.DataFrame, setup: Dict,
                               direction: SignalDirection) -> Tuple[float, float, float, float, float]:
        """Calculate entry, SL, TP1, TP2, TP3. Override in subclass."""
        raise NotImplementedError


class M15Strategy(BaseTimeframeStrategy):
    """
    15-Minute Strategy: Intraday Swing Trading
    - Hold time: 1-4 hours
    - Best: London-NY overlap (13:00-16:00 UTC)
    - Focus: Liquidity sweeps + volume profile + session alignment
    - Risk: Tight SL, quick exits
    """
    
    def __init__(self):
        super().__init__('15m')
        self.min_confidence = 85
        self.min_risk_reward = 2.0
        self.session_required = True
    
    def _get_min_session_score(self) -> float:
        return 65  # Need decent session for 15m
    
    def find_setup(self, df: pd.DataFrame, direction: SignalDirection) -> Optional[Dict]:
        """
        15m setups: Look for liquidity sweep + volume profile discount/premium
        """
        structure = self.analyzer.analyze_structure(df)
        
        if structure['trend'] == 'neutral':
            return None
        
        # For 15m, we want a clear liquidity sweep in the direction
        current_price = df['close'].iloc[-1]
        
        # Find liquidity zones
        zones = self.analyzer.find_liquidity_zones(df)
        
        if direction == SignalDirection.LONG:
            # Need: downtrend or potential reversal (could reverse up) + swept liquidity below
            if structure['trend'] not in ['downtrend', 'potential_reversal']:
                return None
            
            # Look for equal lows (liquidity below)
            equal_lows = [z for z in zones if z.type == 'equal_lows']
            if not equal_lows:
                return None
            
            # Check if price swept below recent low then reversed
            recent_low = df['low'].iloc[-10:].min()
            if df['low'].iloc[-1] <= recent_low * 1.002 and current_price > df['open'].iloc[-1]:
                return {
                    'type': SetupType.LIQUIDITY_SWEEP,
                    'direction': direction,
                    'entry_zone': (recent_low * 0.998, current_price),
                    'swept_level': recent_low,
                    'reason': '15m liquidity sweep + bullish reversal candle'
                }
        
        else:  # SHORT
            if structure['trend'] not in ['uptrend', 'potential_reversal']:
                return None
            
            equal_highs = [z for z in zones if z.type == 'equal_highs']
            if not equal_highs:
                return None
            
            recent_high = df['high'].iloc[-10:].max()
            if df['high'].iloc[-1] >= recent_high * 0.998 and current_price < df['open'].iloc[-1]:
                return {
                    'type': SetupType.LIQUIDITY_SWEEP,
                    'direction': direction,
                    'entry_zone': (current_price, recent_high * 1.002),
                    'swept_level': recent_high,
                    'reason': '15m liquidity sweep + bearish reversal candle'
                }
        
        return None
    
    def calculate_entry_sl_tp(self, df: pd.DataFrame, setup: Dict,
                               direction: SignalDirection) -> Tuple[float, float, float, float, float]:
        """15m: Tight entries, 2R minimum, quick targets"""
        current = df['close'].iloc[-1]
        atr = (df['high'].iloc[-20:] - df['low'].iloc[-20:]).mean()
        
        if direction == SignalDirection.LONG:
            entry = max(setup['entry_zone'][0], current * 0.998)
            sl = setup['swept_level'] * 0.997  # Below the sweep
            risk = entry - sl
            tp1 = entry + risk * 2.0
            tp2 = entry + risk * 3.0
            tp3 = entry + risk * 4.0
        else:
            entry = min(setup['entry_zone'][1], current * 1.002)
            sl = setup['swept_level'] * 1.003  # Above the sweep
            risk = sl - entry
            tp1 = entry - risk * 2.0
            tp2 = entry - risk * 3.0
            tp3 = entry - risk * 4.0
        
        return entry, sl, tp1, tp2, tp3


class H1Strategy(BaseTimeframeStrategy):
    """
    1-Hour Strategy: Swing Trading
    - Hold time: 4-24 hours
    - Best: Any active session (London or NY)
    - Focus: Order blocks + structure + higher TF alignment
    - Risk: Medium SL, wider targets
    """
    
    def __init__(self):
        super().__init__('1h')
        self.min_confidence = 85
        self.min_risk_reward = 2.5
        self.session_required = True
    
    def _get_min_session_score(self) -> float:
        return 55  # 1h is more flexible
    
    def find_setup(self, df: pd.DataFrame, direction: SignalDirection) -> Optional[Dict]:
        """
        1h setups: Order blocks at key structure points
        """
        structure = self.analyzer.analyze_structure(df)
        
        if structure['trend'] == 'neutral':
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Look for order blocks: last opposing candle before a strong move
        if len(df) < 30:
            return None
        
        if direction == SignalDirection.LONG:
            # Need structure support: higher lows or BOS
            if structure['trend'] not in ['uptrend', 'potential_reversal']:
                return None
            
            # Find bullish order block (last bearish candle before strong up move)
            for i in range(-20, -3):
                if i < -len(df):
                    break
                
                # Strong move up after this candle
                price_after = df['close'].iloc[-1]
                price_before = df['close'].iloc[i]
                
                if (price_after - price_before) / price_before > 0.02:  # 2%+ move
                    ob_candle = df.iloc[i]
                    
                    # Check if price retraced into the OB
                    ob_low = ob_candle['low']
                    ob_high = ob_candle['high']
                    
                    if current_price <= ob_high and df['low'].iloc[-1] >= ob_low * 0.995:
                        return {
                            'type': SetupType.ORDER_BLOCK,
                            'direction': direction,
                            'ob_low': ob_low,
                            'ob_high': ob_high,
                            'reason': '1h bullish order block + higher timeframe uptrend'
                        }
        
        else:  # SHORT
            if structure['trend'] not in ['downtrend', 'potential_reversal']:
                return None
            
            for i in range(-20, -3):
                if i < -len(df):
                    break
                
                price_after = df['close'].iloc[-1]
                price_before = df['close'].iloc[i]
                
                if (price_before - price_after) / price_before > 0.02:
                    ob_candle = df.iloc[i]
                    ob_low = ob_candle['low']
                    ob_high = ob_candle['high']
                    
                    if current_price >= ob_low and df['high'].iloc[-1] <= ob_high * 1.005:
                        return {
                            'type': SetupType.ORDER_BLOCK,
                            'direction': direction,
                            'ob_low': ob_low,
                            'ob_high': ob_high,
                            'reason': '1h bearish order block + higher timeframe downtrend'
                        }
        
        return None
    
    def calculate_entry_sl_tp(self, df: pd.DataFrame, setup: Dict,
                               direction: SignalDirection) -> Tuple[float, float, float, float, float]:
        """1h: Medium entries, 2.5R minimum, wider targets"""
        current = df['close'].iloc[-1]
        
        if direction == SignalDirection.LONG:
            entry = setup['ob_low']
            sl = entry * 0.985
            risk = entry - sl
            tp1 = entry + risk * 2.5
            tp2 = entry + risk * 3.5
            tp3 = entry + risk * 5.0
        else:
            entry = setup['ob_high']
            sl = entry * 1.015
            risk = sl - entry
            tp1 = entry - risk * 2.5
            tp2 = entry - risk * 3.5
            tp3 = entry - risk * 5.0
        
        return entry, sl, tp1, tp2, tp3


class H4Strategy(BaseTimeframeStrategy):
    """
    4-Hour Strategy: Position Trading
    - Hold time: 1-3 days
    - Best: Any time (4h is slow enough)
    - Focus: Major structure + volume profile + multi-day context
    - Risk: Wide SL, large targets (3R+)
    """
    
    def __init__(self):
        super().__init__('4h')
        self.min_confidence = 88  # Higher bar for 4h
        self.min_risk_reward = 3.0
        self.session_required = False  # 4h doesn't care about intraday session
    
    def _get_min_session_score(self) -> float:
        return 30  # 4h doesn't care about sessions
    
    def find_setup(self, df: pd.DataFrame, direction: SignalDirection) -> Optional[Dict]:
        """
        4h setups: Major structure breaks with volume confirmation
        """
        structure = self.analyzer.analyze_structure(df)
        
        # 4h needs BOS (break of structure) for high conviction
        if not structure.get('bos'):
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Volume profile for entry precision
        vol_profile = self.analyzer.calculate_volume_profile(df, num_bins=30)
        if not vol_profile:
            return None
        
        poc = next((l for l in vol_profile if l.type == 'poc'), None)
        
        if direction == SignalDirection.LONG:
            if structure['trend'] != 'uptrend':
                return None
            
            # Entry near POC or below (discount)
            if poc and current_price <= poc.price * 1.02:
                return {
                    'type': SetupType.BOS_RETEST,
                    'direction': direction,
                    'entry_reference': poc.price,
                    'reason': '4h BOS confirmed + entry at volume profile discount'
                }
        
        else:  # SHORT
            if structure['trend'] != 'downtrend':
                return None
            
            if poc and current_price >= poc.price * 0.98:
                return {
                    'type': SetupType.BOS_RETEST,
                    'direction': direction,
                    'entry_reference': poc.price,
                    'reason': '4h BOS confirmed + entry at volume profile premium'
                }
        
        return None
    
    def calculate_entry_sl_tp(self, df: pd.DataFrame, setup: Dict,
                               direction: SignalDirection) -> Tuple[float, float, float, float, float]:
        """4h: Wide entries, 3R minimum, large targets"""
        current = df['close'].iloc[-1]
        
        # Use recent swing for SL reference
        structure = self.analyzer.analyze_structure(df)
        
        if direction == SignalDirection.LONG:
            entry = current * 0.995
            sl = structure.get('recent_swing_low', entry * 0.97) * 0.995
            risk = entry - sl
            tp1 = entry + risk * 3.0
            tp2 = entry + risk * 4.5
            tp3 = entry + risk * 6.0
        else:
            entry = current * 1.005
            sl = structure.get('recent_swing_high', entry * 1.03) * 1.005
            risk = sl - entry
            tp1 = entry - risk * 3.0
            tp2 = entry - risk * 4.5
            tp3 = entry - risk * 6.0
        
        return entry, sl, tp1, tp2, tp3


class DailyStrategy(BaseTimeframeStrategy):
    """
    Daily Strategy: Macro Position Trading
    - Hold time: 3-7 days
    - Best: End of day analysis, weekly structure
    - Focus: Weekly/monthly structure + macro alignment + volume profile
    - Risk: Very wide SL, huge targets (4R+)
    """
    
    def __init__(self):
        super().__init__('1d')
        self.min_confidence = 90  # Highest bar
        self.min_risk_reward = 4.0
        self.session_required = False
    
    def _get_min_session_score(self) -> float:
        return 20  # Daily doesn't care about intraday
    
    def find_setup(self, df: pd.DataFrame, direction: SignalDirection) -> Optional[Dict]:
        """
        Daily setups: Major weekly/monthly structure breaks
        Only the highest conviction setups.
        """
        if len(df) < 50:
            return None
        
        structure = self.analyzer.analyze_structure(df)
        
        # Daily needs clear BOS + trend alignment
        if not structure.get('bos'):
            return None
        
        # Check for volume profile extreme
        vol_profile = self.analyzer.calculate_volume_profile(df, num_bins=20)
        if not vol_profile:
            return None
        
        current_price = df['close'].iloc[-1]
        
        if direction == SignalDirection.LONG:
            if structure['trend'] != 'uptrend':
                return None
            
            # Price should be near or below POC (discount entry)
            poc = next((l for l in vol_profile if l.type == 'poc'), None)
            if poc and current_price <= poc.price * 1.03:
                return {
                    'type': SetupType.BOS_RETEST,
                    'direction': direction,
                    'entry_reference': poc.price,
                    'reason': 'Daily BOS + macro uptrend + volume profile value entry'
                }
        
        else:  # SHORT
            if structure['trend'] != 'downtrend':
                return None
            
            poc = next((l for l in vol_profile if l.type == 'poc'), None)
            if poc and current_price >= poc.price * 0.97:
                return {
                    'type': SetupType.BOS_RETEST,
                    'direction': direction,
                    'entry_reference': poc.price,
                    'reason': 'Daily BOS + macro downtrend + volume profile premium entry'
                }
        
        return None
    
    def calculate_entry_sl_tp(self, df: pd.DataFrame, setup: Dict,
                               direction: SignalDirection) -> Tuple[float, float, float, float, float]:
        """Daily: Wide SL based on weekly structure, huge targets"""
        current = df['close'].iloc[-1]
        
        # Use ATR-based SL for daily (more robust)
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        if direction == SignalDirection.LONG:
            entry = current * 0.99
            sl = entry - (atr * 2.0)  # Wide SL: 2x ATR
            risk = entry - sl
            tp1 = entry + risk * 4.0
            tp2 = entry + risk * 6.0
            tp3 = entry + risk * 8.0
        else:
            entry = current * 1.01
            sl = entry + (atr * 2.0)
            risk = sl - entry
            tp1 = entry - risk * 4.0
            tp2 = entry - risk * 6.0
            tp3 = entry - risk * 8.0
        
        return entry, sl, tp1, tp2, tp3


class TimeframeStrategyFactory:
    """Factory to get the right strategy for a timeframe"""
    
    STRATEGIES = {
        '15m': M15Strategy,
        '1h': H1Strategy,
        '4h': H4Strategy,
        '1d': DailyStrategy
    }
    
    @classmethod
    def get_strategy(cls, timeframe: str) -> BaseTimeframeStrategy:
        strategy_class = cls.STRATEGIES.get(timeframe)
        if strategy_class:
            return strategy_class()
        # Default to 1h if unknown
        logger.warning(f"Unknown timeframe {timeframe}, defaulting to 1h strategy")
        return H1Strategy()
    
    @classmethod
    def get_supported_timeframes(cls) -> list:
        return list(cls.STRATEGIES.keys())
