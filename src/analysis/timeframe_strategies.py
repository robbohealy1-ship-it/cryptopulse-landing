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
from src.analysis.stop_validator import StopValidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseTimeframeStrategy:
    """Base class for all timeframe strategies"""
    
    def __init__(self, timeframe: str):
        self.timeframe = timeframe
        self.analyzer = InstitutionalAnalyzer()
        self.stop_validator = StopValidator()
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
            # For higher timeframes and 15m momentum, expansion can be good
            if self.timeframe in ['4h', '1d', '15m']:
                return True, "Volatility expansion — momentum/trend forming"
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
        return 50  # Allow 15m signals in any active session
    
    def find_setup(self, df: pd.DataFrame, direction: SignalDirection) -> Optional[Dict]:
        """
        15m setups: Liquidity sweeps, order blocks, and fair value gaps.
        Multiple setup types = more signals while keeping quality high.
        """
        structure = self.analyzer.analyze_structure(df)

        if structure['trend'] == 'neutral':
            return None

        current_price = df['close'].iloc[-1]

        # ─── SETUP 1: Liquidity Sweep (original, strictest) ───
        zones = self.analyzer.find_liquidity_zones(df)

        if direction == SignalDirection.LONG:
            if structure['trend'] in ['downtrend', 'potential_reversal']:
                equal_lows = [z for z in zones if z.type == 'equal_lows']
                if equal_lows:
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
            if structure['trend'] in ['uptrend', 'potential_reversal']:
                equal_highs = [z for z in zones if z.type == 'equal_highs']
                if equal_highs:
                    recent_high = df['high'].iloc[-10:].max()
                    if df['high'].iloc[-1] >= recent_high * 0.998 and current_price < df['open'].iloc[-1]:
                        return {
                            'type': SetupType.LIQUIDITY_SWEEP,
                            'direction': direction,
                            'entry_zone': (current_price, recent_high * 1.002),
                            'swept_level': recent_high,
                            'reason': '15m liquidity sweep + bearish reversal candle'
                        }

        # ─── SETUP 2: Order Block (same as 1h, but tighter) ───
        if len(df) >= 30:
            if direction == SignalDirection.LONG:
                if structure['trend'] in ['uptrend', 'potential_reversal']:
                    for i in range(-7, -2):
                        if i < -len(df):
                            break
                        price_after = df['close'].iloc[-1]
                        price_before = df['close'].iloc[i]
                        if (price_after - price_before) / price_before > 0.015:  # 1.5%+ move (tighter than 1h's 2%)
                            ob_candle = df.iloc[i]
                            ob_low, ob_high = ob_candle['low'], ob_candle['high']
                            if current_price <= ob_high and df['low'].iloc[-1] >= ob_low * 0.995:
                                return {
                                    'type': SetupType.ORDER_BLOCK,
                                    'direction': direction,
                                    'ob_low': ob_low,
                                    'ob_high': ob_high,
                                    'reason': '15m bullish order block + momentum'
                                }
            else:  # SHORT
                if structure['trend'] in ['downtrend', 'potential_reversal']:
                    for i in range(-7, -2):
                        if i < -len(df):
                            break
                        price_after = df['close'].iloc[-1]
                        price_before = df['close'].iloc[i]
                        if (price_before - price_after) / price_before > 0.015:
                            ob_candle = df.iloc[i]
                            ob_low, ob_high = ob_candle['low'], ob_candle['high']
                            if current_price >= ob_low and df['high'].iloc[-1] <= ob_high * 1.005:
                                return {
                                    'type': SetupType.ORDER_BLOCK,
                                    'direction': direction,
                                    'ob_low': ob_low,
                                    'ob_high': ob_high,
                                    'reason': '15m bearish order block + momentum'
                                }

        # ─── SETUP 3: Fair Value Gap (price leaves a gap, returns to fill it) ───
        if len(df) >= 10:
            for i in range(-10, -2):
                if i < -len(df) + 1:
                    break
                candle_i = df.iloc[i]
                candle_next = df.iloc[i + 1]
                if direction == SignalDirection.LONG:
                    # Bullish FVG: next candle low > current candle high (gap up)
                    if candle_next['low'] > candle_i['high']:
                        fvg_top = candle_next['low']
                        fvg_bottom = candle_i['high']
                        if current_price <= fvg_top and current_price >= fvg_bottom * 0.998:
                            return {
                                'type': SetupType.FAIR_VALUE_GAP,
                                'direction': direction,
                                'fvg_top': fvg_top,
                                'fvg_bottom': fvg_bottom,
                                'reason': '15m bullish FVG retest'
                            }
                else:  # SHORT
                    # Bearish FVG: next candle high < current candle low (gap down)
                    if candle_next['high'] < candle_i['low']:
                        fvg_top = candle_i['low']
                        fvg_bottom = candle_next['high']
                        if current_price >= fvg_bottom and current_price <= fvg_top * 1.002:
                            return {
                                'type': SetupType.FAIR_VALUE_GAP,
                                'direction': direction,
                                'fvg_top': fvg_top,
                                'fvg_bottom': fvg_bottom,
                                'reason': '15m bearish FVG retest'
                            }

        return None
    
    def calculate_entry_sl_tp(self, df: pd.DataFrame, setup: Dict,
                               direction: SignalDirection) -> Tuple[float, float, float, float, float]:
        """15m: Tight entries, 2R minimum, quick targets"""
        current = df['close'].iloc[-1]
        atr = (df['high'].iloc[-20:] - df['low'].iloc[-20:]).mean()
        
        setup_type = setup.get('type')
        
        if direction == SignalDirection.LONG:
            if setup_type == SetupType.LIQUIDITY_SWEEP:
                entry = max(setup['entry_zone'][0], current * 0.998)
                sl = setup['swept_level'] * 0.997
            elif setup_type == SetupType.ORDER_BLOCK:
                # Cap entry at current price — never chase above current
                entry = min(setup['ob_low'], current)
                sl = entry * 0.985
            elif setup_type == SetupType.FAIR_VALUE_GAP:
                entry = setup['fvg_bottom']
                sl = setup['fvg_bottom'] * 0.995
            else:
                entry = current * 0.998
                sl = current * 0.985
            
            risk = entry - sl
            tp1 = entry + risk * 2.0
            tp2 = entry + risk * 3.0
            tp3 = entry + risk * 4.0
        else:
            if setup_type == SetupType.LIQUIDITY_SWEEP:
                entry = min(setup['entry_zone'][1], current * 1.002)
                sl = setup['swept_level'] * 1.003
            elif setup_type == SetupType.ORDER_BLOCK:
                # Cap entry at current price — never chase below current
                entry = max(setup['ob_high'], current)
                sl = entry * 1.015
            elif setup_type == SetupType.FAIR_VALUE_GAP:
                entry = setup['fvg_top']
                sl = setup['fvg_top'] * 1.005
            else:
                entry = current * 1.002
                sl = current * 1.015
            
            risk = sl - entry
            tp1 = entry - risk * 2.0
            tp2 = entry - risk * 3.0
            tp3 = entry - risk * 4.0
        
        # GUARD: prevent inverted SL and negative TPs
        if direction == SignalDirection.LONG and sl >= entry:
            sl = entry * 0.95
            risk = entry - sl
            tp1 = entry + risk * 2.0
            tp2 = entry + risk * 3.0
            tp3 = entry + risk * 4.0
        elif direction == SignalDirection.SHORT and sl <= entry:
            sl = entry * 1.05
            risk = sl - entry
            tp1 = entry - risk * 2.0
            tp2 = entry - risk * 3.0
            tp3 = entry - risk * 4.0
        min_tp = entry * 0.1 if entry > 0 else 0.0001
        if tp3 <= 0:
            tp3 = min_tp
        if tp2 <= 0:
            tp2 = min_tp * 2
        if tp1 <= 0:
            tp1 = min_tp * 3
        
        # SMART STOP VALIDATION FOR 15M
        is_valid, adjusted_stop, warning = self.stop_validator.validate_stop(
            entry=entry, stop=sl, timeframe='15m', df=df, direction=direction.value
        )
        if not is_valid and adjusted_stop:
            logger.warning(f"15m stop adjusted: ${sl:.8f} -> ${adjusted_stop:.8f}. {warning}")
            sl = adjusted_stop
            risk = abs(entry - sl)
            if direction == SignalDirection.LONG:
                tp1, tp2, tp3 = entry + risk * 2.0, entry + risk * 3.0, entry + risk * 4.0
            else:
                tp1, tp2, tp3 = entry - risk * 2.0, entry - risk * 3.0, entry - risk * 4.0
        elif warning:
            setup['stop_warning'] = warning
        
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
        self.min_risk_reward = 2.0
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
        
        # GUARD: prevent inverted SL and negative TPs
        if direction == SignalDirection.LONG and sl >= entry:
            sl = entry * 0.95
            risk = entry - sl
            tp1 = entry + risk * 2.5
            tp2 = entry + risk * 3.5
            tp3 = entry + risk * 5.0
        elif direction == SignalDirection.SHORT and sl <= entry:
            sl = entry * 1.05
            risk = sl - entry
            tp1 = entry - risk * 2.5
            tp2 = entry - risk * 3.5
            tp3 = entry - risk * 5.0
        min_tp = entry * 0.1 if entry > 0 else 0.0001
        if tp3 <= 0:
            tp3 = min_tp
        if tp2 <= 0:
            tp2 = min_tp * 2
        if tp1 <= 0:
            tp1 = min_tp * 3
        
        # SMART STOP VALIDATION FOR 1H
        is_valid, adjusted_stop, warning = self.stop_validator.validate_stop(
            entry=entry, stop=sl, timeframe='1h', df=df, direction=direction.value
        )
        if not is_valid and adjusted_stop:
            logger.warning(f"1h stop adjusted: ${sl:.8f} -> ${adjusted_stop:.8f}. {warning}")
            sl = adjusted_stop
            risk = abs(entry - sl)
            if direction == SignalDirection.LONG:
                tp1, tp2, tp3 = entry + risk * 2.5, entry + risk * 3.5, entry + risk * 5.0
            else:
                tp1, tp2, tp3 = entry - risk * 2.5, entry - risk * 3.5, entry - risk * 5.0
        elif warning:
            setup['stop_warning'] = warning
        
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
        self.min_confidence = 85
        self.min_risk_reward = 2.0
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
        """4h: Wide entries, 3R minimum, large targets with smart stop validation"""
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
        
        # GUARD: prevent inverted SL and negative TPs
        if direction == SignalDirection.LONG and sl >= entry:
            sl = entry * 0.95
            risk = entry - sl
            tp1 = entry + risk * 3.0
            tp2 = entry + risk * 4.5
            tp3 = entry + risk * 6.0
        elif direction == SignalDirection.SHORT and sl <= entry:
            sl = entry * 1.05
            risk = sl - entry
            tp1 = entry - risk * 3.0
            tp2 = entry - risk * 4.5
            tp3 = entry - risk * 6.0
        min_tp = entry * 0.1 if entry > 0 else 0.0001
        if tp3 <= 0:
            tp3 = min_tp
        if tp2 <= 0:
            tp2 = min_tp * 2
        if tp1 <= 0:
            tp1 = min_tp * 3
        
        # SMART STOP VALIDATION: Check if stop makes sense for 4h structure
        is_valid, adjusted_stop, warning = self.stop_validator.validate_stop(
            entry=entry,
            stop=sl,
            timeframe='4h',
            df=df,
            direction=direction.value
        )
        
        if not is_valid and adjusted_stop:
            # Stop is too tight - use adjusted stop
            logger.warning(f"4h stop adjusted: ${sl:.8f} -> ${adjusted_stop:.8f}. Reason: {warning}")
            sl = adjusted_stop
            # Recalculate TPs with new stop
            if direction == SignalDirection.LONG:
                risk = entry - sl
                tp1 = entry + risk * 3.0
                tp2 = entry + risk * 4.5
                tp3 = entry + risk * 6.0
            else:
                risk = sl - entry
                tp1 = entry - risk * 3.0
                tp2 = entry - risk * 4.5
                tp3 = entry - risk * 6.0
        elif warning:
            # Stop is valid but has a warning (tight structure, etc.)
            logger.info(f"4h stop warning: {warning}")
            # Store warning in setup for signal message
            setup['stop_warning'] = warning
        
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
        self.min_confidence = 85
        self.min_risk_reward = 2.0
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
        
        # GUARD: prevent inverted SL (SL must be below entry for LONG, above for SHORT)
        if direction == SignalDirection.LONG and sl >= entry:
            sl = entry * 0.95
            risk = entry - sl
            tp1 = entry + risk * 4.0
            tp2 = entry + risk * 6.0
            tp3 = entry + risk * 8.0
        elif direction == SignalDirection.SHORT and sl <= entry:
            sl = entry * 1.05
            risk = sl - entry
            tp1 = entry - risk * 4.0
            tp2 = entry - risk * 6.0
            tp3 = entry - risk * 8.0
        
        # GUARD: prevent negative or zero TPs for very low-priced tokens
        min_tp = entry * 0.1 if entry > 0 else 0.0001
        if tp3 <= 0:
            tp3 = min_tp
        if tp2 <= 0:
            tp2 = min_tp * 2
        if tp1 <= 0:
            tp1 = min_tp * 3
        
        # SMART STOP VALIDATION FOR DAILY
        is_valid, adjusted_stop, warning = self.stop_validator.validate_stop(
            entry=entry, stop=sl, timeframe='1d', df=df, direction=direction.value
        )
        if not is_valid and adjusted_stop:
            logger.warning(f"1d stop adjusted: ${sl:.8f} -> ${adjusted_stop:.8f}. {warning}")
            sl = adjusted_stop
            risk = abs(entry - sl)
            if direction == SignalDirection.LONG:
                tp1, tp2, tp3 = entry + risk * 4.0, entry + risk * 6.0, entry + risk * 8.0
            else:
                tp1, tp2, tp3 = entry - risk * 4.0, entry - risk * 6.0, entry - risk * 8.0
        elif warning:
            setup['stop_warning'] = warning
        
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
