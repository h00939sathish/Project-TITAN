# TEST EFFECTIVENESS REPORT

**Date:** 2026-09-29. Repo verified byte-identical to baseline after the audit.

## 1. Real test results

```
1180 passed, 17 skipped, 6 warnings in 64.24s
```

The 1196 claim is accurate as a *count*. The 17 skips are all credential-gated and
legitimate — **fake coverage from skipping is not the problem here.**

Line coverage is genuinely high: **85%** across backtest/risk/execution. This is not a
"no tests" repo. **It is a repo where coverage measures line execution, not correctness.**

## 2. Mutation testing — the decisive experiment

20 mutants run against the full suite in a sandbox copy. **8 killed, 6 survived** (6 not
informative on a bare function).

### Survivors — these are the dangerous ones

| # | Mutation | Result | What it proves |
|---|---|---|---|
| **M8** | `dual_ma.py:29` → `return "BUY"` (strategy can **never short**) | **SURVIVED** | A two-sided strategy hardcoded to one side is indistinguishable from correct |
| **M7** | `dual_ma.py:29` `>` → `>=` (dead short leg) | **SURVIVED** | |
| **M9** | `vwap_reversion.py:59` SELL→BUY (long-only blindness) | **SURVIVED** | |
| **M17** | `results.py:100` → **`abs(...)`** on Sharpe | **SURVIVED** | **Every losing strategy reports a positive Sharpe** |
| **M18** | `results.py:62` `profit_factor` → hardcoded **`100.0`** | **SURVIVED** | A perfect score for every strategy, forever |
| **M11** | `results.py:43` drawdown sign inverted | **SURVIVED** | |
| **M10** | `results.py:100` `sqrt(252)` → `sqrt(12)` (Sharpe off 4.6×) | **SURVIVED** | |
| **M20** | `results.py:108` `sqrt(252)` → `sqrt(52)` (vol off 2.2×) | **SURVIVED** | |

**M17 and M18 are the headline.** `sharpe_ratio` and `profit_factor` are the inputs to
`src/titan/research/promotion.py` and to the ADR-032 promotion certificates. **The ratchet
that decides whether a strategy goes live cannot tell a good strategy from a broken one.**

### Killed — the good news

`Sizer` step-size floor (M1) · 10× position size (M2) · fill slippage sign (M3) ·
crypto taker fee zeroed (M6) · `total_pnl` sign (M13) · trailing stop direction (M15) ·
**risk-gate bypass (M16)** · risk limits 10× looser (M12) · FX USD invariant (M19).

Plus: a **realized-PnL sign-flip injected across the whole suite → 35 failures.** The Rust
ledger is genuinely defended. That is the one piece of hard evidence in this repo.

**The boundary is razor-sharp:** execution, risk gating, fill pricing and the Rust core are
properly defended. **The hole is specifically strategy signals and performance metrics.**

## 3. Root cause of the survivors — self-consistency, not correctness

Every assertion on the economic metrics is **self-consistency**, never absolute value:

```python
tests/research/test_independent_reproduction.py:102   assert r1.sharpe_ratio == r2.sharpe_ratio
tests/research/test_independent_reproduction.py:103   assert r1.max_drawdown_pct == r2.max_drawdown_pct
tests/replay/test_deterministic_replay.py:45           assert result1 == result2   # dict compared with itself
```

Determinism tests (run twice, compare) prove **reproducibility**, never **correctness**.

The canonical weak assertion is at `tests/replay/test_deterministic_replay.py:74`, in a test
literally named `test_replay_with_sell` / "correct cash and position":

```python
assert cash_amount > 0
```

Cash is positive after any round trip, **including a catastrophically wrong one.**

**Exactly ONE test in 1180 asserts an absolute PnL number:** `tests/backtest/test_exit_intents.py:434`
(`== -95.0`). The auditor hand-verified the Rust core independently (buy 100@50 → sell 100@60 =
`+1000`; short round trip = `−1000`) — **it is correct, and unpinned.**

## 4. The 3-function experiment (real body vs mocked)

| Production function | Real-body executions | Mocked away |
|---|---|---|
| `core/src/portfolio.rs` `PortfolioEngine` | 13 files / 30 refs, **always the real Rust class** | 0 — cannot be mocked (PyO3, non-subclassable) |
| `src/titan/strategies/sizing.py` `Sizer.size` | **3 call sites, 1 test file** | 0 |
| `src/titan/backtest/fills.py` `BarConservativeFillModel.fill` | ~6 files | 0 |

The ratio misleads in both directions: the Rust core is **structurally** well-protected (0 mock
escapes; corrupting it fails 35 tests), while the Python strategy layer is effectively **0%**
covered — `dual_ma` and `vwap_reversion` have **zero** references anywhere in `tests/`.

## 5. False confidence, ranked

1. **Performance metrics are unfalsifiable** (M10, M11, M17, M18, M20). Sharpe, profit factor
   and drawdown can be arbitrarily wrong with a green suite. **Since promotion decisions run off
   these, the governance gate inherits the blind spot.** Highest-risk defect in the repo.
2. **Strategy signal logic is untested** (M7, M8, M9). Two strategy modules can be deleted and
   the suite stays green. No test asserts a strategy can produce **both** sides from a symmetric
   input.
3. **The suite proves the runtime works by not running it.** `tests/conftest.py:81-85` is an
   `autouse` fixture that replaces `submit_intent` with `_submit_intent_core`, skipping the
   certificate gate — **the exact gate the production runtime hits and dies on**. The comment
   claims the integrity tests "will NOT use this patch, proving the engine works exactly as
   designed out of the box". It proves the opposite: the suite is green *because* the failure
   mode is patched out.
4. **87–92 Rust `#[test]` functions never run under pytest.** `grep -c "#\[test\]" core/src/*.rs`
   = 10+5+9+22+8+38 = **92**. The advertised "1196 tests" excludes the entire Rust unit-test
   suite; it runs only in the separate `rust` CI job. `rustup`/`cargo` are **absent locally**, so
   the prebuilt `.so` (Sep 22) cannot be rebuilt or verified by a developer.
5. **Tests with side effects.** The sandbox run revealed a code path writing into the tracked
   artifact `research/backtest_results_summary.json` (caused by a symlink; the real suite is
   clean — but the test/data path boundary is not enforced).
6. **No coverage floor, no mutation testing, no import-linter** — which is why the
   `execution/engine.py:48` layering inversion (execution importing `titan.research`) has stood.

## 6. "If this test passes, what important failure could still happen?"

| Test class | Failure that still occurs |
|---|---|
| `test_deterministic_replay.py` | A replay that is *deterministically wrong*. A sign-flipped PnL replays identically. |
| `test_independent_reproduction.py` | Two implementations that agree because both are wrong. The EXP-00031 "reproduction" is exactly this. |
| `test_replay_with_sell` (`assert cash > 0`) | Any magnitude of PnL error, including a total loss booked as a gain. |
| `test_duplicate_fill.py` | Double-counting on the *other* side — the live bug is double-counting in `harness.py:135-147`, which no test covers. |
| `test_circuit_breaker_wired.py` | Breaker that fires one cycle too late. |
| All of the above | **The paper runtime crashing on its first trade** — the one failure that has actually happened. |
| All of the above | Sharpe computed with `abs()`. |

## 7. CI gate strength

`.github/workflows/ci.yml` — 1 workflow, 2 jobs.

**Genuinely blocking:** `cargo check`, `cargo clippy -D warnings`, `cargo test`; `pytest tests/`;
a throughput benchmark (`test_throughput.py:62`, < 15.0s). `python scripts/check_adr_gate.py`
verifies ADRs have `status:`/`date:`/`owner:` — **it gates document formatting, not behavior**
(`scripts/check_adr_gate.py:12-16`).

**Not gating:**
- **`ruff` is installed and never invoked.** No `run:` step calls it. **1,593 violations** accumulate silently.
- **`mypy --strict` is `continue-on-error: true`** (`ci.yml:44-46`).
- **`tests/test_ci_workflow.py:47-56` actively asserts mypy stays non-blocking** — a test enforcing the *absence* of a gate.
- The comment is stale: *"mypy reports **387** errors"* → **actual: 2,368 errors in 213 files**;
  *"ruff **1580** violations"* → **actual 1,593**.

**Most damning:** commit `698cd7b` ("repoint dead workflow trigger to master trunk") reveals the
workflow triggered only on `main`, a branch that **does not exist**. **The entire CI gate never
ran** until that commit. Four commits have landed since. The history contains commits that were
never gated by anything.

## 8. Doc-to-code ratio

| | Count | LOC |
|---|---|---|
| Code (`src/titan`) | 143 files | 23,242 |
| Rust (`core/src`) | 9 files | 4,123 |
| Docs + specifications | 118 files | 13,816 |
| Root markdown | 13 files | 756 |
| **Total governance** | **~140 files** | **~14,572** |

**Ratio ≈ 0.53 doc-LOC per code-LOC**, ~1 governance file per 5 source files, 34 ADRs.
This is the **process-as-substitute** pattern — and the mutation results give it teeth:
34 ADRs and 13.8k lines of decision records coexist with `profit_factor` returning `100.0`
permanently. ADR-034 even formalizes *not* enforcing mypy. **The ADR count is evidence of
deliberation, not of correctness.**

## 9. Fixes, in cost order

1. **One hand-computed fixture:** fixed return series → asserted absolute Sharpe, drawdown,
   profit factor, volatility. *Kills M10, M11, M17, M18, M20 in ~20 lines.* **Do this first.**
2. **A strategy-invariant test:** for each registered strategy, assert a symmetric input
   sequence produces **both** BUY and SELL. *Kills M7, M8, M9.* **~30 lines.**
3. **Delete `tests/conftest.py:76-85`.** The suite must go red and stay red until the runtime
   path is genuinely clean. *This is the highest-value deletion in the repo.*
4. **Wrap `paper_session.py:914` in `try/except`.** One bad intent must not kill a session.
5. **Deduplicate `_compute_max_drawdown`** (5 copies → 1). Removes the M11 evasion surface.
6. **Wire `ruff` into CI** — already installed, already failing 1,593 times.
7. **Record `n_trades` per bar in `traderdev_fx_screen.py:338`** and evaluate the power gate on
   trades, not bars.
8. Add `import-linter` to block `execution/` → `research/`.

**Skipped:** full `mutmut` integration and the import-linter — both worth it, but they are
tooling, not the four assertions above that would have caught every surviving mutant.
