# CryptoPulse Signals - Landing Page

A high-conversion, responsive landing page for your crypto signals business.

## Quick Start

1. **Update Telegram Links**
   Open `index.html` and replace these URLs with your actual channels:
   ```
   https://t.me/CryptoPulseSignals   -> Your free channel
   https://t.me/CryptoPulseVIPBot    -> Your VIP bot
   ```
   Search for these in the file and replace all occurrences.

2. **Add Your Logo (Optional)**
   - Save your logo as `logo.png` in this folder
   - Replace the inline SVG logo in the navbar if you want to use your image

3. **Update Stats (Optional)**
   Edit the numbers in the `.hero-stats` section to match your actual performance.

## Deploy Options

### Option A: Netlify (Recommended - Free)
1. Go to [netlify.com](https://netlify.com)
2. Drag & drop this `landing-page` folder
3. Done! You'll get a free `.netlify.app` domain
4. Add custom domain in settings

### Option B: Vercel (Free)
1. Install Vercel CLI: `npm i -g vercel`
2. Run: `cd landing-page && vercel`
3. Follow prompts

### Option C: GitHub Pages (Free)
1. Create a GitHub repo
2. Push this folder as the repo contents
3. Enable GitHub Pages in repo settings
4. Select "Deploy from branch" → `main`

### Option D: Hostinger/Any Web Host
Upload these 3 files to your public_html:
- `index.html`
- `styles.css`
- `script.js`

## Customize Colors

Edit `styles.css` `:root` variables:
```css
--primary: #00D4FF;        /* Main accent */
--primary-dark: #0066FF;   /* Darker accent */
--gold: #FFD700;           /* Lifetime plan */
--bg: #0A0E1A;             /* Background */
```

## Features Included

- Hero with animated stats counter
- Features grid with hover effects
- 4-tier pricing (Free, Monthly, Quarterly, Lifetime)
- How it works steps
- Performance chart visualization
- Affiliate program section
- FAQ accordion
- Social links (Telegram, X, Discord, YouTube)
- Mobile responsive
- Scroll animations
- Glassmorphism design

## SEO

Update `<title>` and `<meta name="description">` in `index.html` for better search ranking.

## Affiliate Section

The affiliate section says "Contact us via Telegram" - make sure this goes to your support/admin bot, not the VIP bot.
