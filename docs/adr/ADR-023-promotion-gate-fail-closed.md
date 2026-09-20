# ADR-023: Promotion gates fail closed — F1/F3/F7 enforcement

- **Status:** Accepted (2026-09-01) — Architecture Council and Risk Owner
- **Date:** 2026-08-07
- **Owners:** Architecture Council, Risk Owner
- **Supersedes:** N/A (complements ADR-022)

## Context

The independent design-assurance audit (2026-08-07) found three fail-open
patterns that let an invalid strategy appear QUALIFIED. These were introduced
slowly and were masked by green test suites that encoded the bad behavior.

1. **Self-referential replication (F1).** The promotion gate passed the SAME
   return-series object as both `primary_returns` and `replication_returns`
   (promotion.py), so `evaluate_replication` computed a series' correlation
   with itself — always ~1.0. The "independent replication" gate could not fail
   on independence grounds regardless of the data.

2. **Free-text metrics (F3).** `_gate_parameter_stability`,
   `_gate_independent_replication`, and `_gate_portfolio_impact` parsed
   `plateau_stability=...`, `replication_sharpe=...`, and `max_correlation=...`
   out of the `notes` string — with a hardcoded coverage default of 0.25 — so a
   comment could satisfy a gate that was supposed to require a real
   ParameterSurface evaluation or real stored metrics.

3. **Exception swallowing (F7).** `_strategy_return_series` caught every signal
   exception and defaulted to HOLD, so a strategy that raises inside its signal
   silently produced a flat (0-return) series that looked acceptable — and fed
   the replication/portfolio gates.

## Decision

1. **Self-referential / non-independent input is rejected.**
   `ReplicationEngine::evaluate_replication` fails closed (LOW confidence,
   `replication_passed=False`) when: (a) the same series object is passed as
   both primary and replication returns, (b) a copied series is passed
   (content-equal but a distinct object — same provenance), or (c) both sides
   carry the same experiment ID (a single run presented as its own
   replication). A genuinely independent second dataset/regime is required;
   identical provenance is never independent.

2. **No free-text gate metrics.** The three name gates read only real stored
   values; absence of a metric means the gate fails closed. The `notes`
   parsing and the hardcoded coverage default are removed.

3. **Signals propagate, not silently flatten.** `_strategy_return_series`
   propagates a strategy's signal exception so the gate fails closed on a
   throwing strategy rather than treating it as clean-and-flat.

4. **Regression tests lock each in.** One test per defect (F1 identity
   rejection, F3 notes-only-metric fail-closed, F7 exception propagation),
   consolidated in the research test suites.

## Consequences

- No strategy can pass "independent replication," "plateau stability," or
  "default clean" on degenerate evidence any longer.
- Strategies whose metrics are only recorded as notes text lose that
  qualification path; they must supply real stored/derived values (consistent
  with ADR-022, where the research DB is the single source of truth).
- Combined with ADR-022, an invalid strategy cannot reach QUALIFIED through a
  gate shortcut.