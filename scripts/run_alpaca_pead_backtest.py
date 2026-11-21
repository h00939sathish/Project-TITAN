"""Project TITAN — Alpaca Retail Empirical Factor Backtest Runner.

Simulates the PEAD Factor Screen on the S&P 50 liquid universe comparing:
1. Baseline IBKR Pro Fixed Costs ($0.005/share, 50 bps borrow)
2. Alpaca Retail Schedule ($0 commission, $0 ETB borrow, 1 bps spread)
3. Alpaca Adversarial Stress Schedule (3 bps spread, 1.5 bps slippage)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from titan.backtest.alpaca_equity_costs import AlpacaEquityCostModel
from titan.backtest.factor_simulator import (
    FactorCostModel,
    simulate_factor_portfolio,
)
from titan.data.equities_universe import (
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.equities_event_screen_009 import (
    calculate_pit_pead_scores,
    load_factor_preregistration,
    load_pit_earnings_events,
    simulate_pit_pead_portfolio,
)

CACHE_DIR = _REPO_ROOT / "research_data" / "intraday_5m"
MANIFEST_PATH = _REPO_ROOT / "research" / "equities" / "manifests" / "us_sp50_earnings_pit_v1.json"
EVENTS_PATH = _REPO_ROOT / "research" / "equities" / "data" / "us_sp50_earnings_events_v1.parquet"
PREREG_PATH = _REPO_ROOT / "research" / "equities" / "hypotheses" / "EQ-009-prereg.json"


def load_daily_prices(symbols: list[str]) -> dict[str, pd.Series]:
    series_map: dict[str, pd.Series] = {}
    for sym in symbols:
        p = CACHE_DIR / f"{sym}_5m.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        ny_index = df.index.tz_convert("America/New_York")
        df["date"] = ny_index.date
        daily = df.groupby("date")["close"].last()
        daily.index = pd.to_datetime(daily.index)
        series_map[sym] = daily
    return series_map


def main() -> None:
    print("=" * 78, flush=True)
    print("PROJECT TITAN — ALPACA RETAIL FACTOR BACKTEST & FRICTION ANALYSIS", flush=True)
    print("=" * 78, flush=True)

    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    prereg = load_factor_preregistration(PREREG_PATH)
    events_df = load_pit_earnings_events(EVENTS_PATH)

    series_map = load_daily_prices(manifest.universe)
    if len(series_map) < len(manifest.universe):
        print(f"Warning: Only {len(series_map)} of {len(manifest.universe)} price caches found.")
        # Filter manifest universe to available symbols
        valid_symbols = [s for s in manifest.universe if s in series_map]
        manifest = EquitiesUniverseManifest(
            dataset_name=manifest.dataset_name,
            asset_class=manifest.asset_class,
            source=manifest.source,
            universe=valid_symbols,
            timezone=manifest.timezone,
            calendar=manifest.calendar,
            coverage_from=manifest.coverage_from,
            coverage_to=manifest.coverage_to,
            is_partition=manifest.is_partition,
            oos_partition=manifest.oos_partition,
            fee_schedule=manifest.fee_schedule,
            retrieval_ts_utc=manifest.retrieval_ts_utc,
            checksums=manifest.checksums,
        )

    universe = build_equities_universe(series_map, manifest)
    print(f"Universe: {len(manifest.universe)} liquid equities across {len(universe.prices)} trading days.")

    # Ingest PIT PEAD Scores
    scores = calculate_pit_pead_scores(universe.prices, events_df, holding_days=42)
    oos_univ = universe.slice_partition("OOS")
    oos_scores = scores.loc[oos_univ.prices.index]

    # 1. Baseline IBKR Pro
    print("\n[1/3] Running OOS Backtest under Baseline IBKR Pro Costs...", flush=True)
    ibkr_cost = FactorCostModel.baseline_ibkr_pro_fixed()
    res_ibkr = simulate_pit_pead_portfolio(
        oos_univ,
        oos_scores,
        hypothesis_id="PEAD_OOS_IBKR",
        cost_model=ibkr_cost,
    )

    # 2. Alpaca Retail ($0 comm, $0 ETB borrow)
    print("[2/3] Running OOS Backtest under Alpaca Retail Schedule...", flush=True)
    alpaca_model = AlpacaEquityCostModel.standard_retail()
    alpaca_sched = alpaca_model.to_venue_cost_schedule()
    res_alpaca = simulate_pit_pead_portfolio(
        oos_univ,
        oos_scores,
        hypothesis_id="PEAD_OOS_ALPACA",
        cost_model=alpaca_sched,
    )

    # 3. Alpaca Adversarial Stress
    print("[3/3] Running OOS Backtest under Alpaca Stressed Adverse Schedule...", flush=True)
    alpaca_stress_model = AlpacaEquityCostModel.stressed_adverse()
    alpaca_stress_sched = alpaca_stress_model.to_venue_cost_schedule()
    res_stress = simulate_pit_pead_portfolio(
        oos_univ,
        oos_scores,
        hypothesis_id="PEAD_OOS_STRESS",
        cost_model=alpaca_stress_sched,
    )

    print("\n" + "=" * 78)
    print("EMPIRICAL COMPARISON SCORECARD (2023 - 2024 Out-of-Sample)")
    print("=" * 78)
    print(f"{'Metric':<25} | {'IBKR Pro Fixed':<15} | {'Alpaca Retail':<15} | {'Alpaca Stressed':<15}")
    print("-" * 78)
    print(f"{'Annualized Net Return':<25} | {res_ibkr.annualized_net_return:<15.2%} | {res_alpaca.annualized_net_return:<15.2%} | {res_stress.annualized_net_return:<15.2%}")
    print(f"{'Annualized Net Sharpe':<25} | {res_ibkr.annualized_net_sharpe:<15.2f} | {res_alpaca.annualized_net_sharpe:<15.2f} | {res_stress.annualized_net_sharpe:<15.2f}")
    print(f"{'Max Drawdown':<25} | {res_ibkr.max_drawdown:<15.2%} | {res_alpaca.max_drawdown:<15.2%} | {res_stress.max_drawdown:<15.2%}")
    print(f"{'Monthly Turnover':<25} | {res_ibkr.monthly_turnover:<15.2%} | {res_alpaca.monthly_turnover:<15.2%} | {res_stress.monthly_turnover:<15.2%}")
    print(f"{'Total Commissions ($)':<25} | ${res_ibkr.costs.get('commission_usd', 0.0):<14.2f} | ${res_alpaca.costs.get('commission_usd', 0.0):<14.2f} | ${res_stress.costs.get('commission_usd', 0.0):<14.2f}")
    print(f"{'Short Borrow Cost ($)':<25} | ${res_ibkr.costs.get('borrow_usd', 0.0):<14.2f} | ${res_alpaca.costs.get('borrow_usd', 0.0):<14.2f} | ${res_stress.costs.get('borrow_usd', 0.0):<14.2f}")
    print(f"{'Total Friction ($)':<25} | ${res_ibkr.costs.get('total_friction_usd', 0.0):<14.2f} | ${res_alpaca.costs.get('total_friction_usd', 0.0):<14.2f} | ${res_stress.costs.get('total_friction_usd', 0.0):<14.2f}")
    print("=" * 78)


if __name__ == "__main__":
    main()
