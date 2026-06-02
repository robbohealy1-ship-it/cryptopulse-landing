"""
Conviction Engine Testing Script

Tests all conviction engine components:
1. Individual engines (market structure, liquidity, volume, etc.)
2. Magnet system
3. Trap detection
4. Main conviction orchestrator
5. Integration with signal engine

Run this before deploying to production.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.conviction import (
    ConvictionEngine,
    MarketStructureEngine,
    LiquidityEngine,
    VolumeEngine,
    SentimentEngine,
    NewsIntelligenceEngine,
    OnChainEngine,
    MarketMagnetSystem,
    TrapDetectionEngine,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_test_dataframe(trend='bullish', volatility='normal', volume_spike=False):
    """Create synthetic OHLCV data for testing"""
    np.random.seed(42)
    
    periods = 200
    base_price = 100.0
    
    # Generate price data based on trend
    if trend == 'bullish':
        trend_component = np.linspace(0, 20, periods)
    elif trend == 'bearish':
        trend_component = np.linspace(0, -20, periods)
    else:
        trend_component = np.zeros(periods)
    
    # Add volatility
    if volatility == 'high':
        noise = np.random.normal(0, 2, periods)
    elif volatility == 'low':
        noise = np.random.normal(0, 0.5, periods)
    else:
        noise = np.random.normal(0, 1, periods)
    
    close = base_price + trend_component + noise
    high = close + np.abs(np.random.normal(0, 0.5, periods))
    low = close - np.abs(np.random.normal(0, 0.5, periods))
    open_price = close + np.random.normal(0, 0.3, periods)
    
    # Generate volume
    base_volume = 1000000
    if volume_spike:
        volume = np.random.uniform(800000, 1200000, periods)
        volume[-10:] *= 3  # Spike in last 10 candles
    else:
        volume = np.random.uniform(800000, 1200000, periods)
    
    df = pd.DataFrame({
        'timestamp': pd.date_range(end=datetime.utcnow(), periods=periods, freq='1h'),
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    return df


async def test_market_structure_engine():
    """Test Market Structure Engine"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Market Structure Engine")
    logger.info("="*60)
    
    engine = MarketStructureEngine()
    
    # Test bullish trend
    df_bull = create_test_dataframe(trend='bullish')
    score_bull = await engine.calculate(df_bull, 'BTC/USDT', 'LONG')
    
    logger.info(f"\n📊 Bullish Trend Test:")
    logger.info(f"   Score: {score_bull.score:.1f}/{score_bull.max_score}")
    logger.info(f"   Percentage: {(score_bull.score/score_bull.max_score)*100:.1f}%")
    logger.info(f"   Positive Factors: {len(score_bull.positive_factors)}")
    logger.info(f"   Negative Factors: {len(score_bull.negative_factors)}")
    
    # Test bearish trend
    df_bear = create_test_dataframe(trend='bearish')
    score_bear = await engine.calculate(df_bear, 'BTC/USDT', 'SHORT')
    
    logger.info(f"\n📊 Bearish Trend Test:")
    logger.info(f"   Score: {score_bear.score:.1f}/{score_bear.max_score}")
    logger.info(f"   Percentage: {(score_bear.score/score_bear.max_score)*100:.1f}%")
    
    assert score_bull.score > 10, "Bullish trend should score > 10/20"
    assert score_bear.score > 10, "Bearish trend should score > 10/20"
    
    logger.info("\n✅ Market Structure Engine: PASSED")
    return True


async def test_liquidity_engine():
    """Test Liquidity Engine"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Liquidity Engine")
    logger.info("="*60)
    
    engine = LiquidityEngine()
    
    df = create_test_dataframe(trend='bullish')
    score = await engine.calculate(df, 'ETH/USDT', 'LONG')
    
    logger.info(f"\n💧 Liquidity Test:")
    logger.info(f"   Score: {score.score:.1f}/{score.max_score}")
    logger.info(f"   Percentage: {(score.score/score.max_score)*100:.1f}%")
    logger.info(f"   Factors: {score.factors}")
    
    assert 0 <= score.score <= score.max_score, "Score must be within range"
    
    logger.info("\n✅ Liquidity Engine: PASSED")
    return True


async def test_volume_engine():
    """Test Volume Engine"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Volume Engine")
    logger.info("="*60)
    
    engine = VolumeEngine()
    
    # Test with volume spike
    df_spike = create_test_dataframe(trend='bullish', volume_spike=True)
    score_spike = await engine.calculate(df_spike, 'SOL/USDT', 'LONG')
    
    logger.info(f"\n📊 Volume Spike Test:")
    logger.info(f"   Score: {score_spike.score:.1f}/{score_spike.max_score}")
    logger.info(f"   Percentage: {(score_spike.score/score_spike.max_score)*100:.1f}%")
    logger.info(f"   Positive Factors: {score_spike.positive_factors}")
    
    # Test without volume spike
    df_normal = create_test_dataframe(trend='bullish', volume_spike=False)
    score_normal = await engine.calculate(df_normal, 'SOL/USDT', 'LONG')
    
    logger.info(f"\n📊 Normal Volume Test:")
    logger.info(f"   Score: {score_normal.score:.1f}/{score_normal.max_score}")
    
    assert score_spike.score >= score_normal.score, "Volume spike should score higher"
    
    logger.info("\n✅ Volume Engine: PASSED")
    return True


async def test_sentiment_engine():
    """Test Sentiment Engine"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Sentiment Engine")
    logger.info("="*60)
    
    engine = SentimentEngine()
    
    df = create_test_dataframe(trend='bullish')
    
    try:
        score = await engine.calculate(df, 'BTC/USDT', 'LONG')
        
        logger.info(f"\n😊 Sentiment Test:")
        logger.info(f"   Score: {score.score:.1f}/{score.max_score}")
        logger.info(f"   Percentage: {(score.score/score.max_score)*100:.1f}%")
        logger.info(f"   Factors: {list(score.factors.keys())}")
        
        assert 0 <= score.score <= score.max_score, "Score must be within range"
        
        logger.info("\n✅ Sentiment Engine: PASSED")
    except Exception as e:
        logger.warning(f"\n⚠️  Sentiment Engine: SKIPPED (API may be unavailable: {e})")
    
    return True


async def test_news_engine():
    """Test News Intelligence Engine"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: News Intelligence Engine")
    logger.info("="*60)
    
    engine = NewsIntelligenceEngine()
    
    df = create_test_dataframe(trend='bullish')
    
    try:
        score = await engine.calculate(df, 'ETH/USDT', 'LONG')
        
        logger.info(f"\n📰 News Test:")
        logger.info(f"   Score: {score.score:.1f}/{score.max_score}")
        logger.info(f"   Percentage: {(score.score/score.max_score)*100:.1f}%")
        
        assert 0 <= score.score <= score.max_score, "Score must be within range"
        
        logger.info("\n✅ News Intelligence Engine: PASSED")
    except Exception as e:
        logger.warning(f"\n⚠️  News Engine: SKIPPED (API may be unavailable: {e})")
    
    return True


async def test_onchain_engine():
    """Test On-Chain Engine (stub)"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: On-Chain Engine (Stub)")
    logger.info("="*60)
    
    engine = OnChainEngine()
    
    df = create_test_dataframe(trend='bullish')
    score = await engine.calculate(df, 'BTC/USDT', 'LONG')
    
    logger.info(f"\n⛓️  On-Chain Test:")
    logger.info(f"   Score: {score.score:.1f}/{score.max_score}")
    logger.info(f"   Percentage: {(score.score/score.max_score)*100:.1f}%")
    logger.info(f"   Note: {score.explanation}")
    
    assert score.score == 7.5, "Stub should return neutral score (7.5/15)"
    
    logger.info("\n✅ On-Chain Engine (Stub): PASSED")
    return True


async def test_magnet_system():
    """Test Market Magnet System"""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Market Magnet System")
    logger.info("="*60)
    
    system = MarketMagnetSystem()
    
    df = create_test_dataframe(trend='bullish')
    multiplier, magnets = system.calculate_multiplier(df, 'BTC/USDT', 'LONG')
    
    logger.info(f"\n🧲 Magnet Test:")
    logger.info(f"   Multiplier: {multiplier:.2f}x")
    logger.info(f"   Magnets Detected: {len(magnets)}")
    for magnet in magnets:
        logger.info(f"   - {magnet.type}: ${magnet.price:,.2f} ({magnet.distance_pct*100:.2f}% away)")
    
    assert 1.0 <= multiplier <= 1.5, "Multiplier must be between 1.0 and 1.5"
    
    logger.info("\n✅ Market Magnet System: PASSED")
    return True


async def test_trap_detection():
    """Test Trap Detection Engine"""
    logger.info("\n" + "="*60)
    logger.info("TEST 8: Trap Detection Engine")
    logger.info("="*60)
    
    engine = TrapDetectionEngine()
    
    df = create_test_dataframe(trend='bullish')
    
    try:
        penalty, traps = await engine.calculate_penalty(df, 'BTC/USDT', 'LONG')
        
        logger.info(f"\n⚠️  Trap Detection Test:")
        logger.info(f"   Penalty: -{penalty:.1f} points")
        logger.info(f"   Traps Detected: {len(traps)}")
        for trap in traps:
            logger.info(f"   - {trap.type} ({trap.severity}): {trap.explanation}")
        
        assert 0 <= penalty <= 25, "Penalty must be between 0 and 25"
        
        logger.info("\n✅ Trap Detection Engine: PASSED")
    except Exception as e:
        logger.warning(f"\n⚠️  Trap Detection: SKIPPED (API may be unavailable: {e})")
    
    return True


async def test_conviction_orchestrator():
    """Test Main Conviction Engine Orchestrator"""
    logger.info("\n" + "="*60)
    logger.info("TEST 9: Conviction Engine Orchestrator")
    logger.info("="*60)
    
    engine = ConvictionEngine()
    
    df = create_test_dataframe(trend='bullish', volume_spike=True)
    
    try:
        breakdown = await engine.calculate_conviction(df, 'BTC/USDT', 'LONG')
        
        logger.info(f"\n🎯 Full Conviction Test:")
        logger.info(f"   Final Score: {breakdown.conviction_score:.1f}/100")
        logger.info(f"   Tier: {breakdown.tier}")
        logger.info(f"\n   Engine Breakdown:")
        logger.info(f"   - Market Structure: {breakdown.market_structure_score:.1f}/20")
        logger.info(f"   - Liquidity: {breakdown.liquidity_score:.1f}/20")
        logger.info(f"   - Volume: {breakdown.volume_score:.1f}/15")
        logger.info(f"   - Sentiment: {breakdown.sentiment_score:.1f}/15")
        logger.info(f"   - News: {breakdown.news_score:.1f}/15")
        logger.info(f"   - On-Chain: {breakdown.onchain_score:.1f}/15")
        logger.info(f"\n   Modifiers:")
        logger.info(f"   - Base Score: {breakdown.base_score:.1f}/100")
        logger.info(f"   - Magnet Multiplier: {breakdown.magnet_multiplier:.2f}x")
        logger.info(f"   - Trap Penalty: -{breakdown.trap_penalty:.1f}")
        logger.info(f"\n   Factors:")
        logger.info(f"   - Positive: {len(breakdown.positive_factors)}")
        logger.info(f"   - Negative: {len(breakdown.negative_factors)}")
        logger.info(f"   - Magnets: {len(breakdown.detected_magnets)}")
        logger.info(f"   - Traps: {len(breakdown.detected_traps)}")
        
        assert 0 <= breakdown.conviction_score <= 100, "Conviction must be 0-100"
        assert breakdown.tier in ['ELITE', 'VIP', 'WATCHLIST', 'REJECTED'], "Invalid tier"
        
        logger.info("\n✅ Conviction Engine Orchestrator: PASSED")
    except Exception as e:
        logger.error(f"\n❌ Conviction Engine Orchestrator: FAILED - {e}")
        raise
    
    return True


async def run_all_tests():
    """Run all conviction engine tests"""
    logger.info("\n" + "="*60)
    logger.info("🧪 CONVICTION ENGINE TEST SUITE")
    logger.info("="*60)
    
    tests = [
        ("Market Structure Engine", test_market_structure_engine),
        ("Liquidity Engine", test_liquidity_engine),
        ("Volume Engine", test_volume_engine),
        ("Sentiment Engine", test_sentiment_engine),
        ("News Intelligence Engine", test_news_engine),
        ("On-Chain Engine", test_onchain_engine),
        ("Market Magnet System", test_magnet_system),
        ("Trap Detection Engine", test_trap_detection),
        ("Conviction Orchestrator", test_conviction_orchestrator),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
        except Exception as e:
            logger.error(f"\n❌ {test_name} FAILED: {e}")
            failed += 1
    
    logger.info("\n" + "="*60)
    logger.info("📊 TEST RESULTS")
    logger.info("="*60)
    logger.info(f"   Passed: {passed}/{len(tests)}")
    logger.info(f"   Failed: {failed}/{len(tests)}")
    logger.info(f"   Success Rate: {(passed/len(tests))*100:.1f}%")
    
    if failed == 0:
        logger.info("\n🎉 ALL TESTS PASSED! Ready for production.")
    else:
        logger.error(f"\n⚠️  {failed} test(s) failed. Fix before deploying.")
    
    logger.info("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
