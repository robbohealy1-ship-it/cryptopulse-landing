"""
CRYPTO PULSE SIGNALS — Signal Ranker
Ranks all discovered signals throughout the day and selects only the best 3 to publish.
Bot continues scanning all day but only sends top-quality setups.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from src.models.signal import TradingSignal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SignalRanker:
    """
    Ranks signals by quality and selects best 3 per day.
    
    Ranking Criteria (weighted):
    1. Confidence score (40%) - institutional + context score
    2. Risk/Reward ratio (25%) - higher R:R = better
    3. Multi-timeframe alignment (20%) - HTF confluence
    4. Setup type performance (15%) - historically winning setups
    """
    
    def __init__(self):
        self.daily_candidates = []  # All signals found today
        self.published_today = []   # Signals already sent
        self.last_reset = datetime.utcnow().date()
        
        # Setup type win rate weights (updated from historical data)
        self.setup_weights = {
            'bos_retest': 1.15,      # BOS retests historically strong
            'liquidity_sweep': 1.10,  # Liquidity sweeps good
            'order_block': 1.05,      # Order blocks solid
            'fair_value_gap': 1.00,   # FVG baseline
            'choch_retest': 0.95,     # CHoCH less reliable
            'breakout_retest': 1.08,  # Breakouts good with retest
        }
    
    def reset_if_new_day(self):
        """Reset daily candidates if it's a new day"""
        today = datetime.utcnow().date()
        if today > self.last_reset:
            logger.info(f"📅 New day - resetting signal candidates. Previous day: {len(self.daily_candidates)} found, {len(self.published_today)} published")
            self.daily_candidates = []
            self.published_today = []
            self.last_reset = today
    
    def add_candidate(self, signal: TradingSignal, inst_score, context_score) -> bool:
        """
        Add a signal candidate for ranking.
        Returns True if signal should be published immediately (top 3), False if held for ranking.
        """
        self.reset_if_new_day()
        
        # Calculate composite rank score
        rank_score = self._calculate_rank_score(signal, inst_score, context_score)
        
        # Store candidate with metadata
        candidate = {
            'signal': signal,
            'rank_score': rank_score,
            'inst_score': inst_score,
            'context_score': context_score,
            'discovered_at': datetime.utcnow()
        }
        
        self.daily_candidates.append(candidate)
        logger.info(f"📊 Signal candidate added: {signal.symbol} {signal.timeframe} (rank: {rank_score:.1f}/100)")
        
        # Sort candidates by rank score
        self.daily_candidates.sort(key=lambda x: x['rank_score'], reverse=True)
        
        # Check if this signal is in top 3
        top_3 = self.daily_candidates[:3]
        is_top_3 = candidate in top_3
        
        # Check if we've already published 3 today
        if len(self.published_today) >= 3:
            logger.info(f"⏸️  {signal.symbol} not published - already sent 3 signals today")
            return False
        
        # If this is in top 3 and not yet published, approve it
        if is_top_3 and signal.id not in [p['signal'].id for p in self.published_today]:
            logger.info(f"✅ {signal.symbol} approved for publishing (rank #{len(self.published_today) + 1}/3, score: {rank_score:.1f})")
            self.published_today.append(candidate)
            return True
        
        logger.info(f"⏸️  {signal.symbol} held for ranking (current rank: #{self.daily_candidates.index(candidate) + 1})")
        return False
    
    def _calculate_rank_score(self, signal: TradingSignal, inst_score, context_score) -> float:
        """
        Calculate composite ranking score (0-100).
        
        Weights:
        - Confidence: 40%
        - Risk/Reward: 25%
        - Multi-TF alignment: 20%
        - Setup type: 15%
        """
        # 1. Confidence score (40%)
        confidence_component = signal.confidence * 0.40
        
        # 2. Risk/Reward score (25%)
        # Normalize R:R to 0-100 scale (2R = 50, 4R = 75, 6R+ = 100)
        rr_normalized = min(100, (signal.risk_reward / 6.0) * 100)
        rr_component = rr_normalized * 0.25
        
        # 3. Multi-timeframe alignment (20%)
        mtf_score = inst_score.multi_tf_score if hasattr(inst_score, 'multi_tf_score') else 70
        mtf_component = mtf_score * 0.20
        
        # 4. Setup type historical performance (15%)
        setup_key = signal.setup_type.value
        setup_weight = self.setup_weights.get(setup_key, 1.0)
        setup_component = (setup_weight * 100) * 0.15
        
        total_score = confidence_component + rr_component + mtf_component + setup_component
        
        logger.debug(
            f"Rank calculation for {signal.symbol}: "
            f"conf={confidence_component:.1f} rr={rr_component:.1f} "
            f"mtf={mtf_component:.1f} setup={setup_component:.1f} "
            f"total={total_score:.1f}"
        )
        
        return total_score
    
    def get_daily_stats(self) -> dict:
        """Get statistics for today's signal discovery"""
        self.reset_if_new_day()
        
        return {
            'total_found': len(self.daily_candidates),
            'published': len(self.published_today),
            'remaining_slots': max(0, 3 - len(self.published_today)),
            'top_unpublished': self._get_top_unpublished(5)
        }
    
    def _get_top_unpublished(self, limit: int = 5) -> List[dict]:
        """Get top unpublished signals"""
        published_ids = {p['signal'].id for p in self.published_today}
        unpublished = [c for c in self.daily_candidates if c['signal'].id not in published_ids]
        
        return [
            {
                'symbol': c['signal'].symbol,
                'timeframe': c['signal'].timeframe,
                'rank_score': c['rank_score'],
                'confidence': c['signal'].confidence,
                'risk_reward': c['signal'].risk_reward
            }
            for c in unpublished[:limit]
        ]
    
    def force_publish_next_best(self) -> Optional[TradingSignal]:
        """
        Manually force publish the next best unpublished signal.
        Used for admin override or end-of-day publishing.
        """
        if len(self.published_today) >= 3:
            logger.warning("Cannot force publish - already sent 3 signals today")
            return None
        
        published_ids = {p['signal'].id for p in self.published_today}
        unpublished = [c for c in self.daily_candidates if c['signal'].id not in published_ids]
        
        if not unpublished:
            logger.warning("No unpublished signals available")
            return None
        
        best = unpublished[0]
        self.published_today.append(best)
        logger.info(f"🔓 Force published: {best['signal'].symbol} (rank: {best['rank_score']:.1f})")
        
        return best['signal']
    
    def update_setup_weights(self, setup_type: str, win_rate: float):
        """Update setup type weight based on actual performance"""
        if win_rate > 0.70:
            self.setup_weights[setup_type] = 1.15
        elif win_rate > 0.60:
            self.setup_weights[setup_type] = 1.10
        elif win_rate > 0.50:
            self.setup_weights[setup_type] = 1.05
        else:
            self.setup_weights[setup_type] = 0.95
        
        logger.info(f"Updated setup weight: {setup_type} = {self.setup_weights[setup_type]:.2f} (win rate: {win_rate:.0%})")
