# Incident Response Runbook

> **Purpose:** Standard procedure for detecting, containing, recovering from, and learning about incidents.
> **Scope:** All TITAN paper operation incidents.

## Severity levels

| Severity | Definition | Response time |
|---|---|---|
| Critical | System halted, unable to recover automatically | Immediate |
| Warning | Drift detected, system degraded but operational | <1 hour |
| Informational | Unusual event, no operational impact | Next business day |

## Detection

Incidents are detected through:
1. **Health endpoint** (`SystemHealth` report) showing DEGRADED or HALTED state
2. **Reconciliation drift** — Critical drift auto-halts; Warning drift alerts
3. **Kill switch trigger** — Operator action or automated circuit breaker
4. **Test failures** — CI/CD or scheduled integration tests

## Containment

1. **Halt trading:** If not already halted, trigger kill switch
2. **Preserve evidence:** Copy logs, event store, and current state snapshot
3. **Assess scope:** Is this a data issue, code bug, or external dependency failure?

## Investigation

1. Check `knowledge/incidents/` for similar past incidents
2. Review event store replay for illegal state transitions
3. Run reconciliation to identify drift sources
4. Check adapter health for connectivity issues

## Recovery

1. Fix root cause.
2. Authorize the release — two distinct approvers, the kill trigger's
   correlation id, an assessment reference and a remediation/rollback reference:
   ```
   python scripts/release_kill_switch.py \
       --approver alice --approver bob \
       --correlation ks-<id-from-trigger> \
       --assessment "INC-9 root cause & scope" \
       --remediation "rollback to v2.0.3 per INC-9"
   ```
3. Let the **running** session perform the release. It polls
   `release_kill_switch.signal`, reconciles against broker truth, verifies
   adapter and data-feed health, re-checks at commit time, and refuses (leaving
   the switch held) if any predicate fails — ADR-019, RISK_POLICY.md.
4. Confirm: `python -m titan.cli risk status` shows `Armed`/`Active`, and the
   session log printed `kill switch RELEASED (authorized)`.
5. `python -m titan.cli risk release` is a read-only diagnostic. It reports the
   held state and the correlation id you need for step 2, and exits non-zero. It
   authorizes nothing: a detached process cannot reconcile, and an unverified
   risk snapshot written here would let the next session boot ready to route.

### Event store loss recovery

1. Identify the last known good backup of the event store file.
2. Restore the backup to the expected event store path.
3. Read the boot state (diagnostic only, never modifies the store):
   ```
   python -m titan.cli recovery restart
   ```
4. A restored store reports `ACTIVE` only if its persisted risk snapshot says
   so and reconciliation is clean.
5. If no backup exists, the store is empty and boot recovery reports `HALTED`.
   That is the correct fail-closed outcome (ADR-020): an empty store is
   indistinguishable from a deleted one. Do not attempt to resume trading. Start
   a fresh session and arm it explicitly, once, with two approvers:
   ```
   python scripts/init_session.py --state-path .titan_state.json \
       --approver alice --approver bob --rationale "state loss on INC-<n>"
   ```

## Learning

1. Document in `knowledge/incidents/<date>-<description>.md`
2. Update ADR if architecture decision needs revision
3. Add test covering the failure mode if missing
4. Update this runbook if procedure needs improvement

## Drill schedule

- Monthly: broker disconnect drill
- Monthly: state store loss drill
- Quarterly: full recovery drill
