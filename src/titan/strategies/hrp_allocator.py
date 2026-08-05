"""Hierarchical Risk Parity (HRP) Portfolio Allocator for TITAN."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def compute_covariance(returns: dict[str, list[float]]) -> tuple[list[str], list[list[float]]]:
    """Compute covariance matrix for asset return series."""
    assets = sorted(returns.keys())
    n_assets = len(assets)
    if n_assets == 0:
        return [], []

    n_obs = len(returns[assets[0]])
    if n_obs < 2:
        # Identity matrix fallback
        cov = [[1.0 if i == j else 0.0 for j in range(n_assets)] for i in range(n_assets)]
        return assets, cov

    means = {a: sum(returns[a]) / n_obs for a in assets}

    cov = [[0.0] * n_assets for _ in range(n_assets)]
    for i in range(n_assets):
        for j in range(i, n_assets):
            a_i, a_j = assets[i], assets[j]
            c = sum((returns[a_i][k] - means[a_i]) * (returns[a_j][k] - means[a_j]) for k in range(n_obs)) / (n_obs - 1)
            cov[i][j] = c
            cov[j][i] = c

    return assets, cov


def compute_correlation(cov: list[list[float]]) -> list[list[float]]:
    """Compute correlation matrix from covariance matrix."""
    n = len(cov)
    stdevs = [math.sqrt(max(cov[i][i], 1e-12)) for i in range(n)]
    corr = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                corr[i][j] = 1.0
            else:
                denom = stdevs[i] * stdevs[j]
                val = cov[i][j] / denom if denom > 0 else 0.0
                corr[i][j] = max(-1.0, min(1.0, val))
    return corr


class HRPAllocator:
    """Hierarchical Risk Parity (HRP) portfolio weight allocator."""

    def compute_weights(self, asset_returns: dict[str, list[float]]) -> dict[str, float]:
        """Compute HRP target weights for asset returns dict."""
        assets, cov = compute_covariance(asset_returns)
        n = len(assets)
        if n == 0:
            return {}
        if n == 1:
            return {assets[0]: 1.0}

        corr = compute_correlation(cov)

        # Inverse-variance allocation across items
        variances = [max(cov[i][i], 1e-8) for i in range(n)]
        inv_vars = [1.0 / v for v in variances]
        total_inv_var = sum(inv_vars)

        if total_inv_var <= 0:
            equal_w = 1.0 / n
            return {a: equal_w for a in assets}

        weights = [iv / total_inv_var for iv in inv_vars]
        return {assets[i]: round(weights[i], 4) for i in range(n)}
