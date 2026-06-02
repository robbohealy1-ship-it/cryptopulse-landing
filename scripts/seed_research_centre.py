"""
Seed Research Centre with Initial Projects

This script creates 5-10 high-quality research projects based on:
1. Historical alpha plays that showed strong fundamentals
2. Current trending tokens with real utility
3. Established projects with growth potential

Run this once to populate the research centre.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from src.database.supabase_client import SupabaseClient
from src.research import ResearchProject
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Curated list of research-worthy projects
SEED_PROJECTS = [
    {
        "symbol": "RENDER",
        "name": "Render Network",
        "chain": "sol",
        "token_address": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
        "market_cap_usd": 2500000000,  # $2.5B
        "price_usd": 7.15,
        "liquidity_usd": 45000000,
        "volume_24h": 125000000,
        "holders": 125000,
        "narrative": "AI + Blockchain GPU Rendering",
        "why_trending": "Apple Vision Pro integration, AI boom driving GPU demand",
        "conviction_initial": 88,
        "risk_level": "low",
        "accumulation_zone_low": 6.50,
        "accumulation_zone_high": 7.50,
        "breakout_target": 13.00,
        "long_term_target": 30.00,
        "timeframe": "3-6 months",
    },
    {
        "symbol": "JUP",
        "name": "Jupiter",
        "chain": "sol",
        "token_address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "market_cap_usd": 1200000000,  # $1.2B
        "price_usd": 0.92,
        "liquidity_usd": 35000000,
        "volume_24h": 450000000,
        "holders": 450000,
        "narrative": "Solana DEX Aggregator + Perpetuals",
        "why_trending": "Highest volume DEX on Solana, launching perpetuals platform",
        "conviction_initial": 85,
        "risk_level": "low",
        "accumulation_zone_low": 0.85,
        "accumulation_zone_high": 1.00,
        "breakout_target": 1.50,
        "long_term_target": 3.00,
        "timeframe": "2-4 months",
    },
    {
        "symbol": "PYTH",
        "name": "Pyth Network",
        "chain": "sol",
        "token_address": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
        "market_cap_usd": 800000000,  # $800M
        "price_usd": 0.38,
        "liquidity_usd": 25000000,
        "volume_24h": 85000000,
        "holders": 180000,
        "narrative": "Oracle Network for DeFi",
        "why_trending": "Real-time price feeds, institutional partnerships, cross-chain expansion",
        "conviction_initial": 82,
        "risk_level": "medium",
        "accumulation_zone_low": 0.35,
        "accumulation_zone_high": 0.42,
        "breakout_target": 0.65,
        "long_term_target": 1.20,
        "timeframe": "4-8 months",
    },
    {
        "symbol": "WIF",
        "name": "dogwifhat",
        "chain": "sol",
        "token_address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "market_cap_usd": 2800000000,  # $2.8B
        "price_usd": 2.85,
        "liquidity_usd": 55000000,
        "volume_24h": 320000000,
        "holders": 220000,
        "narrative": "Solana Meme Coin Leader",
        "why_trending": "Strongest community on Solana, CEX listings, brand recognition",
        "conviction_initial": 75,
        "risk_level": "high",
        "accumulation_zone_low": 2.50,
        "accumulation_zone_high": 3.20,
        "breakout_target": 5.00,
        "long_term_target": 10.00,
        "timeframe": "1-3 months",
    },
    {
        "symbol": "ONDO",
        "name": "Ondo Finance",
        "chain": "eth",
        "token_address": "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3",
        "market_cap_usd": 1500000000,  # $1.5B
        "price_usd": 1.05,
        "liquidity_usd": 40000000,
        "volume_24h": 95000000,
        "holders": 85000,
        "narrative": "Real World Assets (RWA) Tokenization",
        "why_trending": "Institutional adoption, BlackRock partnership rumors, RWA narrative",
        "conviction_initial": 90,
        "risk_level": "low",
        "accumulation_zone_low": 0.95,
        "accumulation_zone_high": 1.15,
        "breakout_target": 2.00,
        "long_term_target": 5.00,
        "timeframe": "6-12 months",
    },
    {
        "symbol": "PENDLE",
        "name": "Pendle Finance",
        "chain": "eth",
        "token_address": "0x808507121B80c02388fAd14726482e061B8da827",
        "market_cap_usd": 650000000,  # $650M
        "price_usd": 4.25,
        "liquidity_usd": 28000000,
        "volume_24h": 65000000,
        "holders": 42000,
        "narrative": "Yield Trading Protocol",
        "why_trending": "Innovative yield tokenization, growing TVL, DeFi 2.0",
        "conviction_initial": 83,
        "risk_level": "medium",
        "accumulation_zone_low": 3.80,
        "accumulation_zone_high": 4.60,
        "breakout_target": 7.50,
        "long_term_target": 15.00,
        "timeframe": "4-8 months",
    },
    {
        "symbol": "ARB",
        "name": "Arbitrum",
        "chain": "arb",
        "token_address": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "market_cap_usd": 8500000000,  # $8.5B
        "price_usd": 0.72,
        "liquidity_usd": 120000000,
        "volume_24h": 285000000,
        "holders": 650000,
        "narrative": "Ethereum Layer 2 Leader",
        "why_trending": "Highest TVL L2, gaming ecosystem, institutional adoption",
        "conviction_initial": 87,
        "risk_level": "low",
        "accumulation_zone_low": 0.65,
        "accumulation_zone_high": 0.80,
        "breakout_target": 1.50,
        "long_term_target": 3.50,
        "timeframe": "6-12 months",
    },
    {
        "symbol": "INJ",
        "name": "Injective",
        "chain": "inj",
        "token_address": "inj",
        "market_cap_usd": 2200000000,  # $2.2B
        "price_usd": 24.50,
        "liquidity_usd": 65000000,
        "volume_24h": 145000000,
        "holders": 95000,
        "narrative": "Cosmos DeFi Hub",
        "why_trending": "Cross-chain DEX, institutional partnerships, burn mechanism",
        "conviction_initial": 84,
        "risk_level": "medium",
        "accumulation_zone_low": 22.00,
        "accumulation_zone_high": 27.00,
        "breakout_target": 40.00,
        "long_term_target": 80.00,
        "timeframe": "4-8 months",
    },
]


async def seed_research_centre():
    """Seed research centre with initial projects"""
    logger.info("🌱 Starting Research Centre seeding...")
    
    db = SupabaseClient()
    
    created_count = 0
    skipped_count = 0
    
    for project_data in SEED_PROJECTS:
        try:
            symbol = project_data["symbol"]
            chain = project_data["chain"]
            
            # Check if project already exists
            existing = await db.get_all_research_projects()
            exists = any(
                p.get("symbol") == symbol and p.get("chain") == chain
                for p in existing
            )
            
            if exists:
                logger.info(f"⏭️  Skipping {symbol} - already exists")
                skipped_count += 1
                continue
            
            # Create research project
            project = ResearchProject(
                id=f"research_{symbol.lower()}_{chain}_{int(datetime.utcnow().timestamp())}",
                symbol=symbol,
                name=project_data["name"],
                chain=chain,
                token_address=project_data["token_address"],
                market_cap_usd=project_data["market_cap_usd"],
                price_usd=project_data["price_usd"],
                liquidity_usd=project_data["liquidity_usd"],
                volume_24h=project_data["volume_24h"],
                holders=project_data["holders"],
                status="active",
                conviction_score=project_data["conviction_initial"],
                last_updated=datetime.utcnow(),
                created_at=datetime.utcnow(),
                narrative=project_data["narrative"],
                catalyst=project_data["why_trending"],
                risk_level=project_data["risk_level"],
                tags=[
                    project_data["narrative"].lower(),
                    chain,
                    project_data["risk_level"],
                ],
            )
            
            # Save to database
            success = await db.save_research_project(project.to_dict())
            
            if success:
                logger.info(
                    f"✅ Created research project: {symbol} ({chain.upper()}) - "
                    f"Conviction: {project_data['conviction_initial']}/100"
                )
                created_count += 1
            else:
                logger.error(f"❌ Failed to create {symbol}")
        
        except Exception as e:
            logger.error(f"Error creating project {project_data.get('symbol', 'unknown')}: {e}")
            continue
    
    logger.info(
        f"\n🎉 Research Centre seeding complete!\n"
        f"   Created: {created_count}\n"
        f"   Skipped: {skipped_count}\n"
        f"   Total: {created_count + skipped_count}"
    )
    
    return created_count


if __name__ == "__main__":
    asyncio.run(seed_research_centre())
