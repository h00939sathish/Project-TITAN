# ADR-022: Qualification is DB-gated — remove baked-in `qualified_variants`

- **Status:** Proposed (awaiting Architecture Council + Risk Owner review)
- **Date:** 2026-08-07
- **Owners:** Architecture Council, Risk Owner
- **Supersedes:** N/A (adds to ADR-016 governance loops)

## Context

Independent design-assurance audit (2026-08-07) identified a fail-open bypass in
the promotion model: several strategies are hard-coded as QUALIFIED **at import
time** in `src/titan/strategies/registrations.py` via a non-empty
`qualified_variants=frozenset({...})`. This field is set by **author code**, not
by the promotion gate (`PromotionGate` in `src/titan/research/promotion.py`,
CLI `research promote`).

Consequences:

1. **The promotion gate never runs for these strategies.** `PromotionGate` is
   invoked only from `scripts/... research cli promote` (src/titan/research/cli.py:240).
   Strategies with a non-empty `qualified_variants` are selectable by the live
   runtime without ever clearing that gate. An invalid strategy is therefore
   QUALIFIED by registration, not by evidence.
2. **Two qualification sources diverge.** The registry field
   (`is_qualified_for`, registry.py:25) and the research DB
   (`qualifications` table, `status=QUALIFIED`) can disagree. The paper session
   uses the DB (`QualifiedStrategyPool.load_qualified`), while the FX paper
   runtime uses the registry field (`multitimeframe_runtime.py:66`).
3. **The live FX paper session trades all 5 of these.** `scripts/ibkr_paper_session.py`
   `STRATEGY_IDS` lists time-series-momentum, ma-crossover, mean-reversion,
   volatility-regime, dual-ma; the runtime gate skips any strategy that is
   neither qualified nor in the watchlist (multitimeframe_runtime.py:66-71). A
   blind removal silently stops FX paper validation.

Selected strategies currently baked-in (registrations.py):
ma-crossover, mean-reversion, volatility-regime, time-series-momentum, dual-ma
(all with real `qualified_variants`); bollinger/rsi also carry baked-in variants.

## Decision

1. **Remove baked-in `qualified_variants` from `registrations.py`.** No strategy
   is born QUALIFIED at import. `qualified_variants` stays `frozenset()` in every
   registration; qualification is earned only through `PromotionGate.promote`,
   which writes `status=QUALIFIED` to the research DB.

2. **The research DB is the single source of truth (SSOT) for qualification.**
   The runtime consults the DB (`QualifiedStrategyPool` / a `qualifications`
   row with `status='QUALIFIED'`), not the registry field. The registry keeps
   strategy **definitions** (factory, schema); the DB keeps **qualification
   state**.

3. **Transition state (no silent live break).** The 6 previously-baked-in
   strategies must continue to be *evaluable* in paper, but their QUALIFIED
   status is revoked pending gate re-approval. Concretely, for the FX session:
   they are routed through `watchlist_ids` (shadow) so they keep producing
   signals and orders are logged as shadow, until each is re-qualified through
   the (now-fixed) gate. No strategy silently drops from the paper feed.

4. **Enforcement (future / CI).** A linter test asserts `qualified_variants` is
   empty at registration time (`is_qualified_for` must consult the DB, never a
   baked set), so a future baked-in variant fails CI.

## Rationale

- Bakes the audit's F2 finding into code: qualification cannot be granted by
  author intent; it is earned by the gate.
- Mirrors the existing DB path the equity paper session already uses
  (`--qualification-db` / `QualifiedStrategyPool.load_qualified`), so one model
  governs both sessions.
- The provenance field keeps the promotion gate the **only** way to reach
  QUALIFIED (fail-closed), and the transition keeps paper validation flowing
  during re-approval.

## Trade-offs

- **Risk:** a strategy previously trading as qualified in FX paper becomes
  shadow-on-paper until re-approved — intended consequence, but call it out to
  operators.
- **Effort:** the FX session runner must accept a watchlist/explicit set. This
  is a modest change to `ibkr_paper_session.py` (route STRATEGY_IDS through
  `watchlist_ids`) plus the registry runtime reading DB state.

## Implementation gate (6-condition, per ADR convention)

1. `registrations.py`: every `qualified_variants` = `frozenset()`.
2. CI/linter test: `is_qualified_for` == False for all registered strategies
   absent a DB grant ("no baked-in qualification").
3. `multitimeframe_runtime.py`: gate consults DB/grant, and FX session routes
   candidates via watchlist during transition.
4. Regression tests: F2-bypass (no baked variant is QUALIFIED), transition
   (watchlist strategy still produces shadow proposals), promotion (DB QUALIFIED
   is respected by the runtime).
5. Verification: full suite green; FX paper session summary reports the 5 as
   WATCHLIST/shadow, not QUALIFIED.
6. Rollback / monitoring: disable via reverting this ADR's registrations change;
   no live-capital routing is affected (this governs paper qualification only).

## Consequences

- Promotion for the 6 is gated again; each must clear `PromotionGate` (with the
  fixed F1/F3/F7 checks) to be re-admitted.
- Runtime and DB converge on one definition of QUALIFIED.