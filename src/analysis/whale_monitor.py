"""
CRYPTO PULSE SIGNALS - Whale Alert Monitor
Detects large trades and unusual exchange activity without paid APIs.
Uses Binance public trade streams and volume anomaly detection.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from dataclasses import dataclass, field
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WhaleAlert:
    """A single whale trade event."""
    symbol: str
    side: str  # 'buy' | 'sell'
    quantity: float
    price: float
    usd_value: float
    timestamp: datetime
    is_market_order: bool = False
    exchange: str = 'binance'


@dataclass
class WhaleSummary:
    """Aggregated whale activity for a symbol."""
    symbol: str
    total_buys_usd: float = 0.0
    total_sells_usd: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    largest_single_trade_usd: float = 0.0
    alerts: List[WhaleAlert] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def net_flow_usd(self) -> float:
        return self.total_buys_usd - self.total_sells_usd

    @property
    def is_accumulating(self) -> bool:
        return self.net_flow_usd > 0 and self.total_buys_usd > self.total_sells_usd * 2

    @property
    def is_distributing(self) -> bool:
        return self.net_flow_usd < 0 and self.total_sells_usd > self.total_buys_usd * 2


class WhaleMonitor:
    """
    Monitors public trade data for whale activity.
    Free-tier: uses Binance public API (no API key required).
    """

    # Thresholds (USD) for what counts as a "whale" trade
    WHALE_THRESHOLD_USD = 50_000       # Single trade > $50k
    MEGA_WHALE_THRESHOLD_USD = 500_000   # Single trade > $500k

    # Poll interval (seconds) — keep it conservative to avoid rate limits
    DEFAULT_POLL_INTERVAL = 60

    def __init__(self):
        self.cache: Dict[str, WhaleSummary] = {}
        self.last_polls: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(minutes=3)
        self.session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._symbols_to_watch: set = set()

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )

    async def fetch_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Fetch recent public trades from Binance."""
        await self._ensure_session()
        # Binance uses PEPEUSDT not PEPE/USDT
        clean_symbol = symbol.replace('/', '')
        url = f"https://api.binance.com/api/v3/trades?symbol={clean_symbol}&limit={limit}"

        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    logger.warning(f"Whale monitor rate limited for {symbol}")
                else:
                    logger.debug(f"Binance trades API returned {resp.status} for {symbol}")
        except Exception as e:
            logger.debug(f"Error fetching trades for {symbol}: {e}")

        return []

    async def check_symbol(self, symbol: str, price: float = 0.0) -> Optional[WhaleSummary]:
        """
        Check a single symbol for whale activity.
        Returns WhaleSummary if activity detected, else None.
        """
        # Check cache first
        cached = self.cache.get(symbol)
        last_poll = self.last_polls.get(symbol)
        if cached and last_poll and (datetime.utcnow() - last_poll) < self.cache_ttl:
            return cached if cached.total_buys_usd > 0 or cached.total_sells_usd > 0 else None

        trades = await self.fetch_recent_trades(symbol)
        if not trades:
            return None

        if price <= 0:
            # Derive price from latest trade
            price = float(trades[0].get('price', 0))

        summary = WhaleSummary(symbol=symbol)

        for t in trades:
            qty = float(t.get('qty', 0))
            p = float(t.get('price', price))
            usd = qty * p
            is_buyer_market = t.get('isBuyerMaker', False) is False
            side = 'buy' if is_buyer_market else 'sell'

            if usd >= self.WHALE_THRESHOLD_USD:
                alert = WhaleAlert(
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    price=p,
                    usd_value=usd,
                    timestamp=datetime.utcnow(),
                    is_market_order=True,
                    exchange='binance'
                )
                summary.alerts.append(alert)

                if side == 'buy':
                    summary.total_buys_usd += usd
                    summary.buy_count += 1
                else:
                    summary.total_sells_usd += usd
                    summary.sell_count += 1

                if usd > summary.largest_single_trade_usd:
                    summary.largest_single_trade_usd = usd

        self.cache[symbol] = summary
        self.last_polls[symbol] = datetime.utcnow()

        # Only return if we found actual whale trades
        if summary.alerts:
            tier = "MEGA" if summary.largest_single_trade_usd >= self.MEGA_WHALE_THRESHOLD_USD else ""
            logger.info(
                f"🐋 Whale alert {tier} for {symbol}: "
                f"${summary.total_buys_usd:,.0f} buy / ${summary.total_sells_usd:,.0f} sell "
                f"({len(summary.alerts)} trades)"
            )
            return summary

        return None

    async def check_multiple(self, symbols: List[str], price_map: Dict[str, float] = None) -> Dict[str, WhaleSummary]:
        """Check whale activity for multiple symbols in parallel."""
        price_map = price_map or {}
        tasks = [self.check_symbol(s, price_map.get(s, 0.0)) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out = {}
        for sym, res in zip(symbols, results):
            if isinstance(res, WhaleSummary):
                out[sym] = res
        return out

    def get_cached_summary(self, symbol: str) -> Optional[WhaleSummary]:
        """Get cached whale summary without fetching."""
        cached = self.cache.get(symbol)
        last_poll = self.last_polls.get(symbol)
        if cached and last_poll and (datetime.utcnow() - last_poll) < self.cache_ttl:
            return cached
        return None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
