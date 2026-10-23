# TITAN STOP BUILDING

**Date:** 2026-09-29.

**The governing fact from this audit: TITAN has ~27.4k LOC of code, ~14.5k LOC of governance
documentation, 34 ADRs, 6 backtest simulators, and a research loop that cannot detect a
Sharpe-1.0 FX strategy in 12 months of data.** The constraint is not capability. It is that
every unit of new capability has been added on top of a broken measurement instrument.

**Rule: nothing new gets built until the instrument is fixed and has produced one trustworthy
result.**

## DELETE

### 1. `tests/conftest.py:76-85` — the global `submit_intent` patch · **FIRST**
```python
@pytest.fixture(autouse=True)
def patch_submit_intent_for_legacy_tests(monkeypatch, request):
    monkeypatch.setattr(PaperTradingEngine, "submit_intent", submit_intent_patched)
```
This autouse fixture removes the certificate gate for nearly the whole suite. **It is the direct
cause of 1180 green tests over a runtime that dies on its first signal.**

**Delete it. The suite will go red — that redness is the correct state and must stay until the
runtime is genuinely clean.** One test file (`test_execution_integrity.py`) is exempt today; make
that the only exemption.

### 2. Five of six backtest simulators · and 4 of 5 copies of `_compute_max_drawdown`

`_compute_max_drawdown` appears at `factor_simulator.py:174`, `equities_factor_screen_006.py:90`,
`equities_event_screen_007.py:93`, `equities_event_screen_008.py:93`, `render/report.py:6`.
Five implementations is the direct mechanism by which mutation M11 (inverted drawdown sign)
survived the suite.

**Delete four; extract one.** Every metric defect found in this audit (C8 `sqrt(252)`, C9
`profit_factor = 100.0`, C11 power gate on bars, C12 `p4` overlapping returns) exists *because*
there are five implementations. **Consolidating is not tidiness — it is the bug fix.**

Six cost models likewise: `crypto_costs.py:11`, `factor_simulator.py:24`, `fx_costs.py:13`,
`fills.py:24`, plus inline logic in `promotion.py`, `harness.py`, `walkforward.py`, `shadow.py`,
and 5 `research/*.py`. **This is the direct mechanism of the 0.9 bp vs 20 bp contradiction**
that killed EXP-00022.

### 3. `src/titan/memory/` — vector memory (172 LOC, entirely dead)
`embedding_vector` is populated **nowhere** in `src/` or `scripts/`. `search_similar_trades` can
never match. `distillation.py` has zero prod importers. `AI_GOVERNANCE.md:17` specifies embedding
models, access classes and expiry for a system with no model.

**Delete both the code and the governance doc.** A spec for an unimplemented subsystem is worse
than nothing — it reads as a capability in any review.

### 4. `src/titan/execution/fincept_adapter.py` — a stub
`fincept_adapter.py:29` `import fincept_native` → `AdapterError` at runtime. No `query_order`
method, so the engine **fails closed** at `_recover_unresolved_orders:833`. Exported in
`__all__:45`, imported by nothing in `scripts/`.

**Delete.** It is a non-functional surface in `__all__`, and TITAN's own reference-repo
critique of Fincept (`PROJECT_TITAN.md:17`: *"un-reconciled execution"*) applies to it directly.

### 5. Four dead entrypoints
- `scripts/backtest_multitimeframe.py:175` — `TypeError` on run
- `src/titan/cli.py:127` — `TypeError` (`transition_on_boot` signature mismatch)
- `scripts/paper_session.py:728 --dashboard` — `dashboard/` is gitignored (`.gitignore:40`) and absent
- `scripts/supervise_paper_session.sh:8`, `run_tws_paper_loop.sh:8` — hardcoded **Windows** path
  `/d/projects/Project TITAN` on a Linux checkout

**Delete, or fix. Shipping known-broken entrypoints is worse than not shipping them.**

### 6. The `--dashboard` flag and the gitignored dashboard
A CLI flag that raises `ModuleNotFoundError` on a Linux checkout. **Delete the flag.**

## FREEZE

### 7. All new strategy hypotheses — until the instrument is repaired
Six structural axes, ~546 trials, 2 asset classes have been run against a harness with a
single-trade screen, a 20-pip FX cost, and a hard-wired `replicated=False`. **A new hypothesis
added today produces another uninterpretable number.** Freeze until the DSR/power gate exists.

### 8. All new infrastructure
Nothing new in: message buses, services, CQRS projections, feature stores, metric pipelines,
dashboards, stream processing, data-lake layers. Infrastructure is **2.4% of LOC** and is
**not the bottleneck**. The bottleneck is that a screen trades once and a Sharpe uses
`sqrt(252)`.

### 9. Rust feature work
The core is 2,882 non-test LOC, mutation-resistant, and correct. **Freeze it.** Every defect
found is in Python. The "do we need Rust" question is settled — the answer is *the Rust you have
is the good part; the problem is the Python above it*.

### 10. Documentation growth
~14.5k LOC across ~140 files, 34 ADRs, 23 specifications — coexisting with `profit_factor`
returning `100.0` permanently and `ruff` never being run. **Freeze new ADRs.** No ADR may be
written for a decision that has no corresponding executable check.

## DEFER

### 11. Vector memory, embeddings, semantic search over trades
Requires a working research loop generating trades. **There are none.** Defer indefinitely.

### 12. Portfolio construction — HRP, rebalancing, covariance, capital allocation
`hrp_allocator.py`, `rebalancing.py`, `pipeline.py` are all dead code. Genuinely the largest
underbuild — **but pointless until a second strategy survives.** Defer. Keep the code; stop
investing in it.

### 13. Tick/L2 / market microstructure / order flow
`PIVOT_DECISION.md:20-21` identifies these as the only classes with theorized non-zero alpha,
and `ALPHA_SEARCH_TERMINAL_REPORT.md:73` skipped them "by budget."

**Defer, but note the reason is wrong.** They are the *highest-value* remaining classes
(Osler NY Fed SR 125: stops are 5–10% of FX deal flow and cascade). They are deferred only
until the instrument is repaired — not skipped.

### 14. Reinforcement learning
**No data pipeline, no statistics layer, no running runtime, and no surviving strategy.**
FinRL is classical RL (ElegantRL/TD3/SB3/RLlib) — not the LLM-flavoured thing the name suggests,
and not applicable here. **Defer indefinitely.**

## SIMPLIFY

### 15. `execution/engine.py` — 1,752 lines, 29 imports, a god object
It *is* the broker/strategy/risk boundary. Split on the boundaries it already has:
cert/scope, risk, execution, fill absorption, reconciliation, authorization. **Mechanical
extraction only — no new abstractions, no new interfaces, no behaviour change.**

### 16. The strategy registry
10 registered strategies, **6 of which crash** on a daily-close feed
(`bridge.py:110` passes `{"close": price}` when `bar is None`). A registry whose entries mostly
do not run is worse than a short list. **Fix the 6, or cut to the ones that work.**

### 17. `walk_forward()` — delete it and use the real optimizer
`harness.py:383-412` is a sliding-window backtest with fixed params, exported as
`walk_forward.mean_sharpe`. The genuine `WalkForwardOptimizer` (`walkforward.py:130`) is called
by **no experiment**. **Delete the fake. Use the real one, or report no WFO at all.**
A misleading key is worse than a missing one.

### 18. The governance apparatus
34 ADRs, `check_adr_gate.py` in CI (which gates **document formatting**,
`scripts/check_adr_gate.py:12-16`), `AI_GOVERNANCE.md`, `OPERATING_PRINCIPLES.md`.

**Keep the principles. Cut the apparatus to what enforces something.** An ADR whose decision
has no executable check is a comment.

### 19. The `EXP-00031` "canonical reproduction" — delete the claim, not the code
It produced 54 trade records where the original produced 163, used `trail_mult=3.0` vs
`2.0×ATR-14`, charged a different fee schedule, and ran through a long-only harness. **It is
not a reproduction** and it was used to close the FX candidate. Delete the artifact; the FX
candidate is **re-opened** pending the corrected re-run.

## STOP BUILDING — the summary

| Action | Item | Why |
|---|---|---|
| **DELETE** | conftest `submit_intent` patch | Hides a total runtime failure |
| **DELETE** | 5 of 6 simulators, 4 of 5 drawdown copies, 5 of 6 cost models | The mechanism of every metric defect |
| **DELETE** | `memory/` + `AI_GOVERNANCE.md` | 0.6% of LOC, entirely dead, spec'd as if built |
| **DELETE** | Fincept adapter, 4 dead entrypoints, `--dashboard` | Non-functional surface |
| **FREEZE** | New hypotheses, new infrastructure, Rust features, docs | Broken instrument underneath |
| **DEFER** | Vector memory, portfolio construction, tick/L2, RL | Premature or wrong-reason-deferred |
| **SIMPLIFY** | `engine.py`, the strategy registry, `walk_forward()`, the ADR apparatus | Complexity that hides the real problem |

**The one-line version of this document:**

> TITAN should stop building because it has already built more than it can measure, and every
> new component is a new place for a defect like `sqrt(252)` on 4-hour bars to hide.
