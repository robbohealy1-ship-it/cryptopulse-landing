from datetime import datetime
from src.models.signal import TradingSignal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SignalValidator:
    """Validates trading signals before processing"""
    
    @staticmethod
    def validate_signal(signal: TradingSignal) -> tuple[bool, str]:
        """
        Validate a trading signal
        Returns: (is_valid, error_message)
        """
        
        # Check if signal has expired
        if signal.expires_at and datetime.utcnow() > signal.expires_at:
            return False, "Signal has expired"
        
        # Validate prices are positive
        if signal.entry_price <= 0:
            return False, "Entry price must be positive"
        if signal.stop_loss <= 0:
            return False, "Stop loss must be positive"
        if signal.take_profit_1 <= 0:
            return False, "Take profit must be positive"
        
        # Validate stop loss placement
        if signal.direction.value == "LONG":
            if signal.stop_loss >= signal.entry_price:
                return False, "Stop loss must be below entry for LONG"
            if signal.take_profit_1 <= signal.entry_price:
                return False, "Take profit must be above entry for LONG"
        else:  # SHORT
            if signal.stop_loss <= signal.entry_price:
                return False, "Stop loss must be above entry for SHORT"
            if signal.take_profit_1 >= signal.entry_price:
                return False, "Take profit must be below entry for SHORT"
        
        # Validate risk/reward ratio
        if signal.risk_reward < 1.0:
            return False, f"Risk/reward ratio too low: {signal.risk_reward:.2f}"
        
        # Validate confidence score
        if signal.confidence < 0 or signal.confidence > 100:
            return False, f"Invalid confidence score: {signal.confidence}"
        
        # Validate technical scores
        if signal.technical_score.total_score < 0 or signal.technical_score.total_score > 100:
            return False, "Invalid technical score"
        
        # Validate context scores
        if signal.context_score.total_score < 0 or signal.context_score.total_score > 100:
            return False, "Invalid context score"
        
        # All validations passed
        return True, ""
    
    @staticmethod
    def check_signal_quality(signal: TradingSignal, min_confidence: float = 90) -> bool:
        """Elite quality filter with 5m-specific strictness"""
        
        symbol = signal.symbol
        timeframe = getattr(signal, 'timeframe', '15m')
        
        # Primary gate: confidence must be elite (90%+)
        if signal.confidence >= 90:
            logger.info(f"✅ Signal {symbol} ELITE quality: {signal.confidence:.1f}% confidence - PASSED")
            return True
        
        # For signals below 90% but above minimum (85-89%), check sub-scores
        if signal.confidence < min_confidence:
            logger.debug(f"Signal {symbol} below elite confidence: {signal.confidence:.1f} < {min_confidence}")
            return False
        
        # Standard checks for ALL signals
        if signal.risk_reward < 2.0:
            logger.debug(f"Signal {symbol} below minimum R:R: {signal.risk_reward:.2f}")
            return False
        
        if signal.volume_24h < 10000000:
            logger.debug(f"Signal {symbol} insufficient volume: ${signal.volume_24h:,.0f}")
            return False
        
        if signal.context_score.news_score < 30:
            logger.debug(f"Signal {symbol} has negative news context: {signal.context_score.news_score}")
            return False
        
        if signal.context_score.macro_score < 30:
            logger.debug(f"Signal {symbol} has poor macro context: {signal.context_score.macro_score}")
            return False
        
        # 🚨 ADDITIONAL 5m STRICTNESS (even for 85-89% range)
        if timeframe == '5m':
            # 5m signals need stronger context alignment
            if signal.context_score.total_score < 55:
                logger.info(f"🚫 5m {symbol}: context score {signal.context_score.total_score:.0f} < 55")
                return False
            
            if signal.context_score.news_score < 45:
                logger.info(f"🚫 5m {symbol}: news score {signal.context_score.news_score:.0f} < 45")
                return False
            
            # 5m signals MUST be limit orders (no market chase)
            if not getattr(signal, 'is_limit_order', False):
                logger.info(f"🚫 5m {symbol}: not a limit order — market entries rejected on 5m")
                return False
            
            # 5m signals need strong technicals
            if signal.technical_score.total_score < 80:
                logger.info(f"🚫 5m {symbol}: technical score {signal.technical_score.total_score:.0f} < 80")
                return False
        
        logger.info(f"✅ Signal {symbol} quality check PASSED: {signal.confidence:.1f}%")
        return True
