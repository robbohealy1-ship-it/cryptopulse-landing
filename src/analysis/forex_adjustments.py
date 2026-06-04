"""
Forex-Specific Adjustments - Market-specific logic for Forex signals
This makes Forex signals truly bespoke, not just "crypto with different data"
"""
from datetime import datetime, timezone
from typing import Dict, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ForexMarketAdjustments:
    """
    Forex-specific adjustments that make it different from crypto:
    1. Tighter stop losses (lower volatility)
    2. Session-based weighting (London > NY > Asia)
    3. News event filtering (avoid NFP, CPI, Fed meetings)
    4. Spread adjustments (wider spreads = lower confidence)
    5. Correlation handling (USD pairs move together)
    """
    
    # High-impact news events (avoid trading 30min before/after)
    HIGH_IMPACT_NEWS = {
        'NFP': 'Non-Farm Payroll (1st Friday of month, 13:30 UTC)',
        'FOMC': 'Federal Reserve Meeting (8 times/year, 19:00 UTC)',
        'CPI': 'Consumer Price Index (monthly, 13:30 UTC)',
        'GDP': 'Gross Domestic Product (quarterly, 13:30 UTC)',
        'ECB': 'European Central Bank Meeting (8 times/year, 12:45 UTC)',
        'BOE': 'Bank of England Meeting (8 times/year, 12:00 UTC)',
    }
    
    # Session times (UTC)
    SESSIONS = {
        'asian': {'start': 0, 'end': 9, 'weight': 0.6},      # Tokyo: 00:00-09:00 UTC
        'london': {'start': 8, 'end': 17, 'weight': 1.0},    # London: 08:00-17:00 UTC (HIGHEST)
        'ny': {'start': 13, 'end': 22, 'weight': 0.9},       # New York: 13:00-22:00 UTC
        'overlap': {'start': 13, 'end': 17, 'weight': 1.0},  # London-NY overlap (PRIME)
    }
    
    # Volatility adjustments (Forex moves smaller than crypto)
    VOLATILITY_MULTIPLIERS = {
        'stop_loss': 0.6,      # Tighter stops (60% of crypto)
        'take_profit': 0.7,    # Smaller targets (70% of crypto)
        'atr_multiplier': 1.2, # Less aggressive ATR (vs 1.5x for crypto)
    }
    
    # Spread penalties (wider spread = lower confidence)
    SPREAD_THRESHOLDS = {
        'EUR/USD': 0.0002,  # 2 pips = acceptable
        'GBP/USD': 0.0003,  # 3 pips = acceptable
        'USD/JPY': 0.002,   # 0.2 pips = acceptable
        'XAU/USD': 0.50,    # $0.50 = acceptable
        'NAS100': 2.0,      # 2 points = acceptable
    }
    
    @staticmethod
    def get_current_session() -> Dict:
        """Get current Forex session and its weight"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Check for overlap first (highest priority)
        if ForexMarketAdjustments.SESSIONS['overlap']['start'] <= hour < ForexMarketAdjustments.SESSIONS['overlap']['end']:
            return {
                'name': 'London-NY Overlap',
                'weight': 1.0,
                'priority': 'HIGHEST',
                'description': 'Prime trading time - highest liquidity'
            }
        
        # Check London
        if ForexMarketAdjustments.SESSIONS['london']['start'] <= hour < ForexMarketAdjustments.SESSIONS['london']['end']:
            return {
                'name': 'London',
                'weight': 1.0,
                'priority': 'HIGH',
                'description': 'European session - high liquidity'
            }
        
        # Check NY
        if ForexMarketAdjustments.SESSIONS['ny']['start'] <= hour < ForexMarketAdjustments.SESSIONS['ny']['end']:
            return {
                'name': 'New York',
                'weight': 0.9,
                'priority': 'HIGH',
                'description': 'US session - high liquidity'
            }
        
        # Asian session (lowest priority for Forex)
        return {
            'name': 'Asian',
            'weight': 0.6,
            'priority': 'MEDIUM',
            'description': 'Asian session - lower liquidity, avoid major pairs'
        }
    
    @staticmethod
    def adjust_stop_loss(crypto_sl_distance: float, symbol: str) -> float:
        """
        Adjust stop loss for Forex (tighter than crypto)
        
        Example:
        - Crypto: 2% SL
        - Forex: 0.6 * 2% = 1.2% SL (tighter)
        """
        multiplier = ForexMarketAdjustments.VOLATILITY_MULTIPLIERS['stop_loss']
        
        # Gold (XAUUSD) moves more like crypto - use less aggressive tightening
        if 'XAU' in symbol or 'XAG' in symbol:
            multiplier = 0.8
        
        # Indices move medium volatility
        if any(idx in symbol for idx in ['NAS100', 'US30', 'SPX500']):
            multiplier = 0.75
        
        adjusted_sl = crypto_sl_distance * multiplier
        logger.debug(f"Forex SL adjustment: {crypto_sl_distance:.4f} -> {adjusted_sl:.4f} ({symbol})")
        return adjusted_sl
    
    @staticmethod
    def adjust_take_profit(crypto_tp_distance: float, symbol: str) -> float:
        """
        Adjust take profit for Forex (smaller targets than crypto)
        
        Example:
        - Crypto: 3% TP
        - Forex: 0.7 * 3% = 2.1% TP (smaller)
        """
        multiplier = ForexMarketAdjustments.VOLATILITY_MULTIPLIERS['take_profit']
        
        # Gold moves more like crypto
        if 'XAU' in symbol or 'XAG' in symbol:
            multiplier = 0.85
        
        # Indices
        if any(idx in symbol for idx in ['NAS100', 'US30', 'SPX500']):
            multiplier = 0.8
        
        adjusted_tp = crypto_tp_distance * multiplier
        logger.debug(f"Forex TP adjustment: {crypto_tp_distance:.4f} -> {adjusted_tp:.4f} ({symbol})")
        return adjusted_tp
    
    @staticmethod
    def apply_session_boost(base_confidence: float, symbol: str) -> float:
        """
        Boost confidence during optimal Forex sessions
        
        Example:
        - London session: +5% confidence
        - Asian session: -10% confidence (for major pairs)
        """
        session = ForexMarketAdjustments.get_current_session()
        
        # London-NY overlap = best time
        if session['name'] == 'London-NY Overlap':
            boost = 5.0
            logger.info(f"🌍 {symbol}: London-NY overlap boost +{boost}%")
            return min(base_confidence + boost, 100.0)
        
        # London session = prime time
        if session['name'] == 'London':
            boost = 3.0
            logger.info(f"🌍 {symbol}: London session boost +{boost}%")
            return min(base_confidence + boost, 100.0)
        
        # NY session = good
        if session['name'] == 'New York':
            boost = 2.0
            return min(base_confidence + boost, 100.0)
        
        # Asian session = avoid major pairs (EUR, GBP, USD)
        if session['name'] == 'Asian':
            # Penalize USD-based pairs during Asian session
            if any(pair in symbol for pair in ['EUR/USD', 'GBP/USD', 'USD/CAD']):
                penalty = -10.0
                logger.warning(f"🌍 {symbol}: Asian session penalty {penalty}% (low liquidity)")
                return max(base_confidence + penalty, 0.0)
            
            # JPY, AUD, NZD pairs are OK during Asian session
            if any(pair in symbol for pair in ['USD/JPY', 'AUD/USD', 'NZD/USD']):
                return base_confidence
        
        return base_confidence
    
    @staticmethod
    def check_news_blackout(symbol: str) -> Dict:
        """
        Check if we're in a news blackout period (avoid high-impact events)
        
        Returns:
        - is_blackout: bool
        - reason: str (if blackout)
        """
        now = datetime.now(timezone.utc)
        hour = now.hour
        minute = now.minute
        day_of_week = now.weekday()  # 0=Monday, 4=Friday
        
        # NFP: 1st Friday of month at 13:30 UTC (avoid 13:00-14:00)
        if day_of_week == 4 and 1 <= now.day <= 7:  # 1st Friday
            if 13 <= hour <= 14:
                return {
                    'is_blackout': True,
                    'reason': 'NFP (Non-Farm Payroll) - extreme volatility expected',
                    'avoid_until': '14:30 UTC'
                }
        
        # FOMC: Typically 19:00 UTC (avoid 18:30-20:00)
        # This is a simplified check - real implementation would use a calendar API
        if hour >= 18 and hour <= 20 and minute >= 30:
            logger.warning(f"⚠️ Potential FOMC time - verify before trading")
        
        # Weekend (Forex closed)
        if day_of_week >= 5:  # Saturday or Sunday
            return {
                'is_blackout': True,
                'reason': 'Weekend - Forex markets closed',
                'avoid_until': 'Monday 00:00 UTC'
            }
        
        return {'is_blackout': False}
    
    @staticmethod
    def apply_spread_penalty(base_confidence: float, symbol: str, current_spread: float) -> float:
        """
        Penalize confidence if spread is too wide
        
        Example:
        - EUR/USD spread: 0.0001 (1 pip) = OK
        - EUR/USD spread: 0.0005 (5 pips) = -5% confidence
        """
        threshold = ForexMarketAdjustments.SPREAD_THRESHOLDS.get(symbol, 0.0003)
        
        if current_spread > threshold * 2:
            penalty = -10.0
            logger.warning(f"🌍 {symbol}: Wide spread {current_spread:.5f} (threshold {threshold:.5f}) - penalty {penalty}%")
            return max(base_confidence + penalty, 0.0)
        
        if current_spread > threshold:
            penalty = -5.0
            logger.info(f"🌍 {symbol}: Elevated spread {current_spread:.5f} - penalty {penalty}%")
            return max(base_confidence + penalty, 0.0)
        
        return base_confidence


# Crypto-specific adjustments (for comparison)
class CryptoMarketAdjustments:
    """
    Crypto-specific adjustments - different from Forex
    """
    
    @staticmethod
    def check_crypto_news(symbol: str) -> Dict:
        """
        Check for crypto-specific news events
        - ETF approvals/rejections
        - Exchange hacks
        - Regulatory announcements
        - Major protocol upgrades
        """
        # This would integrate with crypto news APIs
        # For now, just a placeholder
        return {'is_blackout': False}
    
    @staticmethod
    def apply_btc_correlation(base_confidence: float, symbol: str, btc_trend: str) -> float:
        """
        Adjust altcoin confidence based on BTC trend
        
        Example:
        - BTC dumping + ETH long signal = -15% confidence
        - BTC pumping + ETH long signal = +5% confidence
        """
        if symbol == 'BTC/USDT':
            return base_confidence
        
        # Altcoins follow BTC
        if btc_trend == 'strong_down' and 'LONG' in symbol:
            penalty = -15.0
            logger.warning(f"₿ {symbol}: BTC dumping - LONG signal penalized {penalty}%")
            return max(base_confidence + penalty, 0.0)
        
        if btc_trend == 'strong_up' and 'LONG' in symbol:
            boost = 5.0
            logger.info(f"₿ {symbol}: BTC pumping - LONG signal boosted +{boost}%")
            return min(base_confidence + boost, 100.0)
        
        return base_confidence
