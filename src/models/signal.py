from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class SignalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ACTIVE = "active"
    STOPPED = "stopped"
    TARGET_HIT = "target_hit"
    CLOSED = "closed"


class SignalGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    REJECTED = "REJECTED"


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SetupType(str, Enum):
    LIQUIDITY_SWEEP = "liquidity_sweep"
    BREAKOUT_RETEST = "breakout_retest"
    FAIR_VALUE_GAP = "fair_value_gap"
    PULLBACK_CONTINUATION = "pullback_continuation"
    SUPPORT_RESISTANCE = "support_resistance"
    ORDER_BLOCK = "order_block"
    BREAKER_BLOCK = "breaker_block"
    MITIGATION_BLOCK = "mitigation_block"
    BOS_RETEST = "bos_retest"
    CHOCH_RETEST = "choch_retest"


class TechnicalScore(BaseModel):
    trend_score: float = Field(ge=0, le=100)
    volume_score: float = Field(ge=0, le=100)
    momentum_score: float = Field(ge=0, le=100)
    structure_score: float = Field(ge=0, le=100)
    total_score: float = Field(ge=0, le=100)


class ContextScore(BaseModel):
    macro_score: float = Field(ge=0, le=100)
    news_score: float = Field(ge=0, le=100)
    sentiment_score: float = Field(ge=0, le=100)
    total_score: float = Field(ge=0, le=100)


class SignalMetrics(BaseModel):
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    risk_reward: float
    atr: float
    volatility: float


class TradingSignal(BaseModel):
    id: Optional[str] = None
    symbol: str
    direction: SignalDirection
    setup_type: SetupType
    timeframe: str
    
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    
    is_limit_order: bool = False  # True for 5m zone-based entries (set limit order, don't market buy)
    
    technical_score: TechnicalScore
    context_score: ContextScore
    confidence: float = Field(ge=0, le=100)
    
    # NEW: Conviction engine scores
    conviction_score: Optional[float] = None  # 0-100 from conviction engine
    conviction_tier: Optional[str] = None  # 'ELITE', 'VIP', 'WATCHLIST', 'REJECTED'
    conviction_breakdown: Optional[dict] = None  # Full breakdown from conviction engine
    
    reasoning: str
    chart_url: Optional[str] = None
    chart_path: Optional[str] = None
    
    status: SignalStatus = SignalStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    risk_reward: float
    atr: float
    volume_24h: float
    
    market_context: Optional[str] = None
    news_context: Optional[str] = None
    
    free_channel_message_id: Optional[int] = None
    vip_channel_message_id: Optional[int] = None
    
    actual_entry: Optional[float] = None
    actual_exit: Optional[float] = None
    pnl_percent: Optional[float] = None
    
    # TP/SL hit tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    tp1_hit_at: Optional[datetime] = None
    tp2_hit_at: Optional[datetime] = None
    tp3_hit_at: Optional[datetime] = None
    stop_hit: bool = False
    stop_hit_at: Optional[datetime] = None
    stop_moved_to_breakeven: bool = False
    
    # Tracking fields for admin workflow
    admin_approved: bool = False
    admin_rejected: bool = False
    rejection_reason: Optional[str] = None
    free_channel_posted: bool = False
    vip_channel_posted: bool = False
    cancelled: bool = False
    cancellation_reason: Optional[str] = None
    
    # Delay tracking
    free_channel_delayed: bool = False
    free_channel_scheduled_at: Optional[datetime] = None
    
    # Validation pipeline
    grade: SignalGrade = SignalGrade.REJECTED
    validation_score: float = 0.0  # 0-100 composite score
    validation_breakdown: Optional[dict] = None  # Per-stage scores
    
    # Trade analytics (filled during tracking)
    max_drawdown_percent: Optional[float] = None  # Worst unrealized loss % during trade
    max_adverse_excursion: Optional[float] = None  # Worst price against position
    max_favorable_excursion: Optional[float] = None  # Best price in favor
    duration_minutes: Optional[float] = None  # Time from entry to close
    entry_slippage_percent: Optional[float] = None  # (actual - expected) / expected
    exit_slippage_percent: Optional[float] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class SignalCandidate(BaseModel):
    symbol: str
    direction: SignalDirection
    setup_type: SetupType
    timeframe: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    confidence: float
    reasoning: str
    technical_score: TechnicalScore
    context_score: ContextScore
    risk_reward: float
