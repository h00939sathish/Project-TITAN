# Coding Standard

> **Owner:** Core Platform Architecture
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [SECURITY.md](SECURITY.md)
> **Supersedes:** None
> **Review Frequency:** Quarterly; per language/platform change

## Philosophy

Code should make unsafe behavior difficult to express. Favor small typed modules, explicit dependencies, immutable domain messages, and narrow interfaces. Do not import a repository’s internal shape merely because one component was selected. The constraints follow the failure patterns in `../FAILURE_ANALYSIS.md` and the adoption boundaries in `../ADOPTION_DECISIONS.md`.

## Organization and naming

Organize by domain boundary: `core/` (messages and state), `risk/`, `execution/`, `brokers/`, `portfolio/`, `research/`, `validation/`, `data/`, `operations/`, and `tests/`. An adapter translates an external protocol at its edge; it does not leak SDK objects inward. Use nouns for immutable events (`OrderSubmitted`), verbs for commands (`SubmitOrder`), and explicit result types (`RiskDecision`). Avoid `manager`, `util`, `common`, or `helper` as ownership substitutes.

## Contracts and state

Messages carry schema version, event/command id, correlation id, causation id, timestamp, source, and validated payload. Represent money, quantity, price, instrument, side, time-in-force, and order status with domain types—not unvalidated strings or floats. Make state transitions explicit and reject illegal transitions. No global singleton owns mutable trading state.

## Errors and logging

Never use broad catch-and-ignore behavior on a trading path. Classify errors as retryable, terminal, data-quality, risk, or operational; preserve cause, correlation id, and remediation. Retries are bounded, idempotent, and observable. Logs are structured; metrics use stable names; traces cross message/broker boundaries. Never log credentials, account identifiers beyond approved masking, or raw prompt data containing secrets.

## Configuration and dependencies

Configuration is typed, validated at startup, environment-scoped, and versioned with each run. Secrets come from an approved secret provider, never source control, local defaults, prompts, or error output. Add dependencies only with owner, license/security review, version policy, and a documented reason. Pin production dependencies and regularly remove unused ones; the large pinned-dependency surface noted in `../FAILURE_ANALYSIS.md` is a caution, not a model.

## Performance and documentation

Profile real workloads before optimization; isolate allocations and blocking I/O off latency-sensitive paths; preserve deterministic replay. Public modules document ownership, inputs, outputs, failure behavior, configuration, telemetry, and tests. Comments explain invariants and rejected alternatives, not syntax.

## Prohibited patterns

* LLM calls in order, risk, balance, or reconciliation paths.
* A safety mechanism that is declared but not invoked by the production path.
* Auto-reset or default-enable behavior for a kill switch.
* Regex parsing of untrusted model output where a schema can be enforced.
* Mutable global state, hidden broker SDK calls, raw exception swallowing, or hard-coded environment credentials.
