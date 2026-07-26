# Operational Readiness Review — Checklist

> **Owner:** Reliability Engineering
> **Status:** Active — Phase -1 baseline
> **Last Review:** 2026-07-13
> **Decision Authority:** Risk Owner

An ORR is required before transitioning from paper operation to any scope decision (Phase F2). Each item must be verified or explicitly waived by ADR.

## Architecture

- [ ] Every subsystem boundary is documented in its `.spec.md` and matches the implementation.
- [ ] No undocumented dependency exists between subsystems.
- [ ] The event store is the canonical source of economic facts.
- [ ] Caches are disposable; no cache miss alters an economic decision.

## Performance

- [ ] All p99 latency budgets from `PERFORMANCE_SPEC.md` are met under the baseline workload.
- [ ] Event store throughput meets or exceeds 50,000 events/s sequential append.
- [ ] Replay throughput meets or exceeds 1M events / 15s.
- [ ] Performance results are recorded in `knowledge/benchmarks/` with reproduction steps.

## Risk controls

- [ ] The risk gate is the sole path from TradeIntent to ApprovedOrderIntent.
- [ ] Every risk check from `specifications/Risk.spec.md` is implemented and tested.
- [ ] Kill-switch state persists across restarts and defaults to halted on unreadable state.
- [ ] Kill switch has been tested end-to-end (trigger during active order lifecycle).
- [ ] Kill switch requires manual two-person release (simulated for solo dev: audited CLI + documented procedure).

## Monitoring and alerting

- [ ] Structured logs carry correlation_id, causation_id, and service/environment/digest tags.
- [ ] Risk rejection rate, kill-switch state, reconciliation drift, event lag, and broker health are emitted as metrics.
- [ ] Safety alerts (kill-switch change, critical drift, risk-gate unavailable, stale data) page immediately.
- [ ] Dashboard exists and answers: is risk working? are orders progressing? does broker truth match?

## Recovery

- [ ] Restart: load state from event store, reconcile with broker, transition to ACTIVE only on clean reconciliation.
- [ ] Adapter truth check: an executed simulated fill reconciles InSync; a snapshot fetch failure and critical divergence both leave routing HALTED.
- [ ] Event store loss: restore from backup, replay, reconcile.
- [ ] Broker disconnect: detect, halt routing, reconcile on reconnect, resume within drift threshold.
- [ ] Reconciliation drift: critical drift halts; warning drift alerts.
- [ ] All recovery procedures tested via chaos tests matching `FAILURE_MATRIX.md`.

## Testing

- [ ] Every `FAILURE_MATRIX.md` row has a passing end-to-end test.
- [ ] Unit tests cover every legal and illegal state transition in every state machine.
- [ ] Integration tests cover the full `TradeIntent → Reconciliation` path.
- [ ] Replay tests prove identical inputs → identical outputs.

## Security

- [ ] No credentials in source code, logs, prompts, fixtures, or local defaults.
- [ ] Secrets come from an approved secret provider.
- [ ] Broker credentials are scoped to the least account/environment/capability.
- [ ] Production identities cannot write research history.

## Runbooks

- [ ] `docs/runbooks/paper-session.md` covers startup, shutdown, normal operation, and daily reconciliation review.
- [ ] `docs/runbooks/incident.md` covers detection, containment, evidence preservation, reconciliation, communication, recovery, and learning.

## Sign-off

- [ ] Architecture Council representative
- [ ] Risk Owner
- [ ] Developer (self-review)

**Date of review:** _________
**Result:** Pass / Conditional (list conditions) / Fail
