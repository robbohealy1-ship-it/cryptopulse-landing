"""
Welcome DM Sequence for new free channel joiners.
Sends a 3-step onboarding sequence to convert free users to VIP.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WelcomeSequence:
    """
    Automated DM sequence for new free channel members.
    Step 1 (instant): Welcome + what to expect
    Step 2 (2 hours): Social proof + first signal teaser
    Step 3 (24 hours): Urgency + limited offer
    """

    def __init__(self, bot=None, db=None):
        self.bot = bot
        self.db = db
        self._sent_sequences = set()  # Track user_ids who've received welcome

    async def on_new_member(self, user_id: int, username: str = None):
        """Trigger welcome sequence when someone joins the free channel."""
        if user_id in self._sent_sequences:
            return
        self._sent_sequences.add(user_id)

        if not self.bot:
            logger.warning("WelcomeSequence: bot not available")
            return

        try:
            # Step 1: Immediate welcome
            await self._send_step_1(user_id, username)

            # Step 2: After 2 hours
            await asyncio.sleep(7200)
            await self._send_step_2(user_id, username)

            # Step 3: After 24 hours total
            await asyncio.sleep(79200)
            await self._send_step_3(user_id, username)

        except Exception as e:
            logger.error(f"Welcome sequence error for {user_id}: {e}")

    async def _send_step_1(self, user_id: int, username: str = None):
        """Immediate welcome - set expectations, no hard sell."""
        name = f"@{username}" if username else "there"
        mexc_url = getattr(settings, 'AFFILIATE_CUSTOM_URL', None)
        mexc_line = f"\n💎 <a href='{mexc_url}'>Trade on MEXC</a> — low fees, deep liquidity\n" if mexc_url else ""
        
        text = (
            f"🚀 <b>Welcome to CryptoPulse, {name}!</b>\n\n"
            f"You just joined the <b>only</b> free signals channel that doesn't spam.\n\n"
            f"<b>Here's what happens next:</b>\n"
            f"📊 1-2 high-quality signals per day (entry + SL only)\n"
            f"🎯 10-minute delay after VIP — you'll see the teaser\n"
            f"📈 Morning market outlook + evening summary\n"
            f"📰 Key headlines + funding data daily\n\n"
            f"<b>Why traders upgrade to VIP:</b>\n"
            f"✅ Instant signals (no delay)\n"
            f"✅ Entry + SL + 3 TP levels\n"
            f"✅ Live TP/SL hit alerts\n"
            f"✅ Weekly P&L reports\n"
            f"✅ 85%+ confidence, institutional-grade analysis\n\n"
            f"🤖 <a href='https://t.me/CryptoPulseVIPAccessBot'>@CryptoPulseVIPAccessBot</a>\n"
            f"💳 Card or Crypto — instant access"
            f"{mexc_line}"
        )
        try:
            await self.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
            logger.info(f"Welcome Step 1 sent to {user_id}")
        except Exception as e:
            logger.debug(f"Welcome Step 1 failed for {user_id}: {e}")

    async def _send_step_2(self, user_id: int, username: str = None):
        """2 hours later: social proof + what they missed."""
        # Try to get real stats from DB
        stats = {}
        if self.db:
            try:
                stats = await self.db.get_daily_stats()
            except Exception:
                pass

        win_rate = stats.get('win_rate', 85)
        signals = stats.get('approved', 2)

        text = (
            f"📊 <b>How's your first day?</b>\n\n"
            f"Today we delivered <b>{signals} signals</b> with a <b>{win_rate:.0f}% win rate</b>.\n\n"
            f"<b>What you saw in the free channel:</b>\n"
            f"• Entry price + Stop loss\n"
            f"• 10-minute delay\n\n"
            f"<b>What VIP members got:</b>\n"
            f"• Same entry, same SL\n"
            f"• <b>PLUS</b> 3 take-profit levels\n"
            f"• <b>PLUS</b> live alerts when TP1/TP2/TP3 hit\n"
            f"• <b>PLUS</b> position sizing guidance\n\n"
            f"The difference? VIP banked the full move. Free watched the teaser.\n\n"
            f"🤖 <a href='https://t.me/CryptoPulseVIPAccessBot'>Upgrade to VIP</a> — $49/mo, cancel anytime"
        )
        try:
            await self.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
            logger.info(f"Welcome Step 2 sent to {user_id}")
        except Exception as e:
            logger.debug(f"Welcome Step 2 failed for {user_id}: {e}")

    async def _send_step_3(self, user_id: int, username: str = None):
        """24 hours later: urgency + limited-time offer."""
        text = (
            f"⏰ <b>24-Hour VIP Offer</b>\n\n"
            f"You've been in the free channel for a day.\n"
            f"You've seen the quality. You've seen the delay.\n\n"
            f"<b>Here's the truth:</b>\n"
            f"Free signals are teasers by design.\n"
            f"We want you to see the quality — then upgrade for the full plan.\n\n"
            f"<b>This week only:</b>\n"
            f"🎁 Use code <b>WELCOME20</b> for 20% off your first month\n"
            f"💰 Monthly VIP: <s>$49</s> → <b>$39</b>\n"
            f"🔒 Cancel anytime — no questions asked\n\n"
            f"🤖 <a href='https://t.me/CryptoPulseVIPAccessBot'>Claim your discount</a>\n"
            f"⏳ Offer expires in 24 hours"
        )
        try:
            await self.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
            logger.info(f"Welcome Step 3 sent to {user_id}")
        except Exception as e:
            logger.debug(f"Welcome Step 3 failed for {user_id}: {e}")
