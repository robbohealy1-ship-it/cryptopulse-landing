import pytest
import pandas as pd
import numpy as np
from src.analysis.technical_analyzer import TechnicalAnalyzer
from src.models.signal import SignalDirection


def create_sample_data(length=200):
    dates = pd.date_range(start='2024-01-01', periods=length, freq='15min')
    
    close_prices = np.random.randn(length).cumsum() + 50000
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices + np.random.randn(length) * 10,
        'high': close_prices + np.abs(np.random.randn(length) * 20),
        'low': close_prices - np.abs(np.random.randn(length) * 20),
        'close': close_prices,
        'volume': np.random.randint(100, 1000, length)
    })
    
    df.set_index('timestamp', inplace=True)
    return df


def test_add_indicators():
    analyzer = TechnicalAnalyzer()
    df = create_sample_data()
    
    df_with_indicators = analyzer.add_indicators(df)
    
    assert 'ema_20' in df_with_indicators.columns
    assert 'ema_50' in df_with_indicators.columns
    assert 'ema_200' in df_with_indicators.columns
    assert 'rsi' in df_with_indicators.columns
    assert 'macd' in df_with_indicators.columns
    assert 'atr' in df_with_indicators.columns
    assert 'vwap' in df_with_indicators.columns


def test_detect_trend():
    analyzer = TechnicalAnalyzer()
    df = create_sample_data()
    df = analyzer.add_indicators(df)
    
    trend = analyzer.detect_trend(df)
    
    assert 'direction' in trend
    assert 'strength' in trend
    assert trend['direction'] in ['bullish', 'bearish', 'neutral']
    assert 0 <= trend['strength'] <= 100


def test_calculate_technical_score():
    analyzer = TechnicalAnalyzer()
    df = create_sample_data()
    df = analyzer.add_indicators(df)
    
    score = analyzer.calculate_technical_score(df)
    
    assert 0 <= score.trend_score <= 100
    assert 0 <= score.volume_score <= 100
    assert 0 <= score.momentum_score <= 100
    assert 0 <= score.structure_score <= 100
    assert 0 <= score.total_score <= 100


def test_calculate_stop_loss():
    analyzer = TechnicalAnalyzer()
    df = create_sample_data()
    df = analyzer.add_indicators(df)
    
    entry = 50000
    
    stop_long = analyzer.calculate_stop_loss(df, SignalDirection.LONG, entry)
    assert stop_long < entry
    
    stop_short = analyzer.calculate_stop_loss(df, SignalDirection.SHORT, entry)
    assert stop_short > entry


def test_calculate_take_profits():
    analyzer = TechnicalAnalyzer()
    
    entry = 50000
    stop_loss = 49000
    
    tp1, tp2, tp3 = analyzer.calculate_take_profits(
        entry, stop_loss, SignalDirection.LONG, min_rr=2.0
    )
    
    assert tp1 > entry
    assert tp2 > tp1
    assert tp3 > tp2
    
    risk = entry - stop_loss
    reward1 = tp1 - entry
    assert reward1 >= risk * 2
