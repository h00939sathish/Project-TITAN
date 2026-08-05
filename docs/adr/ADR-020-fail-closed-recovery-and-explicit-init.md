# ADR-020: Fail-closed recovery and explicit session initialization

- **Status:** Accepted (2026-08-05, review gate — recovery boundary, authorization
  semantics, and fresh-build evidence confirmed)
- **Date:** 2026-08-04
- **Owners:** Architecture Council, Risk Owner
- **Supersedes:** ADR-019's implicit `SessionStarted` bootstrap at engine construction (removed here)

## Context

ADR-019 and the risk kill-switch state machine require that a session which was
halted (or whose halt reasoning is lost) must **never** silently restart trading.
An earlier attempt to satisfy this added an automatic `SessionStarted` bootstrap
event at engine construction, so a fresh/empty store would restore `Armed`/`Active`.
That bootstrap undermined the guarantee for the exact incident it was meant to
close: a killed session whose state store is deleted, unreadable, or corrupt
restarts with an *empty* store, then the bootstrap re-arms it and trading resumes
without any release authority.

The failure mode is fundamental: an empty store is indistinguishable from a
genuinely brand-new environment. There is no safe way to auto-arm it.

## Decision

1. **Missing / unreadable / deleted risk state ⇒ Triggered/Halted.** `RiskGate::load_or_default`
   applies a `RiskStateSnapshot` only if one is present; otherwise (no snapshot at
   all — including a store that has *other* events but no risk snapshot) it fails
   closed to `Triggered`/`Halted`. Absence of risk state is never interpreted as
   "safe to trade".
2. **No automatic bootstrap.** The engine does **not** write any `SessionStarted`
   arming marker at construction. An empty store stays fail-closed.
3. **Explicit, durable, audited initialization command.** A genuinely new paper
   environment reaches `Armed`/`Active` only via `PaperTradingEngine.initialize_new_session(...)`,
   with the same authorization discipline as kill-switch release:
   - two distinct approvers
   - rationale (root-cause/scope note)
   - bounded expiry
   - nonce replay protection
   - durable audit event (`SessionInitialized`) on success
   - refusal (durably recorded as `InitializationRefused`) on missing /
     incomplete / expired / replayed / unbounded-expiry /
     conflicting-with-existing-state / audit-write-failure.
   - a refusal that cannot be durably persisted fails loudly (it is never
     silently dropped).
4. **Initialization cannot bypass release.** `initialize_new_session` refuses if a
   `RiskStateSnapshot` already exists (`initialization_conflicts_with_existing_state`),
   so it cannot be used to arm a killed session back to trade without going through
   the release discipline.
5. **Distinct from ordinary startup — a dedicated command.** Initialization is a
   privileged, irreversible safety action, NOT a paper_session startup flag. It is
   invoked only via the standalone operator command
   `python scripts/init_session.py --state-path <session state> --approver A --approver B
   --rationale "..."` (interactive confirmation unless `--yes`; refuses on fewer
   than two distinct approvers, missing rationale, or existing risk state). A
   dedicated command makes intent, authorization, auditing, and operator runbooks
   unambiguous and reduces accidental invocation. It is never triggered implicitly
   by an empty store.
6. **Tests may use an explicit test-only initialization fixture.** Production
   defaults remain fail-closed; the fixture only arms engines under test.

## Consequences

- Safety: the lost/deleted-state restart incident is closed — restarting a killed
  session after its store is lost starts `Triggered`/`Halted`, never trading.
- First-run ergonomics: a brand-new environment must be explicitly initialized once
  before trading; thereafter normal restarts restore the persisted `Armed` snapshot.
- Test impact: engine tests that need a tradeable engine explicitly initialize via
  the fixture.
- The release authority model (ADR-019) is unchanged; initialization is a separate,
  prior step for genuinely new environments.