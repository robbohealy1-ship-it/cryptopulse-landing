![CRYPTO PULSE SIGNALS Logo](assets/logo.png)

# 📱 CRYPTO PULSE SIGNALS - Telegram Setup Guide

Complete guide to setting up Telegram bots and channels for SIGNALFORGE AI.

---

## 📋 Overview

You will need to create:
1. **Admin Bot** - For receiving and approving signals
2. **Free Channel** - Public channel for free signals
3. **VIP Channel** - Private channel for premium signals

---

## 🤖 Step 1: Create Telegram Bot

### 1.1 Start BotFather

1. Open Telegram
2. Search for `@BotFather`
3. Start conversation: `/start`

### 1.2 Create New Bot

Send command:
```
/newbot
```

BotFather will ask for:

**Bot Name:**
```
CryptoPulse AI
```
(This is the display name users see)

**Bot Username:**
```
cryptopulse_ai_bot
```
(Must end with 'bot' and be unique)

### 1.3 Save Bot Token

BotFather will reply with:
```
Done! Congratulations on your new bot...
Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789
```

**Copy this token** → Add to `.env` as `TELEGRAM_BOT_TOKEN`

### 1.4 Configure Bot Settings

Send to BotFather:
```
/setdescription
```
Select your bot, then send:
```
Premium crypto trading signals powered by AI. Get high-probability setups with detailed analysis.
```

Set about text:
```
/setabouttext
```
```
SIGNALFORGE AI - Elite crypto trading signals
```

Set commands:
```
/setcommands
```
```
start - Start the bot
status - Check bot status
help - Get help
```

---

## 💬 Step 2: Get Admin Chat ID

### 2.1 Start Your Bot

1. Find your bot in Telegram
2. Send: `/start`

### 2.2 Get Chat ID

**Method 1: Using API**

Open browser and visit:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

Replace `<YOUR_BOT_TOKEN>` with your actual token.

Look for:
```json
{
  "message": {
    "chat": {
      "id": 123456789,
      "first_name": "Your Name"
    }
  }
}
```

**Method 2: Using Bot**

1. Add `@userinfobot` to Telegram
2. Send any message
3. It will reply with your chat ID

**Copy the chat ID** → Add to `.env` as `TELEGRAM_ADMIN_CHAT_ID`

---

## 📢 Step 3: Create Free Channel

### 3.1 Create Channel

1. In Telegram, tap menu → **New Channel**
2. **Channel Name:** `CryptoPulse Free Signals`
3. **Description:**
```
🚀 Free Crypto Trading Signals

Get quality trading signals for FREE!

📊 What you get:
• Entry price
• Stop loss
• First target
• Risk/reward ratio

💎 Want more? Join VIP for:
• Detailed analysis
• Multiple targets
• Priority signals
• Market context

Join VIP: [your link]
```

4. Choose **Public Channel**
5. **Username:** `cryptopulse_free` (must be unique)

### 3.2 Add Bot as Admin

1. Open channel settings
2. **Administrators** → **Add Administrator**
3. Search for your bot username
4. Grant permissions:
   - ✅ Post Messages
   - ✅ Edit Messages
   - ✅ Delete Messages
5. Save

### 3.3 Get Channel ID

**For Public Channel:**

The channel ID is simply: `@cryptopulse_free`

**Copy this** → Add to `.env` as `TELEGRAM_FREE_CHANNEL_ID`

---

## 💎 Step 4: Create VIP Channel

### 4.1 Create Channel

1. Tap menu → **New Channel**
2. **Channel Name:** `CryptoPulse VIP Signals`
3. **Description:**
```
💎 VIP CRYPTO TRADING SIGNALS

Premium members only!

✅ What you get:
• Detailed technical analysis
• Multiple take profit levels
• Market context & news
• Priority signals
• Risk management tips
• Real-time updates

🎯 High-quality signals only
📊 Proven track record
💰 Maximize your profits
```

4. Choose **Private Channel**
5. Create invite link (we'll use Stripe for this)

### 4.2 Add Bot as Admin

1. Open channel settings
2. **Administrators** → **Add Administrator**
3. Search for your bot
4. Grant permissions:
   - ✅ Post Messages
   - ✅ Edit Messages
   - ✅ Delete Messages
   - ✅ Invite Users via Link
5. Save

### 4.3 Get Channel ID

**For Private Channel:**

1. Post any message in the channel
2. Forward it to `@userinfobot`
3. It will show the channel ID (starts with `-100`)

**OR**

1. Post in channel
2. Visit:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```
3. Look for `"chat":{"id":-1001234567890}`

**Copy the ID** → Add to `.env` as `TELEGRAM_VIP_CHANNEL_ID`

---

## 🔗 Step 5: Create Invite Links

### 5.1 VIP Channel Invite Link

1. Open VIP channel
2. Settings → **Invite Links**
3. Create new link
4. **Name:** VIP Subscription
5. **Limit:** Unlimited
6. **Expiration:** Never
7. Copy link

This link will be sent to users after Stripe payment.

### 5.2 Configure in Stripe

When setting up Stripe (see DEPLOYMENT_GUIDE.md):
- Use this invite link as the success URL
- Or send it via email after payment

---

## ✅ Step 6: Test Everything

### 6.1 Test Bot

```bash
# Run test script
python scripts/test_setup.py
```

Should send test message to admin chat.

### 6.2 Test Channels

**Test Free Channel:**
```python
from telegram import Bot
import asyncio

async def test():
    bot = Bot('YOUR_BOT_TOKEN')
    await bot.send_message(
        chat_id='@cryptopulse_free',
        text='✅ Test message - Free channel working!'
    )

asyncio.run(test())
```

**Test VIP Channel:**
```python
from telegram import Bot
import asyncio

async def test():
    bot = Bot('YOUR_BOT_TOKEN')
    await bot.send_message(
        chat_id='-1001234567890',  # Your VIP channel ID
        text='✅ Test message - VIP channel working!'
    )

asyncio.run(test())
```

---

## 📝 Step 7: Configure .env

Your `.env` should now have:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ADMIN_CHAT_ID=123456789
TELEGRAM_FREE_CHANNEL_ID=@cryptopulse_free
TELEGRAM_VIP_CHANNEL_ID=-1001234567890
```

---

## 🎨 Step 8: Customize Channels

### Free Channel

**Pin Message:**
```
🚀 Welcome to CryptoPulse Free Signals!

📊 What to expect:
• 1-3 quality signals per day
• Entry, stop loss, and target
• Basic risk/reward info

⚠️ Risk Warning:
Trading crypto is risky. Never invest more than you can afford to lose.

💎 Upgrade to VIP:
Get detailed analysis, multiple targets, and priority signals!
[Upgrade Link]
```

### VIP Channel

**Pin Message:**
```
💎 Welcome to CryptoPulse VIP!

You now have access to:
✅ Detailed technical analysis
✅ Multiple take profit levels
✅ Market context & news
✅ Priority signals
✅ Real-time updates

📊 How to use signals:
1. Wait for signal notification
2. Review analysis carefully
3. Enter at specified price
4. Set stop loss immediately
5. Take profits at targets

⚠️ Risk Management:
• Never risk more than 2% per trade
• Always use stop loss
• Move SL to breakeven after TP1

Questions? Contact: @your_support
```

---

## 🔔 Step 9: Notification Settings

### For Users

Recommend users to:
1. Enable notifications for channels
2. Turn on sound for important messages
3. Add channels to favorites

### Channel Settings

1. **Free Channel:**
   - Public
   - Anyone can join
   - Comments disabled (optional)

2. **VIP Channel:**
   - Private
   - Invite link only
   - Comments enabled for questions

---

## 📊 Step 10: Analytics

### Track Performance

1. **Telegram Analytics:**
   - Channel views
   - Member growth
   - Message reach

2. **Bot Analytics:**
   - Commands used
   - User interactions
   - Response times

---

## 🚨 Troubleshooting

### Bot Not Responding

**Check:**
- Bot token is correct
- Bot is not blocked
- Chat ID is correct

**Fix:**
```bash
# Test bot
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### Can't Post to Channel

**Check:**
- Bot is admin
- Bot has post permissions
- Channel ID is correct

**Fix:**
1. Remove bot from channel
2. Re-add as admin
3. Grant all permissions

### Wrong Chat ID

**Symptoms:**
- Messages not received
- "Chat not found" error

**Fix:**
1. Delete old messages
2. Send new message
3. Use getUpdates to find correct ID

---

## 🔐 Security

### Best Practices

1. **Never share bot token**
2. **Keep channel IDs private**
3. **Use private VIP channel**
4. **Regularly check admins**
5. **Monitor for spam**

### Backup

Save these safely:
- Bot token
- Channel invite links
- Admin credentials

---

## 📈 Growth Tips

### Free Channel

1. **Quality over quantity**
2. **Consistent posting**
3. **Engage with users**
4. **Share success stories**
5. **Promote on social media**

### VIP Channel

1. **Exclusive content**
2. **Personal attention**
3. **Regular updates**
4. **Member-only perks**
5. **Community building**

---

## ✅ Final Checklist

- [ ] Bot created and token saved
- [ ] Admin chat ID obtained
- [ ] Free channel created and configured
- [ ] VIP channel created and configured
- [ ] Bot added as admin to both channels
- [ ] All IDs added to .env
- [ ] Test messages sent successfully
- [ ] Pin messages created
- [ ] Invite links generated
- [ ] Notifications configured

---

## 🎉 You're Ready!

Your Telegram setup is complete. The system will now:
- Send signals to admin for approval
- Publish approved signals to channels
- Send updates automatically
- Track performance

**Next:** Complete the full deployment (see DEPLOYMENT_GUIDE.md)

---

**Need Help?**

Common issues and solutions are in the Troubleshooting section above.
