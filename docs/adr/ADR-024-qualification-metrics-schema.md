# ADR-024: Store promotion-gate surface metrics in the qualifications schema

- **Status:** Accepted (2026-08-07) — implementation lands in this PR
- **Date:** 2026-08-07
- **Owners:** Architecture Council, Risk Owner, Research Platform
- **Supersedes:** none; completes ADR-023 F3 (which removed notes-string metric
  parsing but left no storage for the metrics it made read-only)
- **Decision scope:** `qualifications` table, `ResearchDB.set_qualification`,
  `PromotionGate._gate_parameter_stability`

## Context

ADR-023 (F3) removed the fail-open path where promotion gates parsed
`plateau_stability=...`, `replication_sharpe=...`, and `max_correlation=...`
out of free-text `notes`. That correctly made the gates fail closed, but it
left a structural gap: the `qualifications` table and `set_qualification`
had **no columns** for these metrics, so `_gate_parameter_stability` was
**unsatisfiable** through the sanctioned DB API — even a real ParameterSurface
evaluation could not be persisted where the gate reads it.

## Decision

Add four optional `REAL` columns to `qualifications`:
`plateau_stability`, `plateau_coverage`, `replication_sharpe`,
`max_correlation`. Extend `ResearchDB.set_qualification` with these four
optional keyword params. Migrate existing pre-023 databases idempotently
(guarded `ALTER TABLE ... ADD COLUMN` in a `_migrate_qualifications_metrics`
method called on init, a no-op when columns already exist). No change to
`_gate_parameter_stability`'s thresholds (`min_plateau_stability` 0.70,
`min_plateau_coverage` 0.20) — it now reads genuinely stored values.

## Effect

`set_qualification` persists the four metrics; fresh and existing DBs both
carry the columns; the parameter_stability gate evaluates real stored values
(fail-closed on absence, pass/fail on threshold). No promotion authority
change; gate criteria unchanged.

## Consequences

Positive: parameter_stability is unblocked for any strategy that produces a
real surface; no values can sneak in via notes; migrations are idempotent.
Negative: existing rows are NULL until repopulated (gate stays failed-closed
for them — correct).

## Verification

`tests/research/test_schema_migration_adr023.py` — 5 tests: fresh columns
exist, pre-existing DB migrated via ALTER, round-trip roundtrip of four
values, gate passes with stored values, gate fails-closed below threshold.
Suite: 18 passed on the promotion/qualification/replication/schema set.

## Rollback

Drop the four columns (`ALTER TABLE qualifications DROP COLUMN ...`) and
revert the `set_qualification` signature; the gate returns to fail-closed on
absent metrics.