"""
One-Click Content Generator
Auto-generates marketing content, reports, and social media posts
"""
from datetime import datetime, timedelta
from typing import Dict, List
import base64
from io import BytesIO


class ContentGenerator:
    """Generate marketing content from signal data"""
    
    def __init__(self, db):
        self.db = db
    
    async def generate_weekly_report(self) -> Dict:
        """Generate weekly performance report for social media"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        result = self.db.client.table('signals')\
            .select('*')\
            .eq('status', 'closed')\
            .gte('created_at', week_ago.isoformat())\
            .execute()
        
        signals = result.data if hasattr(result, 'data') else []
        
        if not signals:
            return {"text": "📊 No closed signals this week. Market scanning continues!", "image": None}
        
        wins = [s for s in signals if (s.get('pnl_percent') or 0) > 0]
        total_pnl = sum(s.get('pnl_percent', 0) or 0 for s in signals)
        win_rate = (len(wins) / len(signals) * 100) if signals else 0
        
        # Generate text
        text = f"""📊 **WEEKLY PERFORMANCE REPORT**
Week of {week_ago.strftime('%b %d')} - {datetime.utcnow().strftime('%b %d, %Y')}

🎯 Total Signals: {len(signals)}
✅ Wins: {len(wins)}
📈 Win Rate: {win_rate:.1f}%
💰 Total P&L: {total_pnl:+.2f}%

🔥 Best Performer: {max(signals, key=lambda x: x.get('pnl_percent', 0))['symbol']} ({max(s.get('pnl_percent', 0) for s in signals):+.2f}%)

Join VIP for full signal access! 🚀
"""
        
        return {"text": text, "image": None, "stats": {
            "total": len(signals),
            "wins": len(wins),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2)
        }}
    
    async def generate_testimonial_graphic(self, signal_id: str) -> Dict:
        """Generate testimonial graphic from winning signal"""
        result = self.db.client.table('signals')\
            .select('*')\
            .eq('id', signal_id)\
            .execute()
        
        if not result.data:
            return {"error": "Signal not found"}
        
        signal = result.data[0]
        pnl = signal.get('pnl_percent', 0)
        
        if pnl <= 0:
            return {"error": "Signal must be a winner for testimonial"}
        
        text = f"""🎯 SIGNAL WINNER

{signal['symbol']} {signal['direction']}
Timeframe: {signal['timeframe']}
Profit: +{pnl:.2f}%
Confidence: {signal.get('confidence', 0):.1f}%

✅ Another winning signal for our VIP members!

Join now: t.me/YourVIPBot
"""
        
        return {"text": text, "signal": signal}
    
    async def generate_comparison_chart_data(self, days: int = 30) -> Dict:
        """Generate data for performance comparison chart"""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = self.db.client.table('signals')\
            .select('*')\
            .eq('status', 'closed')\
            .gte('created_at', since.isoformat())\
            .execute()
        
        signals = result.data if hasattr(result, 'data') else []
        
        # Daily P&L
        daily_pnl = {}
        for s in signals:
            created = s.get('created_at')
            if created:
                try:
                    date = datetime.fromisoformat(created.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    pnl = s.get('pnl_percent', 0) or 0
                    daily_pnl[date] = daily_pnl.get(date, 0) + pnl
                except:
                    pass
        
        # Convert to chart data
        chart_data = [
            {"date": date, "pnl": round(pnl, 2)}
            for date, pnl in sorted(daily_pnl.items())
        ]
        
        return {
            "chart_data": chart_data,
            "total_pnl": sum(daily_pnl.values()),
            "best_day": max(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else None,
            "worst_day": min(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else None
        }
    
    async def generate_social_media_post(self, post_type: str = "performance") -> Dict:
        """Generate social media post templates"""
        
        if post_type == "performance":
            report = await self.generate_weekly_report()
            return {
                "platform": "twitter",
                "text": report["text"][:280],  # Twitter limit
                "hashtags": ["crypto", "trading", "signals", "bitcoin"]
            }
        
        elif post_type == "teaser":
            # Get latest pending signal
            result = self.db.client.table('signals')\
                .select('*')\
                .eq('status', 'pending')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                signal = result.data[0]
                text = f"""🚨 NEW SIGNAL ALERT

{signal['symbol']} setup detected
Timeframe: {signal['timeframe']}
Confidence: {signal.get('confidence', 0):.1f}%

VIP members get full entry, SL, and TP levels!

Join: t.me/YourVIPBot 🚀
"""
                return {"platform": "twitter", "text": text[:280]}
            
            return {"error": "No pending signals"}
        
        elif post_type == "education":
            tips = [
                "💡 TIP: Always use stop losses. Risk management > being right.",
                "📚 LESSON: Higher timeframes = higher probability. Trade with the trend.",
                "🎯 PRO TIP: Best signals come during London-NY overlap (12-4pm UTC).",
                "⚡ REMINDER: Quality over quantity. We send max 3 signals/day for a reason.",
                "🔥 FACT: Our 85%+ confidence signals have 70%+ win rate historically."
            ]
            import random
            return {"platform": "twitter", "text": random.choice(tips)}
        
        return {"error": "Unknown post type"}
    
    async def export_signals_pdf_data(self, days: int = 30) -> Dict:
        """Export signal history data for PDF generation"""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = self.db.client.table('signals')\
            .select('*')\
            .gte('created_at', since.isoformat())\
            .order('created_at', desc=True)\
            .execute()
        
        signals = result.data if hasattr(result, 'data') else []
        
        # Format for PDF
        formatted_signals = []
        for s in signals:
            formatted_signals.append({
                "date": s.get('created_at', '')[:10],
                "symbol": s.get('symbol', ''),
                "direction": s.get('direction', ''),
                "timeframe": s.get('timeframe', ''),
                "entry": s.get('entry_price', 0),
                "exit": s.get('actual_exit', 0),
                "pnl": s.get('pnl_percent', 0),
                "status": s.get('status', ''),
                "confidence": s.get('confidence', 0)
            })
        
        return {
            "signals": formatted_signals,
            "period": f"{since.strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')}",
            "total_signals": len(signals),
            "closed_signals": len([s for s in signals if s.get('status') == 'closed'])
        }
