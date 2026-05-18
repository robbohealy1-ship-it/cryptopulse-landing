"""
CryptoPulse Admin Dashboard Server
FastAPI backend for full operational control.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.config import settings
from src.utils.logger import get_logger
from src.admin.analytics_engine import AnalyticsEngine
from src.admin.content_generator import ContentGenerator

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

logger = get_logger(__name__)

app = FastAPI(title="CryptoPulse Admin", version="2.0")

# ==================== Rate Limiting ====================
_request_log: Dict[str, List[datetime]] = {}
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 5  # Max 5 signal creations per minute per IP

def _check_rate_limit(client_ip: str) -> bool:
    """Simple in-memory rate limiter. Returns True if allowed."""
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    
    # Get or init request history for this IP
    history = _request_log.get(client_ip, [])
    # Filter to only requests in the current window
    history = [t for t in history if t > window_start]
    
    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        _request_log[client_ip] = history
        return False
    
    history.append(now)
    _request_log[client_ip] = history
    return True

# Global reference to the orchestrator (set at startup)
orchestrator = None
analytics_engine = None
content_generator = None


# ==================== Pydantic Models ====================

class SignalAction(BaseModel):
    signal_id: str
    action: str  # "approve" or "reject"


class MarketingPost(BaseModel):
    channel: str  # "free", "vip", "both"
    message: str
    pin: bool = False


class CampaignTrigger(BaseModel):
    campaign_type: str  # "fomo", "social_proof", "urgency", "custom"
    message: Optional[str] = None


class ScheduleJob(BaseModel):
    job_type: str  # "outlook", "recap", "weekly", "scan"
    when: Optional[str] = None  # ISO datetime or "now"


class SettingsUpdate(BaseModel):
    key: str
    value: Any


# ==================== Helper ====================

def require_orch():
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    return orchestrator


# ==================== API Endpoints ====================

@app.get("/marketing")
async def marketing_dashboard():
    """Serve the free marketing dashboard page"""
    return FileResponse(os.path.join(_STATIC_DIR, "marketing.html"))


@app.get("/api/status")
async def system_status():
    """Overall system health and status."""
    orch = require_orch()
    scheduler_running = orch.scheduler.running if orch.scheduler else False
    
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "scheduler": scheduler_running,
        "admin_bot": orch.admin_bot.app is not None if orch.admin_bot else False,
        "vip_bot": orch.vip_bot.app is not None if orch.vip_bot else False,
        "components": {
            "signal_engine": True,
            "channel_publisher": True,
            "database": True,
            "social_media": orch.social_media.twitter_enabled if orch.social_media else False,
            "discord": orch.discord_publisher.enabled if orch.discord_publisher else False,
            "viral_growth": orch.viral_growth is not None if hasattr(orch, 'viral_growth') else False,
        }
    }


@app.get("/api/stats/daily")
async def daily_stats():
    """Today's signal statistics."""
    orch = require_orch()
    try:
        stats = await orch.db.get_daily_stats()
        return stats
    except Exception as e:
        logger.error(f"Dashboard daily stats error: {e}")
        return {"error": str(e)}


@app.get("/api/stats/weekly")
async def weekly_stats():
    """This week's signal statistics."""
    orch = require_orch()
    try:
        stats = await orch.db.get_weekly_stats()
        return stats
    except Exception as e:
        logger.error(f"Dashboard weekly stats error: {e}")
        return {"error": str(e)}


@app.get("/api/signals/pending")
async def pending_signals():
    """Signals waiting for admin approval."""
    orch = require_orch()
    try:
        pending = list(orch.admin_bot.pending_signals.values())
        return {
            "count": len(pending),
            "signals": [
                {
                    "id": s.id,
                    "symbol": s.symbol,
                    "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                    "timeframe": s.timeframe,
                    "confidence": s.confidence,
                    "risk_reward": s.risk_reward,
                    "entry_price": s.entry_price,
                    "stop_loss": s.stop_loss,
                    "take_profit_1": s.take_profit_1,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in pending
            ]
        }
    except Exception as e:
        return {"count": 0, "signals": [], "error": str(e)}


@app.get("/api/signals/active")
async def active_signals():
    """Active/running signals being tracked (persists across restarts)."""
    orch = require_orch()
    try:
        active = await orch.db.get_active_signals()
        
        # Get current prices for P&L calculation
        signals_with_pnl = []
        for s in active:
            current_price = await orch._get_current_price(s.symbol)
            entry = s.actual_entry or s.entry_price
            
            pnl = 0
            if current_price and entry and entry != 0:
                pnl = ((current_price - entry) / entry) * 100
                if s.direction.value == "SHORT":
                    pnl = -pnl
            
            signals_with_pnl.append({
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                "timeframe": s.timeframe,
                "confidence": s.confidence,
                "risk_reward": s.risk_reward,
                "entry_price": entry,
                "current_price": current_price,
                "stop_loss": s.stop_loss,
                "take_profit_1": s.take_profit_1,
                "take_profit_2": s.take_profit_2,
                "take_profit_3": s.take_profit_3,
                "tp1_hit": getattr(s, 'tp1_hit', False),
                "tp2_hit": getattr(s, 'tp2_hit', False),
                "tp3_hit": getattr(s, 'tp3_hit', False),
                "pnl_percent": round(pnl, 2),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "approved_at": s.approved_at.isoformat() if hasattr(s, 'approved_at') and s.approved_at else None,
            })
        
        return {
            "count": len(signals_with_pnl),
            "signals": signals_with_pnl
        }
    except Exception as e:
        logger.error(f"Error getting active signals: {e}")
        return {"count": 0, "signals": [], "error": str(e)}


# ==================== ALPHA/DEGEN PLAYS ENDPOINTS ====================

@app.get("/api/alpha/plays")
async def alpha_plays():
    """Get alpha plays (pending, active, or completed)."""
    orch = require_orch()
    try:
        active = []
        pending = []
        
        # Get active plays from engine
        if orch.alpha_engine:
            for play_id, play in orch.alpha_engine.active_plays.items():
                active.append({
                    "id": play_id,
                    "symbol": play.candidate.symbol,
                    "name": play.candidate.name,
                    "chain": play.candidate.chain,
                    "status": play.status,
                    "entry_price": play.entry_price,
                    "current_price": play.current_price,
                    "current_pnl": round(play.current_pnl, 2),
                    "stop_loss": play.stop_loss,
                    "take_profit_1": play.take_profit_1,
                    "take_profit_2": play.take_profit_2,
                    "market_cap": play.candidate.market_cap_usd,
                    "volume_24h": play.candidate.volume_24h,
                    "price_change_24h": round(play.candidate.price_change_24h, 1),
                    "overall_score": round(play.candidate.overall_score, 1),
                    "catalyst": play.candidate.catalyst,
                    "dex_url": play.candidate.dex_url,
                    "chart_url": play.candidate.chart_url,
                    "buy_url": play.candidate.buy_url,
                    "red_flags": play.candidate.red_flags,
                    "approved_at": play.approved_at.isoformat() if play.approved_at else None,
                    "position_size": play.position_size,
                })
            
            # Get pending plays
            for symbol, candidate in orch.alpha_engine.pending_plays.items():
                pending.append({
                    "symbol": symbol,
                    "name": candidate.name,
                    "chain": candidate.chain,
                    "market_cap": candidate.market_cap_usd,
                    "volume_24h": candidate.volume_24h,
                    "price_change_24h": round(candidate.price_change_24h, 1),
                    "overall_score": round(candidate.overall_score, 1),
                    "catalyst": candidate.catalyst,
                })
        
        return {
            "active_count": len(active),
            "pending_count": len(pending),
            "active": active,
            "pending": pending
        }
    except Exception as e:
        logger.error(f"Error getting alpha plays: {e}")
        return {"active_count": 0, "pending_count": 0, "active": [], "pending": [], "error": str(e)}


@app.post("/api/alpha/approve")
async def approve_alpha(symbol: str):
    """Approve a pending alpha play from dashboard."""
    orch = require_orch()
    try:
        if not orch.alpha_engine:
            return {"success": False, "error": "Alpha engine not initialized"}
        
        play = await orch.alpha_engine.approve_play(symbol)
        if play:
            # Publish to VIP
            await orch.alpha_engine.publish_to_vip(play)
            # Try to publish teaser to free
            await orch.alpha_engine.publish_teaser_to_free(play)
            
            return {
                "success": True,
                "play_id": play.id,
                "symbol": symbol,
                "entry": play.entry_price,
                "tp1": play.take_profit_1,
                "tp2": play.take_profit_2,
                "sl": play.stop_loss,
            }
        else:
            return {"success": False, "error": f"Alpha play {symbol} not found in pending queue"}
    except Exception as e:
        logger.error(f"Error approving alpha play: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/alpha/trigger")
async def trigger_alpha_scan():
    """Manually trigger an alpha play discovery scan."""
    orch = require_orch()
    try:
        if not orch.alpha_engine:
            return {"success": False, "error": "Alpha engine not initialized"}
        
        # Run scan in background
        asyncio.create_task(orch._scan_alpha_plays())
        
        return {"success": True, "message": "Alpha scan triggered. Check logs for results."}
    except Exception as e:
        logger.error(f"Error triggering alpha scan: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/alpha/stats")
async def alpha_stats():
    """Get alpha plays statistics."""
    orch = require_orch()
    try:
        if not orch.alpha_engine:
            return {
                "vip_daily_count": 0,
                "free_weekly_count": 0,
                "active_plays": 0,
                "pending_plays": 0,
                "enabled": False
            }
        
        return {
            "vip_daily_count": orch.alpha_engine.vip_count_today,
            "free_weekly_count": orch.alpha_engine.free_count_this_week,
            "vip_daily_limit": orch.alpha_engine.vip_daily_limit,
            "free_weekly_limit": orch.alpha_engine.free_weekly_limit,
            "active_plays": len(orch.alpha_engine.active_plays),
            "pending_plays": len(orch.alpha_engine.pending_plays),
            "enabled": True
        }
    except Exception as e:
        logger.error(f"Error getting alpha stats: {e}")
        return {"error": str(e)}


# ==================== SIGNALS ====================

@app.post("/api/signals/action")
async def signal_action(action: SignalAction):
    """Approve or reject a pending signal from the dashboard."""
    orch = require_orch()
    signal = orch.admin_bot.pending_signals.get(action.signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    if action.action == "approve":
        await orch.on_signal_approved(signal)
        del orch.admin_bot.pending_signals[action.signal_id]
        return {"success": True, "message": f"Signal {action.signal_id} approved"}
    elif action.action == "reject":
        await orch.on_signal_rejected(signal)
        del orch.admin_bot.pending_signals[action.signal_id]
        return {"success": True, "message": f"Signal {action.signal_id} rejected"}
    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")


@app.get("/api/signals/history")
async def signal_history(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None)
):
    """Recent signal history."""
    orch = require_orch()
    try:
        query = orch.db.client.table('signals').select('*').order('created_at', desc=True).limit(limit)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        signals = result.data if hasattr(result, 'data') else []
        return {"count": len(signals), "signals": signals}
    except Exception as e:
        logger.error(f"Dashboard history error: {e}")
        return {"count": 0, "signals": [], "error": str(e)}


@app.post("/api/marketing/post")
async def send_marketing_post(post: MarketingPost):
    """Send a custom message to free, vip, or both channels."""
    orch = require_orch()
    try:
        channels = []
        if post.channel in ("free", "both"):
            channels.append(getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None))
        if post.channel in ("vip", "both"):
            channels.append(getattr(settings, 'TELEGRAM_VIP_CHANNEL_ID', None))
        
        sent = []
        for ch in channels:
            if ch:
                msg = await orch.admin_bot.app.bot.send_message(
                    chat_id=ch, text=post.message, parse_mode='HTML'
                )
                sent.append({"channel": ch, "message_id": msg.message_id})
                if post.pin:
                    await orch.admin_bot.app.bot.pin_chat_message(ch, msg.message_id)
        
        return {"success": True, "sent": sent}
    except Exception as e:
        logger.error(f"Dashboard marketing post error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/marketing/campaign")
async def trigger_campaign(campaign: CampaignTrigger):
    """Trigger a marketing campaign manually."""
    orch = require_orch()
    try:
        if campaign.campaign_type == "fomo":
            # Send FOMO to free channel
            text = campaign.message or "🔥 VIP members just hit targets. Full signals exclusively in VIP."
            await orch.channel_publisher.send_free_channel_message(text)
            return {"success": True, "type": "fomo"}
        
        elif campaign.campaign_type == "social_proof":
            stats = await orch.db.get_weekly_stats()
            text = (
                f"📊 <b>This Week's Results</b>\n\n"
                f"Signals: {stats.get('total_signals', 0)}\n"
                f"Win Rate: {stats.get('win_rate', 0):.0f}%\n"
                f"Total P&L: +{stats.get('total_pnl', 0):.1f}%\n\n"
                f"💎 See full plans in VIP"
            )
            await orch.channel_publisher.send_free_channel_message(text)
            return {"success": True, "type": "social_proof"}
        
        elif campaign.campaign_type == "urgency":
            text = (
                "⏰ <b>Limited VIP Spots</b>\n\n"
                "Only 20 VIP memberships available this month.\n"
                "Once full, free channel stays teaser-only.\n\n"
                f"🤖 <a href='https://t.me/{settings.TELEGRAM_VIP_BOT_USERNAME}'>Join VIP Now</a>"
            )
            await orch.channel_publisher.send_free_channel_message(text)
            return {"success": True, "type": "urgency"}
        
        elif campaign.campaign_type == "custom":
            if not campaign.message:
                raise HTTPException(status_code=400, detail="Custom campaign requires a message")
            await orch.channel_publisher.send_free_channel_message(campaign.message)
            return {"success": True, "type": "custom"}
        
        else:
            raise HTTPException(status_code=400, detail="Unknown campaign type")
    except Exception as e:
        logger.error(f"Dashboard campaign error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schedule/trigger")
async def trigger_scheduled_job(job: ScheduleJob):
    """Manually trigger a scheduled job."""
    orch = require_orch()
    try:
        if job.job_type == "outlook":
            await orch._post_morning_outlook()
            return {"success": True, "job": "morning_outlook"}
        elif job.job_type == "recap":
            await orch._post_evening_recap()
            return {"success": True, "job": "evening_recap"}
        elif job.job_type == "weekly":
            await orch._post_weekly_report()
            return {"success": True, "job": "weekly_report"}
        elif job.job_type == "scan":
            await orch.scan_15m()
            return {"success": True, "job": "scan_15m"}
        else:
            raise HTTPException(status_code=400, detail="Unknown job type")
    except Exception as e:
        logger.error(f"Dashboard schedule trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subscribers")
async def subscribers():
    """List VIP subscribers."""
    orch = require_orch()
    try:
        result = orch.db.client.table('subscribers').select('*').order('created_at', desc=True).limit(100).execute()
        subs = result.data if hasattr(result, 'data') else []
        return {"count": len(subs), "subscribers": subs}
    except Exception as e:
        logger.error(f"Dashboard subscribers error: {e}")
        return {"count": 0, "subscribers": [], "error": str(e)}


@app.get("/api/settings")
async def get_settings():
    """View current config (safe values only)."""
    return {
        "signal_expiry_minutes": settings.SIGNAL_EXPIRY_MINUTES,
        "min_confidence": getattr(settings, 'MIN_CONFIDENCE', 85),
        "vip_price_monthly": getattr(settings, 'VIP_PRICE_MONTHLY', 49),
        "vip_price_quarterly": getattr(settings, 'VIP_PRICE_QUARTERLY', 129),
        "vip_price_lifetime": getattr(settings, 'VIP_PRICE_LIFETIME', 499),
        "free_channel_id": getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None),
        "vip_channel_id": getattr(settings, 'TELEGRAM_VIP_CHANNEL_ID', None),
        "landing_page": getattr(settings, 'LANDING_PAGE_URL', None),
        "twitter_enabled": getattr(settings, 'TWITTER_API_KEY', None) is not None,
        "newsapi_enabled": getattr(settings, 'NEWS_API_KEY', None) is not None,
    }


@app.get("/api/signals/performance")
async def signal_performance(days: int = Query(30, ge=1, le=365)):
    """Get signal performance analytics."""
    orch = require_orch()
    try:
        # Defensive: ensure db is connected
        if not orch.db or not getattr(orch.db, 'client', None):
            logger.warning("Performance endpoint: database not connected")
            return {
                "period_days": days,
                "total_signals": 0,
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_pnl_per_trade": 0,
                "by_symbol": {},
                "by_timeframe": {},
            }
        since = datetime.utcnow() - timedelta(days=days)
        result = orch.db.client.table('signals').select('*').gte('created_at', since.isoformat()).execute()
        rows = result.data if hasattr(result, 'data') else []
        
        total = len(rows)
        wins = sum(1 for r in rows if (r.get('pnl_percent') or 0) > 0)
        losses = sum(1 for r in rows if (r.get('pnl_percent') or 0) < 0)
        breakeven = total - wins - losses
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        total_pnl = sum(r.get('pnl_percent', 0) or 0 for r in rows)
        avg_pnl = total_pnl / total if total > 0 else 0
        
        by_symbol = {}
        for r in rows:
            sym = r.get('symbol', 'Unknown')
            if sym not in by_symbol:
                by_symbol[sym] = {"count": 0, "wins": 0, "total_pnl": 0}
            by_symbol[sym]["count"] += 1
            pnl = r.get('pnl_percent', 0) or 0
            by_symbol[sym]["total_pnl"] += pnl
            if pnl > 0:
                by_symbol[sym]["wins"] += 1
        
        by_timeframe = {}
        for r in rows:
            tf = r.get('timeframe', 'Unknown')
            if tf not in by_timeframe:
                by_timeframe[tf] = {"count": 0, "wins": 0, "total_pnl": 0}
            by_timeframe[tf]["count"] += 1
            pnl = r.get('pnl_percent', 0) or 0
            by_timeframe[tf]["total_pnl"] += pnl
            if pnl > 0:
                by_timeframe[tf]["wins"] += 1
        
        return {
            "period_days": days,
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl_per_trade": round(avg_pnl, 2),
            "by_symbol": by_symbol,
            "by_timeframe": by_timeframe,
        }
    except Exception as e:
        logger.error(f"Performance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SIGNALS PRO ====================

@app.get("/api/signals/{signal_id}")
async def get_signal_detail(signal_id: str):
    """Get full details of a single signal."""
    orch = require_orch()
    try:
        result = orch.db.client.table('signals').select('*').eq('id', signal_id).execute()
        rows = result.data if hasattr(result, 'data') else []
        if not rows:
            raise HTTPException(status_code=404, detail="Signal not found")
        return {"signal": rows[0]}
    except Exception as e:
        logger.error(f"Signal detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BulkSignalAction(BaseModel):
    signal_ids: List[str]
    action: str  # "approve" or "reject"


@app.post("/api/signals/bulk-action")
async def bulk_signal_action(bulk: BulkSignalAction):
    """Bulk approve or reject multiple signals."""
    orch = require_orch()
    results = {"approved": [], "rejected": [], "failed": []}
    try:
        for sid in bulk.signal_ids:
            try:
                if bulk.action == "approve":
                    signal = orch.admin_bot.pending_signals.get(sid)
                    if signal:
                        await orch.on_signal_approved(signal)
                        results["approved"].append(sid)
                    else:
                        results["failed"].append(sid)
                elif bulk.action == "reject":
                    orch.admin_bot.pending_signals.pop(sid, None)
                    results["rejected"].append(sid)
                else:
                    results["failed"].append(sid)
            except Exception as inner:
                logger.error(f"Bulk action failed for {sid}: {inner}")
                results["failed"].append(sid)
        return {"success": True, "results": results}
    except Exception as e:
        logger.error(f"Bulk action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ManualSignal(BaseModel):
    symbol: str
    direction: str  # LONG or SHORT
    timeframe: str = "1h"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    confidence: float = 90.0
    notes: Optional[str] = None


@app.post("/api/signals/create")
async def create_manual_signal(request: Request, sig: ManualSignal):
    """Manually create a signal and optionally publish immediately."""
    # Rate limit: max 5 creations per minute per IP
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 5 signal creations per minute.")
    
    orch = require_orch()
    try:
        from src.models.signal import (
            SignalDirection, TradingSignal, SetupType,
            TechnicalScore, ContextScore
        )
        
        # Validate required fields are present and valid
        if sig.stop_loss is None or sig.take_profit_1 is None:
            raise HTTPException(status_code=400, detail="stop_loss and take_profit_1 are required")
        if sig.entry_price <= 0 or sig.stop_loss <= 0 or sig.take_profit_1 <= 0:
            raise HTTPException(status_code=400, detail="Prices must be positive numbers")
        
        direction = SignalDirection.LONG if sig.direction.upper() == "LONG" else SignalDirection.SHORT
        
        # Calculate risk/reward
        risk = abs(sig.entry_price - sig.stop_loss)
        reward_1 = abs(sig.take_profit_1 - sig.entry_price)
        risk_reward = round(reward_1 / risk, 2) if risk > 0 else 2.0
        
        # Create required score objects with defaults
        technical_score = TechnicalScore(
            trend_score=sig.confidence,
            volume_score=sig.confidence * 0.9,
            momentum_score=sig.confidence * 0.95,
            structure_score=sig.confidence * 0.85,
            total_score=sig.confidence
        )
        
        context_score = ContextScore(
            macro_score=sig.confidence * 0.8,
            news_score=sig.confidence * 0.75,
            sentiment_score=sig.confidence * 0.85,
            total_score=sig.confidence * 0.8
        )
        
        # Estimate ATR as 2x the stop distance (rough approximation)
        atr = risk * 2.0
        
        signal = TradingSignal(
            symbol=sig.symbol,
            direction=direction,
            setup_type=SetupType.SUPPORT_RESISTANCE,  # Default for manual
            timeframe=sig.timeframe,
            entry_price=sig.entry_price,
            stop_loss=sig.stop_loss,
            take_profit_1=sig.take_profit_1,
            take_profit_2=sig.take_profit_2,
            take_profit_3=sig.take_profit_3,
            confidence=sig.confidence,
            technical_score=technical_score,
            context_score=context_score,
            reasoning=sig.notes or "Manual signal created from dashboard",
            risk_reward=risk_reward,
            atr=atr,
            volume_24h=0,  # Manual signals don't have volume data
            notes=sig.notes or "Manual signal from dashboard"
        )
        await orch.on_signal_approved(signal)
        return {"success": True, "signal_id": signal.id}
    except Exception as e:
        logger.error(f"Manual signal creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MARKETING PRO ====================

@app.get("/api/marketing/history")
async def marketing_history(limit: int = Query(50, ge=1, le=200)):
    """Get recent marketing posts sent."""
    orch = require_orch()
    try:
        result = orch.db.client.table('marketing_posts').select('*').order('created_at', desc=True).limit(limit).execute()
        rows = result.data if hasattr(result, 'data') else []
        return {"count": len(rows), "posts": rows}
    except Exception as e:
        logger.error(f"Marketing history error: {e}")
        return {"count": 0, "posts": []}


@app.get("/api/marketing/templates")
async def marketing_templates():
    """Get available marketing message templates."""
    return {
        "templates": [
            {"id": "fomo", "name": "FOMO Alert", "text": "🔥 VIP members just hit targets. Full signals exclusively in VIP."},
            {"id": "social_proof", "name": "Social Proof", "text": "📊 This week's results: {win_rate}% win rate, +{total_pnl}% P&L."},
            {"id": "urgency", "name": "Urgency", "text": "⏰ Limited VIP spots available. Join before we close signups."},
            {"id": "welcome", "name": "Welcome", "text": "🚀 Welcome to CryptoPulse! Here's what to expect..."},
            {"id": "education", "name": "Education", "text": "📚 Trading tip: Never risk more than 2% per trade."},
            {"id": "outlook", "name": "Morning Outlook", "text": "🌅 Good morning! Today's market outlook..."},
            {"id": "recap", "name": "Evening Recap", "text": "🌙 Market wrap. Today's signals and results..."},
        ]
    }


class ScheduledPost(BaseModel):
    channel: str  # free, vip, both
    message: str
    scheduled_at: str  # ISO datetime
    pin: bool = False


@app.post("/api/marketing/schedule")
async def schedule_marketing_post(post: ScheduledPost):
    """Schedule a future marketing post."""
    orch = require_orch()
    try:
        record = {
            "channel": post.channel,
            "message": post.message,
            "scheduled_at": post.scheduled_at,
            "pin": post.pin,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        orch.db.client.table('scheduled_posts').insert(record).execute()
        return {"success": True, "scheduled_at": post.scheduled_at}
    except Exception as e:
        logger.error(f"Schedule post error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/marketing/schedule")
async def get_scheduled_posts():
    """Get upcoming scheduled posts."""
    orch = require_orch()
    try:
        result = orch.db.client.table('scheduled_posts').select('*').eq('status', 'pending').order('scheduled_at', desc=True).limit(50).execute()
        rows = result.data if hasattr(result, 'data') else []
        return {"count": len(rows), "posts": rows}
    except Exception as e:
        logger.error(f"Get scheduled posts error: {e}")
        return {"count": 0, "posts": []}


# ==================== SUBSCRIBERS PRO ====================

@app.get("/api/subscribers/detailed")
async def subscribers_detailed():
    """Get full VIP subscriber details."""
    orch = require_orch()
    try:
        result = orch.db.client.table('subscribers').select('*').order('created_at', desc=True).limit(200).execute()
        subs = result.data if hasattr(result, 'data') else []
        active = sum(1 for s in subs if s.get('status') == 'active')
        expired = sum(1 for s in subs if s.get('status') == 'expired')
        trial = sum(1 for s in subs if s.get('status') == 'trial')
        return {
            "count": len(subs),
            "active": active,
            "expired": expired,
            "trial": trial,
            "subscribers": subs
        }
    except Exception as e:
        logger.error(f"Subscribers detailed error: {e}")
        return {"count": 0, "active": 0, "expired": 0, "trial": 0, "subscribers": []}


class DmBlast(BaseModel):
    message: str
    filter_status: Optional[str] = None  # active, expired, trial, or None for all


@app.post("/api/subscribers/blast")
async def subscriber_dm_blast(blast: DmBlast):
    """Send a DM blast to VIP subscribers."""
    orch = require_orch()
    sent = 0
    failed = 0
    try:
        query = orch.db.client.table('subscribers').select('telegram_user_id')
        if blast.filter_status:
            query = query.eq('status', blast.filter_status)
        result = query.execute()
        subs = result.data if hasattr(result, 'data') else []
        
        for sub in subs:
            try:
                user_id = sub.get('telegram_user_id')
                if user_id:
                    await orch.admin_bot.app.bot.send_message(chat_id=user_id, text=blast.message, parse_mode='HTML')
                    sent += 1
            except Exception as inner:
                failed += 1
                logger.error(f"DM blast failed for {sub}: {inner}")
        
        return {"success": True, "sent": sent, "failed": failed, "total": len(subs)}
    except Exception as e:
        logger.error(f"DM blast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subscribers/stats")
async def subscriber_stats():
    """Get subscriber growth and revenue stats."""
    orch = require_orch()
    try:
        result = orch.db.client.table('subscribers').select('*').execute()
        subs = result.data if hasattr(result, 'data') else []
        
        active = [s for s in subs if s.get('status') == 'active']
        expired = [s for s in subs if s.get('status') == 'expired']
        trial = [s for s in subs if s.get('status') == 'trial']
        
        # Simple revenue estimate
        monthly_revenue = sum(
            getattr(settings, 'VIP_MONTHLY_PRICE', 49) if s.get('plan') == 'monthly' else
            getattr(settings, 'VIP_QUARTERLY_PRICE', 129) / 3 if s.get('plan') == 'quarterly' else
            0 for s in active
        )
        
        return {
            "total": len(subs),
            "active": len(active),
            "expired": len(expired),
            "trial": len(trial),
            "monthly_revenue_estimate": round(monthly_revenue, 2),
            "active_percentage": round(len(active) / len(subs) * 100, 1) if subs else 0,
        }
    except Exception as e:
        logger.error(f"Subscriber stats error: {e}")
        return {"total": 0, "active": 0, "expired": 0, "trial": 0, "monthly_revenue_estimate": 0, "active_percentage": 0}


# ==================== Static Files ====================

@app.get("/")
async def root():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.get("/health")
async def health():
    """Health check endpoint for startup scripts."""
    return {"status": "ok", "dashboard": True, "port": _PORT}


@app.post("/api/test/send-signal")
async def send_test_signal():
    """Send a test signal to VIP and Free channels"""
    orch = require_orch()
    try:
        import uuid
        from src.models.signal import TradingSignal, SignalDirection, SetupType, SignalStatus, TechnicalScore, ContextScore
        
        # Create test signal
        test_signal = TradingSignal(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            direction=SignalDirection.LONG,
            setup_type=SetupType.BREAKOUT,
            timeframe="1h",
            entry_price=67500.00,
            stop_loss=66800.00,
            take_profit_1=68900.00,
            take_profit_2=69800.00,
            take_profit_3=70500.00,
            technical_score=TechnicalScore(
                structure=95,
                momentum=88,
                volume=82,
                liquidity=90,
                session_alignment=85,
                total=88
            ),
            context_score=ContextScore(
                news_sentiment=75,
                macro_trend=80,
                market_regime=70,
                total=75
            ),
            confidence=89.5,
            reasoning="🎯 **TEST SIGNAL** - Strong bullish breakout above key resistance. "
                      "Clean HTF structure with volume confirmation. R/R: 1:2.0",
            risk_reward=2.0,
            atr=850.00,
            volume_24h=28500000000,
            market_context="BTC reclaiming key support",
            news_context="Positive macro sentiment",
            status=SignalStatus.APPROVED,
            admin_approved=True,
            approved_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        # Send to VIP
        await orch.channel_publisher.publish_to_vip(test_signal)
        
        # Send teaser to Free via campaign engine
        if orch.campaign_engine:
            await orch.campaign_engine._free_channel_teaser(test_signal)
        
        return {
            "success": True,
            "message": "Test signal sent to VIP and Free channels",
            "signal_id": test_signal.id,
            "symbol": test_signal.symbol,
            "confidence": test_signal.confidence
        }
    except Exception as e:
        logger.error(f"Test signal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ENHANCED ANALYTICS ====================

@app.get("/api/analytics/performance")
async def enhanced_performance_analytics(days: int = Query(30, ge=1, le=365)):
    """Enhanced performance analytics with Sharpe ratio, time analysis, best performers"""
    orch = require_orch()
    if not analytics_engine:
        raise HTTPException(status_code=503, detail="Analytics engine not initialized")
    
    try:
        return await analytics_engine.get_performance_analytics(days)
    except Exception as e:
        logger.error(f"Enhanced analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/subscribers")
async def subscriber_analytics():
    """Subscriber lifecycle, churn, LTV, and revenue analytics"""
    orch = require_orch()
    if not analytics_engine:
        raise HTTPException(status_code=503, detail="Analytics engine not initialized")
    
    try:
        return await analytics_engine.get_subscriber_analytics()
    except Exception as e:
        logger.error(f"Subscriber analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CONTENT GENERATOR ====================

@app.get("/api/content/weekly-report")
async def generate_weekly_report():
    """Generate weekly performance report for social media"""
    orch = require_orch()
    if not content_generator:
        raise HTTPException(status_code=503, detail="Content generator not initialized")
    
    try:
        return await content_generator.generate_weekly_report()
    except Exception as e:
        logger.error(f"Weekly report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content/social-post")
async def generate_social_post(post_type: str = Query("performance")):
    """Generate social media post (performance, teaser, education)"""
    orch = require_orch()
    if not content_generator:
        raise HTTPException(status_code=503, detail="Content generator not initialized")
    
    try:
        return await content_generator.generate_social_media_post(post_type)
    except Exception as e:
        logger.error(f"Social post error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content/comparison-chart")
async def generate_comparison_chart(days: int = Query(30, ge=1, le=365)):
    """Generate performance comparison chart data"""
    orch = require_orch()
    if not content_generator:
        raise HTTPException(status_code=503, detail="Content generator not initialized")
    
    try:
        return await content_generator.generate_comparison_chart_data(days)
    except Exception as e:
        logger.error(f"Comparison chart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content/export-pdf")
async def export_signals_pdf(days: int = Query(30, ge=1, le=365)):
    """Export signal history data for PDF generation"""
    orch = require_orch()
    if not content_generator:
        raise HTTPException(status_code=503, detail="Content generator not initialized")
    
    try:
        return await content_generator.export_signals_pdf_data(days)
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FREE VIRAL MARKETING ====================

@app.post("/api/marketing/viral-daily")
async def trigger_viral_daily_marketing():
    """Trigger daily viral marketing campaign (Discord + Telegram + Forums)"""
    orch = require_orch()
    if not orch.viral_growth:
        raise HTTPException(status_code=503, detail="Viral growth engine not initialized")
    
    try:
        await orch.viral_growth.execute_daily_marketing()
        return {"success": True, "message": "Daily viral marketing executed"}
    except Exception as e:
        logger.error(f"Viral daily marketing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/marketing/viral-weekly")
async def trigger_viral_weekly_marketing():
    """Trigger weekly viral marketing blitz (Reddit + Discord + Forums)"""
    orch = require_orch()
    if not orch.viral_growth:
        raise HTTPException(status_code=503, detail="Viral growth engine not initialized")
    
    try:
        await orch.viral_growth.execute_weekly_marketing()
        return {"success": True, "message": "Weekly viral marketing blitz completed"}
    except Exception as e:
        logger.error(f"Viral weekly marketing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/marketing/reddit-post")
async def post_to_reddit():
    """Post performance report to Reddit"""
    orch = require_orch()
    if not orch.viral_growth:
        raise HTTPException(status_code=503, detail="Viral growth engine not initialized")
    
    try:
        success = await orch.viral_growth.post_to_reddit(content_type='performance')
        if success:
            return {"success": True, "message": "Posted to Reddit successfully"}
        else:
            return {"success": False, "message": "Reddit posting disabled (add REDDIT_CLIENT_ID to .env)"}
    except Exception as e:
        logger.error(f"Reddit post error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/marketing/discord-blast")
async def post_to_discord_servers():
    """Post to multiple Discord servers"""
    orch = require_orch()
    if not orch.viral_growth:
        raise HTTPException(status_code=503, detail="Viral growth engine not initialized")
    
    try:
        social_proof = await orch.viral_growth.generate_social_proof_content()
        await orch.viral_growth.post_to_multiple_discord_servers(
            "📊 Performance Update",
            social_proof
        )
        return {"success": True, "message": "Posted to Discord servers"}
    except Exception as e:
        logger.error(f"Discord blast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/marketing/forum-content")
async def generate_forum_content():
    """Generate forum post content (for manual posting)"""
    orch = require_orch()
    if not orch.viral_growth:
        raise HTTPException(status_code=503, detail="Viral growth engine not initialized")
    
    try:
        content = await orch.viral_growth.post_to_crypto_forums()
        return {"success": True, "content": content, "message": "Forum content generated"}
    except Exception as e:
        logger.error(f"Forum content error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/marketing/social-proof")
async def get_social_proof():
    """Get social proof content for sharing"""
    orch = require_orch()
    if not orch.viral_growth:
        raise HTTPException(status_code=503, detail="Viral growth engine not initialized")
    
    try:
        content = await orch.viral_growth.generate_social_proof_content()
        return {"success": True, "content": content}
    except Exception as e:
        logger.error(f"Social proof error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def start_dashboard(orch, port: int = 8080):
    """Start the admin dashboard server. Call from main.py via asyncio.create_task()"""
    global orchestrator, _PORT, analytics_engine, content_generator
    orchestrator = orch
    _PORT = port
    
    # Initialize analytics and content engines
    if orch.db:
        analytics_engine = AnalyticsEngine(orch.db)
        content_generator = ContentGenerator(orch.db)
        logger.info("📊 Analytics & Content engines initialized")
    
    import uvicorn
    from uvicorn import Config, Server
    config = Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = Server(config)
    logger.info(f"🎛️  Admin Dashboard starting on http://localhost:{port}")
    await server.serve()
