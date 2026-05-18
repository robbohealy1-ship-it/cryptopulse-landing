![CRYPTO PULSE SIGNALS Logo](assets/logo.png)

# 💰 Crypto Payments Guide

## Overview

Your platform now supports **8 cryptocurrencies** for VIP subscriptions:
- ₿ Bitcoin (BTC)
- Ξ Ethereum (ETH)
- ◎ Solana (SOL)
- Ł Litecoin (LTC)
- ⓩ Zcash (ZEC)
- 🔗 Chainlink (LINK)
- ɱ Monero (XMR)
- 🌊 Hyperliquid (HYPE)

---

## 🎯 How It Works

### For Users:
1. User requests VIP subscription
2. Chooses cryptocurrency
3. Gets payment invoice with:
   - Exact amount to send
   - Your wallet address
   - Network to use
   - 24-hour expiry
4. Sends payment
5. Replies with transaction hash
6. You confirm payment manually
7. VIP access activated automatically

### For You (Admin):
1. User sends payment
2. You verify transaction on blockchain
3. Confirm in dashboard or via command
4. System activates VIP subscription

---

## ⚙️ Setup Required

### Step 1: Add Wallet Addresses to .env

Open your `.env` file and add these lines:

```env
# Crypto Payment Wallets
CRYPTO_WALLET_BTC=your_bitcoin_address_here
CRYPTO_WALLET_ETH=your_ethereum_address_here
CRYPTO_WALLET_SOL=your_solana_address_here
CRYPTO_WALLET_LTC=your_litecoin_address_here
CRYPTO_WALLET_ZEC=your_zcash_address_here
CRYPTO_WALLET_XMR=your_monero_address_here
```

**Notes:**
- LINK and HYPE use same address as ETH (they're ERC-20 tokens)
- Use addresses you control and can verify payments on
- Recommended: Use separate addresses for tracking

### Step 2: Run SQL Setup

In Supabase SQL Editor, run:
```sql
-- Copy content from scripts/crypto_payments_setup.sql
```

This creates the `crypto_payments` table.

---

## 💳 Payment Flow Example

### User Requests VIP:
```
User: /vip
Bot: Choose payment method:
     • Stripe ($99/month)
     • Crypto (see options)

User: Crypto
Bot: Select cryptocurrency:
     • BTC: 0.00234567 BTC
     • ETH: 0.0456789 ETH
     • SOL: 1.234 SOL
     ... etc

User: BTC
Bot: 💎 VIP Subscription Payment
     
     Amount: 0.00234567 BTC
     USD Value: $99.00
     
     Network: Bitcoin
     Send to: bc1q...your...address...here
     
     ⚠️ IMPORTANT:
     • Send EXACTLY 0.00234567 BTC
     • Use Bitcoin network only
     • Payment expires in 24 hours
     • After sending, reply with transaction hash
     
     Invoice ID: abc123...
```

### User Sends Payment:
```
User: Sent! TX: 1234abcd5678efgh...
```

### You Verify:
1. Check blockchain explorer (blockchain.com, etherscan.io, etc.)
2. Verify amount and address
3. Confirm in dashboard or run:
   ```python
   await crypto_payment_handler.confirm_payment('invoice_id', 'tx_hash')
   ```

### System Activates VIP:
```
Bot: ✅ Payment confirmed!
     Your VIP subscription is now active.
     Welcome to CryptoPulse VIP! 💎
```

---

## 🔍 Verifying Payments

### Bitcoin (BTC):
- Explorer: https://blockchain.com
- Search for your address or TX hash
- Verify amount matches invoice

### Ethereum (ETH, LINK, HYPE):
- Explorer: https://etherscan.io
- For LINK/HYPE: Check "Token Transfers" tab
- Verify amount and token type

### Solana (SOL):
- Explorer: https://solscan.io
- Search for your address or TX hash

### Litecoin (LTC):
- Explorer: https://blockchair.com/litecoin
- Search for your address or TX hash

### Zcash (ZEC):
- Explorer: https://zcashblockexplorer.com
- Note: Shielded transactions won't show details

### Monero (XMR):
- Explorer: https://xmrchain.net
- Note: Privacy coin - verify via wallet

---

## 📊 Dashboard Integration

### View Pending Payments:
```sql
SELECT * FROM pending_crypto_payments;
```

Shows:
- User info
- Amount due
- Wallet address
- Time until expiry

### Confirm Payment:
```python
from src.payments.crypto_payment_handler import crypto_payment_handler

# Confirm payment
await crypto_payment_handler.confirm_payment(
    invoice_id='abc123',
    tx_hash='1234abcd...'  # Optional but recommended
)
```

### Check Payment Status:
```python
is_paid = await crypto_payment_handler.check_payment_received('invoice_id')
```

---

## 🤖 Bot Commands

Add these to your Telegram bot:

```python
/vip - Subscribe to VIP
/payment - Check payment status
/cryptos - List supported cryptocurrencies
```

---

## 💡 Best Practices

### Security:
- ✅ Use hardware wallet addresses
- ✅ Verify every transaction manually
- ✅ Never share private keys
- ✅ Use different addresses per crypto

### User Experience:
- ✅ Respond quickly to payment confirmations
- ✅ Provide clear instructions
- ✅ Set up blockchain explorer bookmarks
- ✅ Have a refund policy

### Accounting:
- ✅ Track all payments in database
- ✅ Note USD value at time of payment
- ✅ Keep transaction hashes
- ✅ Export monthly reports

---

## 🔄 Automatic vs Manual

### Automatic (Built-in):
- ✅ Price calculation (live from CoinGecko)
- ✅ Invoice generation
- ✅ Payment tracking
- ✅ VIP activation after confirmation
- ✅ Expiry handling

### Manual (You do):
- ⚠️ Verify payment on blockchain
- ⚠️ Confirm payment in system
- ⚠️ Handle refunds if needed

**Why manual confirmation?**
- Prevents fraud
- Ensures correct amount
- Verifies correct network
- You stay in control

---

## 📈 Pricing

**Current:** $99/month VIP

**Crypto amounts update every 5 minutes** based on live prices from CoinGecko.

Example at current prices:
- BTC @ $45,000 = 0.0022 BTC
- ETH @ $2,500 = 0.0396 ETH
- SOL @ $100 = 0.99 SOL
- etc.

---

## 🆘 Troubleshooting

### "Price unavailable"
- CoinGecko API may be down
- Check internet connection
- Prices cache for 5 minutes

### "Payment expired"
- Invoice valid for 24 hours
- User must request new invoice
- Old payments won't be accepted

### "Wrong amount sent"
- Contact user
- Offer refund or top-up
- Don't activate VIP until correct

### "Wrong network"
- User sent on wrong chain
- May be recoverable (contact support)
- Educate user on correct network

---

## 🎯 Revenue Tracking

All crypto payments stored in database with:
- USD value at time of payment
- Crypto amount
- Transaction hash
- Timestamp
- User info

Export monthly:
```sql
SELECT 
    DATE_TRUNC('month', confirmed_at) as month,
    crypto_symbol,
    COUNT(*) as payments,
    SUM(amount_usd) as total_usd
FROM crypto_payments
WHERE status = 'confirmed'
GROUP BY month, crypto_symbol
ORDER BY month DESC;
```

---

## ✅ Advantages Over Stripe

**For You:**
- ✅ No 2.9% + $0.30 fees
- ✅ Instant settlement
- ✅ No chargebacks
- ✅ Global access
- ✅ Privacy-friendly

**For Users:**
- ✅ Anonymous (no KYC)
- ✅ Fast activation
- ✅ Multiple coin options
- ✅ No credit card needed

---

## 🚀 Next Steps

1. ✅ Add wallet addresses to `.env`
2. ✅ Run SQL setup in Supabase
3. ✅ Test with small payment
4. ✅ Add bot commands
5. ✅ Announce to community

---

**Your platform now accepts crypto! Welcome to the future of payments.** 💎
