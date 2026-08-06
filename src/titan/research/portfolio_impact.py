"""Portfolio Impact Evaluator — measures incremental portfolio Sharpe and diversification benefit."""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioImpactReport:
    """Evaluates candidate impact on existing qualified strategy portfolio."""

    candidate_id: str
    existing_portfolio_sharpe: float
    combined_portfolio_sharpe: float
    incremental_sharpe: float
    max_correlation_with_existing: float
    diversification_benefit_pct: float
    marginal_drawdown_contribution_pct: float
    adds_portfolio_value: bool

    def summary(self) -> str:
        lines = [
            f"+-- PORTFOLIO IMPACT EVALUATION: {self.candidate_id} ------------------------+",
            f"|  Existing Portfolio Sharpe: {self.existing_portfolio_sharpe:5.2f}                                  |",
            f"|  Combined Portfolio Sharpe: {self.combined_portfolio_sharpe:5.2f}                                  |",
            f"|  Incremental Sharpe:        {'+' if self.incremental_sharpe >= 0 else ''}{self.incremental_sharpe:5.2f}                                  |",
            f"|  Max Strategy Correlation:  {self.max_correlation_with_existing:5.2f}  (Threshold < 0.50)               |",
            f"|  Diversification Benefit:   {self.diversification_benefit_pct:5.1f}%                                 |",
            f"|  Portfolio Verdict:         {'[ADDS PORTFOLIO VALUE]' if self.adds_portfolio_value else '[NO DIVERSIFICATION BENEFIT]'}          |",
            "+--------------------------------------------------------------------+",
        ]
        return "\n".join(lines)


def _equity_curve(returns: list[float]) -> list[float]:
    """Compound a return series into an equity curve (starts at 1.0)."""
    curve: list[float] = []
    eq = 1.0
    for r in returns:
        eq *= (1.0 + r)
        curve.append(eq)
    return curve


def _max_drawdown_pct(returns: list[float]) -> float:
    """Peak-to-trough max drawdown of a return series, in percent."""
    if len(returns) < 2:
        return 0.0
    peak = 0.0
    mdd = 0.0
    for eq in _equity_curve(returns):
        if eq > peak:
            peak = eq
        if peak > 0.0:
            mdd = max(mdd, (peak - eq) / peak)
    return mdd * 100.0


def _compute_sharpe(returns: list[float], periods_per_year: float = 252.0) -> float:
    if not returns or len(returns) < 2:
        return 0.0
    mean_r = statistics.mean(returns)
    stdev_r = statistics.stdev(returns)
    if stdev_r <= 1e-9:
        return 0.0
    return (mean_r / stdev_r) * (periods_per_year ** 0.5)


class PortfolioImpactEvaluator:
    """Evaluates strategy candidates at the portfolio level rather than in isolation."""

    def evaluate_candidate(
        self,
        candidate_id: str,
        candidate_returns: list[float],
        existing_portfolio_returns: list[list[float]] | None = None,
    ) -> PortfolioImpactReport:
        if not candidate_returns or len(candidate_returns) < 5:
            return PortfolioImpactReport(
                candidate_id=candidate_id,
                existing_portfolio_sharpe=0.0,
                combined_portfolio_sharpe=0.0,
                incremental_sharpe=0.0,
                max_correlation_with_existing=1.0,
                diversification_benefit_pct=0.0,
                marginal_drawdown_contribution_pct=0.0,
                adds_portfolio_value=False,
            )

        cand_sharpe = _compute_sharpe(candidate_returns)

        if not existing_portfolio_returns:
            # First candidate entering an empty portfolio pool
            adds_val = cand_sharpe >= 0.5
            return PortfolioImpactReport(
                candidate_id=candidate_id,
                existing_portfolio_sharpe=0.0,
                combined_portfolio_sharpe=round(cand_sharpe, 4),
                incremental_sharpe=round(cand_sharpe, 4),
                max_correlation_with_existing=0.0,
                diversification_benefit_pct=100.0 if adds_val else 0.0,
                marginal_drawdown_contribution_pct=round(_max_drawdown_pct(candidate_returns), 2),
                adds_portfolio_value=adds_val,
            )

        # Equal-weighted baseline portfolio return series
        n_obs = len(candidate_returns)
        valid_existing = [r for r in existing_portfolio_returns if len(r) == n_obs]
        if not valid_existing:
            adds_val = cand_sharpe >= 0.5
            return PortfolioImpactReport(
                candidate_id=candidate_id,
                existing_portfolio_sharpe=0.0,
                combined_portfolio_sharpe=round(cand_sharpe, 4),
                incremental_sharpe=round(cand_sharpe, 4),
                max_correlation_with_existing=0.0,
                diversification_benefit_pct=100.0 if adds_val else 0.0,
                marginal_drawdown_contribution_pct=round(_max_drawdown_pct(candidate_returns), 2),
                adds_portfolio_value=adds_val,
            )

        num_exist = len(valid_existing)
        existing_combined = [
            sum(valid_existing[s][i] for s in range(num_exist)) / num_exist
            for i in range(n_obs)
        ]
        ex_sharpe = _compute_sharpe(existing_combined)

        # Combined equal-weighted portfolio return series (existing + candidate)
        num_total = num_exist + 1
        all_series = valid_existing + [candidate_returns]
        combined_returns = [
            sum(all_series[s][i] for s in range(num_total)) / num_total
            for i in range(n_obs)
        ]
        comb_sharpe = _compute_sharpe(combined_returns)
        inc_sharpe = comb_sharpe - ex_sharpe

        # Calculate correlations with existing strategy return series
        correlations = []
        mean_c = statistics.mean(candidate_returns)
        var_c = sum((c - mean_c) ** 2 for c in candidate_returns)

        for ex_ret in valid_existing:
            mean_e = statistics.mean(ex_ret)
            cov = sum((c - mean_c) * (e - mean_e) for c, e in zip(candidate_returns, ex_ret))
            var_e = sum((e - mean_e) ** 2 for e in ex_ret)
            denom = (var_c * var_e) ** 0.5
            r = cov / denom if denom > 0 else 0.0
            correlations.append(r)

        max_corr = max(correlations) if correlations else 0.0
        div_benefit = ((comb_sharpe - ex_sharpe) / ex_sharpe * 100.0) if ex_sharpe > 0 else 0.0
        adds_value = inc_sharpe > 0.05 and max_corr < 0.50 and comb_sharpe >= 0.50

        # Marginal drawdown contribution: % change in portfolio max drawdown
        # from adding the candidate, computed from the real return series.
        mdd_existing = _max_drawdown_pct(existing_combined)
        mdd_combined = _max_drawdown_pct(combined_returns)
        if mdd_existing > 1e-9:
            marginal_dd = ((mdd_combined - mdd_existing) / mdd_existing) * 100.0
        else:
            marginal_dd = mdd_combined  # absolute when baseline has no drawdown

        return PortfolioImpactReport(
            candidate_id=candidate_id,
            existing_portfolio_sharpe=round(ex_sharpe, 4),
            combined_portfolio_sharpe=round(comb_sharpe, 4),
            incremental_sharpe=round(inc_sharpe, 4),
            max_correlation_with_existing=round(max_corr, 4),
            diversification_benefit_pct=round(max(0.0, div_benefit), 2),
            marginal_drawdown_contribution_pct=round(marginal_dd, 2),
            adds_portfolio_value=adds_value,
        )

