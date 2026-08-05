"""Unit tests for Hierarchical Risk Parity (HRP) Allocator."""

import pytest
from titan.strategies.hrp_allocator import HRPAllocator, compute_covariance, compute_correlation


class TestHRPAllocator:
    def test_single_asset_returns_full_weight(self):
        alloc = HRPAllocator()
        returns = {"AAPL": [0.01, -0.005, 0.02, 0.015]}
        weights = alloc.compute_weights(returns)
        assert weights == {"AAPL": 1.0}

    def test_two_assets_inverse_variance_weighting(self):
        alloc = HRPAllocator()
        # AAPL has low volatility, TSLA has high volatility
        returns = {
            "AAPL": [0.01, -0.01, 0.01, -0.01, 0.01],
            "TSLA": [0.05, -0.05, 0.05, -0.05, 0.05],
        }
        weights = alloc.compute_weights(returns)
        assert len(weights) == 2
        assert weights["AAPL"] > weights["TSLA"]
        assert abs(sum(weights.values()) - 1.0) < 1e-3

    def test_compute_covariance_and_correlation(self):
        returns = {
            "A": [0.01, 0.02, 0.03],
            "B": [0.02, 0.04, 0.06],
        }
        assets, cov = compute_covariance(returns)
        assert assets == ["A", "B"]
        corr = compute_correlation(cov)
        assert abs(corr[0][1] - 1.0) < 1e-4  # Perfectly correlated
