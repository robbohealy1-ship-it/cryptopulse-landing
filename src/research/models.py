"""
Data models for Investment Intelligence Engine
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from decimal import Decimal


@dataclass
class ResearchProject:
    """Core research project model"""
    id: str
    symbol: str
    name: str
    chain: str
    token_address: Optional[str] = None
    
    # Classification
    category: Optional[str] = None
    narrative: Optional[str] = None
    sector: Optional[str] = None
    
    # Market Data
    market_cap: float = 0.0
    fdv: float = 0.0
    price: float = 0.0
    volume_24h: float = 0.0
    liquidity: float = 0.0
    
    # Fundamentals
    tvl: Optional[float] = None
    revenue_24h: Optional[float] = None
    active_users: Optional[int] = None
    transactions_24h: Optional[int] = None
    
    # Social
    twitter_followers: Optional[int] = None
    discord_members: Optional[int] = None
    
    # Conviction Scores
    conviction_score: float = 0.0
    risk_score: float = 0.0
    quality_score: float = 0.0
    valuation_score: float = 0.0
    momentum_score: float = 0.0
    
    # Status
    status: str = 'discovered'  # discovered, researching, basket, archived
    in_basket: bool = False
    basket_rank: Optional[int] = None
    
    # Research
    investment_thesis: Optional[str] = None
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    key_risks: List[str] = field(default_factory=list)
    
    # Links
    website: Optional[str] = None
    twitter: Optional[str] = None
    dex_url: Optional[str] = None
    
    # Metadata
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    last_scored_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'chain': self.chain,
            'token_address': self.token_address,
            'category': self.category,
            'narrative': self.narrative,
            'sector': self.sector,
            'market_cap': float(self.market_cap) if self.market_cap else 0,
            'fdv': float(self.fdv) if self.fdv else 0,
            'price': float(self.price) if self.price else 0,
            'volume_24h': float(self.volume_24h) if self.volume_24h else 0,
            'liquidity': float(self.liquidity) if self.liquidity else 0,
            'tvl': float(self.tvl) if self.tvl else None,
            'revenue_24h': float(self.revenue_24h) if self.revenue_24h else None,
            'active_users': self.active_users,
            'transactions_24h': self.transactions_24h,
            'twitter_followers': self.twitter_followers,
            'discord_members': self.discord_members,
            'conviction_score': float(self.conviction_score),
            'risk_score': float(self.risk_score),
            'quality_score': float(self.quality_score),
            'valuation_score': float(self.valuation_score),
            'momentum_score': float(self.momentum_score),
            'status': self.status,
            'in_basket': self.in_basket,
            'basket_rank': self.basket_rank,
            'investment_thesis': self.investment_thesis,
            'bull_case': self.bull_case,
            'bear_case': self.bear_case,
            'key_risks': self.key_risks,
            'website': self.website,
            'twitter': self.twitter,
            'dex_url': self.dex_url,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'last_scored_at': self.last_scored_at.isoformat() if self.last_scored_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ResearchProject':
        """Create from database dictionary"""
        return cls(
            id=data['id'],
            symbol=data['symbol'],
            name=data['name'],
            chain=data['chain'],
            token_address=data.get('token_address'),
            category=data.get('category'),
            narrative=data.get('narrative'),
            sector=data.get('sector'),
            market_cap=float(data.get('market_cap', 0)),
            fdv=float(data.get('fdv', 0)),
            price=float(data.get('price', 0)),
            volume_24h=float(data.get('volume_24h', 0)),
            liquidity=float(data.get('liquidity', 0)),
            tvl=float(data['tvl']) if data.get('tvl') else None,
            revenue_24h=float(data['revenue_24h']) if data.get('revenue_24h') else None,
            active_users=data.get('active_users'),
            transactions_24h=data.get('transactions_24h'),
            twitter_followers=data.get('twitter_followers'),
            discord_members=data.get('discord_members'),
            conviction_score=float(data.get('conviction_score', 0)),
            risk_score=float(data.get('risk_score', 0)),
            quality_score=float(data.get('quality_score', 0)),
            valuation_score=float(data.get('valuation_score', 0)),
            momentum_score=float(data.get('momentum_score', 0)),
            status=data.get('status', 'discovered'),
            in_basket=data.get('in_basket', False),
            basket_rank=data.get('basket_rank'),
            investment_thesis=data.get('investment_thesis'),
            bull_case=data.get('bull_case'),
            bear_case=data.get('bear_case'),
            key_risks=data.get('key_risks', []),
            website=data.get('website'),
            twitter=data.get('twitter'),
            dex_url=data.get('dex_url'),
            discovered_at=datetime.fromisoformat(data['discovered_at']) if data.get('discovered_at') else datetime.utcnow(),
            last_updated=datetime.fromisoformat(data['last_updated']) if data.get('last_updated') else datetime.utcnow(),
            last_scored_at=datetime.fromisoformat(data['last_scored_at']) if data.get('last_scored_at') else None,
        )


@dataclass
class ConvictionScore:
    """Conviction scoring result"""
    project_id: str
    conviction_score: float
    risk_score: float
    quality_score: float
    valuation_score: float
    momentum_score: float
    score_change: Optional[float] = None
    change_reason: Optional[str] = None
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    
    # Explanation
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    weightings: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'project_id': self.project_id,
            'conviction_score': float(self.conviction_score),
            'risk_score': float(self.risk_score),
            'quality_score': float(self.quality_score),
            'valuation_score': float(self.valuation_score),
            'momentum_score': float(self.momentum_score),
            'score_change': float(self.score_change) if self.score_change else None,
            'change_reason': self.change_reason,
            'recorded_at': self.recorded_at.isoformat(),
        }


@dataclass
class AlphaBasketEntry:
    """Alpha basket entry"""
    id: str
    project_id: str
    rank: int
    previous_rank: Optional[int] = None
    added_at: datetime = field(default_factory=datetime.utcnow)
    added_reason: str = ""
    entry_price: float = 0.0
    entry_market_cap: float = 0.0
    current_price: float = 0.0
    current_market_cap: float = 0.0
    pnl_percent: float = 0.0
    status: str = 'active'
    removed_at: Optional[datetime] = None
    removal_reason: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'rank': self.rank,
            'previous_rank': self.previous_rank,
            'added_at': self.added_at.isoformat(),
            'added_reason': self.added_reason,
            'entry_price': float(self.entry_price),
            'entry_market_cap': float(self.entry_market_cap),
            'current_price': float(self.current_price),
            'current_market_cap': float(self.current_market_cap),
            'pnl_percent': float(self.pnl_percent),
            'status': self.status,
            'removed_at': self.removed_at.isoformat() if self.removed_at else None,
            'removal_reason': self.removal_reason,
            'last_updated': self.last_updated.isoformat(),
        }


@dataclass
class ResearchReport:
    """Research report"""
    id: str
    project_id: str
    report_type: str
    title: str
    executive_summary: str = ""
    investment_thesis: str = ""
    bull_case: str = ""
    bear_case: str = ""
    key_risks: List[str] = field(default_factory=list)
    conviction_score: float = 0.0
    risk_score: float = 0.0
    generated_at: datetime = field(default_factory=datetime.utcnow)
    published: bool = False
    published_at: Optional[datetime] = None
    telegram_message_id: Optional[int] = None
    
    # Full AI-generated report content (rich HTML)
    ai_report_content: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'report_type': self.report_type,
            'title': self.title,
            'executive_summary': self.executive_summary,
            'investment_thesis': self.investment_thesis,
            'bull_case': self.bull_case,
            'bear_case': self.bear_case,
            'key_risks': self.key_risks,
            'conviction_score': float(self.conviction_score),
            'risk_score': float(self.risk_score),
            'generated_at': self.generated_at.isoformat(),
            'published': self.published,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'telegram_message_id': self.telegram_message_id,
            'ai_report_content': self.ai_report_content,
        }
