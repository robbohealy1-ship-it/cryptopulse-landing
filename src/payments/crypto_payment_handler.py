"""
CRYPTO PULSE SIGNALS - Crypto Payment Handler
Support for BTC, ETH, SOL, LTC, ZEC, HYPE, LINK, XMR payments
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.config import settings
from src.database.supabase_client import SupabaseClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CryptoPaymentHandler:
    """Handle cryptocurrency payments for VIP subscriptions"""
    
    # Supported cryptocurrencies
    SUPPORTED_COINS = {
        'BTC': {'name': 'Bitcoin', 'decimals': 8, 'network': 'bitcoin'},
        'ETH': {'name': 'Ethereum', 'decimals': 18, 'network': 'ethereum'},
        'SOL': {'name': 'Solana', 'decimals': 9, 'network': 'solana'},
        'LTC': {'name': 'Litecoin', 'decimals': 8, 'network': 'litecoin'},
        'ZEC': {'name': 'Zcash', 'decimals': 8, 'network': 'zcash'},
        'LINK': {'name': 'Chainlink', 'decimals': 18, 'network': 'ethereum'},
        'XMR': {'name': 'Monero', 'decimals': 12, 'network': 'monero'},
        'HYPE': {'name': 'Hyperliquid', 'decimals': 18, 'network': 'ethereum'},
    }
    
    # Plan prices from config
    PLAN_PRICES = {
        'monthly': settings.VIP_MONTHLY_PRICE,
        'quarterly': settings.VIP_QUARTERLY_PRICE,
        'lifetime': settings.VIP_LIFETIME_PRICE,
    }
    
    def __init__(self):
        self.db = SupabaseClient()
        
        # Your wallet addresses (from .env)
        self.wallet_addresses = {
            'BTC': settings.CRYPTO_WALLET_BTC,
            'ETH': settings.CRYPTO_WALLET_ETH,
            'SOL': settings.CRYPTO_WALLET_SOL,
            'LTC': settings.CRYPTO_WALLET_LTC,
            'ZEC': settings.CRYPTO_WALLET_ZEC,
            'LINK': settings.CRYPTO_WALLET_LINK or settings.CRYPTO_WALLET_ETH,  # Fallback to ETH
            'XMR': settings.CRYPTO_WALLET_XMR,
            'HYPE': settings.CRYPTO_WALLET_HYPE or settings.CRYPTO_WALLET_ETH,  # Fallback to ETH
        }
        
        # Price cache
        self.price_cache = {}
        self.price_cache_time = {}
        self.cache_duration = timedelta(minutes=5)
    
    # Fallback prices if API fails (update periodically)
    FALLBACK_PRICES = {
        'BTC': 65000.0,
        'ETH': 3500.0,
        'SOL': 150.0,
        'LTC': 80.0,
        'ZEC': 30.0,
        'LINK': 18.0,
        'XMR': 175.0,
        'HYPE': 15.0,
    }
    
    async def get_crypto_price(self, symbol: str) -> Optional[float]:
        """Get current crypto price in USD"""
        
        # Check cache first
        if symbol in self.price_cache:
            if datetime.utcnow() - self.price_cache_time[symbol] < self.cache_duration:
                return self.price_cache[symbol]
        
        # Try API
        try:
            coin_ids = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'SOL': 'solana',
                'LTC': 'litecoin',
                'ZEC': 'zcash',
                'LINK': 'chainlink',
                'XMR': 'monero',
                'HYPE': 'hyperliquid',
            }
            
            coin_id = coin_ids.get(symbol)
            if not coin_id:
                logger.error(f"Unknown coin symbol: {symbol}")
                return self.FALLBACK_PRICES.get(symbol)
            
            url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get(coin_id, {}).get('usd')
                        
                        if price:
                            self.price_cache[symbol] = price
                            self.price_cache_time[symbol] = datetime.utcnow()
                            logger.info(f"{symbol} price: ${price:,.2f}")
                            return price
                    else:
                        logger.warning(f"CoinGecko API returned status {response.status}")
        
        except Exception as e:
            logger.error(f"Error fetching {symbol} price: {e}")
        
        # Fallback to hardcoded prices
        fallback = self.FALLBACK_PRICES.get(symbol)
        if fallback:
            logger.warning(f"Using fallback price for {symbol}: ${fallback:,.2f}")
        return fallback
    
    async def calculate_payment_amount(self, symbol: str, plan: str = 'monthly') -> Optional[Dict]:
        """Calculate how much crypto needed for VIP subscription"""
        
        price_usd = await self.get_crypto_price(symbol)
        plan_price = self.PLAN_PRICES.get(plan, settings.VIP_MONTHLY_PRICE)
        
        if not price_usd:
            return None
        
        # Calculate amount needed
        amount = plan_price / price_usd
        
        # Round to appropriate decimals
        decimals = self.SUPPORTED_COINS[symbol]['decimals']
        if decimals >= 8:
            amount = round(amount, 8)
        elif decimals >= 4:
            amount = round(amount, 4)
        else:
            amount = round(amount, 2)
        
        return {
            'symbol': symbol,
            'amount': amount,
            'usd_price': price_usd,
            'total_usd': plan_price,
            'plan': plan,
            'wallet_address': self.wallet_addresses.get(symbol),
            'network': self.SUPPORTED_COINS[symbol]['network'],
            'expires_at': datetime.utcnow() + timedelta(hours=24)
        }
    
    async def generate_payment_invoice(self, user_id: str, telegram_username: str, crypto: str, plan: str = 'monthly') -> Optional[Dict]:
        """Generate a payment invoice for user"""
        
        if crypto not in self.SUPPORTED_COINS:
            logger.error(f"Unsupported cryptocurrency: {crypto}")
            return None
        
        payment_details = await self.calculate_payment_amount(crypto, plan)
        
        if not payment_details:
            return None
        
        # Create payment record in database
        # NOTE: 'plan' stored in notes since table may not have plan column
        invoice = {
            'user_id': user_id,
            'telegram_username': telegram_username,
            'crypto_symbol': crypto,
            'amount_crypto': payment_details['amount'],
            'amount_usd': payment_details['total_usd'],
            'wallet_address': payment_details['wallet_address'],
            'network': payment_details['network'],
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': payment_details['expires_at'].isoformat(),
            'notes': f"Plan: {plan}"
        }
        
        try:
            # Save to database
            result = self.db.client.table('crypto_payments').insert(invoice).execute()
            
            if result.data:
                invoice_id = result.data[0]['id']
                logger.info(f"Created crypto payment invoice {invoice_id} for {telegram_username}")
                
                return {
                    'invoice_id': invoice_id,
                    'crypto': crypto,
                    'amount': payment_details['amount'],
                    'wallet_address': payment_details['wallet_address'],
                    'network': payment_details['network'],
                    'usd_value': payment_details['total_usd'],
                    'expires_at': payment_details['expires_at']
                }
        
        except Exception as e:
            logger.error(f"Error creating payment invoice in DB: {e}")
            logger.error(f"Invoice data: {invoice}")
        
        return None
    
    async def check_payment_received(self, invoice_id: str) -> bool:
        """
        Check if payment has been received
        NOTE: This is a manual verification system
        Admin must confirm payment in dashboard
        """
        
        try:
            result = self.db.client.table('crypto_payments')\
                .select('*')\
                .eq('id', invoice_id)\
                .single()\
                .execute()
            
            if result.data:
                return result.data.get('status') == 'confirmed'
        
        except Exception as e:
            logger.error(f"Error checking payment: {e}")
        
        return False
    
    async def confirm_payment(self, invoice_id: str, tx_hash: Optional[str] = None) -> bool:
        """
        Manually confirm a payment (admin action)
        """
        
        try:
            # Update payment status
            update_data = {
                'status': 'confirmed',
                'confirmed_at': datetime.utcnow().isoformat()
            }
            
            if tx_hash:
                update_data['transaction_hash'] = tx_hash
            
            result = self.db.client.table('crypto_payments')\
                .update(update_data)\
                .eq('id', invoice_id)\
                .execute()
            
            if result.data:
                payment = result.data[0]
                
                # Activate VIP subscription
                await self._activate_vip_subscription(
                    payment['user_id'],
                    payment['telegram_username']
                )
                
                logger.info(f"Payment {invoice_id} confirmed and VIP activated")
                return True
        
        except Exception as e:
            logger.error(f"Error confirming payment: {e}")
        
        return False
    
    async def _activate_vip_subscription(self, user_id: str, telegram_username: str):
        """Activate VIP subscription after payment"""
        
        try:
            # Check if subscriber exists
            existing = self.db.client.table('subscribers')\
                .select('*')\
                .eq('telegram_user_id', user_id)\
                .execute()
            
            subscription_data = {
                'telegram_user_id': user_id,
                'telegram_username': telegram_username,
                'subscription_tier': 'vip',
                'subscription_status': 'active',
                'subscribed_at': datetime.utcnow().isoformat(),
                'subscription_end': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'payment_method': 'crypto'
            }
            
            if existing.data:
                # Update existing
                self.db.client.table('subscribers')\
                    .update(subscription_data)\
                    .eq('telegram_user_id', user_id)\
                    .execute()
            else:
                # Create new
                self.db.client.table('subscribers')\
                    .insert(subscription_data)\
                    .execute()
            
            logger.info(f"VIP subscription activated for {telegram_username}")
        
        except Exception as e:
            logger.error(f"Error activating VIP subscription: {e}")
    
    def get_payment_instructions(self, invoice: Dict) -> str:
        """Generate payment instructions message"""
        
        coin_info = self.SUPPORTED_COINS[invoice['crypto']]
        
        message = f"""
💎 <b>VIP Subscription Payment</b>

<b>Amount:</b> {invoice['amount']} {invoice['crypto']}
<b>USD Value:</b> ${invoice['usd_value']:.2f}

<b>Network:</b> {coin_info['network'].title()}
<b>Send to:</b>
<code>{invoice['wallet_address']}</code>

⚠️ <b>IMPORTANT:</b>
• Send EXACTLY {invoice['amount']} {invoice['crypto']}
• Use {coin_info['network'].title()} network only
• Payment expires in 24 hours
• After sending, reply with transaction hash

<b>Invoice ID:</b> <code>{invoice['invoice_id']}</code>

Once payment is confirmed, your VIP access will be activated within 1 hour.
"""
        
        return message.strip()
    
    async def get_supported_cryptos_list(self) -> str:
        """Get formatted list of supported cryptocurrencies with prices"""
        
        message = "💰 <b>Supported Cryptocurrencies</b>\n\n"
        message += f"<b>VIP Price:</b> ${self.VIP_PRICE_USD}/month\n\n"
        
        for symbol, info in self.SUPPORTED_COINS.items():
            price = await self.get_crypto_price(symbol)
            
            if price:
                amount = self.VIP_PRICE_USD / price
                decimals = info['decimals']
                
                if decimals >= 8:
                    amount_str = f"{amount:.8f}"
                elif decimals >= 4:
                    amount_str = f"{amount:.4f}"
                else:
                    amount_str = f"{amount:.2f}"
                
                message += f"• <b>{symbol}</b> ({info['name']}): {amount_str} {symbol}\n"
            else:
                message += f"• <b>{symbol}</b> ({info['name']}): Price unavailable\n"
        
        message += "\n<i>Prices update every 5 minutes</i>"
        
        return message


# Create global instance
crypto_payment_handler = CryptoPaymentHandler()
