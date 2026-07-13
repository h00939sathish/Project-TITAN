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

1. Fix root cause
2. Reconcile state: verify portfolio == broker truth
3. Release kill switch: `release_initiated()` → `release_completed()`
4. Verify with health endpoint
5. Resume normal operation

### Event store loss recovery

1. Identify the last known good backup of the event store file.
2. Restore the backup to the expected event store path.
3. Run recovery:
   ```
   python -m titan.cli recovery restart
   ```
4. Verify system starts in ACTIVE and reconciliation is clean.
5. If no backup exists, start a fresh session and reconstruct state manually.

## Learning

1. Document in `knowledge/incidents/<date>-<description>.md`
2. Update ADR if architecture decision needs revision
3. Add test covering the failure mode if missing
4. Update this runbook if procedure needs improvement

## Drill schedule

- Monthly: broker disconnect drill
- Monthly: state store loss drill
- Quarterly: full recovery drill
