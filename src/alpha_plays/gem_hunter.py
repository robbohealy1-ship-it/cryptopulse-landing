"""
Gem Hunter Module - Long-term gem discovery for bear market accumulation.

Detects tokens with genuine fundamental potential beyond momentum signals.
Integrates contract safety, narrative alignment, tokenomics, social sentiment,
smart money tracking, and ecosystem verification into a unified Gem Score.

API Keys Required (optional - falls back gracefully):
- RUGCHECK_API_KEY / RUGCHECK_API_URL
- HELIUS_API_KEY (for smart money / holder analysis)
- LUNARCRUSH_API_KEY (for real social sentiment)
- KAITO_API_KEY (for mindshare / narrative tracking)
- SOLSCAN_API_KEY (for on-chain analytics)
"""

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import aiohttp
import logging

logger = logging.getLogger(__name__)

# Narrative keyword databases for scoring alignment with hot sectors
NARRATIVE_KEYWORDS = {
    "ai_agent": ["ai", "agent", "llm", "gpt", "neural", "autonomous", "bot", "intelligence", "model"],
    "depin": ["depin", "infrastructure", "physical", "iot", "wireless", "compute", "storage", "bandwidth", "sensor", "node"],
    "rwa": ["rwa", "real world", "real-world", "asset", "tokenized", "treasury", "bond", "estate", "commodity", "gold"],
    "gaming": ["game", "gaming", "play", "player", "nft", "metaverse", "virtual", "esports", "loot", "quest"],
    "meme": ["meme", "dog", "cat", "pepe", "shib", "wojak", "bonk", "culture", "community"],
    "l2": ["rollup", "layer2", "l2", "scaling", "zero-knowledge", "zk", "optimistic", "sequencer"],
    "defi": ["defi", "yield", "lending", "amm", "dex", "perp", "derivative", "synthetic", "vault"],
    "infra": ["oracle", "bridge", "indexer", "rpc", "sequencer", "modular", "interoperability", "cross-chain"],
}

# Weighted narrative priorities (adjust based on market cycle)
NARRATIVE_WEIGHTS = {
    "ai_agent": 1.3,
    "depin": 1.2,
    "rwa": 1.1,
    "gaming": 1.0,
    "meme": 0.9,
    "l2": 0.9,
    "defi": 0.9,
    "infra": 1.0,
}


@dataclass
class GemMetrics:
    """Enriched metrics for long-term gem evaluation."""
    # Contract Safety
    rugcheck_score: Optional[float] = None  # 0-100, higher = safer
    rugcheck_risks: List[str] = field(default_factory=list)
    is_honeypot: bool = False
    mint_authority_disabled: bool = False
    freeze_authority_disabled: bool = False
    top_holders_risk: str = "unknown"  # low/medium/high/critical

    # Narrative
    narrative_alignment: Dict[str, float] = field(default_factory=dict)  # narrative -> 0-1 score
    primary_narrative: str = ""
    narrative_score: float = 0.0  # 0-100

    # Tokenomics
    fdv_mc_ratio: Optional[float] = None  # lower = better for accumulation
    circulating_supply_pct: Optional[float] = None  # % of total supply circulating
    unlock_risk: str = "unknown"  # low/medium/high (based on upcoming unlocks)
    inflation_rate_annual: Optional[float] = None  # % annual inflation
    supply_concentration_risk: str = "unknown"

    # Social Sentiment (real or proxy)
    social_volume_score: float = 0.0  # 0-100
    bullish_sentiment_pct: Optional[float] = None  # % of posts that are bullish
    unique_contributors_24h: int = 0
    social_growth_rate: Optional[float] = None  # % change in mentions week-over-week

    # Smart Money / On-chain
    smart_money_netflow_7d: Optional[float] = None  # positive = accumulation
    whale_holdings_change_7d: Optional[float] = None  # % change in whale holdings
    new_wallets_7d: int = 0
    holder_retention_30d: Optional[float] = None  # % of holders from 30d ago still holding

    # Ecosystem
    ecosystem_grants: List[str] = field(default_factory=list)
    github_activity_score: float = 0.0  # 0-100
    partnership_signals: List[str] = field(default_factory=list)

    # Bear Market Accumulation Profile
    accumulation_score: float = 0.0  # 0-100, detects stealth buying vs pump
    volatility_compression: bool = False  # low volatility after high volatility = accumulation
    volume_trend_30d: str = "neutral"  # rising/falling/neutral

    # Final Gem Score
    gem_score: float = 0.0  # 0-100 composite
    gem_tier: str = "unrated"  # s_tier / a_tier / b_tier / c_tier / avoid
    gem_report: str = ""


class GemHunter:
    """Analyzes tokens for long-term gem potential beyond momentum."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
        
        # API keys
        self.rugcheck_api_url = os.getenv("RUGCHECK_API_URL", "https://api.rugcheck.xyz")
        self.rugcheck_api_key = os.getenv("RUGCHECK_API_KEY", "")
        self.helius_api_key = os.getenv("HELIUS_API_KEY", "")
        self.lunarcrush_api_key = os.getenv("LUNARCRUSH_API_KEY", "")
        self.kaito_api_key = os.getenv("KAITO_API_KEY", "")
        self.solscan_api_key = os.getenv("SOLSCAN_API_KEY", "")

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=5, limit_per_host=2),
                timeout=aiohttp.ClientTimeout(total=15)
            )
            self._own_session = True

    async def close(self):
        if self._own_session and self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    # ------------------------------------------------------------------
    #  PUBLIC API
    # ------------------------------------------------------------------
    async def analyze_candidate(self, candidate) -> GemMetrics:
        """Run full gem analysis on an AlphaPlayCandidate. Returns enriched metrics."""
        await self.ensure_session()
        metrics = GemMetrics()

        symbol = candidate.symbol
        name = candidate.name
        token_address = candidate.token_address
        chain = candidate.chain.lower()

        # Run analyses in parallel where possible
        tasks = [
            self._analyze_contract_safety(token_address, chain, metrics),
            self._analyze_narrative(symbol, name, candidate.narrative or "", metrics),
            self._analyze_tokenomics(candidate, metrics),
            self._analyze_social_sentiment(symbol, token_address, chain, metrics),
            self._analyze_smart_money(token_address, chain, metrics),
            self._analyze_ecosystem(symbol, token_address, chain, metrics),
            self._analyze_accumulation_profile(candidate, metrics),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate composite Gem Score
        metrics.gem_score = self._calculate_gem_score(metrics, candidate)
        metrics.gem_tier = self._tier_from_score(metrics.gem_score, metrics)
        metrics.gem_report = self._generate_gem_report(metrics, candidate)

        return metrics

    # ------------------------------------------------------------------
    #  1. CONTRACT SAFETY
    # ------------------------------------------------------------------
    async def _analyze_contract_safety(self, token_address: str, chain: str, metrics: GemMetrics):
        """Check contract safety via RugCheck for Solana tokens."""
        if chain != "sol" or not token_address:
            # For non-SOL, try to infer safety from holder data if available
            metrics.rugcheck_score = 50.0  # neutral baseline
            return

        try:
            url = f"{self.rugcheck_api_url}/v1/tokens/{token_address}/report"
            headers = {}
            if self.rugcheck_api_key:
                headers["Authorization"] = f"Bearer {self.rugcheck_api_key}"
            
            async with self.session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    report = data.get("report", {}) or data
                    
                    # Overall score (RugCheck uses 0 = safe, higher = riskier usually)
                    # Normalize to 0-100 where 100 = safest
                    raw_score = report.get("score", 0)
                    if isinstance(raw_score, (int, float)):
                        # RugCheck: negative is good, positive is bad
                        metrics.rugcheck_score = max(0, min(100, 100 - (raw_score * 10)))
                    else:
                        metrics.rugcheck_score = 50.0
                    
                    # Risk flags
                    risks = report.get("risks", [])
                    metrics.rugcheck_risks = [r.get("name", str(r)) for r in risks]
                    
                    # Specific authorities
                    token_meta = report.get("tokenMeta", {})
                    mint_auth = report.get("mintAuthority", None)
                    freeze_auth = report.get("freezeAuthority", None)
                    metrics.mint_authority_disabled = mint_auth is None or mint_auth == ""
                    metrics.freeze_authority_disabled = freeze_auth is None or freeze_auth == ""
                    
                    # Honeypot check
                    for risk in risks:
                        risk_name = risk.get("name", "").lower()
                        if "honeypot" in risk_name or "unable to sell" in risk_name:
                            metrics.is_honeypot = True
                    
                    # Top holder concentration from RugCheck
                    top_holders = report.get("topHolders", [])
                    if top_holders:
                        total_top_pct = sum(float(h.get("pct", 0)) for h in top_holders[:5])
                        if total_top_pct > 50:
                            metrics.top_holders_risk = "critical"
                        elif total_top_pct > 30:
                            metrics.top_holders_risk = "high"
                        elif total_top_pct > 15:
                            metrics.top_holders_risk = "medium"
                        else:
                            metrics.top_holders_risk = "low"
                    else:
                        metrics.top_holders_risk = "unknown"
                        
                else:
                    metrics.rugcheck_score = 50.0  # unknown baseline
        except Exception as e:
            logger.debug(f"RugCheck analysis failed for {token_address[:8]}: {e}")
            metrics.rugcheck_score = 50.0

    # ------------------------------------------------------------------
    #  2. NARRATIVE ALIGNMENT
    # ------------------------------------------------------------------
    async def _analyze_narrative(self, symbol: str, name: str, narrative_text: str, metrics: GemMetrics):
        """Score how well the token aligns with high-conviction narratives."""
        combined_text = f"{symbol} {name} {narrative_text}".lower()
        
        best_narrative = ""
        best_score = 0.0
        alignment = {}
        
        for narrative, keywords in NARRATIVE_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                # Exact word matches score higher
                if re.search(rf'\b{re.escape(kw)}\b', combined_text):
                    score += 1.0
                # Partial matches score lower
                elif kw in combined_text:
                    score += 0.3
            
            # Normalize by keyword count
            score = min(1.0, score / max(len(keywords) * 0.15, 1.0))
            
            # Apply narrative priority weight
            weighted = score * NARRATIVE_WEIGHTS.get(narrative, 1.0)
            alignment[narrative] = round(score, 2)
            
            if weighted > best_score:
                best_score = weighted
                best_narrative = narrative
        
        metrics.narrative_alignment = alignment
        metrics.primary_narrative = best_narrative
        # Scale to 0-100
        metrics.narrative_score = min(100, best_score * 100)

    # ------------------------------------------------------------------
    #  3. TOKENOMICS
    # ------------------------------------------------------------------
    async def _analyze_tokenomics(self, candidate, metrics: GemMetrics):
        """Analyze tokenomics health for long-term holding."""
        mc = candidate.market_cap_usd
        fdv = candidate.fdv or mc * 1.5 if mc else None
        circ = candidate.circulating_supply
        total = candidate.total_supply
        
        # FDV / Market Cap ratio
        if fdv and mc and mc > 0:
            metrics.fdv_mc_ratio = fdv / mc
        else:
            metrics.fdv_mc_ratio = 2.0  # assume high if unknown
        
        # Circulating supply percentage
        if circ and total and total > 0:
            metrics.circulating_supply_pct = (circ / total) * 100
        else:
            metrics.circulating_supply_pct = 50.0  # neutral guess
        
        # Unlock risk (proxy: if FDV >> MC, high unlock risk)
        if metrics.fdv_mc_ratio:
            if metrics.fdv_mc_ratio > 10:
                metrics.unlock_risk = "critical"
            elif metrics.fdv_mc_ratio > 5:
                metrics.unlock_risk = "high"
            elif metrics.fdv_mc_ratio > 2:
                metrics.unlock_risk = "medium"
            else:
                metrics.unlock_risk = "low"
        
        # Inflation proxy (high FDV/MC with low circulation = high inflation)
        if metrics.circulating_supply_pct and metrics.circulating_supply_pct < 20:
            metrics.inflation_rate_annual = 50.0  # very high
        elif metrics.circulating_supply_pct and metrics.circulating_supply_pct < 50:
            metrics.inflation_rate_annual = 25.0
        else:
            metrics.inflation_rate_annual = 10.0
        
        # Supply concentration from top_holder_concentration
        top_conc = getattr(candidate, 'top_holder_concentration', 0.0)
        if top_conc > 50:
            metrics.supply_concentration_risk = "critical"
        elif top_conc > 30:
            metrics.supply_concentration_risk = "high"
        elif top_conc > 15:
            metrics.supply_concentration_risk = "medium"
        else:
            metrics.supply_concentration_risk = "low"

    # ------------------------------------------------------------------
    #  4. SOCIAL SENTIMENT
    # ------------------------------------------------------------------
    async def _analyze_social_sentiment(self, symbol: str, token_address: str, chain: str, metrics: GemMetrics):
        """Fetch real social sentiment when API keys are available, else use proxy."""
        
        # Try LunarCrush first
        if self.lunarcrush_api_key:
            try:
                url = f"https://api.lunarcrush.com/v3/coins/{symbol}/time-series?interval=1w&key={self.lunarcrush_api_key}"
                async with self.session.get(url, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ts = data.get("data", {}).get("timeSeries", [])
                        if ts:
                            latest = ts[-1]
                            metrics.social_volume_score = min(100, float(latest.get("social_volume", 0)) / 100)
                            metrics.bullish_sentiment_pct = float(latest.get("sentiment", 0.5)) * 100
                            metrics.unique_contributors_24h = int(latest.get("unique_social_contributors", 0))
                            if len(ts) > 1:
                                prev_vol = float(ts[-2].get("social_volume", 1))
                                curr_vol = float(latest.get("social_volume", 1))
                                metrics.social_growth_rate = ((curr_vol - prev_vol) / prev_vol) * 100 if prev_vol > 0 else 0
                        return
            except Exception as e:
                logger.debug(f"LunarCrush failed for {symbol}: {e}")
        
        # Try Kaito for mindshare/narrative strength
        if self.kaito_api_key and token_address:
            try:
                url = f"https://api.kaito.ai/api/v1/yaps?token={token_address}"
                headers = {"Authorization": f"Bearer {self.kaito_api_key}"}
                async with self.session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        mindshare = float(data.get("mindshare", 0))
                        metrics.social_volume_score = min(100, mindshare * 100)
                        metrics.bullish_sentiment_pct = float(data.get("sentiment", 0.5)) * 100
                        return
            except Exception as e:
                logger.debug(f"Kaito failed for {symbol}: {e}")
        
        # Proxy fallback: use price changes as social hype indicator (existing logic enhanced)
        # This is NOT ideal but provides a baseline when no APIs are configured
        metrics.social_volume_score = 30.0  # conservative baseline
        metrics.bullish_sentiment_pct = 50.0
        metrics.social_growth_rate = None
        metrics.unique_contributors_24h = 0

    # ------------------------------------------------------------------
    #  5. SMART MONEY / ON-CHAIN
    # ------------------------------------------------------------------
    async def _analyze_smart_money(self, token_address: str, chain: str, metrics: GemMetrics):
        """Track whale movements and smart money flows."""
        if chain != "sol" or not token_address:
            return
        
        # Try Helius for enriched holder data
        if self.helius_api_key:
            try:
                url = "https://mainnet.helius-rpc.com/?api-key=" + self.helius_api_key
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenLargestAccounts",
                    "params": [token_address]
                }
                async with self.session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        accounts = data.get("result", {}).get("value", [])
                        # Analyze top 20 holders
                        if accounts:
                            total_supply = sum(float(a.get("amount", 0)) for a in accounts)
                            whale_pct = (float(accounts[0].get("amount", 0)) / total_supply) * 100 if total_supply > 0 else 0
                            if whale_pct > 30:
                                metrics.supply_concentration_risk = "critical"
                            elif whale_pct > 15:
                                metrics.supply_concentration_risk = "high"
            except Exception as e:
                logger.debug(f"Helius analysis failed for {token_address[:8]}: {e}")
        
        # Try Solscan for holder retention and new wallets
        if self.solscan_api_key:
            try:
                url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=20"
                headers = {"Accept": "application/json"}
                async with self.session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        holders = data.get("data", []) if isinstance(data, dict) else []
                        metrics.new_wallets_7d = len([h for h in holders if h.get("time", 0) > 7 * 86400])
            except Exception as e:
                logger.debug(f"Solscan holder analysis failed: {e}")

    # ------------------------------------------------------------------
    #  6. ECOSYSTEM VERIFICATION
    # ------------------------------------------------------------------
    async def _analyze_ecosystem(self, symbol: str, token_address: str, chain: str, metrics: GemMetrics):
        """Check ecosystem grants, partnerships, and development activity."""
        combined_text = f"{symbol} {token_address}".lower()
        
        # Known ecosystem grant markers (proxy via symbol/name matching)
        grant_keywords = {
            "solana": ["solana", "sol"],
            "base": ["base", "coinbase"],
            "ethereum": ["ethereum", "eth"],
            "arbitrum": ["arbitrum", "arb"],
            "optimism": ["optimism", "op"],
        }
        
        for ecosystem, keywords in grant_keywords.items():
            if any(kw in combined_text for kw in keywords):
                metrics.ecosystem_grants.append(ecosystem)
        
        # GitHub proxy: check if name suggests open-source/utility
        dev_keywords = ["protocol", "dao", "labs", "network", "chain", "infra", "sdk", "api", "oracle"]
        metrics.github_activity_score = sum(10 for kw in dev_keywords if kw in combined_text)
        metrics.github_activity_score = min(100, metrics.github_activity_score)

    # ------------------------------------------------------------------
    #  7. BEAR MARKET ACCUMULATION PROFILE
    # ------------------------------------------------------------------
    async def _analyze_accumulation_profile(self, candidate, metrics: GemMetrics):
        """Detect stealth accumulation vs pump-and-dump patterns."""
        vol = candidate.volume_24h
        liq = candidate.liquidity_usd
        mc = candidate.market_cap_usd
        change_1h = candidate.price_change_1h
        change_24h = candidate.price_change_24h
        txns = candidate.transactions_24h
        
        # Stealth accumulation signals:
        # - Low volatility after a period of high volatility
        # - Consistent volume without explosive spikes
        # - Positive price change but not parabolic
        # - Higher buy ratio
        
        score = 0.0
        
        # 1. Not parabolic (avoids P&D)
        if abs(change_24h) < 50 and abs(change_1h) < 20:
            score += 25
        elif abs(change_24h) < 100 and abs(change_1h) < 30:
            score += 10
        
        # 2. Reasonable volume-to-liquidity ratio (not fake volume)
        if liq > 0 and vol / liq < 5:
            score += 20  # Healthy turnover
        elif liq > 0 and vol / liq < 10:
            score += 10
        
        # 3. Sustained transaction count (not just a few whale txs)
        if txns > 500:
            score += 15
        elif txns > 100:
            score += 10
        
        # 4. Market cap sweet spot for gems ($1M - $50M)
        if 1_000_000 < mc < 50_000_000:
            score += 20
        elif 500_000 < mc < 100_000_000:
            score += 10
        
        # 5. Good buy/sell ratio
        bsr = getattr(candidate, 'buy_sell_ratio', 1.0)
        if bsr > 1.5:
            score += 20
        elif bsr > 1.0:
            score += 10
        
        metrics.accumulation_score = min(100, score)
        
        # Volatility compression proxy
        if abs(change_24h) < 15 and abs(change_1h) < 5:
            metrics.volatility_compression = True
        
        # Volume trend (proxy using 1h vs 24h ratio)
        if change_1h > 0 and txns > 200:
            metrics.volume_trend_30d = "rising"
        elif change_1h < -5:
            metrics.volume_trend_30d = "falling"

    # ------------------------------------------------------------------
    #  8. GEM SCORE CALCULATION
    # ------------------------------------------------------------------
    def _calculate_gem_score(self, metrics: GemMetrics, candidate) -> float:
        """Compute composite Gem Score (0-100).
        
        Weights optimized for long-term holds:
        - Contract safety: 20%
        - Narrative alignment: 20%
        - Tokenomics health: 20%
        - Social/community health: 15%
        - Smart money/accumulation: 15%
        - Ecosystem legitimacy: 10%
        """
        
        # Safety score (0-100)
        if metrics.rugcheck_score is not None:
            safety = metrics.rugcheck_score
        else:
            safety = 50.0
        
        # Reduce safety for critical risks
        if metrics.is_honeypot:
            safety = 0
        if metrics.top_holders_risk == "critical":
            safety *= 0.5
        elif metrics.top_holders_risk == "high":
            safety *= 0.75
        if not metrics.mint_authority_disabled:
            safety *= 0.7
        if not metrics.freeze_authority_disabled:
            safety *= 0.9
        
        # Narrative (already 0-100)
        narrative = metrics.narrative_score
        
        # Tokenomics health (0-100, lower FDV/MC = higher score)
        tokenomics = 50.0
        if metrics.fdv_mc_ratio:
            if metrics.fdv_mc_ratio <= 1.2:
                tokenomics = 95
            elif metrics.fdv_mc_ratio <= 2:
                tokenomics = 80
            elif metrics.fdv_mc_ratio <= 5:
                tokenomics = 60
            else:
                tokenomics = 30
        if metrics.circulating_supply_pct and metrics.circulating_supply_pct < 10:
            tokenomics *= 0.5
        if metrics.unlock_risk == "critical":
            tokenomics *= 0.3
        elif metrics.unlock_risk == "high":
            tokenomics *= 0.6
        
        # Social (0-100)
        social = metrics.social_volume_score * 0.7
        if metrics.bullish_sentiment_pct:
            social += metrics.bullish_sentiment_pct * 0.3
        else:
            social += 15
        social = min(100, social)
        
        # Smart money / accumulation (0-100)
        smart = metrics.accumulation_score * 0.6
        if metrics.smart_money_netflow_7d and metrics.smart_money_netflow_7d > 0:
            smart += min(40, metrics.smart_money_netflow_7d)
        if metrics.whale_holdings_change_7d and metrics.whale_holdings_change_7d > 0:
            smart += min(20, metrics.whale_holdings_change_7d)
        smart = min(100, smart)
        
        # Ecosystem (0-100)
        ecosystem = min(100, len(metrics.ecosystem_grants) * 25 + metrics.github_activity_score)
        
        # Composite
        gem_score = (
            safety * 0.20 +
            narrative * 0.20 +
            tokenomics * 0.20 +
            social * 0.15 +
            smart * 0.15 +
            ecosystem * 0.10
        )
        
        return round(max(0, min(100, gem_score)), 1)

    def _tier_from_score(self, score: float, metrics: GemMetrics) -> str:
        """Map gem score to investment tier, with veto conditions."""
        # Automatic vetos
        if metrics.is_honeypot:
            return "avoid"
        if metrics.rugcheck_score is not None and metrics.rugcheck_score < 20:
            return "avoid"
        if metrics.top_holders_risk == "critical":
            return "avoid"
        if metrics.fdv_mc_ratio and metrics.fdv_mc_ratio > 20:
            return "avoid"
        
        if score >= 80:
            return "s_tier"
        elif score >= 65:
            return "a_tier"
        elif score >= 50:
            return "b_tier"
        elif score >= 35:
            return "c_tier"
        else:
            return "avoid"

    def _generate_gem_report(self, metrics: GemMetrics, candidate) -> str:
        """Generate a concise gem report for dashboard display."""
        lines = [
            f"🎯 Gem Score: {metrics.gem_score}/100 ({metrics.gem_tier.upper()})",
            f"📊 Narrative: {metrics.primary_narrative or 'none'} ({metrics.narrative_score:.0f}/100)",
            f"🛡️ Safety: {metrics.rugcheck_score:.0f}/100 | Top Holders: {metrics.top_holders_risk}",
        ]
        if metrics.fdv_mc_ratio:
            lines.append(f"📈 FDV/MC: {metrics.fdv_mc_ratio:.1f}x | Circulating: {metrics.circulating_supply_pct:.1f}%")
        lines.append(f"💎 Accumulation: {metrics.accumulation_score:.0f}/100 | Vol Compression: {metrics.volatility_compression}")
        if metrics.rugcheck_risks:
            lines.append(f"⚠️ Risks: {', '.join(metrics.rugcheck_risks[:3])}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  HELPER: Apply gem metrics back to AlphaPlayCandidate
    # ------------------------------------------------------------------
    def enrich_candidate(self, candidate, metrics: GemMetrics):
        """Attach GemMetrics fields to an AlphaPlayCandidate for downstream use."""
        candidate.gem_score = metrics.gem_score
        candidate.gem_tier = metrics.gem_tier
        candidate.gem_report = metrics.gem_report
        candidate.narrative_score = metrics.narrative_score
        candidate.primary_narrative = metrics.primary_narrative
        candidate.contract_safety_score = metrics.rugcheck_score or 0.0
        candidate.fdv_mc_ratio = metrics.fdv_mc_ratio
        candidate.is_honeypot = metrics.is_honeypot
        candidate.top_holders_risk = metrics.top_holders_risk
        candidate.accumulation_score = metrics.accumulation_score
        
        # Override trade_type for true gems
        if metrics.gem_tier in ("s_tier", "a_tier") and metrics.gem_score >= 70:
            if candidate.trade_type != "portfolio":
                candidate.trade_type = "fundamental"
                candidate.time_frame = "1-3d"
                if not candidate.fundamental_report:
                    candidate.fundamental_report = metrics.gem_report

    def should_flag_as_gem(self, candidate) -> bool:
        """Quick check if a candidate meets minimum gem criteria."""
        gem_score = getattr(candidate, 'gem_score', 0)
        gem_tier = getattr(candidate, 'gem_tier', 'unrated')
        is_honeypot = getattr(candidate, 'is_honeypot', False)
        return gem_score >= 60 and gem_tier in ('s_tier', 'a_tier') and not is_honeypot
