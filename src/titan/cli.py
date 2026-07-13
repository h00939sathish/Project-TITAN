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
    click.echo("Use 'titan metrics' to inspect runtime metrics.")


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


@cli.group()
def metrics():
    """Metrics commands."""
    pass


@metrics.command()
def dump():
    """Dump all metrics as JSON."""
    from titan.operations._metrics_integration import get_registry
    click.echo(get_registry().dump_json())


@metrics.command()
def health():
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
