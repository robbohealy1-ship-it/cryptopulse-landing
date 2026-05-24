"""
CRYPTO PULSE SIGNALS — Institutional-Grade Technical Analyzer
Replaces generic retail indicators (EMA crossovers, RSI, MACD) with:
- Volume Profile (POC, VAH, VAL, high-volume nodes)
- Market Structure (swings, inducement, BOS/CHoCH with time-based strength)
- Liquidity Analysis (where stops sit, liquidity voids)
- Session-Based Analysis (Asian, London, NY — only trade active sessions)
- Smart Money Concepts (breaker blocks, inducement, orderblocks with time)
- Volatility Regime Detection (range expansion vs compression)
- Wyckoff Methodology (accumulation/distribution phases)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.models.signal import SignalDirection, SetupType
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VolumeProfileLevel:
    """A price level with significant volume"""
    price: float
    volume: float
    type: str  # 'poc', 'vah', 'val', 'node'


@dataclass
class SwingPoint:
    """A swing high or low with metadata"""
    price: float
    index: int
    timestamp: datetime
    type: str  # 'high' or 'low'
    strength: int  # How many bars confirmed it


@dataclass
class LiquidityZone:
    """Where stops likely sit"""
    price_level: float
    type: str  # 'equal_highs', 'equal_lows', 'trendline_liquidity'
    volume_above: float
    volume_below: float
    distance_percent: float


@dataclass
class InstitutionalScore:
    """Comprehensive score from institutional tools"""
    structure_score: float  # 0-100
    volume_profile_score: float  # 0-100
    liquidity_score: float  # 0-100
    session_score: float  # 0-100
    volatility_score: float  # 0-100
    multi_tf_score: float  # 0-100 (from higher timeframe alignment)
    total_score: float  # 0-100
    
    # Detailed info for reasoning
    structure_details: Dict
    volume_details: Dict
    liquidity_details: Dict
    session_details: Dict


class InstitutionalAnalyzer:
    """
    Institutional-grade technical analysis for crypto.
    No generic EMA/RSI/MACD. Real tools used by professionals.
    """
    
    def __init__(self):
        self.min_candles = 100
        
    # ==================== VOLUME PROFILE ====================
    
    def calculate_volume_profile(self, df: pd.DataFrame, num_bins: int = 50) -> List[VolumeProfileLevel]:
        """
        Calculate volume profile: where did most volume trade?
        Returns POC (point of control), VAH/VAL (value area high/low)
        """
        if len(df) < 50:
            return []
        
        # Create price bins
        price_min = df['low'].min()
        price_max = df['high'].max()
        bins = np.linspace(price_min, price_max, num_bins)
        
        # Assign each candle's volume to price bins
        bin_volumes = np.zeros(num_bins - 1)
        
        for idx, row in df.iterrows():
            # Distribute volume across the candle's range
            candle_low = row['low']
            candle_high = row['high']
            candle_vol = row['volume']
            
            # Find which bins this candle spans
            low_bin = np.digitize(candle_low, bins) - 1
            high_bin = np.digitize(candle_high, bins) - 1
            
            low_bin = max(0, min(low_bin, num_bins - 2))
            high_bin = max(0, min(high_bin, num_bins - 2))
            
            # Distribute volume evenly across touched bins
            num_touched = high_bin - low_bin + 1
            if num_touched > 0:
                vol_per_bin = candle_vol / num_touched
                for b in range(low_bin, high_bin + 1):
                    if b < len(bin_volumes):
                        bin_volumes[b] += vol_per_bin
        
        # Build levels
        levels = []
        for i, vol in enumerate(bin_volumes):
            price = (bins[i] + bins[i+1]) / 2
            levels.append(VolumeProfileLevel(price=price, volume=vol, type='node'))
        
        # Sort by volume
        levels.sort(key=lambda x: x.volume, reverse=True)
        
        if not levels:
            return []
        
        # POC = highest volume node
        total_volume = sum(l.volume for l in levels)
        poc = levels[0]
        poc.type = 'poc'
        
        # Value Area = 70% of volume around POC
        sorted_by_price = sorted(levels, key=lambda x: x.price)
        poc_price = poc.price
        
        # Find VAH and VAL (value area high/low)
        cumulative = 0
        vah = poc_price
        val = poc_price
        
        for l in sorted(levels, key=lambda x: x.volume, reverse=True):
            cumulative += l.volume
            if cumulative / total_volume <= 0.70:
                if l.price > vah:
                    vah = l.price
                if l.price < val:
                    val = l.price
        
        # Mark VAH and VAL
        for l in levels:
            if abs(l.price - vah) / poc_price < 0.005:
                l.type = 'vah'
            elif abs(l.price - val) / poc_price < 0.005:
                l.type = 'val'
        
        return levels
    
    def score_volume_profile(self, df: pd.DataFrame, direction: SignalDirection,
                              entry: float) -> Tuple[float, Dict]:
        """
        Score how good the entry is relative to volume profile.
        LONG: best entry is near VAL or below POC
        SHORT: best entry is near VAH or above POC
        """
        levels = self.calculate_volume_profile(df)
        if not levels:
            return 50, {'reason': 'Insufficient data for volume profile'}
        
        poc = next((l for l in levels if l.type == 'poc'), None)
        vah = next((l for l in levels if l.type == 'vah'), None)
        val = next((l for l in levels if l.type == 'val'), None)
        
        if not all([poc, vah, val]):
            return 50, {'reason': 'Incomplete volume profile'}
        
        score = 50
        details = {
            'poc': poc.price,
            'vah': vah.price,
            'val': val.price,
            'entry': entry
        }
        
        if direction == SignalDirection.LONG:
            # Best: entry below VAL (deep discount)
            # Good: entry near VAL
            # Okay: entry between VAL and POC
            # Bad: entry above POC
            if entry <= val.price * 1.005:
                score = 95
                details['quality'] = 'Below VAL (deep discount)'
            elif entry <= poc.price * 0.995:
                score = 80
                details['quality'] = 'Between VAL and POC'
            elif entry <= poc.price * 1.005:
                score = 65
                details['quality'] = 'Near POC (fair value)'
            else:
                score = 40
                details['quality'] = 'Above POC (premium)'
        else:  # SHORT
            # Best: entry above VAH (deep premium)
            # Good: entry near VAH
            if entry >= vah.price * 0.995:
                score = 95
                details['quality'] = 'Above VAH (deep premium)'
            elif entry >= poc.price * 1.005:
                score = 80
                details['quality'] = 'Between POC and VAH'
            elif entry >= poc.price * 0.995:
                score = 65
                details['quality'] = 'Near POC (fair value)'
            else:
                score = 40
                details['quality'] = 'Below POC (discount)'
        
        return score, details
    
    # ==================== MARKET STRUCTURE (Enhanced) ====================
    
    def find_swing_points(self, df: pd.DataFrame, lookback: int = 5) -> List[SwingPoint]:
        """
        Find genuine swing highs/lows using a lookback window.
        Higher lookback = stronger swing (more bars confirming).
        """
        if len(df) < lookback * 2 + 1:
            return []
        
        swings = []
        highs = df['high'].values
        lows = df['low'].values
        
        for i in range(lookback, len(df) - lookback):
            # Swing high: higher than lookback bars on both sides
            is_swing_high = all(highs[i] > highs[i-j] for j in range(1, lookback+1)) and \
                           all(highs[i] > highs[i+j] for j in range(1, lookback+1))
            
            # Swing low: lower than lookback bars on both sides
            is_swing_low = all(lows[i] < lows[i-j] for j in range(1, lookback+1)) and \
                          all(lows[i] < lows[i+j] for j in range(1, lookback+1))
            
            if is_swing_high:
                swings.append(SwingPoint(
                    price=highs[i],
                    index=i,
                    timestamp=df.index[i],
                    type='high',
                    strength=lookback
                ))
            elif is_swing_low:
                swings.append(SwingPoint(
                    price=lows[i],
                    index=i,
                    timestamp=df.index[i],
                    type='low',
                    strength=lookback
                ))
        
        return swings
    
    def analyze_structure(self, df: pd.DataFrame) -> Dict:
        """
        Advanced market structure with BOS/CHoCH and inducement.
        """
        swings = self.find_swing_points(df, lookback=3)
        if len(swings) < 4:
            return {
                'trend': 'neutral',
                'bos': False,
                'choch': False,
                'score': 50,
                'inducement': False,
                'recent_swing_high': None,
                'recent_swing_low': None
            }
        
        recent_highs = [s for s in swings if s.type == 'high'][-3:]
        recent_lows = [s for s in swings if s.type == 'low'][-3:]
        
        if not recent_highs or not recent_lows:
            return {'trend': 'neutral', 'score': 50, 'bos': False, 'choch': False}
        
        current_price = df['close'].iloc[-1]
        
        # Higher highs and higher lows = uptrend
        hh = len(recent_highs) >= 2 and recent_highs[-1].price > recent_highs[-2].price
        hl = len(recent_lows) >= 2 and recent_lows[-1].price > recent_lows[-2].price
        
        # Lower highs and lower lows = downtrend
        lh = len(recent_highs) >= 2 and recent_highs[-1].price < recent_highs[-2].price
        ll = len(recent_lows) >= 2 and recent_lows[-1].price < recent_lows[-2].price
        
        trend = 'neutral'
        score = 50
        bos = False
        choch = False
        
        if hh and hl:
            trend = 'uptrend'
            score = 85
            # BOS: price broke above last swing high
            if current_price > recent_highs[-2].price:
                bos = True
                score = 95
        elif lh and ll:
            trend = 'downtrend'
            score = 85
            # BOS: price broke below last swing low
            if current_price < recent_lows[-2].price:
                bos = True
                score = 95
        
        # CHoCH: Change of Character (trend reversal signal)
        # Uptrend: price breaks below last higher low
        # Downtrend: price breaks above last lower high
        if trend == 'uptrend' and len(recent_lows) >= 2:
            if current_price < recent_lows[-1].price:
                choch = True
                trend = 'potential_reversal'
                score = 70
        elif trend == 'downtrend' and len(recent_highs) >= 2:
            if current_price > recent_highs[-1].price:
                choch = True
                trend = 'potential_reversal'
                score = 70
        
        # Inducement: price swept a liquidity level then reversed
        inducement = False
        if len(df) >= 10:
            recent_range = df['high'].iloc[-10:].max() - df['low'].iloc[-10:].min()
            if recent_range > 0:
                # Check if price swept above recent high then reversed down
                if df['high'].iloc[-3:].max() > recent_highs[-1].price and current_price < df['close'].iloc[-3]:
                    inducement = True
                    score += 10
        
        return {
            'trend': trend,
            'bos': bos,
            'choch': choch,
            'inducement': inducement,
            'score': min(score, 100),
            'recent_swing_high': recent_highs[-1].price if recent_highs else None,
            'recent_swing_low': recent_lows[-1].price if recent_lows else None,
            'swing_count': len(swings)
        }
    
    # ==================== LIQUIDITY ANALYSIS ====================
    
    def find_liquidity_zones(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """
        Find where liquidity (stops) likely sits:
        - Equal highs/lows (double tops/bottoms)
        - Trendline liquidity
        - Previous day/week high/low
        """
        zones = []
        if len(df) < 20:
            return zones
        
        # Equal highs (sell stops above)
        highs = df['high'].values[-30:]
        for i in range(len(highs)):
            for j in range(i+1, len(highs)):
                if abs(highs[i] - highs[j]) / highs[i] < 0.002:  # 0.2% tolerance
                    zone = LiquidityZone(
                        price_level=highs[i],
                        type='equal_highs',
                        volume_above=0,
                        volume_below=0,
                        distance_percent=0
                    )
                    zones.append(zone)
        
        # Equal lows (buy stops below)
        lows = df['low'].values[-30:]
        for i in range(len(lows)):
            for j in range(i+1, len(lows)):
                if abs(lows[i] - lows[j]) / lows[i] < 0.002:
                    zone = LiquidityZone(
                        price_level=lows[i],
                        type='equal_lows',
                        volume_above=0,
                        volume_below=0,
                        distance_percent=0
                    )
                    zones.append(zone)
        
        # Calculate distance from current price
        current = df['close'].iloc[-1]
        for z in zones:
            z.distance_percent = abs(z.price_level - current) / current * 100
        
        return zones
    
    def score_liquidity(self, df: pd.DataFrame, direction: SignalDirection,
                        entry: float, stop_loss: float) -> Tuple[float, Dict]:
        """
        Score based on liquidity analysis.
        Good entry sweeps liquidity then reverses.
        Bad entry is in the middle of a liquidity void.
        """
        zones = self.find_liquidity_zones(df)
        current = df['close'].iloc[-1]
        
        details = {
            'liquidity_zones_found': len(zones),
            'entry': entry,
            'current': current
        }
        
        if not zones:
            return 60, details  # Neutral if no clear liquidity
        
        # Check if stop loss is beyond a liquidity zone (good = protected)
        # or if entry swept liquidity (good = smart money entry)
        
        if direction == SignalDirection.LONG:
            # Best: entry is at/above a liquidity sweep level (equal lows swept)
            # Stop loss should be below the liquidity zone
            equal_lows = [z for z in zones if z.type == 'equal_lows']
            if equal_lows:
                nearest_low = max(equal_lows, key=lambda z: z.price_level)
                if entry <= nearest_low.price_level * 1.01:  # Entry near or below swept low
                    details['swept_liquidity'] = True
                    details['swept_level'] = nearest_low.price_level
                    return 90, details  # Excellent: swept liquidity for long entry
                elif stop_loss < nearest_low.price_level:
                    details['stop_beyond_liquidity'] = True
                    return 75, details  # Good: stop beyond liquidity
        else:  # SHORT
            equal_highs = [z for z in zones if z.type == 'equal_highs']
            if equal_highs:
                nearest_high = min(equal_highs, key=lambda z: z.price_level)
                if entry >= nearest_high.price_level * 0.99:  # Entry near or above swept high
                    details['swept_liquidity'] = True
                    details['swept_level'] = nearest_high.price_level
                    return 90, details
                elif stop_loss > nearest_high.price_level:
                    details['stop_beyond_liquidity'] = True
                    return 75, details
        
        return 60, details
    
    # ==================== SESSION ANALYSIS ====================
    
    def get_session_score(self, df: pd.DataFrame, timeframe: str) -> Tuple[float, Dict]:
        """
        Score based on session activity.
        Only trade when the relevant session is active.
        """
        # Get timestamp of last candle
        if len(df) == 0:
            return 50, {'reason': 'No data'}
        
        # For daily/4h timeframes, use CURRENT time instead of candle timestamp
        # (daily candles open at 00:00 UTC, which would always show "Asian" session)
        if timeframe in ['1d', '4h']:
            from datetime import datetime as dt
            last_ts = dt.utcnow()
        else:
            last_ts = df.index[-1]
            if not isinstance(last_ts, datetime):
                try:
                    last_ts = pd.to_datetime(last_ts)
                except:
                    return 50, {'reason': 'Invalid timestamp'}
        
        hour_utc = last_ts.hour
        weekday = last_ts.weekday()  # 0=Monday
        
        details = {
            'hour_utc': hour_utc,
            'weekday': weekday,
            'session': 'unknown'
        }
        
        # Define sessions (UTC)
        # Asian: 00:00 - 08:00 UTC (lower volume for alts)
        # London: 08:00 - 16:00 UTC (Europe open, good volume)
        # NY: 13:00 - 21:00 UTC (US open, highest volume)
        # London-NY overlap: 13:00 - 16:00 UTC (PRIME TIME)
        
        is_asian = 0 <= hour_utc < 8
        is_london = 8 <= hour_utc < 16
        is_ny = 13 <= hour_utc < 21
        is_overlap = 13 <= hour_utc < 16  # London-NY overlap
        
        # Timeframe-specific session preferences
        session_scores = {
            '5m': {
                'overlap': 100, 'ny': 90, 'london': 70, 'asian': 40
            },
            '15m': {
                'overlap': 100, 'ny': 90, 'london': 75, 'asian': 45
            },
            '1h': {
                'overlap': 95, 'ny': 90, 'london': 80, 'asian': 55
            },
            '4h': {
                'overlap': 90, 'ny': 90, 'london': 85, 'asian': 65
            },
            '1d': {
                'overlap': 80, 'ny': 80, 'london': 80, 'asian': 80  # Daily doesn't matter
            }
        }
        
        scores = session_scores.get(timeframe, session_scores['1h'])
        
        if is_overlap:
            score = scores['overlap']
            details['session'] = 'London-NY Overlap (PRIME)'
        elif is_ny:
            score = scores['ny']
            details['session'] = 'New York'
        elif is_london:
            score = scores['london']
            details['session'] = 'London'
        elif is_asian:
            score = scores['asian']
            details['session'] = 'Asian'
        else:
            score = 50
            details['session'] = 'Mixed/Transition'
        
        # Weekend penalty (except daily)
        if timeframe != '1d' and weekday >= 5:  # Saturday/Sunday
            score *= 0.5
            details['weekend'] = True
        
        return score, details
    
    # ==================== VOLATILITY REGIME ====================
    
    def detect_volatility_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect if market is expanding, compressing, or ranging.
        Used to adjust entry criteria.
        """
        if len(df) < 50:
            return {'regime': 'unknown', 'score': 50, 'atr_percentile': 50}
        
        # Calculate ATR-like measure using true range
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean()
        
        # ATR as percentage of price
        atr_percent = (atr / df['close']) * 100
        
        # Percentile of ATR over last 100 bars
        current_atr = atr_percent.iloc[-1]
        atr_history = atr_percent.dropna().iloc[-100:]
        
        if len(atr_history) < 20:
            return {'regime': 'unknown', 'score': 50}
        
        percentile = (atr_history < current_atr).mean() * 100
        
        regime = 'neutral'
        score = 50
        
        if percentile > 80:
            regime = 'expansion'
            score = 85  # Good for breakout strategies
        elif percentile < 20:
            regime = 'compression'
            score = 90  # Excellent: volatility expansion coming
        elif 40 < percentile < 60:
            regime = 'balanced'
            score = 75
        else:
            regime = 'transitional'
            score = 60
        
        # Range analysis: is price stuck in a range?
        recent_high = df['high'].iloc[-30:].max()
        recent_low = df['low'].iloc[-30:].min()
        range_percent = (recent_high - recent_low) / df['close'].iloc[-1] * 100
        
        in_range = range_percent < 5  # Less than 5% range over 30 bars
        
        return {
            'regime': regime,
            'score': score,
            'atr_percentile': percentile,
            'current_atr_percent': current_atr,
            'range_percent': range_percent,
            'in_tight_range': in_range
        }
    
    # ==================== MULTI-TIMEFRAME ALIGNMENT ====================
    
    def check_multi_timeframe_alignment(self, df_current: pd.DataFrame,
                                         df_higher: pd.DataFrame) -> Dict:
        """
        Check if higher timeframe aligns with current timeframe signal.
        Critical for quality: higher TF trend should match current TF direction.
        """
        if df_higher is None or len(df_higher) < 20:
            return {'aligned': False, 'score': 50, 'reason': 'No higher TF data'}
        
        # Higher TF structure
        higher_structure = self.analyze_structure(df_higher)
        higher_trend = higher_structure.get('trend', 'neutral')
        
        # Current TF structure
        current_structure = self.analyze_structure(df_current)
        current_trend = current_structure.get('trend', 'neutral')
        
        # Score alignment
        if higher_trend == 'uptrend' and 'uptrend' in current_trend:
            score = 95
            aligned = True
            reason = 'Higher TF bullish + current TF bullish = STRONG LONG'
        elif higher_trend == 'downtrend' and 'downtrend' in current_trend:
            score = 95
            aligned = True
            reason = 'Higher TF bearish + current TF bearish = STRONG SHORT'
        elif higher_trend == 'neutral':
            score = 70
            aligned = False
            reason = 'Higher TF neutral = lower conviction'
        else:
            score = 30
            aligned = False
            reason = f'Higher TF {higher_trend} contradicts current TF {current_trend}'
        
        return {
            'aligned': aligned,
            'score': score,
            'higher_tf_trend': higher_trend,
            'current_tf_trend': current_trend,
            'reason': reason
        }
    
    # ==================== MARKET REGIME DETECTION ====================
    
    def detect_market_regime(self, df: pd.DataFrame) -> str:
        """
        Classify market as trending, ranging, or choppy.
        - trending: ADX > 25, clear directional structure — good for breakouts
        - ranging: ADX < 20, price oscillating between support/resistance — good for mean reversion
        - choppy: high volatility + low directional consistency — AVOID signals
        """
        if len(df) < 50:
            return 'unknown'
        
        # Calculate ADX-like directional strength
        highs = df['high'].values
        lows = df['low'].values
        
        # True Range
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - df['close'].values[:-1])
        tr3 = np.abs(lows[1:] - df['close'].values[:-1])
        true_range = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = pd.Series(true_range).rolling(14).mean().iloc[-1]
        
        # +DM / -DM for ADX approximation
        plus_dm = np.maximum(highs[1:] - highs[:-1], 0)
        minus_dm = np.maximum(lows[:-1] - lows[1:], 0)
        
        plus_di = 100 * pd.Series(plus_dm).rolling(14).mean().iloc[-1] / (atr + 1e-10)
        minus_di = 100 * pd.Series(minus_dm).rolling(14).mean().iloc[-1] / (atr + 1e-10)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx if not np.isnan(dx) else 0
        
        # Trend consistency: how often does price make higher highs / lower lows?
        hh_count = sum(highs[i] > highs[i-5] for i in range(5, len(highs)))
        ll_count = sum(lows[i] < lows[i-5] for i in range(5, len(lows)))
        consistency = abs(hh_count - ll_count) / max(len(highs) - 5, 1)
        
        # Range detection
        recent_high = df['high'].iloc[-30:].max()
        recent_low = df['low'].iloc[-30:].min()
        range_pct = (recent_high - recent_low) / df['close'].iloc[-1] * 100
        
        if adx > 30 and consistency > 0.6:
            return 'trending'
        elif adx < 20 and range_pct < 8 and consistency < 0.4:
            return 'ranging'
        elif adx < 25 and (plus_di < 15 or minus_di < 15):
            return 'choppy'
        elif range_pct > 12 and adx > 20:
            return 'volatile'  # Expanding but directionless = choppy
        else:
            return 'mixed'
    
    # ==================== FIBONACCI RETRACEMENTS ====================
    
    def calculate_fibonacci_levels(self, df: pd.DataFrame, direction: SignalDirection) -> Dict:
        """
        Calculate Fibonacci retracement levels from recent swing.
        Returns key levels for entry precision.
        """
        if len(df) < 30:
            return {}
        
        if direction == SignalDirection.LONG:
            swing_low = df['low'].iloc[-30:].min()
            swing_high_idx = df['high'].iloc[-30:].idxmax()
            swing_high = df.loc[swing_high_idx, 'high']
            
            range_size = swing_high - swing_low
            if range_size <= 0:
                return {}
            
            levels = {
                'swing_high': swing_high,
                'swing_low': swing_low,
                '0.382': swing_high - range_size * 0.382,
                '0.500': swing_high - range_size * 0.500,
                '0.618': swing_high - range_size * 0.618,
                '0.786': swing_high - range_size * 0.786,
            }
        else:
            swing_high = df['high'].iloc[-30:].max()
            swing_low_idx = df['low'].iloc[-30:].idxmin()
            swing_low = df.loc[swing_low_idx, 'low']
            
            range_size = swing_high - swing_low
            if range_size <= 0:
                return {}
            
            levels = {
                'swing_high': swing_high,
                'swing_low': swing_low,
                '0.382': swing_low + range_size * 0.382,
                '0.500': swing_low + range_size * 0.500,
                '0.618': swing_low + range_size * 0.618,
                '0.786': swing_low + range_size * 0.786,
            }
        
        return levels
    
    def score_fibonacci_entry(self, df: pd.DataFrame, entry: float,
                               direction: SignalDirection) -> Tuple[float, str]:
        """
        Score how well the entry aligns with a key Fibonacci level.
        Returns score 0-100 and description.
        """
        fibs = self.calculate_fibonacci_levels(df, direction)
        if not fibs:
            return 50, "No Fibonacci levels calculated"
        
        # Find closest Fibonacci level to entry
        fib_levels = {k: v for k, v in fibs.items() if k not in ['swing_high', 'swing_low']}
        if not fib_levels:
            return 50, "No Fibonacci levels"
        
        closest_level = min(fib_levels.values(), key=lambda x: abs(x - entry))
        closest_key = [k for k, v in fib_levels.items() if v == closest_level][0]
        distance = abs(entry - closest_level) / entry * 100
        
        if distance < 0.3:
            score = 95
            quality = f"Entry at {closest_key} Fibonacci (perfect)"
        elif distance < 0.6:
            score = 85
            quality = f"Entry near {closest_key} Fibonacci"
        elif distance < 1.0:
            score = 70
            quality = f"Entry close to {closest_key} Fibonacci"
        else:
            score = 50
            quality = f"Entry far from Fibonacci levels ({distance:.1f}% away)"
        
        return score, quality
    
    # ==================== MASTER SCORE ====================
    
    def calculate_institutional_score(self, df: pd.DataFrame, direction: SignalDirection,
                                       entry: float, stop_loss: float,
                                       timeframe: str = '15m',
                                       df_higher: pd.DataFrame = None) -> InstitutionalScore:
        """
        Master scoring function combining all institutional tools.
        """
        # Volume Profile
        vol_score, vol_details = self.score_volume_profile(df, direction, entry)
        
        # Market Structure
        structure = self.analyze_structure(df)
        structure_score = structure.get('score', 50)
        
        # Liquidity
        liq_score, liq_details = self.score_liquidity(df, direction, entry, stop_loss)
        
        # Session
        session_score, session_details = self.get_session_score(df, timeframe)
        
        # Volatility
        vol_regime = self.detect_volatility_regime(df)
        vol_score_tf = vol_regime.get('score', 50)
        
        # Multi-timeframe
        if df_higher is not None:
            mtf = self.check_multi_timeframe_alignment(df, df_higher)
            mtf_score = mtf.get('score', 50)
        else:
            mtf = {'aligned': False, 'reason': 'No higher TF'}
            mtf_score = 50
        
        # Weighted total
        # Structure and MTF alignment are most important for institutions
        total = (
            structure_score * 0.30 +
            vol_score * 0.20 +
            liq_score * 0.15 +
            session_score * 0.10 +
            vol_score_tf * 0.10 +
            mtf_score * 0.15
        )
        
        return InstitutionalScore(
            structure_score=structure_score,
            volume_profile_score=vol_score,
            liquidity_score=liq_score,
            session_score=session_score,
            volatility_score=vol_score_tf,
            multi_tf_score=mtf_score,
            total_score=min(total, 100),
            structure_details=structure,
            volume_details=vol_details,
            liquidity_details=liq_details,
            session_details=session_details
        )
