# ARCHITECTURE HEALTH REPORT — 2026-09-29

Assessment of the Rust/Python boundary, event architecture, state ownership, boundaries
and coupling. Verdict: **the core architecture is sound and worth keeping; the damage is
duplication at the research/backtest layer, a dead AI layer, and a documentation stack
that has outrun the implementation.**

---

## 1. What is healthy

- **Rust authority boundary**: risk, orders, portfolio, reconciliation, event store live
  in one PyO3 core (core/src/*.rs; 9 files), exported via lib.rs:20-72, consumed by the
  Python engine. One place owns money, positions, order state, and persistence. This is
  the right boundary — comparable in intent to NautilusTrader's Rust core, and the single
  best architectural decision in the project.
- **Determinism**: append-only SQLite event store with message_id dedup (event_store.rs),
  nanosecond-grade ordering intent, replay by aggregate/type.
- **Fail-closed defaults everywhere it matters**: risk gate restores HALTED on empty/
  unparseable state (risk.rs:742-752); certificate default deny; kill switch never
  auto-resets; two-person release with nonce replay + reconciliation predicate.
- **State ownership**: fills absorbed exactly once through `_absorb_broker_fill`
  (engine.py:638-739); portfolio is the single authority; broker is reconciled against it,
  not trusted.
- **Contracts**: schema-first JSON contracts in contracts/ (trade-intent, approved-order,
  risk-decision, event-envelope, crypto-market-event) — real and versioned.

## 2. What is unhealthy

1. **Two backtest systems that share nothing.** The research harness
   (scripts/backtest_strategies.py → research/harness.py) and the ReplayEngine
   (backtest/engine.py → PaperTradingEngine) have separate fills, separate cost models,
   separate PnL accounting (Python floats vs Rust portfolio). Results are not comparable;
   candidate evidence runs on the engine path (replay_traderdev_ema9vwap.py) while all
   gate evidence runs on the harness. The "one deterministic core" claim is false today.
2. **Four divergent fill/cost semantics** (harness next-bar; ReplayEngine same-bar-zero-cost;
   BarConservativeFillModel; FxCostModel) with script-level parameters disagreeing
   (0.10-1.0 bps slippage across 8+ scripts). No canonical cost object.
3. **Dead layers**: feature graph (runtime/feature_graph.py), memory subsystem (vector_memory
   via mcp_bridge — imported by nothing), regime classifier, HRP allocator, ensemble
   allocator, rebalancing, bar_aggregator, the "full pipeline" orchestrator — all
   test-only or zero-import. Each was built spec-first; none is wired. The AI boundary
   (ADR-007) is advisory by design, but today it is not even loaded.
4. **Two competing qualification authorities.** Path 1 (scripts/qualification_pipeline.py)
   writes status=QUALIFIED directly to the DB on weak thresholds
   (IS Sharpe ≥0.5, OOS ≥0.0, lines 113-119, 479-488); Path 2 (PromotionGate,
   research/promotion.py) is fail-closed and stronger — and its artifact gate
   (evaluate_from_artifact) has zero callers. ADR-022 says only the gate can qualify;
   the script contradicts the ADR and no code prevents it.
5. **The admission seam is unbuilt**: promotion writes a DB row, never a certificate
   (promotion.py:508-529); the engine hard-requires a certificate (engine.py:886-946);
   the only issuers are tests. The architecture's most important interface was never
   integrated — everything downstream of it (paper, research feedback) is consequently dead.
6. **Documentation has outrun implementation**: 34+ ADRs, ARCHITECTURE.md, phase-j docs
   referencing non-existent classes (HealthReporter, telemetry.py:9-33), runbook claims
   that don't match behavior ("System state: ACTIVE" after warmup), Monte Carlo documented
   with no code, metrics documented that don't exist (_metrics_integration.py:14-54).
   The governance layer now costs more to maintain than it protects.
7. **Environment lock-in residue**: ops scripts hardcode Windows paths (`D:\projects\...`);
   runbook says Python 3.14+, pyproject requires ≥3.12, shipped .so is cp313; one
   uncommitted data-module edit (fincept_feed in data/__init__.py) from another agent.
8. **TOCTOU/threading is unaddressed**: nonce check-then-act (engine.py:941-943), no
   concurrency tests, engine assumes single-threaded operation without enforcing it.

## 3. Does the architecture slow research or experimentation?

Yes, in one specific way: **the path from a candidate to paper evidence requires the
promotion gate, the qualification DB (which does not exist in the repo), a certificate
issuer (which does not exist), a session initializer (not wired into the entrypoint), and
a working paper loop (crashes)**. A researcher who finds a promising backtest has no
mechanism to see how it behaves against a broker simulator. The research loop terminates
at the PDF. That single seam is why the project feels "architecturally complete but
economically dead."

## 4. Boundary-by-boundary verdict

| Boundary | Verdict |
|---|---|
| Rust/Python | Good. Keep. (The .so is buildable via maturin; wheel-vs-src drift is a packaging-discipline problem, not an architecture problem.) |
| Event architecture | Good in core (append-only store, dedup); the fill-delta restore bug (B4) is the one real flaw. |
| State ownership | Good: portfolio + event store are authorities; broker is reconciled. |
| Persistence | Good in engine; absent in research path (results are JSON bundles + a DB that doesn't exist in-tree). |
| Broker boundary | Fine adapters; Fincept is scaffolding; IBKR paper-locked; no live broker economics recording. |
| Strategy boundary | Good (registry + lifecycle states); but lifecycle machine (CANDIDATE→…→RETIRED) has never had an ACTIVE strategy pass through it. |
| Risk boundary | Good and tested; documented limits (net/sector/vol) absent from code. |
| AI boundary | Correctly advisory; incorrectly dead (nothing imports it). Either wire the advisory loop or archive it. |
| Configuration | Risk: two miswired positional args (paper_session gross cap; papertrade daily-loss-as-gross). |

## 5. What to change (architecture-level)

1. Pick ONE qualification authority (the gate), delete the Path-1 direct-DB write.
2. Complete the admission seam: promotion (or an explicit dev-cert flow) issues a
   certificate; paper/backtest entrypoints consume it; session init is wired into the
   entrypoint. This is ~2 days of work and unblocks everything downstream.
3. Collapse to one fill/cost model object consumed by harness AND engine; kill the
   ReplayEngine zero-cost defaults.
4. Archive (not delete) the dead layers; stop writing ADRs for systems before they are
   wired. Adopt a rule: an ADR lands with its wiring commit or not at all.
5. Move the monkeypatch opt-in (test architecture) per the Test Effectiveness report.
