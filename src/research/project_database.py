"""
Project Database Manager

Manages research projects lifecycle and data enrichment.
"""

from typing import List, Optional, Dict
from datetime import datetime
import uuid

from src.utils.logger import get_logger
from src.alpha_plays.alpha_discovery import AlphaPlayCandidate
from .models import ResearchProject
from .conviction_engine import ConvictionEngine

logger = get_logger(__name__)


class ProjectDatabase:
    """Manage research projects"""
    
    def __init__(self, db_client, conviction_engine: ConvictionEngine):
        self.db = db_client
        self.conviction = conviction_engine
    
    async def create_from_alpha_candidate(self, candidate: AlphaPlayCandidate) -> Optional[ResearchProject]:
        """
        Convert an alpha play candidate into a research project.
        
        This bridges the existing alpha discovery with the new research engine.
        """
        try:
            # Check if project already exists
            existing = await self.get_by_symbol(candidate.symbol, candidate.chain)
            if existing:
                logger.info(f"Research project already exists for {candidate.symbol}")
                return existing
            
            # Create new research project
            project = ResearchProject(
                id=str(uuid.uuid4()),
                symbol=candidate.symbol,
                name=candidate.name,
                chain=candidate.chain,
                token_address=candidate.token_address,
                
                # Classification (can be enhanced later)
                category=self._detect_category(candidate),
                narrative=candidate.narrative if hasattr(candidate, 'narrative') else None,
                sector=self._detect_sector(candidate),
                
                # Market data from candidate
                market_cap=candidate.market_cap_usd,
                fdv=candidate.fdv,
                price=candidate.price_usd,
                volume_24h=candidate.volume_24h,
                liquidity=candidate.liquidity_usd,
                
                # Social
                twitter_followers=None,  # Not in candidate yet
                discord_members=None,
                
                # Links
                website=None,
                twitter=None,
                dex_url=candidate.dex_url,
                
                # Status
                status='discovered',
                discovered_at=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
            
            # Calculate initial conviction score
            score = await self.conviction.calculate_conviction(project)
            project.conviction_score = score.conviction_score
            project.quality_score = score.quality_score
            project.valuation_score = score.valuation_score
            project.momentum_score = score.momentum_score
            project.risk_score = score.risk_score
            project.last_scored_at = datetime.utcnow()
            
            # Save to database
            await self.db.save_research_project(project.to_dict())
            
            # Save initial score to history
            await self.conviction.track_score_change(project.id, score)
            
            logger.info(f"✅ Created research project: {project.symbol} (Conviction: {score.conviction_score:.1f}/100)")
            
            return project
            
        except Exception as e:
            logger.error(f"Error creating research project from candidate: {e}")
            return None
    
    async def get_by_symbol(self, symbol: str, chain: str) -> Optional[ResearchProject]:
        """Get project by symbol and chain"""
        try:
            projects = await self.db.get_all_research_projects()
            for p in projects:
                if p['symbol'] == symbol and p['chain'] == chain:
                    return ResearchProject.from_dict(p)
            return None
        except Exception as e:
            logger.error(f"Error getting project by symbol: {e}")
            return None
    
    async def get_project(self, project_id: str) -> Optional[ResearchProject]:
        """Get project by ID"""
        try:
            data = await self.db.get_research_project(project_id)
            return ResearchProject.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return None
    
    async def get_all_projects(self, status: str = None) -> List[ResearchProject]:
        """Get all projects with optional status filter"""
        try:
            data = await self.db.get_all_research_projects(status=status)
            return [ResearchProject.from_dict(p) for p in data]
        except Exception as e:
            logger.error(f"Error getting all projects: {e}")
            return []
    
    async def update_project(self, project_id: str, updates: Dict) -> bool:
        """Update project fields"""
        try:
            updates['last_updated'] = datetime.utcnow().isoformat()
            return await self.db.update_research_project(project_id, updates)
        except Exception as e:
            logger.error(f"Error updating project: {e}")
            return False
    
    async def rescore_project(self, project_id: str) -> Optional[float]:
        """
        Recalculate conviction score for a project.
        
        Returns new conviction score or None on error.
        """
        try:
            project = await self.get_project(project_id)
            if not project:
                return None
            
            # Calculate new score
            score = await self.conviction.calculate_conviction(project)
            
            # Track change
            await self.conviction.track_score_change(project_id, score)
            
            logger.info(f"📊 Rescored {project.symbol}: {score.conviction_score:.1f}/100")
            
            return score.conviction_score
            
        except Exception as e:
            logger.error(f"Error rescoring project: {e}")
            return None
    
    async def rescore_all_projects(self) -> int:
        """
        Rescore all active projects.
        
        Returns number of projects rescored.
        """
        try:
            projects = await self.get_all_projects(status='discovered')
            count = 0
            
            for project in projects:
                score = await self.rescore_project(project.id)
                if score is not None:
                    count += 1
            
            logger.info(f"✅ Rescored {count} projects")
            return count
            
        except Exception as e:
            logger.error(f"Error rescoring all projects: {e}")
            return 0
    
    def _detect_category(self, candidate: AlphaPlayCandidate) -> str:
        """Detect project category from candidate data"""
        # Simple heuristic - can be enhanced with AI later
        symbol_lower = candidate.symbol.lower()
        name_lower = candidate.name.lower()
        
        if any(x in symbol_lower or x in name_lower for x in ['ai', 'gpt', 'agent']):
            return 'AI'
        elif any(x in symbol_lower or x in name_lower for x in ['game', 'play', 'nft']):
            return 'Gaming'
        elif any(x in symbol_lower or x in name_lower for x in ['defi', 'swap', 'dex', 'lend']):
            return 'DeFi'
        elif any(x in symbol_lower or x in name_lower for x in ['meme', 'dog', 'cat', 'pepe']):
            return 'Meme'
        else:
            return 'Other'
    
    def _detect_sector(self, candidate: AlphaPlayCandidate) -> str:
        """Detect project sector"""
        # Map category to broader sector
        category = self._detect_category(candidate)
        
        sector_map = {
            'AI': 'Infrastructure',
            'Gaming': 'Consumer',
            'DeFi': 'Finance',
            'Meme': 'Culture',
            'Other': 'Miscellaneous'
        }
        
        return sector_map.get(category, 'Miscellaneous')
