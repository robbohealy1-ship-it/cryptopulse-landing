"""
PRO FEATURES ENGINE
Handles all premium tier features:
- Whale alerts (quarterly+)
- Educational content (quarterly+)
- Priority support flagging (quarterly+)
- Custom price alerts (all VIP)
- VIP-only giveaways (lifetime)
- Bonus market reports (quarterly+)
"""

import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============== 1. WHALE ALERT SYSTEM ==============

class WhaleAlertSystem:
    """Monitor large orders/liquidations on Binance and alert Pro+ members"""

    def __init__(self, channel_publisher=None, admin_notification=None):
        self.channel_publisher = channel_publisher
        self._notify_admin = admin_notification
        self.target_channel_id = getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None)  # Whale intel → free channel
        self.whale_threshold_usd = getattr(settings, 'WHALE_THRESHOLD_USD', 1000000)  # Only $1M+ events
        self.enabled = getattr(settings, 'ENABLE_WHALE_ALERTS', True)

    async def scan_for_whale_activity(self):
        """Check Binance for large liquidations and unusual volume"""
        if not self.enabled:
            return

        try:
            # Fetch recent liquidations from Binance public API
            liqs = await self._fetch_liquidations()
            if liqs:
                for liq in liqs:
                    usd_value = liq.get('usd_value', 0)
                    if usd_value >= self.whale_threshold_usd:
                        await self._post_whale_alert(liq)

            # Fetch unusual volume spikes (reported as whale alerts)
            volume_spikes = await self._fetch_volume_spikes()
            if volume_spikes:
                for spike in volume_spikes:
                    await self._post_whale_volume_alert(spike)

        except Exception as e:
            logger.error(f"Whale scan error: {e}")

    async def _fetch_liquidations(self) -> List[Dict]:
        """Fetch recent liquidations from Binance"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://fapi.binance.com/fapi/v1/forceOrders"
                async with session.get(url, params={'limit': 100}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for item in data:
                            qty = float(item.get('origQty', 0))
                            price = float(item.get('avgPrice', 0))
                            usd = qty * price
                            if usd >= self.whale_threshold_usd:
                                results.append({
                                    'symbol': item.get('symbol', 'UNKNOWN'),
                                    'side': item.get('side', 'SELL'),
                                    'usd_value': usd,
                                    'price': price,
                                    'qty': qty,
                                    'type': 'liquidation'
                                })
                        return results
        except Exception as e:
            logger.debug(f"Liquidation fetch failed: {e}")
        return []

    async def _fetch_volume_spikes(self) -> List[Dict]:
        """Detect 24h volume spikes > 3x average"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        spikes = []
                        for item in data:
                            vol = float(item.get('volume', 0))
                            quote_vol = float(item.get('quoteVolume', 0))
                            price_change = float(item.get('priceChangePercent', 0))
                            symbol = item.get('symbol', '')
                            # Focus on USDT pairs with significant volume
                            if symbol.endswith('USDT') and quote_vol > 50000000 and abs(price_change) > 8:
                                spikes.append({
                                    'symbol': symbol,
                                    'volume_24h': quote_vol,
                                    'price_change': price_change,
                                    'type': 'volume_spike'
                                })
                        # Sort by volume, take top 3
                        spikes.sort(key=lambda x: x['volume_24h'], reverse=True)
                        return spikes[:3]
        except Exception as e:
            logger.debug(f"Volume spike fetch failed: {e}")
        return []

    async def _post_whale_alert(self, liq: Dict):
        """Post major liquidation alert to free channel as market intel"""
        if not self.channel_publisher or not self.target_channel_id:
            return

        emoji = "🐋" if liq['usd_value'] > 1000000 else "🐟"
        side_emoji = "🔴" if liq['side'] == 'SELL' else "🟢"

        text = (
            f"{emoji} <b>WHALE ALERT</b> {emoji}\n\n"
            f"<b>{liq['symbol']}</b> Liquidation\n"
            f"{side_emoji} Side: {liq['side']}\n"
            f"💰 Value: ${liq['usd_value']:,.0f}\n"
            f"📊 Price: ${liq['price']:,.4f}\n\n"
            f"⚠️ Large liquidations can create short-term volatility.\n"
            f"💎 Pro members get these alerts in real-time."
        )

        try:
            await self.channel_publisher.bot.send_message(
                chat_id=self.target_channel_id,
                text=text,
                parse_mode='HTML'
            )
            logger.info(f"🐋 Whale alert posted to free: {liq['symbol']} ${liq['usd_value']:,.0f}")
        except Exception as e:
            logger.error(f"Whale alert post failed: {e}")

    async def _post_whale_volume_alert(self, spike: Dict):
        """Post volume-based whale activity alert to free channel"""
        if not self.channel_publisher or not self.target_channel_id:
            return

        emoji = "🚀" if spike['price_change'] > 0 else "🔻"

        text = (
            f"{emoji} <b>WHALE ALERT</b> {emoji}\n\n"
            f"<b>{spike['symbol']}</b>\n"
            f"📈 24h Change: {spike['price_change']:+.1f}%\n"
            f"💰 24h Volume: ${spike['volume_24h']:,.0f}\n\n"
            f"⚡ Unusual whale activity detected.\n"
            f"💎 Pro members get these alerts in real-time."
        )

        try:
            await self.channel_publisher.bot.send_message(
                chat_id=self.target_channel_id,
                text=text,
                parse_mode='HTML'
            )
            logger.info(f"� Whale alert (volume) posted to free: {spike['symbol']}")
        except Exception as e:
            logger.error(f"Whale volume alert post failed: {e}")


# ============== 2. EDUCATIONAL CONTENT ENGINE ==============

class EducationalContentEngine:
    """Scheduled educational posts for Pro+ members"""

    CONTENT_LIBRARY = {
        'risk_management': [
            "📚 <b>RISK MANAGEMENT 101</b>\n\n"
            "The #1 reason traders fail: poor risk management.\n\n"
            "✅ Never risk >2% per trade\n"
            "✅ Always use a stop loss\n"
            "✅ Risk/Reward minimum 1:2\n"
            "✅ Move SL to breakeven after TP1\n\n"
            "💡 A 50% win rate with 2:1 R/R = profitable.\n"
            "A 70% win rate with 0.5:1 R/R = broke.",

            "📚 <b>POSITION SIZING</b>\n\n"
            "Formula: Position Size = (Account * Risk%) / (Entry - SL)\n\n"
            "Example:\n"
            "$10,000 account, 2% risk = $200\n"
            "Entry $100, SL $95 = $5 risk per unit\n"
            "Position = $200 / $5 = 40 units\n\n"
            "🎯 This keeps losses controlled.\n"
            "💎 Pro members get exact sizing with every signal.",
        ],
        'market_structure': [
            "📚 <b>MARKET STRUCTURE</b>\n\n"
            "Institutions read structure. Retail reads indicators.\n\n"
            "Higher Highs + Higher Lows = Uptrend\n"
            "Lower Highs + Lower Lows = Downtrend\n\n"
            "🔑 Key levels:\n"
            "• Previous swing high/low\n"
            "• Session opens\n"
            "• Liquidity pools\n\n"
            "💎 We find entries at structure discounts.",

            "📚 <b>LIQUIDITY ZONES</b>\n\n"
            "Where do stops cluster? That's liquidity.\n\n"
            "Common liquidity pools:\n"
            "• Equal highs/lows\n"
            "• Previous day high/low\n"
            "• Round numbers\n\n"
            "🎯 Price often sweeps these levels,\n"
            "then reverses to target the next pool.\n\n"
            "💎 Pro signals target liquidity to liquidity.",
        ],
        'trading_psychology': [
            "📚 <b>TRADING PSYCHOLOGY</b>\n\n"
            "FOMO is the #1 account killer.\n\n"
            "Signs you're FOMOing:\n"
            "• Entering after a big candle\n"
            "• Increasing size after a loss\n"
            "• Trading outside your plan\n\n"
            "✅ Wait for YOUR setup\n"
            "✅ Stick to your risk rules\n"
            "✅ Missed money is better than lost money\n\n"
            "💎 Our system removes emotion. You get the plan. You execute.",

            "📚 <b>THE COMPOUNDING MINDSET</b>\n\n"
            "1% per day = 37x per year.\n\n"
            "You don't need home runs.\n"
            "You need consistency.\n\n"
            "✅ Small, repeatable wins\n"
            "✅ Strict risk management\n"
            "✅ No gambling mentality\n\n"
            "💎 That's why we filter for 85%+ confidence only.",
        ],
        'institutional_tools': [
            "📚 <b>VOLUME PROFILE</b>\n\n"
            "Where did the most volume trade?\n"
            "That's the Point of Control (POC).\n\n"
            "Key concepts:\n"
            "• Value Area High/Low = support/resistance\n"
            "• POC = magnet for price\n"
            "• Volume gaps = fast moves\n\n"
            "🎯 We enter when price returns to value.\n"
            "💎 Pro signals include volume profile analysis.",

            "📚 <b>SESSION ANALYSIS</b>\n\n"
            "Not all hours are equal.\n\n"
            "💰 London-NY overlap (13:00-16:00 UTC):\n"
            "  Highest volume, best liquidity\n\n"
            "🌏 Asia session (00:00-08:00 UTC):\n"
            "  Lower volume, cleaner ranges\n\n"
            "⚡ We only trade during active sessions.\n"
            "No dead-market fakeouts.",
        ],
        'macro_context': [
            "📚 <b>FUNDING RATES</b>\n\n"
            "Positive funding = longs pay shorts\n"
            "→ Crowded longs, potential short squeeze\n\n"
            "Negative funding = shorts pay longs\n"
            "→ Crowded shorts, potential long squeeze\n\n"
            "🎯 Extreme funding = contrarian signal\n\n"
            "💎 Our context engine monitors funding 24/7.",

            "📚 <b>OPEN INTEREST</b>\n\n"
            "Rising OI + Rising price = strong trend\n"
            "Rising OI + Falling price = distribution\n"
            "Falling OI + Any direction = weak move\n\n"
            "🎯 OI tells you if \"smart money\" is committed.\n\n"
            "💎 Pro signals filter for OI confirmation.",
        ],
    }

    def __init__(self, channel_publisher=None):
        self.channel_publisher = channel_publisher
        self.target_channel_id = getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None)  # Education → free channel as upsell
        self.posted_topics = set()

    def get_next_lesson(self) -> str:
        """Get next educational post, cycling through topics"""
        category = random.choice(list(self.CONTENT_LIBRARY.keys()))
        lessons = self.CONTENT_LIBRARY[category]
        lesson = random.choice(lessons)
        return lesson

    async def post_educational_content(self):
        """Post educational content to free channel as VIP upsell"""
        if not self.channel_publisher or not self.target_channel_id:
            return

        text = self.get_next_lesson()
        text += "\n\n📚 <b>Pro Education — Exclusive to VIP</b>\n"
        text += "💎 Upgrade to Quarterly for priority support + whale alerts"

        try:
            await self.channel_publisher.bot.send_message(
                chat_id=self.target_channel_id,
                text=text,
                parse_mode='HTML'
            )
            logger.info("📚 Educational content posted to free channel")
        except Exception as e:
            logger.error(f"Educational post failed: {e}")


# ============== 3. CUSTOM ALERT SYSTEM ==============

class CustomAlertSystem:
    """
    Users can set custom price alerts via VIP bot.
    Alerts checked every 5 minutes alongside signal monitoring.
    """

    def __init__(self, channel_publisher=None, db=None):
        self.channel_publisher = channel_publisher
        self.db = db
        self.alerts: List[Dict] = []  # In-memory store; could use DB

    async def add_alert(self, user_id: str, symbol: str, target_price: float, direction: str) -> bool:
        """Add a custom price alert for a user"""
        alert = {
            'id': f"{user_id}_{symbol}_{target_price}_{datetime.utcnow().timestamp()}",
            'user_id': user_id,
            'symbol': symbol.upper(),
            'target_price': target_price,
            'direction': direction.upper(),  # ABOVE or BELOW
            'created_at': datetime.utcnow(),
            'triggered': False,
        }
        self.alerts.append(alert)
        logger.info(f"Custom alert added: {symbol} {direction} ${target_price}")
        return True

    async def remove_alert(self, alert_id: str) -> bool:
        """Remove a user's alert"""
        self.alerts = [a for a in self.alerts if a['id'] != alert_id]
        return True

    async def get_user_alerts(self, user_id: str) -> List[Dict]:
        """Get all active alerts for a user"""
        return [a for a in self.alerts if a['user_id'] == user_id and not a['triggered']]

    async def check_alerts(self, scanner):
        """Check all alerts against current prices"""
        if not self.alerts:
            return

        for alert in list(self.alerts):
            if alert['triggered']:
                continue

            try:
                ticker = await scanner.fetch_ticker(alert['symbol'])
                current_price = ticker.get('last', 0)

                triggered = False
                if alert['direction'] == 'ABOVE' and current_price >= alert['target_price']:
                    triggered = True
                elif alert['direction'] == 'BELOW' and current_price <= alert['target_price']:
                    triggered = True

                if triggered:
                    alert['triggered'] = True
                    await self._notify_user(alert, current_price)

            except Exception as e:
                logger.error(f"Alert check error for {alert['symbol']}: {e}")

    async def _notify_user(self, alert: Dict, current_price: float):
        """Send alert notification to user"""
        emoji = "🚀" if alert['direction'] == 'ABOVE' else "🔻"
        text = (
            f"{emoji} <b>CUSTOM ALERT TRIGGERED</b> {emoji}\n\n"
            f"📊 <b>{alert['symbol']}</b>\n"
            f"🎯 Target: ${alert['target_price']:,.4f}\n"
            f"📈 Current: ${current_price:,.4f}\n"
            f"⏱ Created: {alert['created_at'].strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"💎 Set more alerts with /alert in the VIP bot."
        )

        try:
            if self.channel_publisher and self.channel_publisher.bot:
                await self.channel_publisher.bot.send_message(
                    chat_id=alert['user_id'],
                    text=text,
                    parse_mode='HTML'
                )
                logger.info(f"🔔 Custom alert sent to {alert['user_id']}: {alert['symbol']}")
        except Exception as e:
            logger.error(f"Custom alert notification failed: {e}")


# ============== 4. GIVEAWAY ENGINE ==============

class GiveawayEngine:
    """
    Random VIP-only giveaways for lifetime members.
    Can be triggered manually by admin or scheduled monthly.
    """

    PRIZES = [
        {"name": "1 MONTH FREE VIP", "weight": 30},
        {"name": "$50 USDT", "weight": 20},
        {"name": "50% OFF Lifetime", "weight": 15},
        {"name": "25% OFF Lifetime", "weight": 15},
        {"name": "Trading Strategy PDF", "weight": 15},
        {"name": "$100 USDT", "weight": 5},
    ]

    def __init__(self, channel_publisher=None, db=None):
        self.channel_publisher = channel_publisher
        self.db = db
        self.vip_channel_id = getattr(settings, 'TELEGRAM_VIP_CHANNEL_ID', None)

    async def run_monthly_giveaway(self):
        """Run a monthly giveaway for lifetime members"""
        if not self.db:
            return

        try:
            # Get lifetime subscribers
            lifetime_users = await self.db.get_active_subscribers(tier='lifetime')
            if not lifetime_users:
                logger.info("No lifetime members — skipping giveaway")
                return

            # Pick winner
            winner = random.choice(lifetime_users)
            prize = self._draw_prize()

            # Announce in VIP channel
            text = (
                "🎉 <b>VIP MONTHLY GIVEAWAY</b> 🎉\n\n"
                f"🏆 Prize: <b>{prize['name']}</b>\n"
                f"🎁 Winner: @{winner.get('username', 'Anonymous')}\n\n"
                "💎 Lifetime members are automatically entered every month.\n"
                "🚀 Upgrade to Lifetime for your chance to win!"
            )

            if self.channel_publisher and self.vip_channel_id:
                await self.channel_publisher.bot.send_message(
                    chat_id=self.vip_channel_id,
                    text=text,
                    parse_mode='HTML'
                )

            # Notify admin
            logger.info(f"🎉 Giveaway winner: {winner.get('username')} -> {prize['name']}")

        except Exception as e:
            logger.error(f"Giveaway error: {e}")

    def _draw_prize(self) -> Dict:
        """Weighted random prize draw"""
        weights = [p['weight'] for p in self.PRIZES]
        return random.choices(self.PRIZES, weights=weights, k=1)[0]


# ============== 5. BONUS REPORTS ==============

class BonusReportEngine:
    """
    Extra market reports for Quarterly+ members.
    Goes beyond weekly reports — includes market bias, funding, OI, etc.
    """

    def __init__(self, channel_publisher=None, context_engine=None):
        self.channel_publisher = channel_publisher
        self.context_engine = context_engine
        self.target_channel_id = getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None)  # Bonus reports → free as teaser

    async def send_bonus_market_report(self):
        """Send bonus market report to free channel"""
        if not self.context_engine:
            return

        try:
            # Fetch market bias data
            context = await self.context_engine.analyze_context("BTC/USDT", "LONG")

            text = (
                "📊 <b>BONUS MARKET REPORT</b>\n\n"
                "💎 Exclusive to Quarterly & Lifetime members\n\n"
            )

            if context:
                text += (
                    f"📈 <b>Market Sentiment:</b> {context.total_score:.0f}/100\n"
                    f"📰 <b>News Score:</b> {context.news_score:.0f}/100\n"
                    f"🌍 <b>Macro Score:</b> {context.macro_score:.0f}/100\n\n"
                )

            text += (
                "🎯 <b>This Week's Focus:</b>\n"
                "• Watch BTC dominance for altcoin rotation\n"
                "• Monitor funding rates for crowded trades\n"
                "• Track OI changes on major coins\n\n"
                "💎 Upgrade to Quarterly for these reports every week."
            )

            if self.channel_publisher and self.target_channel_id:
                await self.channel_publisher.bot.send_message(
                    chat_id=self.target_channel_id,
                    text=text,
                    parse_mode='HTML'
                )
                logger.info("📊 Bonus market report sent to free channel")

        except Exception as e:
            logger.error(f"Bonus report error: {e}")


# ============== 6. PRIORITY SUPPORT ==============

class PrioritySupport:
    """
    Flags Pro/Lifetime member messages for admin priority.
    Simple wrapper that adds tier info to admin notifications.
    """

    PRO_TIERS = {'quarterly', 'lifetime'}

    def __init__(self, db=None):
        self.db = db

    async def is_priority_user(self, user_id: str) -> bool:
        """Check if user is on a Pro tier"""
        if not self.db:
            return False
        try:
            sub = await self.db.get_subscriber(user_id)
            if sub and sub.get('active'):
                return sub.get('tier', '') in self.PRO_TIERS
        except Exception:
            pass
        return False

    def format_priority_notification(self, message: str, user_id: str, tier: str = None) -> str:
        """Wrap notification with priority badge"""
        if tier in self.PRO_TIERS:
            return f"🌟 <b>[PRIORITY — {tier.upper()}]</b>\n\n{message}"
        return message
