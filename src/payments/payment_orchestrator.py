"""
CRYPTO PULSE SIGNALS — Payment Orchestrator
Routes users between Stripe (auto-renewal) and Crypto (manual) payments.
Handles trial expiry, payment reminders, and activation.
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from src.config import settings
from src.utils.logger import get_logger
from src.database.supabase_client import SupabaseClient

logger = get_logger(__name__)


class PaymentOrchestrator:
    """
    Central payment routing system.
    Users pick: Card (Stripe, auto-renew) or Crypto (NOWPayments, manual).
    """
    
    def __init__(self, stripe_handler=None, crypto_handler=None, db=None):
        self.stripe = stripe_handler
        self.crypto = crypto_handler
        self.db = db or SupabaseClient()
        
        # Pricing (can be overridden via settings)
        self.prices = {
            'monthly': {
                'gbp': 29.00,
                'usd': 39.00,
                'crypto_usdt': 39.00
            },
            'quarterly': {
                'gbp': 79.00,
                'usd': 99.00,
                'crypto_usdt': 99.00
            },
            'yearly': {
                'gbp': 249.00,
                'usd': 349.00,
                'crypto_usdt': 349.00
            }
        }
        
        # Discounts for longer plans
        self.discounts = {
            'monthly': 0,
            'quarterly': 15,  # 15% off
            'yearly': 30       # 30% off
        }
    
    # ==================== PAYMENT METHOD SELECTION ====================
    
    def get_payment_options_message(self, tier: str = 'monthly') -> str:
        """Generate payment options message for VIP bot"""
        price_gbp = self.prices[tier]['gbp']
        price_crypto = self.prices[tier]['crypto_usdt']
        discount = self.discounts[tier]
        
        discount_text = f" (Save {discount}%)" if discount > 0 else ""
        
        msg = (
            f"💎 <b>Choose Your VIP Access</b>\n\n"
            f"<b>{tier.title()} Plan:</b> £{price_gbp:.0f}{discount_text}\n\n"
            f"<b>Payment Method:</b>\n"
            f"💳 Card (Stripe) — Auto-renews, cancel anytime\n"
            f"   • Never lose access\n"
            f"   • Cancel in 2 clicks\n\n"
            f"₿ Crypto (USDT) — One-time payment\n"
            f"   • ${price_crypto:.0f} USDT\n"
            f"   • Private, no KYC\n"
            f"   • Manual renewal each month\n\n"
            f"Tap a button below to pay:"
        )
        return msg
    
    async def create_stripe_checkout(self, user_id: str, username: str, tier: str = 'monthly') -> Optional[str]:
        """Create Stripe checkout session, return URL"""
        if not self.stripe:
            logger.warning("Stripe handler not configured")
            return None
        
        try:
            url = await self.stripe.create_checkout_session(user_id, username)
            if url:
                logger.info(f"Stripe checkout created for {username}: {url[:60]}...")
            return url
        except Exception as e:
            logger.error(f"Stripe checkout error: {e}")
            return None
    
    async def create_crypto_invoice(self, user_id: str, username: str, tier: str = 'monthly') -> Optional[Dict]:
        """Create NOWPayments crypto invoice"""
        if not self.crypto:
            logger.warning("Crypto handler not configured")
            return None
        
        try:
            amount_usd = self.prices[tier]['crypto_usdt']
            # This calls the existing crypto payment handler
            result = await self.crypto.create_payment(
                user_id=user_id,
                username=username,
                amount_usd=amount_usd,
                crypto_symbol='USDT',
                network='TRC20'
            )
            logger.info(f"Crypto invoice created for {username}: ${amount_usd}")
            return result
        except Exception as e:
            logger.error(f"Crypto invoice error: {e}")
            return None
    
    # ==================== TRIAL EXPIRY HANDLING ====================
    
    async def handle_trial_expiry(self, user_id: str, username: str) -> str:
        """
        Called when a user's 7-day trial expires.
        Sends payment options message.
        Returns the message text.
        """
        # Check if they have an active paid subscription already
        sub = await self.db.get_subscriber(user_id)
        if sub and sub.get('tier') == 'vip' and sub.get('active'):
            logger.info(f"{username} already has VIP — skipping trial expiry")
            return ""
        
        # Build expiry message with payment options
        message = (
            f"⏰ <b>Your VIP Trial Has Expired</b>\n\n"
            f"Hope you enjoyed the elite signals!\n\n"
            f"To keep receiving VIP access, choose a plan:\n\n"
        )
        
        for tier in ['monthly', 'quarterly', 'yearly']:
            gbp = self.prices[tier]['gbp']
            usd = self.prices[tier]['usd']
            crypto = self.prices[tier]['crypto_usdt']
            disc = self.discounts[tier]
            
            save = f" (Save {disc}%)" if disc > 0 else ""
            
            message += (
                f"📅 {tier.title()}: £{gbp:.0f} / ${usd:.0f}{save}\n"
                f"   💳 Card: Auto-renews monthly\n"
                f"   ₿ Crypto: ${crypto:.0f} USDT (one-time)\n\n"
            )
        
        message += (
            f"<b>How to pay:</b>\n"
            f"1. Type /vip to see payment buttons\n"
            f"2. Choose Card or Crypto\n"
            f"3. Complete payment in 2 minutes\n\n"
            f"Questions? Contact support 💎"
        )
        
        logger.info(f"Trial expiry message sent to {username}")
        return message
    
    async def handle_payment_reminder(self, user_id: str, username: str, days_until_expiry: int) -> str:
        """
        Called for crypto users before their access expires.
        (Stripe handles auto-renewal, so only crypto users get reminded.)
        """
        message = (
            f"⏰ <b>Subscription Reminder</b>\n\n"
            f"Your VIP access expires in <b>{days_until_expiry} days</b>.\n\n"
            f"To avoid losing access to elite signals:\n"
            f"1. Type /vip to renew\n"
            f"2. Pay with Card (auto-renews) or Crypto (manual)\n\n"
            f"💡 Tip: Switch to Card payments to never worry about expiry!\n\n"
            f"Stay profitable 💎"
        )
        
        logger.info(f"Payment reminder sent to {username} ({days_until_expiry} days left)")
        return message
    
    # ==================== ACTIVATION ====================
    
    async def activate_vip(self, user_id: str, username: str, payment_method: str,
                          tier: str = 'monthly', stripe_customer_id: str = None) -> bool:
        """Activate VIP after successful payment"""
        try:
            # Calculate expiry based on tier
            duration_days = {'monthly': 30, 'quarterly': 90, 'yearly': 365}
            days = duration_days.get(tier, 30)
            
            data = {
                'user_id': user_id,
                'username': username,
                'tier': 'vip',
                'payment_method': payment_method,
                'active': True,
                'subscribed_at': datetime.utcnow().isoformat(),
                'expires_at': (datetime.utcnow() + timedelta(days=days)).isoformat(),
            }
            
            if stripe_customer_id:
                data['stripe_customer_id'] = stripe_customer_id
            
            await self.db.save_subscriber(extra_data=data)
            
            logger.info(f"✅ VIP activated for {username} via {payment_method}")
            return True
            
        except Exception as e:
            logger.error(f"Error activating VIP: {e}")
            return False
    
    async def check_subscription_expiry(self) -> List[Dict]:
        """Check for expired subscriptions and downgrade them"""
        try:
            now = datetime.utcnow()
            
            # Get all active VIP subscribers
            subs = await self.db.get_active_subscribers(tier='vip')
            
            expired = []
            for sub in subs:
                expires_at = sub.get('expires_at')
                if expires_at:
                    expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if expiry < now:
                        # Downgrade
                        await self.db.update_subscriber(sub['user_id'], {
                            'active': False,
                            'tier': 'expired',
                            'expired_at': now.isoformat()
                        })
                        expired.append(sub)
                        logger.info(f"⏰ Subscription expired for {sub.get('username')}")
            
            return expired
            
        except Exception as e:
            logger.error(f"Error checking subscription expiry: {e}")
            return []
    
    # ==================== STATS ====================
    
    async def get_revenue_stats(self, days: int = 30) -> Dict:
        """Get payment/revenue stats"""
        try:
            # This would query your payments table
            # For now, return placeholder structure
            return {
                'period_days': days,
                'stripe_revenue': 0,  # TODO: query from DB
                'crypto_revenue': 0,  # TODO: query from DB
                'total_revenue': 0,
                'new_subscribers': 0,
                'churned': 0,
                'trial_to_paid_rate': 0
            }
        except Exception as e:
            logger.error(f"Error getting revenue stats: {e}")
            return {}
