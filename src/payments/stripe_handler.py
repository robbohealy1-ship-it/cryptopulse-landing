import stripe
from typing import Dict, Optional
from datetime import datetime
from src.config import settings
from src.database.supabase_client import SupabaseClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StripeHandler:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        self.vip_price_id = settings.STRIPE_VIP_PRICE_ID
        self.db = SupabaseClient()
    
    async def create_checkout_session(self, user_id: str, username: str) -> Optional[str]:
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': self.vip_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url='https://t.me/your_vip_channel',
                cancel_url='https://your-website.com/cancelled',
                client_reference_id=user_id,
                metadata={
                    'user_id': user_id,
                    'username': username,
                    'tier': 'vip'
                }
            )
            
            logger.info(f"Checkout session created for user {username}")
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return None
    
    async def create_customer_portal_session(self, customer_id: str) -> Optional[str]:
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url='https://your-website.com/account',
            )
            
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating portal session: {e}")
            return None
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_type = event['type']
            
            if event_type == 'checkout.session.completed':
                await self._handle_checkout_completed(event['data']['object'])
            
            elif event_type == 'customer.subscription.created':
                await self._handle_subscription_created(event['data']['object'])
            
            elif event_type == 'customer.subscription.updated':
                await self._handle_subscription_updated(event['data']['object'])
            
            elif event_type == 'customer.subscription.deleted':
                await self._handle_subscription_deleted(event['data']['object'])
            
            elif event_type == 'invoice.payment_succeeded':
                await self._handle_payment_succeeded(event['data']['object'])
            
            elif event_type == 'invoice.payment_failed':
                await self._handle_payment_failed(event['data']['object'])
            
            return {'status': 'success', 'event_type': event_type}
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _handle_checkout_completed(self, session):
        try:
            user_id = session.get('client_reference_id')
            username = session['metadata'].get('username')
            customer_id = session.get('customer')
            
            await self.db.save_subscriber(
                user_id=user_id,
                username=username,
                tier='vip',
                stripe_customer_id=customer_id
            )
            
            logger.info(f"Checkout completed for {username}")
            
        except Exception as e:
            logger.error(f"Error handling checkout completed: {e}")
    
    async def _handle_subscription_created(self, subscription):
        try:
            customer_id = subscription['customer']
            
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get('user_id')
            
            logger.info(f"Subscription created for customer {customer_id}")
            
        except Exception as e:
            logger.error(f"Error handling subscription created: {e}")
    
    async def _handle_subscription_updated(self, subscription):
        try:
            status = subscription['status']
            customer_id = subscription['customer']
            
            logger.info(f"Subscription updated for {customer_id}: {status}")
            
            if status == 'canceled':
                customer = stripe.Customer.retrieve(customer_id)
                user_id = customer.metadata.get('user_id')
                if user_id:
                    await self.db.deactivate_subscriber(user_id)
            
        except Exception as e:
            logger.error(f"Error handling subscription updated: {e}")
    
    async def _handle_subscription_deleted(self, subscription):
        try:
            customer_id = subscription['customer']
            
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get('user_id')
            
            if user_id:
                await self.db.deactivate_subscriber(user_id)
            
            logger.info(f"Subscription deleted for {customer_id}")
            
        except Exception as e:
            logger.error(f"Error handling subscription deleted: {e}")
    
    async def _handle_payment_succeeded(self, invoice):
        try:
            customer_id = invoice['customer']
            amount = invoice['amount_paid'] / 100
            
            logger.info(f"Payment succeeded: ${amount} from {customer_id}")
            
        except Exception as e:
            logger.error(f"Error handling payment succeeded: {e}")
    
    async def _handle_payment_failed(self, invoice):
        try:
            customer_id = invoice['customer']
            
            logger.warning(f"Payment failed for {customer_id}")
            
        except Exception as e:
            logger.error(f"Error handling payment failed: {e}")
    
    async def get_subscription_status(self, customer_id: str) -> Dict:
        try:
            subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
            
            if subscriptions.data:
                sub = subscriptions.data[0]
                return {
                    'active': sub['status'] == 'active',
                    'status': sub['status'],
                    'current_period_end': datetime.fromtimestamp(sub['current_period_end']),
                    'cancel_at_period_end': sub['cancel_at_period_end']
                }
            
            return {'active': False, 'status': 'none'}
            
        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            return {'active': False, 'status': 'error'}
    
    async def cancel_subscription(self, subscription_id: str) -> bool:
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            logger.info(f"Subscription {subscription_id} will cancel at period end")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            return False
