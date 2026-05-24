"""
Portfolio Analytics Engine

Calculates advanced trading metrics from signal history:
- Sharpe Ratio: risk-adjusted return
- Sortino Ratio: downside-risk-adjusted return
- Profit Factor: gross profit / gross loss
- Expectancy: average R per trade
- Calmar Ratio: return / max drawdown
- Win Rate, Avg Win/Loss, Payoff Ratio
"""

import math
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioMetrics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    payoff_ratio: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    expectancy: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    avg_duration_minutes: float = 0.0
    avg_slippage: float = 0.0


class PortfolioAnalytics:
    """Calculate portfolio-level trading metrics."""

    RISK_FREE_RATE = 0.0  # Assume 0% risk-free for crypto daily

    def calculate(self, trades: List[Dict], days: int = 30) -> PortfolioMetrics:
        """Calculate all metrics from a list of closed trade dicts."""
        if not trades:
            return PortfolioMetrics()

        pnls = [t.get('pnl_percent', 0) or 0 for t in trades]
        total = len(trades)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        metrics = PortfolioMetrics()
        metrics.total_trades = total
        metrics.wins = len(wins)
        metrics.losses = len(losses)
        metrics.win_rate = (len(wins) / total) * 100 if total > 0 else 0
        metrics.avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        metrics.avg_win = sum(wins) / len(wins) if wins else 0
        metrics.avg_loss = sum(losses) / len(losses) if losses else 0
        metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss) if metrics.avg_loss != 0 else 0

        # Profit Factor
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999 if gross_profit > 0 else 0)

        # Sharpe Ratio (daily returns approximated from trade pnls)
        if len(pnls) >= 2:
            avg = metrics.avg_pnl
            variance = sum((p - avg) ** 2 for p in pnls) / (len(pnls) - 1)
            std = math.sqrt(variance) if variance > 0 else 0
            metrics.sharpe_ratio = ((avg - self.RISK_FREE_RATE) / std) * math.sqrt(365) if std > 0 else 0

        # Sortino Ratio (downside deviation only)
        if len(pnls) >= 2:
            downside_pnl = [p for p in pnls if p < 0]
            if downside_pnl:
                downside_avg = sum(downside_pnl) / len(downside_pnl)
                downside_var = sum((p - downside_avg) ** 2 for p in downside_pnl) / (len(downside_pnl))
                downside_std = math.sqrt(downside_var) if downside_var > 0 else 0
                metrics.sortino_ratio = ((avg - self.RISK_FREE_RATE) / downside_std) * math.sqrt(365) if downside_std > 0 else 0
            else:
                metrics.sortino_ratio = 999  # No losses

        # Expectancy = (Win% * AvgWin) + (Loss% * AvgLoss)
        win_pct = metrics.win_rate / 100
        loss_pct = 1 - win_pct
        metrics.expectancy = (win_pct * metrics.avg_win) + (loss_pct * metrics.avg_loss)

        # Max Drawdown from equity curve
        equity = 100.0
        peak = equity
        max_dd = 0.0
        for pnl in pnls:
            equity *= (1 + pnl / 100)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd
        metrics.max_drawdown = max_dd

        # Calmar Ratio
        total_return = (equity - 100) / 100 * 100
        annualized_return = total_return * (365 / days) if days > 0 else 0
        metrics.calmar_ratio = annualized_return / max_dd if max_dd > 0 else (999 if annualized_return > 0 else 0)

        # Consecutive streaks
        max_loss_streak = 0
        max_win_streak = 0
        current_loss = 0
        current_win = 0
        for pnl in pnls:
            if pnl > 0:
                current_win += 1
                current_loss = 0
                max_win_streak = max(max_win_streak, current_win)
            else:
                current_loss += 1
                current_win = 0
                max_loss_streak = max(max_loss_streak, current_loss)
        metrics.max_consecutive_losses = max_loss_streak
        metrics.max_consecutive_wins = max_win_streak

        # Duration & slippage averages
        durations = [t.get('duration_minutes') for t in trades if t.get('duration_minutes')]
        metrics.avg_duration_minutes = sum(durations) / len(durations) if durations else 0

        entry_slips = [t.get('entry_slippage_percent') for t in trades if t.get('entry_slippage_percent') is not None]
        exit_slips = [t.get('exit_slippage_percent') for t in trades if t.get('exit_slippage_percent') is not None]
        all_slips = entry_slips + exit_slips
        metrics.avg_slippage = sum(all_slips) / len(all_slips) if all_slips else 0

        return metrics

    def to_dict(self, metrics: PortfolioMetrics) -> Dict:
        return {
            'total_trades': metrics.total_trades,
            'wins': metrics.wins,
            'losses': metrics.losses,
            'win_rate': round(metrics.win_rate, 2),
            'avg_pnl': round(metrics.avg_pnl, 2),
            'avg_win': round(metrics.avg_win, 2),
            'avg_loss': round(metrics.avg_loss, 2),
            'payoff_ratio': round(metrics.payoff_ratio, 2),
            'profit_factor': round(metrics.profit_factor, 2),
            'sharpe_ratio': round(metrics.sharpe_ratio, 2),
            'sortino_ratio': round(metrics.sortino_ratio, 2),
            'expectancy': round(metrics.expectancy, 2),
            'calmar_ratio': round(metrics.calmar_ratio, 2),
            'max_drawdown': round(metrics.max_drawdown, 2),
            'max_consecutive_losses': metrics.max_consecutive_losses,
            'max_consecutive_wins': metrics.max_consecutive_wins,
            'avg_duration_minutes': round(metrics.avg_duration_minutes, 2),
            'avg_slippage': round(metrics.avg_slippage, 4),
        }
