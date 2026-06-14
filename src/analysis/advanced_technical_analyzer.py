"""
Advanced Technical Analyzer - Integrates Pine Script indicators
Includes: PVSRA, Market Structure (HH/HL/LL/LH), Pivot Points, ADR/AWR, 
Session Analysis, EMA Cloud, Vector Candles, and Multi-EMA Strategy
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AdvancedTechnicalAnalyzer:
    """
    Implements advanced technical analysis from TradingView Pine Scripts:
    - OMAR NASR Sniper (Structure + EMA + ATR-based TP/SL)
    - Traders Reality Main (PVSRA, Sessions, Pivots, ADR/AWR)
    - 3EMA Strategy (Fast/Middle/Slow EMA with ATR TP/SL)
    """
    
    def __init__(self):
        self.min_candles = 200
        
        # EMA periods from Pine Scripts
        self.fast_ema = 9
        self.middle_ema = 21
        self.slow_ema = 55
        self.trend_ema = 200
        self.cloud_ema = 50
        
        # ATR settings
        self.atr_length = 14
        self.tp1_mult = 1.5
        self.tp2_mult = 2.5
        self.tp3_mult = 4.0
        self.sl_mult = 2.0
        
        # Structure detection
        self.left_bars = 10
        self.right_bars = 10
        
        # PVSRA thresholds
        self.vector_volume_mult = 2.0  # 200% of avg volume
        self.blue_volume_mult = 1.5    # 150% of avg volume
        
    def analyze_comprehensive(self, df: pd.DataFrame, symbol: str) -> Dict:
        """
        Comprehensive technical analysis combining all Pine Script indicators
        Returns a detailed breakdown for signal generation
        """
        if len(df) < self.min_candles:
            logger.warning(f"{symbol}: Insufficient data ({len(df)} candles)")
            return self._empty_analysis()
        
        df = self._add_all_indicators(df)
        
        # Core analysis components
        ema_analysis = self._analyze_ema_structure(df)
        structure_analysis = self._analyze_market_structure(df)
        pvsra_analysis = self._analyze_pvsra(df)
        atr_levels = self._calculate_atr_levels(df)
        pivot_analysis = self._calculate_pivot_points(df)
        volume_analysis = self._analyze_volume_profile(df)
        
        # Generate trading signal if conditions met
        signal_detected = self._detect_entry_signal(
            df, ema_analysis, structure_analysis, pvsra_analysis
        )
        
        # Calculate overall technical score
        technical_score = self._calculate_technical_score(
            ema_analysis, structure_analysis, pvsra_analysis, volume_analysis
        )
        
        return {
            'ema_analysis': ema_analysis,
            'structure_analysis': structure_analysis,
            'pvsra_analysis': pvsra_analysis,
            'atr_levels': atr_levels,
            'pivot_analysis': pivot_analysis,
            'volume_analysis': volume_analysis,
            'signal_detected': signal_detected,
            'technical_score': technical_score,
            'description': self._generate_description(
                ema_analysis, structure_analysis, pvsra_analysis, signal_detected
            )
        }
    
    def _add_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to dataframe"""
        df = df.copy()
        
        # EMAs (5, 9, 13, 21, 50, 55, 200, 800)
        for period in [5, 9, 13, 21, 50, 55, 200, 800]:
            df[f'ema_{period}'] = EMAIndicator(close=df['close'], window=period).ema_indicator()
        
        # ATR
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=self.atr_length)
        df['atr'] = atr.average_true_range()
        
        # Volume indicators
        df['volume_sma_10'] = df['volume'].rolling(window=10).mean()
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_10']
        
        # Candle spread
        df['candle_spread'] = df['high'] - df['low']
        df['volume_spread'] = df['candle_spread'] * df['volume']
        df['max_volume_spread_10'] = df['volume_spread'].rolling(window=10).max()
        
        return df
    
    def _analyze_ema_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analyze EMA alignment and cloud structure
        Based on 3EMA strategy and OMAR NASR indicators
        """
        current = df.iloc[-1]
        
        ema_9 = current['ema_9']
        ema_21 = current['ema_21']
        ema_55 = current['ema_55']
        ema_200 = current['ema_200']
        price = current['close']
        
        # EMA alignment score
        bullish_alignment = (price > ema_9 > ema_21 > ema_55 > ema_200)
        bearish_alignment = (price < ema_9 < ema_21 < ema_55 < ema_200)
        
        # EMA crossovers (entry signals)
        prev = df.iloc[-2]
        fast_cross_middle_up = (current['ema_9'] > current['ema_21']) and (prev['ema_9'] <= prev['ema_21'])
        fast_cross_middle_down = (current['ema_9'] < current['ema_21']) and (prev['ema_9'] >= prev['ema_21'])
        middle_cross_slow_up = (current['ema_21'] > current['ema_55']) and (prev['ema_21'] <= prev['ema_55'])
        middle_cross_slow_down = (current['ema_21'] < current['ema_55']) and (prev['ema_21'] >= prev['ema_55'])
        
        # Price vs EMA 21 crossover (OMAR NASR signal)
        price_cross_ema21_up = (price > ema_21) and (prev['close'] <= prev['ema_21'])
        price_cross_ema21_down = (price < ema_21) and (prev['close'] >= prev['ema_21'])
        
        # Trend strength
        if bullish_alignment:
            trend = 'strong_bullish'
            trend_score = 95
        elif price > ema_200:
            trend = 'bullish'
            trend_score = 70
        elif bearish_alignment:
            trend = 'strong_bearish'
            trend_score = 95
        elif price < ema_200:
            trend = 'bearish'
            trend_score = 70
        else:
            trend = 'neutral'
            trend_score = 40
        
        return {
            'trend': trend,
            'trend_score': trend_score,
            'bullish_alignment': bullish_alignment,
            'bearish_alignment': bearish_alignment,
            'fast_cross_middle_up': fast_cross_middle_up,
            'fast_cross_middle_down': fast_cross_middle_down,
            'middle_cross_slow_up': middle_cross_slow_up,
            'middle_cross_slow_down': middle_cross_slow_down,
            'price_cross_ema21_up': price_cross_ema21_up,
            'price_cross_ema21_down': price_cross_ema21_down,
            'ema_9': ema_9,
            'ema_21': ema_21,
            'ema_55': ema_55,
            'ema_200': ema_200
        }
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Detect market structure: HH, HL, LH, LL (Higher Highs, Higher Lows, etc.)
        Based on OMAR NASR structure detection
        """
        if len(df) < (self.left_bars + self.right_bars + 1):
            return {'structure': 'unknown', 'structure_score': 0}
        
        highs = []
        lows = []
        
        # Find pivot highs and lows
        for i in range(self.left_bars, len(df) - self.right_bars):
            # Pivot high
            is_pivot_high = True
            for j in range(i - self.left_bars, i + self.right_bars + 1):
                if j != i and df['high'].iloc[j] >= df['high'].iloc[i]:
                    is_pivot_high = False
                    break
            if is_pivot_high:
                highs.append({'index': i, 'value': df['high'].iloc[i]})
            
            # Pivot low
            is_pivot_low = True
            for j in range(i - self.left_bars, i + self.right_bars + 1):
                if j != i and df['low'].iloc[j] <= df['low'].iloc[i]:
                    is_pivot_low = False
                    break
            if is_pivot_low:
                lows.append({'index': i, 'value': df['low'].iloc[i]})
        
        # Determine structure type
        structure_type = 'unknown'
        structure_score = 50
        
        if len(highs) >= 2:
            last_high = highs[-1]['value']
            prev_high = highs[-2]['value']
            
            if last_high > prev_high:
                structure_type = 'HH'  # Higher High
                structure_score = 85
            else:
                structure_type = 'LH'  # Lower High
                structure_score = 85
        
        if len(lows) >= 2:
            last_low = lows[-1]['value']
            prev_low = lows[-2]['value']
            
            if last_low > prev_low:
                if structure_type == 'HH':
                    structure_type = 'HH_HL'  # Bullish structure
                    structure_score = 95
                else:
                    structure_type = 'HL'  # Higher Low
                    structure_score = 85
            else:
                if structure_type == 'LH':
                    structure_type = 'LH_LL'  # Bearish structure
                    structure_score = 95
                else:
                    structure_type = 'LL'  # Lower Low
                    structure_score = 85
        
        return {
            'structure': structure_type,
            'structure_score': structure_score,
            'pivot_highs': highs[-3:] if len(highs) >= 3 else highs,
            'pivot_lows': lows[-3:] if len(lows) >= 3 else lows
        }
    
    def _analyze_pvsra(self, df: pd.DataFrame) -> Dict:
        """
        Price Volume Spread Range Analysis (PVSRA)
        Detects vector candles (high volume + spread)
        """
        if len(df) < 11:
            return {'vector_type': 'none', 'pvsra_score': 0}
        
        current = df.iloc[-1]
        
        # Check volume conditions
        avg_volume_10 = df['volume'].iloc[-11:-1].mean()
        volume_ratio = current['volume'] / avg_volume_10
        
        # Check volume-spread product
        max_vol_spread_10 = df['volume_spread'].iloc[-11:-1].max()
        current_vol_spread = current['volume_spread']
        
        is_green = current['close'] > current['open']
        is_red = current['close'] < current['open']
        
        # Determine vector type
        vector_type = 'none'
        pvsra_score = 0
        
        # Red/Green vectors (200% volume OR highest vol*spread)
        if volume_ratio >= self.vector_volume_mult or current_vol_spread >= max_vol_spread_10:
            if is_green:
                vector_type = 'green_vector'
                pvsra_score = 90
            elif is_red:
                vector_type = 'red_vector'
                pvsra_score = 90
        # Blue/Violet vectors (150% volume)
        elif volume_ratio >= self.blue_volume_mult:
            if is_green:
                vector_type = 'blue_vector'
                pvsra_score = 75
            elif is_red:
                vector_type = 'violet_vector'
                pvsra_score = 75
        else:
            vector_type = 'regular'
            pvsra_score = 40
        
        return {
            'vector_type': vector_type,
            'pvsra_score': pvsra_score,
            'volume_ratio': volume_ratio,
            'is_high_volume': volume_ratio >= self.blue_volume_mult
        }
    
    def _calculate_atr_levels(self, df: pd.DataFrame) -> Dict:
        """
        Calculate ATR-based TP and SL levels
        Based on OMAR NASR and 3EMA strategy
        """
        current = df.iloc[-1]
        price = current['close']
        atr = current['atr']
        
        # Long levels
        long_tp1 = price + (atr * self.tp1_mult)
        long_tp2 = price + (atr * self.tp2_mult)
        long_tp3 = price + (atr * self.tp3_mult)
        long_sl = price - (atr * self.sl_mult)
        
        # Short levels
        short_tp1 = price - (atr * self.tp1_mult)
        short_tp2 = price - (atr * self.tp2_mult)
        short_tp3 = price - (atr * self.tp3_mult)
        short_sl = price + (atr * self.sl_mult)
        
        return {
            'atr': atr,
            'long': {
                'entry': price,
                'tp1': long_tp1,
                'tp2': long_tp2,
                'tp3': long_tp3,
                'sl': long_sl,
                'rr': (long_tp1 - price) / (price - long_sl) if (price - long_sl) > 0 else 0
            },
            'short': {
                'entry': price,
                'tp1': short_tp1,
                'tp2': short_tp2,
                'tp3': short_tp3,
                'sl': short_sl,
                'rr': (price - short_tp1) / (short_sl - price) if (short_sl - price) > 0 else 0
            }
        }
    
    def _calculate_pivot_points(self, df: pd.DataFrame) -> Dict:
        """
        Calculate daily pivot points (PP, R1-R3, S1-S3, M0-M5)
        Based on Traders Reality Main indicator
        """
        if len(df) < 2:
            return {}
        
        # Use previous day's data for pivot calculation
        prev_day = df.iloc[-2]
        high = prev_day['high']
        low = prev_day['low']
        close = prev_day['close']
        
        # Pivot Point
        pp = (high + low + close) / 3
        
        # Resistance and Support levels
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp - s1 + r1
        s2 = pp - r1 + s1
        r3 = 2 * pp + high - 2 * low
        s3 = 2 * pp - (2 * high - low)
        
        # M-levels (mid-points)
        m0 = (s2 + s3) / 2
        m1 = (s1 + s2) / 2
        m2 = (pp + s1) / 2
        m3 = (pp + r1) / 2
        m4 = (r1 + r2) / 2
        m5 = (r2 + r3) / 2
        
        return {
            'pp': pp,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3,
            'm0': m0, 'm1': m1, 'm2': m2,
            'm3': m3, 'm4': m4, 'm5': m5
        }
    
    def _analyze_volume_profile(self, df: pd.DataFrame) -> Dict:
        """Analyze volume characteristics"""
        if len(df) < 20:
            return {'volume_score': 0}
        
        current = df.iloc[-1]
        avg_volume = df['volume'].iloc[-20:].mean()
        volume_ratio = current['volume'] / avg_volume
        
        if volume_ratio >= 2.0:
            volume_score = 95
            volume_strength = 'very_high'
        elif volume_ratio >= 1.5:
            volume_score = 80
            volume_strength = 'high'
        elif volume_ratio >= 1.0:
            volume_score = 60
            volume_strength = 'normal'
        else:
            volume_score = 30
            volume_strength = 'low'
        
        return {
            'volume_score': volume_score,
            'volume_strength': volume_strength,
            'volume_ratio': volume_ratio
        }
    
    def _detect_entry_signal(self, df: pd.DataFrame, ema_analysis: Dict, 
                            structure_analysis: Dict, pvsra_analysis: Dict) -> Optional[Dict]:
        """
        Detect entry signals based on combined indicators
        """
        # LONG signal conditions
        long_signal = (
            # EMA crossover
            (ema_analysis['price_cross_ema21_up'] or ema_analysis['middle_cross_slow_up']) and
            # Bullish structure
            structure_analysis['structure'] in ['HH_HL', 'HH', 'HL'] and
            # Strong volume
            pvsra_analysis['vector_type'] in ['green_vector', 'blue_vector']
        )
        
        # SHORT signal conditions
        short_signal = (
            # EMA crossover
            (ema_analysis['price_cross_ema21_down'] or ema_analysis['middle_cross_slow_down']) and
            # Bearish structure
            structure_analysis['structure'] in ['LH_LL', 'LH', 'LL'] and
            # Strong volume
            pvsra_analysis['vector_type'] in ['red_vector', 'violet_vector']
        )
        
        if long_signal:
            return {
                'direction': 'LONG',
                'trigger': 'EMA_CROSS_STRUCTURE_VOLUME',
                'confidence': 85
            }
        elif short_signal:
            return {
                'direction': 'SHORT',
                'trigger': 'EMA_CROSS_STRUCTURE_VOLUME',
                'confidence': 85
            }
        
        return None
    
    def _calculate_technical_score(self, ema_analysis: Dict, structure_analysis: Dict,
                                   pvsra_analysis: Dict, volume_analysis: Dict) -> float:
        """
        Calculate overall technical score (0-100)
        Weighted average of all components
        """
        weights = {
            'trend': 0.30,
            'structure': 0.25,
            'pvsra': 0.25,
            'volume': 0.20
        }
        
        score = (
            ema_analysis['trend_score'] * weights['trend'] +
            structure_analysis['structure_score'] * weights['structure'] +
            pvsra_analysis['pvsra_score'] * weights['pvsra'] +
            volume_analysis['volume_score'] * weights['volume']
        )
        
        return round(score, 2)
    
    def _generate_description(self, ema_analysis: Dict, structure_analysis: Dict,
                             pvsra_analysis: Dict, signal_detected: Optional[Dict]) -> str:
        """
        Generate human-readable description of technical analysis
        """
        parts = []
        
        # Trend
        trend = ema_analysis['trend']
        if trend == 'strong_bullish':
            parts.append("📈 Strong bullish trend (all EMAs aligned)")
        elif trend == 'bullish':
            parts.append("📈 Bullish trend (price above EMA 200)")
        elif trend == 'strong_bearish':
            parts.append("📉 Strong bearish trend (all EMAs aligned)")
        elif trend == 'bearish':
            parts.append("📉 Bearish trend (price below EMA 200)")
        else:
            parts.append("➡️ Neutral trend")
        
        # Structure
        structure = structure_analysis['structure']
        if structure == 'HH_HL':
            parts.append("🔺 Bullish structure (Higher Highs + Higher Lows)")
        elif structure == 'LH_LL':
            parts.append("🔻 Bearish structure (Lower Highs + Lower Lows)")
        elif structure in ['HH', 'HL']:
            parts.append(f"🔺 {structure} detected")
        elif structure in ['LH', 'LL']:
            parts.append(f"🔻 {structure} detected")
        
        # PVSRA
        vector = pvsra_analysis['vector_type']
        if vector == 'green_vector':
            parts.append("🟢 Green vector candle (high bullish volume)")
        elif vector == 'red_vector':
            parts.append("🔴 Red vector candle (high bearish volume)")
        elif vector == 'blue_vector':
            parts.append("🔵 Blue vector candle (elevated bullish volume)")
        elif vector == 'violet_vector':
            parts.append("🟣 Violet vector candle (elevated bearish volume)")
        
        # Signal
        if signal_detected:
            direction = signal_detected['direction']
            parts.append(f"✅ {direction} signal triggered")
        
        return " | ".join(parts)
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis structure"""
        return {
            'ema_analysis': {},
            'structure_analysis': {'structure': 'unknown', 'structure_score': 0},
            'pvsra_analysis': {'vector_type': 'none', 'pvsra_score': 0},
            'atr_levels': {},
            'pivot_analysis': {},
            'volume_analysis': {'volume_score': 0},
            'signal_detected': None,
            'technical_score': 0,
            'description': 'Insufficient data for analysis'
        }
