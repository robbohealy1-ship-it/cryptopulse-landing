"""
CRYPTO PULSE SIGNALS - Enhanced Context Engine
Comprehensive market context with multiple data sources
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from newsapi import NewsApiClient
from src.config import settings
from src.models.signal import ContextScore
from src.utils.logger import get_logger
from src.analysis.whale_monitor import WhaleMonitor
from src.analysis.forex_macro_engine import ForexMacroEngine

logger = get_logger(__name__)


class EnhancedContextEngine:
    """Multi-source context analysis for crypto trading signals"""
    
    def __init__(self):
        # NewsAPI is optional - will use CryptoCompare if not available
        self.news_api = None
        if settings.NEWS_API_KEY:
            try:
                self.news_api = NewsApiClient(api_key=settings.NEWS_API_KEY)
                logger.info("NewsAPI initialized")
            except Exception as e:
                logger.warning(f"NewsAPI initialization failed: {e}. Using CryptoCompare only.")
        else:
            logger.info("NewsAPI key not provided. Using CryptoCompare news only.")
        
        # Whale monitor (free tier via Binance public API)
        self.whale_monitor = WhaleMonitor()
        
        # Forex macro engine (DXY, risk appetite, session analysis)
        self.forex_macro = ForexMacroEngine()
        
        # Cache management
        self.cache_duration = timedelta(minutes=15)
        self.last_fetches = {}
        self.caches = {}
        
        # High-impact keywords for risk detection
        self.high_impact_keywords = [
            'fomc', 'federal reserve', 'interest rate', 'cpi', 'inflation',
            'employment', 'gdp', 'recession', 'crisis', 'crash', 'rally',
            'etf approval', 'sec', 'regulation', 'ban', 'hack', 'exploit',
            'bankruptcy', 'liquidation', 'delisting', 'intervention',
            'sanctions', 'war', 'conflict', 'default', 'collapse',
            'whale', 'massive selloff', 'flash crash', 'margin call'
        ]
        
        self.negative_keywords = [
            'crash', 'hack', 'exploit', 'scam', 'fraud', 'ban', 'regulation',
            'lawsuit', 'investigation', 'bankruptcy', 'liquidation', 'outage',
            'down', 'suspended', 'halted', 'dump', 'bearish', 'sell-off',
            'withdrawal halted', 'frozen', 'seized', 'rug pull'
        ]
        
        self.positive_keywords = [
            'approval', 'adoption', 'partnership', 'integration', 'upgrade',
            'launch', 'rally', 'surge', 'breakthrough', 'milestone',
            'etf approved', 'listing', 'bullish', 'institutional',
            'accumulation', ' ATH', 'all-time high'
        ]
        
        # Data source URLs
        self.fear_greed_url = 'https://api.alternative.me/fng/?limit=1'
        self.coingecko_global = 'https://api.coingecko.com/api/v3/global'
        self.coingecko_btc = 'https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7'
        self.cryptopanic_url = 'https://cryptopanic.com/api/v1/posts/'
    
    # ==================== NEWS SOURCES ====================
    
    async def fetch_newsapi_news(self) -> List[Dict]:
        """Fetch from NewsAPI (general crypto news)"""
        if not self.news_api:
            return []  # Skip if NewsAPI not configured
        
        cache_key = 'newsapi'
        # Use longer cache for NewsAPI to stay within free tier (100 req/24h)
        # Extended to 120 minutes (2 hours) to minimize rate limit hits
        if self._is_cache_valid(cache_key, duration_minutes=120):
            return self.caches[cache_key]
        
        try:
            news = await asyncio.to_thread(
                self.news_api.get_everything,
                q='(cryptocurrency OR bitcoin OR ethereum OR crypto OR blockchain) AND (trading OR market OR price)',
                language='en',
                sort_by='publishedAt',
                page_size=20,
                from_param=(datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%d')
            )
            
            articles = [
                {
                    'title': a.get('title', ''),
                    'description': a.get('description', ''),
                    'source': a.get('source', {}).get('name', 'Unknown'),
                    'published_at': a.get('publishedAt', ''),
                    'url': a.get('url', ''),
                    'sentiment': None
                }
                for a in news.get('articles', [])
            ]
            
            self._update_cache(cache_key, articles)
            logger.info(f"NewsAPI: Fetched {len(articles)} articles")
            return articles
            
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return self.caches.get(cache_key, [])
    
    async def fetch_cryptonews(self) -> List[Dict]:
        """Fetch from CryptoNews API (if available)"""
        cache_key = 'cryptonews'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try to fetch from a crypto news RSS or alternative source
                # Using a public crypto news aggregator endpoint
                url = 'https://min-api.cryptocompare.com/data/v2/news/?lang=EN&limit=20'
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = [
                            {
                                'title': item.get('title', ''),
                                'description': item.get('body', '')[:200],
                                'source': item.get('source', 'Unknown'),
                                'published_at': datetime.fromtimestamp(item.get('published_on', 0)).isoformat(),
                                'url': item.get('url', ''),
                                'sentiment': item.get('sentiment', 'neutral'),
                                'categories': item.get('categories', '')
                            }
                            for item in data.get('Data', [])
                        ]
                        self._update_cache(cache_key, articles)
                        logger.info(f"CryptoCompare News: Fetched {len(articles)} articles")
                        return articles
        except Exception as e:
            logger.warning(f"CryptoCompare news error: {e}")
        
        return []
    
    async def fetch_fear_greed_index(self) -> Dict:
        """Fetch Crypto Fear & Greed Index"""
        cache_key = 'fear_greed'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.fear_greed_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data'):
                            latest = data['data'][0]
                            result = {
                                'value': int(latest.get('value', 50)),
                                'classification': latest.get('value_classification', 'Neutral'),
                                'timestamp': latest.get('timestamp', '')
                            }
                            self._update_cache(cache_key, result)
                            logger.info(f"Fear & Greed: {result['value']} ({result['classification']})")
                            return result
        except Exception as e:
            logger.warning(f"Fear & Greed API error: {e}")
        
        return {'value': 50, 'classification': 'Neutral', 'timestamp': ''}
    
    # ==================== MARKET DATA ====================
    
    async def fetch_market_data(self) -> Dict:
        """Fetch comprehensive market data from CoinGecko"""
        cache_key = 'market_data'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                # Global market data
                async with session.get(self.coingecko_global, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        market_data = data.get('data', {})
                        
                        result = {
                            'btc_dominance': market_data.get('market_cap_percentage', {}).get('btc', 0),
                            'eth_dominance': market_data.get('market_cap_percentage', {}).get('eth', 0),
                            'total_market_cap': market_data.get('total_market_cap', {}).get('usd', 0),
                            'total_volume_24h': market_data.get('total_volume', {}).get('usd', 0),
                            'market_cap_change_24h': market_data.get('market_cap_change_percentage_24h_usd', 0),
                            'active_cryptocurrencies': market_data.get('active_cryptocurrencies', 0),
                            'markets': market_data.get('markets', 0)
                        }
                        
                        self._update_cache(cache_key, result)
                        return result
        except Exception as e:
            logger.error(f"Market data fetch error: {e}")
        
        return {
            'btc_dominance': 0, 'eth_dominance': 0, 'total_market_cap': 0,
            'total_volume_24h': 0, 'market_cap_change_24h': 0
        }
    
    async def fetch_global_market_data(self) -> Dict:
        """Alias for fetch_market_data for backward compatibility"""
        return await self.fetch_market_data()
    
    # ==================== MARKET BIAS DATA (Binance Public API) ====================
    
    async def fetch_funding_rates(self, symbol: str = 'BTCUSDT') -> Dict:
        """
        Fetch perpetual futures funding rate.
        Positive = longs pay shorts (crowded longs, potential bearish)
        Negative = shorts pay longs (crowded shorts, potential bullish)
        """
        cache_key = f'funding_{symbol}'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f'https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}'
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        rate = float(data.get('lastFundingRate', 0))
                        
                        # Extreme funding = crowded trade = reversal risk
                        is_extreme = abs(rate) > 0.001  # > 0.1% per 8h
                        
                        result = {
                            'funding_rate': rate,
                            'funding_annualized': rate * 3 * 365,  # 3 times per day
                            'mark_price': float(data.get('markPrice', 0)),
                            'index_price': float(data.get('indexPrice', 0)),
                            'is_extreme': is_extreme,
                            'bias': 'overleveraged_long' if rate > 0.0005 else 'overleveraged_short' if rate < -0.0005 else 'neutral'
                        }
                        
                        self._update_cache(cache_key, result)
                        logger.info(f"Funding rate for {symbol}: {rate:.6f} ({result['bias']})")
                        return result
        except Exception as e:
            logger.error(f"Funding rate fetch error: {e}")
        
        return {'funding_rate': 0, 'bias': 'neutral', 'is_extreme': False}
    
    async def fetch_liquidations(self, symbol: str = 'BTCUSDT') -> Dict:
        """
        Fetch recent liquidations. Large liquidations = potential reversal zones.
        High long liq = shorts got squeezed = potential top
        High short liq = longs got squeezed = potential bottom
        """
        cache_key = f'liq_{symbol}'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get forced orders (liquidations) - requires API key, so we use estimated from trades
                # Alternative: fetch 24h stats which include liquidation info
                url = f'https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}'
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # High volume with extreme wicks = liquidations happened
                        high = float(data.get('highPrice', 0))
                        low = float(data.get('lowPrice', 0))
                        open_p = float(data.get('openPrice', 0))
                        close = float(data.get('lastPrice', 0))
                        volume = float(data.get('volume', 0))
                        quote_volume = float(data.get('quoteVolume', 0))
                        
                        # Detect liquidation wicks
                        upper_wick = (high - max(open_p, close)) / close if close > 0 else 0
                        lower_wick = (min(open_p, close) - low) / close if close > 0 else 0
                        
                        wick_ratio = upper_wick + lower_wick
                        
                        result = {
                            'volume_24h': volume,
                            'quote_volume_24h': quote_volume,
                            'upper_wick_pct': upper_wick * 100,
                            'lower_wick_pct': lower_wick * 100,
                            'wick_ratio': wick_ratio,
                            'liquidation_estimate': 'high' if wick_ratio > 0.03 else 'moderate' if wick_ratio > 0.015 else 'low',
                            'bias': 'potential_reversal_down' if upper_wick > lower_wick * 2 else 'potential_reversal_up' if lower_wick > upper_wick * 2 else 'neutral'
                        }
                        
                        self._update_cache(cache_key, result)
                        return result
        except Exception as e:
            logger.error(f"Liquidation fetch error: {e}")
        
        return {'liquidation_estimate': 'unknown', 'bias': 'neutral'}
    
    async def fetch_open_interest(self, symbol: str = 'BTCUSDT') -> Dict:
        """
        Fetch open interest. Rising OI + rising price = strong trend.
        Rising OI + falling price = distribution (potential reversal).
        """
        cache_key = f'oi_{symbol}'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f'https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}'
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        oi = float(data.get('openInterest', 0))
                        
                        result = {
                            'open_interest': oi,
                            'timestamp': data.get('time', 0),
                            'high_oi': oi > 500000  # Contextual threshold for BTC
                        }
                        
                        self._update_cache(cache_key, result)
                        return result
        except Exception as e:
            logger.error(f"Open interest fetch error: {e}")
        
        return {'open_interest': 0, 'high_oi': False}
    
    async def fetch_btc_trend(self) -> Dict:
        """Fetch BTC price trend for market direction"""
        cache_key = 'btc_trend'
        if self._is_cache_valid(cache_key):
            return self.caches[cache_key]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.coingecko_btc, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = [p[1] for p in data.get('prices', [])]
                        
                        if len(prices) >= 2:
                            change_24h = ((prices[-1] - prices[-2]) / prices[-2]) * 100
                            change_7d = ((prices[-1] - prices[0]) / prices[0]) * 100
                            
                            result = {
                                'current_price': prices[-1],
                                'change_24h': change_24h,
                                'change_7d': change_7d,
                                'trend': 'bullish' if change_24h > 2 else 'bearish' if change_24h < -2 else 'neutral'
                            }
                            
                            self._update_cache(cache_key, result)
                            return result
        except Exception as e:
            logger.error(f"BTC trend fetch error: {e}")
        
        return {'current_price': 0, 'change_24h': 0, 'change_7d': 0, 'trend': 'neutral'}
    
    # ==================== ANALYSIS ====================
    
    def analyze_sentiment(self, articles: List[Dict], direction: str = None) -> Dict:
        """Analyze sentiment from all news sources - direction-aware
        
        Args:
            articles: List of news articles
            direction: Signal direction ('LONG' or 'SHORT') - determines if news aligns with trade
        """
        if not articles:
            return {'score': 70, 'sentiment': 'neutral', 'high_impact': False, 'high_impact_positive': False, 'news_aligns_direction': True}
        
        positive_count = 0
        negative_count = 0
        high_impact_count = 0
        high_impact_positive = 0
        high_impact_negative = 0
        
        for article in articles[:20]:  # Analyze top 20
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            
            # Check if this article has high-impact keywords
            has_high_impact = any(kw in text for kw in self.high_impact_keywords)
            
            if has_high_impact:
                high_impact_count += 1
                
                # Check if this high-impact news is POSITIVE or NEGATIVE
                if any(kw in text for kw in self.positive_keywords):
                    high_impact_positive += 1
                    positive_count += 1
                elif any(kw in text for kw in self.negative_keywords):
                    high_impact_negative += 1
                    negative_count += 1
                else:
                    # High-impact but unclear sentiment - check pre-analyzed
                    if article.get('sentiment') == 'positive':
                        high_impact_positive += 1
                        positive_count += 1
                    elif article.get('sentiment') == 'negative':
                        high_impact_negative += 1
                        negative_count += 1
                    else:
                        # Neutral high-impact (like "SEC announcement") - be cautious
                        negative_count += 1
            else:
                # Not high-impact - just check normal sentiment
                if any(kw in text for kw in self.positive_keywords):
                    positive_count += 1
                elif any(kw in text for kw in self.negative_keywords):
                    negative_count += 1
                elif article.get('sentiment') == 'positive':
                    positive_count += 1
                elif article.get('sentiment') == 'negative':
                    negative_count += 1
        
        # Calculate sentiment score
        total_analyzed = positive_count + negative_count
        if total_analyzed == 0:
            return {'score': 70, 'sentiment': 'neutral', 'high_impact': False, 'high_impact_positive': False, 'news_aligns_direction': True}
        
        positive_ratio = positive_count / total_analyzed
        
        # Check if news aligns with trade direction
        # LONG signals need positive news (bullish)
        # SHORT signals need negative news (bearish)
        if direction == 'LONG':
            # For LONG: positive news = good, negative news = bad
            news_aligns = positive_ratio > 0.4  # More positive than negative
            alignment_score = positive_ratio
        elif direction == 'SHORT':
            # For SHORT: negative news = good, positive news = bad
            news_aligns = positive_ratio < 0.5  # More negative than positive
            alignment_score = 1 - positive_ratio
        else:
            news_aligns = True
            alignment_score = positive_ratio
        
        # Direction-aware scoring logic:
        # For LONG signals:
        #   - Positive high-impact news = GOOD (e.g., "ETF approved", "Bullish rally")
        #   - Negative high-impact news = BAD (e.g., "Hack", "Crash", "Ban")
        # For SHORT signals:
        #   - Negative high-impact news = GOOD (market crash, ban, etc.)
        #   - Positive high-impact news = BAD (ETF approval, rally = market going up)
        
        if high_impact_count > 2:
            if direction == 'SHORT':
                # For SHORT signals: negative news is GOOD
                if high_impact_negative > high_impact_positive:
                    score = 90  # Mostly negative high-impact news = EXCELLENT for SHORT
                elif high_impact_positive > high_impact_negative:
                    score = 25  # Mostly positive high-impact news = BAD for SHORT
                else:
                    score = 50  # Mixed
            else:
                # For LONG signals (default): positive news is GOOD
                if high_impact_positive > high_impact_negative:
                    score = 90  # Mostly positive high-impact news = EXCELLENT for LONG
                elif high_impact_negative > high_impact_positive:
                    score = 25  # Mostly negative high-impact news = BAD for LONG
                else:
                    score = 50  # Mixed
        elif alignment_score > 0.6:
            score = 85
        elif alignment_score > 0.4:
            score = 70
        elif alignment_score > 0.2:
            score = 55
        else:
            score = 40
        
        sentiment = 'positive' if positive_ratio > 0.6 else 'negative' if positive_ratio < 0.3 else 'neutral'
        
        return {
            'score': score,
            'sentiment': sentiment,
            'high_impact': high_impact_count > 0,
            'high_impact_positive': high_impact_positive > high_impact_negative,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'high_impact_count': high_impact_count,
            'high_impact_positive_count': high_impact_positive,
            'high_impact_negative_count': high_impact_negative,
            'news_aligns_direction': news_aligns,
            'alignment_score': alignment_score
        }
    
    def check_macro_conditions(self, fear_greed: Dict, market_data: Dict, btc_trend: Dict) -> Dict:
        """Check macro economic conditions"""
        score = 70  # Neutral baseline
        warnings = []
        
        # Fear & Greed analysis
        fng_value = fear_greed.get('value', 50)
        if fng_value <= 20:  # Extreme fear
            score -= 20
            warnings.append("Extreme fear in market - potential bottom")
        elif fng_value <= 40:  # Fear
            score -= 10
            warnings.append("Market fear detected")
        elif fng_value >= 80:  # Extreme greed
            score -= 15
            warnings.append("Extreme greed - potential top")
        elif fng_value >= 70:  # Greed
            score -= 5
        else:
            score += 5  # Neutral zone = good for trading
        
        # Market cap change
        market_change = market_data.get('market_cap_change_24h', 0)
        if market_change < -5:
            score -= 15
            warnings.append(f"Market down {market_change:.1f}% in 24h")
        elif market_change > 5:
            score += 10
        
        # BTC trend
        btc_change = btc_trend.get('change_24h', 0)
        if btc_change < -3:
            score -= 10
            warnings.append(f"BTC down {btc_change:.1f}% in 24h")
        elif btc_change > 3:
            score += 5
        
        # Volume analysis
        if market_data.get('total_volume_24h', 0) > 0:
            volume_ratio = market_data['total_volume_24h'] / market_data.get('total_market_cap', 1)
            if volume_ratio > 0.05:  # High volume day
                score -= 5
                warnings.append("High volume - potential volatility")
        
        return {
            'score': max(0, min(100, score)),
            'fear_greed': fng_value,
            'fear_greed_classification': fear_greed.get('classification', 'Neutral'),
            'btc_24h_change': btc_change,
            'market_24h_change': market_change,
            'warnings': warnings
        }
    
    # ==================== MAIN INTERFACE ====================
    
    async def analyze_context(self, symbol: str, direction: str = None, forex_client=None) -> ContextScore:
        """Comprehensive context analysis for a trading symbol
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT or EUR/USD)
            direction: Signal direction ('LONG' or 'SHORT') - used to check if news aligns with trade
            forex_client: Optional ForexClient for DXY/risk appetite data (Forex symbols only)
        """
        
        # Detect Forex symbols (contain "/" like EUR/USD, XAU/USD)
        is_forex = '/' in symbol
        
        # Fetch all data sources
        newsapi_articles = await self.fetch_newsapi_news()
        crypto_articles = await self.fetch_cryptonews() if not is_forex else []
        
        # Combine all news
        all_articles = newsapi_articles + crypto_articles
        
        # For Forex: use dedicated macro engine (DXY, risk appetite, session)
        if is_forex:
            # Get news sentiment
            sentiment = self.analyze_sentiment(all_articles, direction)
            news_score = sentiment['score']
            
            # Get macro analysis (DXY, risk appetite, session)
            if forex_client:
                try:
                    macro_data = await self.forex_macro.analyze_macro(forex_client, symbol, direction)
                    macro_score = macro_data['macro_score']
                    sentiment_score = macro_data['sentiment_score']
                    total_score = (
                        macro_score * 0.35 +
                        news_score * 0.45 +
                        sentiment_score * 0.20
                    )
                    
                    for warning in macro_data.get('warnings', []):
                        logger.info(f"🌍 {symbol}: {warning}")
                    
                    logger.info(
                        f"🌍 Context analysis for {symbol} ({direction}): "
                        f"DXY={macro_data['dxy_reading']:.2f}({macro_data['dxy_trend']}), "
                        f"Risk={macro_data['risk_appetite']}, Session={macro_data['session']}, "
                        f"News={news_score:.0f}, Macro={macro_score:.0f}, Sentiment={sentiment_score:.0f}, Total={total_score:.0f}"
                    )
                    
                    return ContextScore(
                        macro_score=macro_score,
                        news_score=news_score,
                        sentiment_score=sentiment_score,
                        total_score=total_score
                    )
                except Exception as e:
                    logger.warning(f"Forex macro analysis failed for {symbol}: {e}, falling back to news-only")
            
            # Fallback: news-only analysis if macro engine fails or no forex_client
            macro_score = 50
            if sentiment.get('news_aligns_direction', False):
                sentiment_score = 80
            elif sentiment.get('high_impact_negative_count', 0) > sentiment.get('high_impact_positive_count', 0):
                sentiment_score = 30
            else:
                sentiment_score = 60
            
            total_score = macro_score * 0.20 + news_score * 0.50 + sentiment_score * 0.30
            
            logger.info(
                f"Context analysis for {symbol} ({direction}): "
                f"News={news_score:.0f}, Macro={macro_score:.0f} (neutral), "
                f"Sentiment={sentiment_score:.0f}, Total={total_score:.0f}"
            )
            
            return ContextScore(
                macro_score=macro_score,
                news_score=news_score,
                sentiment_score=sentiment_score,
                total_score=total_score
            )
        
        # ========== CRYPTO-SPECIFIC ANALYSIS BELOW ==========
        
        # Fetch market context
        fear_greed = await self.fetch_fear_greed_index()
        market_data = await self.fetch_market_data()
        btc_trend = await self.fetch_btc_trend()
        
        # Fetch market bias data (futures/leverage sentiment)
        base_symbol = symbol.replace('/', '')  # BTC/USDT -> BTCUSDT
        if not base_symbol.endswith('USDT'):
            base_symbol += 'USDT'
        
        funding = await self.fetch_funding_rates(base_symbol)
        liquidations = await self.fetch_liquidations(base_symbol)
        oi = await self.fetch_open_interest(base_symbol)
        
        # Whale activity (free via Binance public trades)
        whale = await self.whale_monitor.check_symbol(symbol)
        
        # Analyze sentiment (direction-aware)
        sentiment = self.analyze_sentiment(all_articles, direction)
        macro = self.check_macro_conditions(fear_greed, market_data, btc_trend)
        
        # Calculate final scores
        news_score = sentiment['score']
        macro_score = macro['score']
        
        # Market sentiment score based on BTC trend and fear/greed
        # Direction-aware: bullish market helps LONG, hurts SHORT
        if btc_trend.get('trend') == 'bullish':
            if direction == 'LONG':
                sentiment_score = 85  # Bullish market + LONG = great
            elif direction == 'SHORT':
                sentiment_score = 45  # Bullish market + SHORT = risky
            else:
                sentiment_score = 80
        elif btc_trend.get('trend') == 'bearish':
            if direction == 'SHORT':
                sentiment_score = 85  # Bearish market + SHORT = great
            elif direction == 'LONG':
                sentiment_score = 45  # Bearish market + LONG = risky
            else:
                sentiment_score = 45
        else:
            sentiment_score = 65  # Neutral
        
        # Adjust for fear/greed
        fng_value = fear_greed.get('value', 50)
        if fng_value < 25:  # Extreme fear
            if direction == 'LONG':
                sentiment_score += 10  # Extreme fear = buying opportunity for LONG
            elif direction == 'SHORT':
                sentiment_score -= 10  # Extreme fear = already crashed, SHORT risky
        elif fng_value > 75:  # Extreme greed
            if direction == 'SHORT':
                sentiment_score += 10  # Extreme greed = top for SHORT
            elif direction == 'LONG':
                sentiment_score -= 10  # Extreme greed = top, LONG risky
        
        # Adjust for MARKET BIAS (futures data)
        # Funding rate: extreme positive = crowded longs = contrarian bearish signal
        funding_bias = funding.get('bias', 'neutral')
        if funding_bias == 'overleveraged_long' and direction == 'SHORT':
            sentiment_score += 12  # Everyone long = SHORT opportunity
        elif funding_bias == 'overleveraged_long' and direction == 'LONG':
            sentiment_score -= 8  # Crowded long = LONG risky
        elif funding_bias == 'overleveraged_short' and direction == 'LONG':
            sentiment_score += 12  # Everyone short = LONG opportunity
        elif funding_bias == 'overleveraged_short' and direction == 'SHORT':
            sentiment_score -= 8  # Crowded short = SHORT risky
        
        # Liquidation bias: recent large wicks = reversal likely
        liq_bias = liquidations.get('bias', 'neutral')
        if liq_bias == 'potential_reversal_down' and direction == 'SHORT':
            sentiment_score += 8  # Upper wick = down reversal = SHORT boost
        elif liq_bias == 'potential_reversal_up' and direction == 'LONG':
            sentiment_score += 8  # Lower wick = up reversal = LONG boost
        
        # Whale activity adjustments (free Binance trade data)
        if whale:
            if whale.is_accumulating:
                if direction == 'LONG':
                    sentiment_score += 10  # Whales buying = LONG boost
                    logger.info(f"🐋 Whale accumulation detected for {symbol} — boosting LONG score")
                elif direction == 'SHORT':
                    sentiment_score -= 8   # Whales buying = SHORT risky
                    logger.info(f"🐋 Whale accumulation detected for {symbol} — penalizing SHORT")
            elif whale.is_distributing:
                if direction == 'SHORT':
                    sentiment_score += 10  # Whales selling = SHORT boost
                    logger.info(f"🐋 Whale distribution detected for {symbol} — boosting SHORT score")
                elif direction == 'LONG':
                    sentiment_score -= 8   # Whales selling = LONG risky
                    logger.info(f"🐋 Whale distribution detected for {symbol} — penalizing LONG")
        
        # Clamp sentiment score
        sentiment_score = max(0, min(100, sentiment_score))
        
        # Weights: Macro 35%, News 40%, Sentiment 25%
        total_score = (
            macro_score * 0.35 +
            news_score * 0.40 +
            sentiment_score * 0.25
        )
        
        # Handle high-impact news with direction awareness:
        # For LONG signals: positive news = BOOST, negative news = PENALTY
        # For SHORT signals: negative news = BOOST, positive news = PENALTY
        if sentiment['high_impact']:
            news_aligns = sentiment.get('news_aligns_direction', False)
            
            if news_aligns:
                # News CONFIRMS the trade direction (e.g., LONG + good news)
                total_score *= 1.20  # 20% boost
                if direction:
                    logger.info(f"✅ News aligns with {direction} for {symbol} - strong boost")
                else:
                    logger.info(f"✅ Positive high-impact news for {symbol} - boosting context score")
            elif sentiment['high_impact_negative_count'] > sentiment.get('high_impact_positive_count', 0):
                if direction:
                    # News CONTRADICTS the trade direction (e.g., LONG + bad news)
                    total_score *= 0.6   # 40% penalty
                    logger.warning(f"⚠️ News contradicts {direction} for {symbol} - strong penalty")
                else:
                    total_score *= 0.7   # 30% penalty
                    logger.warning(f"⚠️ Negative high-impact news for {symbol} - reducing context score")
            else:
                # Mixed/unclear high-impact news - be cautious
                total_score *= 0.85  # 15% penalty
                logger.warning(f"⚠️ Mixed high-impact news for {symbol} - slight caution")
        
        logger.info(
            f"Context analysis for {symbol} ({direction or 'no direction'}): "
            f"News={news_score:.0f}, Macro={macro_score:.0f}, "
            f"Sentiment={sentiment_score:.0f}, Total={total_score:.0f}"
        )
        
        return ContextScore(
            macro_score=macro_score,
            news_score=news_score,
            sentiment_score=sentiment_score,
            total_score=total_score
        )
    
    async def get_context_summary(self, symbol: str) -> str:
        """Generate human-readable context summary"""
        
        # Fetch data
        fear_greed = await self.fetch_fear_greed_index()
        market_data = await self.fetch_market_data()
        btc_trend = await self.fetch_btc_trend()
        all_articles = await self.fetch_newsapi_news() + await self.fetch_cryptonews()
        
        # Analyze sentiment
        sentiment = self.analyze_sentiment(all_articles)
        macro = self.check_macro_conditions(fear_greed, market_data, btc_trend)
        
        summary = []
        
        # Market sentiment
        fng = fear_greed.get('value', 50)
        fng_class = fear_greed.get('classification', 'Neutral')
        summary.append(f"😰 Fear & Greed: {fng}/100 ({fng_class})")
        
        # BTC trend
        btc_change = btc_trend.get('change_24h', 0)
        summary.append(f"₿ BTC 24h: {btc_change:+.2f}%")
        
        # Market cap change
        market_change = market_data.get('market_cap_change_24h', 0)
        summary.append(f"📊 Market 24h: {market_change:+.2f}%")
        
        # News sentiment
        summary.append(f"📰 News: {sentiment['sentiment'].title()} ({sentiment['positive_count']}+ / {sentiment['negative_count']}-)")
        
        # Whale activity (free via Binance public API)
        whale = await self.whale_monitor.check_symbol(symbol)
        if whale and whale.alerts:
            net = whale.net_flow_usd
            emoji = "🟢" if net > 0 else "🔴"
            summary.append(
                f"🐋 Whale Activity: {emoji} ${abs(net):,.0f} net "
                f"({whale.buy_count} buy / {whale.sell_count} sell trades, "
                f"largest ${whale.largest_single_trade_usd:,.0f})"
            )
        
        # Warnings
        if macro['warnings']:
            summary.append(f"⚠️ Warnings: {', '.join(macro['warnings'])}")
        
        # High impact news - SHOW SPECIFIC HEADLINES with dates/times
        if sentiment['high_impact'] and all_articles:
            high_impact_articles = self._extract_high_impact_news(all_articles)
            if high_impact_articles:
                summary.append("\n🔴 HIGH-IMPACT NEWS:")
                for article in high_impact_articles[:2]:  # Show top 2
                    published = article.get('publishedAt', article.get('date', ''))
                    if published:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                            time_str = dt.strftime('%b %d, %H:%M UTC')
                        except:
                            time_str = published[:16] if len(published) > 16 else published
                    else:
                        time_str = 'Recent'
                    
                    title = article.get('title', 'Unknown')[:80]
                    summary.append(f"  • {title}")
                    summary.append(f"    📅 {time_str}")
        
        return '\n'.join(summary)
    
    def _extract_high_impact_news(self, articles: List[Dict]) -> List[Dict]:
        """Extract high-impact news articles from the list"""
        high_impact = []
        
        for article in articles:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            text = f"{title} {description}"
            
            # Check for high-impact keywords
            has_high_impact = any(kw in text for kw in self.high_impact_keywords)
            
            if has_high_impact:
                high_impact.append(article)
        
        # Sort by date (most recent first)
        high_impact.sort(key=lambda x: x.get('publishedAt', x.get('date', '')), reverse=True)
        
        return high_impact
    
    # ==================== CACHE MANAGEMENT ====================
    
    def _is_cache_valid(self, key: str, duration_minutes: int = None) -> bool:
        """Check if cache entry is still valid"""
        if key not in self.last_fetches:
            return False
        duration = timedelta(minutes=duration_minutes) if duration_minutes else self.cache_duration
        return datetime.utcnow() - self.last_fetches[key] < duration
    
    def _update_cache(self, key: str, data):
        """Update cache with new data"""
        self.caches[key] = data
        self.last_fetches[key] = datetime.utcnow()
    
    async def clear_cache(self):
        """Clear all caches"""
        self.caches.clear()
        self.last_fetches.clear()
        logger.info("Context engine cache cleared")


# Backwards compatibility alias
ContextEngine = EnhancedContextEngine
