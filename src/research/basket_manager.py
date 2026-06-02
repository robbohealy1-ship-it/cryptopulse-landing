"""
Alpha Basket Manager - Maintains top 20 research projects
"""
from typing import List, Dict
from datetime import datetime
import uuid
from src.utils.logger import get_logger

logger = get_logger(__name__)

class BasketManager:
    def __init__(self, db_client):
        self.db = db_client
        self.max_basket_size = 20
    
    async def update_basket(self) -> List[Dict]:
        """Update basket based on conviction scores"""
        try:
            all_projects = await self.db.get_all_research_projects(status='discovered', limit=50)
            sorted_projects = sorted(all_projects, key=lambda x: x.get('conviction_score', 0), reverse=True)
            top_projects = sorted_projects[:self.max_basket_size]
            current_basket = await self.db.get_alpha_basket()
            current_ids = {b['project_id']: b for b in current_basket}
            
            new_basket = []
            for rank, project in enumerate(top_projects, 1):
                project_id = project['id']
                if project_id in current_ids:
                    existing = current_ids[project_id]
                    entry = {
                        'id': existing['id'], 'project_id': project_id, 'rank': rank,
                        'previous_rank': existing.get('rank'), 'added_at': existing['added_at'],
                        'entry_price': existing.get('entry_price', project.get('price', 0)),
                        'current_price': project.get('price', 0),
                        'pnl_percent': ((project.get('price', 0) - existing.get('entry_price', 0)) / existing.get('entry_price', 1)) * 100 if existing.get('entry_price', 0) > 0 else 0,
                        'status': 'active'
                    }
                else:
                    entry = {
                        'id': str(uuid.uuid4()), 'project_id': project_id, 'rank': rank,
                        'added_at': datetime.utcnow().isoformat(),
                        'added_reason': f"Conviction: {project.get('conviction_score', 0):.1f}/100",
                        'entry_price': project.get('price', 0), 'current_price': project.get('price', 0),
                        'pnl_percent': 0.0, 'status': 'active'
                    }
                    logger.info(f"➕ Added to basket: {project.get('symbol')} (Rank #{rank})")
                
                await self.db.add_to_basket(entry)
                await self.db.update_research_project(project_id, {'in_basket': True, 'basket_rank': rank})
                new_basket.append({'entry': entry, 'project': project})
            
            top_ids = {p['id'] for p in top_projects}
            for b in current_basket:
                if b['project_id'] not in top_ids:
                    await self.db.remove_from_basket(b['project_id'], "Fell below top 20")
                    await self.db.update_research_project(b['project_id'], {'in_basket': False, 'basket_rank': None})
            
            logger.info(f"✅ Basket updated: {len(new_basket)} projects")
            return new_basket
        except Exception as e:
            logger.error(f"Error updating basket: {e}")
            return []
    
    async def get_basket(self) -> List[Dict]:
        """Get current basket with project details"""
        try:
            basket = await self.db.get_alpha_basket()
            result = []
            for entry in basket:
                project = await self.db.get_research_project(entry['project_id'])
                if project:
                    result.append({'entry': entry, 'project': project})
            return result
        except Exception as e:
            logger.error(f"Error getting basket: {e}")
            return []
