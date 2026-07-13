# ADR-0006: Paper broker certification

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** Execution Platform, Security Engineering
- **Decision scope:** Broker adapter certification, paper trading, credential boundaries
- **Supersedes / superseded by:** None

## Context

A broker adapter is the boundary between TITAN's deterministic core and an external, untrusted financial system. It must be certified through contract tests, sandbox validation, and security review before handling any order. Paper trading proves the full lifecycle without capital exposure.

## Evidence

- `EVIDENCE_SYNTHESIS.md` §6: Fincept's connector patterns inform the adapter design; its stale-fork and broad-boundary lessons are cautionary.
- `../BROKER_SPEC.md`: adapter certification requires sandbox lifecycle tests, auth-expiry tests, rate-limit tests, restart/reconciliation tests.
- `../SECURITY.md`: broker credentials are scoped to the least environment/capability and segregated from research/AI identities.

## Decision

1. **Simulated adapter first.** Phase C uses an in-memory deterministic adapter that simulates acknowledgements, fills, partial fills, rejects, timeouts, and disconnects. This is the primary test path for the vertical slice.
2. **Paper adapter is a separate adapter implementation** of the same trait. It connects to a broker sandbox or paper-trading API with no capital authority.
3. **Broker selection (Phase E) prioritizes sandbox quality** — a broker with a well-documented paper API, clear rate limits, and no capital risk for sandbox accounts is preferred over one with better production features but no safe test mode.
4. **PAT (Production Acceptance Test) must pass** before paper trading opens. PAT validates deployment artifact, startup, restart recovery, config validation, secret resolution, telemetry, and health endpoint.
5. **No live credentials.** The paper broker adapter uses sandbox/paper credentials that cannot route capital.

## Alternatives and trade-offs

- **Direct live broker integration** — would prove real-world connectivity faster but risks capital exposure before safety controls are proven. Rejected; paper-only is the plan's mandate.
- **Multiple broker adapters in Phase E** — adds scope without proving the safety loop. Solo developer should certify one adapter well before expanding.

## Consequences

- Simulated adapter tests are the primary safety proof. Paper adapter tests are the operational proof.
- Broker selection in Phase E is constrained by sandbox quality, not production features.
- The PAT checklist becomes a required gate before any external connectivity.

## Validation and operations

- Adapter contract tests: every method returns expected types for valid and invalid inputs.
- Sandbox tests: authentication expiry, heartbeat, reconnect, rate-limit, partial-fill, restart, reconciliation.
- 14-day paper session with daily reconciliation review and incident log.
- No live capital until the Phase F2 gate and a subsequent ADR.

## Approval

Architecture Council — 2026-07-13
