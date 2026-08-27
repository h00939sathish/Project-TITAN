"""Tests for the Market Regime Classifier."""

import pytest
from titan.research.regime_classifier import RegimeClassifier, MarketRegime

def test_volatility_expansion_regime():
    classifier = RegimeClassifier()
    state = classifier.classify(
        market_data={},
        vol_percentile=0.90,  # High vol
        adx_value=15.0,       # Low trend
        avg_yield_differential=0.03  # Decent yield, but vol overrides
    )
    assert state.current_regime == MarketRegime.VOLATILITY_EXPANSION
    assert state.confidence == 0.90

def test_trend_holding_regime():
    classifier = RegimeClassifier()
    state = classifier.classify(
        market_data={},
        vol_percentile=0.70,  # Elevated vol, but below expansion
        adx_value=35.0,       # Strong trend
        avg_yield_differential=0.01  # Low yield
    )
    assert state.current_regime == MarketRegime.TREND_HOLDING
    assert state.confidence > 0.5 

def test_carry_dominant_regime():
    classifier = RegimeClassifier()
    state = classifier.classify(
        market_data={},
        vol_percentile=0.30,  # Low vol compression
        adx_value=15.0,       # Weak trend
        avg_yield_differential=0.04  # High yield
    )
    assert state.current_regime == MarketRegime.CARRY_DOMINANT
    assert state.confidence > 0.5

def test_range_bound_fallback():
    classifier = RegimeClassifier()
    state = classifier.classify(
        market_data={},
        vol_percentile=0.40,  # Moderate/low vol
        adx_value=15.0,       # Weak trend
        avg_yield_differential=0.005  # Poor yield (below 0.02 threshold)
    )
    assert state.current_regime == MarketRegime.RANGE_BOUND
    assert state.confidence == 0.5
