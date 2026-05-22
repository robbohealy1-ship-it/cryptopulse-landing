"""
cTrader Open API client — READ-ONLY
Supports BEM Funding and any cTrader broker.
Fetches balance, positions, and order history.
"""
import asyncio
import aiohttp
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CTraderClient:
    """Read-only cTrader Open API client."""

    # cTrader demo (sandbox) and live servers
    SERVERS = {
        "demo": "https://openapi.ctrader.com",
        "live": "https://openapi.ctrader.com",
    }

    def __init__(
        self,
        access_token: str,
        account_id: str,
        server: str = "live",
    ):
        self.access_token = access_token
        self.account_id = account_id
        self.base_url = self.SERVERS.get(server, self.SERVERS["live"])
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
        return self._session

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an authenticated request to cTrader Open API."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        try:
            async with session.request(method, url, **kwargs) as resp:
                if resp.status == 401:
                    logger.error("cTrader API: Unauthorized — check access token")
                    return None
                if resp.status == 404:
                    logger.error(f"cTrader API: Not found — {path}")
                    return None
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(f"cTrader API error {resp.status}: {text}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"cTrader API request failed: {e}")
            return None

    # ─── READ-ONLY METHODS ───

    async def get_account_summary(self) -> Optional[Dict]:
        """Fetch account balance and margin info."""
        data = await self._request("GET", f"/v1/accounts/{self.account_id}")
        if not data:
            return None
        return {
            "balance": data.get("balance"),
            "equity": data.get("equity"),
            "margin_used": data.get("marginUsed"),
            "margin_available": data.get("freeMargin"),
            "unrealized_pnl": data.get("unrealizedPnL"),
            "currency": data.get("currency", "USD"),
            "account_id": self.account_id,
            "broker": "cTrader (BEM Funding)",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_positions(self) -> List[Dict]:
        """Fetch all open positions with unrealized P&L."""
        data = await self._request("GET", f"/v1/accounts/{self.account_id}/positions")
        if not data or "data" not in data:
            return []
        positions = []
        for p in data.get("data", []):
            positions.append({
                "symbol": p.get("symbolName", "UNKNOWN"),
                "direction": "LONG" if p.get("tradeSide") == "BUY" else "SHORT",
                "entry_price": p.get("entryPrice"),
                "current_price": p.get("currentPrice"),
                "volume": p.get("volume"),
                "unrealized_pnl": p.get("unrealizedPnL"),
                "realized_pnl": p.get("realizedPnL", 0),
                "swap": p.get("swap", 0),
                "commission": p.get("commission", 0),
                "open_time": p.get("openTime"),
                "position_id": p.get("positionId"),
            })
        return positions

    async def get_orders(self, status: str = "FILLED", limit: int = 50) -> List[Dict]:
        """Fetch recent closed/filled orders for trade history."""
        params = {"accountId": self.account_id, "status": status, "limit": limit}
        data = await self._request("GET", "/v1/orders", params=params)
        if not data or "data" not in data:
            return []
        orders = []
        for o in data.get("data", []):
            orders.append({
                "symbol": o.get("symbolName", "UNKNOWN"),
                "direction": "LONG" if o.get("tradeSide") == "BUY" else "SHORT",
                "order_type": o.get("orderType", "MARKET"),
                "status": o.get("status"),
                "volume": o.get("volume"),
                "filled_volume": o.get("filledVolume", 0),
                "price": o.get("price"),
                "average_price": o.get("avgPrice"),
                "realized_pnl": o.get("realizedPnL", 0),
                "commission": o.get("commission", 0),
                "swap": o.get("swap", 0),
                "create_time": o.get("createTime"),
                "fill_time": o.get("fillTime"),
            })
        return orders

    async def get_all_data(self) -> Dict[str, Any]:
        """Fetch account + positions + recent orders in one call."""
        account, positions, orders = await asyncio.gather(
            self.get_account_summary(),
            self.get_positions(),
            self.get_orders(status="FILLED", limit=50),
        )
        return {
            "account": account,
            "positions": positions,
            "orders": orders,
            "source": "ctrader",
            "label": "BEM Funding Challenge",
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
