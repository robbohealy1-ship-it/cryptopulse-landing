"""AI Content Generator — LLM-powered market summaries and educational content.

Requires OPENAI_API_KEY in environment. Falls back to template-based content if unavailable.
"""
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import openai, but don't fail if it's not installed
try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. AI content generation disabled. pip install openai to enable.")


class AIContentGenerator:
    """Generate trading content using LLMs. Gracefully degrades without API key."""

    def __init__(self):
        self.enabled = bool(settings.OPENAI_API_KEY) and _OPENAI_AVAILABLE
        self.model = settings.OPENAI_MODEL or "gpt-4o-mini"
        if self.enabled:
            self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info(f"AI Content Generator initialized (model: {self.model})")
        else:
            logger.info("AI Content Generator: offline (no API key or openai package missing)")

    async def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> Optional[str]:
        """Call OpenAI ChatCompletion. Returns None on any failure."""
        if not self.enabled:
            logger.debug("AI _call_llm skipped: not enabled (no API key or openai package missing)")
            return None
        try:
            logger.info(f"🤖 AI API CALL: model={self.model}, max_tokens={max_tokens}, prompt_len={len(user_prompt)}")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            # Log usage for transparency
            usage = response.usage
            if usage:
                logger.info(f"✅ AI content generated: {len(content)} chars | prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}, total={usage.total_tokens}")
            else:
                logger.info(f"✅ AI content generated: {len(content)} chars (no usage data)")
            return content.strip()
        except Exception as e:
            logger.error(f"❌ LLM call failed: {e}")
            return None

    # ───────────────────────────────────────────────
    # DAILY MARKET SUMMARY
    # ───────────────────────────────────────────────

    async def generate_daily_summary(self, market_data: Dict[str, Any], active_trades: list = None) -> Optional[str]:
        """Generate an AI-powered daily market summary for VIP channel.

        Falls back to None so the caller can use its own template.
        """
        if not settings.AI_DAILY_SUMMARY_ENABLED:
            return None

        system = (
            "You are a professional crypto trading analyst writing a morning market outlook for VIP subscribers. "
            "Be specific and actionable - analyze the actual data provided and give clear trading bias. "
            "Use Telegram HTML formatting (<b>bold</b>, emojis). Max 400 words. "
            "Include specific price levels, session times, and what to watch. "
            "IMPORTANT: Always end with these two lines on separate lines:\n"
            "🔥 Trade on Hyperliquid (https://app.hyperliquid.xyz/join/HYPERLIQUIDCODECP)\n"
            "💎 Trade on MEXC (https://promote.mexc.com/r/RMWIMN3p5q)"
        )

        # SAFE: handle None values that would crash string formatting
        fr = market_data.get('funding_rate', 0) or 0
        btc_price = market_data.get('btc_price')

        lines = [
            f"Date: {datetime.utcnow().strftime('%A, %d %B %Y')}",
            f"Fear & Greed: {market_data.get('fear_class', 'N/A')} ({market_data.get('fear_value', 'N/A')}/100)",
            f"Global Market Cap: ${market_data.get('total_market_cap', 'N/A')}T",
            f"BTC Dominance: {market_data.get('btc_dominance', 'N/A')}%",
            f"BTC Price: ${btc_price:,.0f}" if btc_price else "",
            f"BTC 24h Change: {market_data.get('btc_24h', 0) or 0:+.2f}%",
            f"Funding Rate: {fr*100:.4f}%",
            f"Active Trades: {len(active_trades) if active_trades else 0}",
        ]
        user = "\n".join([l for l in lines if l])
        user += "\n\nWrite a compelling morning market outlook in Telegram HTML."

        result = await self._call_llm(system, user, max_tokens=600)
        if result:
            logger.info("✅ AI daily summary generated successfully")
        else:
            logger.warning("⚠️ AI daily summary returned None (API error or disabled)")
        return result

    async def generate_evening_recap(self, market_data: Dict[str, Any], closed_today: list = None, pnl_today: float = 0) -> Optional[str]:
        """Generate an AI-powered evening recap."""
        if not settings.AI_DAILY_SUMMARY_ENABLED:
            return None

        system = (
            "You are a professional crypto trading analyst writing an evening market outlook for VIP subscribers. "
            "Analyze today's performance and provide specific expectations for tomorrow. "
            "Focus on actionable insights - what levels to watch, what bias to have, what sessions to focus on. "
            "Use Telegram HTML formatting. Max 400 words. "
            "IMPORTANT: Always end with these two lines on separate lines:\n"
            "🔥 Trade on Hyperliquid (https://app.hyperliquid.xyz/join/HYPERLIQUIDCODECP)\n"
            "💎 Trade on MEXC (https://promote.mexc.com/r/RMWIMN3p5q)"
        )

        # SAFE: handle None values that would crash string formatting
        btc_24h = market_data.get('btc_24h', 0) or 0

        lines = [
            f"Date: {datetime.utcnow().strftime('%A, %d %B %Y')}",
            f"Today's P&L: {pnl_today:+.2f}%",
            f"Trades Closed Today: {len(closed_today) if closed_today else 0}",
            f"Fear & Greed: {market_data.get('fear_class', 'N/A')}",
            f"BTC 24h: {btc_24h:+.2f}%",
        ]
        if closed_today:
            for s in closed_today[:3]:
                pnl = s.get('pnl_percent', 0) or 0
                lines.append(f"- {s.get('symbol', '?')}: {pnl:+.2f}% ({s.get('result', 'closed')})")

        user = "\n".join(lines)
        user += "\n\nWrite an evening recap in Telegram HTML."
        result = await self._call_llm(system, user, max_tokens=600)
        if result:
            logger.info("✅ AI evening recap generated successfully")
        else:
            logger.warning("⚠️ AI evening recap returned None (API error or disabled)")
        return result

    async def generate_daily_performance(self, performance_data: Dict[str, Any]) -> Optional[str]:
        """Generate AI-powered daily performance report."""
        if not settings.AI_DAILY_SUMMARY_ENABLED:
            return None

        system = (
            "You are a professional crypto trading analyst writing a daily performance summary for VIP subscribers. "
            "Analyze the signals closed today and provide insights on what worked and what didn't. "
            "Be honest about losses - they're part of trading. Highlight key lessons. "
            "Use Telegram HTML formatting. Max 300 words. "
            "IMPORTANT: Always end with these two lines on separate lines:\n"
            "🔥 Trade on Hyperliquid (https://app.hyperliquid.xyz/join/HYPERLIQUIDCODECP)\n"
            "💎 Trade on MEXC (https://promote.mexc.com/r/RMWIMN3p5q)"
        )

        lines = [
            f"Date: {datetime.utcnow().strftime('%B %d, %Y')}",
            f"Total Signals Today: {performance_data.get('total_signals', 0)}",
            f"Signals Closed: {performance_data.get('closed_count', 0)}",
            f"Wins: {performance_data.get('wins', 0)}",
            f"Losses: {performance_data.get('losses', 0)}",
            f"Win Rate: {performance_data.get('win_rate', 0):.1f}%",
            f"Total P&L: {performance_data.get('total_pnl', 0):+.2f}%",
            f"Average Confidence: {performance_data.get('avg_confidence', 0):.1f}%",
        ]
        
        if performance_data.get('closed_trades'):
            lines.append("\nTrades closed today:")
            for trade in performance_data.get('closed_trades', [])[:5]:
                symbol = trade.get('symbol', '?')
                pnl = trade.get('pnl_percent', 0)
                result = trade.get('result', 'closed')
                lines.append(f"- {symbol}: {pnl:+.2f}% ({result})")

        user = "\n".join(lines)
        user += "\n\nWrite a professional daily performance summary in Telegram HTML with clear sections."
        
        result = await self._call_llm(system, user, max_tokens=500)
        if result:
            logger.info("✅ AI daily performance generated successfully")
        else:
            logger.warning("⚠️ AI daily performance returned None (API error or disabled)")
        return result

    # ───────────────────────────────────────────────
    # EDUCATIONAL CONTENT
    # ───────────────────────────────────────────────

    _EDUCATION_TOPICS = [
        "How to read funding rates and avoid liquidation traps",
        "The difference between market, limit, and stop orders",
        "Why risk management matters more than win rate",
        "How to use the Fear & Greed index in your trading",
        "What is BTC dominance and why it affects altcoins",
        "How to identify support and resistance zones",
        "The role of volume in confirming breakouts",
        "Why you should journal every trade",
        "Understanding risk-reward ratio (R:R)",
        "How to spot a rug pull before it happens",
        "Diversification vs concentration in crypto",
        "The psychology of FOMO and how to control it",
    ]

    async def generate_educational_post(self, topic: Optional[str] = None) -> Optional[str]:
        """Generate a bite-sized educational post for the free channel.

        If no topic provided, picks one randomly from the topic pool.
        """
        if not settings.AI_EDUCATION_ENABLED:
            return None

        if not topic:
            import random
            topic = random.choice(self._EDUCATION_TOPICS)

        system = (
            "You are a crypto trading educator. Write a short, punchy educational post "
            "for a free Telegram channel. Use emojis, bullet points, and keep it under 250 words. "
            "Make it practical — traders should be able to apply the advice immediately."
        )

        user = f"Topic: {topic}\n\nWrite the educational post in Telegram-friendly format."
        return await self._call_llm(system, user, max_tokens=500)

    async def generate_risk_reminder(self) -> Optional[str]:
        """Generate a periodic risk-management reminder."""
        if not settings.AI_EDUCATION_ENABLED:
            return None

        system = (
            "You are a risk-focused trading coach. Write a short risk-management reminder "
            "for a VIP Telegram channel. Be encouraging but firm. Under 150 words."
        )
        user = "Write a risk management reminder for crypto traders."
        return await self._call_llm(system, user, max_tokens=300)
