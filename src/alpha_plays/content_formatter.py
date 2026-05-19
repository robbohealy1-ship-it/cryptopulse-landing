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
    }
    
    @classmethod
    def format_vip_alpha(cls, play: AlphaPlayCandidate, 
                         entry_price: float = None,
                         stop_loss: float = None,
                         take_profit_1: float = None,
                         take_profit_2: float = None,
                         position_size: str = "2-5%") -> str:
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
        message = f"""🎰 <b>ALPHA PLAY ALERT</b> 🎰

{chain_emoji} <b>{play.symbol}</b> - {play.name}
{trade_label} | {risk_level} | ⏱️ {play.time_frame}

📊 <b>Metrics:</b>
• Price: ${play.price_usd:.6f}
• Market Cap: ${play.market_cap_usd/1e6:.2f}M
• Liquidity: ${play.liquidity_usd/1e3:.0f}K
• Volume 24h: ${play.volume_24h/1e3:.0f}K
• 24h Change: {play.price_change_24h:+.1f}%
• 1h Change: {play.price_change_1h:+.1f}%
• 5min Change: {play.price_change_5min:+.1f}%
• Buy/Sell Ratio: {play.buy_sell_ratio:.2f}x
"""
        
        # Add FDV if available
        if play.fdv > 0:
            message += f"• FDV: ${play.fdv/1e6:.2f}M\n"
        
        message += f"""
🎯 <b>Trade Setup:</b>
"""
        
        if entry_price:
            message += f"• Entry: ${entry_price:.6f}\n"
        else:
            message += f"• Entry: ~${play.price_usd:.6f} (current)\n"
        
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

📈 <b>Scores:</b>
• Technical: {play.technical_score:.0f}/100
• Community: {play.community_score:.0f}/100
• Social: {play.social_score:.0f}/100
• Fundamental: {play.fundamental_score:.0f}/100
• Overall: {play.overall_score:.0f}/100
"""
        
        # Fundamental Mini-Report
        if play.narrative or play.why_trending:
            message += f"""
📋 <b>Fundamental Mini-Report:</b>
"""
            if play.narrative:
                message += f"🏷️ Narrative: {play.narrative}\n"
            if play.why_trending:
                message += f"\n📣 Why Trending:\n{play.why_trending}\n"
            if play.short_term_potential:
                message += f"\n⏱️ Short Term (1-3d): {play.short_term_potential}\n"
            if play.long_term_potential:
                message += f"\n🗓️ Long Term (1-4w): {play.long_term_potential}\n"
        
        # Add red flags if any
        if play.red_flags:
            message += f"\n⚠️ <b>Risk Warnings:</b>\n"
            for flag in play.red_flags:
                message += f"• {flag}\n"
        
        # Add DEX links
        message += f"""
🔗 <b>Quick Links:</b>
📊 <a href='{play.chart_url}'>Chart</a>
💱 <a href='{play.buy_url}'>Buy on DEX</a>
📋 <a href='{play.dex_url}'>Token Info</a>
"""
        # Always show contract address for manual copy-paste
        if play.token_address:
            message += f"\n🏷️ <b>Contract:</b> <code>{play.token_address}</code>"
        if play.pair_address:
            message += f"\n🔗 <b>Pair:</b> <code>{play.pair_address}</code>"
        
        message += f"""

⚡ <b>Act fast - alpha plays move quickly!</b>
⏰ Posted: {datetime.utcnow().strftime('%H:%M UTC')}
"""
        
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
        
        message = f"""🎰 <b>ALPHA PLAY TEASER</b> 🎰

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
✅ Fundamental mini-report
✅ Risk warnings & red flags
✅ Direct DEX buy link

🔒 <b>This alpha play is VIP EXCLUSIVE!</b>

👉 <b>Want the full signal?</b>
DM @{cls._get_vip_bot_username()} for instant access

💰 <b>VIP gets 1 alpha play per day</b>
🆓 <b>Free gets 1 alpha play per week</b>

⏰ Next free alpha: Coming this Sunday!
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
        
        message = f"""{emoji} <b>ALPHA PLAY RESULT</b> {emoji}

🎰 <b>{play.symbol}</b> ({play.chain.upper()})
<b>{result_text}</b>

📊 <b>Performance:</b>
• Entry: ${play.price_usd:.6f}
• Exit: ${exit_price:.6f}
• P&L: {pnl_emoji} {pnl_percent:+.1f}%

💎 <b>Want more alpha plays like this?</b>
VIP members get 1 per day!

👉 DM @{cls._get_vip_bot_username()} for access
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
