# 🌐 ORACLE DASHBOARD ACCESS GUIDE

**Quick Access:** `http://141.147.114.169:8081`

---

## 📱 DESKTOP ACCESS

### **URL:**
```
http://141.147.114.169:8081
```

### **Browser:**
- Chrome, Firefox, Edge, Safari (any modern browser)

### **Login:**
- Use your admin credentials
- Same login as local dashboard

---

## 📱 MOBILE ACCESS (PHONE/TABLET)

### **Step 1: Open Browser**
Open any browser on your phone:
- iPhone: Safari or Chrome
- Android: Chrome or Samsung Internet

### **Step 2: Navigate to Oracle Dashboard**
```
http://141.147.114.169:8081
```

### **Step 3: Login**
- Enter your credentials
- Dashboard is fully mobile-responsive

---

## 🏠 ADD TO HOME SCREEN (RECOMMENDED)

### **iPhone/iPad:**
1. Open `http://141.147.114.169:8081` in Safari
2. Tap the **Share** button (square with arrow up)
3. Scroll down and tap **"Add to Home Screen"**
4. Name it: **"CryptoPulse Oracle"**
5. Tap **"Add"**

### **Android:**
1. Open `http://141.147.114.169:8081` in Chrome
2. Tap the **menu** (3 dots in top-right)
3. Tap **"Add to Home Screen"**
4. Name it: **"CryptoPulse Oracle"**
5. Tap **"Add"**

### **Result:**
- App-like icon on your home screen
- Quick access with one tap
- Full-screen experience (no browser UI)

---

## 🔐 SECURITY NOTES

### **IP Address:**
- Oracle Server: `141.147.114.169`
- Port: `8081`
- Protocol: HTTP (internal network)

### **Access:**
- Accessible from anywhere with internet
- Login required for security
- Same credentials as local dashboard

---

## ✅ FEATURES AVAILABLE ON ORACLE

### **Full Telegram Integration:**
- ✅ Partial close notifications
- ✅ Signal approval notifications
- ✅ TP/SL hit alerts
- ✅ Trade management recommendations
- ✅ Morning outlook
- ✅ Evening recap

### **Live Data:**
- ✅ Real-time signal tracking
- ✅ Active trade monitoring
- ✅ AutoPilot TP/SL tracking
- ✅ Alpha plays tracking
- ✅ Portfolio analytics

### **Mobile Optimized:**
- ✅ Touch-friendly sliders
- ✅ Responsive design
- ✅ Partial close UI works perfectly
- ✅ All buttons accessible

---

## 🆚 LOCAL vs ORACLE DASHBOARD

### **Local Dashboard (`START_DASHBOARD.bat`):**
- URL: `http://localhost:8081`
- Access: **Only on your PC**
- Telegram: **Disabled** (dashboard-only mode)
- Use for: UI testing, development

### **Oracle Dashboard:**
- URL: `http://141.147.114.169:8081`
- Access: **Anywhere (desktop, phone, tablet)**
- Telegram: **Fully enabled**
- Use for: Production, live trading, Telegram testing

---

## 🧪 TESTING PARTIAL CLOSE WITH TELEGRAM

### **Step-by-Step:**

1. **Open Oracle Dashboard:**
   - Desktop: `http://141.147.114.169:8081`
   - Mobile: Same URL

2. **Navigate to Active Trades Tab**

3. **Click "Close" on any active signal**

4. **Move slider to desired %:**
   - 25% = Quarter close
   - 50% = Half close
   - 75% = Three-quarter close

5. **Review live preview:**
   - Full position P&L
   - Locked profit
   - Remaining position %

6. **Click "Confirm Partial Close"**

7. **Check Telegram:**
   - Admin notification channel
   - VIP subscriber channel

### **Expected Telegram Message:**
```
📉 PARTIAL CLOSE

EUR/USDT SHORT
Closed: 50% of position
Remaining: 50%

💰 P&L on closed portion: +0.92%
📊 Close Price: $1.153400
🎯 Entry: $1.175135

✅ Profit locked in. Remaining position continues to run.
Stop loss remains active on remaining 50%.
```

---

## 🔧 TROUBLESHOOTING

### **Can't Access Dashboard:**
1. Check Oracle bot is running:
   ```bash
   ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "ps aux | grep python"
   ```

2. Check bot logs:
   ```bash
   ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "tail -50 /home/opc/CryptoPulse-Signals/bot.log"
   ```

3. Restart if needed:
   ```bash
   deploy_oracle.bat
   ```

### **Dashboard Loads but No Data:**
- Check database connection in logs
- Verify signals exist in database
- Refresh the page (Ctrl+R or pull down on mobile)

### **Partial Close Works but No Telegram:**
- Verify you're on **Oracle dashboard** (not localhost)
- Check Telegram bot tokens are set in Oracle `.env`
- Check Oracle logs for Telegram errors

---

## 📊 MONITORING ORACLE BOT

### **Check Bot Status:**
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "ps aux | grep python"
```

### **View Live Logs:**
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "tail -f /home/opc/CryptoPulse-Signals/bot.log"
```

### **Check Partial Close Logs:**
```bash
ssh -i "ssh-key-2026-05-20 (2).key" opc@141.147.114.169 "grep -i 'partial' /home/opc/CryptoPulse-Signals/bot.log | tail -20"
```

---

## 🚀 QUICK REFERENCE

| Feature | Local Dashboard | Oracle Dashboard |
|---------|----------------|------------------|
| **URL** | `localhost:8081` | `141.147.114.169:8081` |
| **Mobile Access** | ❌ No | ✅ Yes |
| **Telegram Notifications** | ❌ No | ✅ Yes |
| **Live Trading Data** | ⚠️ Test data | ✅ Production |
| **Partial Close UI** | ✅ Yes | ✅ Yes |
| **Telegram Alerts** | ❌ Disabled | ✅ Enabled |
| **Use Case** | Development | Production |

---

## ✅ SUMMARY

- **Oracle Dashboard:** `http://141.147.114.169:8081`
- **Works on:** Desktop, phone, tablet
- **Add to home screen** for app-like experience
- **Full Telegram** notifications enabled
- **24/7 uptime** - always accessible
- **No `.bat` file needed** - just open the URL

**Ready to use!** 🚀
