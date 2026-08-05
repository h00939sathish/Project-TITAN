#!/usr/bin/env python
"""Dedicated, privileged operator command: explicitly initialize a NEW session.

Initialization is a privileged, irreversible safety action — NOT ordinary
session startup (ADR-020). It is the only way a genuinely new paper
environment becomes Armed/Active: the engine always restores
Triggered/Halted (fail closed) when no risk state exists, and refuses to
bootstrap itself implicitly.

A dedicated command (instead of a paper_session flag) makes intent,
authorization, auditing, and operator runbooks unambiguous and reduces the
chance of accidental invocation.

Usage:
    python scripts/init_session.py --state-path .titan_state.json \
        --approver "alice" --approver "bob" --rationale "New 90-day paper env" \
        [--config session_config.json] [--mode broker-paper] \
        [--starting-capital 100000] [--expiry-min 15] [--yes]

Refuses (exit 1) when:
- fewer than two distinct approvers are given (authorization_incomplete),
- no rationale is given,
- the authorization window is invalid,
- the store already contains risk state (initialization would bypass
  release / re-arm a killed session) — initialization_conflicts_with_existing_state,
- anything is unreadable/undecidable (fail closed).

On success it persists a SessionInitialized event + Armed risk snapshot and
prints the audit record (nonce, approvers, rationale, state path).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from titan._core import Money, ReconciliationConfig, RiskConfig
from titan.execution import PaperConfig, PaperTradingEngine
from titan.risk.session_initialization import InitializerApproval, SessionInitialization, new_nonce

# scripts/ is not a package: make sibling imports resolve regardless of cwd
# (invocation is always `python scripts/init_session.py`, but be robust).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Reuse the session runner's config/adapter construction so the initialized
# store is byte-for-byte compatible with the session that will run on it.
from paper_session import _bar_seconds, _build_adapter, _merge_config

MIN_APPROVERS = 2


def _build_config(args) -> tuple[PaperConfig, str]:
    """Build the PaperConfig exactly as paper_session would for this env."""
    if not args.config and Path("session_config.json").exists():
        args.config = "session_config.json"
    if args.config:
        cfg_path = Path(args.config)
        if cfg_path.exists():
            import json
            _merge_config(args, json.loads(cfg_path.read_text(encoding="utf-8")))
            print(f"Loaded config from {args.config}", flush=True)

    bar_seconds = _bar_seconds(args.bar_size)
    data_freshness_threshold_ms = (bar_seconds * 2 + 1) * 1000
    risk_config = RiskConfig(
        [],
        Money(args.starting_capital, "USD"),
        1000,
        5000,
        Money(args.starting_capital, "USD"),
        0.10,
        Money("5000", "USD"),
        data_freshness_threshold_ms,
        100,
    )
    paper_config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital=args.starting_capital,
        account_id="paper-1",
        state_path=args.state_path,
    )
    return paper_config, args.state_path


def _check_fresh(engine: PaperTradingEngine) -> None:
    """Fail closed unless this is a genuinely new, uninitialized environment."""
    snapshots = []
    try:
        snapshots = engine._event_store.replay_by_type("RiskStateSnapshot")
    except Exception as e:  # noqa: BLE001 - fail closed on unreadable store
        raise RuntimeError(f"initialization_refused_unreadable_store: {e}") from e
    if snapshots:
        raise RuntimeError(
            "initialization_conflicts_with_existing_state: the store already "
            "contains risk state; initialization cannot re-arm an existing or "
            "killed session (it would bypass release)."
        )
    # Fail-closed engine guarantees the gate is held on a fresh store; if it
    # is somehow NOT held, something already armed this session — refuse.
    if not engine.risk_gate.kill_switch.blocks_routing():
        raise RuntimeError(
            "initialization_conflicts_with_existing_state: risk gate is not "
            "fail-closed held; refusing to initialize an already-armed session."
        )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Explicitly initialize a NEW paper session (privileged, audited).",
        epilog="This is a safety action: it refuses if risk state already exists.",
    )
    parser.add_argument("--config", default=None,
                        help="Path to JSON config file (same shape as paper_session)")
    parser.add_argument("--mode", default="simulation",
                        choices=["simulation", "paper-preflight", "broker-paper"],
                        help="Session mode the initialized env will run under")
    parser.add_argument("--state-path", default=".titan_state.json",
                        help="State/event-store path (the SESSION's state_path)")
    parser.add_argument("--starting-capital", default="100000",
                        help="Starting capital (must match the session's)")
    parser.add_argument("--bar-size", default="5 mins",
                        help="Session bar size (drives data-freshness threshold)")
    parser.add_argument("--approver", action="append", default=[],
                        help="Initialization approver (provide at least two, distinct)")
    parser.add_argument("--rationale", default="",
                        help="Rationale for creating this new environment (durable audit field)")
    parser.add_argument("--expiry-min", type=int, default=15,
                        help="Authorization lifetime in minutes (bounded expiry)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the interactive confirmation prompt (runbook use)")
    args = parser.parse_args()

    approvers = [a.strip() for a in args.approver if a and a.strip()]

    # Build the engine FIRST so EVERY refusal (including CLI validation
    # failures below) is recorded as a durable InitializationRefused event
    # before the process exits (ADR-020: refusal audit trail is mandatory).
    paper_config, state_path = _build_config(args)
    adapter = _build_adapter(args.mode, use_tws=False)
    engine = PaperTradingEngine(paper_config, adapter)

    def _refuse(reason: str, message: str) -> int:
        try:
            engine._record_init_refusal(reason)
        except RuntimeError as re:
            print(f"FATAL: {message} (AND refusal could not be durably "
                  f"recorded: {re})", flush=True)
        else:
            print(f"FATAL: {message}", flush=True)
        engine._event_store.close()
        return 1

    if len(set(approvers)) < MIN_APPROVERS:
        return _refuse(
            "initialization_incomplete",
            f"initialization requires at least {MIN_APPROVERS} DISTINCT "
            f"approvers (got {approvers})")
    if not args.rationale.strip():
        return _refuse("initialization_incomplete",
                       "--rationale is required (durable audit field)")
    if args.expiry_min <= 0:
        return _refuse("initialization_incomplete",
                       "--expiry-min must be positive")

    try:
        _check_fresh(engine)
    except Exception as e:  # noqa: BLE001 - surface the refusal reason
        return _refuse("initialization_conflicts_with_existing_state", str(e))

    now = datetime.now(timezone.utc)
    init = SessionInitialization(
        approvers=[InitializerApproval(a, now.isoformat()) for a in approvers],
        rationale=args.rationale.strip(),
        issued_at=now.isoformat(),
        expiry=(now + timedelta(minutes=args.expiry_min)).isoformat(),
        nonce=new_nonce(),
    )

    print("", flush=True)
    print("=== INITIALIZE NEW SESSION (privileged, irreversible) ===", flush=True)
    print(f"  state path    : {Path(state_path).resolve()}", flush=True)
    print(f"  starting cap  : {args.starting_capital} USD", flush=True)
    print(f"  mode          : {args.mode}", flush=True)
    print(f"  approvers     : {approvers}", flush=True)
    print(f"  rationale     : {args.rationale.strip()}", flush=True)
    print(f"  auth expires  : {init.expiry}", flush=True)
    if not args.yes:
        resp = input('Type "INITIALIZE" to confirm: ')
        if resp.strip() != "INITIALIZE":
            print("Aborted by operator.", flush=True)
            engine._event_store.close()
            return 1

    try:
        engine.initialize_new_session(init)
    except Exception as e:  # noqa: BLE001 - surface the refusal reason
        print(f"FATAL: session initialization refused: {e}", flush=True)
        engine._event_store.close()
        return 1

    state = engine.risk_gate
    print("", flush=True)
    print("SESSION INITIALIZED (audited)", flush=True)
    print(f"  nonce         : {init.nonce}", flush=True)
    print(f"  kill switch   : {state.kill_switch}", flush=True)
    print(f"  trading state : {state.trading_state}", flush=True)
    events = [e.message_type for e in engine._event_store.replay_all()]
    print(f"  events        : {events}", flush=True)
    engine._event_store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
