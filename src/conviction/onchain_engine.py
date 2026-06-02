"""
On-Chain Engine - Scores on-chain activity (STUB - Future Enhancement)

Scoring Breakdown (0-15 points):
- Whale Activity: 0-6 points
- Exchange Flows: 0-5 points
- Stablecoin Flows: 0-4 points

Inputs (Future):
- Whale accumulation/distribution (Glassnode, CryptoQuant)
- Exchange inflows/outflows (Glassnode, CryptoQuant)
- Stablecoin flows (DefiLlama)
- Dormant wallet activity (Glassnode)

Current Status:
- Returns neutral score (7.5/15) for all symbols
- Ready for future integration with on-chain data providers
- Optional feature - system works without it
"""

import pandas as pd
from typing import Dict, List
from .base_engine import BaseConvictionEngine, EngineScore


class OnChainEngine(BaseConvictionEngine):
    """
    Analyzes and scores on-chain activity
    
    NOTE: This is currently a STUB that returns neutral scores.
    On-chain data requires paid API access (Glassnode, CryptoQuant, Nansen).
    
    Future Implementation:
    - Integrate Glassnode API for whale tracking
    - Integrate CryptoQuant for exchange flows
    - Integrate DefiLlama for stablecoin flows
    - Add dormant wallet activity tracking
    
    For now, returns neutral score (7.5/15) to not penalize signals.
    """
    
    def __init__(self):
        super().__init__(name="OnChain", max_score=15.0)
        self.enabled = False  # Set to True when APIs are integrated
    
    async def calculate(self, df: pd.DataFrame, symbol: str, direction: str, **kwargs) -> EngineScore:
        """
        Calculate on-chain score (0-15 points)
        
        Currently returns neutral score (7.5/15) as on-chain data is not yet integrated.
        
        Args:
            df: OHLCV dataframe
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
        
        Returns:
            EngineScore with neutral score
        """
        # STUB: Return neutral score
        score = 7.5  # Neutral (50% of max)
        factors = {
            'whale_activity': 3.0,  # Neutral
            'exchange_flows': 2.5,  # Neutral
            'stablecoin_flows': 2.0  # Neutral
        }
        positive = ["On-chain analysis not yet implemented (neutral score)"]
        negative = []
        
        explanation = (
            f"On-Chain Score: {score:.1f}/15 (neutral) | "
            "On-chain data integration pending | "
            "Future: Whale tracking, exchange flows, stablecoin flows"
        )
        
        result = EngineScore(
            score=score,
            max_score=self.max_score,
            factors=factors,
            positive_factors=positive,
            negative_factors=negative,
            explanation=explanation
        )
        
        self._log_score(symbol, result)
        return result
    
    # ─── FUTURE IMPLEMENTATION METHODS ───
    
    async def _score_whale_activity(self, symbol: str, direction: str,
                                    positive: List[str], negative: List[str]) -> float:
        """
        Future: Score whale accumulation/distribution (0-6 points)
        
        Data sources:
        - Glassnode: Whale transaction count, whale balance changes
        - CryptoQuant: Large transaction volume
        - Nansen: Smart money flows
        """
        # TODO: Implement when API access is available
        return 3.0  # Neutral
    
    async def _score_exchange_flows(self, symbol: str, direction: str,
                                    positive: List[str], negative: List[str]) -> float:
        """
        Future: Score exchange inflows/outflows (0-5 points)
        
        Data sources:
        - Glassnode: Exchange netflow
        - CryptoQuant: Exchange reserve changes
        
        Logic:
        - Outflows (coins leaving exchanges) = bullish (accumulation)
        - Inflows (coins entering exchanges) = bearish (distribution)
        """
        # TODO: Implement when API access is available
        return 2.5  # Neutral
    
    async def _score_stablecoin_flows(self, symbol: str, direction: str,
                                      positive: List[str], negative: List[str]) -> float:
        """
        Future: Score stablecoin flows (0-4 points)
        
        Data sources:
        - DefiLlama: Stablecoin supply changes
        - Glassnode: Stablecoin exchange inflows
        
        Logic:
        - Stablecoin inflows to exchanges = bullish (buying power)
        - Stablecoin outflows from exchanges = bearish (selling pressure)
        """
        # TODO: Implement when API access is available
        return 2.0  # Neutral
    
    def enable_onchain_analysis(self, glassnode_api_key: str = None,
                                cryptoquant_api_key: str = None,
                                nansen_api_key: str = None):
        """
        Enable on-chain analysis with API keys
        
        Args:
            glassnode_api_key: Glassnode API key
            cryptoquant_api_key: CryptoQuant API key
            nansen_api_key: Nansen API key
        
        Call this method when you have API access to enable real on-chain scoring.
        """
        if glassnode_api_key or cryptoquant_api_key or nansen_api_key:
            self.enabled = True
            self.logger.info("On-chain analysis enabled with API keys")
            # TODO: Store API keys and implement real scoring
        else:
            self.logger.warning("No API keys provided - on-chain analysis remains disabled")
