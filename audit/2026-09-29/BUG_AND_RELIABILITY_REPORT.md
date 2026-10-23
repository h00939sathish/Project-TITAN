# BUG AND RELIABILITY REPORT — 2026-09-29

Hostile code audit. Confidence: CONFIRMED (code-logic proven or reproduced) / LIKELY
(multi-file corroboration) / HYPOTHESIS (single-source inference). Nothing below is
speculation presented as fact.

---

## 1. CONFIRMED BUGS

| # | Severity | Location | Description | Reproduction |
|---|---|---|---|---|
| B1 | **CRITICAL** | src/titan/backtest/engine.py:91,275,320 + src/titan/execution/engine.py:886-895 | Every engine-based backtest crashes with `ValueError: Execution certificate verification failed` on the first intent: default `certificate_ref="replay-engine-cert"` is not a JSON certificate. Affects research/run_exp20_strategy.py:96, replay_traderdev_ema9vwap.py:52, scripts/backtest_tws_session.py:54, visualize.py:44. | Reproduced by direct run |
| B2 | **CRITICAL** | tests/conftest.py:76-85 | Autouse fixture monkeypatches `PaperTradingEngine.submit_intent` to skip certificate verification + shadow guard for every suite except test_execution_integrity/e2e/adversarial. The green suite actively masks B1 and B3. | Read the fixture; run vs pytest |
| B3 | **CRITICAL** | src/titan/execution/engine.py:886-895 vs src/titan/strategies/bridge.py:34 | `StrategyBridge` default `certificate_ref="dummy_cert_for_paper_session"` → the first real signal in scripts/paper_session.py:914 kills the session process (unhandled ValueError in the loop). Paper trading is structurally dead. | paper_session.py:914 has no try/except |
| B4 | **HIGH** | src/titan/execution/engine.py:365-370 vs 657-659, 699-708 | Crash-restart fill double-apply: `OrderFilled` events persist per-poll DELTA; `_replay_state_from_events` restores `_order_filled_quantity[coid] = delta` (last event wins). An order filled 40+60 of 100 across polls restores 60; broker cumulative 100 → next poll re-absorbs 40 → position/cash inflation. | Code-logic proof; no test covers multi-poll restart |
| B5 | **HIGH** | src/titan/execution/engine.py:290-328 | `start(sync_from_broker=True)` crashes (`ValueError: side must be 'buy' or 'sell'`) whenever the broker holds any position — adapters report "LONG"/"SHORT" (simulated_adapter.py:106), `_sync_from_broker` passes it to apply_fill (:325). Even with side fixed: cash double-counts (portfolio rebuilt from broker cash at 313-317 which is already net of position cost, then apply_fill subtracts again at 323-328); shorts silently skipped (`qty <= 0: continue`, :320); missing entry price seeds cost basis 0 (:322). | Reproduced |
| B6 | **HIGH** | src/titan/backtest/engine.py:134-143, 206, 349-354 | ADR-021 trailing stops do not ratchet across bars: `_check_exits` recomputes eff_stop from the CURRENT bar's open/high with no carried state. Trail armed at 107 (low 108, no pierce) is lost next bar; position rides to 101 instead of stopping at 107. Docstring claims monotonic ratchet (line 123) — false. | Reproduced end-to-end with gate bypassed |
| B7 | **MED** | src/titan/backtest/engine.py:147-171 | Gap checks test only the static `stop`, never `eff_stop`; intrabar fills use `eff_stop`. A gap through a within-bar ratcheted trail fills at the trail price above the open — overstates exits; contradicts the stated convention "gap pierce at bar.open fills at open" (:122). | Code-path proof |
| B8 | **MED** | src/titan/backtest/engine.py:96-106 + core/src/portfolio.rs:358-365 | ReplayEngine runs a REAL RiskGate with `max_daily_loss=50000`, but daily realized loss is dated by WALL CLOCK (`Utc::now().format(...)`). A multi-month backtest run in one real day accumulates all realized losses into one "day" → silent mid-backtest intent rejections with no warning, skewing results. | Logic proof; magnitude depends on churn |
| B9 | **MED (security)** | src/titan/execution/engine.py:1086 | `risk_secret_key` defaults to literal `'TITAN_RISK_SECRET_KEY'`; the "risk token" is signed and verified with a public constant → no integrity protection. | Constant in source |
| B10 | **LOW** | src/titan/execution/engine.py:52-77, 1313 | Broker status "Expired" not in `_DEAD_ORDER_STATUSES`; poll_fills never transitions to `OrderState.Expired` → expired orders poll forever; `status == ""` falls through to fill absorption. | Enumerated set proof |
| B11 | **LOW** | src/titan/strategies/sizing.py:29-35 | `except ValueError: pass` on malformed timestamps makes the staleness gate FAIL OPEN — sizing proceeds with stale conversion data. | Explicit silent fallback |
| B12 | **LOW** | src/titan/backtest/engine.py:235-236 | `_mark()` swallows all exceptions from `portfolio.update_market_price` — a broken mark silently freezes equity/drawdown. | bare `except Exception: pass` |
| B13 | **LOW** | src/titan/data/polygon_feed.py:67 | `date.fromtimestamp(ts_ms/1000)` without tz=UTC → local-timezone date shift on non-UTC hosts. | Code proof; runtime impact untested |

## 2. LIKELY ISSUES

| # | Severity | Location | Description |
|---|---|---|---|
| L1 | MED | src/titan/execution/engine.py:662-665 | Fill priced at "0" when broker omits fill_price and no `_last_prices` mark → zero-cost position, phantom PnL. No test feeds missing-price fills. |
| L2 | MED | src/titan/execution/engine.py:941-943 vs 1211-1212 | Certificate nonce check is check-then-act (TOCTOU): concurrent submits with the same nonce both pass membership before consumption. No concurrency tests exist anywhere. |
| L3 | LOW | src/titan/backtest/fills.py:100-111 | Legacy fill path uses float arithmetic + round(x,2) on costs/commissions — sub-cent precision loss on crypto-scale prices. |
| L4 | LOW | src/titan/execution/engine.py:1364-1370 | Reconcile cash substitution: when holdings fetch fails, local cash is compared to itself → cash drift always "InSync". |
| L5 | LOW | scripts/papertrade.py:49-59 | `daily_loss_limit` ("5000") passed positionally as `max_gross_exposure` — $5,000 gross cap miswire (see Risk audit). |

## 3. UNVERIFIED HYPOTHESES

- H1: paper sessions have never completed an accepted order in the current code state.
  Evidence: every entrypoint crashes at the gate; logs/ holds 1 entry; the only
  `.titan_state.db` present was created by THIS AUDIT's own test-suite run
  (mtime 2026-09-29 12:58, 28KB — test-generated, not paper-session-generated).
- H2: `tws_approved` CSVs in US/Eastern passing through TWSDataFeed unnormalized
  (tws_feed.py:53-60) could shift bar dates by a session on non-US/Eastern hosts.
- H3: Midpoint pricing + tick-count "volume" systematically understates FX costs and makes
  volume filters (orb min_volume_ratio) meaningless for FX.

## 4. Reliability summary

The fail-closed recovery design is real: Unknown-order resolution via idempotency key
(engine.py:1121-1155), crash recovery New/Validated→Reject, Submitted→broker query or
kill switch (802-880), append-only event store with message_id dedup. The problem is the
**admission seam**: the exact place where production entrypoints meet the engine (the
certificate) was never integrated, so all of the recovery machinery has never run against
a real session, and the two highest-impact bugs (B4, B5) live in paths no test exercises
(restart with multi-poll fills; broker-held positions at startup).

## 5. Fix priority

1. B3 + B1: one fix — make the promotion path issue a real certificate AND make the
   paper/backtest entrypoints consume it (or provide an explicit, scoped dev-cert flow).
2. B2: remove/constrain the conftest monkeypatch so the real gate is the tested path.
3. B4, B5: fill-delta restore semantics; broker sync side/cash handling.
4. B6, B7: carry trailing state across bars; gap checks against eff_stop.
5. B8: date the daily-loss window by SIMULATED time in backtests.
6. B9: risk token secret from env; fail-closed when unset.
7. L1, L2, B10-B13, L4: cheap hardening after 1-6.

---

## 6. Secondary-audit findings — merged 2026-09-29

A second independent audit (3,538 lines, same 20 report names) was merged into
`audit/2026-09-29/secondary/`. Its bug report contains **C1–C48** plus mutation-testing
results that this report did not have. Full text: `secondary/BUG_AND_RELIABILITY_REPORT.md`.
Consolidated rulings: `MERGE_RECONCILIATION.md`. Everything below is attributed to the
secondary audit; CONFIRMED there means reproduced or read directly by that auditor.

### 6.1 CRITICAL — voids published evidence (secondary audit)

| # | Defect | Location |
|---|---|---|
| C1 | Screen **never exits a position** (`pos` set once, only exit is the final bar) → `results.json` shows `"trades": 1` in **every** per-pair cell. Voids the "0/15 concepts" row of the terminal report | `scripts/screening/screen.py:40-61` |
| C2 | `replicated` **hard-wired `False`** in every screen; gate `rep_ok = replicated`; no production call site passes `True`. CRYPTO-001 evidence bundle: replication=false, n_trades=1 | `crypto_screen.py:140,254` et al. |
| C3 | Failed gates **invisible to the decision function**: failure detector matches `False` or strings containing `"❌"`, but `❌` appears exactly once in `validator.py` — inside the detector itself. EXP-00017/19 committed `"promote"` with failing IC and cost gates | `validator.py:262-265, 376` |
| C4 | **FX cost 10–100× overstated**: "cost_bps=10 (~1 pip retail RT)" — 1 pip = 1 bp, not 10; validator subtracts 2×0.001 = 20 bps; EXP-00022 charged 5.20%/yr against a 5.4%/yr gross edge. Same repo uses 0.9 bp RT elsewhere | `run_fx_experiments.py:10-11`, `validator.py:194,214` |
| C5 | **Research harness is long-only** — no short branch. EXP-00031 "canonical reproduction" produced 54 trade records vs the original 163. Not a reproduction | `harness.py:99-151` |
| C6 | **PnL and trade counts double-counted**: pnl written onto the ENTRY record *and* a new record → total_trades = 2× round trips (min_trades(30) is really a 15-trade gate), gross/net PnL 2×, bootstrap CIs inflated 2× — under-powered backtests look *more* significant | `harness.py:135-137, 299-311` |
| C7 | `walk_forward()` **performs no walk-forward** — sliding window, same params, no training, no test partition; its mean Sharpe is exported as `walk_forward.mean_sharpe`. Real `WalkForwardOptimizer` reachable only from mcp/cli, no experiment calls it | `harness.py:383-412`, `walkforward.py:130` |
| C8 | **Sharpe hard-codes `sqrt(252)` on per-bar returns** — 4h FX understated 3.0×, 5m overstated 11.6×; no caller can pass frequency; variable literally named `daily_returns` | `results.py:100`, `metrics.py:153` |
| C9 | `profit_factor` **returns a perfect 100.0 when there are no losses** | `results.py:62` |
| C10 | **Bonferroni correction computed and discarded**; 546 trials evaluated at α=0.05 instead of 9.2×10⁻⁵. Also `mt_penalty` applied to an already-annualised Sharpe (dimension mismatch, inert) | `validator.py:271-273, 153-159` |
| C11 | **Power gate checks bar count, not trades** (`n = len(rets)` = 644 bars vs gate `n >= 60`). Never bound — all 16 cells report n=644 | `traderdev_fx_screen.py:337,361` |
| C12 | p4 **annualizes cumulative-since-entry returns** → Sharpe 19.25/21.13 on 4h FX (impossible); bootstrap pairs 18 gated vs 47 ungated trades by index, silently truncated | `p4_multi_tf_confluence.py:138-156` |
| C13 | Same-bar lookahead in P2 (inflationary — P2's FAIL survives the bug) | `p2_gold_macro_momentum.py:118-124` |
| C14 | **Crypto simulator never marks price PnL** — `attr.price` = Decimal("0") forever; only funding/costs ever realised; spot hedge charged full fees on every rebalance. CRYPTO-001 "+482 USD from 1 trade in 6 events"; CRYPTO-002/003 0 OOS trades = empty files with verdicts | `crypto_simulator.py:126-151` |
| C15 | **Preregistered thresholds are non-binding** — evaluator invents defaults (min_sharpe 1.0 etc.) for keys absent from the prereg. Preregistration is decorative | `equities_factor_screen_006.py:384-389` |

### 6.2 HIGH — the runtime cannot trade (secondary audit)

| # | Defect | Location |
|---|---|---|
| C16 | **Paper session dies on the first signal**: `dummy_cert_for_paper_session` → `json.loads` → `JSONDecodeError` → `ValueError`, called with no try/except. 1180 tests pass only because the autouse conftest monkeypatch replaces `submit_intent` | `bridge.py:34`, `engine.py:890-895`, `paper_session.py:914` |
| C17 | `cli.py` recovery path raises `TypeError` (arg-count mismatch with `restart.py:121`) | `cli.py:127` |
| C18 | Hardcoded Windows paths on a Linux checkout | `scripts/supervise_paper_session.sh:8`, `run_tws_paper_loop.sh:8` |
| C19 | **Correlation risk rule can never fire** — runner writes `_last_prices` directly instead of `engine.update_price()`; `risk.rs:706` reads engine state. Confirms this report's H1 | `paper_session.py:861` |
| C20 | Dual authorization is **weaker on release than on init** — no `authorized_approvers` check; any 2 distinct strings pass | `engine.py:1607` |
| C21 | HMAC risk secret is a hardcoded literal (same as B9) | `engine.py:1086` |

### 6.3 MEDIUM — dead, unwired, or lying (secondary audit, condensed)

| # | Defect | Location |
|---|---|---|
| C22 | `RiskDecision` constructed nowhere; "All decisions are persisted" (Risk.spec.md:44) is false | grep: 0 prod sites |
| C23 | `correlation_id` never passed → decision-trace subsystem inert | `engine.py:585`, `messages.rs:60` |
| C24 | `RiskDecisionRecorded` fields exist, never written | `messages.rs:267` |
| C25 | `contracts/*.schema.json` zero imports; events written with `schema_version=100` vs schema `v1` | `PROJECT_STRUCTURE.md:44` |
| C26 | 15 of 25 Prometheus metrics never written; health check reads a metric nobody writes → always "Broker truth matches: YES" | `operations/export.py:79`, `cli.py:142` |
| C27 | `embedding_vector` populated nowhere → `search_similar_trades` can never match | `memory/vector_memory.py:84-97` |
| C28 | `mcp_bridge.py:66` returns **fabricated** strategy names (`ma_crossover`, `bollinger_breakout` — neither registered) | |
| C29 | financial "Sharpe" gate is `net > 0` — a sign test; with n=1, a one-observation sign test | `crypto_screen.py:111` |
| C30 | `concentration = 1.0/len(universe)` — passes by construction | `crypto_screen.py:193` |
| C31 | `annualized_turnover_pct` returns the raw total | `metrics.py:41-42` |
| C32 | `per_regime["trades"]` assigns the running cumulative counter | `metrics.py:337` |
| C33 | session EMA derives session from bar index `mod 6`, not timestamps | `traderdev_fx_screen.py:210-228` |
| C34 | `dual_ma` / `vwap_reversion` have **zero** references in `tests/` | verified |
| C35 | 6 of 10 registered strategies crash on a daily-close feed | `bridge.py:110` |
| C36 | `backtest_multitimeframe.py:175` TypeError; `paper_session --dashboard` ModuleNotFoundError (dashboard/ gitignored, absent); `scripts/monitor.py` no argparse | |
| C37 | **Impossible metrics archived as evidence**: EQ-Micro-001 Sharpe −32.47, DD 99.9%, 568× monthly turnover; no validator rejects out-of-range values | `EQ-Micro-001-evidence-bundle.json` |
| C38 | `BARS_PER_YEAR = 2190` on data with 1,610 4h bars/yr → Sharpe overstated 1.167× (toward passing) | `traderdev_fx_screen.py:41` |
| C39 | `ann_ret = mu × 2190` — arithmetic, ignores compounding | `traderdev_fx_screen.py:337` |
| C40 | `exposure_adjusted_benchmark` reads an attribute `BacktestResult` doesn't define → dead branch, silent fallthrough | `metrics.py:176-205` |
| C41 | 92 Rust `#[test]` functions never run under pytest; `rustup`/`cargo` absent locally, `.so` cannot be rebuilt | `core/src/*.rs` |
| C42 | Two Windows paths in shell scripts (duplicate of C18) | |
| C43 | IS/OOS rebalance grids anchored to each partition's start → different monthly phase | `equities_factor_screen_006.py:136,143` |
| C44 | IS and OOS use **different gate sets** for the same hypothesis ID; `run_eq002_core7.py:165-172` has **no significance test at all** → EQ-002-core7 marked "candidate" | |
| C45 | `promotion.py:82-106` long/flat only, 1.5 bps, zero spread; self-disclosed as inflating Sharpe to 5.93/7.13 vs real +71.8/+336.5 pips | `ema9vwap_promotion_report.md:35-43` |
| C46 | `trade[].pnl` written to the entry record — `trades[-1]` semantics differ from every other consumer | `harness.py:135` |
| C47 | EXP-00025 artifact missing the `pnl_list` written at runtime — truncated after the run | `run_traderdev_families.py:369` |
| C48 | Preregs and results committed in the **same commit** (`80ee522`); no timestamp field → no preregistration is provably prior | `git log --diff-filter=A` |

### 6.4 Mutation testing (secondary audit, 20 mutants, full suite)

**Killed (8):** risk-gate bypass · 10× looser risk limits · fill slippage sign · trailing stop
direction · `Sizer` step-size floor · 10× position size · crypto taker fee zeroed · total-PnL
sign. Plus a full realized-PnL sign-flip across the suite → 35 failures.

**Survived (6) — the dangerous ones:** `dual_ma` hardcoded to `"BUY"` · `vwap_reversion`
SELL→BUY · `abs()` on Sharpe · `profit_factor` → `100.0` · drawdown sign inverted ·
`sqrt(252)`→`sqrt(12)` and →`sqrt(52)`.

**Interpretation (adopted by both audits):** the Rust kernel and the risk/execution/fill layer
are genuinely protected. **The strategy-signal layer and the performance-metric layer have
~0% effective coverage** — and those are exactly the components that decide whether TITAN
makes money. This corroborates §5 items 4-5 of this report and sharpens their priority:
hand-computed fixtures + per-strategy invariants before any further strategy work.

### 6.5 Statistics layer (secondary audit)

- Lo (2002): SE(SR_ann) ≥ 1/√T — one year of 4h FX cannot resolve a Sharpe below ~1.15.
  The F1@4h cell's t ≈ 0.46–1.28 sits inside a 95% CI of [−1.45, +3.05]: UNDERPOWERED,
  not refuted.
- 546-trial census: with Bonferroni the per-trial α is 9.2×10⁻⁵; the validator computes
  this and discards it (C10). The archive's "passes" at α=0.05 are consistent with pure
  multiple-testing noise.
- Verdict class `UNDERPOWERED` does not exist in the validator; experiments that cannot
  resolve their own hurdle are instead reported as pass/fail.

### 6.6 Cross-audit delta

**In THIS report but absent from the secondary audit** (the four the maintainer flagged,
plus supporting ones):

1. **Free paper fills** — `engine.py:736` `fees=Money("0")` (see EXECUTION_ECONOMICS.md §4):
   paper sessions trade cost-free, so no paper result is comparable to promotion evidence.
2. **`papertrade.py:49-59` positional miswire** — `daily_loss_limit` ("5000") passed as
   `max_gross_exposure` ($5,000 gross cap). (This report L5.)
3. **`paper_session.py:540-550` gross cap = 1× capital** — silently caps any session.
4. **Fill-delta vs cumulative restore** (`engine.py:365-370`, B4) — restart restore semantics.
   (Plus B5 broker-sync crash/cash double-count/shorts-skipped, B8 wall-clock daily loss,
   B12 `_mark()` swallowing — spot-check comparison, not exhaustive.)

**In the secondary audit but absent from this report:** C1 (one-trade-per-hypothesis),
C2 (replication gate constant-false), C3 (❌ detector), C4 (cost units), C5 (long-only
harness), C6 (2× PnL), C7 (fake walk-forward), C8 (sqrt(252)), C10 (discarded Bonferroni),
C11 (bar-count power gate), C12 (P4 Sharpe 19-21), C14 (crypto price PnL), C15 (decorative
preregs), C19 (correlation rule — resolves this report's H1), the full mutation programme,
and the Lo power analysis.

**Confirmed overlaps** (both audits, independently): cert-gate crash (C16 = B1/B3),
conftest mask (their §1 = B2), hardcoded risk secret (C21 = B9), Windows paths
(C18/C42 = environment-drift finding).

---

# 1b. RESEARCH & MEASUREMENT DEFECTS — second audit, independently re-verified

A second independent audit traced the *research* path rather than the execution path. Its
defects are complementary to §1, not duplicative: §1 shows the runtime cannot trade; §1b shows
that even if it could, **the research loop could not tell it whether a strategy works.**

All items below were re-verified by direct inspection and execution on 2026-09-29.

## 1b.1 CRITICAL — defects that void published evidence

| # | Severity | Location | Description | Verification |
|---|---|---|---|---|
| R1 | **CRITICAL** | scripts/screening/screen.py:40-61 | The 15-concept screen **never exits a position**. `pos` is set at `:49` and never reset to `0`; the only exit is `:56-61` (final bar); `n_trades` increments once. **Every result in the family is the PnL of ONE trade.** | **VERIFIED**: `scripts/screening/results.json` has `"trades": 1` in every per-pair cell. `ALPHA_SEARCH_TERMINAL_REPORT.md:27`'s "0/15 concepts" row is void |
| R2 | **CRITICAL** | crypto_screen.py:140,254 · crypto_screen_002.py:93 · crypto_screen_003.py:91 · equities_factor_screen_006.py:380,477 · equities_event_screen_007.py · equities_event_screen_008.py:469,566 | `replicated: bool = False` is the default in all six screen modules; the gate is `rep_ok = replicated` (`crypto_screen.py:115`); **no production call site ever passes `True`.** Zero survivors is therefore a **constant, not a measurement**. | **VERIFIED**: `CRYPTO-001` = `{"oos_net_positive":true,"ic_frac":true,"concentration":true,"adverse_capacity":true,"replication":false}` — **4 of 5 gates PASS**, `n_trades: 1`. `EQ-007` passes 5 of 9 including `oos_net_sharpe` (1.249 ≥ 1.0), `max_drawdown`, `quantile_monotonicity`, `adverse_net_positive` |
| R3 | **CRITICAL** | src/titan/research/validator.py:262-265, 376 | A check counts as failed only if it is `False` or a string containing `"❌"`. `:376` stores the failure **message** (`cost_msg`) on failure. | **VERIFIED**: the character `❌` appears **exactly once** in `validator.py` — at line 265, inside the detector itself. No message string can match. **Consequence: `EXP-00017` and `EXP-00019` both committed `"decision": "promote"` with failing IC and cost gates** |
| R4 | **CRITICAL** | research/run_fx_experiments.py:10-11 · validator.py:194,214 · run_exp22_xs_momentum.py:26,78,82 · run_exp23_carry.py:29,104 · run_exp_00024_carry_vol.py:34 · run_regime_test.py:27 · run_exp21_tsm_daily.py:69 | `COST_BPS = 10.0` is annotated *"cost_bps=10 (~1 pip retail round turn)"* — but 1 pip = 1 bp, so the constant is **10× its own comment** and 10–100× the plausible figure. `validator.py` subtracts `2×0.001` = 20 bps. **Counter-example in the same repo: `run_traderdev_families.py:23-24` uses 0.9 bp RT for the same instrument in the same month.** | **VERIFIED** by grep and by arithmetic. **EXP-00022** (G10 cross-sectional momentum, t=2.67, 412 weekly obs, 8 years — a published anomaly) nets exactly 0.00% because 10 bps × 52 = 5.20%/yr against a 5.4%/yr gross edge. At 1–2 bps it nets **+4.4 to +4.9%/yr, Sharpe 0.48–0.54** |
| R5 | **CRITICAL** | src/titan/research/harness.py:99-151 | The research harness is **long-only**. `if pending_signal == "BUY" and not in_position` / `elif pending_signal == "SELL" and in_position`. **No short branch exists.** | **VERIFIED**. Strategies emitting `SELL` while flat do nothing, then desynchronise. **EXP-00031's "canonical reproduction" produced 54 trade records where the original produced 163** — it is a different strategy |
| R6 | **HIGH** | src/titan/research/harness.py:135-137 | PnL is written to the entry record **and** to a newly-appended record. | **VERIFIED**. Consequences: `total_trades` = 2× round trips (so `check_min_trades(30)` is effectively a 15-trade gate); `gross_pnl`/`net_pnl` (`:299-311`) report **2× the true PnL**; `block_bootstrap` (`metrics.py:352-382`) resamples a list where each PnL appears twice → **bootstrap CIs inflated 2×**, making under-powered results look *more* significant |
| R7 | **HIGH** | src/titan/research/harness.py:383-412 | `walk_forward()` does **no training, no parameter selection, no test partition** — a sliding window run with identical params. Its mean Sharpe is exported as `to_dict()["walk_forward"]["mean_sharpe"]` (`:550-555`). | **VERIFIED**. The genuine `WalkForwardOptimizer` (`walkforward.py:130`) is called by **no experiment** |
| R8 | **HIGH** | src/titan/backtest/results.py:100 · metrics.py:153 | Sharpe and volatility hard-code `sqrt(252)` while the input is **per-bar** returns (`daily_returns`, `results.py:47`). No caller can supply a frequency. | **VERIFIED**. 4h FX (2,190 bars/yr) → Sharpe **understated 3.0×**; 5m → **overstated 11.6×** |
| R9 | **HIGH** | src/titan/backtest/results.py:62 | `profit_factor = 100.0 if gross_loss < 0.01 else min(...)` — a **perfect score for any strategy with no losing trades**. | **VERIFIED**; mutation-survived (see §5) |
| R10 | **HIGH** | validator.py:271-273 · walkforward.py:163-164 | Bonferroni `alpha = 0.05/total_experiments` is formatted into a `reasons` string and **never used**; `check_ic_significance` uses hard `p > 0.05`. `mt_penalty = sqrt(2 lnM/N)` is applied to an **already-annualised** Sharpe — a dimension mismatch that makes it inert. | **VERIFIED**. ~546 trials were evaluated at α=0.05 instead of the family-wise **9.2×10⁻⁵** (|t| ≥ 3.90) |
| R11 | **HIGH** | research/traderdev_fx_screen.py:361 vs :337 | The frozen "≥60 OOS trades" power gate is evaluated as `st["n"] >= 60` where `n = len(rets)` = **bar count**. | **VERIFIED**: all 16 committed cells report `n = 644`. The gate never bound; no trade count exists anywhere in the archive |
| R12 | **HIGH** | research/p4_multi_tf_confluence.py:138-149, 156 | Cumulative-since-entry returns are appended **per bar** while in a position (overlapping, not per-period), then annualized by `sqrt(BARS_PER_YEAR)`. The "decisive" bootstrap then pairs gated (18 trades) against ungated (47) by index, silently truncated. | **VERIFIED in the committed artifact**: `P4_multi_tf_confurrence.json` reports `sharpe_ungated` **19.25 (EURUSD) / 21.13 (GBPUSD)** on 4h FX. A 4h EURUSD strategy cannot have Sharpe 19–21 |
| R13 | **MED** | src/titan/research/equities_factor_screen_006.py:384-389 | Preregistered thresholds are **non-binding** — the evaluator reads `prereg.pass_criteria.get(key, DEFAULT)`, inventing Sharpe ≥ 1.0, IC-frac ≥ 0.70, mean-IC ≥ 0.05, DD ≤ 12% that appear in **no preregistration**. `EQ-002-prereg.json` specifies none of these keys. | **VERIFIED** |
| R14 | **MED** | src/titan/backtest/crypto_simulator.py:126-151 | `attr.price` is initialised to `Decimal("0")` and **never assigned** — all reported "net" is funding minus costs, with **zero price risk and zero basis PnL**. The spot hedge (`:147-149`) is charged taker fee + spread + impact on **every** rebalance, including perp flips with no change in spot exposure. | **VERIFIED**. CRYPTO-001 reports **+482 USD from 1 trade in 6 events**; CRYPTO-002/003 report **0 OOS trades** |
| R15 | **MED** | src/titan/research/crypto_screen.py:111, 193 | The crypto "Sharpe" gate is `sharpe_ok = net > 0` — a sign test on total PnL. With `n_trades = 1` it is a **one-observation** sign test. `concentration = 1.0/len(universe)` is a **tautology that passes by construction**. | **VERIFIED** |
| R16 | **MED** | research/ema9vwap_parameter_surface.py:69-84, 96 | `sharpe_from_pnl` multiplies by `trades_per_year_factor(n)`, which **unconditionally returns 1.0**; it is not a Sharpe, it is never called, and the caller's t-statistic is never written to the output. | **VERIFIED**: the 198-cell surface reports **no significance statistic at all** (`json` keys are `grid`, `cells`, `summary` — no t/p field) |
| R17 | **MED** | research/p2_gold_macro_momentum.py:118-124 | Same-bar lookahead — enters at bar *i*'s close and immediately collects `close[i]/close[i-1] - 1`; the exit bar does the same. | **VERIFIED**. Direction is **inflationary**, so P2's FAIL survives its own bug |
| R18 | **MED** | research/traderdev_fx_screen.py:210-228, 46-52 | `sig_session_ema` derives session from **bar index `mod 6`**, not timestamps — which `load_4h_closes` has already dropped. This is not a session filter. | **VERIFIED** |
| R19 | **MED** | research/equities_factor_screen_006.py:136,143 | `rebalance_dates = common_index[::freq]` anchors the grid to each partition's start, so IS and OOS rebalance on **different phases** of the monthly cycle. | **VERIFIED** (causal — weights are shifted +1 day at `:235` — but an unforced IS/OOS mismatch) |
| R20 | **MED** | scripts/run_eq002_core7.py:165-172 vs equities_factor_screen_006.py:391-401 | Two different, incompatible gate sets for the same hypothesis ID; the script variant has **no significance test at all**. | **VERIFIED**. Consequence: `EQ-002-core7` carries `"verdict": "candidate"` and is **not counted** in the "0 survivors" figure |
| R21 | **LOW** | metrics.py:41-42 · metrics.py:337 · metrics.py:176-205 | `annualized_turnover_pct` returns the raw total; `per_regime[rn]["trades"]` assigns the running **cumulative** counter; `exposure_adjusted_benchmark` reads `result.equity_curve`, an attribute `BacktestResult` does not define → dead branch. | **VERIFIED** |
| R22 | **LOW** | traderdev_fx_screen.py:41, 337 | `BARS_PER_YEAR = 2190` applied to Dukascopy data that has **1,610** 4h bars/yr → Sharpe **overstated 1.167×** (i.e. *toward* passing). `ann_ret = mu × 2190` ignores compounding. | **VERIFIED** |
| R23 | **LOW** | research/equities/results/EQ-Micro-001-evidence-bundle.json | Impossible metrics archived as evidence: OOS Sharpe **−32.4729**, max drawdown **0.999**, monthly turnover **568.58×**. | **VERIFIED**: the equity curve is exploding, not a market finding. No validator rejects out-of-range metric values |
| R24 | **LOW** | git log --diff-filter=A | Preregs and their result bundles land in the **same commit** (`80ee522`, 2026-09-20 for EQ-006/007/008; 2026-08-18 for EQ-001/002/003, CRYPTO-001), and prereg JSONs carry no timestamp field. | **VERIFIED**: **no preregistration is provably prior to its results** |
| R25 | **LOW** | research/ | `knowledge/experiments/` is **empty** (`.gitkeep` only) despite `RESEARCH_CONSTITUTION.md:86` mandating a journal per experiment. Only EXP-00008..00011 exist. | **VERIFIED**: the "absorbing negative result" protocol (§124) is unimplemented |

## 1b.2 Duplicated systems — the mechanism behind R8/R9/R11/R12

Six independent backtest simulators (`backtest/engine.py:63`, `backtest/crypto_simulator.py:91`,
`backtest/factor_simulator.py:181`, `research/crypto_screen_004.py:159` **and** `:395`,
`research/equities_micro_screen_001.py:170`, `equities_event_screen_007.py:169`,
`_008.py:194`, `equities_factor_screen_006.py:97`, `traderdev_fx_screen.py:302`).

**`_compute_max_drawdown` is copy-pasted 5×** — `factor_simulator.py:174`,
`equities_factor_screen_006.py:90`, `equities_event_screen_007.py:93`,
`equities_event_screen_008.py:93`, `render/report.py:6`.
**This is the direct mechanism by which mutation M11 (drawdown sign inverted) survived the suite.**

Six cost models — `crypto_costs.py:11`, `factor_simulator.py:24`, `fx_costs.py:13`,
`fills.py:24`, plus inline logic in `promotion.py`, `harness.py`, `walkforward.py`, `shadow.py`
and 5 `research/*.py`. **This is the direct mechanism of the 0.9 bp vs 20 bp contradiction
behind R4.**

## 1b.3 Data reproducibility

- `research/dukascopy_1m_ba/` is **absent** (gitignored `.gitignore:101`) but referenced by
  **seven** scripts (`traderdev_fx_screen.py:37`, `run_traderdev_families.py:20`,
  `screen.py`→`m.DATA`, `exp17_2fold_retest.py:20`, `p4:33`, `p2`, `reproduce_exp00031.py:27`).
  **Every FX number in the terminal report is currently unverifiable and un-rerunnable.**
- `research/crypto/data/` **absent** (`:143`); `research/equities/data/` **absent**.
- `EXP-00025_traderdev_families.json` is **missing the `pnl_list`** that
  `run_traderdev_families.py:369` writes → per-trade t-statistics are not computable from the
  archive for the one FX candidate.

## 1b.4 Additional fix priority (research side)

1. **R1** — allow exits in `screen.py:40-61`; re-run the 15 concepts. *Zero cost.*
2. **R2** — delete the `replicated=False` default; reclassify CRYPTO-001 and EQ-007 as
   `INCONCLUSIVE` rather than `negative_result`. *Two hours.*
3. **R4** — one sourced per-instrument cost schedule, consumed by research AND `promotion.py`.
4. **R3, R13** — make failed gates and missing prereg keys hard failures, not strings/defaults.
5. **R5, R6, R7, R8, R11** — the harness repair set (short branch, one PnL record per round
   trip, real walk-forward, `periods_per_year` argument, real trade counts).
6. **R10, R16** — vendor DSR/PSR/PBO/purged-CPCV; compute N; record the trial ledger.
7. **Add an `UNDERPOWERED` verdict** when `SE(SR_ann) = sqrt((1+0.5*SR^2)/T) > 0.5` (Lo 2002).
8. Consolidate the 6 simulators / 6 cost models / 5 drawdown copies.
