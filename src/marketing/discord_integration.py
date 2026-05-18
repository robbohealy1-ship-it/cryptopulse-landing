"""
Discord Integration
Posts signals and marketing content to Discord via webhooks
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DiscordPublisher:
    """Publish signals and content to Discord servers via webhooks"""
    
    def __init__(self):
        self.webhook_url = getattr(settings, 'DISCORD_WEBHOOK_URL', None)
        self.enabled = bool(self.webhook_url)
        
        if self.enabled:
            logger.info("Discord publisher initialized")
        else:
            logger.info("Discord webhook not configured - Discord posting disabled")
    
    async def _send_webhook(self, payload: dict, image_path: Optional[str] = None) -> bool:
        """Send payload to Discord webhook"""
        if not self.enabled:
            return False
        
        try:
            import aiohttp
            
            form_data = aiohttp.FormData()
            
            # Add JSON payload as 'payload_json'
            import json
            form_data.add_field('payload_json', json.dumps(payload))
            
            # Add image if provided
            if image_path and Path(image_path).exists():
                with open(image_path, 'rb') as f:
                    form_data.add_field('file', f, filename=Path(image_path).name)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, data=form_data) as resp:
                    if resp.status in (200, 204):
                        logger.info("Discord webhook sent successfully")
                        return True
                    else:
                        logger.warning(f"Discord webhook returned {resp.status}: {await resp.text()}")
                        return False
        except Exception as e:
            logger.error(f"Discord webhook failed: {e}")
            return False
    
    def _get_tradingview_link(self, symbol: str, timeframe: str = '15') -> str:
        """Generate a professional TradingView chart link"""
        base, quote = symbol.split('/')
        tv_symbol = f"BINANCE:{base}{quote}"
        interval_map = {'1m': '1', '5m': '5', '15m': '15', '1h': '60', '4h': '240', '1d': 'D'}
        interval = interval_map.get(timeframe, '15')
        return f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"
    
    async def post_signal(self, signal) -> bool:
        """Post a signal as a rich Discord embed with TradingView chart"""
        direction_color = 0x00ff00 if signal.direction.value == "LONG" else 0xff0000
        ticker = signal.symbol.replace('/', '')
        tv_link = self._get_tradingview_link(signal.symbol, getattr(signal, 'timeframe', '15m'))
        
        embed = {
            "title": f"🎯 {signal.direction.value} SIGNAL - #{ticker}",
            "description": f"Confidence: {signal.confidence:.1f}% | Timeframe: {signal.timeframe}",
            "color": direction_color,
            "fields": [
                {
                    "name": "📊 TradingView Chart",
                    "value": f"[Open Chart]({tv_link})",
                    "inline": False
                },
                {
                    "name": "💰 Entry",
                    "value": f"${signal.entry_price:.8f}",
                    "inline": True
                },
                {
                    "name": "🛑 Stop Loss",
                    "value": f"${signal.stop_loss:.8f}",
                    "inline": True
                },
                {
                    "name": "📊 R/R",
                    "value": f"1:{signal.risk_reward:.2f}",
                    "inline": True
                },
                {
                    "name": "🎯 Target 1",
                    "value": f"${signal.take_profit_1:.8f}",
                    "inline": True
                },
                {
                    "name": "🎯 Target 2",
                    "value": f"${signal.take_profit_2:.8f}" if signal.take_profit_2 is not None else "N/A",
                    "inline": True
                },
                {
                    "name": "🎯 Target 3",
                    "value": f"${signal.take_profit_3:.8f}" if signal.take_profit_3 is not None else "N/A",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Signal ID: {signal.id[:8]} | Join VIP: t.me/CryptoPulseVIPAccessBot"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if signal.market_context:
            embed["fields"].append({
                "name": "🌍 Market Context",
                "value": signal.market_context[:250] + "..." if len(signal.market_context) > 250 else signal.market_context,
                "inline": False
            })
        
        payload = {
            "content": "📢 New signal detected!",
            "embeds": [embed]
        }
        
        return await self._send_webhook(payload)
    
    async def post_performance(self, stats: dict) -> bool:
        """Post performance stats to Discord"""
        embed = {
            "title": "📊 Weekly Performance Report",
            "description": "CryptoPulse Signals - VIP Results",
            "color": 0x5865F2,
            "fields": [
                {
                    "name": "📈 Total Signals",
                    "value": str(stats.get('total_signals', 0)),
                    "inline": True
                },
                {
                    "name": "✅ Win Rate",
                    "value": f"{stats.get('win_rate', 0):.1f}%",
                    "inline": True
                },
                {
                    "name": "💰 Total P&L",
                    "value": f"{stats.get('total_pnl', 0):.2f}%",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Join VIP: t.me/CryptoPulseVIPAccessBot"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        payload = {"content": "🏆 Performance update!", "embeds": [embed]}
        return await self._send_webhook(payload)
    
    async def post_marketing(self, title: str, message: str, color: int = 0x00ff00) -> bool:
        """Post general marketing content"""
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "footer": {
                "text": "CryptoPulse Signals | Join VIP: t.me/CryptoPulseVIPAccessBot"
            }
        }
        
        payload = {"embeds": [embed]}
        return await self._send_webhook(payload)
    
    async def post_free_teaser(self, signal) -> bool:
        """Post free channel teaser to Discord (no prices, same as Telegram Free)"""
        direction = signal.direction.value
        color = 0x00ff00 if direction == "LONG" else 0xff4444
        ticker = signal.symbol.replace('/', '')
        
        tv_link = self._get_tradingview_link(signal.symbol, getattr(signal, 'timeframe', '15m'))
        
        embed = {
            "title": f"🔥 {direction} SIGNAL ALERT",
            "description": (
                f"**{ticker}** | Confidence: {signal.confidence:.0f}%\n"
                f"⏱ Timeframe: {signal.timeframe}\n\n"
                f"💡 **Free channel gets the teaser.**\n"
                f"💎 **VIP gets the full plan:**\n"
                f"   ✅ Exact entry price\n"
                f"   ✅ Stop loss level\n"
                f"   ✅ 3 profit targets\n"
                f"   ✅ Live updates\n\n"
                f"📈 [View Chart]({tv_link})\n\n"
                f"🔐 [Join VIP Instantly](https://t.me/CryptoPulseVIPAccessBot)"
            ),
            "color": color,
            "footer": {
                "text": "CryptoPulse Signals | Free Channel"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        payload = {"embeds": [embed]}
        return await self._send_webhook(payload)
    
    async def post_welcome(self, member_count: int = 0) -> bool:
        """Post welcome/announcement message"""
        message = (
            "🎉 Welcome to CryptoPulse Signals!\n\n"
            "📢 **What we do:**\n"
            "• High-accuracy crypto trading signals\n"
            "• Entry, stop loss, and 3 take profits\n"
            "• 90%+ confidence setups only\n"
            "• Real-time market analysis\n\n"
            "� **Join VIP:** t.me/CryptoPulseVIPAccessBot\n\n"
            "Let's trade smarter together! 🚀"
        )
        
        return await self.post_marketing(
            f"🚀 Welcome! ({member_count} members)" if member_count else "🚀 Welcome!",
            message,
            color=0xFFD700
        )
