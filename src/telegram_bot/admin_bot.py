import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, ChatMemberHandler, filters
)
from telegram.error import NetworkError
from datetime import datetime, timedelta
from typing import Optional
from src.models.signal import TradingSignal, SignalStatus
from src.config import settings
from src.utils.logger import get_logger
from src.telegram_bot.chart_generator import ChartGenerator
from src.payments.crypto_payment_handler import CryptoPaymentHandler
from src.marketing.welcome_sequence import WelcomeSequence

logger = get_logger(__name__)


class AdminBot:
    def __init__(self, signal_callback=None, rejection_callback=None):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.admin_chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
        self.signal_callback = signal_callback
        self.rejection_callback = rejection_callback
        
        self.app = None
        self.chart_generator = ChartGenerator()
        self.payment_handler = CryptoPaymentHandler()
        self.welcome_sequence = WelcomeSequence()
        
        self.pending_signals = {}
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Suppress repetitive network error spam; log at debug level only."""
        error = context.error
        if isinstance(error, NetworkError) or 'ConnectError' in str(type(error)) or 'getaddrinfo' in str(error):
            logger.debug(f"Network hiccup (auto-retrying): {error}")
        else:
            logger.error(f"Bot error: {error}", exc_info=True)

    async def initialize(self):
        logger.info("Initializing admin bot...")
        
        self.app = (
            Application.builder()
            .token(self.bot_token)
            .connect_timeout(30)
            .read_timeout(30)
            .get_updates_connect_timeout(30)
            .get_updates_read_timeout(30)
            .build()
        )
        
        self.app.add_error_handler(self._error_handler)
        
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("vip", self.vip_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("testtwitter", self.test_twitter_command))
        self.app.add_handler(CommandHandler("dashboard", self.dashboard_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Welcome new members to free channel
        self.app.add_handler(
            ChatMemberHandler(self._handle_chat_member, ChatMemberHandler.CHAT_MEMBER)
        )
        
        # Handle regular user DMs (non-admin)
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL, self.handle_user_message)
        )
        
        await self.app.initialize()
        await self.app.start()
        
        # Delete any existing webhook before polling
        await self.app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared existing webhooks")
        
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("Admin bot initialized and running")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        
        if user_id == self.admin_chat_id:
            # Admin welcome
            await update.message.reply_text(
                "🤖 CRYPTO PULSE SIGNALS Admin Bot\n\n"
                "I will send you trading signal candidates for approval.\n\n"
                "Commands:\n"
                "/status - Check bot status\n"
            )
        else:
            # Regular user welcome
            keyboard = [
                [InlineKeyboardButton("💎 Join VIP", callback_data=f"vip_request_{user_id}")],
                [InlineKeyboardButton("📊 See Plans", callback_data=f"vip_plans_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🚀 <b>Welcome to Crypto Pulse Signals!</b>\n\n"
                "📢 Free Channel: Get trade teasers and market updates\n"
                "💎 VIP Channel: Get full signals with entry, SL, 3 TPs\n\n"
                "✅ 90%+ confidence signals\n"
                "✅ 1-3 elite setups per day\n"
                "✅ Real-time trade updates\n"
                "✅ Pre-market outlook\n\n"
                "Click below to join VIP!",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send admin the dashboard URL with a button to open it."""
        user_id = str(update.effective_user.id)
        if user_id != self.admin_chat_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        port = getattr(settings, 'ADMIN_DASHBOARD_PORT', 8080)
        url = f"http://localhost:{port}"
        
        keyboard = [[InlineKeyboardButton("🎛️ Open Dashboard", url=url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎛️ <b>Admin Dashboard</b>\n\n"
            f"Open in your browser:\n<code>{url}</code>\n\n"
            f"You can also bookmark this URL.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP pricing and let user pick crypto for invoice"""
        user_id = str(update.effective_user.id)
        username = update.effective_user.username or "N/A"
        
        # Build crypto selection keyboard
        keyboard = []
        available_coins = []
        
        if settings.CRYPTO_WALLET_BTC:
            keyboard.append([InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data=f"pay_BTC_{user_id}")])
            available_coins.append("BTC")
        if settings.CRYPTO_WALLET_ETH:
            keyboard.append([InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data=f"pay_ETH_{user_id}")])
            available_coins.append("ETH")
        if settings.CRYPTO_WALLET_SOL:
            keyboard.append([InlineKeyboardButton("◎ Solana (SOL)", callback_data=f"pay_SOL_{user_id}")])
            available_coins.append("SOL")
        if settings.CRYPTO_WALLET_LTC:
            keyboard.append([InlineKeyboardButton("Ł Litecoin (LTC)", callback_data=f"pay_LTC_{user_id}")])
            available_coins.append("LTC")
        
        if not available_coins:
            await update.message.reply_text(
                "💎 <b>VIP Access</b>\n\n"
                "Payment setup is being configured.\n"
                "Please contact admin for manual activation.",
                parse_mode='HTML'
            )
            return
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💎 <b>VIP Subscription</b>\n\n"
            "🥉 <b>Monthly</b> - $49/month\n"
            "🥈 <b>Quarterly</b> - $129/3 months (Save 12%)\n"
            "🥇 <b>Lifetime</b> - $299 one-time\n\n"
            "✅ Full signals with entry, SL, 3 TPs\n"
            "✅ 90%+ confidence elite setups\n"
            "✅ Real-time trade updates\n"
            "✅ Weekly performance reports\n\n"
            "<b>Select cryptocurrency to pay:</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Notify admin
        await self.send_notification(
            f"📩 <b>New VIP Interest!</b>\n"
            f"User ID: {user_id}\n"
            f"Username: @{username}\n"
            f"Clicked /vip command."
        )
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pricing plans"""
        await update.message.reply_text(
            "💎 <b>VIP Pricing Plans</b>\n\n"
            "🥉 <b>Monthly</b> - $49/month\n"
            "Full access to all signals\n\n"
            "🥈 <b>Quarterly</b> - $129/3 months\n"
            "Save 12% + bonus reports\n\n"
            "🥇 <b>Lifetime</b> - $299 one-time\n"
            "Never pay again\n\n"
            "💰 Crypto payments accepted:\n"
            "BTC, ETH, SOL, LTC\n\n"
            "👉 DM @{settings.TELEGRAM_BOT_USERNAME} with /vip for payment",
            parse_mode='HTML'
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        
        if user_id == self.admin_chat_id:
            pending_count = len(self.pending_signals)
            await update.message.reply_text(
                f"✅ Bot is running\n"
                f"📊 Pending signals: {pending_count}\n"
                f"⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
        else:
            await update.message.reply_text(
                "🤖 I'm your VIP signup assistant!\n\n"
                "Type /vip to see payment options\n"
                "Type /price to see plans"
            )
    
    async def handle_user_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle DMs from regular users (non-admin)"""
        user_id = str(update.effective_user.id)
        
        if user_id == self.admin_chat_id:
            return  # Admin messages handled elsewhere
        
        text = update.message.text
        
        # If user sends a TXID (looks like a hash), forward to admin
        if len(text) > 20 and any(c in text for c in '0123456789abcdefABCDEF'):
            await self.send_notification(
                f"💰 <b>Possible Payment TXID!</b>\n\n"
                f"User: {update.effective_user.username or user_id}\n"
                f"User ID: {user_id}\n"
                f"Message: <code>{text}</code>\n\n"
                f"⚠️ Check and activate VIP if valid."
            )
            await update.message.reply_text(
                "✅ Payment received! Forwarding to admin for verification.\n"
                "You'll get VIP access within 24 hours.\n\n"
                "Thank you! 🙏"
            )
        else:
            # Generic response
            keyboard = [
                [InlineKeyboardButton("💎 Join VIP", callback_data=f"vip_request_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🤖 Hi! I'm the Crypto Pulse VIP assistant.\n\n"
                "Want VIP access? Click below!",
                reply_markup=reply_markup
            )
    
    async def send_signal_for_approval(self, signal: TradingSignal) -> bool:
        try:
            self.pending_signals[signal.id] = signal
            
            # Format approval message (condensed to fit in caption)
            approval_message = self._format_signal_message(signal)
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{signal.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{signal.id}")
                ],
                [
                    InlineKeyboardButton("⏰ Delay 5min", callback_data=f"delay_{signal.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            chart_path = await self.chart_generator.generate_chart(signal)
            
            if chart_path:
                # Send photo with approval message as caption
                with open(chart_path, 'rb') as photo:
                    await self.app.bot.send_photo(
                        chat_id=self.admin_chat_id,
                        photo=photo,
                        caption=approval_message,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
            else:
                # No chart: send as text message
                await self.app.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=approval_message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            
            logger.info(f"Sent signal {signal.symbol} to admin for approval")
            return True
            
        except Exception as e:
            logger.error(f"Error sending signal for approval: {e}")
            # Fallback: send simple text notification so admin knows a signal is waiting
            try:
                await self.send_notification(
                    f"⚠️ <b>Signal approval message failed</b>\n\n"
                    f"Symbol: {signal.symbol} {signal.direction.value}\n"
                    f"ID: {signal.id}\n"
                    f"Check dashboard to approve/reject.\n\n"
                    f"Error: {str(e)[:100]}"
                )
            except Exception as fallback_err:
                logger.error(f"Fallback notification also failed: {fallback_err}")
            return False
    
    def _format_signal_message(self, signal: TradingSignal) -> str:
        """Condensed approval message that fits in 1024 char Telegram caption limit"""
        direction_emoji = "🟢" if signal.direction.value == "LONG" else "🔴"
        
        tp2_str = f"${signal.take_profit_2:.8f}" if signal.take_profit_2 is not None else "N/A"
        tp3_str = f"${signal.take_profit_3:.8f}" if signal.take_profit_3 is not None else "N/A"
        
        # Entry type indicator
        if signal.is_limit_order:
            entry_type = "⏳ LIMIT"
        else:
            entry_type = "⚡ MARKET"
        
        # Truncate reasoning to fit in caption
        reasoning_short = signal.reasoning[:150] + "..." if len(signal.reasoning) > 150 else signal.reasoning
        
        message = f"""{direction_emoji} <b>SIGNAL CANDIDATE</b> {direction_emoji}

<b>{signal.symbol}</b> | {signal.direction.value} | {signal.timeframe}
<b>Setup:</b> {signal.setup_type.value.replace('_', ' ').title()}

{entry_type} <b>ENTRY:</b> ${signal.entry_price:.8f}
🛑 <b>SL:</b> ${signal.stop_loss:.8f}
🎯 <b>TP1:</b> ${signal.take_profit_1:.8f}
🎯 <b>TP2:</b> {tp2_str}
🎯 <b>TP3:</b> {tp3_str}

📊 <b>R/R:</b> 1:{signal.risk_reward:.2f} | ⚡ <b>Conf:</b> {signal.confidence:.1f}%

<b>Tech:</b> {signal.technical_score.total_score:.0f}/100 (T:{signal.technical_score.trend_score:.0f} V:{signal.technical_score.volume_score:.0f} M:{signal.technical_score.momentum_score:.0f} S:{signal.technical_score.structure_score:.0f})
<b>Context:</b> {signal.context_score.total_score:.0f}/100 (M:{signal.context_score.macro_score:.0f} N:{signal.context_score.news_score:.0f} S:{signal.context_score.sentiment_score:.0f})

<b>Analysis:</b>
{reasoning_short}
"""
        return message.strip()
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Handle VIP signup callbacks
        if data.startswith("vip_request_"):
            await self._handle_vip_request(query, update.effective_user.id)
            return
        elif data.startswith("vip_plans_"):
            await self._handle_vip_plans(query)
            return
        elif data.startswith("pay_"):
            # Format: pay_BTC_userid
            parts = data.split("_")
            if len(parts) >= 3:
                crypto = parts[1]
                user_id = parts[2]
                await self._handle_payment_selection(query, user_id, crypto)
                return
        
        # Handle signal approval callbacks
        action, signal_id = data.split('_', 1)
        
        if signal_id not in self.pending_signals:
            await query.edit_message_caption(
                caption="❌ Signal expired or already processed"
            )
            return
        
        signal = self.pending_signals[signal_id]
        
        if action == "approve":
            await self._handle_approve(query, signal)
        elif action == "reject":
            await self._handle_reject(query, signal)
        elif action == "delay":
            await self._handle_delay(query, signal)
    
    async def _handle_vip_request(self, query, user_id):
        """Handle VIP join request - show crypto selection"""
        # Build crypto selection keyboard
        keyboard = []
        available_coins = []
        
        if settings.CRYPTO_WALLET_BTC:
            keyboard.append([InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data=f"pay_BTC_{user_id}")])
            available_coins.append("BTC")
        if settings.CRYPTO_WALLET_ETH:
            keyboard.append([InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data=f"pay_ETH_{user_id}")])
            available_coins.append("ETH")
        if settings.CRYPTO_WALLET_SOL:
            keyboard.append([InlineKeyboardButton("◎ Solana (SOL)", callback_data=f"pay_SOL_{user_id}")])
            available_coins.append("SOL")
        if settings.CRYPTO_WALLET_LTC:
            keyboard.append([InlineKeyboardButton("Ł Litecoin (LTC)", callback_data=f"pay_LTC_{user_id}")])
            available_coins.append("LTC")
        
        if not available_coins:
            await query.edit_message_text(
                text="💎 <b>VIP Access</b>\n\n"
                     "Payment setup is being configured.\n"
                     "Please contact admin for manual activation.",
                parse_mode='HTML'
            )
            return
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="💎 <b>VIP Subscription</b>\n\n"
                 "🥉 <b>Monthly</b> - $49/month\n"
                 "🥈 <b>Quarterly</b> - $129/3 months (Save 12%)\n"
                 "🥇 <b>Lifetime</b> - $299 one-time\n\n"
                 "✅ Full signals with entry, SL, 3 TPs\n"
                 "✅ 90%+ confidence elite setups\n"
                 "✅ Real-time trade updates\n"
                 "✅ Weekly performance reports\n\n"
                 "<b>Select cryptocurrency to pay:</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Notify admin
        await self.send_notification(
            f"📩 <b>New VIP Interest!</b>\n"
            f"User ID: {user_id}\n"
            f"Clicked 'Join VIP' button."
        )
    
    async def _handle_vip_plans(self, query):
        """Show VIP pricing plans"""
        await query.edit_message_text(
            text="💎 <b>VIP Pricing Plans</b>\n\n"
            "🥉 <b>Monthly</b> - $49/month\n"
            "Full access to all signals\n\n"
            "🥈 <b>Quarterly</b> - $129/3 months\n"
            "Save 12% + bonus reports\n\n"
            "🥇 <b>Lifetime</b> - $299 one-time\n"
            "Never pay again\n\n"
            "💰 Crypto payments accepted:\n"
            "BTC, ETH, SOL, LTC\n\n"
            f"👉 DM @{settings.TELEGRAM_BOT_USERNAME} with /vip for payment",
            parse_mode='HTML'
        )
    
    async def _handle_payment_selection(self, query, user_id: str, crypto: str):
        """Generate payment invoice with exact crypto amount"""
        try:
            # Get user info from query
            username = query.from_user.username or "N/A"
            
            # Generate invoice
            invoice = await self.payment_handler.generate_payment_invoice(
                user_id=user_id,
                telegram_username=username,
                crypto=crypto
            )
            
            if not invoice:
                await query.edit_message_text(
                    text="❌ Error generating payment invoice.\n"
                         "Please try again or contact admin.",
                    parse_mode='HTML'
                )
                return
            
            # Build payment message
            coin_name = self.payment_handler.SUPPORTED_COINS[crypto]['name']
            network = self.payment_handler.SUPPORTED_COINS[crypto]['network']
            
            payment_text = f"""💎 <b>VIP Payment Invoice</b>

<b>Plan:</b> Monthly VIP Access
<b>Amount:</b> <code>{invoice['amount']}</code> {crypto}
<b>USD Value:</b> ${invoice['usd_value']:.2f}
<b>Network:</b> {network.title()}

<b>Send To:</b>
<code>{invoice['wallet_address']}</code>

⚠️ <b>IMPORTANT:</b>
• Send EXACTLY {invoice['amount']} {crypto}
• Use {network.title()} network ONLY
• Payment expires in 24 hours
• After sending, reply with your transaction hash

<b>Invoice ID:</b> <code>{invoice['invoice_id']}</code>

✅ Once confirmed, VIP access is activated within 1 hour."""
            
            await query.edit_message_text(
                text=payment_text,
                parse_mode='HTML'
            )
            
            # Notify admin
            await self.send_notification(
                f"💰 <b>New Payment Invoice Created!</b>\n\n"
                f"User: @{username}\n"
                f"User ID: {user_id}\n"
                f"Crypto: {crypto}\n"
                f"Amount: {invoice['amount']} {crypto}\n"
                f"USD: ${invoice['usd_value']:.2f}\n"
                f"Invoice ID: {invoice['invoice_id']}"
            )
            
        except Exception as e:
            logger.error(f"Error generating payment invoice: {e}")
            await query.edit_message_text(
                text="❌ Error creating invoice. Please contact admin.",
                parse_mode='HTML'
            )
    
    async def _handle_approve(self, query, signal: TradingSignal):
        signal.status = SignalStatus.APPROVED
        signal.approved_at = datetime.utcnow()
        
        del self.pending_signals[signal.id]
        
        await query.edit_message_caption(
            caption=f"✅ <b>APPROVED</b>\n\n{query.message.caption}",
            parse_mode='HTML'
        )
        
        if self.signal_callback:
            await self.signal_callback(signal)
        
        logger.info(f"Signal {signal.symbol} approved by admin")
    
    async def _handle_reject(self, query, signal: TradingSignal):
        signal.status = SignalStatus.REJECTED
        
        del self.pending_signals[signal.id]
        
        await query.edit_message_caption(
            caption=f"❌ <b>REJECTED</b>\n\n{query.message.caption}",
            parse_mode='HTML'
        )
        
        if self.rejection_callback:
            await self.rejection_callback(signal)
        
        logger.info(f"Signal {signal.symbol} rejected by admin")
    
    async def _handle_delay(self, query, signal: TradingSignal):
        await query.edit_message_caption(
            caption=f"⏰ <b>DELAYED 5 MINUTES</b>\n\n{query.message.caption}",
            parse_mode='HTML'
        )
        
        await asyncio.sleep(300)
        
        if signal.id in self.pending_signals:
            await self.send_signal_for_approval(signal)
        
        logger.info(f"Signal {signal.symbol} delayed by admin")
    
    async def test_twitter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin diagnostic: Test Twitter/X API connection"""
        user_id = str(update.effective_user.id)
        if user_id != self.admin_chat_id:
            await update.message.reply_text("❌ Admin only")
            return
        
        await update.message.reply_text("🧪 Testing Twitter/X API connection...")
        
        try:
            from src.marketing.social_media_poster import SocialMediaPoster
            poster = SocialMediaPoster()
            result = await poster.test_twitter_connection()
            
            # Build diagnostic message
            msg_parts = ["<b>Twitter/X API Diagnostic</b>\n"]
            msg_parts.append(f"tweepy installed: {'✅' if result.get('tweepy_installed') else '❌'}")
            if result.get('tweepy_version'):
                msg_parts.append(f"  Version: {result['tweepy_version']}")
            msg_parts.append(f"Credentials set: {'✅' if result.get('credentials_set') else '❌'}")
            msg_parts.append(f"API initialized: {'✅' if result.get('api_initialized') else '❌'}")
            msg_parts.append(f"Can read user: {'✅' if result.get('can_read_user') else '❌'}")
            if result.get('username'):
                msg_parts.append(f"  Connected as: @{result['username']}")
            msg_parts.append(f"Can post tweet: {'✅' if result.get('can_post_tweet') else '❌'}")
            if result.get('test_tweet_url'):
                msg_parts.append(f"  Test tweet: {result['test_tweet_url']}")
            
            if result.get('errors'):
                msg_parts.append("\n<b>❌ ERRORS:</b>")
                for err in result['errors']:
                    msg_parts.append(f"• {err}")
            
            if result.get('can_post_tweet'):
                msg_parts.append("\n✅ <b>Twitter is working!</b> Signals will auto-post.")
            else:
                msg_parts.append("\n⚠️ <b>Twitter posting will NOT work.</b> Fix the errors above.")
            
            await update.message.reply_text('\n'.join(msg_parts), parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Test error: {str(e)[:500]}")
    
    async def send_notification(self, message: str):
        try:
            await self.app.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    async def _handle_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detect new members joining the free channel and trigger welcome DM sequence."""
        try:
            # Only handle joins to the free channel
            if str(update.chat_member.chat.id) != settings.TELEGRAM_FREE_CHANNEL_ID:
                return
            
            old_status = update.chat_member.old_chat_member.status
            new_status = update.chat_member.new_chat_member.status
            
            # User joined (was not member, now is)
            if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator']:
                user = update.chat_member.new_chat_member.user
                user_id = user.id
                username = user.username
                
                # Wire bot instance and trigger sequence
                if not self.welcome_sequence.bot:
                    self.welcome_sequence.bot = self.app.bot
                
                # Fire-and-forget the 3-step sequence
                asyncio.create_task(self.welcome_sequence.on_new_member(user_id, username))
                logger.info(f"Welcome sequence triggered for new member {user_id} (@{username})")
        except Exception as e:
            logger.error(f"Chat member handler error: {e}")

    async def close(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        logger.info("Admin bot closed")
