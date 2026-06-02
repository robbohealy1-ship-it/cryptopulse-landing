"""
Alpha Content Formatter

Formats Alpha/Degen plays for VIP and Free channels.
VIP gets the full signal with entry, exits, and DEX links.
Free gets a teaser to drive VIP signups.
"""

from datetime import datetime
from typing import Optional
from src.utils.logger import get_logger
from .alpha_discovery import AlphaPlayCandidate

logger = get_logger(__name__)


class AlphaContentFormatter:
    """
    Formats alpha play content for different channel types.
    """
    
    # Chain emojis
    CHAIN_EMOJIS = {
        'sol': '☀️ SOL',
        'eth': '💎 ETH',
        'base': '🔵 BASE',
        'arb': '🔷 ARB',
    }
    
    # Risk level indicators
    RISK_LEVELS = {
        'low': '🟢 Low Risk',
        'medium': '🟡 Medium Risk',
        'high': '🔴 High Risk',
        'degen': '💀 DEGEN MODE',
    }
    
    # Trade type labels
    TRADE_TYPE_LABELS = {
        'day_trade': '⚡ DAY TRADE',
        'swing': '📊 SWING TRADE',
        'fundamental': '🏗️ FUNDAMENTAL',
        'portfolio': '💼 PORTFOLIO HOLD',
    }
    
    @classmethod
    def format_vip_alpha(cls, play: AlphaPlayCandidate,
                         entry_price: float = None,
                         stop_loss: float = None,
                         take_profit_1: float = None,
                         take_profit_2: float = None,
                         position_size: str = "2-5%",
                         is_limit_order: bool = False,
                         is_degen: bool = False) -> str:
        """
        Format a full alpha play for VIP channel with trade classification and fundamental report.
        """
        
        chain_emoji = cls.CHAIN_EMOJIS.get(play.chain, '🪙')
        risk_level = cls.RISK_LEVELS.get(play.risk_level, cls.RISK_LEVELS['medium'])
        trade_label = cls.TRADE_TYPE_LABELS.get(play.trade_type, '📊 SWING TRADE')
        
        # Calculate potential upside
        if entry_price and take_profit_1:
            upside_1 = ((take_profit_1 - entry_price) / entry_price) * 100
            upside_str = f"+{upside_1:.0f}%"
        else:
            upside_str = "🎯 High"
        
        if entry_price and take_profit_2:
            upside_2 = ((take_profit_2 - entry_price) / entry_price) * 100
            upside_2_str = f"+{upside_2:.0f}%"
        else:
            upside_2_str = "🚀 Higher"
        
        # Build the message
        message = f"""🎰 <b>ALPHA ALERT</b> 🎰

{chain_emoji} <b>{play.symbol}</b> - {play.name}
{trade_label} | {risk_level} | ⏱️ {play.time_frame}

📊 <b>DEXScreener Data:</b>
• Price: ${play.price_usd:.6f}
• Market Cap: ${play.market_cap_usd/1e6:.2f}M
• FDV: ${play.fdv/1e6:.2f}M
• Liquidity: ${play.liquidity_usd/1e3:.0f}K
• Volume 24h: ${play.volume_24h/1e3:.0f}K
• Volume/Liquidity: {(play.volume_24h/play.liquidity_usd) if play.liquidity_usd > 0 else 0:.1f}x
• 24h Change: {play.price_change_24h:+.1f}%
• 1h Change: {play.price_change_1h:+.1f}%
• 5min Change: {play.price_change_5min:+.1f}%
"""
        
        # Build holders section with real data only
        holders_lines = ["\n👥 <b>Holders Data:</b>"]
        if play.holders and play.holders > 0:
            holders_lines.append(f"• Holders: {play.holders:,}")
        if play.holder_growth_24h != 0.0:
            holders_lines.append(f"• Holder Growth 24h: {play.holder_growth_24h:+.1f}%")
        if play.top_holder_concentration and play.top_holder_concentration > 0:
            holders_lines.append(f"• Top 10 Concentration: {play.top_holder_concentration:.1f}%")
        if play.transactions_24h and play.transactions_24h > 0:
            holders_lines.append(f"• Transactions 24h: {play.transactions_24h:,}")
        if play.buys_24h or play.sells_24h:
            holders_lines.append(f"• Buys: {play.buys_24h:,} | Sells: {play.sells_24h:,}")
        if play.buy_sell_ratio > 0:
            holders_lines.append(f"• Buy/Sell Ratio: {play.buy_sell_ratio:.2f}x")
        
        # Only show the section if we have at least one real metric
        if len(holders_lines) > 1:
            message += "\n".join(holders_lines) + "\n"
        
        message += "\n🎯 <b>Trade Setup:</b>\n"
        order_label = "🎯 LIMIT ORDER" if is_limit_order else "⚡ MARKET ORDER"
        message += f"• Type: {order_label}\n"

        if entry_price:
            message += f"• Entry: ${entry_price:.6f}\n"
        else:
            message += f"• Entry: ~${play.price_usd:.6f} (current)\n"

        if is_degen:
            # Degen strategy layout
            message += f"""
🎰 <b>DEGEN STRATEGY:</b>
• TP1 (2x): Sell 50% at ${take_profit_1:.6f}
• TP2 (5x): Sell 25% at ${take_profit_2:.6f}
• Runner: 25% with 20% trailing stop
• ❌ No hard stop loss — rug protection active
• ⏰ Time stop: 48h if no breakout
"""
            # Whale concentration warning
            if play.top_holder_concentration > 50:
                message += f"⚠️ <b>WHALE ALERT:</b> Top 10 hold {play.top_holder_concentration:.1f}% — high concentration risk!\n"
        else:
            # Standard strategy
            if stop_loss:
                message += f"• Stop Loss: ${stop_loss:.6f}\n"
            if take_profit_1:
                message += f"• Take Profit 1: ${take_profit_1:.6f} ({upside_str})\n"
            if take_profit_2:
                message += f"• Take Profit 2: ${take_profit_2:.6f} ({upside_2_str})\n"
        
        message += f"""
💰 <b>Position Size:</b> {position_size} of portfolio

🔥 <b>Catalyst:</b>
{play.catalyst}

📈 <b>Analysis Scores:</b>
• Technical: {play.technical_score:.0f}/100
• Community: {play.community_score:.0f}/100
• Social: {play.social_score:.0f}/100
• Fundamental: {play.fundamental_score:.0f}/100
• Overall: {play.overall_score:.0f}/100

📋 <b>Technical Analysis:</b>
{play.short_term_potential if play.short_term_potential else 'Technical data pending...'}

📋 <b>Fundamental Analysis:</b>
{play.long_term_potential if play.long_term_potential else 'Fundamental data pending...'}
"""
        
        # Narrative & Why Trending
        if play.narrative or play.why_trending:
            message += f"""
📣 <b>Why Trending:</b>
"""
            if play.narrative:
                message += f"🏷️ Narrative: {play.narrative}\n"
            if play.why_trending:
                message += f"{play.why_trending}\n"
        
        # Add red flags if any
        if play.red_flags:
            message += f"\n⚠️ <b>Risk Warnings:</b>\n"
            for flag in play.red_flags:
                message += f"• {flag}\n"
        
        # Add DEX links
        message += f"""
🔗 <b>Quick Links:</b>
📊 <a href='{play.chart_url}'>Chart</a>
💱 <a href='{play.buy_url}'>Buy</a>
📋 <a href='{play.dex_url}'>Token Info</a>
"""
        # Always show contract address for manual copy-paste
        if play.token_address:
            message += f"\n🏷️ <b>Contract:</b> <code>{play.token_address}</code>"
        if play.pair_address:
            message += f"\n🔗 <b>Pair:</b> <code>{play.pair_address}</code>"
        
        message += f"""

⚡ <b>Act fast - alpha moves quickly!</b>
⏰ Posted: {datetime.utcnow().strftime('%H:%M UTC')}
"""
        
        # Add MEXC referral link (non-spammy, at the bottom)
        from src.config import settings
        mexc_url = getattr(settings, 'AFFILIATE_CUSTOM_URL', None)
        if mexc_url:
            message += f"""

💎 <a href="{mexc_url}"><b>Trade on MEXC</b></a>
<i>Sign up through our link to support the channel</i>
"""
        
        # Add portfolio section (respects SHOW_PORTFOLIO_IN_ALPHA toggle)
        portfolio_section = cls._format_portfolio_section(play)
        if portfolio_section:
            message += portfolio_section
        
        return message.strip()
    
    @classmethod
    def format_free_alpha_teaser(cls, play: AlphaPlayCandidate) -> str:
        """
        Format a teaser for the free channel to drive VIP signups.
        Shows limited info + creates FOMO.
        """
        
        chain_emoji = cls.CHAIN_EMOJIS.get(play.chain, '🪙')
        trade_label = cls.TRADE_TYPE_LABELS.get(play.trade_type, '📊 SWING TRADE')
        risk_level = cls.RISK_LEVELS.get(play.risk_level, cls.RISK_LEVELS['medium'])
        
        # Determine teaser text based on performance
        if play.price_change_24h > 50:
            fomo_text = f"🚀 Already up {play.price_change_24h:.0f}% in 24h!"
        elif play.price_change_1h > 15:
            fomo_text = f"🔥 Pumping {play.price_change_1h:.0f}% in the last hour!"
        else:
            fomo_text = "💎 Early entry opportunity!"
        
        message = f"""🎰 <b>ALPHA TEASER</b> 🎰

{chain_emoji} <b>{play.symbol}</b> | {trade_label}
{risk_level} | ⏱️ {play.time_frame}
{fomo_text}

📊 <b>What we know:</b>
• Market Cap: ${play.market_cap_usd/1e6:.1f}M
• Volume 24h: ${play.volume_24h/1e3:.0f}K
• Chain: {play.chain.upper()}
• 24h: {play.price_change_24h:+.1f}% | 1h: {play.price_change_1h:+.1f}%

💎 <b>VIP Members just got:</b>
✅ Exact entry price
✅ Stop loss level
✅ 2 take profit targets
✅ Position size recommendation
✅ Holders & community analysis
✅ DexScreener live data
✅ Technical & fundamental report
✅ Risk warnings & red flags
✅ Direct buy link (Jupiter/Uniswap)

🔒 <b>This alpha is VIP EXCLUSIVE!</b>

👉 <b>Want the full signal?</b>
DM @{cls._get_vip_bot_username()} for instant access

💰 <b>VIP gets 1 alpha per day</b>
🆓 <b>Free gets 1 alpha per week</b>

⏰ Next free alpha: Coming this Sunday!
"""
        
        # Add MEXC referral link (non-spammy, at the bottom)
        from src.config import settings
        mexc_url = getattr(settings, 'AFFILIATE_CUSTOM_URL', None)
        if mexc_url:
            message += f"""
💎 <a href="{mexc_url}"><b>Trade on MEXC</b></a>
<i>Sign up through our link to support the channel</i>
"""
        
        return message.strip()
    
    @classmethod
    def format_alpha_result(cls, play: AlphaPlayCandidate, pnl_percent: float,
                           exit_price: float, status: str) -> str:
        """
        Format a result/closed alpha play.
        
        Args:
            play: The alpha play
            pnl_percent: Realized P&L
            exit_price: Exit price
            status: 'TP1_HIT', 'TP2_HIT', 'SL_HIT', 'CLOSED'
        """
        
        if status == 'TP2_HIT':
            emoji = "🎉"
            result_text = "MAX PROFIT!"
        elif status == 'TP1_HIT':
            emoji = "✅"
            result_text = "TP1 HIT!"
        elif status == 'SL_HIT':
            emoji = "🛑"
            result_text = "STOP LOSS HIT"
        else:
            emoji = "📊"
            result_text = "TRADE CLOSED"
        
        pnl_emoji = "🟢" if pnl_percent > 0 else "🔴"
        
        message = f"""{emoji} <b>ALPHA RESULT</b> {emoji}

🎰 <b>{play.symbol}</b> ({play.chain.upper()})
<b>{result_text}</b>

📊 <b>Performance:</b>
• Entry: ${play.price_usd:.6f}
• Exit: ${exit_price:.6f}
• P&L: {pnl_emoji} {pnl_percent:+.1f}%

💎 <b>Want more alpha like this?</b>
VIP members get 1 per day!

👉 DM @{cls._get_vip_bot_username()} for access
"""
        
        # Add MEXC referral link (non-spammy, at the bottom)
        from src.config import settings
        mexc_url = getattr(settings, 'AFFILIATE_CUSTOM_URL', None)
        if mexc_url:
            message += f"""
💎 <a href="{mexc_url}"><b>Trade on MEXC</b></a>
"""
        
        return message.strip()
    
    @classmethod
    def _get_vip_bot_username(cls) -> str:
        """Get VIP bot username from settings"""
        try:
            from src.config import settings
            return settings.TELEGRAM_VIP_BOT_USERNAME or "CryptoPulseVIPBot"
        except:
            return "CryptoPulseVIPBot"
    
    @classmethod
    def _get_portfolio_wallets(cls) -> dict:
        """
        Get configured wallet addresses mapped by chain/token.
        Returns dict like {'eth': '0x...', 'sol': 'abc...', 'btc': 'bc1...'}
        """
        from src.config import settings
        wallets = {}
        
        # ETH / EVM chains (Base, ETH, Arbitrum all use ETH addresses)
        eth_wallet = getattr(settings, 'TRUST_WALLET_ADDRESS', None) or getattr(settings, 'CRYPTO_WALLET_ETH', None)
        if eth_wallet:
            wallets['eth'] = eth_wallet
            wallets['base'] = eth_wallet
            wallets['arb'] = eth_wallet
        
        # Solana
        sol_wallet = getattr(settings, 'CRYPTO_WALLET_SOL', None)
        if sol_wallet:
            wallets['sol'] = sol_wallet
        
        # Bitcoin
        btc_wallet = getattr(settings, 'CRYPTO_WALLET_BTC', None)
        if btc_wallet:
            wallets['btc'] = btc_wallet
        
        return wallets
    
    @classmethod
    def _format_portfolio_section(cls, play: AlphaPlayCandidate) -> str:
        """
        Format portfolio section showing the correct wallet for the token's chain.
        Respects SHOW_PORTFOLIO_IN_ALPHA toggle.
        """
        from src.config import settings
        
        # Check if portfolio display is enabled
        if not getattr(settings, 'SHOW_PORTFOLIO_IN_ALPHA', False):
            return ""
        
        wallets = cls._get_portfolio_wallets()
        if not wallets:
            return ""
        
        lines = ["\n🔐 <b>Portfolio:</b>"]
        
        # Show the wallet matching this token's chain
        chain_wallet = wallets.get(play.chain)
        if chain_wallet:
            if play.chain in ('eth', 'base', 'arb'):
                lines.append(f"📊 <a href='https://debank.com/profile/{chain_wallet}'>Track ETH/BASE portfolio on DeBank</a>")
            elif play.chain == 'sol':
                lines.append(f"📊 <a href='https://solscan.io/account/{chain_wallet}'>Track SOL portfolio on Solscan</a>")
            elif play.chain == 'btc':
                lines.append(f"📊 <a href='https://mempool.space/address/{chain_wallet}'>Track BTC on Mempool</a>")
        
        # Show ALL configured wallets as a compact list (optional, only if more than 1)
        unique_wallets = {}
        for ch, addr in wallets.items():
            unique_wallets[addr] = ch
        
        if len(unique_wallets) > 1:
            lines.append("\n<i>All tracked wallets:</i>")
            for addr, ch in unique_wallets.items():
                ch_label = {'eth': 'ETH/BASE', 'base': 'ETH/BASE', 'arb': 'ETH/BASE', 'sol': 'SOL', 'btc': 'BTC'}.get(ch, ch.upper())
                lines.append(f"• {ch_label}: <code>{addr[:10]}...{addr[-6:]}</code>")
        
        return "\n".join(lines)
