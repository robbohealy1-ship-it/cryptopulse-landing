"""
Conviction Scoring Engine - MVP Version

Calculates multi-factor conviction scores for research projects.
"""

from typing import Dict, List, Optional
from datetime import datetime
import uuid

from src.utils.logger import get_logger
from .models import ResearchProject, ConvictionScore

logger = get_logger(__name__)


class ConvictionEngine:
    """Calculate and track conviction scores"""
    
    def __init__(self, db_client):
        self.db = db_client
        
        # Scoring weights (can be adjusted)
        self.weights = {
            'quality': 0.30,      # Fundamentals
            'valuation': 0.25,    # Market cap vs. potential
            'momentum': 0.20,     # Price/volume action
            'risk': 0.15,         # Risk factors
            'social': 0.10,       # Community strength
        }
    
    async def calculate_conviction(self, project: ResearchProject) -> ConvictionScore:
        """
        Calculate overall conviction score for a project.
        
        Returns ConvictionScore with breakdown and explanation.
        """
        try:
            # Calculate component scores
            quality = self._calculate_quality_score(project)
            valuation = self._calculate_valuation_score(project)
            momentum = self._calculate_momentum_score(project)
            risk = self._calculate_risk_score(project)
            social = self._calculate_social_score(project)
            
            # Weighted average (risk is inverted)
            conviction = (
                quality * self.weights['quality'] +
                valuation * self.weights['valuation'] +
                momentum * self.weights['momentum'] +
                (100 - risk) * self.weights['risk'] +
                social * self.weights['social']
            )
            
            # Get explanation factors
            positive_factors = self._get_positive_factors(project, quality, valuation, momentum, social)
            negative_factors = self._get_negative_factors(project, risk)
            
            score = ConvictionScore(
                project_id=project.id,
                conviction_score=round(conviction, 1),
                quality_score=round(quality, 1),
                valuation_score=round(valuation, 1),
                momentum_score=round(momentum, 1),
                risk_score=round(risk, 1),
                recorded_at=datetime.utcnow(),
                positive_factors=positive_factors,
                negative_factors=negative_factors,
                weightings=self.weights
            )
            
            logger.info(f"📊 Conviction calculated for {project.symbol}: {conviction:.1f}/100")
            return score
            
        except Exception as e:
            logger.error(f"Error calculating conviction for {project.symbol}: {e}")
            # Return default score on error
            return ConvictionScore(
                project_id=project.id,
                conviction_score=0.0,
                quality_score=0.0,
                valuation_score=0.0,
                momentum_score=0.0,
                risk_score=100.0,
                recorded_at=datetime.utcnow(),
                positive_factors=[],
                negative_factors=["Error calculating score"],
                weightings=self.weights
            )
    
    def _calculate_quality_score(self, project: ResearchProject) -> float:
        """
        Score based on fundamentals and activity.
        
        Factors:
        - Liquidity (higher is better)
        - Volume (higher is better)
        - TVL if available
        - Active users if available
        - Transactions if available
        """
        score = 0.0
        
        # Liquidity scoring (0-30 points)
        if project.liquidity > 0:
            if project.liquidity > 1_000_000:
                score += 30
            elif project.liquidity > 500_000:
                score += 25
            elif project.liquidity > 100_000:
                score += 20
            elif project.liquidity > 50_000:
                score += 15
            else:
                score += 10
        
        # Volume scoring (0-25 points)
        if project.volume_24h > 0:
            if project.volume_24h > 1_000_000:
                score += 25
            elif project.volume_24h > 500_000:
                score += 20
            elif project.volume_24h > 100_000:
                score += 15
            else:
                score += 10
        
        # TVL scoring (0-20 points) - if available
        if project.tvl:
            if project.tvl > 100_000_000:
                score += 20
            elif project.tvl > 10_000_000:
                score += 15
            elif project.tvl > 1_000_000:
                score += 10
        
        # Active users (0-15 points) - if available
        if project.active_users:
            if project.active_users > 10_000:
                score += 15
            elif project.active_users > 1_000:
                score += 10
            elif project.active_users > 100:
                score += 5
        
        # Transactions (0-10 points) - if available
        if project.transactions_24h:
            if project.transactions_24h > 10_000:
                score += 10
            elif project.transactions_24h > 1_000:
                score += 7
            elif project.transactions_24h > 100:
                score += 5
        
        return min(score, 100)
    
    def _calculate_valuation_score(self, project: ResearchProject) -> float:
        """
        Score based on market cap and valuation.
        
        Lower market cap = higher score (more upside potential)
        But must have minimum liquidity to be viable.
        """
        score = 0.0
        
        # Market cap scoring (inverse - lower is better for upside)
        if project.market_cap > 0:
            if project.market_cap < 1_000_000:
                score += 40  # Micro cap - highest upside
            elif project.market_cap < 5_000_000:
                score += 35
            elif project.market_cap < 10_000_000:
                score += 30
            elif project.market_cap < 50_000_000:
                score += 25
            elif project.market_cap < 100_000_000:
                score += 20
            else:
                score += 10  # Large cap - lower upside
        
        # FDV vs Market Cap ratio (0-30 points)
        if project.fdv > 0 and project.market_cap > 0:
            ratio = project.fdv / project.market_cap
            if ratio < 1.5:
                score += 30  # Low unlock risk
            elif ratio < 3:
                score += 20
            elif ratio < 5:
                score += 10
            else:
                score += 5  # High unlock risk
        
        # Volume/Market Cap ratio (0-30 points)
        if project.market_cap > 0 and project.volume_24h > 0:
            vol_ratio = project.volume_24h / project.market_cap
            if vol_ratio > 0.5:
                score += 30  # Very high activity
            elif vol_ratio > 0.2:
                score += 25
            elif vol_ratio > 0.1:
                score += 20
            elif vol_ratio > 0.05:
                score += 15
            else:
                score += 10
        
        return min(score, 100)
    
    def _calculate_momentum_score(self, project: ResearchProject) -> float:
        """
        Score based on price and volume momentum.
        
        Uses existing market data from discovery.
        """
        score = 50.0  # Neutral baseline
        
        # Volume trend (higher volume = higher score)
        if project.volume_24h > 0:
            if project.volume_24h > 1_000_000:
                score += 25
            elif project.volume_24h > 500_000:
                score += 15
            elif project.volume_24h > 100_000:
                score += 10
        
        # Liquidity trend
        if project.liquidity > 0:
            if project.liquidity > 500_000:
                score += 25
            elif project.liquidity > 100_000:
                score += 15
            elif project.liquidity > 50_000:
                score += 10
        
        return min(score, 100)
    
    def _calculate_risk_score(self, project: ResearchProject) -> float:
        """
        Score based on risk factors.
        
        Higher score = higher risk (this gets inverted in final calculation)
        """
        risk = 0.0
        
        # Liquidity risk (0-30 points)
        if project.liquidity > 0:
            if project.liquidity < 10_000:
                risk += 30  # Very high risk
            elif project.liquidity < 50_000:
                risk += 20
            elif project.liquidity < 100_000:
                risk += 10
            # else: low risk (0 points)
        else:
            risk += 30  # No liquidity data = high risk
        
        # Market cap risk (0-20 points)
        if project.market_cap > 0:
            if project.market_cap < 100_000:
                risk += 20  # Extreme micro cap
            elif project.market_cap < 500_000:
                risk += 15
            elif project.market_cap < 1_000_000:
                risk += 10
        
        # FDV unlock risk (0-25 points)
        if project.fdv > 0 and project.market_cap > 0:
            ratio = project.fdv / project.market_cap
            if ratio > 10:
                risk += 25  # Massive unlock risk
            elif ratio > 5:
                risk += 20
            elif ratio > 3:
                risk += 15
            elif ratio > 2:
                risk += 10
        
        # Volume risk (0-25 points)
        if project.volume_24h > 0 and project.liquidity > 0:
            vol_liq_ratio = project.volume_24h / project.liquidity
            if vol_liq_ratio < 0.1:
                risk += 25  # Very low volume
            elif vol_liq_ratio < 0.5:
                risk += 15
            elif vol_liq_ratio < 1.0:
                risk += 10
        
        return min(risk, 100)
    
    def _calculate_social_score(self, project: ResearchProject) -> float:
        """
        Score based on social metrics and community.
        """
        score = 0.0
        
        # Twitter followers (0-50 points)
        if project.twitter_followers:
            if project.twitter_followers > 100_000:
                score += 50
            elif project.twitter_followers > 50_000:
                score += 40
            elif project.twitter_followers > 10_000:
                score += 30
            elif project.twitter_followers > 5_000:
                score += 20
            elif project.twitter_followers > 1_000:
                score += 10
        
        # Discord members (0-30 points)
        if project.discord_members:
            if project.discord_members > 10_000:
                score += 30
            elif project.discord_members > 5_000:
                score += 20
            elif project.discord_members > 1_000:
                score += 10
        
        # Has social presence (0-20 points)
        if project.twitter or project.discord_members:
            score += 20
        
        return min(score, 100)
    
    def _get_positive_factors(self, project: ResearchProject, quality: float, 
                             valuation: float, momentum: float, social: float) -> List[str]:
        """Extract positive factors for explanation"""
        factors = []
        
        if quality > 70:
            factors.append(f"Strong fundamentals (Quality: {quality:.0f}/100)")
        if valuation > 70:
            factors.append(f"Attractive valuation (Valuation: {valuation:.0f}/100)")
        if momentum > 70:
            factors.append(f"Positive momentum (Momentum: {momentum:.0f}/100)")
        if social > 70:
            factors.append(f"Strong community (Social: {social:.0f}/100)")
        
        if project.liquidity > 500_000:
            factors.append(f"High liquidity (${project.liquidity:,.0f})")
        if project.volume_24h > 1_000_000:
            factors.append(f"Strong volume (${project.volume_24h:,.0f}/24h)")
        if project.market_cap < 10_000_000:
            factors.append(f"Low market cap (${project.market_cap/1e6:.1f}M - high upside potential)")
        if project.twitter_followers and project.twitter_followers > 10_000:
            factors.append(f"Large Twitter following ({project.twitter_followers:,})")
        
        return factors
    
    def _get_negative_factors(self, project: ResearchProject, risk: float) -> List[str]:
        """Extract negative factors for explanation"""
        factors = []
        
        if risk > 70:
            factors.append(f"High risk profile (Risk: {risk:.0f}/100)")
        
        if project.liquidity < 50_000:
            factors.append(f"Low liquidity (${project.liquidity:,.0f})")
        if project.volume_24h < 100_000:
            factors.append(f"Low volume (${project.volume_24h:,.0f}/24h)")
        if project.market_cap < 500_000:
            factors.append(f"Extreme micro cap (${project.market_cap/1e6:.2f}M)")
        
        if project.fdv > 0 and project.market_cap > 0:
            ratio = project.fdv / project.market_cap
            if ratio > 5:
                factors.append(f"High token unlock risk (FDV/MC: {ratio:.1f}x)")
        
        if not project.twitter_followers or project.twitter_followers < 1000:
            factors.append("Limited social presence")
        
        return factors
    
    async def track_score_change(self, project_id: str, new_score: ConvictionScore) -> bool:
        """
        Save score to history and calculate change from previous.
        """
        try:
            # Get previous score
            history = await self.db.get_conviction_history(project_id, days=7)
            
            if history:
                prev_score = history[0].get('conviction_score', 0)
                new_score.score_change = new_score.conviction_score - prev_score
                
                # Determine change reason
                if abs(new_score.score_change) > 10:
                    if new_score.score_change > 0:
                        new_score.change_reason = "Significant improvement in metrics"
                    else:
                        new_score.change_reason = "Metrics deteriorated"
            
            # Save to history
            await self.db.save_conviction_score(new_score.to_dict())
            
            # Update project with latest scores
            await self.db.update_research_project(project_id, {
                'conviction_score': new_score.conviction_score,
                'quality_score': new_score.quality_score,
                'valuation_score': new_score.valuation_score,
                'momentum_score': new_score.momentum_score,
                'risk_score': new_score.risk_score,
                'last_scored_at': datetime.utcnow().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error tracking score change: {e}")
            return False
