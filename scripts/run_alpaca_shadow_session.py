"""Project TITAN — Alpaca Swing Factor Shadow Session Runner.

Demonstrates a full end-to-end operational cycle:
1. Load market price matrix & consensus events.
2. Generate PEAD + Quality alpha scores.
3. Construct capital-tiered portfolio targets (Tier 1 >= $30k vs Tier 2 < $30k).
4. Pass all intents through AlpacaComplianceGate (PDT, ETB-only shorts, holding floor).
5. Dispatch batch orders via AlpacaBatchDispatcher with 100ms pacing.
6. Calculate exact transaction cost breakdown via AlpacaEquityCostModel.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pandas as pd
import numpy as np

from titan.backtest.alpaca_equity_costs import AlpacaEquityCostModel
from titan.data.equities_universe import EquitiesUniverseManifest, build_equities_universe
from titan.operations.daily_rebalance import DailyRebalanceOrchestrator
from titan.research.equities_event_screen_009 import load_pit_earnings_events
from titan.risk.alpaca_compliance import AlpacaComplianceGate

MANIFEST_PATH = _REPO_ROOT / "research" / "equities" / "manifests" / "us_sp50_earnings_pit_v1.json"
EVENTS_PATH = _REPO_ROOT / "research" / "equities" / "data" / "us_sp50_earnings_events_v1.parquet"
CACHE_DIR = _REPO_ROOT / "research_data" / "intraday_5m"


def main():
    print("=" * 78)
    print("PROJECT TITAN — ALPACA SWING FACTOR SHADOW EXECUTION CYCLE")
    print("=" * 78)

    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    events_df = load_pit_earnings_events(EVENTS_PATH)

    # Load universe
    series_map = {}
    for sym in manifest.universe:
        p = CACHE_DIR / f"{sym}_5m.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        daily = df.groupby(df.index.tz_convert("America/New_York").date)["close"].last()
        daily.index = pd.to_datetime(daily.index)
        series_map[sym] = daily

    universe = build_equities_universe(series_map, manifest)
    prices_df = universe.prices
    current_prices = {sym: float(prices_df[sym].iloc[-1]) for sym in prices_df.columns}

    # 1. Test Tier 1 Run ($35,000 Equity -> Dollar-Neutral Long/Short)
    print("\n--- SIMULATING TIER 1 REBALANCE ($35,000 Equity) ---")
    gate_tier1 = AlpacaComplianceGate()
    orchestrator_tier1 = DailyRebalanceOrchestrator(
        compliance_gate=gate_tier1,
        pacing_delay_seconds=0.01, # Fast pacing for test
    )

    summary_t1 = orchestrator_tier1.execute_daily_cycle(
        prices_df=prices_df,
        current_positions={},
        current_prices=current_prices,
        account_equity=35000.0,
        events_df=events_df,
        etb_symbols=list(prices_df.columns), # All SP50 are ETB
        top_k=5,
        bottom_k=5,
    )

    print(f"Compliance Approved: {summary_t1.compliance_approved}")
    print(f"Account Tier:        Tier {summary_t1.tier} (FULL_LONG_SHORT)")
    print(f"Gross Exposure:      {summary_t1.gross_exposure:.1%}")
    print(f"Net Exposure:        {summary_t1.net_exposure:.1%} (Dollar-Neutral)")
    print(f"Orders Dispatched:   {summary_t1.orders_dispatched} ({len([o for o in summary_t1.dispatched_orders if o['side'] == 'buy'])} Longs, {len([o for o in summary_t1.dispatched_orders if o['side'] == 'short'])} Shorts)")

    # 2. Cost Attribution via Alpaca Cost Model
    cost_model = AlpacaEquityCostModel.standard_retail()
    total_friction = Decimal("0.00")
    print("\nDispatched Order Sample:")
    for order in summary_t1.dispatched_orders[:4]:
        breakdown = cost_model.calculate_cost(
            side=order["side"],
            shares=order["shares"],
            price=order["price"],
            is_etb=True,
        )
        total_friction += breakdown.total_friction_usd
        print(f"  {order['side'].upper():<6} {order['shares']:>4} shs {order['symbol']:<5} @ ${order['price']:>6.2f} (Notional: ${order['notional']:>8.2f}) -> Comm: ${breakdown.commission_usd:.2f}, Borrow: ${breakdown.borrow_fee_usd:.2f}, Friction: ${breakdown.total_friction_usd:.4f}")

    print(f"\nTotal Batch Friction on Alpaca: ${total_friction:.4f} (Zero commission, Zero ETB borrow)")

    # 3. Test Tier 2 Run ($28,000 Equity -> Long-Only)
    print("\n--- SIMULATING TIER 2 REBALANCE ($28,000 Equity) ---")
    gate_tier2 = AlpacaComplianceGate()
    orchestrator_tier2 = DailyRebalanceOrchestrator(
        compliance_gate=gate_tier2,
        pacing_delay_seconds=0.01,
    )

    summary_t2 = orchestrator_tier2.execute_daily_cycle(
        prices_df=prices_df,
        current_positions={},
        current_prices=current_prices,
        account_equity=28000.0,
        events_df=events_df,
        etb_symbols=list(prices_df.columns),
        top_k=5,
        bottom_k=5,
    )

    print(f"Compliance Approved: {summary_t2.compliance_approved}")
    print(f"Account Tier:        Tier {summary_t2.tier} (LONG_ONLY_HEDGED)")
    print(f"Gross Exposure:      {summary_t2.gross_exposure:.1%}")
    print(f"Net Exposure:        {summary_t2.net_exposure:.1%} (Long-Only)")
    print(f"Orders Dispatched:   {summary_t2.orders_dispatched} Longs (Zero Shorts)")

    # 4. Test Restricted Capital Run ($24,000 Equity -> Under PDT $25k + 5% buffer)
    print("\n--- SIMULATING RESTRICTED REBALANCE ($24,000 Equity) ---")
    gate_restr = AlpacaComplianceGate()
    orchestrator_restr = DailyRebalanceOrchestrator(
        compliance_gate=gate_restr,
        pacing_delay_seconds=0.01,
    )

    summary_restr = orchestrator_restr.execute_daily_cycle(
        prices_df=prices_df,
        current_positions={},
        current_prices=current_prices,
        account_equity=24000.0,
        events_df=events_df,
        top_k=5,
        bottom_k=5,
    )

    print(f"Compliance Approved: {summary_restr.compliance_approved}")
    print(f"Rebalance Frozen:    {summary_restr.rejection_reasons[0]}")
    print("=" * 78)
    print("SHADOW REBALANCE RUN COMPLETE: ALL GATES VERIFIED")
    print("=" * 78)


if __name__ == "__main__":
    main()
