"""
Research Report Generator - AI-Powered Professional Reports

Generates rich, detailed research reports using OpenAI GPT.
Each report includes: Executive Summary, Investment Thesis, Technical Analysis,
Market Context, Risk Assessment, Price Targets, and Strategic Recommendation.
"""
from typing import Optional
from datetime import datetime
import uuid
import asyncio
from src.utils.logger import get_logger
from src.config import settings
from .models import ResearchProject, ConvictionScore, ResearchReport

logger = get_logger(__name__)

# Try to import openai
try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. AI report generation disabled.")


class ReportGenerator:
    """Generate AI-powered research reports"""

    def __init__(self, db_client, content_generator=None):
        self.db = db_client
        self.ai = content_generator
        self._init_openai()

    def _init_openai(self):
        """Initialize OpenAI client"""
        self.openai_enabled = bool(settings.OPENAI_API_KEY) and _OPENAI_AVAILABLE
        if self.openai_enabled:
            self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
            logger.info("🤖 AI Report Generator initialized")
        else:
            logger.warning("⚠️ AI Report Generator: OpenAI not available (fallback to template)")

    async def _call_openai(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Call OpenAI API for content generation"""
        if not self.openai_enabled:
            return None
        try:
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
            logger.info(f"🤖 AI report generated ({len(content)} chars)")
            return content.strip()
        except Exception as e:
            logger.warning(f"OpenAI call failed: {e}")
            return None

    # ═══════════════════════════════════════════════════
    # MAIN REPORT GENERATION
    # ═══════════════════════════════════════════════════

    async def generate_new_candidate_report(self, project: ResearchProject, score: ConvictionScore) -> ResearchReport:
        """Generate a comprehensive AI-powered research report for a new alpha candidate"""
        try:
            logger.info(f"📝 Generating AI report for {project.symbol}...")

            # Build data context for AI
            data_context = self._build_data_context(project, score)

            # Generate each section with OpenAI
            ai_content = await self._generate_full_ai_report(project, score, data_context)

            # Build structured report sections (from AI or fallback)
            exec_summary = ai_content.get('executive_summary', self._fallback_exec_summary(project, score))
            thesis = ai_content.get('investment_thesis', self._fallback_thesis(project, score))
            bull_case = ai_content.get('bull_case', self._format_factors(score.positive_factors, "bull"))
            bear_case = ai_content.get('bear_case', self._format_factors(score.negative_factors, "bear"))
            key_risks = score.negative_factors if score.negative_factors else ["Market risk", "Liquidity risk", "Smart contract risk"]

            # Build rich HTML report content
            full_report_html = self._build_report_html(project, score, ai_content, data_context)

            # Create report object
            report = ResearchReport(
                id=str(uuid.uuid4()),
                project_id=project.id,
                report_type='new_candidate',
                title=f"{project.symbol} Research Report",
                executive_summary=exec_summary,
                investment_thesis=thesis,
                bull_case=bull_case,
                bear_case=bear_case,
                key_risks=key_risks,
                conviction_score=score.conviction_score,
                risk_score=score.risk_score,
                generated_at=datetime.utcnow(),
                ai_report_content=full_report_html
            )

            # Save to database
            await self.db.save_research_report(report.to_dict())
            logger.info(f"✅ AI report saved for {project.symbol} ({len(full_report_html)} chars)")

            return report

        except Exception as e:
            logger.error(f"Error generating AI report: {e}")
            return None

    async def generate_conviction_change_report(self, project: ResearchProject, old_score: float, new_score: ConvictionScore) -> ResearchReport:
        """Generate report for conviction score change"""
        try:
            change = new_score.conviction_score - old_score
            direction = "UPGRADE" if change > 0 else "DOWNGRADE"

            # Build change context
            context = f"""
Project: {project.name} ({project.symbol}) on {project.chain.upper()}
Previous Conviction: {old_score:.1f}/100
New Conviction: {new_score.conviction_score:.1f}/100
Change: {change:+.1f} points

Quality: {new_score.quality_score:.1f}/100
Valuation: {new_score.valuation_score:.1f}/100
Momentum: {new_score.momentum_score:.1f}/100
Risk: {new_score.risk_score:.1f}/100

Positive Factors:
{chr(10).join(f"- {f}" for f in new_score.positive_factors[:5])}

Negative Factors:
{chr(10).join(f"- {f}" for f in new_score.negative_factors[:5])}
"""

            system = (
                "You are a senior crypto research analyst writing a conviction update report. "
                "Analyze what changed and why. Be specific about the implications. "
                "Write in professional Markdown. Max 400 words."
            )

            user = f"Write a conviction {direction.lower()} report:\n\n{context}"
            ai_analysis = await self._call_openai(system, user, max_tokens=800)

            if ai_analysis:
                exec_summary = f"Conviction {direction.lower()}d from {old_score:.1f} to {new_score.conviction_score:.1f}/100. {ai_analysis[:200]}..."
                thesis = ai_analysis
            else:
                exec_summary = f"{project.symbol} conviction {direction.lower()}d from {old_score:.1f} to {new_score.conviction_score:.1f} ({change:+.1f} points)."
                thesis = f"Conviction Score Change: {old_score:.1f} → {new_score.conviction_score:.1f} ({change:+.1f})\n\nWhat Changed:\n{new_score.change_reason or 'Metrics updated'}"

            report = ResearchReport(
                id=str(uuid.uuid4()),
                project_id=project.id,
                report_type=f'conviction_{direction.lower()}',
                title=f"{project.symbol} Conviction {direction}",
                executive_summary=exec_summary,
                investment_thesis=thesis,
                bull_case="\n".join(f"• {f}" for f in new_score.positive_factors),
                bear_case="\n".join(f"• {f}" for f in new_score.negative_factors),
                key_risks=new_score.negative_factors,
                conviction_score=new_score.conviction_score,
                risk_score=new_score.risk_score,
                generated_at=datetime.utcnow()
            )

            await self.db.save_research_report(report.to_dict())
            return report

        except Exception as e:
            logger.error(f"Error generating conviction change report: {e}")
            return None

    async def generate_basket_update_report(self, basket: list) -> ResearchReport:
        """Generate weekly basket update report"""
        try:
            top_5 = basket[:5]

            context = "Alpha Basket Top Projects:\n\n"
            for i, item in enumerate(top_5, 1):
                p = item['project']
                context += f"{i}. {p['symbol']} - Conviction: {p.get('conviction_score', 0):.1f}/100\n"

            system = "You are a portfolio analyst writing a weekly alpha basket update. Highlight top performers and key changes. Max 300 words."
            ai_content = await self._call_openai(system, context, max_tokens=600)

            report = ResearchReport(
                id=str(uuid.uuid4()),
                project_id=top_5[0]['project']['id'],
                report_type='basket_update',
                title="Alpha Basket Weekly Update",
                executive_summary=f"Basket tracking {len(basket)} projects. Top: {top_5[0]['project']['symbol']}.",
                investment_thesis=ai_content or "Basket rankings updated.",
                bull_case="Top projects showing strong metrics",
                bear_case="Market volatility remains a concern",
                key_risks=["Market risk", "Volatility"],
                conviction_score=top_5[0]['project'].get('conviction_score', 0),
                risk_score=50.0,
                generated_at=datetime.utcnow()
            )

            await self.db.save_research_report(report.to_dict())
            return report

        except Exception as e:
            logger.error(f"Error generating basket update: {e}")
            return None

    # ═══════════════════════════════════════════════════
    # AI REPORT GENERATION
    # ═══════════════════════════════════════════════════

    async def _generate_full_ai_report(self, project: ResearchProject, score: ConvictionScore, data_context: str) -> dict:
        """Generate full AI report with multiple sections"""
        if not self.openai_enabled:
            return {}

        sections = {}

        # Generate Executive Summary
        exec_system = (
            "You are a senior crypto investment analyst. Write a compelling 2-3 sentence executive summary "
            "for a research report on a crypto token. Focus on the investment opportunity, key metrics, "
            "and why this matters. Be concise but insightful."
        )
        exec_user = f"Token: {project.name} ({project.symbol}) on {project.chain.upper()}\n\n{data_context}"
        sections['executive_summary'] = await self._call_openai(exec_system, exec_user, max_tokens=200)

        # Generate Investment Thesis
        thesis_system = (
            "You are a crypto VC analyst. Write a compelling investment thesis (3-4 paragraphs) "
            "explaining why this token is an interesting opportunity. Cover: market opportunity, "
            "competitive advantage, growth catalysts, and tokenomics. Use Markdown."
        )
        thesis_user = f"Token: {project.name} ({project.symbol})\n\n{data_context}"
        sections['investment_thesis'] = await self._call_openai(thesis_system, thesis_user, max_tokens=600)

        # Generate Technical Analysis
        tech_system = (
            "You are a crypto technical analyst. Analyze the on-chain and market data for this token. "
            "Cover: liquidity health, volume trends, holder distribution, price momentum. "
            "Give a clear buy/hold/avoid signal with reasoning. Use Markdown bullet points."
        )
        tech_user = f"Token: {project.name} ({project.symbol})\n\n{data_context}"
        sections['technical_analysis'] = await self._call_openai(tech_system, tech_user, max_tokens=500)

        # Generate Market Context
        market_system = (
            "You are a crypto market strategist. Analyze the current market environment for this type of token. "
            "Cover: sector trends, narrative alignment, macro factors, competitive landscape. Use Markdown."
        )
        market_user = f"Token: {project.name} ({project.symbol}) in {project.category or 'crypto'} sector\nChain: {project.chain.upper()}\n\n{data_context}"
        sections['market_context'] = await self._call_openai(market_system, market_user, max_tokens=500)

        # Generate Risk Assessment
        risk_system = (
            "You are a risk analyst specializing in crypto. Identify and assess the key risks for this token. "
            "Cover: smart contract risk, team/execution risk, market risk, regulatory risk, liquidity risk. "
            "Rate each as Low/Medium/High. Use Markdown table format."
        )
        risk_user = f"Token: {project.name} ({project.symbol})\nConviction: {score.conviction_score:.1f}/100\nRisk Score: {score.risk_score:.1f}/100\n\n{data_context}"
        sections['risk_assessment'] = await self._call_openai(risk_system, risk_user, max_tokens=500)

        # Generate Price Targets
        targets_system = (
            "You are a crypto valuation analyst. Based on the market cap, volume, and sector, "
            "provide realistic price target scenarios (conservative, base, optimistic) with rationale. "
            "Be realistic - don't promise 100x. Use Markdown table format."
        )
        targets_user = f"Token: {project.name} ({project.symbol})\nCurrent Price: ${project.price:.6f}\nMarket Cap: ${project.market_cap/1e6:.2f}M\n\n{data_context}"
        sections['price_targets'] = await self._call_openai(targets_system, targets_user, max_tokens=400)

        # Generate Bull Case
        bull_system = (
            "You are an optimistic but realistic crypto analyst. Write the bull case for this token. "
            "3-5 bullet points on why this could be a big winner. Be specific, not generic."
        )
        bull_user = f"Token: {project.name} ({project.symbol})\n\n{data_context}"
        sections['bull_case'] = await self._call_openai(bull_system, bull_user, max_tokens=300)

        # Generate Bear Case
        bear_system = (
            "You are a skeptical but fair crypto analyst. Write the bear case for this token. "
            "3-5 bullet points on what could go wrong. Be specific about failure modes."
        )
        bear_user = f"Token: {project.name} ({project.symbol})\n\n{data_context}"
        sections['bear_case'] = await self._call_openai(bear_system, bear_user, max_tokens=300)

        return {k: v for k, v in sections.items() if v}

    # ═══════════════════════════════════════════════════
    # HTML REPORT BUILDER
    # ═══════════════════════════════════════════════════

    def _build_report_html(self, project: ResearchProject, score: ConvictionScore, ai_content: dict, data_context: str) -> str:
        """Build rich HTML report for dashboard viewing"""

        def section(title: str, content: str, icon: str = ""):
            if not content:
                return ""
            return f"""
            <div class="report-section">
                <h3>{icon} {title}</h3>
                <div class="report-content">{content}</div>
            </div>
            """

        # Format conviction color
        conviction_color = "#00ff88" if score.conviction_score >= 70 else "#ffa500" if score.conviction_score >= 50 else "#ff4444"
        conviction_label = "STRONG BUY" if score.conviction_score >= 80 else "BUY" if score.conviction_score >= 65 else "HOLD" if score.conviction_score >= 45 else "AVOID"

        # Build risk table rows from AI content or fallback
        risk_html = self._extract_risk_table(ai_content.get('risk_assessment', ''), score)
        targets_html = self._extract_targets_table(ai_content.get('price_targets', ''), project)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0e27; color: #e0e0e0; line-height: 1.6; padding: 0; margin: 0; }}
        .report-container {{ max-width: 900px; margin: 0 auto; padding: 30px; }}
        .report-header {{ background: linear-gradient(135deg, #1a1f3a 0%, #0d1221 100%); border-radius: 12px; padding: 30px; margin-bottom: 24px; border: 1px solid #1e2547; }}
        .report-header h1 {{ color: #00d4ff; margin: 0 0 10px 0; font-size: 2em; }}
        .report-header .subtitle {{ color: #888; margin-bottom: 20px; }}
        .report-meta {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 20px; }}
        .meta-card {{ background: #0d1221; border-radius: 8px; padding: 15px; text-align: center; border: 1px solid #1e2547; }}
        .meta-label {{ color: #888; font-size: 0.85em; margin-bottom: 5px; }}
        .meta-value {{ font-size: 1.4em; font-weight: bold; color: #00d4ff; }}
        .conviction-badge {{ display: inline-block; padding: 8px 20px; border-radius: 20px; font-weight: bold; font-size: 1.1em; background: {conviction_color}20; color: {conviction_color}; border: 2px solid {conviction_color}; }}
        .report-section {{ background: #1a1f3a; border-radius: 12px; padding: 24px; margin-bottom: 20px; border: 1px solid #1e2547; }}
        .report-section h3 {{ color: #00d4ff; margin: 0 0 15px 0; font-size: 1.3em; border-bottom: 2px solid #1e2547; padding-bottom: 10px; }}
        .report-content {{ color: #c0c0c0; }}
        .report-content p {{ margin: 0 0 12px 0; }}
        .report-content ul {{ padding-left: 20px; }}
        .report-content li {{ margin-bottom: 8px; }}
        .report-content strong {{ color: #e0e0e0; }}
        .risk-high {{ color: #ff4444; }}
        .risk-medium {{ color: #ffa500; }}
        .risk-low {{ color: #00ff88; }}
        .targets-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .targets-table th {{ background: #151932; color: #00d4ff; padding: 12px; text-align: left; }}
        .targets-table td {{ padding: 12px; border-bottom: 1px solid #1e2547; }}
        .targets-table tr:hover {{ background: #1f2542; }}
        .score-bar {{ height: 10px; background: #0a0e27; border-radius: 5px; overflow: hidden; margin-top: 8px; }}
        .score-fill {{ height: 100%; background: linear-gradient(90deg, #ff4444, #ffa500, #00ff88); border-radius: 5px; }}
        .two-column {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        @media (max-width: 768px) {{ .two-column {{ grid-template-columns: 1fr; }} .report-meta {{ grid-template-columns: repeat(2, 1fr); }} }}
    </style>
</head>
<body>
    <div class="report-container">
        <!-- Header -->
        <div class="report-header">
            <h1>{project.symbol} Research Report</h1>
            <p class="subtitle">{project.name} on {project.chain.upper()} | Generated {datetime.utcnow().strftime('%d %b %Y')}</p>
            <div style="text-align: center; margin: 20px 0;">
                <span class="conviction-badge">{conviction_label} — {score.conviction_score:.1f}/100</span>
            </div>
            <div class="report-meta">
                <div class="meta-card">
                    <div class="meta-label">Market Cap</div>
                    <div class="meta-value">${project.market_cap/1e6:.2f}M</div>
                </div>
                <div class="meta-card">
                    <div class="meta-label">Liquidity</div>
                    <div class="meta-value">${project.liquidity/1e3:.0f}K</div>
                </div>
                <div class="meta-card">
                    <div class="meta-label">24h Volume</div>
                    <div class="meta-value">${project.volume_24h/1e3:.0f}K</div>
                </div>
                <div class="meta-card">
                    <div class="meta-label">Risk Score</div>
                    <div class="meta-value">{score.risk_score:.1f}/100</div>
                </div>
            </div>
            <div style="margin-top: 15px;">
                <div class="meta-label">Conviction Score</div>
                <div class="score-bar"><div class="score-fill" style="width: {min(score.conviction_score, 100)}%"></div></div>
            </div>
        </div>

        {section("Executive Summary", ai_content.get('executive_summary', self._fallback_exec_summary(project, score)), "📊")}

        {section("Investment Thesis", ai_content.get('investment_thesis', self._fallback_thesis(project, score)), "💎")}

        {section("Technical Analysis", ai_content.get('technical_analysis', ''), "📈")}

        {section("Market Context", ai_content.get('market_context', ''), "🌍")}

        <div class="two-column">
            {section("Bull Case", ai_content.get('bull_case', self._format_factors(score.positive_factors, "bull")), "🚀")}
            {section("Bear Case", ai_content.get('bear_case', self._format_factors(score.negative_factors, "bear")), "⚠️")}
        </div>

        {section("Risk Assessment", risk_html, "🛡️")}

        {section("Price Targets", targets_html, "🎯")}

        <div class="report-section">
            <h3>📋 Score Breakdown</h3>
            <div class="report-content">
                <p><strong>Quality:</strong> {score.quality_score:.1f}/100 — Fundamentals and on-chain health</p>
                <p><strong>Valuation:</strong> {score.valuation_score:.1f}/100 — Price relative to market cap and FDV</p>
                <p><strong>Momentum:</strong> {score.momentum_score:.1f}/100 — Volume and price trends</p>
                <p><strong>Risk:</strong> {score.risk_score:.1f}/100 — Lower is better (inverted in conviction)</p>
            </div>
        </div>

        <div style="text-align: center; color: #666; font-size: 0.85em; padding: 20px;">
            <p>⚠️ This report is for research purposes only. Not financial advice.</p>
            <p>CryptoPulse Signals — AI-Powered Research</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _extract_risk_table(self, ai_risk_text: str, score: ConvictionScore) -> str:
        """Extract and format risk assessment from AI text"""
        if not ai_risk_text:
            return f"""
            <p>Overall Risk Score: <strong>{score.risk_score:.1f}/100</strong></p>
            <ul>
                <li>Market Risk: High (crypto market volatility)</li>
                <li>Liquidity Risk: {'High' if score.risk_score > 70 else 'Medium' if score.risk_score > 50 else 'Low'}</li>
                <li>Smart Contract Risk: Unknown (audit status not verified)</li>
                <li>Team/Execution Risk: Unknown (anonymous team common in low-caps)</li>
            </ul>
            """
        # If AI provided content, use it directly (it's already formatted)
        return ai_risk_text.replace('\n', '<br>')

    def _extract_targets_table(self, ai_targets_text: str, project: ResearchProject) -> str:
        """Extract and format price targets from AI text"""
        if not ai_targets_text:
            current_mc = project.market_cap
            return f"""
            <table class="targets-table">
                <tr><th>Scenario</th><th>Market Cap Target</th><th>Upside</th><th>Probability</th></tr>
                <tr><td>🐻 Conservative</td><td>${current_mc*1.5/1e6:.1f}M</td><td>+50%</td><td>High</td></tr>
                <tr><td>⚖️ Base Case</td><td>${current_mc*3/1e6:.1f}M</td><td>+200%</td><td>Medium</td></tr>
                <tr><td>🚀 Optimistic</td><td>${current_mc*10/1e6:.1f}M</td><td>+900%</td><td>Low</td></tr>
            </table>
            <p><em>Targets based on current market cap of ${current_mc/1e6:.2f}M and sector comparables.</em></p>
            """
        return ai_targets_text.replace('\n', '<br>')

    # ═══════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════

    def _build_data_context(self, project: ResearchProject, score: ConvictionScore) -> str:
        """Build structured data context for AI prompts"""
        return f"""
Token: {project.name} ({project.symbol})
Blockchain: {project.chain.upper()}
Category: {project.category or 'Unknown'}
Sector: {project.sector or 'Crypto'}

Market Data:
- Price: ${project.price:.6f}
- Market Cap: ${project.market_cap/1e6:.2f}M
- FDV: ${project.fdv/1e6:.2f}M
- Liquidity: ${project.liquidity:,.0f}
- 24h Volume: ${project.volume_24h:,.0f}

Scores:
- Conviction: {score.conviction_score:.1f}/100
- Quality: {score.quality_score:.1f}/100
- Valuation: {score.valuation_score:.1f}/100
- Momentum: {score.momentum_score:.1f}/100
- Risk: {score.risk_score:.1f}/100

Positive Factors:
{chr(10).join(f"- {f}" for f in score.positive_factors[:5])}

Negative Factors:
{chr(10).join(f"- {f}" for f in score.negative_factors[:5])}
"""

    def _fallback_exec_summary(self, project: ResearchProject, score: ConvictionScore) -> str:
        """Fallback executive summary when AI is unavailable"""
        return (
            f"{project.name} ({project.symbol}) is a {project.category or 'crypto'} project on {project.chain.upper()} "
            f"with a market cap of ${project.market_cap/1e6:.2f}M. Our conviction score is {score.conviction_score:.1f}/100, "
            f"indicating a {'strong' if score.conviction_score >= 70 else 'moderate' if score.conviction_score >= 50 else 'weak'} opportunity."
        )

    def _fallback_thesis(self, project: ResearchProject, score: ConvictionScore) -> str:
        """Fallback investment thesis when AI is unavailable"""
        return f"""{project.name} represents a potential asymmetric opportunity in the {project.sector or 'crypto'} sector.

Key Metrics:
• Market Cap: ${project.market_cap/1e6:.2f}M
• Liquidity: ${project.liquidity/1e3:.0f}K
• 24h Volume: ${project.volume_24h/1e3:.0f}K
• Quality Score: {score.quality_score:.1f}/100
• Valuation Score: {score.valuation_score:.1f}/100

The project shows {'strong' if score.conviction_score >= 70 else 'moderate' if score.conviction_score >= 50 else 'weak'} conviction based on current metrics."""

    def _format_factors(self, factors: list, type_: str) -> str:
        """Format positive/negative factors"""
        if not factors:
            if type_ == "bull":
                return "• Strong fundamentals\n• Attractive valuation\n• Growing momentum"
            return "• Market volatility\n• Execution risk\n• Competition"
        return "\n".join(f"• {f}" for f in factors[:5])

    def _get_strength_label(self, score: float) -> str:
        """Get strength label from score"""
        if score >= 80:
            return "very strong"
        elif score >= 70:
            return "strong"
        elif score >= 60:
            return "moderate"
        elif score >= 50:
            return "neutral"
        else:
            return "weak"

    async def format_report_for_telegram(self, report: ResearchReport, project: ResearchProject) -> str:
        """Format report for Telegram publishing"""
        message = f"""
🔬 <b>RESEARCH REPORT: {project.symbol}</b>

<b>{report.title}</b>

📊 <b>Executive Summary:</b>
{report.executive_summary}

💎 <b>Investment Thesis:</b>
{report.investment_thesis[:500]}...

📈 <b>Bull Case:</b>
{report.bull_case[:300]}...

📉 <b>Bear Case:</b>
{report.bear_case[:300]}...

⚠️ <b>Key Risks:</b>
{chr(10).join(f'• {r}' for r in report.key_risks[:5])}

📊 <b>Scores:</b>
• Conviction: {report.conviction_score:.1f}/100
• Risk: {report.risk_score:.1f}/100

🔗 <b>Links:</b>
• DEX: {project.dex_url or 'N/A'}
• Chart: {project.dex_url or 'N/A'}

<i>Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}</i>

⚠️ <i>This report is for research purposes only. Not financial advice.</i>
        """.strip()

        return message
