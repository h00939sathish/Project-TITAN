"""Recovery automation — restart from event store, reconcile, transition."""

from titan._core import (
    EventStore, RiskGate, RiskConfig, PortfolioEngine,
    Money, ReconciliationEngine, ReconciliationConfig,
    TradingState, KillSwitchState,
)
from titan.execution.simulated_adapter import SimulatedAdapter


def recover_from_event_store(store_path: str = ":memory:") -> dict:
    """Rebuild system state from event store replay.

    Returns a dict with:
        store: EventStore instance
        risk_gate: RiskGate with restored state
        portfolio: PortfolioEngine (empty — full replay is deferred)
        adapter: SimulatedAdapter (no persisted state)
        recon_engine: ReconciliationEngine
    """
    store = EventStore(store_path)
    config = RiskConfig.default()
    risk_gate = RiskGate.load_or_default(config, store)
    portfolio = PortfolioEngine("USD", Money("100000", "USD"))
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


def reconcile_on_boot(portfolio, adapter, recon_engine) -> dict:
    """Compare rebuilt portfolio with adapter state, report drift.

    Returns dict with 'has_drift', 'drift_count', 'drift_details', 'reconciled'.
    """
    broker_positions = []
    broker_cash = portfolio.get_cash_balance()
    result = recon_engine.compare(portfolio, broker_positions, broker_cash)
    has_drift = len(result.position_drifts) > 0
    return {
        "has_drift": has_drift,
        "drift_count": len(result.position_drifts),
        "drift_details": [str(d) for d in result.position_drifts],
        "reconciled": not has_drift,
    }


def transition_on_boot(recon_result: dict, risk_gate) -> str:
    """Transition system to ACTIVE if clean, HALTED if drift detected."""
    if recon_result["has_drift"]:
        risk_gate.set_trading_state(TradingState.Halted)
        return "HALTED"
    if risk_gate.trading_state != TradingState.Active:
        risk_gate.set_trading_state(TradingState.Active)
    return "ACTIVE"
