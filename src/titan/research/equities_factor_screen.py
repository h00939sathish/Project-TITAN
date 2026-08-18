"""US Equities Cross-Sectional Factor Evaluation and Decision Gate Screen.

Research-only. Evaluates factor pre-registrations against point-in-time multi-asset
data, computing net Sharpe, rank Information Coefficient (IC), turnover friction,
and adverse capacity gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from titan.backtest.factor_simulator import (
    FactorCostModel,
    FactorSimulationResult,
    simulate_factor_portfolio,
)
from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseData,
)
from titan.research.factors import (
    factor_low_volatility,
    factor_momentum_12_1m,
    factor_reversal_12_1m,
    factor_short_term_reversal,
    factor_volatility_adjusted_momentum,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
HYP_DIR = _REPO_ROOT / "research" / "equities" / "hypotheses"
RESULTS_DIR = _REPO_ROOT / "research" / "equities" / "results"


@dataclass(frozen=True)
class FactorPreRegistration:
    hypothesis_id: str
    factor_name: str
    universe: list[str]
    parameters: dict[str, Any]
    cost_label: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    pass_criteria: dict[str, Any]

    def missing_fields(self) -> list[str]:
        missing = []
        for f in (
            "hypothesis_id",
            "factor_name",
            "universe",
            "parameters",
            "cost_label",
            "is_partition",
            "oos_partition",
            "pass_criteria",
        ):
            if not getattr(self, f):
                missing.append(f)
        return missing

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "FactorPreRegistration":
        return FactorPreRegistration(
            hypothesis_id=data.get("hypothesis_id", ""),
            factor_name=data.get("factor_name", ""),
            universe=list(data.get("universe", [])),
            parameters=dict(data.get("parameters", {})),
            cost_label=data.get("cost_label", ""),
            is_partition=dict(data.get("is_partition", {})),
            oos_partition=dict(data.get("oos_partition", {})),
            pass_criteria=dict(data.get("pass_criteria", {})),
        )


def load_factor_preregistration(path: str | Path) -> FactorPreRegistration:
    with open(path, encoding="utf-8") as fh:
        return FactorPreRegistration.from_dict(json.load(fh))


def evaluate_factor_gates(
    oos_res: FactorSimulationResult,
    adverse_res: FactorSimulationResult,
    prereg: FactorPreRegistration,
    *,
    replicated: bool = False,
) -> dict[str, Any]:
    min_sharpe = float(prereg.pass_criteria.get("min_oos_net_sharpe", 1.0))
    min_ic_pos = float(prereg.pass_criteria.get("min_ic_positive_frac", 0.7))
    min_mean_ic = float(prereg.pass_criteria.get("min_mean_rank_ic", 0.05))
    max_turnover = float(prereg.pass_criteria.get("max_monthly_turnover", 0.60))
    max_dd = float(prereg.pass_criteria.get("max_drawdown", 0.15))

    gates = {
        "oos_net_sharpe": bool(oos_res.annualized_net_sharpe >= min_sharpe),
        "rank_ic_fraction": bool(oos_res.ic_positive_fraction >= min_ic_pos),
        "rank_ic_magnitude": bool(oos_res.mean_rank_ic >= min_mean_ic),
        "max_drawdown": bool(oos_res.max_drawdown <= max_dd),
        "turnover_capacity": bool(oos_res.monthly_turnover <= max_turnover),
        "adverse_net_positive": bool(adverse_res.annualized_net_return > 0.0),
        "replication": bool(replicated),
    }

    all_passed = all(gates.values())
    verdict = "candidate" if all_passed else "negative_result"

    return {
        "verdict": verdict,
        "gates": gates,
        "metrics": {
            "annualized_net_sharpe": oos_res.annualized_net_sharpe,
            "annualized_net_return": oos_res.annualized_net_return,
            "mean_rank_ic": oos_res.mean_rank_ic,
            "ic_positive_fraction": oos_res.ic_positive_fraction,
            "monthly_turnover": oos_res.monthly_turnover,
            "max_drawdown": oos_res.max_drawdown,
            "adverse_annualized_net_return": adverse_res.annualized_net_return,
        },
    }


def run_factor_screen(
    universe: EquitiesUniverseData,
    prereg: FactorPreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    missing = prereg.missing_fields()
    if missing:
        raise EquitiesDataError(f"missing pre-registration fields: {missing}")
    if allow_oos_for_parameters:
        raise EquitiesDataError("OOS partition cannot be used for parameter choice")

    prices = universe.prices
    params = prereg.parameters

    # Compute factor scores
    if prereg.factor_name == "momentum_12_1m":
        lookback = int(params.get("lookback_days", 252))
        skip = int(params.get("skip_days", 21))
        scores = factor_momentum_12_1m(prices, lookback=lookback, skip=skip)
    elif prereg.factor_name in ("reversal_12_1m", "cross_sectional_reversal_12_1m_inverse_momentum"):
        lookback = int(params.get("lookback_days", 252))
        skip = int(params.get("skip_days", 21))
        scores = factor_reversal_12_1m(prices, lookback=lookback, skip=skip)
    elif prereg.factor_name == "short_term_reversal_5d":
        window = int(params.get("window_days", 5))
        scores = factor_short_term_reversal(prices, window=window)

    elif prereg.factor_name == "volatility_adjusted_momentum":
        mom_lb = int(params.get("mom_lookback_days", 252))
        skip = int(params.get("skip_days", 21))
        vol_win = int(params.get("vol_window_days", 63))
        scores = factor_volatility_adjusted_momentum(prices, mom_lookback=mom_lb, skip=skip, vol_window=vol_win)
    elif prereg.factor_name == "low_volatility":
        vol_win = int(params.get("window_days", 63))
        scores = factor_low_volatility(prices, window=vol_win)
    else:
        raise EquitiesDataError(f"unrecognized factor {prereg.factor_name}")

    top_k = int(params.get("top_k", 3))
    bottom_k = int(params.get("bottom_k", 3))
    reb_freq = int(params.get("rebalance_freq_days", 21))

    # IS simulation
    is_univ = universe.slice_partition("IS")
    is_res = simulate_factor_portfolio(
        is_univ,
        scores.loc[is_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="IS",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        cost_model=FactorCostModel.standard_us_equity(),
    )

    # OOS simulation
    oos_univ = universe.slice_partition("OOS")
    oos_res = simulate_factor_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        cost_model=FactorCostModel.standard_us_equity(),
    )

    # Adverse Stress OOS simulation
    adverse_res = simulate_factor_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS_ADVERSE",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        cost_model=FactorCostModel.stressed_adverse(),
    )

    # Decision Gates
    gates_eval = evaluate_factor_gates(oos_res, adverse_res, prereg, replicated=replicated)

    bundle = {
        "hypothesis_id": prereg.hypothesis_id,
        "factor_name": prereg.factor_name,
        "manifest_digest": universe.manifest.digest(),
        "is": is_res.to_dict(),
        "oos": oos_res.to_dict(),
        "adverse_oos": adverse_res.to_dict(),
        "gates": gates_eval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / f"{prereg.hypothesis_id}-evidence-bundle.json"
    out_file.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    return bundle
