"""Recovery automation — restart from event store, reconcile, transition."""

from typing import Any

from titan._core import (
    EventStore, RiskGate, RiskConfig, PortfolioEngine,
    Money, ReconciliationEngine, ReconciliationConfig,
    TradingState, KillSwitchState, ReconciliationDriftSeverity,
)

from titan.execution.simulated_adapter import SimulatedAdapter


import json


def replay_portfolio_events(store: EventStore, portfolio: PortfolioEngine) -> int:
    """Replay OrderFilled events from EventStore to rebuild portfolio state.

    Returns the number of replayed fill events.
    """
    events = store.replay_by_type("OrderFilled")
    replayed_count = 0

    for envelope in events:
        try:
            data = json.loads(envelope.payload)
            inst_id = data.get("instrument_id")
            side = data.get("side", "").lower()
            qty = int(data.get("filled_quantity", data.get("quantity", 0)))
            price_str = str(data.get("fill_price", data.get("price", "0")))

            if inst_id and side in ("buy", "sell") and qty > 0:
                portfolio.apply_fill(
                    instrument_id=inst_id,
                    side=side,
                    quantity=qty,
                    price=Money(price_str, "USD"),
                )
                replayed_count += 1
        except Exception:
            pass

    return replayed_count


def recover_from_event_store(store_path: str = ":memory:") -> dict:
    """Rebuild system state from event store replay.

    Returns a dict with:
        store: EventStore instance
        risk_gate: RiskGate with restored state
        portfolio: PortfolioEngine with replayed state
        adapter: SimulatedAdapter (no persisted state)
        recon_engine: ReconciliationEngine
    """
    store = EventStore(store_path)
    config = RiskConfig.default()
    risk_gate = RiskGate.load_or_default(config, store)
    portfolio = PortfolioEngine("USD", Money("100000", "USD"))
    replay_portfolio_events(store, portfolio)
    adapter = SimulatedAdapter()
    recon_engine = ReconciliationEngine(
        ReconciliationConfig(
            critical_drift_fraction=0.05,
            warning_drift_fraction=0.01,
        )
    )
    return {
        "store": store,
        "risk_gate": risk_gate,
        "portfolio": portfolio,
        "adapter": adapter,
        "recon_engine": recon_engine,
    }



def reconcile_on_boot(portfolio: PortfolioEngine, adapter: Any,
                       recon_engine: ReconciliationEngine) -> dict[str, Any]:
    """Compare rebuilt portfolio with adapter state, report drift.

    Fetches broker positions/cash from adapter if available.
    Returns dict with 'has_drift', 'drift_count', 'drift_details', 'reconciled'.
    """
    broker_positions: list[Any] = []
    broker_cash = portfolio.get_cash_balance()
    snapshot_fetch_failed = False
    if hasattr(adapter, 'positions'):
        try:
            pos_snap = adapter.positions("paper-1")
            broker_positions = pos_snap.positions
        except Exception:
            snapshot_fetch_failed = True
    if hasattr(adapter, 'holdings'):
        try:
            broker_cash = adapter.holdings("paper-1").cash
        except Exception:
            snapshot_fetch_failed = True
    if snapshot_fetch_failed:
        return {
            "has_drift": True,
            "drift_count": 0,
            "drift_details": ["broker truth snapshot unavailable"],
            "reconciled": False,
            "snapshot_fetch_failed": True,
        }
    result = recon_engine.compare(portfolio, broker_positions, broker_cash)
    has_drift = result.severity != ReconciliationDriftSeverity.InSync
    non_zero_drifts = [d for d in result.position_drifts if getattr(d, 'quantity_drift', 0) > 0]

    return {
        "has_drift": has_drift,
        "drift_count": len(non_zero_drifts),
        "drift_details": [str(d) for d in non_zero_drifts],
        "reconciled": not has_drift,
    }



def transition_on_boot(recon_result: dict[str, Any], risk_gate: RiskGate) -> str:
    """Transition system to ACTIVE if clean, HALTED if drift or fetch failure."""
    if recon_result.get("snapshot_fetch_failed"):
        if risk_gate.trading_state != TradingState.Halted:
            risk_gate.set_trading_state(TradingState.Halted)
        return "HALTED (broker truth unavailable)"
    if recon_result["has_drift"]:
        if risk_gate.trading_state != TradingState.Halted:
            risk_gate.set_trading_state(TradingState.Halted)
        return "HALTED (drift)"
    if risk_gate.trading_state != TradingState.Active:
        risk_gate.set_trading_state(TradingState.Active)
    return "ACTIVE"

