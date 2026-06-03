import asyncio
import re
from datetime import datetime
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
        # Deduplication: track which (signal_id, event_type) combos have been sent
        # to prevent duplicate messages if stale recovery fires or signal is re-processed
        self._sent_notifications: set = set()

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
            
            # Send chart FIRST so it appears at the top of the thread
            chart_msg_id = None
            try:
                chart_path = await self.chart_generator.generate_chart(signal)
                if chart_path:
                    with open(chart_path, 'rb') as photo:
                        short_caption = f"📊 {signal.symbol} | {signal.direction.value} | {signal.timeframe}"
                        chart_msg = await self.bot.send_photo(
                            chat_id=self.vip_channel_id,
                            photo=photo,
                            caption=short_caption,
                            parse_mode='HTML'
                        )
                        chart_msg_id = chart_msg.message_id
            except Exception as chart_err:
                logger.warning(f"Chart generation failed for {signal.symbol}: {chart_err}")
            
            # Send full text as reply to chart (or standalone if no chart)
            # Append referral CTA at the very end of the message
            vip_message += self._get_referral_cta()
            
            kwargs = {'chat_id': self.vip_channel_id, 'text': vip_message, 'parse_mode': 'HTML'}
            if chart_msg_id:
                kwargs['reply_to_message_id'] = chart_msg_id
            msg = await self.bot.send_message(**kwargs)
            signal.vip_channel_message_id = msg.message_id
            
            signal.vip_channel_posted = True
            logger.info(f"Published signal {signal.symbol} to VIP channel")
            
        except Exception as e:
            logger.error(f"Error publishing to VIP: {e}")
            raise
    
    async def publish_to_free(self, signal: TradingSignal):
        """Publish text-only teaser to free channel — NEVER send full signal cards or charts to free"""
        try:
            direction_emoji = "🟢 LONG" if signal.direction.value == "LONG" else "🔴 SHORT"
            ticker = signal.symbol.replace('/', '')
            
            # Text-only teaser — no prices, no chart, no targets
            text = (
                f"🔥 <b>{direction_emoji} SIGNAL ALERT</b>\n\n"
                f"📊 <b>#{ticker}</b> | Confidence: {signal.confidence:.0f}%\n"
                f"⏱ Timeframe: {signal.timeframe}\n\n"
                f"💡 <b>Free channel gets the teaser.</b>\n"
                f"💎 <b>VIP gets the full plan:</b>\n"
                f"   ✅ Exact entry price\n"
                f"   ✅ Stop loss level\n"
                f"   ✅ 3 profit targets\n"
                f"   ✅ Live updates\n\n"
                f"🔐 <a href='https://t.me/CryptoPulseVIPAccessBot'>Join VIP Instantly</a>\n"
                f"or DM @CryptoPulseVIPAccessBot"
            )
            
            # Append referral CTA
            text += self._get_referral_cta()
            
            msg = await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            signal.free_channel_message_id = msg.message_id
            signal.free_channel_posted = True
            logger.info(f"Published text teaser for {signal.symbol} to FREE channel")
            
        except Exception as e:
            logger.error(f"Error publishing to free channel: {e}")
            raise
    
    def _get_exchange_link(self, symbol: str) -> str:
        """Build affiliate trading link for a symbol based on configured exchange."""
        exchange = settings.AFFILIATE_EXCHANGE.lower()
        
        # CUSTOM: User pasted their own URL — use it exactly as-is
        if exchange == 'custom':
            custom_url = settings.AFFILIATE_CUSTOM_URL
            if custom_url and not self._is_placeholder_url(custom_url):
                return custom_url
            elif custom_url and self._is_placeholder_url(custom_url):
                logger.warning(f"⚠️ Skipping custom exchange link — placeholder detected in {custom_url}")
            # Fallback if custom URL not set or is placeholder
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
            if custom_url and not self._is_placeholder_url(custom_url):
                return custom_url
            return f"https://www.google.com/search?q={base}+USDT+price"
        
        return url
    
    def _is_placeholder_url(self, url: str) -> bool:
        """Detect unreplaced placeholder URLs that should not be sent."""
        if not url:
            return True
        placeholders = ['HYPERLIQUIDCODE', 'YOURCODE', 'YOUR_REF', 'PLACEHOLDER', 'EXAMPLE', 'XXXXXX', 'ABC123']
        url_upper = url.upper()
        for p in placeholders:
            # Only match as a whole segment (not followed by more letters/numbers)
            # e.g. HYPERLIQUIDCODE blocks, HYPERLIQUIDCODECP allows
            pattern = re.escape(p) + r'(?![A-Z0-9])'
            if re.search(pattern, url_upper):
                return True
        return False

    def _get_referral_cta(self) -> str:
        """Return referral links for Hyperliquid and MEXC at the bottom of all signals."""
        # Always include both referral links
        cta = (
            "\n\n🔥 <a href=\"https://app.hyperliquid.xyz/join/HYPERLIQUIDCODECP\"><b>Trade on Hyperliquid</b></a>\n"
            "💎 <a href=\"https://promote.mexc.com/r/RMWIMN3p5q\"><b>Trade on MEXC</b></a>"
        )
        return cta
    
    _current_symbol: str = ""
    
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
            
            teaser += self._get_referral_cta()
            await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=teaser,
                parse_mode='HTML'
            )
            logger.info(f"Sent VIP teaser for {signal.symbol} to FREE channel")
            
        except Exception as e:
            logger.error(f"Error sending VIP teaser: {e}")
    
    async def publish_teaser_to_free(self, signal: TradingSignal):
        """Send a 'warm-up' teaser for a lower-confidence signal to the free channel.
        These signals don't make the VIP cut but still show value to free members."""
        try:
            direction_emoji = "🟢 LONG" if signal.direction.value == "LONG" else "🔴 SHORT"
            ticker = signal.symbol.replace('/', '')
            
            text = (
                f"📊 <b>{direction_emoji} WARM-UP SIGNAL</b>\n\n"
                f"<b>#{ticker}</b> | Confidence: {signal.confidence:.0f}%\n"
                f"⏱ Timeframe: {signal.timeframe}\n\n"
                f"💡 <b>This is a warm-up setup.</b>\n"
                f"💎 <b>VIP members get the elite signals:</b>\n"
                f"   ✅ 85%+ confidence only\n"
                f"   ✅ Exact entry, SL & 3 TPs\n"
                f"   ✅ Live trade management\n"
                f"   ✅ Risk guidance & sizing\n\n"
                f"🔐 <a href='https://t.me/CryptoPulseVIPAccessBot'>Join VIP for elite signals</a>\n"
                f"or DM @CryptoPulseVIPAccessBot"
            )
            
            text += self._get_referral_cta()
            
            msg = await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            logger.info(f"Published warm-up teaser for {signal.symbol} to FREE channel")
            return msg
            
        except Exception as e:
            logger.error(f"Error publishing teaser to free channel: {e}")
    
    async def publish_free_real_to_free(self, signal: TradingSignal):
        """Send a full signal (entry, SL, TPs) to the free channel.
        This is the 1-per-day 70-80% confidence free-tier signal."""
        try:
            direction_emoji = "🟢" if signal.direction.value == "LONG" else "🔴"
            link = self._get_exchange_link(signal.symbol)
            ticker = signal.symbol.replace('/', '')
            self._current_symbol = ticker
            
            tp2_line = f"TP2: ${signal.take_profit_2:.8f}" if signal.take_profit_2 else ""
            tp3_line = f"TP3: ${signal.take_profit_3:.8f}" if signal.take_profit_3 else ""
            
            entry_type = "⏳ <b>LIMIT ORDER</b>" if signal.is_limit_order else "⚡ <b>MARKET ENTRY</b>"
            entry_instruction = f"Set limit order at ${signal.entry_price:.8f} — wait for retest" if signal.is_limit_order else f"Enter now at market price (~${signal.entry_price:.8f})"
            
            text = (
                f"📊 {direction_emoji} <b>FREE SIGNAL</b> {direction_emoji}\n\n"
                f"<a href='{link}'><b>#{ticker}</b></a>\n"
                f"<b>Direction:</b> {signal.direction.value}\n"
                f"<b>Timeframe:</b> {signal.timeframe}\n\n"
                f"{entry_type}\n"
                f"💰 <b>Entry:</b> ${signal.entry_price:.8f}\n"
                f"🔹 <i>{entry_instruction}</i>\n\n"
                f"🛑 <b>Stop Loss:</b> ${signal.stop_loss:.8f}\n\n"
                f"🎯 <b>Targets:</b>\n"
                f"TP1: ${signal.take_profit_1:.8f}\n"
                f"{tp2_line}\n"
                f"{tp3_line}\n\n"
                f"📊 <b>Risk/Reward:</b> 1:{signal.risk_reward:.2f}\n"
                f"⚡ <b>Confidence:</b> {signal.confidence:.1f}%\n"
                f"⚠️ <b>Risk Management:</b>\n"
                f"• Use proper position sizing\n"
                f"• Never risk more than 2% per trade\n"
                f"• Move SL to breakeven after TP1\n\n"
                f"<i>💎 Want 85%+ elite signals with live management?\n"
                f"Join VIP for premium signals!</i>"
            )
            
            # Append referral CTA at the very end
            text += self._get_referral_cta()
            
            msg = await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            logger.info(f"Published FREE REAL signal for {signal.symbol} to FREE channel")
            return msg
            
        except Exception as e:
            logger.error(f"Error publishing free real signal to free channel: {e}")
    
    def _format_signal_for_channel(self, signal: TradingSignal, vip_only: bool = False) -> str:
        direction_emoji = "🟢" if signal.direction.value == "LONG" else "🔴"
        
        if vip_only:
            # Check if this is VIP-exclusive (90%+ confidence)
            is_exclusive = signal.confidence >= 90
            exclusive_header = "🌟 VIP EXCLUSIVE 🌟\n⭐ ELITE SIGNAL ⭐\n\n" if is_exclusive else ""
            
            link = self._get_exchange_link(signal.symbol)
            ticker = signal.symbol.replace('/', '')
            self._current_symbol = ticker
            
            # Build analysis section
            setup_name = signal.setup_type.value.replace('_', ' ').title()
            confluence = "High Confluence" if signal.confidence >= 92 else "Medium Confluence" if signal.confidence >= 85 else "Low Confluence"
            regime = "Volatile" if signal.atr and signal.atr > signal.entry_price * 0.02 else "Trending"
            structure = "Uptrend" if signal.direction.value == "LONG" else "Downtrend"
            
            tp2_line = f"TP2: ${signal.take_profit_2:.8f}" if signal.take_profit_2 else ""
            tp3_line = f"TP3: ${signal.take_profit_3:.8f}" if signal.take_profit_3 else ""
            
            # Parse market context if available
            market_ctx = signal.market_context or ""
            fear_greed = "N/A"
            btc_24h = "N/A"
            market_24h = "N/A"
            news_sentiment = "N/A"
            warnings = ""
            high_impact = False
            
            if market_ctx:
                if "Fear" in market_ctx or "Greed" in market_ctx:
                    for line in market_ctx.split('\n'):
                        if "Fear" in line or "Greed" in line:
                            fear_greed = line.strip()
                            break
                if "BTC" in market_ctx:
                    for line in market_ctx.split('\n'):
                        if "BTC" in line and "%" in line:
                            btc_24h = line.strip()
                            break
                if "Market 24h" in market_ctx or "24h" in market_ctx:
                    for line in market_ctx.split('\n'):
                        if "24h" in line and "%" in line:
                            market_24h = line.strip()
                            break
                if "News" in market_ctx:
                    for line in market_ctx.split('\n'):
                        if "News" in line:
                            news_sentiment = line.strip()
                            break
                if "Warning" in market_ctx or "caution" in market_ctx.lower():
                    warnings = "⚠️ Market fear detected"
                if "HIGH-IMPACT" in market_ctx.upper() or "high-impact" in market_ctx.lower():
                    high_impact = True
            
            # Chart link
            chart_link = signal.chart_url or ""
            chart_section = f"\n📊 <a href='{chart_link}'>View Chart</a>\n" if chart_link else ""
            
            # Entry type and instructions
            if signal.is_limit_order:
                entry_type = "⏳ <b>LIMIT ORDER</b>"
                entry_instruction = f"Set limit order at ${signal.entry_price:.8f} — wait for retest"
            else:
                entry_type = "⚡ <b>MARKET ENTRY</b>"
                entry_instruction = f"Enter now at market price (~${signal.entry_price:.8f})"
            
            # Setup-specific entry context
            setup_context = ""
            if signal.setup_type.value == "breakout_retest":
                setup_context = "📍 Entry: Breakout retest zone"
            elif signal.setup_type.value == "liquidity_sweep":
                setup_context = "📍 Entry: After liquidity sweep"
            elif signal.setup_type.value == "fair_value_gap":
                setup_context = "📍 Entry: FVG fill zone"
            
            message = f"""
{exclusive_header}{direction_emoji} <b>VIP SIGNAL</b> {direction_emoji}

<a href="{link}"><b>#{ticker}</b></a>
<b>Direction:</b> {signal.direction.value}
<b>Timeframe:</b> {signal.timeframe}

{entry_type}
💰 <b>Entry:</b> ${signal.entry_price:.8f}
{setup_context}
🔹 <i>{entry_instruction}</i>

🛑 <b>Stop Loss:</b> ${signal.stop_loss:.8f}

🎯 <b>Targets:</b>
TP1: ${signal.take_profit_1:.8f}
{tp2_line}
{tp3_line}

📊 <b>Risk/Reward:</b> 1:{signal.risk_reward:.2f}
⚡ <b>Confidence:</b> {signal.confidence:.1f}%
{chart_section}
<b>📋 Analysis:</b>
{signal.reasoning or 'Analysis loading...'}

<b>📊 Market Context:</b>
{fear_greed}
{btc_24h}
{market_24h}
{news_sentiment}
{warnings}
{'🔴 HIGH-IMPACT NEWS DETECTED - Exercise caution' if high_impact else ''}

⚠️ <b>Risk Management:</b>
• Use proper position sizing
• Never risk more than 2% per trade
• Move SL to breakeven after TP1

💡 <b>New to trading?</b> <a href="https://t.me/{settings.TELEGRAM_VIP_BOT_USERNAME or 'CryptoPulseVIPAccessBot'}">DM @CryptoPulseVIPAccessBot</a> and type /guide

<i>Signal ID: {(signal.id[:8] if signal.id else 'MANUAL')}</i>
"""
        else:
            link = self._get_exchange_link(signal.symbol)
            ticker = signal.symbol.replace('/', '')
            self._current_symbol = ticker
            
            message = f"""
{direction_emoji} <b>FREE SIGNAL</b> {direction_emoji}

<a href="{link}"><b>#{ticker}</b></a> | {signal.direction.value}

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
            cta = self._get_referral_cta()
            
            if signal.confidence < 85 and signal.free_channel_message_id:
                free_text = f"📢 <b>UPDATE - {signal.symbol}</b>\n\n{update_text}"
                free_text += cta
                await self.bot.send_message(
                    chat_id=self.free_channel_id,
                    text=free_text,
                    parse_mode='HTML'
                )
            
            if signal.vip_channel_message_id:
                vip_text = f"📢 <b>UPDATE - {signal.symbol}</b>\n\n{update_text}"
                vip_text += cta
                await self.bot.send_message(
                    chat_id=self.vip_channel_id,
                    text=vip_text,
                    parse_mode='HTML'
                )
            
            logger.info(f"Updated signal {signal.symbol} in channels")
            
        except Exception as e:
            logger.error(f"Error updating signal: {e}")
    
    async def send_tp_hit(self, signal: TradingSignal, tp_level: int):
        dedup_key = f"{signal.id}:tp{tp_level}"
        if dedup_key in self._sent_notifications:
            logger.debug(f"🛡️ Deduplicating TP{tp_level} hit for {signal.symbol}")
            return
        self._sent_notifications.add(dedup_key)
        
        # VIP channel gets full update
        tp_val = getattr(signal, f'take_profit_{tp_level}', None)
        tp_str = f"${tp_val:.4f}" if tp_val is not None else "N/A"
        vip_text = f"🎯 <b>TP{tp_level} HIT</b> | {signal.symbol}\n"
        vip_text += f"Target {tp_str} reached"
        
        if tp_level == 1:
            vip_text += "\n➡️ Next: TP2, TP3 | SL → breakeven suggested"
        elif tp_level == 2:
            vip_text += "\n➡️ Next: TP3"
        elif tp_level == 3:
            vip_text += "\n✅ Full position closed"
        
        # Send to VIP
        vip_text += self._get_referral_cta()
        if signal.vip_channel_message_id:
            await self.bot.send_message(
                chat_id=self.vip_channel_id,
                text=vip_text,
                parse_mode='HTML'
            )
        
        # Free channel only gets TP1 with marketing — ONLY for free signals (<85% conf)
        # VIP signals: trade lifecycle stays in VIP channel only
        if tp_level == 1 and signal.confidence < 85 and signal.free_channel_message_id:
            tp_val = getattr(signal, f'take_profit_{tp_level}', None)
            tp_str = f"${tp_val:.4f}" if tp_val is not None else "N/A"
            free_text = f"🎉 <b>{signal.symbol} TP1 HIT!</b>\n\n"
            free_text += f"Target {tp_str} reached\n\n"
            free_text += "💎 <b>Want TP2, TP3 and live updates?</b>\n"
            free_text += "Join VIP for full trade management!\n\n"
            free_text += f"👉 DM @{settings.TELEGRAM_VIP_BOT_USERNAME} for VIP access"
            free_text += self._get_referral_cta()
            
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
        
        dedup_key = f"{signal.id}:tp{tp_level}_free"
        if dedup_key in self._sent_notifications:
            return
        self._sent_notifications.add(dedup_key)
        
        tp_val = getattr(signal, f'take_profit_{tp_level}', None)
        tp_str = f"${tp_val:.4f}" if tp_val is not None else "N/A"
        free_text = f"🎯 <b>{signal.symbol} TP{tp_level} HIT</b>\nTarget {tp_str} reached\n\n"
        free_text += f"Want full signals? DM @{settings.TELEGRAM_VIP_BOT_USERNAME or 'CryptoPulseVIPBot'}"
        free_text += self._get_referral_cta()
        
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
        dedup_key = f"{signal.id}:closed"
        if dedup_key in self._sent_notifications:
            logger.debug(f"🛡️ Deduplicating trade close for {signal.symbol}")
            return
        self._sent_notifications.add(dedup_key)
        
        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        
        # Full details message
        full_text = (
            f"{'✅' if pnl > 0 else '❌'} <b>TRADE CLOSED</b> | {signal.symbol} {signal.direction.value}\n"
            f"Result: {result}\n"
            f"Entry: ${signal.actual_entry or signal.entry_price:.4f} → Exit: ${signal.actual_exit or signal.entry_price:.4f}\n"
            f"P&L: {pnl_emoji} {pnl:+.2f}%\n"
            f"Closed: {datetime.utcnow().strftime('%H:%M UTC')}"
        )
        full_text += self._get_referral_cta()
        
        # Teaser message for free channel
        teaser_text = (
            f"{'✅' if pnl > 0 else '❌'} <b>TRADE CLOSED</b> | {signal.symbol}\n"
            f"P&L: {pnl_emoji} {pnl:+.2f}%\n\n"
            f"Want full signals? DM @{settings.TELEGRAM_VIP_BOT_USERNAME or 'CryptoPulseVIPBot'}"
        )
        teaser_text += self._get_referral_cta()
        
        # Route based on signal confidence
        if signal.confidence < 85:
            # Free channel signal - send full details to free channel only
            try:
                if self.free_channel_id:
                    await self.bot.send_message(
                        chat_id=self.free_channel_id,
                        text=full_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info(f"Trade closed sent to FREE (full): {signal.symbol} ({pnl:+.2f}%, conf: {signal.confidence:.1f}%)")
            except Exception as e:
                logger.error(f"Error sending trade close to Free: {e}")
        else:
            # VIP signal - send full to VIP, teaser to free
            try:
                if self.vip_channel_id:
                    await self.bot.send_message(
                        chat_id=self.vip_channel_id,
                        text=full_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info(f"Trade closed sent to VIP: {signal.symbol} ({pnl:+.2f}%)")
            except Exception as e:
                logger.error(f"Error sending trade close to VIP: {e}")
            
            try:
                if self.free_channel_id:
                    await self.bot.send_message(
                        chat_id=self.free_channel_id,
                        text=teaser_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info(f"Trade closed teaser sent to Free: {signal.symbol} ({pnl:+.2f}%)")
            except Exception as e:
                logger.error(f"Error sending trade close teaser to Free: {e}")
