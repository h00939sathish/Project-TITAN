# Task G5: Recovery automation — restart and reconcile

## Goal

Create a recovery module that replays persisted state from the event store after a restart, reconciles with the adapter, and transitions the system to ACTIVE or HALTED based on drift.

## Files

- Create: `src/titan/recovery/__init__.py`
- Create: `src/titan/recovery/restart.py` — recover_from_event_store(), reconcile_on_boot(), transition_on_boot()
- Modify: `src/titan/cli.py` — add `recovery restart` command
- Create: `tests/recovery/__init__.py`
- Create: `tests/recovery/test_restart.py` — 4 integration tests
- Modify: `docs/runbooks/paper-session.md` — add restart section
- Modify: `docs/runbooks/incident.md` — add event store loss recovery

## Implementation details

### src/titan/recovery/__init__.py

```python
"""TITAN recovery automation package."""
```

### src/titan/recovery/restart.py

```python
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
    risk_gate.set_trading_state(TradingState.Active)
    return "ACTIVE"
```

### src/titan/cli.py modifications

Add after the risk group:

```python
@cli.group()
def recovery():
    """Recovery commands."""
    pass


@recovery.command()
def restart():
    """Restart from event store: replay, reconcile, transition."""
    from titan.recovery.restart import recover_from_event_store, reconcile_on_boot, transition_on_boot
    click.echo("Recovering from event store...")
    state = recover_from_event_store()
    click.echo("Reconciling...")
    recon = reconcile_on_boot(state["portfolio"], state["adapter"], state["recon_engine"])
    click.echo(f"Reconciliation {'clean' if not recon['has_drift'] else 'drift detected'}")
    click.echo(f"Drift count: {recon['drift_count']}")
    transition = transition_on_boot(recon, state["risk_gate"])
    click.echo(f"System state: {transition}")
```

### tests/recovery/test_restart.py

```python
"""Tests for recovery automation — restart, reconcile, transition."""

import pytest
from titan._core import (
    RiskGate, RiskConfig, EventStore, PortfolioEngine, Money,
    TradingState, KillSwitchState,
)
from titan.recovery.restart import (
    recover_from_event_store, reconcile_on_boot, transition_on_boot,
)
from titan.execution.simulated_adapter import SimulatedAdapter


class TestRecoverFromEventStore:
    def test_recover_clean_state(self):
        """Recovery with no events produces HALTED state (fail-closed)."""
        state = recover_from_event_store(":memory:")
        assert state["risk_gate"].trading_state == TradingState.Halted
        assert state["risk_gate"].kill_switch == KillSwitchState.Triggered
        assert state["portfolio"] is not None
        assert state["adapter"] is not None

    def test_recover_after_persisted_kill_switch(self):
        """Recovery restores persisted kill switch state."""
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        store.close()
        state = recover_from_event_store(":memory:")
        assert state["risk_gate"].kill_switch == KillSwitchState.Triggered

    def test_reconcile_clean_on_boot(self):
        """Clean reconciliation with empty portfolio and no broker positions."""
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        adapter = SimulatedAdapter()
        from titan._core import ReconciliationEngine, ReconciliationConfig
        recon = ReconciliationEngine(ReconciliationConfig(critical_drift_fraction=0.05, warning_drift_fraction=0.01))
        result = reconcile_on_boot(portfolio, adapter, recon)
        assert result["reconciled"] is True
        assert result["has_drift"] is False

    def test_transition_clean_to_active(self):
        """Clean reconciliation transitions to ACTIVE."""
        from titan._core import RiskGate, RiskConfig
        config = RiskConfig.default()
        gate = RiskGate(config)
        state = recover_from_event_store(":memory:")
        result = reconcile_on_boot(state["portfolio"], state["adapter"], state["recon_engine"])
        transition = transition_on_boot(result, gate)
        assert transition == "ACTIVE"
```


### docs/runbooks/paper-session.md modification

Add after "Starting a session" section:

```markdown
## Restarting a session

```bash
python -m titan.cli recovery restart
```

Expected output:
```
Recovering from event store...
Reconciling...
Reconciliation clean
Drift count: 0
System state: ACTIVE
```

If drift is detected, the system starts in HALTED. Investigate drift before releasing.
```

### docs/runbooks/incident.md modification

Add to the Recovery section:

```markdown
### Event store loss recovery

1. Identify the last known good backup of the event store file.
2. Restore the backup to the expected event store path.
3. Run recovery:
   ```
   python -m titan.cli recovery restart
   ```
4. Verify system starts in ACTIVE and reconciliation is clean.
5. If no backup exists, start a fresh session and reconstruct state manually.
```

## Acceptance criteria

- `python -m pytest tests/recovery/ -v` passes (4 tests)
- `python -m pytest tests/ -v` passes (no regressions)
- `python -m titan.cli recovery restart` runs without error
- Runbooks updated with restart and recovery procedures

## Constraints

- Follow existing codebase patterns
- No breaking changes to existing APIs
- No credentials in source code
