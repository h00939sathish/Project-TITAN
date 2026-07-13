### Task C1c: Kill switch persistence + Python risk config loader + CLI

**Files:**
- Create: `src/titan/risk/__init__.py`
- Create: `src/titan/risk/limits.py` (Python config loader)
- Create: `tests/risk/test_gate.py`
- Create: `tests/risk/test_kill_switch.py`
- Modify: `src/titan/cli.py` (add risk commands)
- Create: `tests/risk/__init__.py`

**Interfaces:**
- Consumes: `titan._core.RiskConfig`, `titan._core.RiskGate`, `titan._core.TradingState`, `titan._core.KillSwitchState`, `titan._core.RiskVerdict`, `titan._core.RiskReasonCode`, `titan._core.TradeIntent`, `titan._core.Money`
- Produces: Python risk package, config loader, CLI commands, comprehensive Python tests

**Exact API signatures (check source code for exact fields):**

- `Money("1000000", "USD")` — takes (amount: str, currency: str)
- `RiskConfig(eligibility: list[str], max_notional: Money, max_qty: int, max_pos: int, max_exposure: Money, drawdown: float, daily_loss: Money, freshness: int)`
- `RiskGate(config)` — constructor  
- `gate.evaluate(intent, pos_size: int|None, exposure: Money|None, drawdown: float|None, daily_loss: Money|None) -> RiskVerdict`
- `gate.set_trading_state(TradingState.Halted)`
- `gate.trigger_kill_switch()`, `gate.release_initiated()`, `gate.release_completed()`
- `gate.kill_switch` — attribute (KillSwitchState enum value)
- `gate.trading_state` — attribute (TradingState enum value)
- `TradeIntent(strategy_id, package_digest, account_id, instrument_id, side, quantity, order_type, time_in_force, risk_profile_version, price=None, stop_price=None)`
  - Note: quantity is `str`, side is `str`, price is `str|None`
- `RiskVerdict.accepted` (bool), `.reason` (RiskReasonCode|None), `.reason_detail` (str)
- `PortfolioEngine("USD", Money("100000", "USD"))`
- `engine.apply_fill("AAPL", "buy", 100, Money("150", "USD"))`
- `engine.get_position("AAPL")` -> Position | None
- `engine.get_cash_balance()` -> Money
- `engine.total_gross_exposure()` -> Money

**What to build:**

1. **`src/titan/risk/__init__.py`** — package init, re-export key names (optional, can be empty).

2. **`tests/risk/__init__.py`** — empty package init.

3. **`src/titan/risk/limits.py`** — Python config loader:

```python
"""Loads risk configuration from dict/JSON into Rust RiskConfig objects."""

from titan._core import Money, RiskConfig

DEFAULT_CFG = {
    "instrument_eligibility": [],
    "max_order_notional": ("1000000", "USD"),
    "max_order_quantity": 10000,
    "max_position_size": 50000,
    "max_gross_exposure": ("10000000", "USD"),
    "max_drawdown_fraction": 0.10,
    "max_daily_loss": ("50000", "USD"),
    "data_freshness_threshold_ms": 5000,
}

def load_config(data: dict | None = None) -> RiskConfig:
    """Load risk config from a dict, falling back to defaults for missing keys."""
    cfg = {**DEFAULT_CFG, **(data or {})}
    return RiskConfig(
        cfg["instrument_eligibility"],
        Money(*cfg["max_order_notional"]),
        cfg["max_order_quantity"],
        cfg["max_position_size"],
        Money(*cfg["max_gross_exposure"]),
        cfg["max_drawdown_fraction"],
        Money(*cfg["max_daily_loss"]),
        cfg["data_freshness_threshold_ms"],
    )
```

4. **`tests/risk/test_gate.py`** — Python tests for risk gate:

Write tests that demonstrate the full risk gate evaluation pipeline from Python:

```python
"""Tests for risk gate from Python."""

from titan._core import (
    Money, RiskConfig, RiskGate, TradingState,
    KillSwitchState, TradeIntent, RiskVerdict, RiskReasonCode,
    PortfolioEngine,
)

# Use the actual TradeIntent constructor signature:
# TradeIntent(strategy_id, package_digest, account_id, instrument_id,
#             side, quantity, order_type, time_in_force, risk_profile_version,
#             price=None, stop_price=None)

def make_intent(instrument="AAPL", side="BUY", quantity="100", price="150") -> TradeIntent:
    return TradeIntent("strat-v1", "abc123", "acct-1", instrument,
                       side, quantity, "LIMIT", "DAY", "1.0",
                       price=price)

def make_default_gate() -> RiskGate:
    config = RiskConfig([], Money("1000000", "USD"), 10000, 50000,
                        Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000)
    return RiskGate(config)

class TestRiskGate:
    def test_accepts_valid_intent(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert verdict.accepted
        assert verdict.reason is None

    def test_rejects_when_kill_switch_triggered(self):
        gate = make_default_gate()
        gate.trigger_kill_switch()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.KillSwitchTriggered

    def test_rejects_when_trading_halted(self):
        gate = make_default_gate()
        gate.set_trading_state(TradingState.Halted)
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.TradingHalted

    def test_rejects_instrument_not_eligible(self):
        gate = RiskGate(RiskConfig(["MSFT"], Money("1000000", "USD"), 10000, 50000,
                        Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000))
        verdict = gate.evaluate(make_intent(instrument="AAPL"), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.InstrumentNotEligible

    def test_rejects_notional_exceeded(self):
        gate = RiskGate(RiskConfig([], Money("100", "USD"), 10000, 50000,
                        Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000))
        verdict = gate.evaluate(make_intent(quantity="10", price="50"), None, None, None, None)
        # 10 * 50 = 500 > 100 → rejected
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.OrderNotionalExceeded

    def test_rejects_quantity_exceeded(self):
        gate = RiskGate(RiskConfig([], Money("1000000", "USD"), 10, 50000,
                        Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000))
        verdict = gate.evaluate(make_intent(quantity="100"), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.OrderQuantityExceeded

    def test_rejects_position_size_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), 60000, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.PositionLimitExceeded

    def test_rejects_gross_exposure_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, Money("20000000", "USD"), None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.GrossExposureExceeded

    def test_rejects_drawdown_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, 0.50, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.DrawdownExceeded

    def test_rejects_daily_loss_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, None, Money("100000", "USD"))
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.DailyLossExceeded

    def test_kill_switch_lifecycle(self):
        gate = make_default_gate()
        assert gate.kill_switch == KillSwitchState.Armed
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered
        gate.release_initiated()
        assert gate.kill_switch == KillSwitchState.Releasing
        gate.release_completed()
        assert gate.kill_switch == KillSwitchState.Released
        # After full lifecycle, should accept intents again
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert verdict.accepted

    def test_trading_state_lifecycle(self):
        gate = make_default_gate()
        assert gate.trading_state == TradingState.Active
        gate.set_trading_state(TradingState.Halted)
        assert gate.trading_state == TradingState.Halted
        gate.set_trading_state(TradingState.Active)
        assert gate.trading_state == TradingState.Active

    def test_portfolio_checks_skipped_when_none(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert verdict.accepted  # all portfolio checks skipped

    def test_risk_verdict_has_correct_fields(self):
        gate = make_default_gate()
        gate.trigger_kill_switch()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert hasattr(verdict, 'accepted')
        assert hasattr(verdict, 'reason')
        assert hasattr(verdict, 'reason_detail')
        assert verdict.accepted is False
        assert verdict.reason is not None
        assert len(verdict.reason_detail) > 0

    def test_full_gate_to_portfolio_integration(self):
        """End-to-end: create portfolio, apply fill, compute exposure, check gate."""
        gate = make_default_gate()
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        portfolio.apply_fill("AAPL", "buy", 100, Money("150", "USD"))
        snapshot = portfolio.get_snapshot()
        verdict = gate.evaluate(
            make_intent(quantity="50", price="160"),
            snapshot.position_size,
            snapshot.gross_exposure,
            snapshot.drawdown_fraction,
            snapshot.daily_realized_loss,
        )
        assert verdict.accepted
```

Important: Test against the actual Rust module. Make sure the test files are runnable with `python -m pytest tests/risk/ -v`. The file paths must be `tests/risk/test_gate.py`.

5. **`tests/risk/test_kill_switch.py`** — dedicated kill switch tests:

```python
"""Tests for kill switch behavior."""

from titan._core import KillSwitchState, RiskConfig, RiskGate

def make_gate():
    return RiskGate(RiskConfig([], Money("1000000", "USD"), 10000, 50000,
                               Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000))

class TestKillSwitch:
    def test_default_armed(self):
        gate = make_gate()
        assert gate.kill_switch == KillSwitchState.Armed

    def test_trigger_changes_state(self):
        gate = make_gate()
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered

    def test_trigger_blocks_routing(self):
        gate = make_gate()
        # This is tested via RiskGate.evaluate, but we verify directly
        assert not KillSwitchState.Armed.blocks_routing()
        assert KillSwitchState.Triggered.blocks_routing()
        assert KillSwitchState.Releasing.blocks_routing()
        assert not KillSwitchState.Released.blocks_routing()

    def test_full_lifecycle(self):
        ks = KillSwitchState.Armed
        ks = KillSwitchState.Triggered
        ks = KillSwitchState.Releasing
        ks = KillSwitchState.Released
        ks = KillSwitchState.Armed

    def test_release_re_trigger(self):
        gate = make_gate()
        gate.trigger_kill_switch()
        gate.release_initiated()
        # Can re-trigger from Releasing
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered
```

6. **`src/titan/cli.py`** — update CLI with risk commands:

```python
"""CLI entry point for Project TITAN."""

import click
from titan._core import version, RiskConfig, RiskGate, TradingState, KillSwitchState
from titan.risk.limits import load_config

@click.group()
def cli():
    """Project TITAN CLI."""
    pass

@cli.command()
def version_cmd():
    """Print the TITAN core library version."""
    click.echo(f"TITAN Core v{version()}")

@cli.group()
def risk():
    """Risk management commands."""
    pass

@risk.command()
def status():
    """Display current risk state (in-memory only in Phase C)."""
    gate = RiskGate(load_config())
    state_name = str(gate.trading_state)
    ks_name = str(gate.kill_switch)
    click.echo(f"Trading state: {state_name}")
    click.echo(f"Kill switch: {ks_name}")
    click.echo("Note: Phase C uses in-memory state. Persistence coming in later phases.")

@risk.command()
@click.option("--reason", default="operator", help="Reason for kill switch")
def halt(reason):
    """Trigger kill switch — halt all trading in-memory."""
    click.echo(f"Kill switch triggered: {reason}")
    click.echo("Trading halted. Use 'titan risk release' after reconciliation.")

@risk.command()
def release():
    """Release kill switch after reconciliation."""
    click.echo("Kill switch released. Trading resumed.")

if __name__ == "__main__":
    cli()
```

   Note: read the existing cli.py first to understand its current structure. Merge changes cleanly without breaking existing commands.

**Exit criteria:** All tests pass with `python -m pytest tests/risk/ -v`. CLI runs without errors.
