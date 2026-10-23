# TITAN PRESERVE — What TITAN Does Right (with implementation evidence)

Every positive claim below is backed by code or artifacts, not documentation.

---

## 1. The Rust authority core (preserve as-is)

- risk.rs, orders.rs, portfolio.rs, reconciliation.rs, event_store.rs, messages.rs,
  validation.rs, types.rs — one place owns money, positions, order state, persistence.
  Decimal-string money types with no NaN/inf (types.rs); instrument tick/step/side
  validation (types.rs:280-298); append-only SQLite event store with message_id dedup
  (event_store.rs); order state machine with partial fills, cancels, expiry, Unknown
  resolution (orders.rs:88-132).
- Dollar-based gross exposure (long+short, M2M with cost-basis fallback,
  portfolio.rs:288-298) — the rare correct implementation of a subtle invariant, proven by
  5 tests including an exact-limit rejection end-to-end
  (tests/adapters/test_paper_trading_engine.py:217-339).

## 2. Fail-closed recovery design

- Risk gate restores Triggered/Halted from empty/unparseable state (risk.rs:742-752).
- Kill switch: Armed→Triggered→Releasing→Released, never auto-resets (risk.rs:92-109);
  triggers on adapter-down, unknown broker outcomes, Critical reconciliation drift,
  startup unresolved orders, corrupt state.
- Crash recovery: New/Validated→local Reject; Submitted→broker query via idempotency key
  or fail-closed kill switch (engine.py:802-880); never resends blindly.
- Two-person kill-switch release with nonce replay protection, expiry, reconciliation
  predicate, adapter+feed health, and TOCTOU re-check (engine.py:1623-1711).

## 3. The honest negative-result research record (the rarest asset)

- ~40 experiments across 4 asset classes with pre-registration, evidence bundles, journal,
  and absorbing negative-result seals (ADRs 029/030). Examples worth keeping verbatim:
  - EXP-00017: promoted, then KILLED BY ITS OWN 2-fold OOS retest
    (EXP-00017_2fold_retest.json `honest_note`: "The ONLY promoted effect … does not
    clear the pre-registered OOS bar").
  - Crypto fee-tier economics: maker fee ≈ 40× harvestable half-spread (CRYPTO-005);
    corr(half_spread, net_edge)=0.967 (CRYPTO-006) — cost walls quantified, not assumed.
  - EXP-00019 real-spread follow-up: the project spent a whole experiment measuring what
    real spreads do to its only positive effect.
  - The promotion report's self-disclaimer that its own gate Sharpe series is
    "drift-inflated… measures directional market drift, not the strategy's cost-aware
    edge" (ema9vwap_promotion_report.md:34-41).
- This is the behavior of a research institution, not a hobby repo. Almost no open-source
  trading project does any of this. Preserve the format, the registry, and the refusal to
  erase failures.

## 4. The fail-closed promotion gate (preserve; fix its bypass)

- 8 gates, `passed = all(...)` (promotion.py:211-223), min_shadow_trades, win-rate,
  Sharpe-degradation, parameter-stability, replication, portfolio-impact, ensemble
  regression. The one live evaluation refused to promote a candidate it had every
  incentive to promote ("Do not promote. Do not trade live", ema9vwap_promotion_report.md:130).
- Caveat (see Architecture Health): the parallel Path-1 script that writes QUALIFIED
  directly to the DB must go — the gate is the thing to preserve, the bypass is the thing
  to delete.

## 5. Deterministic event design

- Schema-first JSON contracts (contracts/), RFC3339/UUID validation (validation.rs),
  single authoritative fill-absorption path (_absorb_broker_fill, engine.py:638-739),
  reconciliation as a first-class engine predicate — not an afterthought.

## 6. Test philosophy where it is applied

- tests/backtest/test_exit_intents.py asserts EXACT economic outcomes (total_pnl == -45.0,
  gap fills at open, TP at level) — the correct standard for trading tests, applied to the
  one subsystem where it was applied.
- tests/adversarial runs the REAL gate against forgery/replay attacks.
- tests/e2e/test_profit_engine_e2e.py drives the real, unpatched submit path with a real
  certificate — the proof the machinery works, and the template for what the rest of the
  suite should look like.

## 7. Governance discipline worth keeping (tightened)

- ADR process, pre-registration, absorbing exclusions (CROSS_MARKET_ALPHA_CHARTER.md:23-31),
  "strictly no live capital authority" — correct defaults for a system with no edge.
- Keep the DISCIPLINE; cut the VOLUME (an ADR should land with its wiring commit).

## Bottom line

The parts of TITAN worth preserving are precisely the parts most trading projects never
build: a deterministic Rust authority for risk/portfolio/reconciliation, fail-closed
recovery, and a ~40-experiment honest negative record with pre-registered OOS discipline.
The project's problem is not these parts — it is the seam that connects them to reality.
