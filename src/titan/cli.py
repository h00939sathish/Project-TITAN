"""CLI entry point for Project TITAN."""

import json
import sys

import click
from titan._core import EventStore, RiskGate, version
from titan.risk.limits import load_config

# The engine maps a session state path to its durable event store the same way.
DEFAULT_STATE_PATH = ".titan_state.json"


def _store_path(state_path: str) -> str:
    return state_path.replace(".json", ".db") if state_path else ".titan_state.db"


def _last_kill_trigger(store: EventStore) -> tuple[str, str]:
    """Return (correlation_id, reason) from the last durable kill trigger.

    The engine stores the kill correlation in ``aggregate_id`` and mirrors it in
    the payload; the envelope's own ``correlation_id`` column is a generated id.
    """
    try:
        events = store.replay_by_type("KillSwitchTriggered")
    except Exception:
        return ("unknown", "unknown")
    if not events:
        return ("unknown", "unknown")
    event = events[-1]
    reason = "unknown"
    correlation = str(event.aggregate_id or "") or "unknown"
    try:
        payload = json.loads(event.payload)
        reason = str(payload.get("reason") or "unknown")
        correlation = str(payload.get("correlation_id") or correlation)
    except Exception:
        pass
    return (correlation, reason)


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
    """Trigger kill switch - halt all trading."""
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
    click.echo("Trading halted. Release requires two authorized human approvals:")
    click.echo("  python scripts/release_kill_switch.py --approver A --approver B "
               "--correlation <id> --assessment <ref> --remediation <ref>")
    click.echo("The running session then performs the gated release. "
               "'titan risk release' reports status and authorizes nothing.")


@risk.command()
@click.option("--state-path", default=DEFAULT_STATE_PATH, show_default=True,
              help="Session state path; its event store holds the risk snapshot.")
def release(state_path: str) -> None:
    """Report a held kill switch. This command authorizes nothing (ADR-019).

    Release belongs to PaperTradingEngine.release_kill_switch() and to no other
    process: it must reconcile against broker truth and verify adapter and
    data-feed health inside the live session, under that session's lock. A
    detached process can do none of it, and writing an unverified risk snapshot
    here would let the NEXT session boot ready to route (ADR-020). Read-only, and
    exits non-zero while the switch is held so no script can mistake it for a
    completed release.
    """
    store = EventStore(_store_path(state_path))
    try:
        gate = RiskGate.load_or_default(load_config(), store)
        correlation, reason = _last_kill_trigger(store)
    finally:
        store.close()

    if not gate.kill_switch.blocks_routing():
        click.echo("Kill switch is not held. Nothing to release.")
        return

    click.echo(f"Kill switch HELD: {gate.kill_switch} / trading {gate.trading_state}")
    click.echo(f"Trigger: correlation={correlation} reason={reason}")
    click.echo("NOT RELEASED - this command holds no release authority.")
    click.echo("Release requires: two authorized human approvals, broker/order/position/")
    click.echo("balance reconciliation, verified adapter and data-feed health, and an")
    click.echo("approved remediation or rollback (ADR-019, RISK_POLICY.md).")
    click.echo("Authorize it:")
    click.echo("  python scripts/release_kill_switch.py --approver A --approver B \\")
    click.echo(f"      --correlation {correlation} --assessment <ref> --remediation <ref>")
    if correlation == "unknown":
        click.echo("(No durable KillSwitchTriggered event: this halt was not raised by")
        click.echo(" the engine. Read the correlation id from the session log.)")
    click.echo("Then leave the live session to perform it; it polls")
    click.echo("release_kill_switch.signal and stays halted if any predicate fails.")
    click.echo("No state was modified.")
    sys.exit(2)


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
@click.option("--state-path", default=DEFAULT_STATE_PATH, show_default=True,
              help="Session state path to recover from; never modified.")
def restart(state_path: str) -> None:
    """Report boot-recovery state for a session store. Read-only.

    A lost or empty event store is reported HALTED, never ACTIVE: absence of
    risk state is not evidence that trading is safe (ADR-020). Arming happens
    only through scripts/init_session.py.
    """
    from titan.recovery.restart import (
        recover_from_event_store,
        reconcile_on_boot,
        transition_on_boot,
    )

    path = _store_path(state_path)
    click.echo(f"Recovering from event store {path}...")
    state = recover_from_event_store(path)
    click.echo("Reconciling...")
    recon = reconcile_on_boot(
        state["portfolio"], state["adapter"], state["recon_engine"])
    click.echo(f"Reconciliation {'clean' if not recon['has_drift'] else 'drift detected'}")
    click.echo(f"Drift count: {recon['drift_count']}")
    store_was_empty = bool(state.get("store_was_empty"))
    if store_was_empty:
        click.echo("WARNING: Event store holds no events - state loss detected, forcing HALTED")
    transition = transition_on_boot(
        recon, state["risk_gate"], store_was_empty=store_was_empty)
    click.echo(f"System state: {transition}")
    if not transition.startswith("ACTIVE"):
        click.echo("Routing stays blocked. Arm a genuinely new environment with "
                   "scripts/init_session.py; resume a halted one with an "
                   "authorized release.")


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


@cli.group()
def research() -> None:
    """Research commands. No LLM, no parameter search, no promotion."""
    pass


@research.command("run")
@click.argument("exp_id")
@click.option("--check-only", is_flag=True,
              help="Report WF-v2 eligibility (including data coverage) without evaluating.")
def research_run(exp_id: str, check_only: bool) -> None:
    """Run hypothesis EXP_ID through the frozen WF-v2 protocol.

    Exit 0 = PASS (or ELIGIBLE with --check-only), 1 = FAIL, 2 = refused.
    Every invocation is appended to research/wf_v2/run_log.jsonl.
    """
    import time

    from titan.research import queue, wf_v2

    started = time.monotonic()
    digest = queue.protocol_digest(wf_v2.REPO_ROOT / wf_v2.PROTOCOL)
    try:
        outcome = wf_v2.run(exp_id, check_only=check_only)
    except Exception as exc:
        queue.log_outcome(wf_v2.REPO_ROOT, trigger="manual", exp_id=exp_id,
                          check_only=check_only, started=started,
                          error=f"{type(exc).__name__}: {exc}", protocol_sha256=digest)
        raise
    queue.log_outcome(wf_v2.REPO_ROOT, trigger="manual", exp_id=exp_id, check_only=check_only,
                      started=started, outcome=outcome, protocol_sha256=digest)
    click.echo(outcome.report)
    sys.exit(outcome.exit_code)


@research.command("queue")
@click.option("--check-only", is_flag=True, help="Report eligibility for each queued hypothesis.")
def research_queue(check_only: bool) -> None:
    """Run every hypothesis in research/queue.toml through WF-v2, logging each attempt.

    Exit 0 = all attempts completed (any verdict), 1 = at least one crashed,
    3 = aborted (frozen protocol changed or queue file invalid).
    """
    from titan.research import queue

    report = queue.run_queue(check_only=check_only)
    click.echo("\n".join(report.lines))
    sys.exit(report.exit_code)


if __name__ == "__main__":
    cli()
