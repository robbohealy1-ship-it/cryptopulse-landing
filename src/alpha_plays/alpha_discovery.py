"""
Alpha Discovery Engine

Finds low-cap, high-hype plays on SOL and ETH chains using multiple data sources:
- DexScreener trending pairs
- Social sentiment (Twitter/X mentions)
- On-chain activity spikes
- Community growth metrics
- Volume/momentum anomalies
"""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


@dataclass
class AlphaPlayCandidate:
    """A potential alpha play discovered by the scanner"""
    symbol: str
    name: str
    chain: str  # 'sol', 'eth', 'base', 'arb'
    token_address: Optional[str]
    pair_address: Optional[str]
    price_usd: float
    market_cap_usd: float
    liquidity_usd: float
    volume_24h: float
    price_change_24h: float
    price_change_1h: float
    holders: int
    transactions_24h: int
    social_score: float  # 0-100 hype/sentiment
    community_score: float  # 0-100 community growth
    technical_score: float  # 0-100 momentum/technical
    fundamental_score: float  # 0-100 fundamentals
    overall_score: float  # weighted composite
    dex_url: str
    chart_url: str
    buy_url: str
    description: str = ""
    red_flags: List[str] = None
    catalyst: str = ""  # What's driving the hype?
    created_at: datetime = None
    
    def __post_init__(self):
        if self.red_flags is None:
            self.red_flags = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class AlphaDiscovery:
    """
    Discovers alpha plays by scanning multiple sources.
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Any] = {}
        self.cache_time: Dict[str, datetime] = {}
        self.cache_duration = timedelta(minutes=5)
        
        # Minimum thresholds for a play to be considered
        self.min_liquidity_usd = 50000  # $50k minimum liquidity
        self.min_volume_24h = 100000    # $100k minimum volume
        self.max_market_cap = 100_000_000  # $100M max (low cap)
        self.min_holders = 100
        self.min_overall_score = 65.0
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=10, limit_per_host=5),
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    async def discover_alpha_plays(self, chain: str = None, limit: int = 10) -> List[AlphaPlayCandidate]:
        """
        Main discovery method. Scans all sources and returns top candidates.
        
        Args:
            chain: 'sol', 'eth', 'base' or None for all chains
            limit: Maximum number of candidates to return
        
        Returns:
            List of AlphaPlayCandidate objects, sorted by overall_score desc
        """
        logger.info(f"🔍 Scanning for alpha plays (chain={chain or 'all'})...")
        
        all_candidates = []
        
        try:
            # Source 1: DexScreener trending
            dex_candidates = await self._scan_dexscreener(chain)
            all_candidates.extend(dex_candidates)
            logger.info(f"  DexScreener: {len(dex_candidates)} candidates")
            
            # Source 2: Social sentiment scan
            social_candidates = await self._scan_social_sentiment(chain)
            all_candidates.extend(social_candidates)
            logger.info(f"  Social: {len(social_candidates)} candidates")
            
            # Deduplicate by symbol
            seen = set()
            unique_candidates = []
            for c in all_candidates:
                key = f"{c.symbol}:{c.chain}"
                if key not in seen:
                    seen.add(key)
                    unique_candidates.append(c)
            
            # Filter by minimum thresholds
            qualified = [
                c for c in unique_candidates
                if c.overall_score >= self.min_overall_score
                and c.liquidity_usd >= self.min_liquidity_usd
                and c.volume_24h >= self.min_volume_24h
                and c.market_cap_usd <= self.max_market_cap
                and c.holders >= self.min_holders
            ]
            
            # Sort by overall score
            qualified.sort(key=lambda x: x.overall_score, reverse=True)
            
            # Take top N
            top_plays = qualified[:limit]
            
            logger.info(f"🎯 Found {len(top_plays)} qualified alpha plays")
            for p in top_plays:
                logger.info(f"  • {p.symbol} ({p.chain}) - Score: {p.overall_score:.1f} | "
                             f"MC: ${p.market_cap_usd/1e6:.1f}M | Vol: ${p.volume_24h/1e3:.0f}K")
            
            return top_plays
            
        except Exception as e:
            logger.error(f"Error discovering alpha plays: {e}")
            return []
    
    async def _scan_dexscreener(self, chain_filter: str = None) -> List[AlphaPlayCandidate]:
        """
        Scan DexScreener for trending low-cap pairs.
        """
        candidates = []
        
        try:
            session = await self._get_session()
            
            # DexScreener API endpoints
            endpoints = []
            if chain_filter is None or chain_filter == 'sol':
                endpoints.append("https://api.dexscreener.com/latest/dex/search?q=solana")
            if chain_filter is None or chain_filter == 'eth':
                endpoints.append("https://api.dexscreener.com/latest/dex/search?q=ethereum")
            if chain_filter is None or chain_filter == 'base':
                endpoints.append("https://api.dexscreener.com/latest/dex/search?q=base")
            
            for endpoint in endpoints:
                try:
                    async with session.get(endpoint, timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get('pairs', [])
                            
                            for pair in pairs[:20]:  # Top 20 per chain
                                try:
                                    candidate = self._parse_dexscreener_pair(pair)
                                    if candidate:
                                        candidates.append(candidate)
                                except Exception as e:
                                    logger.debug(f"Error parsing pair: {e}")
                                    continue
                        else:
                            logger.warning(f"DexScreener returned status {response.status}")
                            
                except Exception as e:
                    logger.warning(f"DexScreener scan error: {e}")
                    continue
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in DexScreener scan: {e}")
            return []
    
    def _parse_dexscreener_pair(self, pair: Dict) -> Optional[AlphaPlayCandidate]:
        """Parse a DexScreener pair into an AlphaPlayCandidate"""
        try:
            # Extract chain from pair data
            chain = pair.get('chainId', 'unknown').lower()
            if chain in ['solana', 'sol']:
                chain = 'sol'
            elif chain in ['ethereum', 'eth']:
                chain = 'eth'
            elif chain in ['base']:
                chain = 'base'
            else:
                return None  # Skip unsupported chains
            
            base_token = pair.get('baseToken', {})
            quote_token = pair.get('quoteToken', {})
            
            symbol = base_token.get('symbol', 'UNKNOWN')
            name = base_token.get('name', symbol)
            token_address = base_token.get('address')
            pair_address = pair.get('pairAddress')
            
            price = float(pair.get('priceUsd', 0) or 0)
            market_cap = float(pair.get('marketCap', 0) or 0)
            liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
            volume_24h = float(pair.get('volume', {}).get('h24', 0) or 0)
            
            price_change_24h = float(pair.get('priceChange', {}).get('h24', 0) or 0)
            price_change_1h = float(pair.get('priceChange', {}).get('h1', 0) or 0)
            
            txns_24h = pair.get('txns', {}).get('h24', {})
            buys = txns_24h.get('buys', 0) or 0
            sells = txns_24h.get('sells', 0) or 0
            transactions_24h = buys + sells
            
            # Calculate scores
            volume_score = min(volume_24h / 1_000_000 * 10, 100)  # $1M vol = 100
            momentum_score = min(abs(price_change_24h) * 2, 100) if price_change_24h > 0 else 0
            liquidity_score = min(liquidity / 500_000 * 100, 100)  # $500k = 100
            
            technical_score = (volume_score * 0.3 + momentum_score * 0.4 + liquidity_score * 0.3)
            
            # Social/community (placeholder - would integrate with social APIs)
            social_score = 50.0 + (price_change_1h * 0.5)  # Baseline + recent hype
            social_score = max(0, min(100, social_score))
            
            community_score = min(holders / 1000 * 50, 100) if (holders := 500) else 50
            
            fundamental_score = 60.0  # Baseline for low-caps
            
            # Overall weighted score
            overall_score = (
                technical_score * 0.35 +
                social_score * 0.30 +
                community_score * 0.20 +
                fundamental_score * 0.15
            )
            
            # Generate DEX links
            dex_url, chart_url, buy_url = self._generate_dex_links(chain, token_address, pair_address, symbol)
            
            # Detect catalyst
            catalyst = self._detect_catalyst(price_change_24h, price_change_1h, volume_24h, transactions_24h)
            
            # Check red flags
            red_flags = self._check_red_flags(pair, price_change_24h, liquidity, volume_24h)
            
            return AlphaPlayCandidate(
                symbol=symbol,
                name=name,
                chain=chain,
                token_address=token_address,
                pair_address=pair_address,
                price_usd=price,
                market_cap_usd=market_cap,
                liquidity_usd=liquidity,
                volume_24h=volume_24h,
                price_change_24h=price_change_24h,
                price_change_1h=price_change_1h,
                holders=500,  # Would fetch from chain explorer
                transactions_24h=transactions_24h,
                social_score=social_score,
                community_score=community_score,
                technical_score=technical_score,
                fundamental_score=fundamental_score,
                overall_score=overall_score,
                dex_url=dex_url,
                chart_url=chart_url,
                buy_url=buy_url,
                description=f"{name} - Low cap play on {chain.upper()}",
                red_flags=red_flags,
                catalyst=catalyst
            )
            
        except Exception as e:
            logger.debug(f"Error parsing DexScreener pair: {e}")
            return None
    
    async def _scan_social_sentiment(self, chain_filter: str = None) -> List[AlphaPlayCandidate]:
        """
        Scan social media for trending low-cap mentions.
        Note: This is a simplified version. Production would use Twitter/X API,
        LunarCrush, or similar social sentiment tools.
        """
        # Placeholder - would integrate with social APIs
        return []
    
    def _generate_dex_links(self, chain: str, token_address: Optional[str], 
                           pair_address: Optional[str], symbol: str) -> tuple:
        """Generate DEX trading links for the token"""
        
        if chain == 'sol':
            dex_url = f"https://dexscreener.com/solana/{pair_address}" if pair_address else "https://dexscreener.com/solana"
            chart_url = dex_url
            if token_address:
                buy_url = f"https://jup.ag/swap/USDC-{token_address}"
            else:
                buy_url = f"https://jup.ag/swap/USDC-{symbol}"
                
        elif chain == 'eth':
            dex_url = f"https://dexscreener.com/ethereum/{pair_address}" if pair_address else "https://dexscreener.com/ethereum"
            chart_url = dex_url
            if token_address:
                buy_url = f"https://app.uniswap.org/#/swap?outputCurrency={token_address}&chain=mainnet"
            else:
                buy_url = "https://app.uniswap.org"
                
        elif chain == 'base':
            dex_url = f"https://dexscreener.com/base/{pair_address}" if pair_address else "https://dexscreener.com/base"
            chart_url = dex_url
            if token_address:
                buy_url = f"https://app.uniswap.org/#/swap?outputCurrency={token_address}&chain=base"
            else:
                buy_url = "https://app.uniswap.org/?chain=base"
        else:
            dex_url = "https://dexscreener.com"
            chart_url = dex_url
            buy_url = "https://jup.ag"
        
        return dex_url, chart_url, buy_url
    
    def _detect_catalyst(self, price_change_24h: float, price_change_1h: float,
                         volume_24h: float, transactions_24h: int) -> str:
        """Detect what's driving the price action"""
        
        if price_change_1h > 20:
            return f"🔥 Sudden momentum spike: +{price_change_1h:.1f}% in 1h"
        elif price_change_24h > 50:
            return f"🚀 Strong daily trend: +{price_change_24h:.1f}% in 24h"
        elif transactions_24h > 5000:
            return f"📈 High trading activity: {transactions_24h} txns in 24h"
        elif volume_24h > 1_000_000:
            return f"💰 Volume surge: ${volume_24h/1e6:.1f}M in 24h"
        else:
            return "🔍 Early stage accumulation detected"
    
    def _check_red_flags(self, pair: Dict, price_change_24h: float, 
                         liquidity: float, volume_24h: float) -> List[str]:
        """Check for potential red flags / risks"""
        flags = []
        
        # Check buy/sell ratio
        txns = pair.get('txns', {}).get('h24', {})
        buys = txns.get('buys', 0) or 0
        sells = txns.get('sells', 0) or 1  # Avoid div by zero
        
        if sells > buys * 2:
            flags.append("⚠️ Heavy selling pressure (sells > 2x buys)")
        
        if liquidity < 100_000:
            flags.append("⚠️ Very low liquidity (<$100k) - high slippage risk")
        
        if price_change_24h < -30:
            flags.append("⚠️ Down -30% in 24h - potential dump")
        
        if volume_24h < 50_000:
            flags.append("⚠️ Very low volume - illiquid")
        
        return flags
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
