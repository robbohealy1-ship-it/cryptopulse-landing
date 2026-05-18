import pytest
import asyncio
from datetime import datetime
from src.engine.signal_engine import SignalEngine
from src.models.signal import SignalDirection, SetupType


@pytest.mark.asyncio
async def test_signal_engine_initialization():
    engine = SignalEngine()
    await engine.initialize()
    
    assert engine.scanner is not None
    assert engine.technical_analyzer is not None
    assert engine.context_engine is not None


@pytest.mark.asyncio
async def test_daily_counter_reset():
    engine = SignalEngine()
    
    engine.signals_today = [1, 2, 3]
    engine.reset_daily_counter()
    
    assert len(engine.signals_today) == 0


def test_can_generate_signal():
    engine = SignalEngine()
    
    assert engine.can_generate_signal() == True
    
    from src.models.signal import TradingSignal, TechnicalScore, ContextScore, SignalStatus
    
    for i in range(3):
        signal = TradingSignal(
            symbol="BTC/USDT",
            direction=SignalDirection.LONG,
            setup_type=SetupType.LIQUIDITY_SWEEP,
            timeframe="15m",
            entry_price=50000,
            stop_loss=49000,
            take_profit_1=52000,
            technical_score=TechnicalScore(
                trend_score=90,
                volume_score=85,
                momentum_score=88,
                structure_score=92,
                total_score=89
            ),
            context_score=ContextScore(
                macro_score=80,
                news_score=85,
                sentiment_score=82,
                total_score=82
            ),
            confidence=90,
            reasoning="Test signal",
            risk_reward=2.0,
            atr=100,
            volume_24h=1000000000,
            status=SignalStatus.APPROVED
        )
        engine.signals_today.append(signal)
    
    assert engine.can_generate_signal() == False


@pytest.mark.asyncio
async def test_close():
    engine = SignalEngine()
    await engine.initialize()
    await engine.close()
