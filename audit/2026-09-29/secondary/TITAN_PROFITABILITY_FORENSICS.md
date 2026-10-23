# TITAN PROFITABILITY FORENSICS

**Date:** 2026-09-29. Baseline claim under audit: *"No simple directional, regime-gated, or
macro-factor signal on liquid OHLCV data produces enough alpha to survive realistic
transaction costs — across every structural axis and asset class tested."*
(`research/ALPHA_SEARCH_TERMINAL_REPORT.md:16`)

## Verdict

**Not supported.** The claim is an artifact of a broken instrument, not a measurement of markets.

## 1. The experiment census

### Trials actually executed (the multiple-testing denominator)

| Source | Independent backtests |
|---|---|
| `research/ema9vwap_parameter_surface.py:32-33` | **198** (99 cells × 2 pairs) |
| `research/backtest_results_summary.json` | **130** |
| `scripts/optimize_fx.py:119-143` | **63** |
| `research/backtest_per_timeframe_results.json` | **45** |
| `scripts/screening/screen.py` | **30** (15 concepts × 2 pairs) |
| `research/run_traderdev_families.py:326,334-336` | **24** |
| `research/traderdev_fx_screen.py:290-299,342-344` | **16** |
| EXP-00007/8/12/14, ensemble_lab, qualification matrix | ~40 |
| **Total** | **≈ 546** |

All 546 share **3 datasets** and **2 distinct OOS windows**. Family-wise false-positive
probability at α=0.05: `1 − 0.95^546 ≈ 1.000`. At the correct Bonferroni threshold
(α = 9.2×10⁻⁵, |t| ≥ 3.90) — which `validator.py:271` computes and then discards.

### The headline experiments

| ID | Market | Strategy | N | Sharpe | Cost assumed | Realistic | Outcome |
|---|---|---|---|---|---|---|---|
| **EXP-00016** | EUR/GBP 1h | 12h→1h TSM | 12,384 | IC −0.0834 | 10 bps | 0.2–1 bp | **FALSIFIED — valid** |
| EXP-00017 | EUR/GBP 1h | vol(20)→fwd \|ret\| | 12,508 | IC 0.267 | 10 bps | n/a | promote *(invalid)* |
| EXP-00017-retest | Dukascopy 1h | honest OOS, 2 folds | 1,245 | IC 0.121/0.053 | — | — | **FAIL — correct** |
| **EXP-00022** | **G10 9ccy, 8y, weekly** | **CS momentum 1m** | **412** | **t = 2.67** | **10 bps/period = 5.20%/yr** | **1–2 bps = 0.52–1.04%/yr** | **rejected on a units error** |
| EXP-00023 | G10 7ccy, 8y | CS carry | 96 mo | t = 1.14 | 10 bps/leg | 1 bp | reject *(27% power)* |
| EXP-00025 | EUR/GBP 4h, 1y | 6 trader.dev families | 163 | ~0.80 (F1) | real bid/ask ✓ | ✓ | **CANDIDATE** |
| EXP-00027 | EUR/GBP 4h | 8 structures | 644 **bars** | −2.60…+0.66 | 0.8 pip RT ✓ | ✓ | 0/16 *(SE(Sharpe)=1.84)* |
| EXP-00031 | EUR/GBP 4h | "canonical" EMA9×VWAP | 11 | 0.03 / 0.66 | IBKR ✓ | ✓ | **NOT ELIGIBLE** *(SE=1.56)* |
| P4 | EUR/GBP 4h | 20-SMA + vol gate | 18 | **19.25 / 21.13** | 0.4 pip ✓ | ✓ | FAIL *(metric broken)* |
| FX-001 | EURUSD, 2y | passive MAE reversal | 210 OOS | 0.60 OOS | real b/a ✓ | ✓ | reject *(~16% power)* |
| EQ-001 | 13 ETFs, 2y OOS | momentum 12-1 | 24 rebal | 0.700 | IBKR ✓ | ✓ | reject *(SE=1.00)* |
| **EQ-002-core7** | **7 ETFs, 2y OOS** | **reversal 12-1** | 24 | **+0.486** | ✓ | ✓ | **`"verdict": "candidate"`** |
| EQ-003 | 13 ETFs | vol-adj momentum | 24 | 0.465 | ✓ | ✓ | reject |
| **EQ-007** | 13 ETFs | **PEAD 42d** | 24 | **1.249** | ✓ | ✓ | reject *(5/9 gates passed)* |
| EQ-008 | 50 names | staggered PEAD | 24 | 0.067 | ✓ | ✓ | reject *(overfit collapse)* |
| EQ-Micro-001 | SP50 intraday | ETF lead-lag | 24 | **−32.47** | — | — | reject *(simulator broken)* |
| CRYPTO-001 | BTC/ETH perp | funding-basis carry | **1** | — | Binance ✓ | ✓ | **4/5 gates PASS**, filed failure |
| CRYPTO-002/003 | BTC/ETH | funding+OI / order flow | **0** | — | ✓ | ✓ | reject |
| CRYPTO-006 | 15 alt perps | maker capture | 4.87M fills | edge 0.157 bps | real maker sched | ✓ | reject *(well powered)* |

## 1b. SECOND-PASS CORRECTION — what EXP-00025's committed artifact actually shows

An adversarial re-read of `research/results/EXP-00025_traderdev_families.json` (24 cells)
produced a finding the first pass got wrong, and it is the strongest single piece of evidence
in the entire audit.

| Family | Pair | Frame | Trades | Net pips | Avg/trade | Win % | MaxDD |
|---|---|---|---|---|---|---|---|
| F1_ema9_vwap | EURUSD | 1h | 296 | **−685.7** | −2.32 | 34.1% | 0.94 |
| F2_ema20_60 | EURUSD | 1h | 4 | −484.9 | −121.22 | 25.0% | 0.91 |
| F3_st_double | EURUSD | 1h | 170 | −348.3 | −2.05 | 33.5% | 0.51 |
| F4_st_vol_trail | EURUSD | 1h | 104 | −238.7 | −2.30 | 26.0% | 0.41 |
| F5_spectral | EURUSD | 1h | 3 | −198.2 | −66.08 | 33.3% | 0.63 |
| F6_adx_vwap | EURUSD | 1h | 201 | −551.8 | −2.75 | 2.0% | 0.55 |
| **F1_ema9_vwap** | **EURUSD** | **4h** | **84** | **+71.8** | **+0.86** | 34.5% | 0.56 |
| F2_ema20_60 | EURUSD | 4h | **1** | +99.6 | +99.62 | 100.0% | 0.68 |
| **F3_st_double** | **EURUSD** | **4h** | **49** | **+60.2** | **+1.23** | 38.8% | 0.22 |
| F4_st_vol_trail | EURUSD | 4h | 25 | −36.8 | −1.47 | 28.0% | 0.22 |
| F5_spectral | EURUSD | 4h | 3 | −305.6 | −101.86 | 33.3% | 0.70 |
| F6_adx_vwap | EURUSD | 4h | 61 | −203.9 | −3.34 | 4.9% | 0.22 |
| **F1_ema9_vwap** | **GBPUSD** | **4h** | **79** | **+336.5** | **+4.26** | 36.7% | 0.63 |
| F2_ema20_60 | GBPUSD | 4h | 3 | −610.3 | −203.42 | 33.3% | 0.87 |
| F3_st_double | GBPUSD | 4h | 49 | −702.7 | −14.34 | 30.6% | 0.75 |
| F4_st_vol_trail | GBPUSD | 4h | 27 | −137.7 | −5.10 | 29.6% | 0.40 |
| F5_spectral | GBPUSD | 4h | 2 | −278.5 | −139.24 | 50.0% | 0.87 |
| F6_adx_vwap | GBPUSD | 4h | 58 | −258.2 | −4.45 | 3.4% | 0.26 |

**Three things follow, and they cut against the terminal report.**

**(a) The terminal report's "0 survivors" is contradicted by its own committed artifact.**
**4 of 24 cells are net positive**, and they are **not randomly distributed: all four are at 4h.**
At 1h, **0 of 12** are positive. Of the 4h cells with n ≥ 49, **3 of 8** are positive.

**(b) The strongest cell is positive on BOTH pairs simultaneously** — F1_ema9_vwap @ 4h:
+71.8 pips / 84 trades (EURUSD) and +336.5 pips / 79 trades (GBPUSD). A single-pair lucky
window cannot do that. **The same family, on the same data, at a different timeframe, flips
sign on 12 of 12 1h cells.** That is a *frame-dependent effect*, and frame-dependence is a
property of real microstructure (execution horizon, spread-to-signal ratio, trailing-stop
geometry) — not a property of a broken harness. **This is the strongest argument in the audit
that the harness is capable of finding something.**

**(c) It is still not statistically significant, and must not be treated as an edge.**
Combined: 163 trades, +408.3 pips, mean +2.50 pips/trade. The trailing exit is 2×ATR(14) on 4h
EURUSD (ATR14 ≈ 20–35 pips ⇒ exit distance ≈ 40–70 pips):

| σ (pips) | t | p (2-sided) | Verdict |
|---|---|---|---|
| 25 | 1.28 | 0.201 | not significant |
| 40 | 0.80 | 0.424 | not significant |
| 55 | 0.58 | 0.561 | not significant |
| 70 | 0.46 | 0.648 | not significant |

σ is an **estimate from trailing-stop geometry, not a measurement** — the artifact has no
`pnl_list`. Lo (2002): `SE(SR_ann) = 1.15` at SR 0.80 over T = 1.0 yr → **95% CI [−1.45, +3.05]**.

**Correction to the first pass — resolved, and the memo settles it.** The first pass reported
"F1@4h +408.3 pips / 163 trades" and the second pass flagged that as a misattribution to a
single cell. **The project's own memo
(`research/neg_results/EXP-00025_traderdev_families.md`) reports the identical figure as a
pooled total and classifies it correctly:**

> `F1_ema9_vwap  4h pooled  +408.3 pips (84+79 trades)  <- NET POSITIVE on the main pair band`
> `Decision: F1_ema9_vwap @4h is a CANDIDATE (net positive on the primary FX pairs at the 4h
> scale); all other families are REJECTED`

So the number is the **project's own pooled figure**, not an audit error. What the second pass
adds is the **per-cell table above** — which the memo does not give — and the observation that
**all four positive cells are at 4h while all twelve 1h cells are negative.** The memo also
records that vol-regime gating is unstable (*"base +408.3 → gate-LB40 −13.3 → gate-LB168 +673.5
… the edge neither collapses nor robustly clears"*) and that F1 fails only *"not quarterly-stable
on both pairs"* — **EURUSD 4h was 2/4 quarters, GBPUSD 3/4.** With 4 quarters, a 2/4 split is
one trade.

**Conclusion:** F1@4h is the **correct** next experiment to re-run — not because it is proven,
but because it is the one result that is (i) positive, (ii) positive on two independent pairs,
(iii) frame-dependently so, (iv) modelled with the **correct cost schedule**
(`run_traderdev_families.py:23-24` = 0.9 bp RT), and (v) **the project itself recorded it as a
CANDIDATE**. The terminal report then closed it with EXP-00031 — a long-only,
differently-parameterised "reproduction" producing 54 records where the original produced 163 —
rather than with a significance test. **That is the actual defect: a candidate was killed by a
non-comparable artifact.**

## 2. The five instrument defects

### D1 — A third of the evidence base executed ONE TRADE PER HYPOTHESIS

`scripts/screening/screen.py:40-61`:
```python
40:  for i in range(n - 1):
41:      if pos == 0:
42:          s = side_fn(i)
...
49:              pos = 1 if s == "BUY" else -1     # set, NEVER reset to 0
50:      if pos != 0:
...
56:  if pos != 0:                                   # only exit = final bar
61:      n_trades += 1
```

**Auditor verification** — `scripts/screening/results.json`, every cell:
```json
{"concept":"sma_cross","survives":false,
 "per_pair":{"EURUSD":{"trades":1,"net_pips":90.6,"pips_per_year":90.6,"bars":1610},
             "GBPUSD":{"trades":1,"net_pips":10.5,"pips_per_year":10.5,"bars":1610}}}
```
`trades: 1` in **every** cell. `pips_per_year` is that single trade's pips
(`frac = max(1610/2190, 1.0) = 1.0`, `:63`).

`ALPHA_SEARCH_TERMINAL_REPORT.md:27` reports this as *"Directional single-pair FX (15 concepts)
— 0/15 survive ≥200 pips/yr × 2 pairs"*. **That row is void.** A screen that trades once
cannot detect anything.

### D2 — Zero survivors was guaranteed by construction

`replicated: bool = False` is the default in all six screen modules
(`crypto_screen.py:140,254`; `crypto_screen_002.py:93`; `crypto_screen_003.py:91`;
`equities_factor_screen_006.py:380,477`; `equities_factor_screen_007.py`; `equities_event_screen_008.py:469,566`).
The gate is `rep_ok = replicated` (`crypto_screen.py:115`). **No production call site ever
passes `True`.**

Verified consequences:
- **CRYPTO-001**: `{"oos_net_positive": true, "ic_frac": true, "concentration": true,
  "adverse_capacity": true, "replication": false}` — **4 of 5 gates PASS**, `n_trades = 1`.
- **EQ-007**: 5 of 9 gates pass — `oos_net_sharpe` **true** (1.249 ≥ 1.0),
  `rank_ic_magnitude` true, `max_drawdown` true, `quantile_monotonicity` true,
  `adverse_net_positive` true. Filed as a failure.

`verdict` is a **constant**, not a measurement. The hypothesis markdowns even list it as a
value: *"Gate 8 | Replication | `replicated=True` | Independent verification"*
(`EQ-006-quality-lowvol.md:62`, `EQ-007-pead.md:69`, `EQ-008-staggered-pead.md:74`).
Nobody typed it.

### D3 — The cost model is 10–100× too high, and only on the studies that failed

| Site | Assumed | Realistic (EURUSD) | Ratio |
|---|---|---|---|
| `validator.py:194,214` `check_cost_sensitivity(cost_bps=10.0)` → `net = gross − 2×0.001` | **20 bps = 20 pips RT** | 0.2–1.0 pip | **20–100×** |
| `run_fx_experiments.py:10-11` comment: *"cost_bps=10 (~1 pip retail round trip)"* | 10 bps | 1 pip | **10×** (bips≠pips) |
| `run_exp22_xs_momentum.py:26,78,82` | 10 bps/period = **5.20%/yr** | 0.52–1.04%/yr | 5–10× |
| `run_exp23_carry.py:29,104` · `run_exp_00024_carry_vol.py:34` · `run_regime_test.py:27` | 10 bps | 1 bp | 10× |
| `run_traderdev_families.py:23-24` (real bid/ask + 0.5 + 0.2 bp) | ~0.9 bp RT | ✓ | **1× correct** |
| `p4_multi_tf_confluence.py:38` (0.4 pip/side) | 0.8 pip RT | ✓ | **1× correct** |
| `p2_gold_macro_momentum.py:32` (1 bp, one side) | 1 bp | XAU 2–5 bp RT | **2–5× under** |
| `promotion.py:79,101` (`cost_bps=1.5`, **zero spread**) | 1.5 bp | +spread | under |

**Internal contradiction:** the same repo uses **0.9 bp** (`run_traderdev_families.py:23`) and
**20 bp** (`validator.py:214`) for the same instrument in the same month. The 20 bp figure was
chosen for the studies that produced negative results.

**The decisive arithmetic — EXP-00022:**
```
gross edge                    = +5.4 %/yr   (t = 2.67, 412 weekly obs, 8 years)
coded cost 10 bps × 52 weeks  = −5.20 %/yr  → net  0.00 %/yr   ← the recorded rejection
realistic 2 bps × 52          = −1.04 %/yr  → net +4.36 %/yr, Sharpe ≈ 0.48
realistic 1 bp × 52           = −0.52 %/yr  → net +4.88 %/yr, Sharpe ≈ 0.54
```
The project's **own memo** records the institutional-cost figure (+2.6 to +3.9%/yr net) and
rejects anyway. This is a published FX anomaly (Menkhoff et al. 2012 style) rejected on a
**units error**.

### D4 — The tests had no power to detect anything

**Lo (2002):** `SE(SR_ann) = √((1 + 0.5·SR²)/T_years)` — bounded below by `1/√T_years`
**regardless of trade count**. The project's "≥60 OOS trades" gate
(`traderdev_fx_screen.py:42`, `protocol_WF_v2_PRE_FROZEN.md §4`) was set for the wrong failure
mode: at σ/μ = 1.5, `t = √60/1.5 = 5.16` — **9 trades** suffice. Real FX trailing-stop trades
ran at **σ/μ ≈ 16**, so no trade count inside a 12-month window would have helped.

| Experiment | T (years) | SE(SR_ann) | 95% CI on the reported Sharpe |
|---|---|---|---|
| EXP-00031 (4h, 644 bars) | 0.41 | **1.56** | EUR 0.03 → [−3.03, +3.09]; GBP 0.66 → [−2.40, +3.72] |
| EXP-00025 F1 (163 trades) | 1.00 | **1.15** | 0.80 → **[−1.45, +3.05]** |
| EXP-00027 (644 bars/cell) | 0.41 | **1.84** | hurdle 0.45 = 0.24 SE from zero |
| EXP-00023 (G10 carry, t=1.14) | 8.0 | **0.37** | 0.40 → [−0.32, +1.12]; **power vs SR=0.5 = 27%** |
| EQ-001/003/006/007 | 2.0 | **0.94** | EQ-007 1.25 → **[−0.60, +3.10]** |
| FX-001 (best-powered FX study) | 2.0 | **0.71** | 0.68 → [−0.71, +2.07]; **~16% power** |

**A true Sharpe of 1.0 and a true Sharpe of 0.0 are statistically indistinguishable on this
evidence.** Rejecting EXP-00031 or EQ-007 on these windows is not a refutation.

Additional gate failures:
- `traderdev_fx_screen.py:361` checks `st["n"] >= 60` where `n = len(rets)` = **bar count**.
  Every cell reports `n = 644`. The gate never bound; no trade count was ever recorded.
- EQ-001's `rank_ic_fraction` gate (hurdle 0.70, n = 24): `SE = √(0.7·0.3/24) = 0.0935`;
  EQ-007 observed 15/24 = 0.625, `P(≥15/24 | true 0.70) = 0.847`. **A coin flip is not evidence.**
- `ema9vwap_parameter_surface.py:69-84` — `sharpe_from_pnl` multiplies by
  `trades_per_year_factor(n)` which **unconditionally returns 1.0**; it is not a Sharpe. It is
  never called. The 198-cell surface therefore reports **no significance statistic at all**.

### D5 — The evidence is not reproducible

- `research/dukascopy_1m_ba/` — referenced by `traderdev_fx_screen.py:37`,
  `run_traderdev_families.py:20`, `screen.py`→`m.DATA`, `exp17_2fold_retest.py:20`, `p4:33`,
  `reproduce_exp00031.py:27` — **does not exist** (gitignored, `.gitignore:101`). **Every FX
  number in the terminal report is currently unverifiable.**
- `research/crypto/data/` **absent** (`.gitignore:143`). `research/equities/data/` **absent**.
- `EXP-00025_traderdev_families.json` is missing the `pnl_list` that
  `run_traderdev_families.py:369` writes — the artifact was truncated after the run.
- `knowledge/experiments/` is **empty** (`.gitkeep` only) despite `RESEARCH_CONSTITUTION.md:86`
  mandating a journal per experiment. **There is no trial ledger.**
- Preregistration timestamps are unverifiable: `git log --diff-filter=A` shows EQ-001/002/003,
  CRYPTO-001 preregs added **2026-08-18**; EQ-006/007/008 **2026-09-20** — the *same commit*
  (`80ee522`) that carries both the preregs **and** their result bundles. **No preregistration
  is provably prior to its results**, and the preregs carry no timestamp field.

## 3. Additional confirmed metric defects

| Defect | Location | Effect |
|---|---|---|
| Long-only harness — no short branch | `harness.py:99-151` | Every short signal discarded. EXP-00031 "reproduction" produced 54 records where the original produced 163 |
| PnL double-counted onto entry record **and** a new record | `harness.py:135-147` | 2× PnL, 2× `total_trades` (so `check_min_trades(30)` is a 15-trade gate), **2×-inflated bootstrap CIs** — under-powered results look *more* significant |
| `sqrt(252)` hard-coded on per-**bar** returns | `results.py:100`; `metrics.py:153` | 4h FX Sharpe **understated 3.0×**; 5m **overstated 11.6×** |
| `profit_factor = 100.0` when `gross_loss < 0.01` | `results.py:62` | Perfect score for any strategy with no losses |
| `walk_forward()` does no training, no test partition | `harness.py:383-412` | Exported as `walk_forward.mean_sharpe` — a key readers take for OOS |
| Cumulative-since-entry returns appended per bar | `p4_multi_tf_confluence.py:139` | Artifact reports **Sharpe 19.25 / 21.13** on 4h FX. The "decisive" bootstrap pairs **misaligned series** (18 gated vs 47 ungated trades, silently truncated) |
| Same-bar lookahead | `p2_gold_macro_momentum.py:118-124` | Enter at bar *i* close, collect bar *i*'s return. Direction is **inflationary** → P2's FAIL survives |
| `annualized_turnover_pct` = the raw total, never annualized | `metrics.py:41-42` | Field is a copy |
| `per_regime[rn]["trades"]` = running **cumulative** counter | `metrics.py:337` | Regime trade counts are cumulative-over-time |
| Crypto simulator never marks price PnL | `crypto_simulator.py:126-151` | `attr.price` initialised to `Decimal("0")`, **never assigned**. Reported "net" is funding minus costs with **zero price risk** |
| Crypto spot hedge charged on every rebalance | `crypto_simulator.py:147-149` | Systematic double-charging |
| `BARS_PER_YEAR = 2190` on Dukascopy data that has **1,610** 4h bars/yr | `traderdev_fx_screen.py:41` | Sharpe **overstated 1.167×** — i.e. *toward* passing |
| `ann_ret = mu × 2190` — arithmetic, ignores compounding | `traderdev_fx_screen.py:337` | — |
| `sharpe_ok = net > 0` labelled "Sharpe" | `crypto_screen.py:111` | A sign test on total PnL. With `n_trades = 1` it is a **one-observation** sign test |
| `concentration = 1.0/len(universe)` | `crypto_screen.py:193` | A constant from universe size — **a tautology that passes by construction** |
| Prereg thresholds non-binding — code invents missing keys | `equities_factor_screen_006.py:384-389` | Imposes Sharpe≥1.0, IC-frac≥0.70, mean-IC≥0.05, DD≤12% that appear in **no** preregistration |
| Bonferroni α computed → string → **never used** | `validator.py:271` | 546 trials at α=0.05 instead of 9.2×10⁻⁵ |
| `mt_penalty = sqrt(2 lnM / N)` applied to an **already-annualised** Sharpe | `walkforward.py:163-164` | Dimension mismatch; magnitude ≈ 0.13 vs score ≈ 2 — inert |
| `sig_session_ema` derives session from **bar index mod 6**, not timestamp | `traderdev_fx_screen.py:210-228` | Not a session filter. Timestamps are dropped at `:46-52`, so session time is unrecoverable |
| `dual_ma`/`vwap_reversion` have **zero** references in `tests/` | — | Untested strategy modules |

## 4. What the evidence base genuinely establishes

**One valid negative result:**
> **EXP-00016** — intraday momentum is *falsified*. IC −0.0834, n = 12,384, bootstrap CI
> [−0.102, −0.067], consistent across 3 temporal thirds and 2 pairs, opposite sign to the
> hypothesis. A real, significant, well-powered negative.

**One correct kill:**
> **EXP-00017 retest** — the one promoted effect failed honest OOS (IC 0.121 → 0.053 EURUSD;
> 0.098 → 0.038 GBPUSD). The script's own note is the most valuable sentence in the archive:
> *"The original EXP-17 'temporal' thirds were same-window sub-periods, NOT out-of-sample — so
> the effect was never OOS-validated before promotion."* It also correctly notes the target
> (**forward |return|**) is not a tradable signal — knowing the magnitude of the next move is
> not knowing its direction, and the "cost check" that passed subtracted a cost from a
> difference of mean **absolute** returns, which is not a spread.

**One well-powered rejection:**
> **CRYPTO-006** (passive spread capture) — 4,872,006 fills, real maker fee schedule, edge
> **0.157 bps**. This was a properly powered study and it correctly found no edge. (It was
> rejected at its IS feasibility probe, a probe-gated not absorbing outcome.)

## 5. What the evidence base does NOT establish

It does **not** establish that liquid OHLCV is efficient. It establishes that:

> a loop with a single-trade screen, a 20-bp FX cost constant, a hard-wired replication gate,
> a `sqrt(252)` Sharpe on 4-hour bars, a 2× PnL double-count, a long-only canonical engine,
> a buy-and-hold "walk-forward", no Monte Carlo, discarded Bonferroni, and absent datasets
>
> **cannot detect a Sharpe-1.0 FX strategy in 12 months of data.**

**These are engineering failures, not market findings.**

## 6. Cause classification (Phase 4 A–M)

| Cause | Applies? | Evidence |
|---|---|---|
| A. No signal edge | **Unknown — untested** | D1, D4, D5 make it unmeasurable |
| **B. Weak implementation** | **YES — primary** | D1, D3, D5; long-only harness; 2× PnL; `sqrt(252)` |
| C. Excessive costs | **YES — as coded** | 10–100× overstated, and only on the failing studies |
| D. Overly restrictive risk | No | Risk is sound, but **nothing reaches it** |
| E. Position sizing | No | Not implicated in any negative result |
| F. Poor execution simulation | No | `run_traderdev_families.py` / `p4` model costs correctly |
| G. Data problems | **YES — secondary** | 0 of 3 core datasets on disk; no tick/L2; no verified borrow costs |
| H. Regime mismatch | **Unknown** | No regime analysis survives the metric defects |
| **I. Overfitting** | **YES** | 546 trials, α=0.05, no FDR, preregs unverifiable, 198-cell surface with no significance test |
| J. Poor portfolio construction | No | Not reached — all single-instrument |
| K. Insufficient diversification | No | Not reached |
| **L. Insufficient research** | **YES** | 2 distinct OOS windows across 546 trials; `knowledge/experiments/` empty |
| M. Other | **YES — the gate** | `validator.py:265` cannot detect failed gates stored as strings; `replicated` guarantees zero |

**Ranked: B (weak implementation) > I (overfitting) > C (costs) > L (sample) > G (data) >
M (gate defects). A (no edge) is UNPROVEN in either direction.**

## 7. Negative findings (recorded deliberately)

- The FX evidence base **cannot currently be re-run** — the dataset is absent.
- `EXP-00025`'s per-trade σ is an **estimate** from trailing-stop geometry (2×ATR(14) on 4h
  ≈ 40 pips), not a measurement. The true t-stat is somewhere in 0.64–1.07.
- `EQ-002-core7` — the one artifact marked `"candidate"` — has **IS Sharpe −0.0296** and a rank
  IC of 0.1817 over 24 obs in 7 names (t ≈ 1.78, p ≈ 0.09). It is **probably noise too**. But
  it was **never tested for significance**, and the "0 survivors" ledger does not count it.
  The ledger is internally inconsistent.
- `EQ-007`'s rejection may well be correct: its turnover cap (0.15) was breached at 0.181, and
  `EQ-008` then **tightened the cap to 0.12** in a prereg that states in its own words that
  EQ-007 "showed massive economic edge (+12.7% net return, 1.46 Sharpe, 0.27 rank IC, strictly
  monotonic quantiles)". That is post-hoc criterion tightening, visible in the artifacts.
- **No causal claim is made about the live market.** This audit found defects in TITAN's
  instrument. It found no defect in the market.
