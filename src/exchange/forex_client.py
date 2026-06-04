"""
Forex market data client using free APIs (Alpha Vantage + Twelve Data)
Provides price data for major Forex pairs, commodities (XAUUSD), and indices (NAS100)
"""
import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ForexClient:
    """Free Forex data provider using Alpha Vantage and Twelve Data APIs"""
    
    # Major Forex pairs + commodities + indices
    FOREX_SYMBOLS = [
        # Major Forex pairs
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'NZD/USD',
        # Commodities
        'XAU/USD',  # Gold
        'XAG/USD',  # Silver
        # Indices (via Twelve Data)
        'NAS100',   # NASDAQ 100
        'US30',     # Dow Jones
        'SPX500',   # S&P 500
    ]
    
    def __init__(self):
        self.alpha_vantage_key = getattr(settings, 'ALPHA_VANTAGE_API_KEY', 'demo')
        self.twelve_data_key = getattr(settings, 'TWELVE_DATA_API_KEY', 'demo')
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache = {}  # Simple price cache
        self._cache_ttl = 60  # 60 seconds
        self._last_request_time = None  # For rate limiting
        self._min_request_interval = 1.0  # 1 second between requests (max 1 req/sec = 60 req/min, well under limit)
        
        # Log API key status (masked for security)
        av_status = "✅ SET" if self.alpha_vantage_key and self.alpha_vantage_key != 'demo' else "❌ DEMO/MISSING"
        td_status = "✅ SET" if self.twelve_data_key and self.twelve_data_key != 'demo' else "❌ DEMO/MISSING"
        logger.info(f"Forex API Keys - Alpha Vantage: {av_status}, Twelve Data: {td_status}")
        
    async def initialize(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # Validate API key by testing a simple request
        test_url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1h&outputsize=1&apikey={self.twelve_data_key}"
        try:
            async with self.session.get(test_url) as resp:
                response_text = await resp.text()
                if resp.status == 401:
                    logger.error(f"❌ Twelve Data API key is INVALID or UNAUTHORIZED")
                    logger.error(f"   Current key starts with: {self.twelve_data_key[:10]}...")
                    logger.error(f"   API Response: {response_text}")
                    logger.error(f"   Get a free key at: https://twelvedata.com/pricing")
                elif resp.status == 200:
                    try:
                        data = await resp.json()
                        if 'status' in data and data['status'] == 'error':
                            logger.error(f"❌ Twelve Data API error: {data.get('message', 'Unknown')}")
                            logger.error(f"   Full response: {data}")
                        else:
                            logger.info(f"✅ Twelve Data API key validated successfully")
                    except:
                        logger.error(f"❌ Twelve Data API returned invalid JSON: {response_text}")
                else:
                    logger.warning(f"⚠️ Twelve Data API returned status {resp.status}: {response_text}")
        except Exception as e:
            logger.error(f"❌ Failed to validate Twelve Data API key: {e}")
        
        logger.info(f"✅ Forex client initialized with {len(self.FOREX_SYMBOLS)} symbols")
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Convert symbol to Twelve Data API format
        EUR/USD -> EUR/USD (keep slash for Forex pairs)
        XAU/USD -> XAU/USD (keep slash for commodities)
        NAS100 -> NDX (Twelve Data uses NDX for NASDAQ 100)
        US30 -> DJI (Twelve Data uses DJI for Dow Jones)
        SPX500 -> SPX (Twelve Data uses SPX for S&P 500)
        """
        # Indices need special mapping
        index_map = {
            'NAS100': 'NDX',
            'US30': 'DJI',
            'SPX500': 'SPX'
        }
        
        if symbol in index_map:
            return index_map[symbol]
        
        # Forex pairs and commodities keep the slash
        return symbol
    
    async def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a Forex symbol"""
        cache_key = f"price_{symbol}"
        if cache_key in self._cache:
            cached_time, cached_price = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self._cache_ttl:
                return cached_price
        
        try:
            # Use Alpha Vantage for Forex pairs and commodities
            if symbol in ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'NZD/USD', 'XAU/USD', 'XAG/USD']:
                price = await self._get_price_alpha_vantage(symbol)
            # Use Twelve Data for indices
            elif symbol in ['NAS100', 'US30', 'SPX500']:
                price = await self._get_price_twelve_data(symbol)
            else:
                logger.warning(f"Unknown Forex symbol: {symbol}")
                return None
            
            if price:
                self._cache[cache_key] = (datetime.utcnow(), price)
            return price
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    async def _get_price_alpha_vantage(self, symbol: str) -> Optional[float]:
        """Fetch price from Alpha Vantage (Forex & commodities)"""
        if not self.session:
            await self.initialize()
        
        try:
            # For Forex pairs
            if '/' in symbol:
                from_currency, to_currency = symbol.split('/')
                url = f"https://www.alphavantage.co/query"
                params = {
                    'function': 'CURRENCY_EXCHANGE_RATE',
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'apikey': self.alpha_vantage_key
                }
                
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if 'Realtime Currency Exchange Rate' in data:
                            price_str = data['Realtime Currency Exchange Rate']['5. Exchange Rate']
                            return float(price_str)
            
            logger.warning(f"Could not fetch price for {symbol} from Alpha Vantage")
            return None
        except Exception as e:
            logger.error(f"Alpha Vantage API error for {symbol}: {e}")
            return None
    
    async def _get_price_twelve_data(self, symbol: str) -> Optional[float]:
        """Fetch price from Twelve Data (indices)"""
        if not self.session:
            await self.initialize()
        
        try:
            url = f"https://api.twelvedata.com/price"
            params = {
                'symbol': symbol,
                'apikey': self.twelve_data_key
            }
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'price' in data:
                        return float(data['price'])
            
            logger.warning(f"Could not fetch price for {symbol} from Twelve Data")
            return None
        except Exception as e:
            logger.error(f"Twelve Data API error for {symbol}: {e}")
            return None
    
    async def get_historical_klines(self, symbol: str, interval: str = '1h', limit: int = 100) -> List[Dict]:
        """
        Get historical candlestick data for Forex symbol
        Returns list of dicts with: timestamp, open, high, low, close, volume
        """
        try:
            if not self.session:
                await self.initialize()
            
            # Rate limiting: wait between requests to avoid 429 errors
            if self._last_request_time:
                elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
                if elapsed < self._min_request_interval:
                    await asyncio.sleep(self._min_request_interval - elapsed)
            self._last_request_time = datetime.utcnow()
            
            # Map interval to API format
            interval_map = {
                '1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min',
                '1h': '1h', '4h': '4h', '1d': '1day'
            }
            api_interval = interval_map.get(interval, '1h')
            
            # Use Twelve Data for historical data (better coverage)
            url = f"https://api.twelvedata.com/time_series"
            params = {
                'symbol': self._normalize_symbol(symbol),
                'interval': api_interval,
                'outputsize': limit,
                'apikey': self.twelve_data_key
            }
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Check for API errors
                    if 'status' in data and data['status'] == 'error':
                        logger.error(f"Forex API error for {symbol}: {data.get('message', 'Unknown error')}")
                        return []
                    
                    if 'values' in data:
                        klines = []
                        for candle in data['values']:
                            klines.append({
                                'timestamp': int(datetime.fromisoformat(candle['datetime'].replace('Z', '+00:00')).timestamp() * 1000),
                                'open': float(candle['open']),
                                'high': float(candle['high']),
                                'low': float(candle['low']),
                                'close': float(candle['close']),
                                'volume': float(candle.get('volume', 0))
                            })
                        return list(reversed(klines))  # Oldest first
                    else:
                        logger.error(f"Forex API response missing 'values' for {symbol}: {data}")
                        return []
                else:
                    logger.error(f"Forex API HTTP {resp.status} for {symbol}")
                    return []
            
            logger.warning(f"Could not fetch historical data for {symbol}")
            return []
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    async def get_24h_volume(self, symbol: str) -> float:
        """Get 24h volume (estimated for Forex, as true volume isn't available)"""
        # Forex doesn't have centralized volume like crypto
        # Return a placeholder or estimate based on pair liquidity
        liquidity_estimates = {
            'EUR/USD': 1000000000,  # Most liquid
            'GBP/USD': 500000000,
            'USD/JPY': 400000000,
            'XAU/USD': 200000000,
            'NAS100': 300000000,
        }
        return liquidity_estimates.get(symbol, 100000000)  # Default estimate
    
    async def get_all_symbols(self) -> List[str]:
        """Return list of supported Forex symbols"""
        return self.FOREX_SYMBOLS.copy()
