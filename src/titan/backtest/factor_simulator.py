"""Market-neutral cross-sectional factor portfolio simulator and cost engine.

Research-only. Implements dollar-neutral long/short quantile portfolio construction,
transaction costs (commissions, bid-ask spread), short borrowing fees, and
Spearman rank Information Coefficient (IC) evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from titan.data.equities_universe import EquitiesUniverseData


@dataclass(frozen=True)
class FactorCostModel:
    commission_per_share_usd: float = 0.005
    assumed_avg_share_price: float = 100.0
    spread_bps: float = 1.0  # 1.0 bps = 0.0001
    slippage_bps: float = 0.5  # 0.5 bps = 0.00005
    annual_short_borrow_bps: float = 50.0  # 50 bps = 0.0050 per year

    @classmethod
    def standard_us_equity(cls) -> "FactorCostModel":
        return cls()

    @classmethod
    def stressed_adverse(cls) -> "FactorCostModel":
        return cls(
            commission_per_share_usd=0.010,
            spread_bps=3.0,
            slippage_bps=1.5,
            annual_short_borrow_bps=150.0,
        )



@dataclass
class FactorSimulationResult:
    hypothesis_id: str
    partition: str
    net_returns: pd.Series
    gross_returns: pd.Series
    long_returns: pd.Series
    short_returns: pd.Series
    turnover_series: pd.Series
    rank_ic_series: pd.Series
    costs: dict[str, float]
    annualized_net_sharpe: float
    annualized_net_return: float
    max_drawdown: float
    monthly_turnover: float
    mean_rank_ic: float
    ic_positive_fraction: float
    quantile_returns: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "partition": self.partition,
            "annualized_net_sharpe": round(self.annualized_net_sharpe, 4),
            "annualized_net_return": round(self.annualized_net_return, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "monthly_turnover": round(self.monthly_turnover, 4),
            "mean_rank_ic": round(self.mean_rank_ic, 4),
            "ic_positive_fraction": round(self.ic_positive_fraction, 4),
            "costs": {k: round(v, 6) for k, v in self.costs.items()},
            "quantile_returns": {k: round(v, 4) for k, v in self.quantile_returns.items()},
        }


def _compute_max_drawdown(returns: pd.Series) -> float:
    cum = (1.0 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(abs(dd.min())) if len(dd) else 0.0


def simulate_factor_portfolio(
    universe: EquitiesUniverseData,
    factor_scores: pd.DataFrame,
    *,
    hypothesis_id: str,
    partition: str = "OOS",
    top_k: int = 3,
    bottom_k: int = 3,
    rebalance_freq_days: int = 21,
    gross_exposure: float = 1.0,
    cost_model: FactorCostModel | None = None,
) -> FactorSimulationResult:
    """Simulates a dollar-neutral long/short factor portfolio.

    Parameters
    ----------
    gross_exposure : float
        Total gross exposure across both legs (default 1.0 = +50% long / -50% short;
        2.0 = +100% long / -100% short). Always maintains zero net dollar exposure.
    """
    cost = cost_model or FactorCostModel.standard_us_equity()
    prices = universe.prices
    returns = universe.returns

    # Align dates between returns and factor scores
    common_index = prices.index.intersection(factor_scores.index)
    prices = prices.loc[common_index]
    returns = returns.loc[common_index]
    factor_scores = factor_scores.loc[common_index]

    n_bars = len(common_index)
    if n_bars < rebalance_freq_days + 5:
        raise ValueError("insufficient data points to simulate factor portfolio")

    # Weights matrix: T x N
    weights = pd.DataFrame(0.0, index=common_index, columns=prices.columns)
    rebalance_dates = common_index[::rebalance_freq_days]
    target_leg_weight = (gross_exposure / 2.0)

    for reb_date in rebalance_dates:
        scores = factor_scores.loc[reb_date].dropna()
        if len(scores) < top_k + bottom_k:
            continue
        sorted_symbols = scores.sort_values(ascending=False).index
        long_syms = sorted_symbols[:top_k]
        short_syms = sorted_symbols[-bottom_k:]

        # Dollar neutral: sum(longs) = +target_leg_weight, sum(shorts) = -target_leg_weight -> sum(all) = 0.0
        w = pd.Series(0.0, index=prices.columns)
        for sym in long_syms:
            w[sym] = target_leg_weight / top_k
        for sym in short_syms:
            w[sym] = -target_leg_weight / bottom_k

        weights.loc[reb_date] = w

    # Forward fill weights across holding period
    weights = weights.replace(0.0, np.nan).ffill().fillna(0.0)

    # Shift weights by 1 day so today's return uses yesterday's decision weight (point-in-time)
    held_weights = weights.shift(1).fillna(0.0)

    # Calculate returns decomposition
    long_w = held_weights.clip(lower=0.0)
    short_w = held_weights.clip(upper=0.0)

    long_daily = (long_w * returns).sum(axis=1)
    short_daily = (short_w * returns).sum(axis=1)
    gross_daily = long_daily + short_daily

    # Cost attribution
    # 1. Short borrow fee: accrued daily on short leg
    daily_borrow_rate = (cost.annual_short_borrow_bps * 1e-4) / 252.0
    borrow_costs = short_w.abs().sum(axis=1) * daily_borrow_rate

    # 2. Turnover friction (commissions + spread + slippage impact) on rebalances
    delta_w = weights.diff().abs().sum(axis=1).fillna(0.0)
    # Commission approx: delta_w / avg_share_price * commission_per_share
    comm_rate = cost.commission_per_share_usd / cost.assumed_avg_share_price
    commission_costs = delta_w * comm_rate
    spread_costs = delta_w * (cost.spread_bps * 1e-4)
    slippage_costs = delta_w * (cost.slippage_bps * 1e-4)

    total_friction = borrow_costs + commission_costs + spread_costs + slippage_costs
    net_daily = gross_daily - total_friction

    # Metrics
    mean_net = float(net_daily.mean())
    std_net = float(net_daily.std())
    ann_sharpe = (mean_net / std_net * np.sqrt(252.0)) if std_net > 0 else 0.0
    ann_return = mean_net * 252.0
    max_dd = _compute_max_drawdown(net_daily)

    # Monthly turnover: sum(delta_w) / (n_days / 21)
    monthly_turnover = float(delta_w.sum() / max(n_bars / 21.0, 1.0))

    # Rank Information Coefficient (IC)
    # Spearman rank correlation between factor score and forward 21d returns
    fwd_21d_returns = prices.pct_change(rebalance_freq_days).shift(-rebalance_freq_days)
    ic_values: list[float] = []

    for reb_date in rebalance_dates[:-1]:
        f_slice = factor_scores.loc[reb_date].dropna()
        r_slice = fwd_21d_returns.loc[reb_date].dropna()
        common_syms = f_slice.index.intersection(r_slice.index)
        if len(common_syms) >= 4:
            f_vals = f_slice[common_syms]
            r_vals = r_slice[common_syms]
            if float(f_vals.std()) > 1e-8 and float(r_vals.std()) > 1e-8:
                corr, _ = spearmanr(f_vals, r_vals)
                if not np.isnan(corr):
                    ic_values.append(float(corr))

    mean_ic = float(np.mean(ic_values)) if ic_values else 0.0
    ic_pos_frac = float(sum(1 for x in ic_values if x > 0) / len(ic_values)) if ic_values else 0.0

    # Quantile Spreads
    q_returns = {
        "long_leg_ann": round(float(long_daily.mean() * 252.0), 4),
        "short_leg_ann": round(float(short_daily.mean() * 252.0), 4),
        "gross_spread_ann": round(float(gross_daily.mean() * 252.0), 4),
        "net_spread_ann": round(ann_return, 4),
    }

    return FactorSimulationResult(
        hypothesis_id=hypothesis_id,
        partition=partition,
        net_returns=net_daily,
        gross_returns=gross_daily,
        long_returns=long_daily,
        short_returns=short_daily,
        turnover_series=delta_w,
        rank_ic_series=pd.Series(ic_values),
        costs={
            "total_borrow_cost": float(borrow_costs.sum()),
            "total_commissions": float(commission_costs.sum()),
            "total_spread": float(spread_costs.sum()),
            "total_slippage": float(slippage_costs.sum()),
            "total_friction": float(total_friction.sum()),
        },
        annualized_net_sharpe=ann_sharpe,
        annualized_net_return=ann_return,
        max_drawdown=max_dd,
        monthly_turnover=monthly_turnover,
        mean_rank_ic=mean_ic,
        ic_positive_fraction=ic_pos_frac,
        quantile_returns=q_returns,
    )

