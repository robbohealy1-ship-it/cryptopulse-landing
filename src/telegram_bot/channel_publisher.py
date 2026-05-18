import asyncio
from telegram import Bot
from telegram.error import NetworkError
from typing import Optional
from src.models.signal import TradingSignal, SignalDirection, SignalStatus
from src.config import settings
from src.utils.logger import get_logger
from src.telegram_bot.chart_generator import ChartGenerator

logger = get_logger(__name__)


class ChannelPublisher:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.free_channel_id = settings.TELEGRAM_FREE_CHANNEL_ID
        self.vip_channel_id = settings.TELEGRAM_VIP_CHANNEL_ID
        self.chart_generator = ChartGenerator()

    async def _send_with_retry(self, send_func, max_retries=3, backoff=2):
        """Retry Telegram sends on network errors with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return await send_func()
            except NetworkError as e:
                if attempt < max_retries - 1:
                    wait = backoff * (2 ** attempt)
                    logger.debug(f"Network error sending message, retrying in {wait}s... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Failed to send message after {max_retries} retries: {e}")
                    raise
    
    async def publish_signal(self, signal: TradingSignal, vip_only: bool = False):
        """Legacy method - use publish_to_vip and publish_to_free separately"""
        try:
            await self.publish_to_vip(signal)
            if not vip_only:
                await self.publish_to_free(signal)
            else:
                await self.send_vip_teaser(signal)
        except Exception as e:
            logger.error(f"Error publishing signal: {e}")
            raise
    
    async def publish_to_vip(self, signal: TradingSignal):
        """Publish full signal to VIP channel immediately"""
        try:
            vip_message = self._format_signal_for_channel(signal, vip_only=True)
            
            # Generate chart with fallback to text-only if it fails
            chart_path = None
            try:
                chart_path = await self.chart_generator.generate_chart(signal)
            except Exception as chart_err:
                logger.warning(f"Chart generation failed for {signal.symbol}, sending text-only: {chart_err}")
            
            if chart_path:
                with open(chart_path, 'rb') as photo:
                    msg = await self.bot.send_photo(
                        chat_id=self.vip_channel_id,
                        photo=photo,
                        caption=vip_message,
                        parse_mode='HTML'
                    )
                    signal.vip_channel_message_id = msg.message_id
            else:
                msg = await self.bot.send_message(
                    chat_id=self.vip_channel_id,
                    text=vip_message,
                    parse_mode='HTML'
                )
                signal.vip_channel_message_id = msg.message_id
            
            signal.vip_channel_posted = True
            signal.status = SignalStatus.ACTIVE
            logger.info(f"Published signal {signal.symbol} to VIP channel")
            
        except Exception as e:
            logger.error(f"Error publishing to VIP: {e}")
            raise
    
    async def publish_to_free(self, signal: TradingSignal):
        """Publish simplified signal to free channel"""
        try:
            free_message = self._format_signal_for_channel(signal, vip_only=False)
            
            # Generate chart with fallback to text-only if it fails
            chart_path = None
            try:
                chart_path = await self.chart_generator.generate_chart(signal)
            except Exception as chart_err:
                logger.warning(f"Chart generation failed for {signal.symbol}, sending text-only: {chart_err}")
            
            if chart_path:
                with open(chart_path, 'rb') as photo:
                    msg = await self.bot.send_photo(
                        chat_id=self.free_channel_id,
                        photo=photo,
                        caption=free_message,
                        parse_mode='HTML'
                    )
                    signal.free_channel_message_id = msg.message_id
            else:
                msg = await self.bot.send_message(
                    chat_id=self.free_channel_id,
                    text=free_message,
                    parse_mode='HTML'
                )
                signal.free_channel_message_id = msg.message_id
            
            signal.free_channel_posted = True
            logger.info(f"Published signal {signal.symbol} to FREE channel")
            
        except Exception as e:
            logger.error(f"Error publishing to free channel: {e}")
            raise
    
    def _get_exchange_link(self, symbol: str) -> str:
        """Build affiliate trading link for a symbol based on configured exchange."""
        exchange = settings.AFFILIATE_EXCHANGE.lower()
        
        # CUSTOM: User pasted their own URL — use it exactly as-is
        if exchange == 'custom':
            custom_url = settings.AFFILIATE_CUSTOM_URL
            if custom_url:
                return custom_url
            # Fallback if custom URL not set
            return "https://www.google.com/search?q=" + symbol.replace('/', '') + "+USDT+price"
        
        base = symbol.replace('/', '').replace('USDT', '').replace('USD', '')
        ref = settings.AFFILIATE_EXCHANGE_REF or ''
        
        if exchange == 'binance':
            url = f"https://www.binance.com/en/trade/{base}_USDT"
            if ref:
                url += f"?ref={ref}"
        elif exchange == 'bybit':
            url = f"https://www.bybit.com/trade/spot/{base}USDT"
            if ref:
                url += f"?affiliate_id={ref}"
        elif exchange == 'okx':
            url = f"https://www.okx.com/trade-spot/{base.lower()}-usdt"
            if ref:
                url += f"?channelId={ref}"
        elif exchange == 'bitget':
            url = f"https://www.bitget.com/spot/{base}USDT"
            if ref:
                url += f"?type=register&inviteCode={ref}"
        elif exchange == 'mexc':
            url = f"https://www.mexc.com/exchange/{base}_USDT"
            if ref:
                url += f"?inviteCode={ref}"
        elif exchange == 'kucoin':
            url = f"https://www.kucoin.com/trade/{base}-USDT"
            if ref:
                url += f"?rcode={ref}"
        else:
            # Default to custom URL or search fallback
            custom_url = settings.AFFILIATE_CUSTOM_URL
            if custom_url:
                return custom_url
            return f"https://www.google.com/search?q={base}+USDT+price"
        
        return url
    
    async def send_free_channel_message(self, text: str, parse_mode: str = 'HTML'):
        """Send a custom message to the free channel (for dashboard campaigns)"""
        try:
            await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=text,
                parse_mode=parse_mode
            )
            logger.info("Sent custom message to FREE channel")
        except Exception as e:
            logger.error(f"Error sending free channel message: {e}")
            raise
    
    async def send_vip_teaser(self, signal: TradingSignal):
        """Send marketing teaser for VIP-exclusive signal to free channel"""
        try:
            link = self._get_exchange_link(signal.symbol)
            ticker = signal.symbol.replace('/', '')
            
            teaser = f"""🌟 <b>VIP EXCLUSIVE SIGNAL</b> 🌟

<a href="{link}">#{ticker}</a> - {signal.direction.value}
⚡ Confidence: {signal.confidence:.1f}%

💎 <b>This elite signal is only for VIP members!</b>

Join VIP to get:
✅ 90%+ confidence signals
✅ 3 profit targets
✅ Full market analysis
✅ Real-time updates

👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for instant VIP access
💰 Crypto payments accepted"""
            
            await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=teaser,
                parse_mode='HTML'
            )
            logger.info(f"Sent VIP teaser for {signal.symbol} to FREE channel")
            
        except Exception as e:
            logger.error(f"Error sending VIP teaser: {e}")
    
    def _format_signal_for_channel(self, signal: TradingSignal, vip_only: bool = False) -> str:
        direction_emoji = "🟢" if signal.direction.value == "LONG" else "🔴"
        
        if vip_only:
            # Check if this is VIP-exclusive (90%+ confidence)
            is_exclusive = signal.confidence >= 90
            exclusive_header = "🌟 VIP EXCLUSIVE 🌟\n⭐ ELITE SIGNAL ⭐\n\n" if is_exclusive else ""
            
            link = self._get_exchange_link(signal.symbol)
            ticker = signal.symbol.replace('/', '')
            
            message = f"""
{exclusive_header}{direction_emoji} <b>VIP SIGNAL</b> {direction_emoji}

<a href="{link}"><b>#{ticker}</b></a>
<b>Direction:</b> {signal.direction.value}
<b>Timeframe:</b> {signal.timeframe}

💰 <b>{'LIMIT Entry' if signal.is_limit_order else 'Entry Zone'}:</b> ${signal.entry_price:.8f}
🛑 <b>Stop Loss:</b> ${signal.stop_loss:.8f}

🎯 <b>Targets:</b>
TP1: ${signal.take_profit_1:.8f}
{f'TP2: ${signal.take_profit_2:.8f}' if signal.take_profit_2 else ''}
{f'TP3: ${signal.take_profit_3:.8f}' if signal.take_profit_3 else ''}

📊 <b>Risk/Reward:</b> 1:{signal.risk_reward:.2f}
⚡ <b>Confidence:</b> {signal.confidence:.1f}%

📐 <b>Sizing</b> (1% risk on $1K = ${int(10 / abs(signal.entry_price - signal.stop_loss)) if abs(signal.entry_price - signal.stop_loss) > 0 else 'N/A'} units)

<b>Analysis:</b>
{(signal.reasoning[:300] + '...' if len(signal.reasoning) > 300 else signal.reasoning) if signal.reasoning else 'N/A'}
{f'''
<b>Market Context:</b>
{signal.market_context[:200]}...''' if signal.market_context else ''}
{f'''
<b>News Context:</b>
{signal.news_context[:200]}...''' if signal.news_context else ''}
⚠️ <b>Risk Management:</b>
• Use proper position sizing
• Never risk more than 2% per trade
• Move SL to breakeven after TP1

<i>Signal ID: {(signal.id[:8] if signal.id else 'MANUAL')}</i>
"""
        else:
            link = self._get_exchange_link(signal.symbol)
            ticker = signal.symbol.replace('/', '')
            
            message = f"""
{direction_emoji} <b>FREE SIGNAL</b> {direction_emoji}

<a href="{link}"><b>#{ticker}</b></a>
<b>Direction:</b> {signal.direction.value}

💰 <b>Entry:</b> ${signal.entry_price:.8f}
🛑 <b>Stop Loss:</b> ${signal.stop_loss:.8f}

📊 <b>R/R:</b> 1:{signal.risk_reward:.2f}

⚠️ <b>Always use stop loss!</b>

💎 <b>Want 3 profit targets & detailed analysis?</b>
Join VIP for premium signals!
"""
        
        return message.strip()
    
    async def update_signal(self, signal: TradingSignal, update_text: str):
        try:
            if signal.free_channel_message_id:
                await self.bot.send_message(
                    chat_id=self.free_channel_id,
                    text=f"📢 <b>UPDATE - {signal.symbol}</b>\n\n{update_text}",
                    parse_mode='HTML'
                )
            
            if signal.vip_channel_message_id:
                await self.bot.send_message(
                    chat_id=self.vip_channel_id,
                    text=f"📢 <b>UPDATE - {signal.symbol}</b>\n\n{update_text}",
                    parse_mode='HTML'
                )
            
            logger.info(f"Updated signal {signal.symbol} in channels")
            
        except Exception as e:
            logger.error(f"Error updating signal: {e}")
    
    async def send_tp_hit(self, signal: TradingSignal, tp_level: int):
        # VIP channel gets full update
        tp_val = getattr(signal, f'take_profit_{tp_level}', None)
        tp_str = f"${tp_val:.4f}" if tp_val is not None else "N/A"
        vip_text = f"✅ <b>TP{tp_level} HIT!</b>\n\n"
        vip_text += f"Target {tp_str} reached\n"
        
        if tp_level == 1:
            vip_text += "\n💡 <b>Tip:</b> Move stop loss to breakeven"
            vip_text += "\n🎯 <b>Next targets:</b> TP2 & TP3 still active"
        elif tp_level == 2:
            vip_text += "\n🚀 <b>Halfway to max profit!</b>"
        elif tp_level == 3:
            vip_text += "\n🎉 <b>MAX PROFIT ACHIEVED!</b>"
        
        # Send to VIP
        if signal.vip_channel_message_id:
            await self.bot.send_message(
                chat_id=self.vip_channel_id,
                text=f"📢 <b>UPDATE - {signal.symbol}</b>\n\n{vip_text}",
                parse_mode='HTML'
            )
        
        # Free channel only gets TP1 with marketing
        if tp_level == 1 and signal.free_channel_message_id:
            tp_val = getattr(signal, f'take_profit_{tp_level}', None)
            tp_str = f"${tp_val:.4f}" if tp_val is not None else "N/A"
            free_text = f"🎉 <b>{signal.symbol} TP1 HIT!</b>\n\n"
            free_text += f"Target {tp_str} reached\n\n"
            free_text += "💎 <b>Want TP2, TP3 and live updates?</b>\n"
            free_text += "Join VIP for full trade management!\n\n"
            free_text += "👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP access"
            
            await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=free_text,
                parse_mode='HTML'
            )
        
        logger.info(f"TP{tp_level} hit on {signal.symbol}")
    
    async def send_tp_hit_free(self, signal: TradingSignal, tp_level: int):
        """Send TP hit update to FREE channel as marketing"""
        if not signal.free_channel_message_id:
            return
        
        tp_val = getattr(signal, f'take_profit_{tp_level}', None)
        tp_str = f"${tp_val:.4f}" if tp_val is not None else "N/A"
        free_text = f"🎉 <b>{signal.symbol} TP{tp_level} HIT!</b>\n\n"
        free_text += f"Target {tp_str} reached\n\n"
        
        if tp_level == 1:
            free_text += "💎 <b>Want TP2, TP3 and live updates?</b>\n"
        elif tp_level == 2:
            free_text += "💎 <b>TP2 hit! VIP members getting TP3 target...</b>\n"
        elif tp_level == 3:
            free_text += "💎 <b>MAX PROFIT! VIP members just banked full gains!</b>\n"
        
        free_text += "Join VIP for full trade management!\n\n"
        free_text += f"👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP access"
        
        await self.bot.send_message(
            chat_id=self.free_channel_id,
            text=free_text,
            parse_mode='HTML'
        )
        
        logger.info(f"TP{tp_level} free channel update sent for {signal.symbol}")
    
    async def send_stop_moved(self, signal: TradingSignal, new_stop: float):
        update_text = f"🔒 <b>STOP LOSS MOVED</b>\n\n"
        update_text += f"New SL: ${new_stop:.8f}\n"
        update_text += f"Trade now risk-free!"
        
        await self.update_signal(signal, update_text)
    
    async def send_trade_closed(self, signal: TradingSignal, result: str, pnl: float):
        emoji = "✅" if pnl > 0 else "❌"
        
        update_text = f"{emoji} <b>TRADE CLOSED</b>\n\n"
        update_text += f"Result: {result}\n"
        update_text += f"P&L: {pnl:+.2f}%\n"
        
        await self.update_signal(signal, update_text)
