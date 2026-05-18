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
        self.vip_channel_id = getattr(settings, 'TELEGRAM_DEGEN_VIP_CHANNEL_ID', None)
        self.free_channel_id = getattr(settings, 'TELEGRAM_DEGEN_CHANNEL_ID', None)
        
        if not self.vip_channel_id:
            logger.warning("TELEGRAM_DEGEN_VIP_CHANNEL_ID not set - alpha VIP publishing disabled")
        if not self.free_channel_id:
            logger.warning("TELEGRAM_DEGEN_CHANNEL_ID not set - alpha FREE publishing disabled")
    
    async def publish_alpha_vip(self, message: str) -> Optional[int]:
        """
        Publish alpha play to VIP degen channel.
        
        Args:
            message: Formatted message text
        
        Returns:
            Message ID if sent, None otherwise
        """
        if not self.bot or not self.vip_channel_id:
            logger.warning("Cannot publish alpha VIP - bot or channel ID missing")
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
        if not self.bot or not self.free_channel_id:
            logger.warning("Cannot publish alpha FREE - bot or channel ID missing")
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
            
            logger.info(f"Alpha result teaser sent to FREE for {play.candidate.symbol}")
            
        except Exception as e:
            logger.error(f"Error sending alpha result to FREE: {e}")
