import ccxt
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MarketScanner:
    def __init__(self):
        # Initialize Binance exchange without API keys (public data only)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        # Only set API keys if they're actually provided (not needed for public data)
        if settings.BINANCE_API_KEY and settings.BINANCE_API_SECRET and \
           settings.BINANCE_API_KEY != "optional_not_needed":
            self.exchange.apiKey = settings.BINANCE_API_KEY
            self.exchange.secret = settings.BINANCE_API_SECRET
            logger.info("Binance API keys configured")
        else:
            logger.info("Using Binance public API (no authentication)")
        
        self.liquid_pairs: List[str] = []
        self.last_refresh: Optional[datetime] = None
        self.min_volume_usd = settings.MIN_DAILY_VOLUME_USD
        
    async def initialize(self):
        logger.info("Initializing market scanner...")
        await self.refresh_liquid_pairs()
        logger.info(f"Market scanner initialized with {len(self.liquid_pairs)} liquid pairs")
        
    async def refresh_liquid_pairs(self):
        try:
            logger.info("Refreshing liquid pairs list...")
            await asyncio.to_thread(self.exchange.load_markets)
            
            markets = self.exchange.markets
            usdt_pairs = [
                symbol for symbol in markets.keys()
                if symbol.endswith('/USDT') and markets[symbol].get('spot', False)
            ]
            
            leveraged_tokens = ['UP', 'DOWN', 'BULL', 'BEAR']
            filtered_pairs = [
                pair for pair in usdt_pairs
                if not any(token in pair for token in leveraged_tokens)
            ]
            
            liquid_pairs = []
            for symbol in filtered_pairs:
                try:
                    ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
                    volume_usd = ticker.get('quoteVolume', 0)
                    
                    if volume_usd >= self.min_volume_usd:
                        liquid_pairs.append(symbol)
                        
                except Exception as e:
                    logger.debug(f"Error fetching ticker for {symbol}: {e}")
                    continue
                    
                await asyncio.sleep(0.1)
            
            self.liquid_pairs = sorted(liquid_pairs)
            self.last_refresh = datetime.utcnow()
            
            logger.info(f"Found {len(self.liquid_pairs)} liquid pairs with volume > ${self.min_volume_usd:,.0f}")
            
        except Exception as e:
            logger.error(f"Error refreshing liquid pairs: {e}")
            raise
    
    async def should_refresh_pairs(self) -> bool:
        if not self.last_refresh:
            return True
        return datetime.utcnow() - self.last_refresh > timedelta(hours=24)
    
    async def get_liquid_pairs(self) -> List[str]:
        if await self.should_refresh_pairs():
            await self.refresh_liquid_pairs()
        return self.liquid_pairs
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        try:
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                symbol,
                timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        try:
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise
    
    async def get_market_info(self, symbol: str) -> Dict:
        try:
            ticker = await self.fetch_ticker(symbol)
            
            return {
                'symbol': symbol,
                'last_price': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'volume_24h': ticker.get('quoteVolume', 0),
                'price_change_24h': ticker.get('percentage', 0),
                'high_24h': ticker.get('high'),
                'low_24h': ticker.get('low'),
            }
        except Exception as e:
            logger.error(f"Error getting market info for {symbol}: {e}")
            return {}
    
    async def scan_all_pairs(self, timeframe: str) -> List[Dict]:
        pairs = await self.get_liquid_pairs()
        results = []
        
        for symbol in pairs:
            try:
                df = await self.fetch_ohlcv(symbol, timeframe)
                market_info = await self.get_market_info(symbol)
                
                results.append({
                    'symbol': symbol,
                    'data': df,
                    'market_info': market_info
                })
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue
        
        return results
    
    async def close(self):
        await asyncio.to_thread(self.exchange.close)
        logger.info("Market scanner closed")
