"""CLI entry point for Project TITAN."""

import click
from titan._core import version, RiskConfig, RiskGate, TradingState, KillSwitchState
from titan.risk.limits import load_config


@click.group()
def cli() -> None:
    """Project TITAN CLI."""
    pass


@cli.command()
def version_cmd() -> None:
    """Print the TITAN core library version."""
    click.echo(f"TITAN Core v{version()}")


@cli.group()
def risk() -> None:
    """Risk management commands."""
    pass


@risk.command()
def status() -> None:
    """Display current risk state."""
    from titan._core import EventStore
    store = EventStore(".titan_state.db")
    gate = RiskGate.load_or_default(load_config(), store)
    state_name = str(gate.trading_state)
    ks_name = str(gate.kill_switch)
    click.echo(f"Trading state: {state_name}")
    click.echo(f"Kill switch: {ks_name}")
    click.echo("Use 'titan metrics' to inspect runtime metrics.")


@risk.command()
@click.option("--reason", default="operator", help="Reason for kill switch")
def halt(reason: str) -> None:
    """Trigger kill switch — halt all trading."""
    from titan._core import EventStore
    store = EventStore(".titan_state.db")
    gate = RiskGate.load_or_default(load_config(), store)
    try:
        gate.trigger_kill_switch()
    except ValueError as e:
        click.echo(f"Error: {e}")
        return
    gate.persist_state(store)
    click.echo(f"Kill switch triggered: {reason}")
    click.echo("Trading halted. Use 'titan risk release' after reconciliation.")


@risk.command()
@click.confirmation_option(prompt="Are you sure you want to release the kill switch?")
def release() -> None:
    """Release kill switch after reconciliation."""
    from titan._core import EventStore
    store = EventStore(".titan_state.db")
    config = load_config()
    gate = RiskGate.load_or_default(config, store)

    if not gate.kill_switch.blocks_routing():
        click.echo("Kill switch is already released.")
        return

    # ponytail: broker reachability check only. Engine does the real reconciliation.
    try:
        from titan.execution.simulated_adapter import SimulatedAdapter
        adapter = SimulatedAdapter()
        adapter.health()
    except Exception:
        click.echo("Warning: broker adapter unreachable, relying on confirmation prompt.", err=True)

    gate.release_initiated()
    gate.release_completed()
    gate.set_trading_state(TradingState.Active)
    gate.persist_state(store)
    click.echo("Kill switch released. Trading resumed.")


@cli.group()
def metrics() -> None:
    """Metrics commands."""
    pass


@metrics.command()
def prometheus() -> None:
    """Start Prometheus metrics exporter (blocking)."""
    from titan.operations._metrics_integration import get_registry
    from titan.operations.export import PrometheusExporter
    PrometheusExporter(get_registry()).start()
    port = int(__import__("os").environ.get("PROMETHEUS_PORT", "9090"))
    click.echo(f"Prometheus exporter running on :{port}")
    import threading
    threading.Event().wait()


@metrics.command()
def dump() -> None:
    """Dump all metrics as JSON."""
    from titan.operations._metrics_integration import get_registry
    click.echo(get_registry().dump_json())


@cli.group()
def recovery() -> None:
    """Recovery commands."""
    pass


@recovery.command()
def restart() -> None:
    """Restart from event store: replay, reconcile, transition."""
    from titan.recovery.restart import recover_from_event_store, reconcile_on_boot, transition_on_boot
    click.echo("Recovering from event store...")
    state = recover_from_event_store()
    click.echo("Reconciling...")
    recon = reconcile_on_boot(state["portfolio"], state["adapter"], state["recon_engine"])
    click.echo(f"Reconciliation {'clean' if not recon['has_drift'] else 'drift detected'}")
    click.echo(f"Drift count: {recon['drift_count']}")
    if state.get("store_was_empty"):
        click.echo("WARNING: Event store was empty — state loss detected, forcing HALTED")
    transition = transition_on_boot(recon, state["risk_gate"], store_was_empty=state.get("store_was_empty", False))
    click.echo(f"System state: {transition}")


@metrics.command()
def health() -> None:
    """Assess system health from metrics."""
    from titan.operations._metrics_integration import (
        get_registry, intents_evaluated, intents_rejected,
        orders_filled, orders_submitted, drift_count_critical,
    )
    reg = get_registry()
    snap = reg.snapshot()
    risk_working = snap.get("intents_evaluated", 0) > 0
    orders_progressing = snap.get("orders_filled", 0) > 0 or snap.get("orders_submitted", 0) > 0
    broker_matches = snap.get("drift_count_critical", 0) == 0
    click.echo(f"Risk working: {'YES' if risk_working else 'NO'}")
    click.echo(f"Orders progressing: {'YES' if orders_progressing else 'NO'}")
    click.echo(f"Broker truth matches: {'YES' if broker_matches else 'NO'}")


if __name__ == "__main__":
    cli()
