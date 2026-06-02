"""
CryptoPulse Admin Dashboard Server
FastAPI backend for full operational control.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query, Request, Body, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from src.config import settings
from src.utils.logger import get_logger
import secrets
from src.admin.analytics_engine import AnalyticsEngine
from src.admin.content_generator import ContentGenerator
from src.exchange.ctrader_client import CTraderClient
from src.exchange.mexc_client import MEXCClient
from src.utils.portfolio_analytics import PortfolioAnalytics
from src.models.signal import SignalStatus

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

logger = get_logger(__name__)

app = FastAPI(title="CryptoPulse Admin", version="2.0")

# ==================== Session Auth ====================
_sessions: Dict[str, datetime] = {}

def _generate_session() -> str:
    return secrets.token_urlsafe(32)

def _set_auth_cookie(response: Response, token: str):
    response.set_cookie(key="cp_session", value=token, httponly=True, max_age=86400*7, samesite="lax")

async def _get_session(request: Request) -> bool:
    token = request.cookies.get("cp_session")
    if token and token in _sessions:
        if _sessions[token] > datetime.utcnow():
            return True
        else:
            _sessions.pop(token, None)
    return False

def _check_basic_auth(request: Request) -> bool:
    if not settings.ADMIN_DASHBOARD_PASSWORD:
        return True
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        creds = __import__('base64').b64decode(auth[6:]).decode("utf-8")
        username, password = creds.split(":", 1)
        return secrets.compare_digest(username, "admin") and secrets.compare_digest(password, settings.ADMIN_DASHBOARD_PASSWORD)
    except Exception:
        return False

# ==================== Rate Limiting ====================
_request_log: Dict[str, List[datetime]] = {}

# Tiered limits: (window_seconds, max_requests)
TIER_STRICT = (60, 5)    # Signal creation, admin actions
TIER_MODERATE = (60, 30)  # Writes, approvals
TIER_LENIENT = (60, 120)  # Reads, analytics

def _check_rate_limit(client_ip: str, tier: tuple = TIER_MODERATE) -> bool:
    """Multi-tier in-memory rate limiter. Returns True if allowed."""
    window_seconds, max_requests = tier
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=window_seconds)
    
    key = f"{client_ip}:{tier}"
    history = _request_log.get(key, [])
    history = [t for t in history if t > window_start]
    
    if len(history) >= max_requests:
        _request_log[key] = history
        return False
    
    history.append(now)
    _request_log[key] = history
    return True

async def require_rate_limit(request: Request, tier: tuple = TIER_MODERATE):
    """FastAPI dependency for rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, tier):
        window, limit = tier
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} requests per {window}s. Please slow down."
        )

async def rate_limit_strict(request: Request):
    await require_rate_limit(request, TIER_STRICT)

async def rate_limit_moderate(request: Request):
    await require_rate_limit(request, TIER_MODERATE)

async def rate_limit_lenient(request: Request):
    await require_rate_limit(request, TIER_LENIENT)

# ==================== Authentication ====================
security = HTTPBasic(auto_error=False)

async def verify_admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify dashboard admin credentials. If no password configured, allow all."""
    if not settings.ADMIN_DASHBOARD_PASSWORD:
        return True  # Auth disabled
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Basic"})
    
    # Use secrets.compare_digest for timing attack resistance
    username_ok = secrets.compare_digest(credentials.username, "admin")
    password_ok = secrets.compare_digest(credentials.password, settings.ADMIN_DASHBOARD_PASSWORD)
    
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})
    
    return True

@app.middleware("http")
async def dashboard_auth_middleware(request: Request, call_next):
    """Protect all routes with session or Basic auth when ADMIN_DASHBOARD_PASSWORD is configured."""
    path = request.url.path
    
    # Always public routes
    public_paths = {"/login", "/api/login", "/api/public/portfolio", "/health", "/favicon.ico"}
    if path in public_paths or path.startswith("/api/public/"):
        return await call_next(request)
    
    # Skip auth if not configured (backwards compatible)
    if not settings.ADMIN_DASHBOARD_PASSWORD:
        return await call_next(request)
    
    # Check session cookie first
    if await _get_session(request):
        return await call_next(request)
    
    # Check Basic auth for API routes
    if path.startswith("/api/") and _check_basic_auth(request):
        return await call_next(request)
    
    # Not authenticated — redirect to login for HTML, 401 for API
    if path.startswith("/api/"):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": "Basic"}
        )
    
    return FileResponse(os.path.join(_STATIC_DIR, "login.html"))


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


class SignalUpdate(BaseModel):
    """Model for updating signal prices and order type"""
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    order_type: Optional[str] = None  # 'market' or 'limit'


class CloseSignal(BaseModel):
    """Model for manually closing a signal"""
    signal_id: str
    close_price: float
    reason: str  # "manual", "tp_hit", "sl_hit", "expired"


class MarkTPHit(BaseModel):
    """Model for manually marking TP as hit"""
    signal_id: str
    tp_level: int  # 1, 2, or 3


class FillLimitOrder(BaseModel):
    """Model for manually filling an approved limit order"""
    fill_price: float


class LoginRequest(BaseModel):
    """Model for dashboard login"""
    username: str
    password: str


# ==================== Helper ====================

def require_orch():
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    return orchestrator


# ==================== API Endpoints ====================

@app.get("/login")
async def login_page():
    """Serve the login page"""
    return FileResponse(os.path.join(_STATIC_DIR, "login.html"))


@app.post("/api/login")
async def api_login(request: LoginRequest, response: Response):
    """Authenticate and set session cookie"""
    if not settings.ADMIN_DASHBOARD_PASSWORD:
        return JSONResponse(status_code=403, content={"detail": "Login not configured"})
    
    username_ok = secrets.compare_digest(request.username, "admin")
    password_ok = secrets.compare_digest(request.password, settings.ADMIN_DASHBOARD_PASSWORD)
    
    if not (username_ok and password_ok):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    
    token = _generate_session()
    _sessions[token] = datetime.utcnow() + timedelta(days=7)
    _set_auth_cookie(response, token)
    return {"success": True}


@app.get("/marketing")
async def marketing_dashboard():
    """Serve the free marketing dashboard page"""
    return FileResponse(os.path.join(_STATIC_DIR, "marketing.html"))


@app.get("/portfolio")
async def portfolio_page():
    """Serve the full portfolio page with all trades and live P&L."""
    return FileResponse(os.path.join(_STATIC_DIR, "portfolio.html"))


@app.get("/public-portfolio")
async def public_portfolio_page():
    """Serve the PUBLIC portfolio page (read-only, no auth required)."""
    if not settings.PUBLIC_PORTFOLIO_ENABLED:
        return JSONResponse(
            status_code=403,
            content={"detail": "Public portfolio is disabled. Enable PUBLIC_PORTFOLIO_ENABLED in settings."}
        )
    return FileResponse(os.path.join(_STATIC_DIR, "public_portfolio.html"))


@app.get("/research")
async def research_center_page():
    """Serve the Research Center page for investment intelligence."""
    return FileResponse(os.path.join(_STATIC_DIR, "research_center.html"))


@app.get("/api/status")
async def system_status(request: Request, _=Depends(rate_limit_lenient)):
    """Overall system health and status with comprehensive component checks."""
    orch = require_orch()
    scheduler_running = orch.scheduler.running if orch.scheduler else False

    # DB connectivity test
    db_healthy = False
    try:
        if orch.db and orch.db.client:
            orch.db.client.table('signals').select('id', count='exact').limit(1).execute()
            db_healthy = True
    except Exception:
        pass

    # Scanner health
    scanner_healthy = False
    try:
        if orch.signal_engine and orch.signal_engine.scanner:
            scanner_healthy = True
    except Exception:
        pass

    # Autopilot stats
    autopilot_stats = {}
    try:
        if orch.autopilot:
            p = orch.autopilot.performance
            autopilot_stats = {
                'active_signals': len(p.active_signals) if p else 0,
                'pending_limits': len(p.pending_limit_orders) if p else 0,
                'tracking_enabled': True
            }
    except Exception:
        pass

    # Signal queue depth
    queue_depth = {'pending': 0, 'active': 0, 'approved': 0}
    try:
        if orch.db:
            pending = orch.db.client.table('signals').select('id', count='exact').eq('status', 'pending').execute()
            active = orch.db.client.table('signals').select('id', count='exact').eq('status', 'active').execute()
            approved = orch.db.client.table('signals').select('id', count='exact').eq('status', 'approved').execute()
            queue_depth = {
                'pending': getattr(pending, 'count', 0) or len(pending.data or []),
                'active': getattr(active, 'count', 0) or len(active.data or []),
                'approved': getattr(approved, 'count', 0) or len(approved.data or [])
            }
    except Exception:
        pass

    # Alpha plays stats
    alpha_stats = {}
    try:
        if orch.alpha_engine:
            alpha_stats = {
                'active': len(orch.alpha_engine.active_plays),
                'pending': len(orch.alpha_engine.pending_alpha_limits) if hasattr(orch.alpha_engine, 'pending_alpha_limits') else 0
            }
    except Exception:
        pass

    return {
        "status": "running" if db_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "scheduler": scheduler_running,
        "db_healthy": db_healthy,
        "scanner_healthy": scanner_healthy,
        "admin_bot": (orch.admin_bot.app is not None or orch.admin_bot.bot is not None) if orch.admin_bot else False,
        "vip_bot": orch.vip_bot.app is not None if orch.vip_bot else False,
        "autopilot": autopilot_stats,
        "alpha_plays": alpha_stats,
        "queue_depth": queue_depth,
        "components": {
            "signal_engine": True,
            "channel_publisher": True,
            "database": db_healthy,
            "scanner": scanner_healthy,
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
async def pending_signals(request: Request, _=Depends(rate_limit_lenient)):
    """Signals waiting for admin approval."""
    orch = require_orch()
    try:
        # Always use DB as source of truth — in-memory dict gets stale
        # when signals are approved via Telegram bot on Oracle
        pending = await orch.db.get_pending_signals()
        
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
        logger.error(f"Error getting pending signals: {e}")
        return {"count": 0, "signals": [], "error": str(e)}


@app.get("/api/signals/active")
async def active_signals(request: Request, _=Depends(rate_limit_lenient)):
    """Active/running signals being tracked (persists across restarts)."""
    orch = require_orch()
    try:
        active = await orch.db.get_active_signals()
        
        # Get current prices for P&L calculation
        signals_with_pnl = []
        for s in active:
            current_price = await orch._get_current_price(s.symbol)
            entry = s.actual_entry or s.entry_price
            
            # CRITICAL FIX: For approved limit orders that haven't filled yet,
            # show 0% PnL. Only calculate PnL once status is 'active' (limit filled)
            status_val = s.status.value if hasattr(s.status, 'value') else str(s.status)
            is_approved_limit = getattr(s, 'is_limit_order', False) and status_val == 'approved'
            
            pnl = 0
            if not is_approved_limit and current_price and entry and entry != 0:
                pnl = ((current_price - entry) / entry) * 100
                if s.direction.value == "SHORT":
                    pnl = -pnl
            
            signals_with_pnl.append({
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                "timeframe": s.timeframe,
                "setup_type": s.setup_type.value if hasattr(s.setup_type, 'value') else str(s.setup_type),
                "is_limit_order": getattr(s, 'is_limit_order', False),
                "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
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
                "stop_moved_to_breakeven": getattr(s, 'stop_moved_to_breakeven', False),
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


@app.get("/api/portfolio")
async def portfolio_data(request: Request, _=Depends(rate_limit_lenient)):
    """Full portfolio: all signals (active + closed + pending) with live P&L and aggregate stats."""
    orch = require_orch()
    try:
        all_signals = await orch.db.get_all_signals(limit=500)
        
        active_pnl_total = 0.0
        closed_pnl_total = 0.0
        wins = 0
        losses = 0
        portfolio_items = []
        
        for s in all_signals:
            entry = s.actual_entry or s.entry_price or 0
            status = getattr(s, 'status', None)
            status_val = status.value if hasattr(status, 'value') else str(status) if status else 'unknown'
            
            # Calculate P&L
            pnl = 0.0
            current_price = None
            
            if status_val == 'active':
                # Live P&L for active trades (entry has been hit)
                current_price = await orch._get_current_price(s.symbol)
                if current_price and entry and entry != 0:
                    pnl = ((current_price - entry) / entry) * 100
                    if s.direction.value == "SHORT":
                        pnl = -pnl
                active_pnl_total += pnl
            elif status_val == 'approved':
                # Approved but not yet triggered (limit orders waiting for fill)
                current_price = await orch._get_current_price(s.symbol)
                pnl = 0.0  # No P&L until entry is hit
            elif status_val == 'closed':
                # Realized P&L for closed trades
                pnl = getattr(s, 'pnl_percent', 0) or 0
                current_price = s.actual_exit or entry
                closed_pnl_total += pnl
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
            
            portfolio_items.append({
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                "timeframe": s.timeframe,
                "status": status_val,
                "entry_price": entry,
                "current_price": current_price,
                "actual_exit": getattr(s, 'actual_exit', None),
                "stop_loss": s.stop_loss,
                "take_profit_1": s.take_profit_1,
                "take_profit_2": s.take_profit_2,
                "take_profit_3": s.take_profit_3,
                "pnl_percent": round(pnl, 2),
                "confidence": s.confidence,
                "risk_reward": s.risk_reward,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "closed_at": getattr(s, 'closed_at', None).isoformat() if getattr(s, 'closed_at', None) else None,
                "tp1_hit": getattr(s, 'tp1_hit', False),
                "tp2_hit": getattr(s, 'tp2_hit', False),
                "tp3_hit": getattr(s, 'tp3_hit', False),
                "cancellation_reason": getattr(s, 'cancellation_reason', None),
            })
        
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        total_pnl = active_pnl_total + closed_pnl_total
        
        return {
            "count": len(portfolio_items),
            "active_count": sum(1 for p in portfolio_items if p['status'] == 'active'),
            "pending_entry_count": sum(1 for p in portfolio_items if p['status'] == 'approved'),
            "closed_count": sum(1 for p in portfolio_items if p['status'] == 'closed'),
            "pending_count": sum(1 for p in portfolio_items if p['status'] == 'pending'),
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "active_pnl": round(active_pnl_total, 2),
            "closed_pnl": round(closed_pnl_total, 2),
            "total_pnl": round(total_pnl, 2),
            "signals": portfolio_items
        }
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return {"count": 0, "signals": [], "error": str(e)}


@app.get("/api/public/portfolio")
async def public_portfolio_data(request: Request, _=Depends(rate_limit_lenient)):
    """
    PUBLIC read-only portfolio endpoint (no auth required).
    Returns closed trades only - no active positions or sensitive data.
    """
    if not settings.PUBLIC_PORTFOLIO_ENABLED:
        return JSONResponse(
            status_code=403,
            content={"detail": "Public portfolio is disabled", "enabled": False}
        )
    
    orch = require_orch()
    try:
        all_signals = await orch.db.get_all_signals(limit=500)
        
        closed_items = []
        wins = 0
        losses = 0
        
        for s in all_signals:
            status = getattr(s, 'status', None)
            status_val = status.value if hasattr(status, 'value') else str(status) if status else 'unknown'
            
            # Only include closed trades in public view
            if status_val != 'closed':
                continue
            
            pnl = getattr(s, 'pnl_percent', 0) or 0
            entry = s.actual_entry or s.entry_price or 0
            
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            
            closed_items.append({
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction.value if hasattr(s.direction, 'value') else str(s.direction),
                "timeframe": s.timeframe,
                "status": status_val,
                "entry_price": entry,
                "actual_exit": getattr(s, 'actual_exit', None),
                "stop_loss": s.stop_loss,
                "take_profit_1": s.take_profit_1,
                "take_profit_2": s.take_profit_2,
                "take_profit_3": s.take_profit_3,
                "pnl_percent": round(pnl, 2),
                "confidence": s.confidence,
                "risk_reward": s.risk_reward,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "closed_at": getattr(s, 'closed_at', None).isoformat() if getattr(s, 'closed_at', None) else None,
                "tp1_hit": getattr(s, 'tp1_hit', False),
                "tp2_hit": getattr(s, 'tp2_hit', False),
                "tp3_hit": getattr(s, 'tp3_hit', False),
                "cancellation_reason": getattr(s, 'cancellation_reason', None),
            })
        
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        total_pnl = sum(p['pnl_percent'] for p in closed_items)
        
        return {
            "enabled": True,
            "count": len(closed_items),
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "signals": closed_items
        }
    except Exception as e:
        logger.error(f"Error getting public portfolio: {e}")
        return {"enabled": True, "count": 0, "signals": [], "error": str(e)}


@app.get("/api/account")
async def account_data():
    """Fetch live account data from cTrader (BEM Funding) and MEXC (personal)."""
    accounts = []
    
    # cTrader / BEM Funding (skip if placeholder values)
    if (settings.CTRADER_ACCESS_TOKEN and settings.CTRADER_ACCOUNT_ID and 
        "your_account_id_here" not in settings.CTRADER_ACCOUNT_ID.lower() and
        "placeholder" not in settings.CTRADER_ACCOUNT_ID.lower()):
        try:
            client = CTraderClient(
                access_token=settings.CTRADER_ACCESS_TOKEN,
                account_id=settings.CTRADER_ACCOUNT_ID,
                server=settings.CTRADER_SERVER,
            )
            data = await client.get_all_data()
            await client.close()
            accounts.append(data)
        except Exception as e:
            logger.debug(f"cTrader account fetch failed: {e}")  # Changed to debug to reduce noise
    
    # MEXC Personal (skip if placeholder/invalid values)
    if (settings.MEXC_API_KEY and settings.MEXC_API_SECRET and
        len(settings.MEXC_API_KEY) > 10 and len(settings.MEXC_API_SECRET) > 10 and
        "your_api" not in settings.MEXC_API_KEY.lower() and
        "placeholder" not in settings.MEXC_API_KEY.lower()):
        try:
            client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
            )
            data = await client.get_all_data()
            await client.close()
            accounts.append(data)
        except Exception as e:
            logger.error(f"MEXC account fetch failed: {e}")
            accounts.append({
                "source": "mexc",
                "label": "MEXC Personal",
                "error": str(e),
            })
    
    return {
        "accounts": accounts,
        "connected_count": sum(1 for a in accounts if "error" not in a),
    }


# ==================== ALPHA/DEX PLAYS ENDPOINTS ====================

@app.get("/api/alpha/plays")
async def alpha_plays():
    """Get alpha/DEX plays (pending, active, or completed)."""
    orch = require_orch()
    try:
        active = []
        pending = []
        
        # Primary: read from in-memory alpha engine (when bot is running)
        if orch.alpha_engine:
            for play_id, play in list(orch.alpha_engine.active_plays.items()):
                # Skip corrupted legacy plays with no real data
                if (not play.entry_price or play.entry_price <= 0) and (not play.stop_loss or play.stop_loss <= 0) and (not play.take_profit_1 or play.take_profit_1 <= 0):
                    continue
                if orch.alpha_engine._looks_like_address_fragment(play.candidate.symbol) and not play.candidate.token_address:
                    continue
                # Try to re-enrich bad symbols before displaying
                symbol = play.candidate.symbol
                name = play.candidate.name
                if orch.alpha_engine._looks_like_address_fragment(symbol) and play.candidate.token_address:
                    try:
                        await orch.alpha_engine._enrich_token_info(play.candidate)
                        symbol = play.candidate.symbol
                        name = play.candidate.name
                    except Exception:
                        pass
                
                # Build display name: prefer real name, then symbol, then UNKNOWN
                display_name = name if name and not orch.alpha_engine._looks_like_address_fragment(name) else symbol
                if orch.alpha_engine._looks_like_address_fragment(display_name):
                    display_name = name or symbol or "UNKNOWN"
                
                # Fetch live price on-demand if not yet tracked
                current_price = play.current_price
                current_pnl = play.current_pnl
                if current_price == 0 and play.candidate.token_address:
                    try:
                        fetched = await orch.alpha_engine._get_current_price(play.candidate)
                        if fetched and fetched > 0:
                            current_price = fetched
                            if play.entry_price > 0:
                                current_pnl = ((current_price - play.entry_price) / play.entry_price) * 100
                            play.current_price = current_price
                            play.current_pnl = current_pnl
                    except Exception as e:
                        logger.debug(f"On-demand price fetch failed for {symbol}: {e}")
                
                active.append({
                    "id": play_id,
                    "symbol": symbol,
                    "name": name,
                    "display_name": display_name,
                    "chain": play.candidate.chain,
                    "status": play.status,
                    "trade_type": play.candidate.trade_type,
                    "risk_level": play.candidate.risk_level,
                    "time_frame": play.candidate.time_frame,
                    "entry_price": play.entry_price,
                    "current_price": current_price if current_price > 0 else play.candidate.price_usd,
                    "current_pnl": round(current_pnl, 2),
                    "stop_loss": play.stop_loss,
                    "take_profit_1": play.take_profit_1,
                    "take_profit_2": play.take_profit_2,
                    "market_cap": play.candidate.market_cap_usd,
                    "volume_24h": play.candidate.volume_24h,
                    "liquidity": play.candidate.liquidity_usd,
                    "price_change_24h": round(play.candidate.price_change_24h, 1),
                    "price_change_1h": round(play.candidate.price_change_1h, 1),
                    "price_change_5min": round(play.candidate.price_change_5min, 1),
                    "buy_sell_ratio": round(play.candidate.buy_sell_ratio, 2),
                    "overall_score": round(play.candidate.overall_score, 1),
                    "catalyst": play.candidate.catalyst,
                    "narrative": play.candidate.narrative,
                    "why_trending": play.candidate.why_trending,
                    "short_term_potential": play.candidate.short_term_potential,
                    "long_term_potential": play.candidate.long_term_potential,
                    "dex_url": play.candidate.dex_url,
                    "chart_url": play.candidate.chart_url,
                    "buy_url": play.candidate.buy_url,
                    "red_flags": play.candidate.red_flags,
                    "dex_source": play.candidate.dex_source,
                    "approved_at": play.approved_at.isoformat() if play.approved_at else None,
                    "position_size": play.position_size,
                })
            
            for symbol, candidate in orch.alpha_engine.pending_plays.items():
                pending.append({
                    "symbol": symbol,
                    "name": candidate.name,
                    "chain": candidate.chain,
                    "token_address": candidate.token_address,
                    "price_usd": candidate.price_usd,
                    "trade_type": candidate.trade_type,
                    "risk_level": candidate.risk_level,
                    "time_frame": candidate.time_frame,
                    "market_cap": candidate.market_cap_usd,
                    "volume_24h": candidate.volume_24h,
                    "liquidity": candidate.liquidity_usd,
                    "price_change_24h": round(candidate.price_change_24h, 1),
                    "price_change_1h": round(candidate.price_change_1h, 1),
                    "buy_sell_ratio": round(candidate.buy_sell_ratio, 2),
                    "overall_score": round(candidate.overall_score, 1),
                    "catalyst": candidate.catalyst,
                    "narrative": candidate.narrative,
                    "why_trending": candidate.why_trending,
                    "short_term_potential": candidate.short_term_potential,
                    "long_term_potential": candidate.long_term_potential,
                    "red_flags": candidate.red_flags,
                    "dex_url": candidate.dex_url,
                    "chart_url": candidate.chart_url,
                    "buy_url": candidate.buy_url,
                    "dex_source": candidate.dex_source,
                })
        else:
            # Fallback: read from database when alpha engine not initialized (dashboard-only mode)
            try:
                import json
                db_plays = await orch.db.get_alpha_plays(status=None, limit=100)
                for p in db_plays:
                    cd = p.get('candidate_data')
                    candidate = {}
                    if cd:
                        try:
                            candidate = json.loads(cd) if isinstance(cd, str) else cd
                        except Exception:
                            pass
                    status = p.get('status', 'active')
                    
                    def _val(field, default=0):
                        """Get value from DB row or candidate, preserving falsy numeric values like 0.0."""
                        v = p.get(field)
                        if v is not None:
                            return v
                        v = candidate.get(field)
                        if v is not None:
                            return v
                        return default
                    
                    play_obj = {
                        "id": p.get('id'),
                        "symbol": p.get('symbol') or candidate.get('symbol', 'UNKNOWN'),
                        "name": p.get('name') or candidate.get('name', ''),
                        "chain": p.get('chain') or candidate.get('chain', 'unknown'),
                        "status": status,
                        "trade_type": candidate.get('trade_type', ''),
                        "risk_level": candidate.get('risk_level', 'unknown'),
                        "time_frame": candidate.get('time_frame', ''),
                        "entry_price": _val('entry_price', 0),
                        "current_price": _val('current_price', 0),
                        "current_pnl": round(float(_val('current_pnl', 0)), 2),
                        "stop_loss": _val('stop_loss', 0),
                        "take_profit_1": _val('take_profit_1', 0),
                        "take_profit_2": _val('take_profit_2', 0),
                        "position_size": _val('position_size', '2-5%'),
                        "market_cap": float(candidate.get('market_cap', 0) or 0),
                        "volume_24h": float(candidate.get('volume_24h', 0) or 0),
                        "liquidity": float(candidate.get('liquidity_usd', 0) or 0),
                        "price_change_24h": round(float(candidate.get('price_change_24h', 0) or 0), 1),
                        "price_change_1h": round(float(candidate.get('price_change_1h', 0) or 0), 1),
                        "price_change_5min": round(float(candidate.get('price_change_5min', 0) or 0), 1),
                        "buy_sell_ratio": round(float(candidate.get('buy_sell_ratio', 1) or 1), 2),
                        "overall_score": round(float(candidate.get('overall_score', 0) or 0), 1),
                        "catalyst": candidate.get('catalyst', ''),
                        "narrative": candidate.get('narrative', ''),
                        "why_trending": candidate.get('why_trending', ''),
                        "short_term_potential": candidate.get('short_term_potential', ''),
                        "long_term_potential": candidate.get('long_term_potential', ''),
                        "dex_url": candidate.get('dex_url', ''),
                        "chart_url": candidate.get('chart_url', ''),
                        "buy_url": candidate.get('buy_url', ''),
                        "red_flags": candidate.get('red_flags', []),
                        "dex_source": candidate.get('dex_source', ''),
                        "approved_at": p.get('approved_at'),
                    }
                    if status == 'pending':
                        pending.append(play_obj)
                    elif status in ('active', 'tp1_hit', 'tp2_hit'):
                        active.append(play_obj)
            except Exception as e:
                logger.warning(f"Could not load alpha plays from DB fallback: {e}")
        
        return {
            "active_count": len(active),
            "pending_count": len(pending),
            "active": active,
            "pending": pending
        }
    except Exception as e:
        logger.error(f"Error getting alpha plays: {e}")
        return {"active_count": 0, "pending_count": 0, "active": [], "pending": [], "error": str(e)}


@app.get("/api/alpha/portfolio")
async def alpha_portfolio_holds():
    """Get long-term portfolio holds (1-4 week positions)."""
    orch = require_orch()
    try:
        holds = []
        
        if orch.alpha_engine:
            for play_id, play in list(orch.alpha_engine.portfolio_holds.items()):
                current_price = play.current_price if play.current_price > 0 else play.candidate.price_usd
                entry = play.actual_entry or play.entry_price
                current_pnl = play.current_pnl
                if current_pnl == 0 and entry > 0 and current_price > 0:
                    current_pnl = ((current_price - entry) / entry) * 100
                
                holds.append({
                    "id": play_id,
                    "symbol": play.candidate.symbol,
                    "name": play.candidate.name,
                    "chain": play.candidate.chain,
                    "status": play.status,
                    "trade_type": play.candidate.trade_type,
                    "risk_level": play.candidate.risk_level,
                    "entry_price": entry,
                    "current_price": current_price,
                    "current_pnl": round(current_pnl, 2),
                    "highest_price": play.highest_price or entry,
                    "stop_loss": play.stop_loss,
                    "take_profit_1": play.take_profit_1,
                    "take_profit_2": play.take_profit_2,
                    "market_cap": play.candidate.market_cap_usd,
                    "liquidity": play.candidate.liquidity_usd,
                    "volume_24h": play.candidate.volume_24h,
                    "price_change_24h": round(play.candidate.price_change_24h, 1),
                    "buy_sell_ratio": round(play.candidate.buy_sell_ratio, 2),
                    "overall_score": round(play.candidate.overall_score, 1),
                    "catalyst": play.candidate.catalyst,
                    "narrative": play.candidate.narrative,
                    "dex_url": play.candidate.dex_url,
                    "chart_url": play.candidate.chart_url,
                    "approved_at": play.approved_at.isoformat() if play.approved_at else None,
                    "position_size": play.position_size,
                })
        else:
            # Fallback from DB
            try:
                db_holds = await orch.db.get_alpha_plays(status='portfolio_hold', limit=50)
                for p in db_holds:
                    cd = p.get('candidate_data', {}) or {}
                    if isinstance(cd, str):
                        import json
                        try:
                            cd = json.loads(cd)
                        except Exception:
                            cd = {}
                    entry = float(p.get('actual_entry', p.get('entry_price', 0)) or 0)
                    current = float(p.get('current_price', 0) or 0)
                    pnl = float(p.get('current_pnl', 0) or 0)
                    if pnl == 0 and entry > 0 and current > 0:
                        pnl = ((current - entry) / entry) * 100
                    holds.append({
                        "id": p.get('id'),
                        "symbol": p.get('symbol') or cd.get('symbol', 'UNKNOWN'),
                        "name": cd.get('name', ''),
                        "chain": cd.get('chain', 'unknown'),
                        "status": p.get('status', 'portfolio_hold'),
                        "trade_type": cd.get('trade_type', 'portfolio'),
                        "entry_price": entry,
                        "current_price": current,
                        "current_pnl": round(pnl, 2),
                        "stop_loss": float(p.get('stop_loss', 0) or 0),
                        "take_profit_1": float(p.get('take_profit_1', 0) or 0),
                        "take_profit_2": float(p.get('take_profit_2', 0) or 0),
                        "market_cap": float(cd.get('market_cap', 0) or 0),
                        "approved_at": p.get('approved_at'),
                    })
            except Exception as e:
                logger.warning(f"Could not load portfolio holds from DB: {e}")
        
        # Compute aggregate stats
        total_pnl = sum(h['current_pnl'] for h in holds)
        best = max(holds, key=lambda x: x['current_pnl']) if holds else None
        worst = min(holds, key=lambda x: x['current_pnl']) if holds else None
        
        return {
            "count": len(holds),
            "total_pnl": round(total_pnl, 2),
            "best_performer": best,
            "worst_performer": worst,
            "holds": holds
        }
    except Exception as e:
        logger.error(f"Error getting portfolio holds: {e}")
        return {"count": 0, "total_pnl": 0, "holds": [], "error": str(e)}


@app.post("/api/alpha/approve")
async def approve_alpha(request: Request, symbol: str, is_limit_order: bool = False,
                        _=Depends(rate_limit_strict)):
    """Approve a pending alpha/DEX play from dashboard."""
    orch = require_orch()
    try:
        if not orch.alpha_engine:
            return {"success": False, "error": "Alpha engine not initialized"}
        
        play = await orch.alpha_engine.approve_play(symbol, is_limit_order=is_limit_order)
        if play:
            # Enrich token info BEFORE publishing to avoid "UNKNOWN" symbols
            await orch.alpha_engine._enrich_token_info(play.candidate)
            
            if not play.is_limit_order:
                await orch.alpha_engine.publish_to_vip(play)
                await orch.alpha_engine.publish_teaser_to_free(play)
            else:
                logger.info(f"Alpha limit order {symbol} approved from dashboard — waiting for entry hit")
            
            return {
                "success": True,
                "play_id": play.id,
                "symbol": symbol,
                "trade_type": play.candidate.trade_type,
                "risk_level": play.candidate.risk_level,
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


@app.post("/api/alpha/reject")
async def reject_alpha(request: Request, symbol: str,
                       _=Depends(rate_limit_strict)):
    """Reject (discard) a pending alpha/DEX play from dashboard."""
    orch = require_orch()
    try:
        if orch.alpha_engine:
            candidate = orch.alpha_engine.pending_plays.pop(symbol, None)
            if candidate:
                # Also mark DB row as rejected so it doesn't reappear on restart
                if orch.db:
                    try:
                        orch.db.client.table('alpha_plays').update({'status': 'rejected'}).eq('symbol', symbol).eq('status', 'pending').execute()
                    except Exception:
                        pass
                return {"success": True, "symbol": symbol, "message": f"Alpha play {symbol} rejected and removed"}
            else:
                return {"success": False, "error": f"Alpha play {symbol} not found in pending queue"}
        else:
            # Fallback: update DB directly when alpha engine not initialized (dashboard-only mode)
            if orch.db:
                try:
                    # Find pending play by symbol, update by its ID
                    result = orch.db.client.table('alpha_plays').select('id').eq('symbol', symbol).eq('status', 'pending').limit(1).execute()
                    if result.data:
                        play_id = result.data[0]['id']
                        await orch.db.update_alpha_play(play_id, {'status': 'rejected'})
                except Exception:
                    pass
            return {"success": True, "symbol": symbol, "message": f"Alpha play {symbol} rejected via DB"}
    except Exception as e:
        logger.error(f"Error rejecting alpha play: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/alpha/close")
async def close_alpha(request: Request, play_id: str, reason: str = "manual",
                      _=Depends(rate_limit_strict)):
    """Manually close an active alpha play from dashboard."""
    orch = require_orch()
    try:
        if orch.alpha_engine:
            result = await orch.alpha_engine.close_play(play_id, reason=reason)
            if result:
                return {"success": True, "play_id": play_id, "message": f"Alpha play {play_id} closed"}
            else:
                return {"success": False, "error": f"Alpha play {play_id} not found or already closed"}
        else:
            # Fallback: update DB directly when alpha engine not initialized (dashboard-only mode)
            from datetime import datetime
            await orch.db.update_alpha_play(play_id, {
                'status': 'closed',
                'closed_at': datetime.utcnow().isoformat(),
            })
            return {"success": True, "play_id": play_id, "message": f"Alpha play {play_id} closed via DB"}
    except Exception as e:
        logger.error(f"Error closing alpha play: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/alpha/update")
async def update_alpha(play_id: str, updates: dict = Body(...)):
    """Update an active alpha play's parameters (SL, TP, entry, position size)."""
    orch = require_orch()
    try:
        if orch.alpha_engine:
            result = await orch.alpha_engine.update_play(play_id, updates)
            if result:
                return {"success": True, "play_id": play_id, "message": f"Alpha play {play_id} updated", "updates": updates}
            else:
                return {"success": False, "error": f"Alpha play {play_id} not found"}
        else:
            # Fallback: update DB directly when alpha engine not initialized (dashboard-only mode)
            await orch.db.update_alpha_play(play_id, updates)
            return {"success": True, "play_id": play_id, "message": f"Alpha play {play_id} updated via DB", "updates": updates}
    except Exception as e:
        logger.error(f"Error updating alpha play: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/alpha/trigger")
async def trigger_alpha_scan(request: Request, chain: str = None,
                             _=Depends(rate_limit_strict)):
    """Manually trigger an alpha/DEX play discovery scan."""
    orch = require_orch()
    try:
        if not orch.alpha_engine:
            return {"success": False, "error": "Alpha engine not initialized"}
        
        asyncio.create_task(orch.alpha_engine.discover_and_create(chain=chain, limit=5))
        
        return {"success": True, "message": f"DEX scan triggered (chain={chain or 'all'}). Check logs for results."}
    except Exception as e:
        logger.error(f"Error triggering alpha scan: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/alpha/stats")
async def alpha_stats():
    """Get alpha/DEX plays statistics."""
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
        
        # Count trade types in pending
        trade_types = {}
        if orch.alpha_engine.pending_plays:
            for c in orch.alpha_engine.pending_plays.values():
                tt = c.trade_type or 'unknown'
                trade_types[tt] = trade_types.get(tt, 0) + 1
        
        return {
            "vip_daily_count": orch.alpha_engine.vip_count_today,
            "free_weekly_count": orch.alpha_engine.free_count_this_week,
            "vip_daily_limit": orch.alpha_engine.vip_daily_limit,
            "free_weekly_limit": orch.alpha_engine.free_weekly_limit,
            "active_plays": len(orch.alpha_engine.active_plays),
            "pending_plays": len(orch.alpha_engine.pending_plays),
            "trade_type_breakdown": trade_types,
            "enabled": True
        }
    except Exception as e:
        logger.error(f"Error getting alpha stats: {e}")
        return {"error": str(e)}


@app.get("/api/whales/{symbol}")
async def get_whale_activity(symbol: str):
    """Get whale activity for a symbol (free via Binance public API)."""
    orch = require_orch()
    try:
        if orch.signal_engine and orch.signal_engine.context_engine:
            whale = await orch.signal_engine.context_engine.whale_monitor.check_symbol(symbol)
            if whale and whale.alerts:
                return {
                    "symbol": symbol,
                    "active": True,
                    "total_buys_usd": round(whale.total_buys_usd, 2),
                    "total_sells_usd": round(whale.total_sells_usd, 2),
                    "net_flow_usd": round(whale.net_flow_usd, 2),
                    "buy_count": whale.buy_count,
                    "sell_count": whale.sell_count,
                    "largest_trade_usd": round(whale.largest_single_trade_usd, 2),
                    "is_accumulating": whale.is_accumulating,
                    "is_distributing": whale.is_distributing,
                    "alerts": [
                        {
                            "side": a.side,
                            "usd_value": round(a.usd_value, 2),
                            "quantity": a.quantity,
                            "price": a.price,
                            "time": a.timestamp.isoformat() if a.timestamp else None
                        }
                        for a in whale.alerts[:10]
                    ]
                }
        return {"symbol": symbol, "active": False, "message": "No whale activity detected"}
    except Exception as e:
        logger.error(f"Error fetching whale data for {symbol}: {e}")
        return {"symbol": symbol, "active": False, "error": str(e)}


@app.get("/api/alpha/performance")
async def alpha_performance(days: int = 90):
    """Get alpha play performance analytics from DB."""
    orch = require_orch()
    try:
        plays = await orch.db.get_alpha_plays(status=None, limit=500)
        if not plays:
            return {
                "total_plays": 0, "win_rate": 0, "big_win_rate": 0,
                "avg_pnl": 0, "avg_hold_hours": 0, "best_play": None, "worst_play": None,
                "by_chain": {}, "by_trade_type": {}, "by_risk": {},
                "history": [], "active": []
            }
        
        from datetime import datetime
        import json
        
        valid_plays = []
        for p in plays:
            cd = p.get('candidate_data')
            entry_price = p.get('entry_price')
            symbol = p.get('symbol', '')
            # Skip obviously broken records: no candidate_data, no entry_price, and symbol looks like a UUID fragment
            if not cd and not entry_price:
                continue
            if not cd and (not symbol or len(symbol) < 2 or symbol in ('UNKNOWN', 'unknown', '')):
                continue
            valid_plays.append(p)
        
        total = len(valid_plays)
        wins = 0
        big_wins = 0
        losses = 0
        pnls = []
        hold_hours = []
        history = []
        active_plays = []
        by_chain = {}
        by_trade_type = {}
        by_risk = {}
        best = None
        worst = None
        
        if not valid_plays:
            return {
                "total_plays": 0, "win_rate": 0, "big_win_rate": 0,
                "avg_pnl": 0, "avg_hold_hours": 0, "best_play": None, "worst_play": None,
                "by_chain": {}, "by_trade_type": {}, "by_risk": {},
                "history": [], "active": [], "message": "No valid alpha play data yet. Plays will appear once alpha scans discover and approve candidates."
            }
        
        for p in valid_plays:
            status = p.get('status', 'active')
            
            # Parse candidate_data for extra metadata
            meta = {}
            cd = p.get('candidate_data')
            if cd:
                try:
                    cdict = json.loads(cd) if isinstance(cd, str) else cd
                    meta = cdict.pop('__play_meta__', {}) if isinstance(cdict, dict) else {}
                except Exception:
                    pass
            
            entry = float(meta.get('entry_price') or p.get('entry_price') or 0)
            current_pnl = float(meta.get('current_pnl') or p.get('current_pnl') or 0)
            chain = p.get('chain', 'unknown')
            trade_type = p.get('trade_type', 'unknown')
            risk_level = p.get('risk_level', 'unknown')
            symbol = p.get('symbol', 'UNKNOWN')
            
            # Determine outcome
            outcome = 'active'
            pnl = current_pnl
            if status == 'tp2_hit':
                outcome = 'tp2_hit'
                wins += 1
                big_wins += 1
                # Estimate PnL from TP2
                tp2 = float(meta.get('take_profit_2') or p.get('take_profit_2') or 0)
                if entry > 0 and tp2 > 0:
                    pnl = round(((tp2 - entry) / entry) * 100, 2)
            elif status == 'tp1_hit':
                outcome = 'tp1_hit'
                wins += 1
                tp1 = float(meta.get('take_profit_1') or p.get('take_profit_1') or 0)
                if entry > 0 and tp1 > 0:
                    pnl = round(((tp1 - entry) / entry) * 100, 2)
            elif status == 'sl_hit':
                outcome = 'sl_hit'
                losses += 1
                sl = float(meta.get('stop_loss') or p.get('stop_loss') or 0)
                if entry > 0 and sl > 0:
                    pnl = round(((sl - entry) / entry) * 100, 2)
            elif status == 'closed':
                if pnl >= 0:
                    outcome = 'win'
                    wins += 1
                else:
                    outcome = 'loss'
                    losses += 1
            elif status == 'active' or status == 'pending':
                active_plays.append({
                    "symbol": symbol,
                    "chain": chain,
                    "status": status,
                    "entry_price": entry,
                    "current_pnl": pnl,
                    "trade_type": trade_type,
                    "risk_level": risk_level,
                    "approved_at": meta.get('approved_at') or (p.get('approved_at') if isinstance(p.get('approved_at'), str) else None),
                })
                continue
            
            # Hold time calculation
            approved_str = meta.get('approved_at') or (p.get('approved_at') if isinstance(p.get('approved_at'), str) else None)
            closed_str = meta.get('closed_at') or (p.get('closed_at') if isinstance(p.get('closed_at'), str) else None)
            hold_h = None
            if approved_str and closed_str:
                try:
                    a = datetime.fromisoformat(approved_str.replace('Z', '+00:00'))
                    c = datetime.fromisoformat(closed_str.replace('Z', '+00:00'))
                    hold_h = round((c - a).total_seconds() / 3600, 1)
                    hold_hours.append(hold_h)
                except Exception:
                    pass
            
            # Track PnL
            pnls.append(pnl)
            
            # Best / Worst
            if best is None or pnl > best['pnl']:
                best = {"symbol": symbol, "pnl": pnl, "outcome": outcome, "chain": chain}
            if worst is None or pnl < worst['pnl']:
                worst = {"symbol": symbol, "pnl": pnl, "outcome": outcome, "chain": chain}
            
            # Aggregate by dimensions
            def _agg(bucket, key):
                entry = bucket.setdefault(key, {"count": 0, "wins": 0, "losses": 0, "pnl_sum": 0})
                entry["count"] += 1
                if outcome in ('tp1_hit', 'tp2_hit', 'win'):
                    entry["wins"] += 1
                elif outcome in ('sl_hit', 'loss'):
                    entry["losses"] += 1
                entry["pnl_sum"] += pnl
            
            _agg(by_chain, chain)
            _agg(by_trade_type, trade_type)
            _agg(by_risk, risk_level)
            
            history.append({
                "symbol": symbol,
                "chain": chain,
                "outcome": outcome,
                "pnl": pnl,
                "entry_price": entry,
                "hold_hours": hold_h,
                "trade_type": trade_type,
                "risk_level": risk_level,
                "approved_at": approved_str,
                "closed_at": closed_str,
            })
        
        closed_count = wins + losses
        return {
            "total_plays": total,
            "closed_count": closed_count,
            "win_rate": round((wins / closed_count) * 100, 1) if closed_count else 0,
            "big_win_rate": round((big_wins / closed_count) * 100, 1) if closed_count else 0,
            "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
            "avg_hold_hours": round(sum(hold_hours) / len(hold_hours), 1) if hold_hours else 0,
            "best_play": best,
            "worst_play": worst,
            "by_chain": {k: {"count": v["count"], "win_rate": round((v["wins"]/v["count"])*100,1) if v["count"] else 0, "avg_pnl": round(v["pnl_sum"]/v["count"],2) if v["count"] else 0} for k,v in by_chain.items()},
            "by_trade_type": {k: {"count": v["count"], "win_rate": round((v["wins"]/v["count"])*100,1) if v["count"] else 0, "avg_pnl": round(v["pnl_sum"]/v["count"],2) if v["count"] else 0} for k,v in by_trade_type.items()},
            "by_risk": {k: {"count": v["count"], "win_rate": round((v["wins"]/v["count"])*100,1) if v["count"] else 0, "avg_pnl": round(v["pnl_sum"]/v["count"],2) if v["count"] else 0} for k,v in by_risk.items()},
            "history": history,
            "active": active_plays,
        }
    except Exception as e:
        logger.error(f"Error getting alpha performance: {e}")
        return {"error": str(e)}


@app.get("/api/dex/opportunities")
async def dex_opportunities(chain: str = None, trade_type: str = None):
    """
    Get current DEX opportunities with filtering.
    Returns pending alpha plays filtered by chain and trade type.
    """
    orch = require_orch()
    try:
        if not orch.alpha_engine:
            return {"opportunities": [], "count": 0, "enabled": False}
        
        opportunities = []
        for symbol, candidate in orch.alpha_engine.pending_plays.items():
            # Filter by chain
            if chain and candidate.chain != chain:
                continue
            # Filter by trade type
            if trade_type and candidate.trade_type != trade_type:
                continue
            
            opportunities.append({
                "symbol": symbol,
                "name": candidate.name,
                "chain": candidate.chain,
                "trade_type": candidate.trade_type,
                "risk_level": candidate.risk_level,
                "time_frame": candidate.time_frame,
                "price_usd": candidate.price_usd,
                "market_cap": candidate.market_cap_usd,
                "volume_24h": candidate.volume_24h,
                "liquidity": candidate.liquidity_usd,
                "price_change_24h": round(candidate.price_change_24h, 1),
                "price_change_1h": round(candidate.price_change_1h, 1),
                "buy_sell_ratio": round(candidate.buy_sell_ratio, 2),
                "overall_score": round(candidate.overall_score, 1),
                "catalyst": candidate.catalyst,
                "narrative": candidate.narrative,
                "why_trending": candidate.why_trending,
                "short_term_potential": candidate.short_term_potential,
                "long_term_potential": candidate.long_term_potential,
                "red_flags": candidate.red_flags,
                "dex_url": candidate.dex_url,
                "chart_url": candidate.chart_url,
                "buy_url": candidate.buy_url,
                "dex_source": candidate.dex_source,
            })
        
        # Sort by overall score
        opportunities.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return {
            "opportunities": opportunities,
            "count": len(opportunities),
            "filters": {"chain": chain, "trade_type": trade_type},
            "enabled": True
        }
    except Exception as e:
        logger.error(f"Error getting DEX opportunities: {e}")
        return {"opportunities": [], "count": 0, "error": str(e)}


# ==================== SIGNALS ====================

@app.post("/api/signals/action")
async def signal_action(action: SignalAction, request: Request,
                        _=Depends(rate_limit_strict)):
    """Approve or reject a pending signal from the dashboard."""
    orch = require_orch()
    signal = orch.admin_bot.pending_signals.get(action.signal_id)
    
    # If not in memory, try loading from database
    if not signal:
        try:
            all_signals = await orch.db.get_pending_signals()
            for s in all_signals:
                if str(s.id) == str(action.signal_id):
                    signal = s
                    orch.admin_bot.pending_signals[signal.id] = signal
                    break
        except Exception as e:
            logger.warning(f"Could not load signal from DB: {e}")
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    if action.action == "approve":
        if action.signal_id in orch.admin_bot.pending_signals:
            del orch.admin_bot.pending_signals[action.signal_id]
        await orch.on_signal_approved(signal)
        return {"success": True, "message": f"Signal {action.signal_id} approved"}
    elif action.action == "reject":
        if action.signal_id in orch.admin_bot.pending_signals:
            del orch.admin_bot.pending_signals[action.signal_id]
        await orch.on_signal_rejected(signal)
        return {"success": True, "message": f"Signal {action.signal_id} rejected"}
    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")


@app.put("/api/signals/{signal_id}/update")
async def update_signal_prices(signal_id: str, update: SignalUpdate,
                               request: Request, _=Depends(rate_limit_moderate)):
    """Update signal entry, SL, or TP prices manually"""
    orch = require_orch()
    try:
        # Get the signal
        signal = await orch.db.get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Build update dict with only provided fields
        updates = {}
        if update.entry_price is not None:
            updates['entry_price'] = update.entry_price
        if update.stop_loss is not None:
            updates['stop_loss'] = update.stop_loss
        if update.take_profit_1 is not None:
            updates['take_profit_1'] = update.take_profit_1
        if update.take_profit_2 is not None:
            updates['take_profit_2'] = update.take_profit_2
        if update.take_profit_3 is not None:
            updates['take_profit_3'] = update.take_profit_3
        if update.order_type is not None:
            updates['is_limit_order'] = update.order_type.lower() == 'limit'
            # Also update in-memory signal object if present
            signal.is_limit_order = updates['is_limit_order']
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update in database
        success = await orch.db.update_signal(signal_id, updates)
        
        if success:
            logger.info(f"Signal {signal_id} updated from dashboard: {updates}")
            return {"success": True, "message": "Signal updated successfully", "updates": updates}
        else:
            raise HTTPException(status_code=500, detail="Failed to update signal")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/{signal_id}/close")
async def close_signal_manually(signal_id: str, close_data: CloseSignal,
                                request: Request, _=Depends(rate_limit_strict)):
    """Manually close an active signal"""
    orch = require_orch()
    try:
        # Get the signal
        signal = await orch.db.get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Calculate P&L
        entry = signal.actual_entry or signal.entry_price
        pnl = 0
        
        # If signal expired (never triggered/filled), PnL must be 0%
        if close_data.reason == "expired":
            pnl = 0.0
            close_reason_display = "Signal Expired"
        elif entry and entry != 0:
            pnl = ((close_data.close_price - entry) / entry) * 100
            if signal.direction.value == "SHORT":
                pnl = -pnl
            close_reason_display = f"Manually closed ({close_data.reason})"
        else:
            pnl = 0.0
            close_reason_display = f"Manually closed ({close_data.reason})"
        
        # Check if already closed to prevent duplicate messages
        if signal.status.value == 'closed':
            logger.warning(f"Signal {signal_id} already closed, ignoring duplicate close request")
            return {
                "success": False,
                "message": "Signal already closed",
                "pnl_percent": signal.pnl_percent or 0
            }
        
        # Update signal status
        updates = {
            'status': 'closed',
            'actual_exit': close_data.close_price,
            'pnl_percent': pnl,
            'cancellation_reason': close_reason_display,
            'closed_at': datetime.utcnow().isoformat()
        }
        
        success = await orch.db.update_signal(signal_id, updates)
        
        if success:
            # CRITICAL: Update signal object in memory so notification displays correct exit price
            signal.actual_exit = close_data.close_price
            signal.pnl_percent = pnl
            signal.status = SignalStatus.CLOSED
            signal.closed_at = datetime.utcnow()
            
            # Send notification to VIP channel
            await orch.channel_publisher.send_trade_closed(
                signal, 
                close_reason_display,
                pnl
            )
            
            logger.info(f"Signal {signal_id} manually closed at {close_data.close_price}, P&L: {pnl:.2f}%")
            return {
                "success": True, 
                "message": "Signal closed successfully",
                "pnl_percent": round(pnl, 2),
                "close_price": close_data.close_price
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to close signal")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/{signal_id}/fill")
async def fill_limit_order_manually(signal_id: str, fill_data: FillLimitOrder,
                                    request: Request, _=Depends(rate_limit_strict)):
    """Manually fill an approved limit order and start tracking"""
    orch = require_orch()
    try:
        signal = await orch.db.get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")

        if signal.status.value != 'approved':
            raise HTTPException(status_code=400, detail="Signal must be in APPROVED status to fill")

        # Update signal to active
        signal.status = SignalStatus.ACTIVE
        signal.actual_entry = fill_data.fill_price

        updates = {
            'status': 'active',
            'actual_entry': fill_data.fill_price,
        }
        success = await orch.db.update_signal(signal_id, updates)

        if success:
            # Start autopilot tracking
            if orch.autopilot:
                await orch.autopilot.track_signal(signal)

            # Send VIP fill notification
            await orch.channel_publisher.send_limit_fill_notification(signal)

            logger.info(f"Signal {signal_id} manually filled at {fill_data.fill_price}")
            return {
                "success": True,
                "message": "Limit order filled and tracking started",
                "fill_price": fill_data.fill_price,
                "signal_id": signal_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to fill signal")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error filling signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/{signal_id}/mark-tp")
async def mark_tp_hit_manually(signal_id: str, tp_data: MarkTPHit,
                               request: Request, _=Depends(rate_limit_strict)):
    """Manually mark a TP level as hit"""
    orch = require_orch()
    try:
        if tp_data.tp_level not in [1, 2, 3]:
            raise HTTPException(status_code=400, detail="TP level must be 1, 2, or 3")
        
        # Get the signal
        signal = await orch.db.get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Get current price for the TP level
        tp_price = getattr(signal, f'take_profit_{tp_data.tp_level}')
        if not tp_price:
            raise HTTPException(status_code=400, detail=f"TP{tp_data.tp_level} not set for this signal")
        
        # Use the orchestrator's handle_tp_hit method (includes cache and notifications)
        await orch.handle_tp_hit(signal, tp_data.tp_level, tp_price)
        
        logger.info(f"TP{tp_data.tp_level} manually marked as hit for {signal.symbol}")
        return {
            "success": True,
            "message": f"TP{tp_data.tp_level} marked as hit",
            "tp_price": tp_price
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking TP hit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals/history")
async def signal_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    _=Depends(rate_limit_lenient)
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
async def send_marketing_post(post: MarketingPost,
                              request: Request, _=Depends(rate_limit_strict)):
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
                msg = await orch.admin_bot.bot.send_message(
                    chat_id=ch, text=post.message, parse_mode='HTML'
                )
                sent.append({"channel": ch, "message_id": msg.message_id})
                if post.pin:
                    await orch.admin_bot.bot.pin_chat_message(ch, msg.message_id)
        
        return {"success": True, "sent": sent}
    except Exception as e:
        logger.error(f"Dashboard marketing post error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/marketing/campaign")
async def trigger_campaign(campaign: CampaignTrigger,
                           request: Request, _=Depends(rate_limit_strict)):
    """Trigger a marketing campaign manually."""
    orch = require_orch()
    try:
        if campaign.campaign_type == "fomo":
            # Build FOMO with TODAY's results — trades/wins/losses/P&L
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            result = orch.db.client.table('signals').select('*')\
                .gte('created_at', today_start.isoformat())\
                .in_('status', ['active', 'closed', 'target_hit', 'stopped'])\
                .execute()
            rows = result.data if hasattr(result, 'data') else []
            closed_rows = [r for r in rows if r.get('pnl_percent') is not None]
            
            total = len(closed_rows)
            wins = sum(1 for r in closed_rows if (r.get('pnl_percent') or 0) > 0)
            losses = sum(1 for r in closed_rows if (r.get('pnl_percent') or 0) < 0)
            breakeven = total - wins - losses
            total_pnl = sum(r.get('pnl_percent', 0) or 0 for r in closed_rows)
            
            # Find best trade today
            best = max(closed_rows, key=lambda x: x.get('pnl_percent', 0) or 0) if closed_rows else None
            
            text = "🔥 <b>VIP JUST BANKED IT!</b>\n\n"
            
            if best and best.get('pnl_percent', 0) > 0:
                text += (
                    f"📊 <b>{best.get('symbol', 'Unknown')}</b> hit TP — "
                    f"<b>+{best.get('pnl_percent', 0):.1f}%</b>\n\n"
                )
            
            text += "📊 <b>Today's Results</b>\n"
            text += f"Trades: {total}\n"
            text += f"Wins: {wins} | Losses: {losses}"
            if breakeven > 0:
                text += f" | BE: {breakeven}"
            text += f"\nTotal P&L: {total_pnl:+.1f}%\n\n"
            
            text += (
                f"While free channel watched the teaser...\n"
                f"VIP members executed the full plan.\n\n"
                f"💎 <a href='https://t.me/{settings.TELEGRAM_VIP_BOT_USERNAME}'>Join VIP for the next one</a>"
            )
            
            target_id = settings.TELEGRAM_FREE_CHANNEL_ID
            await orch.channel_publisher.bot.send_message(
                chat_id=target_id,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            return {"success": True, "type": "fomo", "trades": total, "wins": wins, "losses": losses, "pnl": total_pnl}
        
        elif campaign.campaign_type == "social_proof":
            # Query only EXECUTED trades (not pending/rejected) from the last 7 days
            since = datetime.utcnow() - timedelta(days=7)
            result = orch.db.client.table('signals').select('*')\
                .gte('created_at', since.isoformat())\
                .in_('status', ['active', 'closed', 'target_hit', 'stopped'])\
                .execute()
            rows = result.data if hasattr(result, 'data') else []
            # Only count trades with a P&L result (closed) or still active
            closed_rows = [r for r in rows if r.get('pnl_percent') is not None]
            total = len(closed_rows)
            wins = sum(1 for r in closed_rows if (r.get('pnl_percent') or 0) > 0)
            losses = sum(1 for r in closed_rows if (r.get('pnl_percent') or 0) < 0)
            breakeven = total - wins - losses
            total_pnl = sum(r.get('pnl_percent', 0) or 0 for r in closed_rows)
            
            # Fallback to all-time if week is empty
            if total == 0:
                result_all = orch.db.client.table('signals').select('*')\
                    .in_('status', ['active', 'closed', 'target_hit', 'stopped'])\
                    .execute()
                rows_all = result_all.data if hasattr(result_all, 'data') else []
                closed_all = [r for r in rows_all if r.get('pnl_percent') is not None]
                total = len(closed_all)
                wins = sum(1 for r in closed_all if (r.get('pnl_percent') or 0) > 0)
                losses = sum(1 for r in closed_all if (r.get('pnl_percent') or 0) < 0)
                breakeven = total - wins - losses
                total_pnl = sum(r.get('pnl_percent', 0) or 0 for r in closed_all)
                period_label = "All Time"
            else:
                period_label = "This Week"
            
            text = f"📊 <b>{period_label}'s Results</b>\n\n"
            text += f"Trades: {total}\n"
            text += f"Wins: {wins} | Losses: {losses}"
            if breakeven > 0:
                text += f" | BE: {breakeven}"
            text += f"\nTotal P&L: {total_pnl:+.1f}%\n\n"
            text += f"💎 See full plans in VIP"
            
            await orch.channel_publisher.send_free_channel_message(text)
            return {"success": True, "type": "social_proof", "trades": total, "wins": wins, "losses": losses, "pnl": total_pnl}
        
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
async def trigger_scheduled_job(job: ScheduleJob,
                                request: Request, _=Depends(rate_limit_strict)):
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
        elif job.job_type == "scan" or job.job_type == "scan_15m":
            await orch.scan_15m()
            return {"success": True, "job": "scan_15m"}
        elif job.job_type == "scan_1h":
            await orch.scan_1h()
            return {"success": True, "job": "scan_1h"}
        elif job.job_type == "scan_4h":
            await orch.scan_4h()
            return {"success": True, "job": "scan_4h"}
        elif job.job_type == "scan_1d" or job.job_type == "scan_daily":
            await orch.scan_daily()
            return {"success": True, "job": "scan_daily"}
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


@app.get("/api/portfolio/analytics")
async def portfolio_analytics(request: Request, days: int = Query(30, ge=1, le=365),
                              _=Depends(rate_limit_moderate)):
    """Get advanced portfolio analytics (Sharpe, Sortino, Profit Factor, etc.)"""
    orch = require_orch()
    try:
        trades = await orch.db.get_closed_signals_for_analytics(days=days)
        if not trades:
            return {"period_days": days, "metrics": {}, "message": "No closed trades in period"}

        analytics = PortfolioAnalytics()
        metrics = analytics.calculate(trades, days=days)
        return {
            "period_days": days,
            "metrics": analytics.to_dict(metrics)
        }
    except Exception as e:
        logger.error(f"Portfolio analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/signal/{signal_id}")
async def get_signal_audit(signal_id: str):
    """Get full audit trail for a specific signal."""
    orch = require_orch()
    try:
        entries = await orch.db.get_signal_audit(signal_id)
        return {"signal_id": signal_id, "entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"Audit trail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/recent")
async def get_recent_audit(event_type: str = Query(None), limit: int = Query(100, ge=1, le=500)):
    """Get recent audit entries, optionally filtered by event type."""
    orch = require_orch()
    try:
        entries = await orch.db.get_recent_audit(event_type=event_type, limit=limit)
        return {"entries": entries, "count": len(entries), "filter": event_type}
    except Exception as e:
        logger.error(f"Recent audit error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/marketing/send-performance")
async def send_performance_to_channel(request: Request, days: int = Query(7, ge=1, le=365), channel: str = Query("free"),
                                      _=Depends(rate_limit_strict)):
    """Send current performance stats to a Telegram channel (free or vip)."""
    orch = require_orch()
    try:
        # Query only EXECUTED trades (not pending/rejected)
        since = datetime.utcnow() - timedelta(days=days)
        result = orch.db.client.table('signals').select('*')\
            .gte('created_at', since.isoformat())\
            .in_('status', ['active', 'closed', 'target_hit', 'stopped'])\
            .execute()
        rows = result.data if hasattr(result, 'data') else []
        closed_rows = [r for r in rows if r.get('pnl_percent') is not None]
        
        total = len(closed_rows)
        wins = sum(1 for r in closed_rows if (r.get('pnl_percent') or 0) > 0)
        losses = sum(1 for r in closed_rows if (r.get('pnl_percent') or 0) < 0)
        breakeven = total - wins - losses
        total_pnl = sum(r.get('pnl_percent', 0) or 0 for r in closed_rows)
        
        period_label = f"Last {days} Days" if days != 7 else "This Week"
        if days >= 365:
            period_label = "All Time"
        
        text = f"📊 <b>{period_label}'s Results</b>\n\n"
        text += f"Trades: {total}\n"
        text += f"Wins: {wins} | Losses: {losses}"
        if breakeven > 0:
            text += f" | BE: {breakeven}"
        text += f"\nTotal P&L: {total_pnl:+.1f}%\n\n"
        text += f"💎 See full plans in VIP"
        
        target_id = settings.TELEGRAM_VIP_CHANNEL_ID if channel == 'vip' else settings.TELEGRAM_FREE_CHANNEL_ID
        await orch.channel_publisher.bot.send_message(
            chat_id=target_id,
            text=text,
            parse_mode='HTML'
        )
        
        logger.info(f"Performance stats sent to {channel} channel: {total} trades, {wins}W/{losses}L, {total_pnl:+.1f}% P&L")
        return {"success": True, "channel": channel, "stats": {"trades": total, "wins": wins, "losses": losses, "pnl": total_pnl}}
        
    except Exception as e:
        logger.error(f"Send performance error: {e}")
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
                    signal = orch.admin_bot.pending_signals.pop(sid, None)
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
async def create_manual_signal(request: Request, sig: ManualSignal,
                                _=Depends(rate_limit_strict)):
    """Manually create a signal and optionally publish immediately."""
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
            {"id": "social_proof", "name": "Social Proof", "text": "📊 This week's results: X trades, Y wins, Z losses, +N% P&L."},
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


class AddBetaTester(BaseModel):
    telegram_user_id: str
    username: Optional[str] = None
    days: int = 30  # Free access duration
    notes: Optional[str] = None


@app.post("/api/subscribers/beta")
async def add_beta_tester(tester: AddBetaTester):
    """Give a user free VIP access (beta/trial)."""
    orch = require_orch()
    try:
        from datetime import datetime, timedelta
        
        expiry = datetime.utcnow() + timedelta(days=tester.days)
        
        success = await orch.db.save_subscriber(
            user_id=tester.telegram_user_id,
            username=tester.username or f"beta_{tester.telegram_user_id[:8]}",
            tier="beta",
            extra_data={
                "status": "trial",
                "trial_ends_at": expiry.isoformat(),
                "notes": tester.notes or "Beta tester - free access",
                "telegram_user_id": tester.telegram_user_id,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        
        if success:
            # Send welcome message from VIP bot so user has direct access
            vip_bot_username = getattr(settings, 'TELEGRAM_VIP_BOT_USERNAME', 'CryptoPulseVIPBot')
            welcome_text = (
                f"🎉 <b>Welcome to Crypto Pulse VIP!</b>\n\n"
                f"You now have <b>FREE VIP access</b> for {tester.days} days.\n\n"
                f"✅ Full signal access\n"
                f"✅ Real-time updates\n"
                f"✅ Alpha alerts (when available)\n\n"
                f"⏰ Expires: {expiry.strftime('%Y-%m-%d')}\n\n"
                f"👇 <b>Tap below to open the VIP bot and join the channel:</b>\n"
                f"https://t.me/{vip_bot_username}?start=access"
            )
            sent = False
            # Try VIP bot first (better UX - same bot they'll use)
            if orch.vip_bot and orch.vip_bot.app and orch.vip_bot.app.bot:
                try:
                    await orch.vip_bot.app.bot.send_message(
                        chat_id=int(tester.telegram_user_id),
                        text=welcome_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    sent = True
                    # Auto-send trading guide to new beta user
                    try:
                        await orch.vip_bot._send_trading_guide(int(tester.telegram_user_id))
                    except Exception as guide_err:
                        logger.warning(f"Beta trading guide send failed: {guide_err}")
                except Exception as e:
                    logger.warning(f"VIP bot welcome failed, falling back to admin: {e}")
            # Fall back to admin bot
            if not sent and orch.admin_bot and orch.admin_bot.bot:
                try:
                    await orch.admin_bot.bot.send_message(
                        chat_id=int(tester.telegram_user_id),
                        text=welcome_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.warning(f"Could not send welcome DM to beta user: {e}")
            
            return {
                "success": True,
                "message": f"Beta access granted for {tester.days} days",
                "expires": expiry.strftime('%Y-%m-%d')
            }
        else:
            return {"success": False, "error": "Failed to save subscriber"}
            
    except Exception as e:
        logger.error(f"Add beta tester error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateSubscriber(BaseModel):
    trial_ends_at: Optional[str] = None  # ISO date string
    notes: Optional[str] = None
    tier: Optional[str] = None
    status: Optional[str] = None


@app.post("/api/subscribers/{user_id}/update")
async def update_subscriber_endpoint(user_id: str, update: UpdateSubscriber):
    """Update subscriber details (trial length, notes, tier, status)."""
    orch = require_orch()
    try:
        update_data = {}
        if update.trial_ends_at:
            update_data['trial_ends_at'] = update.trial_ends_at
        if update.notes is not None:
            update_data['notes'] = update.notes
        if update.tier:
            update_data['tier'] = update.tier
        if update.status:
            update_data['status'] = update.status
        
        if not update_data:
            return {"success": False, "error": "No fields to update"}
        
        success = await orch.db.update_subscriber(user_id, update_data)
        
        if success:
            return {"success": True, "message": "Subscriber updated", "updated": update_data}
        else:
            return {"success": False, "error": "Failed to update subscriber"}
            
    except Exception as e:
        logger.error(f"Update subscriber error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subscribers/{user_id}/cancel")
async def cancel_subscriber_endpoint(user_id: str):
    """Cancel/deactivate a subscriber."""
    orch = require_orch()
    try:
        success = await orch.db.deactivate_subscriber(user_id)
        
        if success:
            # Notify user if possible
            try:
                await orch.admin_bot.bot.send_message(
                    chat_id=int(user_id),
                    text="⚠️ Your VIP access has been cancelled. Contact admin if this was a mistake.",
                    parse_mode='HTML'
                )
            except Exception:
                pass
            
            return {"success": True, "message": "Subscriber cancelled"}
        else:
            return {"success": False, "error": "Failed to cancel subscriber"}
            
    except Exception as e:
        logger.error(f"Cancel subscriber error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                    await orch.admin_bot.bot.send_message(chat_id=user_id, text=blast.message, parse_mode='HTML')
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

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon - inline SVG to avoid 404"""
    svg = b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%2338bdf8'/><path d='M16 8L22 16L16 24L10 16L16 8Z' fill='white'/></svg>"
    return Response(content=svg, media_type="image/svg+xml")


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


@app.post("/api/test/telegram")
async def test_telegram_channels():
    """Test Telegram bot can post to VIP and Free channels. Returns detailed diagnostics."""
    orch = require_orch()
    results = {"tests": [], "all_passed": False}
    all_passed = True
    
    # Test 1: Bot instance exists
    bot = getattr(orch.channel_publisher, 'bot', None)
    vip_id = getattr(orch.channel_publisher, 'vip_channel_id', None)
    free_id = getattr(orch.channel_publisher, 'free_channel_id', None)
    
    results["tests"].append({
        "name": "Bot instance",
        "status": "PASS" if bot else "FAIL",
        "detail": f"Bot type: {type(bot).__name__}" if bot else "channel_publisher.bot is None"
    })
    if not bot:
        all_passed = False
    
    results["tests"].append({
        "name": "VIP channel ID",
        "status": "PASS" if vip_id else "FAIL",
        "detail": str(vip_id) if vip_id else "TELEGRAM_VIP_CHANNEL_ID not set"
    })
    if not vip_id:
        all_passed = False
    
    results["tests"].append({
        "name": "Free channel ID",
        "status": "PASS" if free_id else "FAIL",
        "detail": str(free_id) if free_id else "TELEGRAM_FREE_CHANNEL_ID not set"
    })
    
    # Test 2: Send text to VIP
    if bot and vip_id:
        try:
            msg = await bot.send_message(
                chat_id=vip_id,
                text="🔧 <b>Test message from dashboard</b>\n\nIf you see this, VIP publishing works.",
                parse_mode='HTML'
            )
            results["tests"].append({
                "name": "VIP text send",
                "status": "PASS",
                "detail": f"Message ID: {msg.message_id}"
            })
        except Exception as e:
            all_passed = False
            results["tests"].append({
                "name": "VIP text send",
                "status": "FAIL",
                "detail": str(e)
            })
    else:
        all_passed = False
        results["tests"].append({
            "name": "VIP text send",
            "status": "SKIP",
            "detail": "Bot or VIP channel ID missing"
        })
    
    # Test 3: Send text to Free
    if bot and free_id:
        try:
            msg = await bot.send_message(
                chat_id=free_id,
                text="🔧 <b>Test message from dashboard</b>\n\nIf you see this, Free publishing works.",
                parse_mode='HTML'
            )
            results["tests"].append({
                "name": "Free text send",
                "status": "PASS",
                "detail": f"Message ID: {msg.message_id}"
            })
        except Exception as e:
            all_passed = False
            results["tests"].append({
                "name": "Free text send",
                "status": "FAIL",
                "detail": str(e)
            })
    else:
        results["tests"].append({
            "name": "Free text send",
            "status": "SKIP",
            "detail": "Bot or Free channel ID missing"
        })
    
    results["all_passed"] = all_passed
    return results


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


@app.get("/api/settings")
async def get_settings(request: Request, _=Depends(rate_limit_lenient)):
    """Get current dashboard settings (public toggles only)."""
    return {
        "show_portfolio_in_alpha": settings.SHOW_PORTFOLIO_IN_ALPHA,
        "public_portfolio_enabled": settings.PUBLIC_PORTFOLIO_ENABLED,
        "affiliate_exchange": settings.AFFILIATE_EXCHANGE,
        "affiliate_custom_url": bool(settings.AFFILIATE_CUSTOM_URL),
        "marketing_posts_per_day": settings.MARKETING_POSTS_PER_DAY,
        "enable_viral_content": settings.ENABLE_VIRAL_CONTENT,
        "enable_engagement_loop": settings.ENABLE_ENGAGEMENT_LOOP,
    }


@app.post("/api/settings/portfolio-toggle")
async def toggle_portfolio_display(request: Request, _=Depends(rate_limit_moderate)):
    """Toggle portfolio visibility in alpha play messages."""
    from pydantic import BaseModel
    import json
    
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except:
        data = {}
    
    show = data.get("show", not settings.SHOW_PORTFOLIO_IN_ALPHA)
    
    # Update the setting in memory
    settings.SHOW_PORTFOLIO_IN_ALPHA = bool(show)
    
    logger.info(f"Portfolio display in alpha messages: {'ENABLED' if show else 'DISABLED'}")
    return {
        "success": True,
        "show_portfolio_in_alpha": settings.SHOW_PORTFOLIO_IN_ALPHA,
        "message": f"Portfolio links {'shown' if show else 'hidden'} in alpha messages"
    }


# ============== RESEARCH ENGINE API ==============

@app.get("/api/research/projects")
async def get_research_projects(request: Request, status: str = None, _=Depends(rate_limit_lenient)):
    """Get all research projects"""
    orch = require_orch()
    try:
        if not orch.db:
            return {"projects": [], "message": "Database not initialized"}
        
        projects = await orch.db.get_all_research_projects(status=status, limit=100)
        return {"success": True, "projects": projects, "count": len(projects)}
    except Exception as e:
        logger.error(f"Error getting research projects: {e}")
        return {"success": False, "error": str(e), "projects": []}


@app.get("/api/research/projects/{project_id}")
async def get_research_project(request: Request, project_id: str, _=Depends(rate_limit_lenient)):
    """Get single research project with full details"""
    orch = require_orch()
    try:
        if not orch.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        
        project = await orch.db.get_research_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get conviction history
        history = await orch.db.get_conviction_history(project_id, days=30)
        
        return {"success": True, "project": project, "conviction_history": history}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/research/projects/{project_id}/rescore")
async def rescore_project(request: Request, project_id: str, _=Depends(rate_limit_moderate)):
    """Recalculate conviction score for a project"""
    orch = require_orch()
    try:
        if not orch.alpha_engine or not orch.alpha_engine.research_project_db:
            raise HTTPException(status_code=503, detail="Research engine not initialized")
        
        new_score = await orch.alpha_engine.research_project_db.rescore_project(project_id)
        if new_score is None:
            raise HTTPException(status_code=404, detail="Project not found or rescore failed")
        
        return {"success": True, "new_conviction_score": new_score}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rescoring project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/basket/current")
async def get_alpha_basket(request: Request, _=Depends(rate_limit_lenient)):
    """Get current alpha basket"""
    orch = require_orch()
    try:
        if not orch.alpha_engine or not orch.alpha_engine.basket_manager:
            return {"basket": [], "message": "Basket manager not initialized"}
        
        basket = await orch.alpha_engine.basket_manager.get_basket()
        return {"success": True, "basket": basket, "count": len(basket)}
    except Exception as e:
        logger.error(f"Error getting basket: {e}")
        return {"success": False, "error": str(e), "basket": []}


@app.post("/api/basket/update")
async def update_alpha_basket(request: Request, _=Depends(rate_limit_moderate)):
    """Manually trigger basket update"""
    orch = require_orch()
    try:
        if not orch.alpha_engine or not orch.alpha_engine.basket_manager:
            raise HTTPException(status_code=503, detail="Basket manager not initialized")
        
        basket = await orch.alpha_engine.basket_manager.update_basket()
        return {"success": True, "basket": basket, "count": len(basket)}
    except Exception as e:
        logger.error(f"Error updating basket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/list")
async def list_research_reports(request: Request, project_id: str = None, _=Depends(rate_limit_lenient)):
    """List research reports"""
    orch = require_orch()
    try:
        if not orch.db:
            return {"reports": [], "message": "Database not initialized"}
        
        reports = await orch.db.get_research_reports(project_id=project_id, limit=50)
        return {"success": True, "reports": reports, "count": len(reports)}
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return {"success": False, "error": str(e), "reports": []}


@app.post("/api/reports/generate")
async def generate_research_report(request: Request, _=Depends(rate_limit_moderate)):
    """Generate a new research report"""
    import json
    orch = require_orch()
    
    try:
        if not orch.alpha_engine or not orch.alpha_engine.report_generator:
            raise HTTPException(status_code=503, detail="Report generator not initialized")
        
        body = await request.body()
        data = json.loads(body) if body else {}
        project_id = data.get('project_id')
        report_type = data.get('report_type', 'new_candidate')
        
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id required")
        
        # Get project
        project_data = await orch.db.get_research_project(project_id)
        if not project_data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        from src.research.models import ResearchProject
        project = ResearchProject.from_dict(project_data)
        
        # Get latest conviction score
        history = await orch.db.get_conviction_history(project_id, days=1)
        if not history:
            raise HTTPException(status_code=400, detail="No conviction score found. Rescore project first.")
        
        from src.research.models import ConvictionScore
        score = ConvictionScore(
            project_id=project_id,
            conviction_score=history[0]['conviction_score'],
            quality_score=history[0].get('quality_score', 0),
            valuation_score=history[0].get('valuation_score', 0),
            momentum_score=history[0].get('momentum_score', 0),
            risk_score=history[0].get('risk_score', 0)
        )
        
        # Generate report
        report = await orch.alpha_engine.report_generator.generate_new_candidate_report(project, score)
        
        if not report:
            raise HTTPException(status_code=500, detail="Report generation failed")
        
        return {"success": True, "report": report.to_dict()}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/{report_id}")
async def get_research_report_detail(request: Request, report_id: str, _=Depends(rate_limit_lenient)):
    """Get a single research report by ID with full content"""
    orch = require_orch()
    try:
        if not orch.db:
            return {"success": False, "error": "Database not initialized"}
        
        # Get report from DB
        reports = await orch.db.get_research_reports(limit=100)
        report = None
        for r in reports:
            if r.get('id') == report_id:
                report = r
                break
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Get project details too
        project = await orch.db.get_research_project(report.get('project_id'))
        
        return {
            "success": True,
            "report": report,
            "project": project
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/public-portfolio-toggle")
async def toggle_public_portfolio(request: Request, _=Depends(rate_limit_moderate)):
    """Toggle public portfolio page (/public-portfolio)."""
    import json
    
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except:
        data = {}
    
    enabled = data.get("enabled", not settings.PUBLIC_PORTFOLIO_ENABLED)
    settings.PUBLIC_PORTFOLIO_ENABLED = bool(enabled)
    
    logger.info(f"Public portfolio page: {'ENABLED' if enabled else 'DISABLED'}")
    return {
        "success": True,
        "public_portfolio_enabled": settings.PUBLIC_PORTFOLIO_ENABLED,
        "url": f"http://localhost:{settings.ADMIN_DASHBOARD_PORT}/public-portfolio" if enabled else None,
        "message": f"Public portfolio {'enabled' if enabled else 'disabled'}"
    }


# ==================== CONVICTION ENGINE SETTINGS ====================

@app.get("/api/conviction/mode")
async def get_conviction_mode(request: Request, _=Depends(rate_limit_lenient)):
    """Get current signal mode (strict/balanced/aggressive)."""
    return {
        "mode": settings.SIGNAL_MODE,
        "thresholds": {
            "strict": {"min_conviction": 85, "expected_signals": "0-5/day", "quality": "Elite"},
            "balanced": {"min_conviction": 75, "expected_signals": "5-15/day", "quality": "High"},
            "aggressive": {"min_conviction": 65, "expected_signals": "15-40/day", "quality": "Moderate"}
        },
        "current_threshold": {
            "strict": 85,
            "balanced": 75,
            "aggressive": 65
        }.get(settings.SIGNAL_MODE, 85)
    }


@app.post("/api/conviction/mode")
async def set_conviction_mode(request: Request, _=Depends(rate_limit_moderate)):
    """Set signal mode (strict/balanced/aggressive)."""
    import json
    
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    mode = data.get("mode", "strict").lower()
    
    if mode not in ["strict", "balanced", "aggressive"]:
        raise HTTPException(status_code=400, detail="Mode must be strict, balanced, or aggressive")
    
    settings.SIGNAL_MODE = mode
    
    # Update signal engine if available
    orch = require_orch()
    if hasattr(orch, 'signal_engine') and orch.signal_engine:
        orch.signal_engine.signal_mode = mode
        logger.info(f"🎯 Signal mode updated to: {mode.upper()}")
    
    return {
        "success": True,
        "mode": mode,
        "threshold": {
            "strict": 85,
            "balanced": 75,
            "aggressive": 65
        }.get(mode, 85),
        "message": f"Signal mode set to {mode.upper()}"
    }


@app.get("/api/conviction/breakdown/{signal_id}")
async def get_conviction_breakdown(signal_id: str, request: Request, _=Depends(rate_limit_lenient)):
    """Get detailed conviction breakdown for a signal."""
    orch = require_orch()
    
    try:
        # Get signal from database
        signal = await orch.db.get_signal_by_id(signal_id)
        
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        # Return conviction breakdown if available
        if signal.conviction_breakdown:
            return {
                "signal_id": signal_id,
                "symbol": signal.symbol,
                "conviction_score": signal.conviction_score,
                "conviction_tier": signal.conviction_tier,
                "breakdown": signal.conviction_breakdown
            }
        else:
            return {
                "signal_id": signal_id,
                "symbol": signal.symbol,
                "conviction_score": None,
                "conviction_tier": None,
                "breakdown": None,
                "message": "Conviction data not available for this signal"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conviction breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conviction/stats")
async def get_conviction_stats(request: Request, _=Depends(rate_limit_lenient)):
    """Get conviction engine statistics."""
    orch = require_orch()
    
    try:
        # Get recent signals with conviction data
        from datetime import datetime, timedelta
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        
        recent_signals = await orch.db.get_signals_by_date(week_start, datetime.utcnow())
        
        # Calculate stats
        total_signals = len(recent_signals)
        with_conviction = [s for s in recent_signals if s.conviction_score is not None]
        
        tier_counts = {"ELITE": 0, "VIP": 0, "WATCHLIST": 0, "REJECTED": 0}
        avg_scores = {
            "conviction": 0,
            "market_structure": 0,
            "liquidity": 0,
            "volume": 0,
            "sentiment": 0,
            "news": 0
        }
        
        if with_conviction:
            for signal in with_conviction:
                if signal.conviction_tier:
                    tier_counts[signal.conviction_tier] = tier_counts.get(signal.conviction_tier, 0) + 1
                
                if signal.conviction_breakdown:
                    breakdown = signal.conviction_breakdown
                    avg_scores["conviction"] += breakdown.get("conviction_score", 0)
                    avg_scores["market_structure"] += breakdown.get("market_structure_score", 0)
                    avg_scores["liquidity"] += breakdown.get("liquidity_score", 0)
                    avg_scores["volume"] += breakdown.get("volume_score", 0)
                    avg_scores["sentiment"] += breakdown.get("sentiment_score", 0)
                    avg_scores["news"] += breakdown.get("news_score", 0)
            
            # Calculate averages
            count = len(with_conviction)
            for key in avg_scores:
                avg_scores[key] = round(avg_scores[key] / count, 1)
        
        return {
            "total_signals_7d": total_signals,
            "signals_with_conviction": len(with_conviction),
            "tier_distribution": tier_counts,
            "average_scores": avg_scores,
            "current_mode": settings.SIGNAL_MODE
        }
    
    except Exception as e:
        logger.error(f"Error fetching conviction stats: {e}")
        return {
            "total_signals_7d": 0,
            "signals_with_conviction": 0,
            "tier_distribution": {"ELITE": 0, "VIP": 0, "WATCHLIST": 0, "REJECTED": 0},
            "average_scores": {},
            "current_mode": settings.SIGNAL_MODE,
            "error": str(e)
        }


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
