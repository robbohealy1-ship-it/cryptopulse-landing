"""
Enhanced Analytics Engine for Admin Dashboard
Provides deep insights into signal performance, subscriber behavior, and revenue
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics
from collections import defaultdict


class AnalyticsEngine:
    """Advanced analytics for trading signals and business metrics"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_performance_analytics(self, days: int = 30) -> Dict:
        """
        Comprehensive performance analytics
        Returns win rates, P&L, best performers, time analysis
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        # Fetch all closed signals
        result = self.db.client.table('signals')\
            .select('*')\
            .eq('status', 'closed')\
            .gte('created_at', since.isoformat())\
            .execute()
        
        signals = result.data if hasattr(result, 'data') else []
        
        if not signals:
            return self._empty_analytics(days)
        
        # Basic metrics
        total = len(signals)
        wins = [s for s in signals if (s.get('pnl_percent') or 0) > 0]
        losses = [s for s in signals if (s.get('pnl_percent') or 0) < 0]
        breakeven = total - len(wins) - len(losses)
        
        win_rate = (len(wins) / (len(wins) + len(losses)) * 100) if (len(wins) + len(losses)) > 0 else 0
        
        # P&L metrics
        pnls = [s.get('pnl_percent', 0) or 0 for s in signals]
        total_pnl = sum(pnls)
        avg_pnl = statistics.mean(pnls) if pnls else 0
        
        # Risk metrics
        avg_win = statistics.mean([s.get('pnl_percent', 0) for s in wins]) if wins else 0
        avg_loss = statistics.mean([abs(s.get('pnl_percent', 0)) for s in losses]) if losses else 0
        profit_factor = (avg_win * len(wins)) / (avg_loss * len(losses)) if losses else 0
        
        # Sharpe ratio (simplified)
        sharpe = (avg_pnl / statistics.stdev(pnls)) if len(pnls) > 1 else 0
        
        # By timeframe
        by_timeframe = self._analyze_by_dimension(signals, 'timeframe')
        
        # By symbol
        by_symbol = self._analyze_by_dimension(signals, 'symbol')
        
        # Time of day analysis
        time_heatmap = self._analyze_time_of_day(signals)
        
        # Best performers
        best_symbols = sorted(by_symbol.items(), key=lambda x: x[1]['total_pnl'], reverse=True)[:5]
        best_timeframes = sorted(by_timeframe.items(), key=lambda x: x[1]['win_rate'], reverse=True)
        
        # Monthly trend
        monthly_trend = self._calculate_monthly_trend(signals)
        
        return {
            "period_days": days,
            "total_signals": total,
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": breakeven,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl_per_trade": round(avg_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
            "by_timeframe": by_timeframe,
            "by_symbol": by_symbol,
            "best_symbols": [{"symbol": s[0], **s[1]} for s in best_symbols],
            "best_timeframes": [{"timeframe": t[0], **t[1]} for t in best_timeframes],
            "time_heatmap": time_heatmap,
            "monthly_trend": monthly_trend
        }
    
    def _analyze_by_dimension(self, signals: List[Dict], dimension: str) -> Dict:
        """Analyze signals by a specific dimension (timeframe, symbol, etc)"""
        analysis = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0})
        
        for s in signals:
            key = s.get(dimension, 'Unknown')
            pnl = s.get('pnl_percent', 0) or 0
            
            analysis[key]["count"] += 1
            analysis[key]["total_pnl"] += pnl
            
            if pnl > 0:
                analysis[key]["wins"] += 1
            elif pnl < 0:
                analysis[key]["losses"] += 1
        
        # Calculate win rates
        for key, data in analysis.items():
            total_trades = data["wins"] + data["losses"]
            data["win_rate"] = round((data["wins"] / total_trades * 100) if total_trades > 0 else 0, 1)
            data["avg_pnl"] = round(data["total_pnl"] / data["count"], 2) if data["count"] > 0 else 0
        
        return dict(analysis)
    
    def _analyze_time_of_day(self, signals: List[Dict]) -> Dict:
        """Analyze performance by hour of day"""
        hourly = defaultdict(lambda: {"count": 0, "wins": 0, "total_pnl": 0})
        
        for s in signals:
            created = s.get('created_at')
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    hour = dt.hour
                    pnl = s.get('pnl_percent', 0) or 0
                    
                    hourly[hour]["count"] += 1
                    hourly[hour]["total_pnl"] += pnl
                    if pnl > 0:
                        hourly[hour]["wins"] += 1
                except:
                    pass
        
        # Calculate win rates
        for hour, data in hourly.items():
            data["win_rate"] = round((data["wins"] / data["count"] * 100) if data["count"] > 0 else 0, 1)
        
        return dict(hourly)
    
    def _calculate_monthly_trend(self, signals: List[Dict]) -> List[Dict]:
        """Calculate monthly P&L trend"""
        monthly = defaultdict(lambda: {"pnl": 0, "count": 0, "wins": 0})
        
        for s in signals:
            created = s.get('created_at')
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    month_key = dt.strftime('%Y-%m')
                    pnl = s.get('pnl_percent', 0) or 0
                    
                    monthly[month_key]["pnl"] += pnl
                    monthly[month_key]["count"] += 1
                    if pnl > 0:
                        monthly[month_key]["wins"] += 1
                except:
                    pass
        
        # Convert to list and sort
        trend = []
        for month, data in sorted(monthly.items()):
            trend.append({
                "month": month,
                "pnl": round(data["pnl"], 2),
                "count": data["count"],
                "win_rate": round((data["wins"] / data["count"] * 100) if data["count"] > 0 else 0, 1)
            })
        
        return trend
    
    def _empty_analytics(self, days: int) -> Dict:
        """Return empty analytics structure"""
        return {
            "period_days": days,
            "total_signals": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_pnl_per_trade": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "sharpe_ratio": 0,
            "by_timeframe": {},
            "by_symbol": {},
            "best_symbols": [],
            "best_timeframes": [],
            "time_heatmap": {},
            "monthly_trend": []
        }
    
    async def get_subscriber_analytics(self) -> Dict:
        """
        Subscriber lifecycle and revenue analytics
        """
        result = self.db.client.table('subscribers').select('*').execute()
        subs = result.data if hasattr(result, 'data') else []
        
        if not subs:
            return self._empty_subscriber_analytics()
        
        # Status breakdown
        active = [s for s in subs if s.get('status') == 'active']
        trial = [s for s in subs if s.get('status') == 'trial']
        expired = [s for s in subs if s.get('status') == 'expired']
        
        # Revenue metrics
        monthly_revenue = len(active) * 100  # Assuming $100/month
        
        # Churn rate (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_cancellations = [
            s for s in expired 
            if s.get('cancelled_at') and 
            datetime.fromisoformat(s['cancelled_at'].replace('Z', '+00:00')) >= thirty_days_ago
        ]
        churn_rate = (len(recent_cancellations) / len(active) * 100) if active else 0
        
        # Conversion funnel
        trial_to_paid = len([s for s in active if s.get('tier') != 'trial'])
        conversion_rate = (trial_to_paid / len(trial) * 100) if trial else 0
        
        # LTV calculation (simplified: avg months * monthly price)
        avg_lifetime_months = 6  # Placeholder - calculate from actual data
        ltv = avg_lifetime_months * 100
        
        return {
            "total_subscribers": len(subs),
            "active": len(active),
            "trial": len(trial),
            "expired": len(expired),
            "monthly_revenue": monthly_revenue,
            "churn_rate": round(churn_rate, 1),
            "conversion_rate": round(conversion_rate, 1),
            "ltv": ltv,
            "recent_cancellations": len(recent_cancellations)
        }
    
    def _empty_subscriber_analytics(self) -> Dict:
        """Return empty subscriber analytics"""
        return {
            "total_subscribers": 0,
            "active": 0,
            "trial": 0,
            "expired": 0,
            "monthly_revenue": 0,
            "churn_rate": 0,
            "conversion_rate": 0,
            "ltv": 0,
            "recent_cancellations": 0
        }
