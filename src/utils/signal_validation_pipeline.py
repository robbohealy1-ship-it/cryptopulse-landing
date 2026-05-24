"""
8-Stage Signal Validation Pipeline

Stages:
1. Structural Validation - Data integrity, price logic, SL/TP placement
2. Risk/Reward Validation - Minimum R:R by timeframe
3. Technical Validation - Indicator thresholds, confluence
4. Context Validation - Market regime, news, macro alignment
5. Liquidity Validation - Volume, spread, slippage
6. Institutional Validation - Order flow alignment (optional)
7. Historical Validation - Setup type performance
8. Final Grading - Composite score -> A+/A/B/C/Rejected
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from src.models.signal import TradingSignal, SignalGrade, SignalDirection
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


@dataclass
class StageResult:
    name: str
    passed: bool
    score: float  # 0-100
    weight: float
    details: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    passed: bool
    grade: SignalGrade
    composite_score: float
    stages: List[StageResult]
    rejection_reasons: List[str] = field(default_factory=list)


class SignalValidationPipeline:
    """
    8-stage validation pipeline for trading signals.
    Each stage contributes a weighted score to the final composite.
    """

    # Default weights (configurable)
    DEFAULT_WEIGHTS = {
        'structural': 0.10,
        'risk_reward': 0.15,
        'technical': 0.25,
        'context': 0.20,
        'liquidity': 0.15,
        'institutional': 0.05,
        'historical': 0.10,
    }

    # Grade thresholds (configurable)
    DEFAULT_THRESHOLDS = {
        'A_PLUS': 92,
        'A': 85,
        'B': 75,
        'C': 65,
    }

    # Minimum R:R by timeframe
    DEFAULT_MIN_RR = {
        '5m': 2.0,
        '15m': 1.5,
        '1h': 1.5,
        '4h': 1.0,
        '1d': 1.0,
    }

    def __init__(self, db=None):
        self.db = db
        self.weights = self._load_weights()
        self.thresholds = self._load_thresholds()
        self.min_rr = self._load_min_rr()

    def _load_weights(self) -> Dict[str, float]:
        return getattr(settings, 'VALIDATION_WEIGHTS', self.DEFAULT_WEIGHTS)

    def _load_thresholds(self) -> Dict[str, float]:
        return getattr(settings, 'GRADE_THRESHOLDS', self.DEFAULT_THRESHOLDS)

    def _load_min_rr(self) -> Dict[str, float]:
        return getattr(settings, 'MIN_RISK_REWARD_BY_TIMEFRAME', self.DEFAULT_MIN_RR)

    async def validate(self, signal: TradingSignal) -> ValidationResult:
        """Run full 8-stage validation pipeline on a signal."""
        stages = []
        rejection_reasons = []

        # Stage 1: Structural
        s1 = self._stage_structural(signal)
        stages.append(s1)
        if not s1.passed:
            rejection_reasons.extend(s1.details)

        # Stage 2: Risk/Reward
        s2 = self._stage_risk_reward(signal)
        stages.append(s2)
        if not s2.passed:
            rejection_reasons.extend(s2.details)

        # Stage 3: Technical
        s3 = self._stage_technical(signal)
        stages.append(s3)
        if not s3.passed:
            rejection_reasons.extend(s3.details)

        # Stage 4: Context
        s4 = self._stage_context(signal)
        stages.append(s4)
        if not s4.passed:
            rejection_reasons.extend(s4.details)

        # Stage 5: Liquidity
        s5 = self._stage_liquidity(signal)
        stages.append(s5)
        if not s5.passed:
            rejection_reasons.extend(s5.details)

        # Stage 6: Institutional (optional, can pass with warning)
        s6 = self._stage_institutional(signal)
        stages.append(s6)

        # Stage 7: Historical (async DB query)
        s7 = await self._stage_historical(signal)
        stages.append(s7)

        # Calculate composite score
        composite = sum(s.score * s.weight for s in stages)

        # Stage 8: Final Grading
        grade = self._calculate_grade(composite, stages, rejection_reasons)

        # Hard reject if structural or risk/reward failed
        passed = grade != SignalGrade.REJECTED

        result = ValidationResult(
            passed=passed,
            grade=grade,
            composite_score=round(composite, 2),
            stages=stages,
            rejection_reasons=rejection_reasons
        )

        # Attach to signal
        signal.grade = grade
        signal.validation_score = result.composite_score
        signal.validation_breakdown = {
            s.name: {'score': s.score, 'passed': s.passed, 'details': s.details}
            for s in stages
        }

        logger.info(
            f"Signal {signal.symbol} {signal.timeframe}: "
            f"Grade={grade.value}, Score={composite:.1f}"
        )

        return result

    def _stage_structural(self, signal: TradingSignal) -> StageResult:
        """Stage 1: Validate basic structural integrity."""
        details = []
        score = 100.0

        # Prices must be positive
        if signal.entry_price <= 0:
            details.append("Entry price must be positive")
            score = 0
        if signal.stop_loss <= 0:
            details.append("Stop loss must be positive")
            score = 0
        if signal.take_profit_1 <= 0:
            details.append("Take profit must be positive")
            score = 0

        # SL/TP placement logic
        if signal.direction == SignalDirection.LONG:
            if signal.stop_loss >= signal.entry_price:
                details.append("SL must be below entry for LONG")
                score = 0
            if signal.take_profit_1 <= signal.entry_price:
                details.append("TP1 must be above entry for LONG")
                score = 0
        else:
            if signal.stop_loss <= signal.entry_price:
                details.append("SL must be above entry for SHORT")
                score = 0
            if signal.take_profit_1 >= signal.entry_price:
                details.append("TP1 must be below entry for SHORT")
                score = 0

        # ATR must be reasonable relative to price
        if signal.atr > 0 and signal.entry_price > 0:
            atr_pct = signal.atr / signal.entry_price * 100
            if atr_pct > 5:
                details.append(f"Extreme ATR: {atr_pct:.1f}%")
                score -= 20

        passed = score >= 60 and not any(
            d.startswith("Entry") or d.startswith("Stop loss") or d.startswith("Take profit")
            for d in details
        )

        return StageResult(
            name='structural',
            passed=passed,
            score=max(0, score),
            weight=self.weights['structural'],
            details=details
        )

    def _stage_risk_reward(self, signal: TradingSignal) -> StageResult:
        """Stage 2: Validate risk/reward meets minimums by timeframe."""
        details = []
        score = 100.0

        min_rr = self.min_rr.get(signal.timeframe, 1.0)

        if signal.risk_reward < min_rr:
            details.append(f"R:R {signal.risk_reward:.2f} < minimum {min_rr}")
            score = 0
        elif signal.risk_reward < min_rr * 1.5:
            score = 60
        elif signal.risk_reward < min_rr * 2.0:
            score = 80

        # Stop loss distance check (max 2x ATR)
        if signal.atr > 0 and signal.entry_price > 0:
            sl_dist = abs(signal.stop_loss - signal.entry_price)
            if sl_dist > signal.atr * 2:
                details.append(f"SL distance {sl_dist:.4f} > 2x ATR {signal.atr * 2:.4f}")
                score -= 30

        passed = score >= 60

        return StageResult(
            name='risk_reward',
            passed=passed,
            score=max(0, score),
            weight=self.weights['risk_reward'],
            details=details
        )

    def _stage_technical(self, signal: TradingSignal) -> StageResult:
        """Stage 3: Validate technical indicators and confluence."""
        details = []
        score = signal.technical_score.total_score

        # Minimum technical score by timeframe
        min_scores = {'5m': 80, '15m': 70, '1h': 65, '4h': 60, '1d': 55}
        min_tech = min_scores.get(signal.timeframe, 60)

        if score < min_tech:
            details.append(f"Technical score {score:.0f} < {min_tech}")
            score = score * 0.5  # Penalize

        # Require at least 2 strong sub-scores (>70)
        strong = 0
        for sub in [signal.technical_score.trend_score, signal.technical_score.volume_score,
                    signal.technical_score.momentum_score, signal.technical_score.structure_score]:
            if sub >= 70:
                strong += 1
        if strong < 2:
            details.append(f"Only {strong}/4 strong technical sub-scores (need >= 2)")
            score -= 15

        # 5m requires limit orders
        if signal.timeframe == '5m' and not signal.is_limit_order:
            details.append("5m signals must be limit orders")
            score -= 30

        passed = score >= 60 and strong >= 1

        return StageResult(
            name='technical',
            passed=passed,
            score=max(0, score),
            weight=self.weights['technical'],
            details=details
        )

    def _stage_context(self, signal: TradingSignal) -> StageResult:
        """Stage 4: Validate market context alignment."""
        details = []
        score = signal.context_score.total_score

        min_ctx = {'5m': 55, '15m': 50, '1h': 45, '4h': 40, '1d': 35}
        min_score = min_ctx.get(signal.timeframe, 40)

        if score < min_score:
            details.append(f"Context score {score:.0f} < {min_score}")
            score = score * 0.5

        # News must not be strongly negative
        if signal.context_score.news_score < 30:
            details.append(f"News context negative: {signal.context_score.news_score}")
            score -= 20

        # Macro alignment
        if signal.context_score.macro_score < 30:
            details.append(f"Macro context poor: {signal.context_score.macro_score}")
            score -= 15

        passed = score >= 50

        return StageResult(
            name='context',
            passed=passed,
            score=max(0, score),
            weight=self.weights['context'],
            details=details
        )

    def _stage_liquidity(self, signal: TradingSignal) -> StageResult:
        """Stage 5: Validate liquidity and volume."""
        details = []
        score = 100.0

        min_volumes = {'5m': 20_000_000, '15m': 15_000_000, '1h': 10_000_000,
                       '4h': 5_000_000, '1d': 2_000_000}
        min_vol = min_volumes.get(signal.timeframe, 5_000_000)

        if signal.volume_24h < min_vol:
            details.append(f"Volume ${signal.volume_24h:,.0f} < ${min_vol:,.0f}")
            score = 40
        elif signal.volume_24h < min_vol * 2:
            score = 70

        passed = score >= 50

        return StageResult(
            name='liquidity',
            passed=passed,
            score=max(0, score),
            weight=self.weights['liquidity'],
            details=details
        )

    def _stage_institutional(self, signal: TradingSignal) -> StageResult:
        """Stage 6: Check institutional/order flow alignment (optional)."""
        details = []
        score = 70.0  # Neutral if no data

        # If the signal has institutional data, score it
        # For now, this is a placeholder that passes with neutral score
        # Real implementation would check order flow, funding rates, etc.

        return StageResult(
            name='institutional',
            passed=True,
            score=score,
            weight=self.weights['institutional'],
            details=details
        )

    async def _stage_historical(self, signal: TradingSignal) -> StageResult:
        """Stage 7: Check setup type historical performance."""
        details = []
        score = 70.0  # Default neutral

        if self.db:
            try:
                setup_type = signal.setup_type.value if hasattr(signal.setup_type, 'value') else str(signal.setup_type)
                stats = await self.db.get_setup_performance(setup_type, signal.timeframe, days=30)

                total = stats.get('total', 0)
                if total >= 5:
                    win_rate = stats.get('win_rate', 0)
                    avg_pnl = stats.get('avg_pnl', 0)

                    if win_rate >= 70:
                        score = 95
                        details.append(f"Strong track record: {win_rate:.0f}% WR ({total} trades)")
                    elif win_rate >= 55:
                        score = 80
                        details.append(f"Good track record: {win_rate:.0f}% WR ({total} trades)")
                    elif win_rate >= 40:
                        score = 65
                        details.append(f"Mixed track record: {win_rate:.0f}% WR ({total} trades)")
                    else:
                        score = 40
                        details.append(f"Poor track record: {win_rate:.0f}% WR ({total} trades)")

                    if avg_pnl < -2:
                        score -= 15
                        details.append(f"Negative avg P&L: {avg_pnl:+.1f}%")
                else:
                    details.append(f"Insufficient history ({total} trades) — neutral score")
            except Exception:
                pass

        return StageResult(
            name='historical',
            passed=True,
            score=max(0, score),
            weight=self.weights['historical'],
            details=details
        )

    def _calculate_grade(self, composite: float, stages: List[StageResult],
                        rejection_reasons: List[str]) -> SignalGrade:
        """Stage 8: Convert composite score to letter grade."""
        # Hard reject if structural or risk/reward failed
        critical_stages = ['structural', 'risk_reward']
        for s in stages:
            if s.name in critical_stages and not s.passed:
                return SignalGrade.REJECTED

        # Also reject if too many stages failed
        failed_count = sum(1 for s in stages if not s.passed)
        if failed_count >= 3:
            return SignalGrade.REJECTED

        # Grade based on composite score
        if composite >= self.thresholds['A_PLUS']:
            return SignalGrade.A_PLUS
        elif composite >= self.thresholds['A']:
            return SignalGrade.A
        elif composite >= self.thresholds['B']:
            return SignalGrade.B
        elif composite >= self.thresholds['C']:
            return SignalGrade.C
        else:
            return SignalGrade.REJECTED
