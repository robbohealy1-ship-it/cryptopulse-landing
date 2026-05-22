"""
MEXC API client — READ-ONLY
Fetches spot account balance, open orders, and trade history.
Uses HMAC-SHA256 signature authentication.
"""
import asyncio
import aiohttp
import hashlib
import hmac
import logging
import urllib.parse
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MEXCClient:
    """Read-only MEXC spot API client."""

    BASE_URL = "https://api.mexc.com"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
    ):
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-MEXC-APIKEY": self.api_key}
            )
        return self._session

    def _sign(self, query_string: str) -> str:
        """Create HMAC-SHA256 signature."""
        return hmac.new(
            self.api_secret,
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def _request(self, method: str, path: str, params: Optional[Dict] = None, signed: bool = False) -> Any:
        """Make an authenticated request to MEXC API."""
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"
        
        query = urllib.parse.urlencode(params or {})
        if signed:
            query += f"&timestamp={int(datetime.utcnow().timestamp() * 1000)}"
            signature = self._sign(query)
            query += f"&signature={signature}"
        
        full_url = f"{url}?{query}" if query else url
        
        try:
            async with session.request(method, full_url) as resp:
                if resp.status == 401:
                    logger.error("MEXC API: Unauthorized — check API key/secret")
                    return None
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(f"MEXC API error {resp.status}: {text}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"MEXC API request failed: {e}")
            return None

    # ─── READ-ONLY METHODS ───

    async def get_account(self) -> Optional[Dict]:
        """Fetch spot account balances (non-zero only)."""
        data = await self._request("GET", "/api/v3/account", signed=True)
        if not data:
            return None
        
        balances = []
        total_usdt = 0.0
        for b in data.get("balances", []):
            free = float(b.get("free", 0))
            locked = float(b.get("locked", 0))
            total = free + locked
            if total > 0:
                balances.append({
                    "asset": b["asset"],
                    "free": free,
                    "locked": locked,
                    "total": total,
                })
        
        return {
            "balances": balances,
            "total_usdt": total_usdt,  # Approximate — would need price lookup for non-USDT
            "account_type": "spot",
            "broker": "MEXC",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Fetch all open orders (limit orders not yet filled)."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = await self._request("GET", "/api/v3/openOrders", params=params, signed=True)
        if not data:
            return []
        
        orders = []
        for o in data:
            orders.append({
                "symbol": o.get("symbol"),
                "order_id": o.get("orderId"),
                "side": o.get("side"),  # BUY or SELL
                "type": o.get("type"),  # LIMIT, MARKET, etc.
                "price": float(o.get("price", 0)),
                "quantity": float(o.get("origQty", 0)),
                "filled": float(o.get("executedQty", 0)),
                "status": o.get("status"),  # NEW, PARTIALLY_FILLED, etc.
                "time": o.get("time"),
            })
        return orders

    async def get_my_trades(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Fetch recent filled trades / order history."""
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        data = await self._request("GET", "/api/v3/myTrades", params=params, signed=True)
        if not data:
            return []
        
        trades = []
        for t in data:
            trades.append({
                "symbol": t.get("symbol"),
                "trade_id": t.get("id"),
                "order_id": t.get("orderId"),
                "side": "LONG" if t.get("isBuyer") else "SHORT",
                "price": float(t.get("price", 0)),
                "quantity": float(t.get("qty", 0)),
                "quote_qty": float(t.get("quoteQty", 0)),
                "commission": float(t.get("commission", 0)),
                "commission_asset": t.get("commissionAsset"),
                "time": t.get("time"),
                "is_maker": t.get("isMaker", False),
            })
        return trades

    async def get_all_data(self) -> Dict[str, Any]:
        """Fetch account + open orders + recent trades in one call."""
        account, orders, trades = await asyncio.gather(
            self.get_account(),
            self.get_open_orders(),
            self.get_my_trades(limit=50),
        )
        return {
            "account": account,
            "open_orders": orders,
            "trades": trades,
            "source": "mexc",
            "label": "MEXC Personal",
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
