# BUG AND RELIABILITY REPORT

**Date:** 2026-09-29. Every CONFIRMED item was reproduced or read directly by the auditor.

Legend: **CONFIRMED** (reproduced/verified) · **LIKELY** (code-smell, not proven) ·
**HYPOTHESIS** (untested).

---

## CRITICAL — voids published evidence

### C1 · Screen never exits a position → ONE TRADE PER HYPOTHESIS · **CONFIRMED**
`scripts/screening/screen.py:40-61`. `pos` is set at `:49` and never reset to `0`; the only
exit is `:56-61` (final bar). `n_trades` increments exactly once.
**Verified:** `scripts/screening/results.json` has `"trades": 1` in **every** per-pair cell.
**Impact:** voids the *"0/15 concepts"* row of `ALPHA_SEARCH_TERMINAL_REPORT.md:27`.

### C2 · `replicated` hard-wired `False` ⇒ zero survivors is a constant · **CONFIRMED**
Defaults at `crypto_screen.py:140,254`, `crypto_screen_002.py:93`, `crypto_screen_003.py:91`,
`equities_factor_screen_006.py:380,477`, `equities_event_screen_007.py`, `equities_event_screen_008.py:469,566`.
Gate: `rep_ok = replicated` (`crypto_screen.py:115`). No production call site passes `True`.
**Verified:** `CRYPTO-001-evidence-bundle.json` → `{"oos_net_positive": true, "ic_frac": true,
"concentration": true, "adverse_capacity": true, "replication": false}` with `n_trades: 1`.
`EQ-007` → 5 of 9 gates true including `oos_net_sharpe` (1.249 ≥ 1.0).

### C3 · Failed gates are invisible to the decision function · **CONFIRMED**
`validator.py:262-265` flags a failure only if the value is `False` or a string containing
`"❌"`. `:376` stores `cost_msg` (a string) on failure.
**Verified:** the character `❌` appears **exactly once** in `validator.py` — at line 265,
inside the detector itself. No message string can ever match.
**Impact:** `EXP-00017` and `EXP-00019` both committed `"decision": "promote"` with failing
IC and cost gates.

### C4 · FX cost constant 10–100× overstated · **CONFIRMED**
`run_fx_experiments.py:10-11`: *"cost_bps=10 (~1 pip retail round trip)"*. 1 pip = 1 bp, not 10.
`validator.py:194,214` subtracts `2 × 0.001` = 20 bps. `run_exp22_xs_momentum.py:26` uses
10 bps/period = 5.20%/yr against a 5.4%/yr gross edge.
**Counter-example in the same repo:** `run_traderdev_families.py:23-24` uses 0.9 bp RT.

### C5 · Research harness is long-only · **CONFIRMED**
`harness.py:99-151`. `if pending_signal == "BUY" and not in_position` / `elif pending_signal ==
"SELL" and in_position`. **No short branch exists.** Strategies that emit `SELL` while flat
(`traderdev_ema9vwap.py:139-143` sets `_position = -1`) do nothing, then desynchronise.
**Impact:** EXP-00031 "canonical reproduction" produced 54 trade records where the original
produced 163. It is not a reproduction.

### C6 · PnL and trade counts double-counted · **CONFIRMED**
```python
135:  trades[-1]["pnl"] = pnl       # written onto the ENTRY record
137:  trades.append({"pnl": pnl, ...})   # and onto a NEW record
```
**Consequences:** `total_trades` = 2× round trips (so `check_min_trades(30)` is effectively a
15-trade gate); `gross_pnl`/`net_pnl` (`harness.py:299-311`) report **2× the true PnL** —
these are the figures in the EXP-00031 report; `block_bootstrap(trades)` (`metrics.py:352-382`)
resamples a list where every PnL appears twice → **bootstrap CIs inflated 2×**, making
under-powered backtests look *more* significant.

### C7 · `walk_forward()` performs no walk-forward · **CONFIRMED**
`harness.py:383-412`: a sliding window over `train_size + step`, run with the **same params**,
no training, no parameter selection, no test partition. Its mean Sharpe is exported as
`to_dict()["walk_forward"]["mean_sharpe"]` (`:550-555`). The genuine `WalkForwardOptimizer`
(`walkforward.py:130`) is reachable only from `mcp_bridge.py:81` and `research/cli.py:275` —
**no experiment calls it.**

### C8 · Sharpe hard-codes `sqrt(252)` on per-bar returns · **CONFIRMED**
`results.py:100` and `metrics.py:153`. `StrategyRunner.run` emits one equity point per input bar.
4h FX (2,190 bars/yr) → Sharpe **understated 3.0×**; 5m → **overstated 11.6×**. No caller can
specify the frequency. The variable is even named `daily_returns` (`results.py:47`).

### C9 · `profit_factor` returns a perfect score when there are no losses · **CONFIRMED**
`results.py:62`: `profit_factor = 100.0 if gross_loss < 0.01 else min(gross_profit/gross_loss, 100.0)`.

### C10 · Bonferroni correction computed and discarded · **CONFIRMED**
`validator.py:271-273`: `alpha = 0.05 / total_experiments` is formatted into a `reasons` string
and never used. `check_ic_significance` (`:153-159`) uses hard `p > 0.05`. 546 trials were
evaluated at α=0.05 instead of 9.2×10⁻⁵.
`walkforward.py:163-164`'s `mt_penalty = sqrt(2 lnM/N)` is applied to an **already-annualised**
Sharpe — a dimension mismatch that makes it ≈0.13 against a score of ≈2 (inert).

### C11 · Power gate evaluated against bars, not trades · **CONFIRMED**
`traderdev_fx_screen.py:361` checks `st["n"] >= 60` where `n = len(rets)` (`:337`) = bar count.
**Verified:** every one of the 16 cells reports `n = 644`. The gate never bound.

### C12 · `p4` annualizes cumulative-since-entry returns · **CONFIRMED**
`p4_multi_tf_confluence.py:138-149` appends `(close-entry)/entry` **per bar** while in a
position — overlapping, cumulative, not per-period — then multiplies by `sqrt(BARS_PER_YEAR)`.
**Verified in the committed artifact:** `P4_multi_tf_confluence.json` reports
`sharpe_ungated: 19.25` (EURUSD) and `21.13` (GBPUSD) on 4h FX. A 4h EURUSD strategy cannot
have Sharpe 19–21. The bootstrap "decisive test" at `:156` then pairs gated (18 trades) with
ungated (47 trades) by index, silently truncated — a meaningless pairing.

### C13 · Same-bar lookahead in P2 · **CONFIRMED** (inflationary)
`p2_gold_macro_momentum.py:118-124`: enters at bar *i*'s close and immediately collects
`gold_r[i] = close[i]/close[i-1] - 1`. The exit bar does the same. **Direction is inflationary,
so P2's FAIL survives this bug** — recorded for completeness.

### C14 · Crypto simulator never marks price PnL · **CONFIRMED**
`crypto_simulator.py:126-151`. `attr.price` initialised to `Decimal("0")` and **never
assigned**. All reported "net" is funding income minus costs, with **zero price risk and zero
basis PnL ever realised**. The spot hedge (`:147-149`) is charged taker fee + spread + impact on
every rebalance, including perp long→short flips with no change in spot exposure.
**Consequence:** CRYPTO-001 reports **+482 USD from 1 trade in 6 events**; CRYPTO-002/003 report
**0 OOS trades**. These are empty files with a verdict attached.

### C15 · Preregistered thresholds are non-binding · **CONFIRMED**
`equities_factor_screen_006.py:384-389` reads `prereg.pass_criteria.get(...)` with defaults
`min_sharpe=1.0`, `min_ic_positive_frac=0.70`, `min_mean_rank_ic=0.05`, `max_drawdown=0.12`.
`EQ-002-prereg.json` specifies **none** of these keys. The evaluator silently imposed criteria
that appear in no preregistration. **Preregistration is decorative for any hypothesis that
omits a key.**

---

## HIGH — the runtime cannot trade

### C16 · Paper session dies on the first signal · **CONFIRMED**
`bridge.py:34` defaults `certificate_ref = "dummy_cert_for_paper_session"`; `engine.py:890-895`
`json.loads()` it → `JSONDecodeError` → `raise ValueError`; `paper_session.py:914` calls
`engine.submit_intent(intent)` with **no `try/except`**. Same in `backtest_smoke.py:152` and
`papertrade.py:144,166`.
**Why 1180 tests pass:** `tests/conftest.py:81-85`, an `autouse` fixture, replaces
`submit_intent` with `_submit_intent_core` — skipping the certificate gate — for every test
lacking `e2e`/`adversarial`/`test_execution_integrity` in the node id.

### C17 · `cli.py` recovery path raises `TypeError` · **CONFIRMED**
`cli.py:127` calls `transition_on_boot(..., store_was_empty=...)`; `restart.py:121` accepts 2 args.

### C18 · Hardcoded Windows paths on a Linux checkout · **CONFIRMED**
`scripts/supervise_paper_session.sh:8` and `run_tws_paper_loop.sh:8` — `cd "/d/projects/Project TITAN"`.

### C19 · Correlation risk rule can never fire · **CONFIRMED**
`paper_session.py:861` writes `_last_prices` directly instead of calling `engine.update_price()`;
`risk.rs:706` reads the engine's own state.

### C20 · Dual authorization is weaker on release than on init · **CONFIRMED**
`engine.py:1607` `_require_release_authorization` does not pass `authorized_approvers`
(unlike `engine.py:1524-1526`). Any 2 distinct strings pass.

### C21 · HMAC risk secret is a hardcoded literal · **CONFIRMED**
`engine.py:1086` — default `"TITAN_RISK_SECRET_KEY"`. Not sourced from env.

---

## MEDIUM — dead, unwired, or lying

| # | Defect | Location |
|---|---|---|
| C22 | `RiskDecision(...)` constructed nowhere; `Risk.spec.md:44` "All decisions are persisted" is **false** | grep 0 prod sites |
| C23 | `correlation_id` never passed; `_trace_decision` no-ops on empty — the whole decision-trace subsystem is inert | `engine.py:585`, `messages.rs:60` |
| C24 | `RiskDecisionRecorded` fields exist, never written | `messages.rs:267` |
| C25 | `contracts/*.schema.json` — zero Python imports; events written with `schema_version=100` vs schema `v1` | `PROJECT_STRUCTURE.md:44`, `messages.rs:58` |
| C26 | 15 of 25 Prometheus metrics never written; `cli.py:142` reads `drift_count_critical` → health check always reports "Broker truth matches: YES" | `operations/export.py:79` |
| C27 | `embedding_vector` populated nowhere — `search_similar_trades` can never match | `memory/vector_memory.py:84-97` |
| C28 | `mcp_bridge.py:66` returns **fabricated** strategy names (`ma_crossover`, `bollinger_breakout` — neither in the registry) | |
| C29 | `financial` "Sharpe" gate is `net > 0` — a sign test; with n=1 it is a one-observation sign test | `crypto_screen.py:111` |
| C30 | `concentration = 1.0/len(universe)` — a tautology that passes by construction | `crypto_screen.py:193` |
| C31 | `annualized_turnover_pct` returns the raw total | `metrics.py:41-42` |
| C32 | `per_regime[rn]["trades"]` assigns the running cumulative counter | `metrics.py:337` |
| C33 | `sig_session_ema` derives session from bar index `mod 6`, not timestamps (dropped at `:46-52`) | `traderdev_fx_screen.py:210-228` |
| C34 | `dual_ma` / `vwap_reversion` have **zero** references in `tests/` | verified |
| C35 | 6 of 10 registered strategies crash on a daily-close feed (`bridge.py:110` passes `{"close": price}` when `bar is None`) | reproduced `TypeError` |
| C36 | `backtest_multitimeframe.py:175` `TypeError`; `paper_session.py --dashboard` `ModuleNotFoundError` (`dashboard/` is gitignored, absent); `scripts/monitor.py` has no argparse | |
| C37 | Impossible metrics archived as evidence: EQ-Micro-001 Sharpe **−32.47**, DD **99.9%**, 568× monthly turnover. No validator rejects out-of-range values | `EQ-Micro-001-evidence-bundle.json` |
| C38 | `BARS_PER_YEAR = 2190` applied to Dukascopy data that has **1,610** 4h bars/yr → Sharpe overstated **1.167×** (toward passing) | `traderdev_fx_screen.py:41` |
| C39 | `ann_ret = mu × 2190` — arithmetic, ignores compounding | `traderdev_fx_screen.py:337` |
| C40 | `exposure_adjusted_benchmark` reads `result.equity_curve`, an attribute `BacktestResult` does not define → dead branch, silent fallthrough | `metrics.py:176-205` |
| C41 | 92 Rust `#[test]` functions never run under pytest (separate CI job only); `rustup`/`cargo` absent locally, so the `.so` cannot be rebuilt | `core/src/*.rs` |
| C42 | Two Windows paths in shell scripts | C18 |
| C43 | IS/OOS rebalance grids anchored to each partition's start → different monthly phase in IS vs OOS | `equities_factor_screen_006.py:136,143` |
| C44 | IS and OOS use different gate sets for the same hypothesis ID; `run_eq002_core7.py:165-172` has **no significance test at all** | → `EQ-002-core7` marked `"candidate"` |
| C45 | `promotion.py:82-106` is long/flat only, 1.5 bps, **zero spread**; self-disclosed as inflating Sharpe to 5.93/7.13 vs the real +71.8/+336.5 pips | `ema9vwap_promotion_report.md:35-43` |
| C46 | `trade[].pnl` written to the entry record means `trades[-1]` semantics differ from every other consumer | `harness.py:135` |
| C47 | `EXP-00025_traderdev_families.json` missing the `pnl_list` written at `run_traderdev_families.py:369` — artifact truncated after the run | verified |
| C48 | Preregs and results committed in the same commit (`80ee522`); prereg JSONs carry no timestamp field → no preregistration is provably prior | `git log --diff-filter=A` |

---

## LIKELY (code-smell, not proven)

- **L1** `traderdev_fx_screen.py:318` charges `COST_RT/2` per flip; a long→short flip is two
  fills = a full round turn. **Under-charges flips 2×** — wrong direction for a conservative protocol.
- **L2** `_compute_max_drawdown` is **copy-pasted 5×** (`factor_simulator.py:174`,
  `equities_factor_screen_006.py:90`, `equities_event_screen_007.py:93`,
  `equities_event_screen_008.py:93`, `render/report.py:6`). Five chances to disagree.
- **L3** "EMA200" is implemented as `sma(s,200)`; `_rng()` uses mean(bar range), not true range.
  EXP-00031's reproduction used `trail_mult=3.0` vs EXP-00025's `2.0` — a **different strategy**.
- **L4** `promotion.py` and `harness.py` import from `titan.research` into the execution hot path
  (`execution/engine.py:48`) — a layering inversion.
- **L5** `knowledge/experiments/` is empty despite `RESEARCH_CONSTITUTION.md:86` mandating a
  journal per experiment. The "absorbing negative result" protocol (§124) is unimplemented.

## HYPOTHESIS (untested, do not act on)

- **H1** The risk gate's correlation rule may be unreachable in practice (`risk.rs:706` reads
  engine state; C19 suggests the engine state is never updated from the runner). Not traced
  end-to-end.
- **H2** `settlement`/`carry` handling for overnight FX financing appears absent from the
  research harness; if correct carry is missing, carry strategies are structurally unrepresentable.
  Not confirmed.

## Mutation testing summary (20 mutants, full suite)

**Killed (8):** risk-gate bypass · 10× looser risk limits · fill slippage sign · trailing stop
direction · `Sizer` step-size floor · 10× position size · crypto taker fee zeroed · total-PnL sign.
Plus a full realized-PnL sign-flip across the suite → **35 failures**.

**Survived (6) — the dangerous ones:**
`dual_ma` hardcoded to `"BUY"` · `vwap_reversion` SELL→BUY · `abs()` on Sharpe ·
`profit_factor` → `100.0` · drawdown sign inverted · `sqrt(252)`→`sqrt(12)` and →`sqrt(52)`.

**Interpretation:** the Rust kernel and the risk/execution/fill layer are genuinely protected.
**The strategy-signal layer and the performance-metric layer have ~0% effective coverage** —
and those are exactly the components that decide whether TITAN makes money.
