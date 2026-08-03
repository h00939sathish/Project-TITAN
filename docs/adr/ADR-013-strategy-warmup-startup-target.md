# ADR-013: Strategy Warmup Startup Target

**Status:** Accepted
**Date:** 2026-07-15
**Decision:** Preserve the latest warmup direction and use it to establish a
flat long-only paper portfolio only when the current bar produces no new
direction.
**Supersedes:** None
**Depends on:** `specifications/StrategyRuntime.spec.md`, `specifications/Risk.spec.md`, ADR-012

## Context

Historical warmup correctly prepares indicator state without emitting orders,
but stateful strategies can update their private direction during warmup. A
fresh paper portfolio may consequently be flat while the strategy already
considers itself long. The first current bar then returns no transition, so the
bridge emits no BUY and fails to establish the intended paper position.

## Decision

`StrategyBridge.warmup()` records each instrument's latest `BUY` or `SELL`
direction while it feeds pre-current-bar closes. When `on_price()` handles the
first current bar, a current-bar direction takes precedence. If that call
returns no direction, the bridge uses the retained warmup direction. Each
later current-bar direction replaces that retained value, so a stale historical
BUY cannot re-enter after a live SELL.

The bridge remains long-only. A retained `BUY` may emit one BUY only when the
reconciled portfolio is flat. A retained `SELL` does not open a short. Existing
position, last-side, and bar-date guards remain authoritative and prevent
duplicate intent emission.

Every resulting `TradeIntent` still traverses the existing deterministic risk
gate and execution pipeline. This decision grants no broker, portfolio, risk,
or secret-management authority to strategies.

## Alternatives considered

- **Discard every historical signal.** Rejected: the strategy's private state
  still changes during warmup, leaving the bridge and strategy out of sync.
- **Warm up including the current bar.** Rejected: it can swallow a current-day
  transition before the engine has an opportunity to evaluate it.
- **Reset opaque strategy internals after warmup.** Rejected: registered
  strategy functions are intentionally opaque and may not expose a safe reset
  operation.

## Verification

- A regression test starts time-series momentum long after warmup, sets the
  reconciled position flat, and verifies one BUY on the first current bar.
- The same test verifies a duplicate call for that bar emits no second intent.
- A regression test verifies a current SELL replaces a retained BUY before a
  later no-transition bar is processed.
- Focused bridge and momentum suites verify existing duplicate and long-only
  safety behavior.

## Monitoring

Review structured `strategy` accept/reject logs with `intents_evaluated` and
`intents_rejected`. At startup, no instrument may have more than one intent for
the same bar date. Unexpected repetition is an incident: halt, preserve state
and logs, and reconcile before release.

## Rollback

1. Trigger the kill switch and stop the session.
2. Preserve the state file and structured logs for replay evidence.
3. Revert the bridge-only warmup-target change.
4. Reconcile broker truth against the portfolio projection.
5. Restart only after clean reconciliation and an audited operator release.
