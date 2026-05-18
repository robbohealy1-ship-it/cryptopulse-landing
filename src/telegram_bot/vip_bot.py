import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)
from telegram.error import NetworkError
from src.config import settings
from src.utils.logger import get_logger
from src.payments.crypto_payment_handler import CryptoPaymentHandler
from src.payments.stripe_handler import StripeHandler
from src.payments.payment_orchestrator import PaymentOrchestrator
from src.marketing.pro_features import CustomAlertSystem

logger = get_logger(__name__)


class VIPBot:
    """Public-facing VIP signup and payment bot (separate from admin bot)"""
    
    def __init__(self, notification_callback=None):
        self.bot_token = settings.TELEGRAM_VIP_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN
        self.bot_username = settings.TELEGRAM_VIP_BOT_USERNAME or "CryptoPulseVIPBot"
        self.admin_chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
        self.notification_callback = notification_callback
        
        self.app = None
        self.payment_handler = CryptoPaymentHandler()
        self.stripe_handler = StripeHandler() if settings.STRIPE_SECRET_KEY else None
        self.payment_orchestrator = PaymentOrchestrator(
            stripe_handler=self.stripe_handler,
            crypto_handler=self.payment_handler
        )
        # Track which crypto plan user selected so TXID handler knows the tier
        self.pending_crypto_plans = {}
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Suppress repetitive network error spam; log at debug level only."""
        error = context.error
        if isinstance(error, NetworkError) or 'ConnectError' in str(type(error)) or 'getaddrinfo' in str(error):
            logger.debug(f"Network hiccup (auto-retrying): {error}")
        else:
            logger.error(f"VIP bot error: {error}", exc_info=True)

    async def initialize(self):
        logger.info("Initializing VIP bot...")
        
        if not self.bot_token:
            logger.error("TELEGRAM_VIP_BOT_TOKEN not set! VIP bot cannot start.")
            return False
        
        self.app = (
            Application.builder()
            .token(self.bot_token)
            .connect_timeout(30)
            .read_timeout(30)
            .get_updates_connect_timeout(30)
            .get_updates_read_timeout(30)
            .build()
        )
        
        # Custom alert system for lifetime/pro members
        self.custom_alerts = CustomAlertSystem()
        
        self.app.add_error_handler(self._error_handler)
        
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("vip", self.vip_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CommandHandler("alert", self.alert_command))
        self.app.add_handler(CommandHandler("myalerts", self.myalerts_command))
        self.app.add_handler(CommandHandler("removealert", self.removealert_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Handle regular messages (TXID, etc.)
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL, 
                          self.handle_user_message)
        )
        
        await self.app.initialize()
        await self.app.start()
        
        # Delete any existing webhook before polling
        await self.app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared existing webhooks")
        
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info(f"VIP bot @{self.bot_username} initialized and running")
        return True
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message for users DMing the VIP bot"""
        keyboard = [
            [InlineKeyboardButton("💎 Join VIP", callback_data="vip_menu")],
            [InlineKeyboardButton("📊 See Plans", callback_data="vip_plans")],
            [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🚀 <b>Welcome to Crypto Pulse VIP!</b>\n\n"
            "Get elite trading signals delivered straight to your VIP channel.\n\n"
            "✅ 90%+ confidence signals\n"
            "✅ 1-3 elite setups per day\n"
            "✅ Entry, Stop Loss, 3 Take Profits\n"
            "✅ Real-time trade updates\n"
            "✅ Weekly performance reports\n\n"
            "<b>Ready to level up your trading?</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP plan selection first"""
        await self._show_plan_selection(update.message)
        
        # Notify admin
        user = update.effective_user
        await self._notify_admin(
            f"📩 <b>New VIP Interest!</b>\n"
            f"User: @{user.username or 'N/A'}\n"
            f"User ID: {user.id}\n"
            f"Action: /vip command"
        )
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pricing plans"""
        m = settings.VIP_MONTHLY_PRICE
        q = settings.VIP_QUARTERLY_PRICE
        l = settings.VIP_LIFETIME_PRICE
        
        await update.message.reply_text(
            f"💎 <b>VIP Pricing Plans</b>\n\n"
            f"🥉 <b>Monthly</b> - ${m:.0f}/month\n"
            f"Full access to all signals\n\n"
            f"🥈 <b>Quarterly</b> - ${q:.0f}/3 months\n"
            f"Save ~12% + bonus reports\n\n"
            f"🥇 <b>Lifetime</b> - ${l:.0f} one-time\n"
            f"Never pay again\n\n"
            f"💰 Crypto payments accepted:\n"
            f"BTC, ETH, SOL, LTC\n\n"
            f"👉 Type /vip to start payment",
            parse_mode='HTML'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        await update.message.reply_text(
            "🤖 <b>CryptoPulse VIP Bot</b>\n\n"
            "Commands:\n"
            "/start - Welcome message\n"
            "/vip - Start VIP payment\n"
            "/price - See pricing plans\n"
            "/status - Check your subscription\n"
            "/alert - Set price alert\n"
            "/myalerts - List your alerts\n"
            "/removealert - Remove an alert\n"
            "/cancel - Cancel subscription\n"
            "/help - This message\n\n"
            "Questions? Contact support.",
            parse_mode='HTML'
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check subscription status"""
        user = update.effective_user
        from src.database.supabase_client import SupabaseClient
        db = SupabaseClient()
        
        sub = await db.get_subscriber(str(user.id))
        
        if not sub:
            keyboard = [[InlineKeyboardButton("💎 Join VIP", callback_data="vip_menu")]]
            await update.message.reply_text(
                "❌ You don't have an active subscription.\n\n"
                "Become a VIP member today!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return
        
        if sub.get('active'):
            tier = sub.get('tier', 'monthly').title()
            sub_date = sub.get('subscribed_at', 'Unknown')
            status_text = (
                f"✅ <b>Active Subscription</b>\n\n"
                f"Plan: {tier}\n"
                f"Started: {sub_date[:10] if sub_date else 'Unknown'}\n\n"
                f"You have full VIP access."
            )
            if tier.lower() in ['monthly', 'quarterly']:
                status_text += "\n\nUse /cancel to stop renewal."
        else:
            status_text = (
                "❌ <b>Subscription Cancelled</b>\n\n"
                f"Cancelled at: {sub.get('cancelled_at', 'Unknown')[:10] if sub.get('cancelled_at') else 'Unknown'}\n\n"
                "Renew anytime with /vip"
            )
        
        await update.message.reply_text(status_text, parse_mode='HTML')
    
    async def alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set custom price alert: /alert BTC/USDT 65000 ABOVE"""
        user = update.effective_user
        args = context.args
        
        if len(args) != 3:
            await update.message.reply_text(
                "🤖 <b>Set Custom Price Alert</b>\n\n"
                "Usage:\n"
                "<code>/alert BTC/USDT 65000 ABOVE</code>\n"
                "<code>/alert ETH/USDT 3000 BELOW</code>\n\n"
                "💎 Available for all VIP members.",
                parse_mode='HTML'
            )
            return
        
        symbol = args[0].upper()
        try:
            target_price = float(args[1])
        except ValueError:
            await update.message.reply_text("❌ Price must be a number. Example: 65000", parse_mode='HTML')
            return
        
        direction = args[2].upper()
        if direction not in ('ABOVE', 'BELOW'):
            await update.message.reply_text("❌ Direction must be ABOVE or BELOW.", parse_mode='HTML')
            return
        
        await self.custom_alerts.add_alert(
            user_id=str(user.id),
            symbol=symbol,
            target_price=target_price,
            direction=direction
        )
        
        emoji = "🚀" if direction == 'ABOVE' else "🔻"
        await update.message.reply_text(
            f"{emoji} <b>Alert Set!</b>\n\n"
            f"📊 {symbol}\n"
            f"🎯 Target: ${target_price:,.2f}\n"
            f"📈 Direction: {direction}\n\n"
            f"You'll get a DM when this hits.\n"
            f"See all alerts: /myalerts",
            parse_mode='HTML'
        )
    
    async def myalerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List user's active alerts"""
        user = update.effective_user
        alerts = await self.custom_alerts.get_user_alerts(str(user.id))
        
        if not alerts:
            await update.message.reply_text(
                "📭 <b>No active alerts.</b>\n\n"
                "Set one with:\n"
                "<code>/alert BTC/USDT 65000 ABOVE</code>",
                parse_mode='HTML'
            )
            return
        
        text = "🔔 <b>Your Active Alerts</b>\n\n"
        for alert in alerts:
            emoji = "🚀" if alert['direction'] == 'ABOVE' else "🔻"
            text += (
                f"{emoji} {alert['symbol']} {alert['direction']} ${alert['target_price']:,.2f}\n"
                f"   <code>/removealert {alert['id']}</code>\n\n"
            )
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def removealert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove an alert by ID"""
        user = update.effective_user
        args = context.args
        
        if not args:
            await update.message.reply_text(
                "❌ Please provide alert ID.\n"
                "Use /myalerts to see your alert IDs.",
                parse_mode='HTML'
            )
            return
        
        alert_id = args[0]
        await self.custom_alerts.remove_alert(alert_id)
        await update.message.reply_text("✅ Alert removed.", parse_mode='HTML')
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel subscription"""
        user = update.effective_user
        from src.database.supabase_client import SupabaseClient
        db = SupabaseClient()
        
        sub = await db.get_subscriber(str(user.id))
        
        if not sub or not sub.get('active'):
            await update.message.reply_text(
                "❌ No active subscription found.\n\n"
                "Use /vip to start one!",
                parse_mode='HTML'
            )
            return
        
        tier = sub.get('tier', 'monthly')
        if tier == 'lifetime':
            await update.message.reply_text(
                "ℹ️ Lifetime subscriptions cannot be cancelled.\n\n"
                "You have permanent VIP access.",
                parse_mode='HTML'
            )
            return
        
        # Deactivate
        success = await db.deactivate_subscriber(str(user.id))
        if success:
            await update.message.reply_text(
                "✅ <b>Subscription Cancelled</b>\n\n"
                "Your VIP access will remain active until the end of your current billing period.\n\n"
                "You can re-subscribe anytime with /vip",
                parse_mode='HTML'
            )
            await self._notify_admin(
                f"⚠️ <b>Subscription Cancelled</b>\n\n"
                f"User: @{user.username or user.id}\n"
                f"User ID: {user.id}\n"
                f"Tier: {tier}"
            )
        else:
            await update.message.reply_text(
                "❌ Error cancelling. Please contact support.",
                parse_mode='HTML'
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks with error recovery"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = update.effective_user
        
        try:
            if data == "vip_menu":
                await self._show_plan_selection(query)
            elif data == "vip_plans":
                await self._show_plans(query)
            elif data == "contact_support":
                await self._handle_contact_support(query, user)
            elif data.startswith("plan_"):
                plan = data.split("_")[1]
                await self._show_payment_method_selection(query, plan)
            elif data.startswith("paymethod_card_"):
                plan = data.split("_")[2]
                await self._create_stripe_checkout(query, user, plan)
            elif data.startswith("paymethod_crypto_"):
                plan = data.split("_")[2]
                await self._show_crypto_selection(query, plan)
            elif data.startswith("pay_"):
                parts = data.split("_")
                crypto = parts[1]
                plan = parts[2] if len(parts) > 2 else 'monthly'
                await self._generate_invoice(query, user, crypto, plan)
            elif data == "back_menu":
                await self._show_main_menu(query)
            elif data == "back_plans":
                await self._show_plan_selection(query)
            elif data == "confirm_sent":
                await self._prompt_txid(query)
            else:
                logger.warning(f"Unknown callback: {data}")
                await query.edit_message_text(
                    "🤖 Oops, that button isn't working. Try /start to restart.",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Callback error [{data}]: {e}")
            try:
                await query.edit_message_text(
                    "❌ Something went wrong. Please try /start again.",
                    parse_mode='HTML'
                )
            except Exception:
                pass  # Message may have been deleted
    
    async def handle_user_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user DMs (TXID, questions, etc.)"""
        text = update.message.text
        user = update.effective_user
        
        # Check if message looks like a TXID
        if len(text) > 20 and any(c in text for c in '0123456789abcdefABCDEF'):
            await self._handle_payment_txid(update, text, user)
        else:
            # General inquiry
            keyboard = [
                [InlineKeyboardButton("💎 Join VIP", callback_data="vip_menu")],
                [InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🤖 Hi! I'm the CryptoPulse VIP assistant.\n\n"
                "I can help you join VIP or answer questions.\n"
                "What would you like to do?",
                reply_markup=reply_markup
            )
    
    async def _show_plan_selection(self, query_or_message):
        """Show plan selection (Monthly/Quarterly/Lifetime)"""
        m_price = settings.VIP_MONTHLY_PRICE
        q_price = settings.VIP_QUARTERLY_PRICE
        l_price = settings.VIP_LIFETIME_PRICE
        
        keyboard = [
            [InlineKeyboardButton(f"🥉 Monthly - ${m_price:.0f}/month", callback_data="plan_monthly")],
            [InlineKeyboardButton(f"🥈 Quarterly - ${q_price:.0f}/3mo", callback_data="plan_quarterly")],
            [InlineKeyboardButton(f"🥇 Lifetime - ${l_price:.0f} one-time", callback_data="plan_lifetime")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (f"💎 <b>Select Your VIP Plan</b>\n\n"
                f"🥉 <b>Monthly</b> - ${m_price:.0f}/month\n"
                f"Full access, cancel anytime\n\n"
                f"🥈 <b>Quarterly</b> - ${q_price:.0f}/3 months\n"
                f"Save ~12%, bonus reports\n\n"
                f"🥇 <b>Lifetime</b> - ${l_price:.0f} one-time\n"
                f"Never pay again\n\n"
                f"All plans include:\n"
                f"✅ 95%+ confidence signals\n"
                f"✅ Entry, SL, 3 TPs\n"
                f"✅ Real-time updates\n"
                f"✅ Weekly reports")
        
        # For callbacks, use edit_message_text to replace existing message
        if hasattr(query_or_message, 'edit_message_text'):
            await query_or_message.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        elif hasattr(query_or_message, 'reply_text'):
            await query_or_message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query_or_message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_crypto_selection(self, query, plan):
        """Show crypto selection for chosen plan"""
        plan_names = {'monthly': 'Monthly', 'quarterly': 'Quarterly', 'lifetime': 'Lifetime'}
        plan_price = settings.VIP_MONTHLY_PRICE if plan == 'monthly' else (settings.VIP_QUARTERLY_PRICE if plan == 'quarterly' else settings.VIP_LIFETIME_PRICE)
        
        keyboard = []
        
        if settings.CRYPTO_WALLET_BTC:
            keyboard.append([InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data=f"pay_BTC_{plan}")])
        if settings.CRYPTO_WALLET_ETH:
            keyboard.append([InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data=f"pay_ETH_{plan}")])
        if settings.CRYPTO_WALLET_SOL:
            keyboard.append([InlineKeyboardButton("◎ Solana (SOL)", callback_data=f"pay_SOL_{plan}")])
        if settings.CRYPTO_WALLET_LTC:
            keyboard.append([InlineKeyboardButton("Ł Litecoin (LTC)", callback_data=f"pay_LTC_{plan}")])
        if settings.CRYPTO_WALLET_LINK:
            keyboard.append([InlineKeyboardButton("🔗 Chainlink (LINK)", callback_data=f"pay_LINK_{plan}")])
        if settings.CRYPTO_WALLET_HYPE:
            keyboard.append([InlineKeyboardButton("🔥 Hyperliquid (HYPE)", callback_data=f"pay_HYPE_{plan}")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_plans")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=f"💎 <b>{plan_names.get(plan, 'VIP')} Plan - ${plan_price:.0f}</b>\n\n"
                 f"Select cryptocurrency to pay:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def _show_payment_method_selection(self, query, plan):
        """Show payment method selection: Card or Crypto"""
        plan_names = {'monthly': 'Monthly', 'quarterly': 'Quarterly', 'lifetime': 'Lifetime'}
        plan_price = settings.VIP_MONTHLY_PRICE if plan == 'monthly' else (settings.VIP_QUARTERLY_PRICE if plan == 'quarterly' else settings.VIP_LIFETIME_PRICE)
        
        keyboard = []
        
        # Card option (if Stripe configured)
        if self.stripe_handler:
            keyboard.append([InlineKeyboardButton("💳 Pay with Card (Auto-renews)", callback_data=f"paymethod_card_{plan}")])
        
        # Crypto option
        keyboard.append([InlineKeyboardButton("₿ Pay with Crypto (One-time)", callback_data=f"paymethod_crypto_{plan}")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_plans")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        stripe_text = "\n💳 <b>Card</b> — Auto-renews monthly, cancel anytime" if self.stripe_handler else ""
        
        await query.edit_message_text(
            text=f"💎 <b>{plan_names.get(plan, 'VIP')} Plan — ${plan_price:.0f}</b>\n"
                 f"Choose your payment method:\n\n"
                 f"{stripe_text}"
                 f"\n₿ <b>Crypto</b> — Private, no KYC, manual renewal\n\n"
                 f"Both methods give the same VIP access.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def _create_stripe_checkout(self, query, user, plan):
        """Create Stripe checkout session and send link to user"""
        try:
            if not self.stripe_handler:
                await query.edit_message_text(
                    text="❌ Card payments not available right now.\n\nPlease use Crypto instead.",
                    parse_mode='HTML'
                )
                return
            
            username = user.username or "N/A"
            user_id = str(user.id)
            
            # Create checkout session
            checkout_url = await self.stripe_handler.create_checkout_session(user_id, username)
            
            if not checkout_url:
                await query.edit_message_text(
                    text="❌ Error creating checkout. Please try again or use Crypto.",
                    parse_mode='HTML'
                )
                return
            
            plan_names = {'monthly': 'Monthly', 'quarterly': 'Quarterly', 'lifetime': 'Lifetime'}
            plan_label = plan_names.get(plan, 'VIP')
            
            keyboard = [
                [InlineKeyboardButton("🔗 Open Secure Checkout", url=checkout_url)],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"plan_{plan}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"💳 <b>{plan_label} VIP — Secure Checkout</b>\n\n"
                     f"Click below to complete payment via Stripe:\n\n"
                     f"✅ Encrypted & secure\n"
                     f"✅ Auto-renews (cancel anytime)\n"
                     f"✅ VIP activated instantly after payment\n\n"
                     f"After paying, your VIP access will be activated automatically.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            # Notify admin
            await self._notify_admin(
                f"💳 <b>Stripe Checkout Started</b>\n\n"
                f"User: @{username}\n"
                f"User ID: {user_id}\n"
                f"Plan: {plan_label}"
            )
            
        except Exception as e:
            logger.error(f"Error creating Stripe checkout: {e}")
            await query.edit_message_text(
                text="❌ Error creating checkout. Please try again or use Crypto.",
                parse_mode='HTML'
            )
    
    async def _show_main_menu(self, query):
        """Show main welcome menu (used by Back button)"""
        keyboard = [
            [InlineKeyboardButton("💎 Join VIP", callback_data="vip_menu")],
            [InlineKeyboardButton("📊 See Plans", callback_data="vip_plans")],
            [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "🚀 <b>Welcome to Crypto Pulse VIP!</b>\n\n"
            "Get elite trading signals delivered straight to your VIP channel.\n\n"
            "✅ 90%+ confidence signals\n"
            "✅ 1-3 elite setups per day\n"
            "✅ Entry, Stop Loss, 3 Take Profits\n"
            "✅ Real-time trade updates\n"
            "✅ Weekly performance reports\n\n"
            "<b>Ready to level up your trading?</b>"
        )
        
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            pass
    
    async def _show_plans(self, query):
        """Show pricing plans"""
        keyboard = [[InlineKeyboardButton("💎 Join VIP", callback_data="vip_menu")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        m = settings.VIP_MONTHLY_PRICE
        q = settings.VIP_QUARTERLY_PRICE
        l = settings.VIP_LIFETIME_PRICE
        
        await query.edit_message_text(
            text=f"💎 <b>VIP Pricing Plans</b>\n\n"
                 f"🥉 <b>Monthly</b> - ${m:.0f}/month\n"
                 f"Full access to all signals\n\n"
                 f"🥈 <b>Quarterly</b> - ${q:.0f}/3 months\n"
                 f"Save ~12% + bonus reports\n\n"
                 f"🥇 <b>Lifetime</b> - ${l:.0f} one-time\n"
                 f"Never pay again\n\n"
                 f"💰 BTC, ETH, SOL, LTC accepted",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def _generate_invoice(self, query, user, crypto, plan='monthly'):
        """Generate payment invoice"""
        try:
            username = user.username or "N/A"
            user_id = str(user.id)
            plan_names = {'monthly': 'Monthly', 'quarterly': 'Quarterly', 'lifetime': 'Lifetime'}
            
            invoice = await self.payment_handler.generate_payment_invoice(
                user_id=user_id,
                telegram_username=username,
                crypto=crypto,
                plan=plan
            )
            
            if not invoice:
                await query.edit_message_text(
                    text="❌ <b>Unable to generate invoice</b>\n\n"
                         "This is usually temporary. Possible causes:\n"
                         "• Crypto price API momentarily unavailable\n"
                         "• Network connectivity issue\n\n"
                         "<b>Please try again in 30 seconds.</b>\n\n"
                         "If it keeps failing, contact support.",
                    parse_mode='HTML'
                )
                return
            
            coin_info = self.payment_handler.SUPPORTED_COINS[crypto]
            
            plan_label = plan_names.get(plan, 'VIP')
            payment_text = f"""💎 <b>VIP Payment Invoice</b>

<b>Plan:</b> {plan_label} VIP Access
<b>Amount:</b> <code>{invoice['amount']}</code> {crypto}
<b>USD Value:</b> ${invoice['usd_value']:.2f}
<b>Network:</b> {coin_info['network'].title()}

<b>Send To:</b>
<code>{invoice['wallet_address']}</code>

⚠️ <b>IMPORTANT:</b>
• Send EXACTLY {invoice['amount']} {crypto}
• Use {coin_info['network'].title()} network ONLY
• Payment expires in 24 hours
• After sending, reply with your transaction hash

<b>Invoice ID:</b> <code>{invoice['invoice_id']}</code>

✅ VIP activated within 1 hour of confirmation."""
            
            keyboard = [
                [InlineKeyboardButton("✅ I've Sent Payment", callback_data="confirm_sent")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_plans")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=payment_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            # Remember which plan this user is paying for
            self.pending_crypto_plans[user_id] = plan
            
            # Notify admin
            await self._notify_admin(
                f"💰 <b>New Payment Invoice!</b>\n\n"
                f"User: @{username}\n"
                f"User ID: {user_id}\n"
                f"Crypto: {crypto}\n"
                f"Amount: {invoice['amount']} {crypto}\n"
                f"USD: ${invoice['usd_value']:.2f}\n"
                f"Invoice: {invoice['invoice_id']}"
            )
            
        except Exception as e:
            logger.error(f"Error generating invoice: {e}")
            await query.edit_message_text(
                text="❌ Error creating invoice. Please contact support.",
                parse_mode='HTML'
            )
    
    async def _prompt_txid(self, query):
        """Prompt user to send TXID after clicking 'I've Sent Payment'"""
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Plans", callback_data="back_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="📤 <b>Send Your Transaction Hash</b>\n\n"
                 "Please reply to this message with your transaction hash (TXID).\n\n"
                 "Example:\n"
                 "<code>0x7f8a9b...c2d3e4f5</code> (ETH/SOL/LINK/HYPE)\n"
                 "<code>a1b2c3d...e4f5g6h7</code> (BTC/LTC)\n\n"
                 "Once received, we'll verify and activate your VIP access.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def _handle_payment_txid(self, update, text, user):
        """Handle TXID submission - auto-activate VIP/Pro/Lifetime with 24h grace period"""
        username = user.username or f"user_{user.id}"
        user_id = str(user.id)
        
        # Retrieve the plan they selected (default monthly if unknown)
        plan = self.pending_crypto_plans.pop(user_id, 'monthly')
        tier = plan  # monthly, quarterly, or lifetime
        tier_label = {'monthly': 'Monthly VIP', 'quarterly': 'Quarterly Pro', 'lifetime': 'Lifetime VIP'}.get(tier, 'VIP')
        
        # Store in database with correct tier
        from src.database.supabase_client import SupabaseClient
        db = SupabaseClient()
        
        # Save subscriber with pending verification
        await db.save_subscriber(
            user_id=user_id,
            username=username,
            tier=tier,
            stripe_customer_id=f"crypto:{text[:20]}"  # Store TXID prefix
        )
        
        # Try to create VIP channel invite link
        vip_link = None
        try:
            if self.app and self.app.bot:
                # Create a single-use invite link that expires in 1 day
                chat = await self.app.bot.get_chat(settings.TELEGRAM_VIP_CHANNEL_ID)
                invite = await self.app.bot.create_chat_invite_link(
                    chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                    member_limit=1,
                    expire_date=datetime.utcnow() + timedelta(hours=24)
                )
                vip_link = invite.invite_link
        except Exception as e:
            logger.error(f"Could not create invite link: {e}")
        
        # Send user confirmation
        if vip_link:
            extra = ""
            if tier == 'quarterly':
                extra = "\n📊 <b>Pro Perks Active:</b> Whale alerts + Education + Bonus reports\n"
            elif tier == 'lifetime':
                extra = "\n👑 <b>Lifetime Perks Active:</b> All features forever + Giveaways + Priority support\n"
            
            await update.message.reply_text(
                f"✅ <b>{tier_label} Access Granted!</b>\n\n"
                f"TXID received: <code>{text[:30]}...</code>\n"
                f"We're verifying on-chain (24h grace period).\n\n"
                f"🔐 <b>Your VIP Channel:</b>\n"
                f"<a href='{vip_link}'>Click to Join VIP Channel</a>\n"
                f"{extra}\n"
                f"📚 <b>Getting Started:</b>\n"
                f"• Join the channel above\n"
                f"• Introduce yourself\n"
                f"• Watch for your first signal!\n\n"
                f"Questions? DM @CryptoPulseVIPAccessBot",
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(
                f"✅ <b>{tier_label} Payment Received!</b>\n\n"
                f"TXID: <code>{text[:30]}...</code>\n"
                f"We're verifying your transaction.\n"
                f"{tier_label} access will be granted within 1 hour.\n\n"
                f"Thank you! 🙏",
                parse_mode='HTML'
            )
        
        # Notify admin
        await self._notify_admin(
            f"🚨 <b>AUTO {tier_label.upper()} ACTIVATION</b>\n\n"
            f"User: @{username}\n"
            f"User ID: {user.id}\n"
            f"Plan: {tier_label}\n"
            f"TXID: <code>{text}</code>\n\n"
            f"✅ User has been auto-granted {tier_label} access (24h verification window).\n"
            f"⚠️ Please verify on-chain. If fake, revoke with /revoke {user.id}"
        )
    
    async def _handle_contact_support(self, query, user):
        """Handle contact support button - forward user's message to admin"""
        await query.edit_message_text(
            "💬 <b>Contact Support</b>\n\n"
            "Please type your message below and I'll forward it to our support team.\n\n"
            "We'll get back to you as soon as possible!",
            parse_mode='HTML'
        )
        
        # Notify admin that user wants to contact support
        await self._notify_admin(
            f"💬 <b>Support Request</b>\n\n"
            f"User: @{user.username or 'Unknown'}\n"
            f"User ID: {user.id}\n"
            f"Name: {user.first_name} {user.last_name or ''}\n\n"
            f"User clicked Contact Support. Waiting for their message..."
        )
    
    async def _notify_admin(self, message: str):
        """Send notification to admin"""
        if self.notification_callback:
            await self.notification_callback(message)
        elif self.app and self.app.bot:
            try:
                await self.app.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
    
    async def shutdown(self):
        """Shutdown the bot"""
        if self.app:
            await self.app.stop()
            logger.info("VIP bot shut down")
