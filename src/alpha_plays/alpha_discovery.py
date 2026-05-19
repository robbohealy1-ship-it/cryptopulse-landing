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
    # Required fields (no defaults)
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

    # Optional fields (all have defaults)
    price_change_5min: float = 0.0
    buys_24h: int = 0
    sells_24h: int = 0
    description: str = ""
    red_flags: List[str] = None
    catalyst: str = ""  # What's driving the hype?
    created_at: datetime = None

    # Trade classification
    trade_type: str = ""  # 'day_trade' or 'swing' or 'fundamental'
    time_frame: str = ""  # '1-4h', '4-24h', '1-3d', '3-7d'

    # Fundamental data for mini-report
    holder_growth_24h: float = 0.0  # % change in holders
    liquidity_growth_24h: float = 0.0  # % change in liquidity
    volume_growth_24h: float = 0.0  # % change in volume vs prev 24h
    top_holder_concentration: float = 0.0  # % held by top 10 wallets
    buy_sell_ratio: float = 1.0  # buys / sells
    fdv: float = 0.0  # Fully diluted valuation
    circulating_supply: float = 0.0
    total_supply: float = 0.0

    # Mini report fields
    narrative: str = ""  # e.g. "AI + Solana ecosystem"
    why_trending: str = ""  # Why is this pumping?
    short_term_potential: str = ""  # 1-3 day outlook
    long_term_potential: str = ""  # 1-4 week outlook
    risk_level: str = "medium"  # low, medium, high, degen

    # DEX source tracking
    dex_source: str = ""  # 'dexscreener', 'geckoterminal', 'birdeye'
    pair_created_at: Optional[datetime] = None  # When was the pair created?

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
        self.min_liquidity_usd = 30000  # $30k minimum liquidity
        self.min_volume_24h = 50000     # $50k minimum volume
        self.max_market_cap = 100_000_000  # $100M max (low cap)
        self.min_holders = 50
        self.min_overall_score = 50.0  # Lowered for realistic low-cap scores
        
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
        Main discovery method. Scans multiple free DEX APIs and returns top candidates.
        
        Sources:
        - DexScreener trending (free, no API key)
        - GeckoTerminal trending (free, no API key)
        - Birdeye trending (Solana only, free tier)
        
        Args:
            chain: 'sol', 'eth', 'base' or None for all chains
            limit: Maximum number of candidates to return
        
        Returns:
            List of AlphaPlayCandidate objects, sorted by overall_score desc
        """
        logger.info(f"🔍 Scanning for alpha plays (chain={chain or 'all'})...")
        
        all_candidates = []
        
        try:
            # Source 1: DexScreener trending pairs (free, no key)
            dex_candidates = await self._scan_dexscreener(chain)
            all_candidates.extend(dex_candidates)
            logger.info(f"  DexScreener: {len(dex_candidates)} candidates")
            
            # Source 2: GeckoTerminal trending (free, no key)
            gecko_candidates = await self._scan_geckoterminal(chain)
            all_candidates.extend(gecko_candidates)
            logger.info(f"  GeckoTerminal: {len(gecko_candidates)} candidates")
            
            # Source 3: DexScreener top gainers (free)
            gainers = await self._scan_dexscreener_gainers(chain)
            all_candidates.extend(gainers)
            logger.info(f"  DexScreener gainers: {len(gainers)} candidates")
            
            # Deduplicate by symbol+chain
            seen = set()
            unique_candidates = []
            for c in all_candidates:
                key = f"{c.symbol}:{c.chain}"
                if key not in seen:
                    seen.add(key)
                    unique_candidates.append(c)
            
            # Enhanced filtering: remove scams, low quality, dead pairs
            qualified = []
            for c in unique_candidates:
                # Score check
                if c.overall_score < self.min_overall_score:
                    continue
                # Liquidity check
                if c.liquidity_usd < self.min_liquidity_usd:
                    continue
                # Volume check
                if c.volume_24h < self.min_volume_24h:
                    continue
                # Market cap check (low cap only)
                if c.market_cap_usd > self.max_market_cap:
                    continue
                # Scam/rug pull checks
                if self._is_likely_scam(c):
                    logger.warning(f"  🚫 Filtered scam: {c.symbol} ({c.chain})")
                    continue
                # Dead pair check
                if c.transactions_24h < 50:
                    continue
                # Extreme dump check
                if c.price_change_24h < -80:
                    continue
                
                # Classify the trade
                self._classify_trade(c)
                
                # Generate mini-report data
                self._generate_fundamental_report(c)
                
                qualified.append(c)
            
            # Sort by overall score
            qualified.sort(key=lambda x: x.overall_score, reverse=True)
            
            # Take top N
            top_plays = qualified[:limit]
            
            logger.info(f"🎯 Found {len(top_plays)} qualified alpha plays")
            for p in top_plays:
                logger.info(f"  • {p.symbol} ({p.chain}) [{p.trade_type}] - Score: {p.overall_score:.1f} | "
                             f"MC: ${p.market_cap_usd/1e6:.1f}M | Vol: ${p.volume_24h/1e3:.0f}K | Risk: {p.risk_level}")
            
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
            
            # Symbol fallback chain: baseToken.symbol -> quoteToken.symbol -> pair symbol -> truncated address
            symbol = base_token.get('symbol', '') or quote_token.get('symbol', '')
            if not symbol:
                # Try to extract from pairAddress or use a generic name
                addr = base_token.get('address', '') or pair.get('pairAddress', '')
                if addr and len(addr) > 8:
                    symbol = addr[:6].upper()
                else:
                    symbol = 'UNKNOWN'
            
            name = base_token.get('name', '') or quote_token.get('name', symbol) or symbol
            token_address = base_token.get('address') or quote_token.get('address')
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
            
            # Calculate scores (tuned for low-cap DEX tokens)
            volume_score = min(volume_24h / 50_000 * 25, 100)  # $50k vol = 25, $200k = 100
            momentum_score = min(abs(price_change_24h) * 3, 100) if price_change_24h > 0 else 0
            liquidity_score = min(liquidity / 30_000 * 50, 100)  # $30k liq = 50, $60k = 100
            
            technical_score = (volume_score * 0.3 + momentum_score * 0.4 + liquidity_score * 0.3)
            
            # Social/community scoring
            social_score = 45.0 + (price_change_1h * 0.8)  # Baseline + recent hype
            social_score = max(25, min(100, social_score))
            
            # Use actual transaction count as proxy for community
            if transactions_24h > 50:
                community_score = min(transactions_24h / 400 * 30, 100)  # 400 txns = 30, 1300 = 100
            else:
                community_score = 20
            
            fundamental_score = 55.0  # Baseline for low-caps
            
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
            
            # Parse pair creation time if available
            pair_created = pair.get('pairCreatedAt')
            if pair_created:
                try:
                    pair_created_at = datetime.fromtimestamp(pair_created / 1000)
                except:
                    pair_created_at = None
            else:
                pair_created_at = None
            
            # Buy/sell ratio
            buy_sell_ratio = buys / sells if sells > 0 else 1.0
            
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
                price_change_5min=float(pair.get('priceChange', {}).get('m5', 0) or 0),
                holders=transactions_24h,  # proxy for now
                transactions_24h=transactions_24h,
                buys_24h=buys,
                sells_24h=sells,
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
                catalyst=catalyst,
                buy_sell_ratio=buy_sell_ratio,
                pair_created_at=pair_created_at,
                dex_source='dexscreener'
            )
            
        except Exception as e:
            logger.debug(f"Error parsing DexScreener pair: {e}")
            return None
    
    async def _scan_geckoterminal(self, chain_filter: str = None) -> List[AlphaPlayCandidate]:
        """
        Scan GeckoTerminal for trending DEX pools.
        Free API, no key required.
        """
        candidates = []
        chain_map = {
            'sol': 'solana',
            'eth': 'eth',
            'base': 'base',
        }
        
        chains_to_scan = []
        if chain_filter is None:
            chains_to_scan = ['solana', 'eth', 'base']
        elif chain_filter in chain_map:
            chains_to_scan = [chain_map[chain_filter]]
        
        try:
            session = await self._get_session()
            
            for chain_id in chains_to_scan:
                try:
                    # GeckoTerminal trending pools endpoint
                    url = f"https://api.geckoterminal.com/api/v2/networks/{chain_id}/pools?page=1"
                    async with session.get(url, timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()
                            pools = data.get('data', [])
                            
                            for pool in pools[:15]:
                                try:
                                    attrs = pool.get('attributes', {})
                                    token_price = float(attrs.get('base_token_price_usd', 0) or 0)
                                    if token_price == 0:
                                        continue
                                    
                                    # Extract token info
                                    relationships = pool.get('relationships', {})
                                    base_token = relationships.get('base_token', {}).get('data', {})
                                    quote_token = relationships.get('quote_token', {}).get('data', {})
                                    
                                    symbol = base_token.get('symbol', '') or quote_token.get('symbol', '')
                                    if not symbol:
                                        addr = base_token.get('id', '') or quote_token.get('id', '')
                                        if '_' in addr:
                                            symbol = addr.split('_')[-1][:6].upper()
                                        elif addr and len(addr) > 8:
                                            symbol = addr[:6].upper()
                                        else:
                                            symbol = 'UNKNOWN'
                                    token_address = base_token.get('id', '').split('_')[-1] if '_' in base_token.get('id', '') else base_token.get('id', '')
                                    
                                    # Metrics
                                    market_cap = float(attrs.get('market_cap_usd', 0) or 0)
                                    if market_cap == 0:
                                        # Estimate from price and FDV
                                        fdv = float(attrs.get('fdv_usd', 0) or 0)
                                        market_cap = fdv * 0.6  # rough estimate
                                    
                                    liquidity = float(attrs.get('reserve_in_usd', 0) or 0)
                                    volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0) or 0)
                                    
                                    price_change_24h = float(attrs.get('price_change_percentage', {}).get('h24', 0) or 0)
                                    price_change_1h = float(attrs.get('price_change_percentage', {}).get('h1', 0) or 0)
                                    price_change_5min = float(attrs.get('price_change_percentage', {}).get('m5', 0) or 0)
                                    
                                    txns_24h = attrs.get('transactions', {}).get('h24', {})
                                    buys = txns_24h.get('buys', 0) or 0
                                    sells = txns_24h.get('sells', 0) or 0
                                    transactions_24h = buys + sells
                                    
                                    # Calculate scores (tuned for low-cap DEX tokens)
                                    volume_score = min(volume_24h / 50_000 * 25, 100)
                                    momentum_score = min(abs(price_change_24h) * 3, 100) if price_change_24h > 0 else 0
                                    liquidity_score = min(liquidity / 30_000 * 50, 100)
                                    
                                    # Recent momentum bonus
                                    recent_bonus = 0
                                    if price_change_5min > 5:
                                        recent_bonus = 10
                                    
                                    technical_score = (volume_score * 0.3 + momentum_score * 0.4 + liquidity_score * 0.3) + recent_bonus
                                    technical_score = min(100, technical_score)
                                    
                                    social_score = 45.0 + (price_change_1h * 0.8)
                                    social_score = max(25, min(100, social_score))
                                    
                                    if transactions_24h > 50:
                                        community_score = min(transactions_24h / 400 * 30, 100)
                                    else:
                                        community_score = 20
                                    
                                    fundamental_score = 55.0
                                    
                                    overall_score = (
                                        technical_score * 0.35 +
                                        social_score * 0.30 +
                                        community_score * 0.20 +
                                        fundamental_score * 0.15
                                    )
                                    
                                    # Links — map GeckoTerminal chain_id to our internal chain
                                    gt_chain_map = {
                                        'solana': 'sol',
                                        'ethereum': 'eth',
                                        'base': 'base',
                                    }
                                    detected_chain = gt_chain_map.get(chain_id, chain_filter or 'sol')
                                    pool_addr = pool.get('id', '').split('_')[-1] if '_' in pool.get('id', '') else pool.get('id', '')
                                    dex_url = f"https://www.geckoterminal.com/{chain_id}/pools/{pool_addr}"
                                    chart_url = dex_url
                                    buy_url = self._generate_buy_link(detected_chain, token_address, symbol)
                                    
                                    # Detect catalyst
                                    catalyst = self._detect_catalyst(price_change_24h, price_change_1h, volume_24h, transactions_24h)
                                    
                                    # Red flags
                                    red_flags = self._check_red_flags_gecko(buys, sells, liquidity, volume_24h, price_change_24h)
                                    
                                    # Buy/sell ratio
                                    buy_sell_ratio = buys / sells if sells > 0 else 1.0
                                    
                                    candidates.append(AlphaPlayCandidate(
                                        symbol=symbol,
                                        name=attrs.get('name', symbol),
                                        chain=detected_chain,
                                        token_address=token_address,
                                        pair_address=pool_addr,
                                        price_usd=token_price,
                                        market_cap_usd=market_cap,
                                        liquidity_usd=liquidity,
                                        volume_24h=volume_24h,
                                        price_change_24h=price_change_24h,
                                        price_change_1h=price_change_1h,
                                        price_change_5min=price_change_5min,
                                        holders=transactions_24h,  # proxy
                                        transactions_24h=transactions_24h,
                                        buys_24h=buys,
                                        sells_24h=sells,
                                        social_score=social_score,
                                        community_score=community_score,
                                        technical_score=technical_score,
                                        fundamental_score=fundamental_score,
                                        overall_score=overall_score,
                                        dex_url=dex_url,
                                        chart_url=chart_url,
                                        buy_url=buy_url,
                                        description=f"{symbol} - GeckoTerminal trending on {chain_id.upper()}",
                                        red_flags=red_flags,
                                        catalyst=catalyst,
                                        buy_sell_ratio=buy_sell_ratio,
                                        fdv=float(attrs.get('fdv_usd', 0) or 0),
                                        dex_source='geckoterminal'
                                    ))
                                except Exception as e:
                                    logger.debug(f"Error parsing GeckoTerminal pool: {e}")
                                    continue
                        else:
                            logger.warning(f"GeckoTerminal returned status {response.status} for {chain_id}")
                            
                except Exception as e:
                    logger.warning(f"GeckoTerminal scan error for {chain_id}: {e}")
                    continue
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in GeckoTerminal scan: {e}")
            return []
    
    async def _scan_dexscreener_gainers(self, chain_filter: str = None) -> List[AlphaPlayCandidate]:
        """
        Scan DexScreener top gainers for momentum plays.
        Uses the token profiles API to find trending tokens.
        """
        candidates = []
        
        try:
            session = await self._get_session()
            
            # Use DexScreener token profiles (trending)
            url = "https://api.dexscreener.com/token-profiles/latest/v1"
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    profiles = data if isinstance(data, list) else data.get('profiles', [])
                    
                    for profile in profiles[:15]:
                        try:
                            token = profile.get('tokenAddress', {})
                            chain = token.get('chainId', 'unknown').lower()
                            if chain in ['solana', 'sol']:
                                chain = 'sol'
                            elif chain in ['ethereum', 'eth']:
                                chain = 'eth'
                            elif chain in ['base']:
                                chain = 'base'
                            else:
                                continue
                            
                            # Skip if chain filter doesn't match
                            if chain_filter and chain != chain_filter:
                                continue
                            
                            symbol = token.get('tokenSymbol', 'UNKNOWN')
                            token_address = token.get('tokenAddress', '')
                            
                            # Get links
                            links = profile.get('links', [])
                            dex_url = next((l['url'] for l in links if l.get('type') == 'dexscreener'), f"https://dexscreener.com/{chain}/{token_address}")
                            
                            # Get description
                            description = profile.get('description', '')
                            
                            # Try to get price data from the profile or skip
                            # Token profiles don't have price data, so we need to enrich
                            # For now, skip ones without price (will be caught by DexScreener search)
                            continue
                            
                        except Exception as e:
                            logger.debug(f"Error parsing token profile: {e}")
                            continue
            
            return candidates
            
        except Exception as e:
            logger.warning(f"DexScreener gainers scan error: {e}")
            return []
    
    def _is_likely_scam(self, candidate: AlphaPlayCandidate) -> bool:
        """
        Advanced scam/rug pull detection for DEX tokens.
        Returns True if likely a scam.
        """
        flags = 0
        
        # Check 1: Extreme sell pressure (>70% sells)
        if candidate.sells_24h > 0 and candidate.buys_24h > 0:
            sell_ratio = candidate.sells_24h / (candidate.buys_24h + candidate.sells_24h)
            if sell_ratio > 0.7:
                flags += 1
        
        # Check 2: Very high price with no volume (honeypot indicator)
        if candidate.price_usd > 1.0 and candidate.volume_24h < 1000:
            flags += 1
        
        # Check 3: Market cap way higher than liquidity (canary)
        if candidate.market_cap_usd > 0 and candidate.liquidity_usd > 0:
            if candidate.market_cap_usd / candidate.liquidity_usd > 100:
                flags += 1
        
        # Check 4: Created very recently + already huge gains (likely pump & dump)
        if candidate.pair_created_at:
            hours_since_creation = (datetime.utcnow() - candidate.pair_created_at).total_seconds() / 3600
            if hours_since_creation < 2 and candidate.price_change_24h > 500:
                flags += 1
        
        # Check 5: No real trading activity but price is up (wash trading indicator)
        if candidate.transactions_24h < 100 and candidate.price_change_24h > 50:
            flags += 1
        
        # Check 6: FDV suspiciously high vs market cap (massive unlock risk)
        if candidate.fdv > 0 and candidate.market_cap_usd > 0:
            if candidate.fdv / candidate.market_cap_usd > 10:
                flags += 1
        
        return flags >= 2  # 2+ red flags = likely scam
    
    def _classify_trade(self, candidate: AlphaPlayCandidate):
        """
        Classify the alpha play as day trade, swing, or fundamental.
        Sets trade_type, time_frame, and risk_level.
        """
        mc = candidate.market_cap_usd
        vol = candidate.volume_24h
        liq = candidate.liquidity_usd
        change_24h = candidate.price_change_24h
        change_1h = candidate.price_change_1h
        txns = candidate.transactions_24h
        
        # Risk level first
        if mc < 1_000_000 or liq < 100_000:
            candidate.risk_level = 'degen'
        elif mc < 10_000_000 or liq < 300_000:
            candidate.risk_level = 'high'
        elif mc < 50_000_000:
            candidate.risk_level = 'medium'
        else:
            candidate.risk_level = 'low'
        
        # Trade classification
        # Day trade: High momentum, high volume, short timeframe
        if (change_1h > 10 or change_24h > 30) and txns > 2000 and vol > 500_000:
            candidate.trade_type = 'day_trade'
            candidate.time_frame = '1-4h'
        
        # Swing: Moderate momentum, good liquidity, medium timeframe
        elif (change_24h > 10 or change_24h < -10) and liq > 200_000 and vol > 200_000:
            candidate.trade_type = 'swing'
            candidate.time_frame = '4-24h'
        
        # Fundamental: Lower momentum but strong structure, longer hold
        elif mc > 5_000_000 and liq > 500_000 and vol > 100_000:
            candidate.trade_type = 'fundamental'
            candidate.time_frame = '1-3d'
        
        # Default to swing if unclear
        else:
            candidate.trade_type = 'swing'
            candidate.time_frame = '4-24h'
    
    def _generate_fundamental_report(self, candidate: AlphaPlayCandidate):
        """
        Generate a comprehensive data-driven mini-report.
        Covers technical, fundamental, community/hype with concrete conclusions.
        """
        mc = candidate.market_cap_usd
        vol = candidate.volume_24h
        liq = candidate.liquidity_usd
        change_24h = candidate.price_change_24h
        change_1h = candidate.price_change_1h
        txns = candidate.transactions_24h
        buys = candidate.buys_24h
        sells = candidate.sells_24h
        bsr = candidate.buy_sell_ratio
        
        # --- NARRATIVE: Ecosystem + driver tags ---
        narratives = []
        if candidate.chain == 'sol':
            narratives.append("Solana ecosystem")
        elif candidate.chain == 'base':
            narratives.append("Base ecosystem")
        elif candidate.chain == 'eth':
            narratives.append("Ethereum ecosystem")
        if change_24h > 50:
            narratives.append("viral momentum")
        if vol > liq * 5:
            narratives.append("high velocity trading")
        if txns > 5000:
            narratives.append("strong community activity")
        if bsr > 1.3:
            narratives.append("buy pressure dominant")
        candidate.narrative = " + ".join(narratives) if narratives else "Emerging low-cap opportunity"
        
        # --- WHY TRENDING: Specific data points ---
        reasons = []
        if change_1h > 15:
            reasons.append(f"🔥 Momentum: +{change_1h:.1f}% in 1h — breakout underway")
        elif change_1h > 5:
            reasons.append(f"📈 Recent push: +{change_1h:.1f}% in 1h — building momentum")
        elif change_24h > 30:
            reasons.append(f"🚀 Daily surge: +{change_24h:.1f}% in 24h — strong directional move")
        elif change_24h > 10:
            reasons.append(f"📊 Steady climb: +{change_24h:.1f}% in 24h — sustained interest")
        
        vol_vs_liq = vol / liq if liq > 0 else 0
        if vol_vs_liq > 10:
            reasons.append(f"💰 Volume/Liquidity ratio: {vol_vs_liq:.1f}x — extremely high turnover (speculative but explosive)")
        elif vol_vs_liq > 3:
            reasons.append(f"💰 Volume/Liquidity ratio: {vol_vs_liq:.1f}x — strong turnover indicating real demand")
        
        if txns > 5000:
            reasons.append(f"🤝 Community: {txns:,} transactions in 24h — very active holder base")
        elif txns > 1000:
            reasons.append(f"🤝 Community: {txns:,} transactions in 24h — healthy activity")
        
        if buys > 0 and sells > 0:
            if bsr > 1.5:
                reasons.append(f"🟢 Buy/Sell: {bsr:.2f}x — clear accumulation, sellers being absorbed")
            elif bsr > 1.1:
                reasons.append(f"🟡 Buy/Sell: {bsr:.2f}x — slight buy edge, neutral to bullish")
            elif bsr < 0.8:
                reasons.append(f"🔴 Buy/Sell: {bsr:.2f}x — more sellers than buyers, caution")
        
        # Liquidity health
        if liq < 50_000:
            reasons.append(f"⚠️ Thin liquidity: ${liq/1e3:.0f}K — high slippage risk on large orders")
        elif liq < 150_000:
            reasons.append(f"⚠️ Low liquidity: ${liq/1e3:.0f}K — manageable for small positions only")
        elif liq > 500_000:
            reasons.append(f"✅ Solid liquidity: ${liq/1e3:.0f}K — decent for entry/exit")
        
        candidate.why_trending = "\n".join(reasons) if reasons else "Early accumulation with limited on-chain data"
        
        # --- SHORT TERM (1-3 days): Data-driven conclusion ---
        st_parts = []
        
        # Technical short term
        if change_1h > 15 and change_24h > 30:
            st_parts.append(f"TECHNICAL: Parabolic short-term move (+{change_1h:.1f}% 1h, +{change_24h:.1f}% 24h). Momentum favors continuation but risk of sharp pullback rises above +50% daily. Consider DCA entry or wait for 10-20% pullback.")
        elif change_24h > 20 and change_1h > 0:
            st_parts.append(f"TECHNICAL: Strong daily trend (+{change_24h:.1f}%) with hourly confirmation (+{change_1h:.1f}%). Pullback to previous resistance-turned-support likely entry zone.")
        elif change_24h > 0 and vol > 200_000:
            st_parts.append(f"TECHNICAL: Positive daily (+{change_24h:.1f}%) with volume backing. If ${vol/1e3:.0f}K vol holds, continuation probable within 24-48h.")
        elif change_24h < -15:
            st_parts.append(f"TECHNICAL: Down {change_24h:.1f}% in 24h. Possible dead cat bounce if volume dries up. High risk mean reversion only.")
        else:
            st_parts.append(f"TECHNICAL: Range-bound (+{change_24h:.1f}% 24h). No clear breakout yet. Wait for volume confirmation above ${vol/1e3:.0f}K average.")
        
        # Community short term
        if txns > 5000 and bsr > 1.2:
            st_parts.append(f"COMMUNITY: {txns:,} txns with {bsr:.2f}x buy ratio = active community buying dips. Short-term support likely strong.")
        elif txns > 1000 and bsr > 1.0:
            st_parts.append(f"COMMUNITY: Moderate activity ({txns:,} txns, {bsr:.2f}x B/S). Community engaged but not euphoric — sustainable.")
        elif txns < 500:
            st_parts.append(f"COMMUNITY: Low activity ({txns:,} txns). Thin community = price can move fast both ways on small orders.")
        
        # Liquidity short term
        if vol_vs_liq > 8:
            st_parts.append(f"LIQUIDITY: Volume is {vol_vs_liq:.1f}x liquidity — this is a hot money pump. Exit liquidity may vanish quickly. In-and-out play only.")
        elif vol_vs_liq > 3:
            st_parts.append(f"LIQUIDITY: Volume {vol_vs_liq:.1f}x liquidity shows real demand. Manageable for 1-3 day swing if momentum holds.")
        else:
            st_parts.append(f"LIQUIDITY: Volume {vol_vs_liq:.1f}x liquidity — low turnover. Price moves will be choppy. Patience required.")
        
        candidate.short_term_potential = "\n\n".join(st_parts)
        
        # --- LONG TERM (1-4 weeks): Data-driven conclusion ---
        lt_parts = []
        
        # Fundamental long term
        if mc < 1_000_000 and liq > 30_000:
            lt_parts.append(f"FUNDAMENTAL: Micro-cap (${mc/1e6:.2f}M MC, ${liq/1e3:.0f}K liq). If this catches narrative, 10-50x is historically possible for micros. But 90% of micro-caps die within 30 days. Position size must reflect this.")
        elif mc < 5_000_000 and liq > 100_000:
            lt_parts.append(f"FUNDAMENTAL: Small-cap (${mc/1e6:.2f}M MC). 3-10x achievable if it graduates from 'unknown' to 'known' within ecosystem. Liquidity ${liq/1e3:.0f}K is sufficient for gradual growth.")
        elif mc < 20_000_000:
            lt_parts.append(f"FUNDAMENTAL: Low-cap (${mc/1e6:.2f}M MC). 2-5x if ecosystem tailwinds continue and holder base grows. More realistic than micro-cap moonshots.")
        else:
            lt_parts.append(f"FUNDAMENTAL: Mid-cap (${mc/1e6:.2f}M MC). 1.5-3x potential with lower volatility. Better for swing holds than degen plays.")
        
        # Community/hype long term
        if txns > 5000 and bsr > 1.3:
            lt_parts.append(f"HYPE: {txns:,} daily txns + {bsr:.2f}x buy pressure = strong community conviction. Best predictor of 1-4 week hold success. Watch for txn decline as early exit signal.")
        elif txns > 2000:
            lt_parts.append(f"HYPE: {txns:,} daily txns = decent community. Hype can sustain 1-2 weeks if volume doesn't collapse. Monitor txn count closely.")
        else:
            lt_parts.append(f"HYPE: {txns:,} daily txns = thin community. Without new buyer influx, price will bleed. Only viable as a 1-3 day play, not a 1-4 week hold.")
        
        # Risk framework
        if candidate.risk_level == 'degen':
            lt_parts.append(f"RISK: DEGEN rated. Treat as lottery ticket. 50-80% drawdowns are normal. Only risk what you can lose entirely. Set alerts for -30% from entry and reassess.")
        elif candidate.risk_level == 'high':
            lt_parts.append(f"RISK: HIGH. Expect 30-50% drawdowns. Use strict stop loss. If volume drops 50% from current, exit immediately regardless of price.")
        elif candidate.risk_level == 'medium':
            lt_parts.append(f"RISK: MEDIUM. More forgiving entry. Still use stop loss. If ${vol/1e3:.0f}K volume drops below ${(vol*0.4)/1e3:.0f}K, momentum is gone.")
        else:
            lt_parts.append(f"RISK: LOW (for low-cap). Relatively safer hold. Still expect 15-25% volatility.")
        
        candidate.long_term_potential = "\n\n".join(lt_parts)
    
    def _check_red_flags_gecko(self, buys: int, sells: int, liquidity: float, 
                                volume: float, price_change: float) -> List[str]:
        """Check red flags from GeckoTerminal data"""
        flags = []
        
        if sells > buys * 2 and sells > 100:
            flags.append("⚠️ Heavy selling pressure")
        
        if liquidity < 100_000:
            flags.append("⚠️ Low liquidity - high slippage")
        
        if price_change < -30:
            flags.append("⚠️ Down -30% in 24h")
        
        if volume < 50_000:
            flags.append("⚠️ Low volume")
        
        if buys + sells < 50:
            flags.append("⚠️ Very few transactions")
        
        return flags
    
    async def _scan_social_sentiment(self, chain_filter: str = None) -> List[AlphaPlayCandidate]:
        """
        Scan social media for trending low-cap mentions.
        Note: Placeholder - would use Twitter/X API or LunarCrush in production.
        """
        return []
    
    def _generate_dex_links(self, chain: str, token_address: Optional[str], 
                           pair_address: Optional[str], symbol: str) -> tuple:
        """Generate DEX trading links for the token"""
        
        if chain == 'sol':
            dex_url = f"https://dexscreener.com/solana/{pair_address}" if pair_address else f"https://dexscreener.com/solana/{token_address}" if token_address else "https://dexscreener.com/solana"
            chart_url = f"https://www.geckoterminal.com/solana/pools/{pair_address}" if pair_address else f"https://www.geckoterminal.com/so/pools/{token_address}" if token_address else "https://www.geckoterminal.com"
            buy_url = self._generate_buy_link('sol', token_address, symbol)
                
        elif chain == 'eth':
            dex_url = f"https://dexscreener.com/ethereum/{pair_address}" if pair_address else f"https://dexscreener.com/ethereum/{token_address}" if token_address else "https://dexscreener.com/ethereum"
            chart_url = f"https://www.geckoterminal.com/eth/pools/{pair_address}" if pair_address else f"https://www.geckoterminal.com/eth/pools/{token_address}" if token_address else "https://www.geckoterminal.com"
            buy_url = self._generate_buy_link('eth', token_address, symbol)
                
        elif chain == 'base':
            dex_url = f"https://dexscreener.com/base/{pair_address}" if pair_address else f"https://dexscreener.com/base/{token_address}" if token_address else "https://dexscreener.com/base"
            chart_url = f"https://www.geckoterminal.com/base/pools/{pair_address}" if pair_address else f"https://www.geckoterminal.com/base/pools/{token_address}" if token_address else "https://www.geckoterminal.com"
            buy_url = self._generate_buy_link('base', token_address, symbol)
        else:
            dex_url = "https://dexscreener.com"
            chart_url = "https://www.geckoterminal.com"
            buy_url = "https://jup.ag"
        
        return dex_url, chart_url, buy_url
    
    def _generate_buy_link(self, chain: str, token_address: Optional[str],
                           symbol: str) -> str:
        """
        Generate direct DEX buy/swap links.

        Solana: Jupiter (with optional referral via JUPITER_REFERRAL_CODE)
        Ethereum/Base: Uniswap (no referral program exists)
        """
        jupiter_ref = getattr(settings, 'JUPITER_REFERRAL_CODE', None)

        if chain == 'sol':
            # Jupiter swap for Solana - referral program is real
            if not token_address:
                url = f"https://jup.ag/swap/USDC-{symbol}"
            else:
                url = f"https://jup.ag/swap/USDC-{token_address}"
            if jupiter_ref:
                url += f"?referrer={jupiter_ref}"
            return url

        elif chain == 'eth':
            # Uniswap mainnet - no referral program exists
            if token_address:
                return f"https://app.uniswap.org/#/swap?outputCurrency={token_address}&chain=mainnet"
            return "https://app.uniswap.org"

        elif chain == 'base':
            # Uniswap Base - no referral program exists
            if token_address:
                return f"https://app.uniswap.org/#/swap?outputCurrency={token_address}&chain=base"
            return "https://app.uniswap.org/?chain=base"

        else:
            # Default to Jupiter for unknown chains
            if token_address:
                url = f"https://jup.ag/swap/USDC-{token_address}"
            else:
                url = f"https://jup.ag/swap/USDC-{symbol}"
            if jupiter_ref:
                url += f"?referrer={jupiter_ref}"
            return url
    
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
