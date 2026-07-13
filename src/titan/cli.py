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
