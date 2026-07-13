# Production Acceptance Test — Checklist

> **Owner:** Reliability Engineering
> **Status:** Active — Phase -1 baseline
> **Last Review:** 2026-07-13
> **Decision Authority:** Risk Owner

PAT validates that the deployment artifact can be installed, started, stopped, recovered, and observed — even though actual production capital is never used. PAT must pass before paper trading opens (Phase E2).

## Deployment artifact

- [ ] Artifact is a single signed/immutable deliverable (or documented equivalent for solo dev: pinned git tag + dependency lock).
- [ ] All dependencies are pinned and vulnerability-scanned.
- [ ] SBOM or equivalent dependency manifest is generated.

## Installation

- [ ] Clean install from artifact (no pre-existing state) succeeds.
- [ ] Install from artifact onto a system with the target OS and runtime succeeds.
- [ ] `--version` flag returns the expected digest.

## Startup

- [ ] With valid configuration: starts, loads contracts, initializes event store, reports healthy.
- [ ] With missing configuration: fails with descriptive error, non-zero exit.
- [ ] With invalid configuration: fails with descriptive error identifying the invalid key.
- [ ] With unreachable event store path: fails, does not create a corrupt state.

## Restart and recovery

- [ ] Clean shutdown → restart: recovers all state from event store, reconciles with broker/adapter.
- [ ] Forced kill → restart: same as above, no data loss.
- [ ] Restart with corrupted event store: detects corruption, fails closed, does not start in ACTIVE state.

## Configuration

- [ ] Every configuration key in every `.spec.md` is validated at startup: wrong type, out of range, missing required key.
- [ ] Environment-specific configuration (paper vs simulation) is strictly separate.
- [ ] Configuration changes are audit-logged.

## Secrets

- [ ] No secrets in configuration files.
- [ ] Secrets are referenced by path/name and resolved from approved secret provider.
- [ ] If secret resolution fails at startup, the process fails (not falls back to a default or prompt).

## Telemetry

- [ ] Structured logs are emitted on startup, state transitions, and errors.
- [ ] Metrics (event lag, risk rejection rate, kill-switch state, reconciliation drift) are emitted on a regular interval.
- [ ] Health endpoint returns current state (ACTIVE/HALTED/DEGRADED), uptime, and last reconciliation timestamp.
- [ ] Health endpoint does not expose secrets.

## Kill switch

- [ ] Kill-switch state persists across restarts.
- [ ] On unreadable kill-switch state, system starts in HALTED.
- [ ] Kill-switch trigger during operation blocks new routing (verified via integration test).

## Adapter connectivity

- [ ] Adapter heartbeat at startup verifies connectivity before enabling routing.
- [ ] Adapter failure during operation triggers disconnect behavior per FAILURE_MATRIX.md.
- [ ] Adapter reconnect after failure recovers and resumes within drift threshold.

## Reconciliation

- [ ] Reconciliation runs at startup, periodically, after reconnect, and before/after halt release.
- [ ] Reconciliation drift (critical) halts routing.
- [ ] Reconciliation drift (warning) alerts but does not halt.

## Result

- [ ] All items pass.

**Date of test:** _________
**Result:** Pass / Fail
