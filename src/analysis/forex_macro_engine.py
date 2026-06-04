"""
Forex Macro Engine - Institutional-grade macro analysis for Forex markets
Replaces crypto-specific Fear & Greed with DXY, risk appetite, and session analysis
"""

from datetime import datetime, time
from typing import Dict, Optional, Tuple
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

# High-impact Forex events that trigger blackouts
FOREX_HIGH_IMPACT_EVENTS = {
    # NFP (Non-Farm Payrolls) - first Friday of each month at 13:30 UTC
    # FOMC - 8 meetings per year (known schedule)
    # CPI - monthly inflation data
    # ECB/BOE/BoJ decisions
}

class ForexMacroEngine:
    """
    Forex-specific macro analysis engine
    - DXY (US Dollar Index) for USD-pair directional bias
    - Risk appetite index (derived from AUD/JPY proxy or existing pairs)
    - Session analysis (London, NY, Tokyo overlap)
    - Economic calendar awareness
    """
    
    def __init__(self):
        self._dxy_cache = None
        self._dxy_cache_time = None
        self._dxy_cache_ttl = 300  # 5 minutes
    
    async def analyze_macro(self, forex_client, symbol: str, direction: str) -> Dict:
        """
        Analyze macro conditions for a Forex pair
        
        Returns dict with:
        - macro_score: 0-100 (high = favorable for trade)
        - sentiment_score: 0-100
        - dxy_reading: current DXY value
        - risk_appetite: 'risk_on', 'risk_off', or 'neutral'
        - session: current active session
        - warnings: list of strings
        """
        warnings = []
        
        # 1. DXY Analysis (most important for USD-based pairs)
        dxy_data = await self._get_dxy(forex_client)
        dxy_reading = dxy_data.get('value', 100.0)
        dxy_trend = dxy_data.get('trend', 'neutral')
        
        # 2. Risk Appetite (using existing pair data)
        risk_appetite = await self._calculate_risk_appetite(forex_client)
        
        # 3. Session Analysis
        session_info = self._get_session_info()
        
        # ===== SCORING LOGIC =====
        
        # DXY impact on USD pairs
        macro_score = 50  # Neutral baseline
        
        if 'USD' in symbol:
            # USD is quote currency (e.g., EUR/USD, GBP/USD, XAU/USD, AUD/USD, NZD/USD)
            if symbol.split('/')[1] == 'USD':
                if direction == 'SHORT':
                    # SHORT EUR/USD = LONG USD = needs strong DXY
                    if dxy_trend == 'bullish':
                        macro_score += 20
                        warnings.append("DXY bullish — supports USD strength for SHORT")
                    elif dxy_trend == 'bearish':
                        macro_score -= 15
                        warnings.append("DXY bearish — contradicts USD SHORT")
                else:  # LONG EUR/USD = SHORT USD = needs weak DXY
                    if dxy_trend == 'bearish':
                        macro_score += 20
                        warnings.append("DXY bearish — supports USD weakness for LONG")
                    elif dxy_trend == 'bullish':
                        macro_score -= 15
                        warnings.append("DXY bullish — contradicts USD LONG")
            
            # USD is base currency (e.g., USD/JPY, USD/CAD)
            elif symbol.split('/')[0] == 'USD':
                if direction == 'LONG':
                    # LONG USD/JPY = LONG USD = needs strong DXY
                    if dxy_trend == 'bullish':
                        macro_score += 20
                        warnings.append("DXY bullish — supports USD LONG")
                    elif dxy_trend == 'bearish':
                        macro_score -= 15
                        warnings.append("DXY bearish — contradicts USD LONG")
                else:  # SHORT USD/JPY = SHORT USD = needs weak DXY
                    if dxy_trend == 'bearish':
                        macro_score += 20
                        warnings.append("DXY bearish — supports USD SHORT")
                    elif dxy_trend == 'bullish':
                        macro_score -= 15
                        warnings.append("DXY bullish — contradicts USD SHORT")
        
        # Risk appetite impact
        sentiment_score = 50
        
        if risk_appetite == 'risk_on':
            if symbol in ['AUD/USD', 'NZD/USD']:
                if direction == 'LONG':
                    sentiment_score += 15
                    warnings.append("Risk-on environment supports commodity LONG")
                else:
                    sentiment_score -= 10
            elif symbol == 'USD/JPY':
                # Risk-on = JPY weakness (flows out of safe haven)
                if direction == 'LONG':  # LONG USD/JPY
                    sentiment_score += 15
                    warnings.append("Risk-on supports JPY weakness = USD/JPY LONG")
                else:
                    sentiment_score -= 10
            elif symbol == 'XAU/USD':
                # Risk-on = gold under pressure (safe haven outflow)
                if direction == 'LONG':
                    sentiment_score -= 10
                    warnings.append("Risk-on typically pressures gold LONGs")
                else:
                    sentiment_score += 15
                    warnings.append("Risk-on supports gold SHORT")
        
        elif risk_appetite == 'risk_off':
            if symbol in ['AUD/USD', 'NZD/USD']:
                if direction == 'SHORT':
                    sentiment_score += 15
                    warnings.append("Risk-off environment supports commodity SHORT")
                else:
                    sentiment_score -= 10
            elif symbol == 'USD/JPY':
                # Risk-off = JPY strength (safe haven inflow)
                if direction == 'SHORT':  # SHORT USD/JPY
                    sentiment_score += 15
                    warnings.append("Risk-off supports JPY strength = USD/JPY SHORT")
                else:
                    sentiment_score -= 10
            elif symbol == 'XAU/USD':
                # Risk-off = gold bid (safe haven demand)
                if direction == 'LONG':
                    sentiment_score += 20
                    warnings.append("Risk-off supports gold LONG (safe haven bid)")
                else:
                    sentiment_score -= 10
        
        # Session impact (overlap = more liquidity = better fills)
        session_boost = 0
        if session_info.get('is_london_ny_overlap', False):
            session_boost = 5
            warnings.append("London/NY overlap — peak liquidity")
        elif session_info.get('is_major_session', False):
            session_boost = 0
        else:
            session_boost = -5
            warnings.append("Low liquidity session — wider spreads possible")
        
        macro_score += session_boost
        
        # Clamp scores
        macro_score = max(0, min(100, macro_score))
        sentiment_score = max(0, min(100, sentiment_score))
        
        # Weighted total: Macro 40%, Sentiment 35%, Session 25%
        total_score = macro_score * 0.40 + sentiment_score * 0.35 + 50 * 0.25
        total_score = max(0, min(100, total_score))
        
        return {
            'macro_score': macro_score,
            'sentiment_score': sentiment_score,
            'total_score': total_score,
            'dxy_reading': dxy_reading,
            'dxy_trend': dxy_trend,
            'risk_appetite': risk_appetite,
            'session': session_info.get('current_session', 'unknown'),
            'warnings': warnings
        }
    
    async def _get_dxy(self, forex_client) -> Dict:
        """Fetch DXY (US Dollar Index) from Twelve Data
        
        Tries multiple symbols: DX-Y.NYB, DXY, DX
        Falls back to neutral if API doesn't support indices (free tier limitation)
        """
        if self._dxy_cache and self._dxy_cache_time:
            elapsed = (datetime.utcnow() - self._dxy_cache_time).total_seconds()
            if elapsed < self._dxy_cache_ttl:
                return self._dxy_cache
        
        # Track if we've already warned about DXY unavailability (suppress spam)
        if getattr(self, '_dxy_unavailable_warned', False):
            # Return cached neutral with extended TTL to avoid API spam
            result = {'value': 100.0, 'trend': 'neutral'}
            self._dxy_cache = result
            self._dxy_cache_time = datetime.utcnow()
            return result
        
        dxy_symbols = ['DX-Y.NYB', 'DXY', 'DX']
        
        for sym in dxy_symbols:
            try:
                klines = await forex_client.get_historical_klines(sym, '1h', limit=20)
                if len(klines) >= 5:
                    df = pd.DataFrame(klines)
                    if 'close' in df.columns and len(df) >= 2:
                        current = float(df['close'].iloc[-1])
                        prev = float(df['close'].iloc[-5])
                        
                        if current > prev * 1.002:
                            trend = 'bullish'
                        elif current < prev * 0.998:
                            trend = 'bearish'
                        else:
                            trend = 'neutral'
                        
                        result = {'value': current, 'trend': trend}
                        self._dxy_cache = result
                        self._dxy_cache_time = datetime.utcnow()
                        logger.info(f"DXY ({sym}): {current:.2f} ({trend})")
                        return result
            except Exception as e:
                err_str = str(e)
                if '404' in err_str or 'Not Found' in err_str:
                    continue  # Try next symbol
                if '429' in err_str:
                    break  # Rate limited, don't keep trying
                # Other errors, log once and continue
                logger.debug(f"DXY ({sym}) fetch failed: {e}")
                continue
        
        # All symbols failed — DXY not available on this API tier
        self._dxy_unavailable_warned = True
        result = {'value': 100.0, 'trend': 'neutral'}
        self._dxy_cache = result
        self._dxy_cache_time = datetime.utcnow()
        logger.warning("DXY not available on Twelve Data free tier — using neutral baseline for macro analysis")
        return result
    
    async def _calculate_risk_appetite(self, forex_client) -> str:
        """
        Calculate risk appetite using AUD/USD and USD/JPY as proxies
        Risk-On: AUD/USD strong + USD/JPY strong
        Risk-Off: AUD/USD weak + USD/JPY weak
        """
        try:
            # Fetch recent data for both pairs
            aud_klines = await forex_client.get_historical_klines('AUD/USD', '1h', limit=10)
            jpy_klines = await forex_client.get_historical_klines('USD/JPY', '1h', limit=10)
            
            if len(aud_klines) >= 3 and len(jpy_klines) >= 3:
                aud_df = pd.DataFrame(aud_klines)
                jpy_df = pd.DataFrame(jpy_klines)
                
                if 'close' in aud_df.columns and 'close' in jpy_df.columns:
                    aud_current = float(aud_df['close'].iloc[-1])
                    aud_prev = float(aud_df['close'].iloc[-3])
                    jpy_current = float(jpy_df['close'].iloc[-1])
                    jpy_prev = float(jpy_df['close'].iloc[-3])
                    
                    aud_strong = aud_current > aud_prev
                    jpy_strong = jpy_current > jpy_prev  # USD/JPY up = JPY weak
                    
                    if aud_strong and jpy_strong:
                        logger.info("Risk Appetite: RISK-ON (AUD strong, JPY weak)")
                        return 'risk_on'
                    elif not aud_strong and not jpy_strong:
                        logger.info("Risk Appetite: RISK-OFF (AUD weak, JPY strong)")
                        return 'risk_off'
        except Exception as e:
            logger.warning(f"Risk appetite calculation failed: {e}")
        
        return 'neutral'
    
    def _get_session_info(self) -> Dict:
        """Get current Forex session info"""
        now = datetime.utcnow()
        hour = now.hour
        
        # Forex session hours (UTC)
        # Tokyo: 00:00 - 09:00
        # London: 08:00 - 17:00
        # New York: 13:00 - 22:00
        
        is_tokyo = 0 <= hour < 9
        is_london = 8 <= hour < 17
        is_ny = 13 <= hour < 22
        
        # Overlaps (highest liquidity)
        is_london_ny_overlap = 13 <= hour < 17  # London + NY overlap
        is_tokyo_london_overlap = 8 <= hour < 9  # Tokyo + London overlap (brief)
        
        is_major_session = is_london or is_ny
        
        if is_london_ny_overlap:
            session = "London/NY Overlap (Peak)"
        elif is_london:
            session = "London"
        elif is_ny:
            session = "New York"
        elif is_tokyo:
            session = "Tokyo"
        else:
            session = "Sydney/Low Liquidity"
        
        return {
            'current_session': session,
            'is_london_ny_overlap': is_london_ny_overlap,
            'is_major_session': is_major_session,
            'hour': hour
        }
    
    def check_news_blackout(self, symbol: str) -> Dict:
        """
        Check if we're in a high-impact news blackout period
        Returns: {'is_blackout': bool, 'reason': str}
        """
        now = datetime.utcnow()
        
        # NFP: First Friday of month at ~13:30 UTC
        # Check if today is Friday and it's around 13:00-14:30 UTC
        if now.weekday() == 4:  # Friday
            if 12 <= now.hour <= 14:
                return {'is_blackout': True, 'reason': 'NFP Friday — high volatility expected'}
        
        # FOMC: Typically 2nd or 3rd Wednesday of month at 18:00 UTC
        # (Hard to predict without calendar, so we check broadly)
        if now.weekday() == 2:  # Wednesday
            if 17 <= now.hour <= 20:
                return {'is_blackout': False, 'reason': 'FOMC week — elevated caution'}
        
        # CPI: Monthly, typically mid-month
        # (General caution for mid-month)
        if 10 <= now.day <= 20:
            if now.hour in [12, 13]:
                return {'is_blackout': False, 'reason': 'Economic data period — moderate caution'}
        
        return {'is_blackout': False, 'reason': ''}
