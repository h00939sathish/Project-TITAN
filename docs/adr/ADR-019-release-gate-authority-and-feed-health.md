# ADR-019: Kill-switch release requires dual approved-human authorization and verified data-feed health

- **Status:** Proposed
- **Date:** 2026-08-04
- **Owners:** Architecture Council, Risk Owner, Execution Platform
- **Decision scope:** The `HALTED` → release transition in `PaperTradingEngine.release_kill_switch` and the market-data health predicate that gates it
- **Supersedes / superseded by:** Extends ADR-0004 (risk and recovery); does not supersede it

## Context

`release_kill_switch()` (src/titan/execution/engine.py:1110) currently releases after
reconciliation alone: it refuses only on Critical position/cash drift, then unconditionally
transitions to `Active`. It does not verify market-data health, and its only release
trigger is a bare `release_kill_switch.signal` file written by `scripts/release_kill_switch.py`
(scripts/paper_session.py:746).

Two gaps follow:

1. **No verified control health.** The broker adapter may be healthy while TWS market data
   is disconnected, stalled, or no longer completing bars. Reconciliation covers
   broker truth, not data freshness. Releasing against a stalled feed routes against
   stale data.
2. **No authorization authority.** A bare `.signal` file is a transport hint, not an
   audit-gated approval. It cannot evidence the two human approvals the Risk Policy
   requires, and it offers no nonce/expiry/replay protection.

RISK_POLICY.md §Kill switch and circuit breakers (line 37) is the binding contract:
release from `HALTED` requires broker/order/position/balance reconciliation, root-cause
and scope assessment, **verified control health**, an approved rollback or remediation,
and **two authorized human approvals**.

## Evidence

- RISK_POLICY.md:37 — release requires reconciliation + assessment + verified control
  health + approved remediation/rollback + two authorized human approvals.
- `src/titan/execution/engine.py:1110-1135` — release gate is reconcile-only today;
  no feed-health check; unconditional `set_trading_state(Active)`.
- `src/titan/execution/engine.py:461` — `_check_adapter_health()` (broker heartbeat →
  connected) is available but not consulted at release.
- `src/titan/data/tws_feed.py:278-323` — `TWSRealtimeFeed` already exposes
  `is_healthy(stale_after_s)`, `bars_advancing(since_ts)`, `latest_ts()`, `needs_recovery()`,
  per-instrument `completed_bars(instr)` / `latest_completed(instr)`, and fail-closed
  feed recovery. The engine does not hold a reference to it.
- `scripts/paper_session.py:525` — `data_freshness_threshold_ms` (2 bars + buffer) already
  exists as the staleness threshold on `RiskConfig`.
- `scripts/paper_session.py:746` — current release is signal-file triggered.

## Decision

Make release a guarded, audited operation. The signal file is retained **only** as a
transport hint that an operator intends a release; it never authorizes one.

### 1. Release authorization authority model

A release must be authorized by a `ReleaseAuthorization` record satisfying:

- **Two distinct authorized approvers** — after reconciliation.
- **Incident/kill-trigger correlation** — the record references the kill incident /
  original trigger (a correlation id or the trigger code).
- **Root-cause / scope assessment** — the record carries an assessment reference.
- **Rationale and remediation reference** — the record carries a rationale and a
  reference to the approved remediation or rollback.
- **Bounded expiry** — the authorization expires after a policy-defined window.
- **Nonce / replay protection** — each record carries a nonce; the engine refuses a
  duplicate nonce replay.
- **Durable audit event** — every release attempt (accept and refusal) is persisted to
  the durable audit/event store.

Release is refused (recorded, state untouched) on **missing, expired, duplicate, or
incomplete** authorization.

### 2. Feed-health owner and contract

New `src/titan/data/feed_health.py` defines a `FeedHealthVerdict` computed by a
**data-feed-owned** `FeedHealthSnapshot`. The owner is the realtime data feed
(`TWSRealtimeFeed`, or any object satisfying the contract). Contract predicates,
evaluated fail-closed:

- feed **absent** (`None`) ⇒ `feed_health_absent`
- `needs_recovery()` ⇒ `feed_recovering`
- not `is_healthy(stale_after_s)` ⇒ `feed_stale` (staleness = `RiskConfig.data_freshness_threshold_ms`)
- not `bars_advancing(...)` since the last known bar ⇒ `bar_not_advancing`
- per required instrument: no `latest_completed(instr)`, or watermark older than the
  threshold ⇒ `instrument_uncovered`

It reports a per-required-instrument completed-bar watermark and a single aggregate reason.

### 3. Engine integration

- `PaperTradingEngine.__init__` gains an optional read-only `feed_health` provider
  (`Optional[Callable[[], FeedHealthVerdict]]`). Default `None` ⇒ release fails closed
  (`feed_health_absent`).
- `release_kill_switch()`:
  1. refuse if no valid, non-expired, non-replayed, complete two-approver authorization
     (`release_not_authorized`);
  2. reconcile; refuse on Critical (`critical_reconcile_drift`, existing);
  3. require adapter health (`_check_adapter_health`) as an additional predicate
     (`adapter_down`);
  4. evaluate feed health; refuse on any degraded predicate;
  5. **TOCTOU**: re-evaluate feed health + reconcile + `is_triggered()` immediately
     before the `release_completed()` / `set_trading_state(Active)` commit;
  6. preserve the original kill trigger; persist refusals separately.
- Broker adapter health is an additional predicate within this gate, not the fix.

## Alternatives and trade-offs

- **Gate on reconcile only (status quo).** Rejected: does not satisfy "verified control
  health"; is the defect being corrected.
- **Operator + rationale single record.** Rejected by policy: does not meet the two-
  approval requirement; no nonce/expiry/replay defense.
- **Add feed state to the Rust core.** Rejected for now: the realtime feed already owns
  the health primitives; keeping the snapshot Python-side minimizes core churn while
  the engine consumes the read-only verdict.

## Consequences

- Release becomes deliberately hard and auditable, matching `HALTED` semantics.
- A stalled/absent feed and a missing/expired/incomplete authorization both block release
  fail-closed.
- Non-TWS/simulated sessions (no realtime feed) inject `None` and therefore cannot
  release without wiring a health provider: correct fail-closed behavior.
- Refusal evidence is durable and distinguishable from the original kill trigger.