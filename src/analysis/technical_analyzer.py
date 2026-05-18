import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice, OnBalanceVolumeIndicator
from typing import Dict, Optional, Tuple
from src.models.signal import TechnicalScore, SetupType, SignalDirection
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    def __init__(self):
        self.min_candles = 200
        
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df['ema_20'] = EMAIndicator(close=df['close'], window=20).ema_indicator()
        df['ema_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['ema_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        
        df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        macd = MACD(close=df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['atr'] = atr.average_true_range()
        
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        
        if len(df) > 0:
            vwap = VolumeWeightedAveragePrice(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df['volume']
            )
            df['vwap'] = vwap.volume_weighted_average_price()
        
        df['obv'] = OnBalanceVolumeIndicator(close=df['close'], volume=df['volume']).on_balance_volume()
        
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        return df
    
    def detect_trend(self, df: pd.DataFrame) -> Dict:
        if len(df) < self.min_candles:
            return {'direction': 'neutral', 'strength': 0}
        
        current_price = df['close'].iloc[-1]
        ema_20 = df['ema_20'].iloc[-1]
        ema_50 = df['ema_50'].iloc[-1]
        ema_200 = df['ema_200'].iloc[-1]
        
        trend_score = 0
        
        if current_price > ema_20 > ema_50 > ema_200:
            trend_score = 100
            direction = 'bullish'
        elif current_price < ema_20 < ema_50 < ema_200:
            trend_score = 100
            direction = 'bearish'
        elif current_price > ema_200:
            trend_score = 60
            direction = 'bullish'
        elif current_price < ema_200:
            trend_score = 60
            direction = 'bearish'
        else:
            trend_score = 30
            direction = 'neutral'
        
        return {
            'direction': direction,
            'strength': trend_score,
            'ema_20': ema_20,
            'ema_50': ema_50,
            'ema_200': ema_200
        }
    
    def detect_market_structure(self, df: pd.DataFrame) -> Dict:
        if len(df) < 50:
            return {'bos': False, 'choch': False, 'structure_score': 0}
        
        highs = df['high'].values
        lows = df['low'].values
        
        recent_high = np.max(highs[-20:])
        recent_low = np.min(lows[-20:])
        prev_high = np.max(highs[-40:-20])
        prev_low = np.min(lows[-40:-20])
        
        current_price = df['close'].iloc[-1]
        
        bos = False
        choch = False
        structure_score = 50
        
        if current_price > recent_high > prev_high:
            bos = True
            structure_score = 90
        elif current_price < recent_low < prev_low:
            bos = True
            structure_score = 90
        
        if (current_price > prev_high and df['close'].iloc[-20] < prev_high):
            choch = True
            structure_score = 85
        elif (current_price < prev_low and df['close'].iloc[-20] > prev_low):
            choch = True
            structure_score = 85
        
        return {
            'bos': bos,
            'choch': choch,
            'structure_score': structure_score,
            'recent_high': recent_high,
            'recent_low': recent_low
        }
    
    def detect_liquidity_sweep(self, df: pd.DataFrame) -> Optional[Dict]:
        if len(df) < 30:
            return None
        
        recent_data = df.tail(30)
        current_price = df['close'].iloc[-1]
        
        swing_low = recent_data['low'].min()
        swing_low_idx = recent_data['low'].idxmin()
        
        swing_high = recent_data['high'].max()
        swing_high_idx = recent_data['high'].idxmax()
        
        last_low = df['low'].iloc[-1]
        last_high = df['high'].iloc[-1]
        
        if last_low <= swing_low * 0.999 and current_price > swing_low * 1.002:
            return {
                'type': 'bullish_sweep',
                'setup_type': SetupType.LIQUIDITY_SWEEP,
                'direction': SignalDirection.LONG,
                'entry': current_price,
                'swept_level': swing_low,
                'confidence_boost': 15
            }
        
        if last_high >= swing_high * 1.001 and current_price < swing_high * 0.998:
            return {
                'type': 'bearish_sweep',
                'setup_type': SetupType.LIQUIDITY_SWEEP,
                'direction': SignalDirection.SHORT,
                'entry': current_price,
                'swept_level': swing_high,
                'confidence_boost': 15
            }
        
        return None
    
    def detect_fair_value_gap(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect FVGs where price has pulled back INTO the gap for entry"""
        if len(df) < 10:
            return None
        
        current_price = df['close'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        
        # Look at recent FVGs (last 10 candles ago, must have formed)
        for i in range(-10, -2):
            candle_1 = df.iloc[i-1]
            candle_2 = df.iloc[i]
            candle_3 = df.iloc[i+1]
            
            # Bullish FVG: candle_1.high < candle_3.low
            if candle_1['high'] < candle_3['low']:
                gap_low = candle_1['high']
                gap_high = candle_3['low']
                gap_size = gap_high - gap_low
                
                if gap_size / candle_2['close'] > 0.0015:
                    # Check if price has pulled back INTO the FVG (for LONG entry)
                    # Current price must be within or near the FVG zone
                    if current_low <= gap_high and current_price >= gap_low:
                        entry = (gap_low + gap_high) / 2  # Middle of FVG
                        return {
                            'type': 'bullish_fvg',
                            'setup_type': SetupType.FAIR_VALUE_GAP,
                            'direction': SignalDirection.LONG,
                            'entry': entry,
                            'stop_loss': gap_low - (gap_size * 0.5),
                            'gap_low': gap_low,
                            'gap_high': gap_high,
                            'confidence_boost': 12
                        }
            
            # Bearish FVG: candle_1.low > candle_3.high
            if candle_1['low'] > candle_3['high']:
                gap_low = candle_3['high']
                gap_high = candle_1['low']
                gap_size = gap_high - gap_low
                
                if gap_size / candle_2['close'] > 0.0015:
                    # Check if price has pulled back INTO the FVG (for SHORT entry)
                    if current_high >= gap_low and current_price <= gap_high:
                        entry = (gap_low + gap_high) / 2  # Middle of FVG
                        return {
                            'type': 'bearish_fvg',
                            'setup_type': SetupType.FAIR_VALUE_GAP,
                            'direction': SignalDirection.SHORT,
                            'entry': entry,
                            'stop_loss': gap_high + (gap_size * 0.5),
                            'gap_low': gap_low,
                            'gap_high': gap_high,
                            'confidence_boost': 12
                        }
        
        return None
    
    def detect_order_block(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect Order Blocks - the last opposing candle before a strong move"""
        if len(df) < 20:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Look for bullish order blocks (last down candle before strong up move)
        for i in range(-15, -3):
            # Check if there was a strong bullish move after candle i
            price_before = df['close'].iloc[i]
            price_after = df['close'].iloc[-1]
            
            # Strong bullish displacement (price moved up significantly)
            if (price_after - price_before) / price_before > 0.03:
                # Find the last bearish candle before the move (the OB)
                ob_candle = df.iloc[i]
                
                # Check if price has retraced into the OB zone
                ob_low = ob_candle['low']
                ob_high = ob_candle['high']
                
                if current_price <= ob_high and df['low'].iloc[-1] >= ob_low * 0.995:
                    entry = (ob_low + ob_high) / 2
                    return {
                        'type': 'bullish_ob',
                        'setup_type': SetupType.ORDER_BLOCK,
                        'direction': SignalDirection.LONG,
                        'entry': entry,
                        'stop_loss': ob_low * 0.99,
                        'ob_low': ob_low,
                        'ob_high': ob_high,
                        'confidence_boost': 14
                    }
            
            # Strong bearish displacement
            if (price_before - price_after) / price_before > 0.03:
                ob_candle = df.iloc[i]
                ob_low = ob_candle['low']
                ob_high = ob_candle['high']
                
                if current_price >= ob_low and df['high'].iloc[-1] <= ob_high * 1.005:
                    entry = (ob_low + ob_high) / 2
                    return {
                        'type': 'bearish_ob',
                        'setup_type': SetupType.ORDER_BLOCK,
                        'direction': SignalDirection.SHORT,
                        'entry': entry,
                        'stop_loss': ob_high * 1.01,
                        'ob_low': ob_low,
                        'ob_high': ob_high,
                        'confidence_boost': 14
                    }
        
        return None
    
    def detect_breaker_block(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect Breaker Blocks - when support becomes resistance or vice versa"""
        if len(df) < 30:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Find previous significant swing points
        highs = df['high'].values[-30:-5]
        lows = df['low'].values[-30:-5]
        
        swing_high = np.max(highs)
        swing_low = np.min(lows)
        
        # Bearish breaker: price swept a high, then broke below it
        if df['high'].iloc[-10:].max() >= swing_high * 0.998 and current_price < swing_high * 0.995:
            # The breaker block is the last bullish candle before the breakdown
            for i in range(-10, -2):
                if df['close'].iloc[i] > df['open'].iloc[i]:  # Bullish candle
                    breaker_low = df['low'].iloc[i]
                    breaker_high = df['high'].iloc[i]
                    if current_price >= breaker_low and current_price <= breaker_high * 1.005:
                        entry = breaker_high
                        return {
                            'type': 'bearish_breaker',
                            'setup_type': SetupType.BREAKER_BLOCK,
                            'direction': SignalDirection.SHORT,
                            'entry': entry,
                            'stop_loss': df['high'].iloc[-10:].max() * 1.005,
                            'confidence_boost': 13
                        }
        
        # Bullish breaker: price swept a low, then broke above it
        if df['low'].iloc[-10:].min() <= swing_low * 1.002 and current_price > swing_low * 1.005:
            for i in range(-10, -2):
                if df['close'].iloc[i] < df['open'].iloc[i]:  # Bearish candle
                    breaker_low = df['low'].iloc[i]
                    breaker_high = df['high'].iloc[i]
                    if current_price <= breaker_high and current_price >= breaker_low * 0.995:
                        entry = breaker_low
                        return {
                            'type': 'bullish_breaker',
                            'setup_type': SetupType.BREAKER_BLOCK,
                            'direction': SignalDirection.LONG,
                            'entry': entry,
                            'stop_loss': df['low'].iloc[-10:].min() * 0.995,
                            'confidence_boost': 13
                        }
        
        return None
    
    def detect_mitigation_block(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect Mitigation Blocks - when price returns to mitigate a previous order block"""
        if len(df) < 40:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Look for previous significant move (15-30 candles ago)
        for lookback in range(15, 35):
            if lookback >= len(df) - 5:
                break
            
            price_before = df['close'].iloc[-lookback]
            price_now = df['close'].iloc[-1]
            
            # Strong move up, now retracing
            if (price_now - price_before) / price_before > 0.04:
                # Find the mitigation block (bearish candles during the move)
                for i in range(-lookback + 1, -2):
                    candle = df.iloc[i]
                    if candle['close'] < candle['open']:  # Bearish candle = mitigation block
                        mb_low = candle['low']
                        mb_high = candle['high']
                        
                        # Price has returned to the mitigation block
                        if current_price <= mb_high and df['low'].iloc[-1] >= mb_low * 0.99:
                            entry = (mb_low + mb_high) / 2
                            return {
                                'type': 'bullish_mitigation',
                                'setup_type': SetupType.MITIGATION_BLOCK,
                                'direction': SignalDirection.LONG,
                                'entry': entry,
                                'stop_loss': mb_low * 0.99,
                                'confidence_boost': 12
                            }
            
            # Strong move down, now retracing
            if (price_before - price_now) / price_before > 0.04:
                for i in range(-lookback + 1, -2):
                    candle = df.iloc[i]
                    if candle['close'] > candle['open']:  # Bullish candle = mitigation block
                        mb_low = candle['low']
                        mb_high = candle['high']
                        
                        if current_price >= mb_low and df['high'].iloc[-1] <= mb_high * 1.01:
                            entry = (mb_low + mb_high) / 2
                            return {
                                'type': 'bearish_mitigation',
                                'setup_type': SetupType.MITIGATION_BLOCK,
                                'direction': SignalDirection.SHORT,
                                'entry': entry,
                                'stop_loss': mb_high * 1.01,
                                'confidence_boost': 12
                            }
        
        return None
    
    def detect_bos_choch_retest(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect BOS/CHoCH with retest entry"""
        if len(df) < 50:
            return None
        
        structure = self.detect_market_structure(df)
        if not structure['bos'] and not structure['choch']:
            return None
        
        current_price = df['close'].iloc[-1]
        recent_high = structure['recent_high']
        recent_low = structure['recent_low']
        
        # Bullish BOS/CHoCH retest
        if structure['bos'] or structure['choch']:
            if current_price > recent_high * 0.995 and current_price < recent_high * 1.01:
                # Price is retesting the broken high as support
                return {
                    'type': 'bos_retest_long',
                    'setup_type': SetupType.BOS_RETEST,
                    'direction': SignalDirection.LONG,
                    'entry': current_price,
                    'stop_loss': recent_low,
                    'confidence_boost': 11
                }
            
            if current_price < recent_low * 1.005 and current_price > recent_low * 0.99:
                # Price is retesting the broken low as resistance
                return {
                    'type': 'bos_retest_short',
                    'setup_type': SetupType.BOS_RETEST,
                    'direction': SignalDirection.SHORT,
                    'entry': current_price,
                    'stop_loss': recent_high,
                    'confidence_boost': 11
                }
        
        return None
    
    def detect_support_resistance(self, df: pd.DataFrame) -> Dict:
        if len(df) < 50:
            return {'levels': [], 'score': 0}
        
        highs = df['high'].values[-100:]
        lows = df['low'].values[-100:]
        
        resistance_levels = []
        support_levels = []
        
        for i in range(10, len(highs) - 10):
            if highs[i] == max(highs[i-10:i+10]):
                resistance_levels.append(highs[i])
        
        for i in range(10, len(lows) - 10):
            if lows[i] == min(lows[i-10:i+10]):
                support_levels.append(lows[i])
        
        current_price = df['close'].iloc[-1]
        
        nearest_support = max([s for s in support_levels if s < current_price], default=0)
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=float('inf'))
        
        score = 0
        if nearest_support and abs(current_price - nearest_support) / current_price < 0.01:
            score = 80
        if nearest_resistance != float('inf') and abs(current_price - nearest_resistance) / current_price < 0.01:
            score = 80
        
        return {
            'support_levels': support_levels[-5:],
            'resistance_levels': resistance_levels[-5:],
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'score': score
        }
    
    def calculate_volume_score(self, df: pd.DataFrame) -> float:
        if len(df) < 20:
            return 50
        
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        if volume_ratio > 2.0:
            return 95
        elif volume_ratio > 1.5:
            return 85
        elif volume_ratio > 1.2:
            return 70
        elif volume_ratio > 0.8:
            return 60
        else:
            return 40
    
    def calculate_momentum_score(self, df: pd.DataFrame) -> float:
        if len(df) < 50:
            return 50
        
        rsi = df['rsi'].iloc[-1]
        macd_diff = df['macd_diff'].iloc[-1]
        
        score = 50
        
        if 40 < rsi < 60:
            score += 20
        elif 30 < rsi < 70:
            score += 10
        
        if abs(macd_diff) > 0:
            if macd_diff > 0:
                score += 15
            else:
                score += 15
        
        return min(score, 100)
    
    def calculate_technical_score(self, df: pd.DataFrame) -> TechnicalScore:
        trend = self.detect_trend(df)
        structure = self.detect_market_structure(df)
        volume_score = self.calculate_volume_score(df)
        momentum_score = self.calculate_momentum_score(df)
        
        trend_score = trend['strength']
        structure_score = structure['structure_score']
        
        total_score = (
            trend_score * 0.35 +
            volume_score * 0.25 +
            momentum_score * 0.20 +
            structure_score * 0.20
        )
        
        return TechnicalScore(
            trend_score=trend_score,
            volume_score=volume_score,
            momentum_score=momentum_score,
            structure_score=structure_score,
            total_score=total_score
        )
    
    def calculate_stop_loss(self, df: pd.DataFrame, direction: SignalDirection, entry: float) -> float:
        atr = df['atr'].iloc[-1]
        
        if direction == SignalDirection.LONG:
            stop_loss = entry - (atr * 1.5)
        else:
            stop_loss = entry + (atr * 1.5)
        
        return stop_loss
    
    def calculate_take_profits(
        self,
        entry: float,
        stop_loss: float,
        direction: SignalDirection,
        min_rr: float = 2.0
    ) -> Tuple[float, float, float]:
        risk = abs(entry - stop_loss)
        
        if direction == SignalDirection.LONG:
            tp1 = entry + (risk * min_rr)
            tp2 = entry + (risk * (min_rr + 1))
            tp3 = entry + (risk * (min_rr + 2))
        else:
            tp1 = entry - (risk * min_rr)
            tp2 = entry - (risk * (min_rr + 1))
            tp3 = entry - (risk * (min_rr + 2))
        
        return tp1, tp2, tp3
    
    # ==================== ICHIMOKU CLOUD ====================
    
    def calculate_ichimoku(self, df: pd.DataFrame) -> Dict:
        """
        Calculate Ichimoku Cloud components for trend confirmation.
        Returns cloud, TK cross, and trend bias.
        """
        if len(df) < 52:
            return {}
        
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        tenkan_sen = (high_9 + low_9) / 2
        
        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        kijun_sen = (high_26 + low_26) / 2
        
        # Senkou Span A: (Tenkan-sen + Kijun-sen) / 2
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        # Senkou Span B: (52-period high + 52-period low) / 2
        high_52 = df['high'].rolling(window=52).max()
        low_52 = df['low'].rolling(window=52).min()
        senkou_span_b = ((high_52 + low_52) / 2).shift(26)
        
        # Chikou Span: Close price shifted back 26 periods
        chikou_span = df['close'].shift(-26)
        
        current_price = df['close'].iloc[-1]
        current_tenkan = tenkan_sen.iloc[-1]
        current_kijun = kijun_sen.iloc[-1]
        current_senkou_a = senkou_span_a.iloc[-1]
        current_senkou_b = senkou_span_b.iloc[-1]
        
        # Cloud color and position
        if pd.notna(current_senkou_a) and pd.notna(current_senkou_b):
            cloud_bullish = current_senkou_a > current_senkou_b
            above_cloud = current_price > max(current_senkou_a, current_senkou_b)
            below_cloud = current_price < min(current_senkou_a, current_senkou_b)
            in_cloud = not above_cloud and not below_cloud
            
            # TK Cross
            tk_bullish = current_tenkan > current_kijun
            tk_cross_recent = False
            if len(df) >= 3:
                prev_tenkan = tenkan_sen.iloc[-3]
                prev_kijun = kijun_sen.iloc[-3]
                if pd.notna(prev_tenkan) and pd.notna(prev_kijun):
                    if prev_tenkan <= prev_kijun and current_tenkan > current_kijun:
                        tk_cross_recent = True
            
            return {
                'tenkan_sen': current_tenkan,
                'kijun_sen': current_kijun,
                'senkou_a': current_senkou_a,
                'senkou_b': current_senkou_b,
                'cloud_bullish': cloud_bullish,
                'above_cloud': above_cloud,
                'below_cloud': below_cloud,
                'in_cloud': in_cloud,
                'tk_bullish': tk_bullish,
                'tk_cross_recent': tk_cross_recent,
            }
        
        return {}
    
    def score_ichimoku_alignment(self, df: pd.DataFrame, direction: SignalDirection) -> Tuple[float, str]:
        """
        Score how well price aligns with Ichimoku Cloud.
        Returns 0-100 and description.
        """
        ichi = self.calculate_ichimoku(df)
        if not ichi:
            return 50, "No Ichimoku data"
        
        score = 50
        details = []
        
        if direction == SignalDirection.LONG:
            if ichi.get('above_cloud'):
                score = 90
                details.append("Price above cloud (strong bullish)")
            elif ichi.get('in_cloud'):
                score = 60
                details.append("Price in cloud (neutral)")
            else:
                score = 20
                details.append("Price below cloud (bearish)")
            
            if ichi.get('tk_bullish'):
                score = min(100, score + 5)
                details.append("TK cross bullish")
            else:
                score = max(0, score - 10)
                details.append("TK cross bearish")
                
        else:  # SHORT
            if ichi.get('below_cloud'):
                score = 90
                details.append("Price below cloud (strong bearish)")
            elif ichi.get('in_cloud'):
                score = 60
                details.append("Price in cloud (neutral)")
            else:
                score = 20
                details.append("Price above cloud (bullish)")
            
            if not ichi.get('tk_bullish'):
                score = min(100, score + 5)
                details.append("TK cross bearish")
            else:
                score = max(0, score - 10)
                details.append("TK cross bullish")
        
        return score, " | ".join(details)
    
    # ==================== ADX (Average Directional Index) ====================
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Dict:
        """
        Calculate ADX for trend strength measurement.
        ADX > 25 = trending, ADX < 20 = ranging, ADX > 50 = very strong trend
        """
        if len(df) < period * 2:
            return {'adx': 0, 'plus_di': 0, 'minus_di': 0, 'trend_strength': 'weak'}
        
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        # True Range
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        true_range = np.maximum(np.maximum(tr1, tr2), tr3)
        
        # +DM / -DM
        plus_dm = np.maximum(highs[1:] - highs[:-1], 0)
        minus_dm = np.maximum(lows[:-1] - lows[1:], 0)
        
        # Smooth with Wilder's method (EMA-like)
        atr_series = pd.Series(true_range).ewm(alpha=1/period, min_periods=period).mean()
        plus_di_series = 100 * pd.Series(plus_dm).ewm(alpha=1/period, min_periods=period).mean() / atr_series
        minus_di_series = 100 * pd.Series(minus_dm).ewm(alpha=1/period, min_periods=period).mean() / atr_series
        
        dx = 100 * np.abs(plus_di_series - minus_di_series) / (plus_di_series + minus_di_series + 1e-10)
        adx_series = dx.ewm(alpha=1/period, min_periods=period).mean()
        
        adx_val = adx_series.iloc[-1] if pd.notna(adx_series.iloc[-1]) else 0
        plus_di_val = plus_di_series.iloc[-1] if pd.notna(plus_di_series.iloc[-1]) else 0
        minus_di_val = minus_di_series.iloc[-1] if pd.notna(minus_di_series.iloc[-1]) else 0
        
        if adx_val > 40:
            strength = 'very_strong'
        elif adx_val > 25:
            strength = 'strong'
        elif adx_val > 20:
            strength = 'moderate'
        else:
            strength = 'weak'
        
        return {
            'adx': adx_val,
            'plus_di': plus_di_val,
            'minus_di': minus_di_val,
            'trend_strength': strength,
            'bullish': plus_di_val > minus_di_val,
        }
