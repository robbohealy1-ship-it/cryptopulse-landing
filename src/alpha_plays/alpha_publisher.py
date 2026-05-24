"""
Alpha Publisher

Handles publishing alpha/degen plays to Telegram channels.
Separate from ChannelPublisher to maintain isolation.
"""

from typing import Optional
from src.utils.logger import get_logger
from src.config import settings
from .alpha_engine import ActiveAlphaPlay

logger = get_logger(__name__)


class AlphaPublisher:
    """
    Publishes alpha plays to VIP and Free Telegram channels.
    """
    
    def __init__(self, bot=None):
        self.bot = bot
        # Use dedicated alpha channels if set, otherwise fall back to main signal channels
        degen_vip = getattr(settings, 'TELEGRAM_DEGEN_VIP_CHANNEL_ID', None)
        main_vip = getattr(settings, 'TELEGRAM_VIP_CHANNEL_ID', None)
        degen_free = getattr(settings, 'TELEGRAM_DEGEN_CHANNEL_ID', None)
        main_free = getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None)
        
        self.vip_channel_id = degen_vip or main_vip
        self.free_channel_id = degen_free or main_free
        
        logger.info(f"AlphaPublisher init — bot={'YES' if bot else 'NO'} | vip_channel={'YES' if self.vip_channel_id else 'NO'} (degen={degen_vip}, main={main_vip}) | free_channel={'YES' if self.free_channel_id else 'NO'} (degen={degen_free}, main={main_free})")
        
        if not self.vip_channel_id:
            logger.warning("No VIP channel configured for alpha (set TELEGRAM_DEGEN_VIP_CHANNEL_ID or TELEGRAM_VIP_CHANNEL_ID)")
        if not self.free_channel_id:
            logger.warning("No FREE channel configured for alpha (set TELEGRAM_DEGEN_CHANNEL_ID or TELEGRAM_FREE_CHANNEL_ID)")
    
    async def publish_alpha_vip(self, message: str) -> Optional[int]:
        """
        Publish alpha play to VIP degen channel.
        
        Args:
            message: Formatted message text
        
        Returns:
            Message ID if sent, None otherwise
        """
        if not self.bot:
            logger.warning("Cannot publish alpha VIP - bot is None (was ChannelPublisher.bot passed to AlphaPublisher init?)")
            return None
        if not self.vip_channel_id:
            logger.warning("Cannot publish alpha VIP - vip_channel_id is None")
            return None
        
        try:
            # Send to VIP channel
            sent = await self.bot.send_message(
                chat_id=self.vip_channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            message_id = sent.message_id
            logger.info(f"Alpha VIP message sent: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error publishing alpha to VIP: {e}")
            return None
    
    async def publish_alpha_free(self, message: str) -> Optional[int]:
        """
        Publish alpha teaser to Free degen channel.
        
        Args:
            message: Formatted teaser text
        
        Returns:
            Message ID if sent, None otherwise
        """
        if not self.bot:
            logger.warning("Cannot publish alpha FREE - bot is None")
            return None
        if not self.free_channel_id:
            logger.warning("Cannot publish alpha FREE - free_channel_id is None")
            return None
        
        try:
            # Send to Free channel
            sent = await self.bot.send_message(
                chat_id=self.free_channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            message_id = sent.message_id
            logger.info(f"Alpha FREE message sent: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error publishing alpha to FREE: {e}")
            return None
    
    async def send_alpha_update(self, play: ActiveAlphaPlay, message: str):
        """
        Send an update about an active alpha play (TP hit, SL hit, etc.).
        Goes to VIP channel as a reply to original message.
        """
        if not self.bot or not self.vip_channel_id:
            return
        
        try:
            # If we have the original message ID, reply to it
            if play.vip_message_id:
                await self.bot.send_message(
                    chat_id=self.vip_channel_id,
                    text=message,
                    parse_mode='HTML',
                    reply_to_message_id=play.vip_message_id,
                    disable_web_page_preview=True
                )
            else:
                await self.bot.send_message(
                    chat_id=self.vip_channel_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            
            logger.info(f"Alpha update sent for {play.candidate.symbol}")
            
        except Exception as e:
            logger.error(f"Error sending alpha update: {e}")
    
    async def publish_alpha_result_vip(self, message: str):
        """
        Publish final result of alpha play to VIP channel.
        """
        if not self.bot or not self.vip_channel_id:
            return
        
        try:
            await self.bot.send_message(
                chat_id=self.vip_channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info("Alpha result sent to VIP")
            
        except Exception as e:
            logger.error(f"Error publishing alpha result: {e}")
    
    async def send_alpha_result_free(self, play: ActiveAlphaPlay, message: str):
        """
        Send result teaser to Free channel.
        """
        if not self.bot or not self.free_channel_id:
            return
        
        try:
            if play.free_message_id:
                await self.bot.send_message(
                    chat_id=self.free_channel_id,
                    text=message,
                    parse_mode='HTML',
                    reply_to_message_id=play.free_message_id,
                    disable_web_page_preview=True
                )
            else:
                await self.bot.send_message(
                    chat_id=self.free_channel_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            logger.info("Alpha result sent to FREE")
            
        except Exception as e:
            logger.error(f"Error publishing alpha result to FREE: {e}")
    
    async def send_portfolio_summary(self, holds: list, total_pnl: float):
        """
        Send weekly portfolio holds summary to VIP channel.
        """
        if not self.bot or not self.vip_channel_id:
            return
        
        if not holds:
            return
        
        try:
            best = max(holds, key=lambda h: h.current_pnl)
            worst = min(holds, key=lambda h: h.current_pnl)
            avg_pnl = sum(h.current_pnl for h in holds) / len(holds)
            
            lines = []
            for h in sorted(holds, key=lambda x: x.current_pnl, reverse=True)[:5]:
                emoji = "🟢" if h.current_pnl >= 0 else "🔴"
                lines.append(f"{emoji} <b>{h.candidate.symbol}</b> | {h.current_pnl:+.1f}%")
            
            message = (
                f"📊 <b>PORTFOLIO HOLD SUMMARY</b>\n\n"
                f"Positions: {len(holds)}\n"
                f"Total P&L: {total_pnl:+.1f}%\n"
                f"Avg P&L: {avg_pnl:+.1f}%\n\n"
                f"🏆 Best: <b>{best.candidate.symbol}</b> | {best.current_pnl:+.1f}%\n"
                f"📉 Worst: <b>{worst.candidate.symbol}</b> | {worst.current_pnl:+.1f}%\n\n"
                f"<b>Top Holdings:</b>\n"
                + "\n".join(lines) +
                f"\n\n<i>Long-term 1-4 week holds. Not financial advice.</i>"
            )
            
            await self.bot.send_message(
                chat_id=self.vip_channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info("Portfolio summary sent to VIP")
            
        except Exception as e:
            logger.error(f"Error sending portfolio summary: {e}")
