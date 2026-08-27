"""Market regime classification state machine for macroeconomic filtering."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Optional
from decimal import Decimal


class MarketRegime(Enum):
    TREND_HOLDING = auto()
    RANGE_BOUND = auto()
    CARRY_DOMINANT = auto()
    VOLATILITY_EXPANSION = auto()


@dataclass
class RegimeState:
    current_regime: MarketRegime
    confidence: float
    volatility_percentile: float
    trend_strength: float
    carry_attractiveness: float


class RegimeClassifier:
    """Classifies the market into distinct macro regimes to gate strategy execution."""
    
    def __init__(self, 
                 lookback_window: int = 21,
                 vol_expansion_threshold: float = 0.85, 
                 trend_adx_threshold: float = 25.0,
                 carry_yield_threshold: float = 0.02):
        self.lookback_window = lookback_window
        self.vol_expansion_threshold = vol_expansion_threshold
        self.trend_adx_threshold = trend_adx_threshold
        self.carry_yield_threshold = carry_yield_threshold
        
    def classify(self, 
                 market_data: Dict[str, List[float]], 
                 vol_percentile: float,
                 adx_value: float,
                 avg_yield_differential: float) -> RegimeState:
        """
        Classifies the current market regime based on macro indicators.
        
        Args:
            market_data: Dictionary of instrument prices
            vol_percentile: Current volatility across the basket relative to history (0.0 to 1.0)
            adx_value: Average Directional Index measuring trend strength (0 to 100)
            avg_yield_differential: The average annualized swap/yield differential in the basket
            
        Returns:
            RegimeState object representing the current market condition
        """
        # Determine regime based on hierarchy of dominance
        
        # 1. High Volatility Expansion overrides everything (deleverage/cap risk)
        if vol_percentile >= self.vol_expansion_threshold:
            return RegimeState(
                current_regime=MarketRegime.VOLATILITY_EXPANSION,
                confidence=vol_percentile,
                volatility_percentile=vol_percentile,
                trend_strength=adx_value,
                carry_attractiveness=avg_yield_differential
            )
            
        # 2. Strong Trend dominates carry
        if adx_value >= self.trend_adx_threshold:
            # Scale confidence from 0.5 to 1.0 based on how far past threshold ADX is (cap at 50)
            conf = 0.5 + min(0.5, (adx_value - self.trend_adx_threshold) / 25.0)
            return RegimeState(
                current_regime=MarketRegime.TREND_HOLDING,
                confidence=conf,
                volatility_percentile=vol_percentile,
                trend_strength=adx_value,
                carry_attractiveness=avg_yield_differential
            )
            
        # 3. Carry Dominant Compression (Low vol, high yield diff)
        if avg_yield_differential >= self.carry_yield_threshold and vol_percentile < 0.60:
            # The lower the vol and higher the yield, the higher confidence
            vol_factor = 1.0 - (vol_percentile / 0.60)
            yield_factor = min(1.0, avg_yield_differential / (self.carry_yield_threshold * 3))
            conf = (vol_factor + yield_factor) / 2.0
            
            return RegimeState(
                current_regime=MarketRegime.CARRY_DOMINANT,
                confidence=conf,
                volatility_percentile=vol_percentile,
                trend_strength=adx_value,
                carry_attractiveness=avg_yield_differential
            )
            
        # 4. Default: Range Bound (chop)
        return RegimeState(
            current_regime=MarketRegime.RANGE_BOUND,
            confidence=0.5,  # Default uncertainty state
            volatility_percentile=vol_percentile,
            trend_strength=adx_value,
            carry_attractiveness=avg_yield_differential
        )
