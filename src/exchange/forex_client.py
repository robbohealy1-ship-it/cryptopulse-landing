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
    """Free Forex data provider using Gold-API (free XAU/USD), Twelve Data (primary), Finnhub (backup), Alpha Vantage, and ExchangeRate-API (fallback)"""
    
    # Major Forex pairs + commodities + indices
    FOREX_SYMBOLS = [
        # Major Forex pairs
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'NZD/USD',
        # Commodities
        'XAU/USD',  # Gold
        # 'XAG/USD',  # Silver - Not supported by Twelve Data (404 error)
        # Indices - NOT supported by Twelve Data free tier (404 errors)
        # 'NAS100',   # NASDAQ 100
        # 'US30',     # Dow Jones
        # 'SPX500',   # S&P 500
    ]
    
    def __init__(self):
        self.alpha_vantage_key = getattr(settings, 'ALPHA_VANTAGE_API_KEY', 'demo')
        self.twelve_data_key = getattr(settings, 'TWELVE_DATA_API_KEY', 'demo')
        self.finnhub_key = getattr(settings, 'FINNHUB_API_KEY', None)
        self.gold_api_key = getattr(settings, 'GOLD_API_KEY', None)  # Free from gold-api.com
        self.exchange_rate_api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)  # Free from exchangerate-api.com
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache = {}  # Simple price cache
        self._cache_ttl = 300  # 5 MINUTES (was 60s) - major API call reduction
        self._klines_cache = {}  # Historical data cache
        self._klines_cache_ttl = 600  # 10 MINUTES for historical data
        self._last_request_time = None  # For rate limiting
        self._min_request_interval = 1.0  # 1 second between requests
        self._rate_limit_lock = asyncio.Lock()
        
        # Log API key status (masked for security)
        av_status = "✅ SET" if self.alpha_vantage_key and self.alpha_vantage_key != 'demo' else "❌ DEMO/MISSING"
        td_status = "✅ SET" if self.twelve_data_key and self.twelve_data_key != 'demo' else "❌ DEMO/MISSING"
        fh_status = "✅ SET" if self.finnhub_key else "❌ MISSING"
        ga_status = "✅ SET" if self.gold_api_key else "🆓 FREE (no key needed)"
        er_status = "✅ SET" if self.exchange_rate_api_key else "🆓 FREE (no key needed)"
        logger.info(f"Forex API Keys - Gold-API: {ga_status}, Twelve Data: {td_status}, Finnhub: {fh_status}, Alpha Vantage: {av_status}, ExchangeRate-API: {er_status}")
        
        # Track API usage for optimization
        self._api_call_count = 0
        self._api_call_reset_time = datetime.utcnow()
        
    async def _apply_rate_limit(self):
        """Wait between API requests to avoid rate limits"""
        async with self._rate_limit_lock:
            if self._last_request_time:
                elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
                if elapsed < self._min_request_interval:
                    wait_time = self._min_request_interval - elapsed
                    logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
            self._last_request_time = datetime.utcnow()
    
    async def initialize(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # OPTIMIZATION: Skip validation call to save 1 API credit on startup
        # Errors will be caught during live price fetching with proper logging
        logger.info(f"✅ Forex client initialized with {len(self.FOREX_SYMBOLS)} symbols")
        logger.info(f"   Price sources: Gold-API (XAU/USD), ExchangeRate-API (currencies), Twelve Data, Finnhub, Alpha Vantage")
    
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
        """
        Get current price for a Forex symbol
        Priority: Gold-API (XAU/USD free) > Twelve Data (800/day) > ExchangeRate-API (1500/mo free) > Finnhub > Alpha Vantage
        """
        cache_key = f"price_{symbol}"
        if cache_key in self._cache:
            cached_time, cached_price = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self._cache_ttl:
                logger.debug(f"📦 Cache hit for {symbol} (age: {(datetime.utcnow()-cached_time).total_seconds():.0f}s)")
                return cached_price
        
        # Apply rate limiting
        await self._apply_rate_limit()
        
        try:
            # OPTIMIZATION 1: Use Gold-API for XAU/USD (FREE, unlimited, no key needed for basic!)
            if symbol == 'XAU/USD':
                price = await self._get_price_gold_api(symbol)
                if price:
                    self._cache[cache_key] = (datetime.utcnow(), price)
                    return price
                # Fallback to Twelve Data for XAU/USD
                price = await self._get_price_twelve_data(symbol)
                if price:
                    self._cache[cache_key] = (datetime.utcnow(), price)
                    return price
            
            # OPTIMIZATION 2: Use ExchangeRate-API for currency pairs (FREE 1500/month)
            elif '/' in symbol and symbol != 'XAU/USD':
                if self.exchange_rate_api_key:
                    price = await self._get_price_exchange_rate_api(symbol)
                    if price:
                        self._cache[cache_key] = (datetime.utcnow(), price)
                        return price
                
                # Fallback to Twelve Data for currency pairs
                price = await self._get_price_twelve_data(symbol)
                if price:
                    self._cache[cache_key] = (datetime.utcnow(), price)
                    return price
            
            # FALLBACK 1: Try Finnhub (stocks only on free tier)
            if self.finnhub_key:
                price = await self._get_price_finnhub(symbol)
                if price:
                    self._cache[cache_key] = (datetime.utcnow(), price)
                    return price
            
            # FALLBACK 2: Use Alpha Vantage (25 calls/day limit)
            logger.warning(f"🔄 Primary APIs failed for {symbol}, trying Alpha Vantage...")
            price = await self._get_price_alpha_vantage(symbol)
            if price:
                self._cache[cache_key] = (datetime.utcnow(), price)
                return price
            
            logger.error(f"❌ All APIs failed to fetch price for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    async def get_prices(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """Batch fetch prices for multiple symbols (more efficient than individual calls)"""
        results = {}
        # Check cache first for all symbols
        uncached = []
        for symbol in symbols:
            cache_key = f"price_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_price = self._cache[cache_key]
                if (datetime.utcnow() - cached_time).total_seconds() < self._cache_ttl:
                    results[symbol] = cached_price
                    continue
            uncached.append(symbol)
        
        # Fetch uncached symbols individually
        for symbol in uncached:
            price = await self.get_price(symbol)
            results[symbol] = price
        
        return results
    
    async def _get_price_gold_api(self, symbol: str) -> Optional[float]:
        """Fetch gold price from Gold-API.com (FREE, no rate limit for real-time prices!)"""
        if not self.session:
            await self.initialize()
        
        # Circuit breaker: if Gold-API consistently fails, skip for 10 min to save API calls
        fail_cache_key = f"goldapi_fail_{symbol}"
        if fail_cache_key in self._cache:
            fail_time = self._cache[fail_cache_key][0]
            if (datetime.utcnow() - fail_time).total_seconds() < 600:  # 10 min cooldown
                logger.debug(f"🛡️ Gold-API circuit breaker active for {symbol}, skipping")
                return None
        
        # Try multiple free gold price endpoints
        endpoints = [
            # Primary: gold-api.com (free, no key)
            ("https://gold-api.com/price/XAU", None, None),
            # Alternative path
            ("https://api.gold-api.com/price/XAU", None, None),
            # Another free endpoint variation
            ("https://gold-api.com/api/v1/price/XAU", None, None),
            # Fallback: goldapi.io (needs any key, demo works for limited calls)
            ("https://www.goldapi.io/api/XAU/USD", {"x-access-token": self.gold_api_key or "goldapi-demo-key"}, None),
        ]
        
        for url, headers, _ in endpoints:
            try:
                async with self.session.get(url, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Various response formats
                        price = None
                        if 'price' in data and data['price']:
                            price = float(data['price'])
                        elif 'rate' in data and data['rate']:
                            price = float(data['rate'])
                        if price and price > 0:
                            logger.info(f"✅ Gold-API ({url.split('/')[2]}): {symbol} = ${price:.2f}")
                            return price
                    elif resp.status == 429:
                        logger.warning(f"⚠️ Gold-API rate limit at {url}")
                    else:
                        logger.debug(f"Gold-API {url} returned status {resp.status}")
            except asyncio.TimeoutError:
                logger.debug(f"Gold-API timeout for {url}")
            except Exception as e:
                logger.debug(f"Gold-API error for {url}: {e}")
        
        # All endpoints failed — set circuit breaker
        self._cache[fail_cache_key] = (datetime.utcnow(), None)
        logger.warning(f"🚫 All Gold-API endpoints failed for {symbol}, cooling down for 10 min")
        return None
    
    async def _get_price_exchange_rate_api(self, symbol: str) -> Optional[float]:
        """Fetch from ExchangeRate-API.com (FREE 1500 requests/month, no key needed for free tier!)"""
        if not self.session:
            await self.initialize()
        
        try:
            # ExchangeRate-API free tier: 1500 requests/month, no API key needed!
            # Just use: https://api.exchangerate-api.com/v4/latest/USD
            from_currency, to_currency = symbol.split('/')
            
            # Use latest endpoint (no key needed for basic usage)
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            async with self.session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'rates' in data and to_currency in data['rates']:
                        rate = float(data['rates'][to_currency])
                        logger.debug(f"✅ ExchangeRate-API: {symbol} = {rate}")
                        return rate
                else:
                    logger.debug(f"ExchangeRate-API returned status {resp.status}")
        except asyncio.TimeoutError:
            logger.debug(f"ExchangeRate-API timeout for {symbol}")
        except Exception as e:
            logger.debug(f"ExchangeRate-API error for {symbol}: {e}")
        
        return None
    
    async def _get_price_alpha_vantage(self, symbol: str, max_retries: int = 2) -> Optional[float]:
        """Fetch price from Alpha Vantage (Forex & commodities) with retry on rate limit"""
        if not self.session:
            await self.initialize()

        for attempt in range(max_retries + 1):
            try:
                await self._apply_rate_limit()

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
                        if resp.status == 429:
                            if attempt < max_retries:
                                wait = 2 ** attempt
                                logger.warning(f"Alpha Vantage 429 for {symbol}, retrying in {wait}s...")
                                await asyncio.sleep(wait)
                                continue
                        if resp.status == 200:
                            data = await resp.json()
                            if 'Realtime Currency Exchange Rate' in data:
                                price_str = data['Realtime Currency Exchange Rate']['5. Exchange Rate']
                                return float(price_str)
                            # API error message in response body
                            if 'Information' in data or 'Note' in data:
                                msg = data.get('Information') or data.get('Note', '')
                                logger.warning(f"Alpha Vantage info for {symbol}: {msg}")
                                if attempt < max_retries:
                                    await asyncio.sleep(2 ** attempt)
                                    continue

                logger.warning(f"Could not fetch price for {symbol} from Alpha Vantage")
                return None
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(f"Alpha Vantage API error for {symbol}: {e}")
                return None
        return None
    
    async def _get_price_finnhub(self, symbol: str) -> Optional[float]:
        """Get price from Finnhub API (60 calls/min free tier)"""
        if not self.session:
            await self.initialize()
        
        await self._apply_rate_limit()
        
        try:
            # Convert symbol format: EUR/USD -> OANDA:EUR_USD
            # Finnhub uses different format for Forex
            fh_symbol = symbol.replace('/', '_')
            if symbol == 'XAU/USD':
                fh_symbol = 'OANDA:XAU_USD'
            else:
                fh_symbol = f'OANDA:{fh_symbol}'
            
            url = f"https://finnhub.io/api/v1/quote"
            params = {
                'symbol': fh_symbol,
                'token': self.finnhub_key
            }
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Finnhub returns: {"c": current_price, "h": high, "l": low, "o": open, "pc": prev_close}
                    if 'c' in data and data['c'] > 0:
                        logger.debug(f"✅ Finnhub: {symbol} = ${data['c']}")
                        return float(data['c'])
                    else:
                        logger.warning(f"⚠️ Finnhub returned invalid data for {symbol}: {data}")
                elif resp.status == 429:
                    logger.warning(f"⚠️ Finnhub rate limit hit for {symbol} (should not happen with 60/min)")
                else:
                    logger.warning(f"⚠️ Finnhub returned status {resp.status} for {symbol}")
            
            return None
        except Exception as e:
            logger.error(f"❌ Finnhub API error for {symbol}: {e}")
            return None
    
    async def _get_price_twelve_data(self, symbol: str, _retry_count: int = 0) -> Optional[float]:
        """Fetch price from Twelve Data (all symbols)"""
        if not self.session:
            await self.initialize()
        
        # Circuit breaker: if Twelve Data is rate limiting us, back off for 15 min
        fail_key = f"twelve_data_429"
        if fail_key in self._cache:
            fail_time = self._cache[fail_key][0]
            if (datetime.utcnow() - fail_time).total_seconds() < 900:  # 15 min
                logger.debug(f"🛡️ Twelve Data circuit breaker active, skipping {symbol}")
                return None
        
        # Apply rate limiting before request
        await self._apply_rate_limit()
        
        try:
            # Normalize symbol for Twelve Data API
            api_symbol = self._normalize_symbol(symbol)
            
            url = f"https://api.twelvedata.com/price"
            params = {
                'symbol': api_symbol,
                'apikey': self.twelve_data_key
            }
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'price' in data:
                        return float(data['price'])
                elif resp.status == 429:
                    if _retry_count < 2:  # Reduced from 3 to 2 retries
                        wait_time = 10 * (2 ** _retry_count)  # 10s, 20s
                        logger.warning(f"🌍 Rate limited (429) getting price for {symbol}, waiting {wait_time}s before retry {_retry_count+1}/2...")
                        await asyncio.sleep(wait_time)
                        return await self._get_price_twelve_data(symbol, _retry_count + 1)
                    else:
                        logger.error(f"🌍 Rate limited (429) getting price for {symbol}, max retries exceeded — circuit breaker activated (15 min cooldown)")
                        self._cache[fail_key] = (datetime.utcnow(), None)
                        return None
            
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
        # Check klines cache first (10 min TTL)
        klines_cache_key = f"klines_{symbol}_{interval}"
        if klines_cache_key in self._klines_cache:
            cached_time, cached_klines = self._klines_cache[klines_cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self._klines_cache_ttl:
                logger.debug(f"📦 Klines cache hit for {symbol} {interval}")
                # Return requested limit (may be subset of cached)
                return cached_klines[:limit] if len(cached_klines) > limit else cached_klines
        
        try:
            if not self.session:
                await self.initialize()
            
            # Apply rate limiting
            await self._apply_rate_limit()
            
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
                        result = list(reversed(klines))  # Oldest first
                        # Cache the result
                        self._klines_cache[klines_cache_key] = (datetime.utcnow(), result)
                        return result
                    else:
                        logger.error(f"Forex API response missing 'values' for {symbol}: {data}")
                        return []
                elif resp.status == 429:
                    # Rate limited - retry with exponential backoff (per-request counter)
                    retry_count = getattr(self, '_429_retry_count', 0)
                    if retry_count < 3:
                        wait_time = 10 * (2 ** retry_count)  # 10s, 20s, 40s
                        logger.warning(f"🌍 Rate limited (429) for {symbol}, waiting {wait_time}s before retry {retry_count+1}/3...")
                        self._429_retry_count = retry_count + 1
                        await asyncio.sleep(wait_time)
                        return await self.get_historical_klines(symbol, interval, limit)
                    else:
                        logger.error(f"🌍 Rate limited (429) for {symbol}, max retries exceeded")
                        self._429_retry_count = 0
                        return []
                else:
                    logger.error(f"Forex API HTTP {resp.status} for {symbol}")
                    self._429_retry_count = 0
                    return []
            
            # Reset retry counter on success
            self._429_retry_count = 0
            
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
