# TITAN PROFITABILITY FORENSICS — 2026-09-29

Question: WHY is TITAN not producing useful trading results?
Method: decompose every documented experiment and the system itself; attribute to the
cause classes A–M; rank only on evidence.

---

## 1. The evidence base (all numbers from research/ bundles; file paths cited)

### Forex — the most thoroughly searched market

| Experiment | Period / TF | Costs | N | Net result | Verdict | Evidence |
|---|---|---|---|---|---|---|
| EXP-00016 | EURUSD+GBPUSD 1h momentum, n=12,384 | 10 bps RT | — | IC -0.0834 / -0.0298 | REJECT (sealed) | neg_results/EXP-00016_*.md |
| EXP-00017 | vol20→\|1h ret\| | 10 bps RT | — | IC +0.267/+0.280, bootstrap same-sign → PROMOTED → **2-fold OOS retest FAIL** (EUR 0.121/0.053; GBP 0.098/0.038) | killed by honest retest | EXP-00017_2fold_retest.json |
| EXP-00019 | 12h reversal, 63,515 bars | real spread | — | EURUSD short-rally **+0.58 pips/day** net; +1.95 in 12-16 UTC; GBP none | promote→REFINE (1 pair, 1 leg) | EXP-00019_real_cost_followup.md |
| EXP-00020 | rolling short-rally, real engine | real engine | 16/10 fills | V1 +6.25 pips/trade; **V2 -20.00 pips/trade** (610 rejects) | REJECT | neg_results/EXP-00020_*.md |
| EXP-00022 | G10 XS momentum 2018-2026 | 10 bps/leg | 412 | gross +0.10%/period (t=2.67) → **net 0.00%** | REJECT | neg_results/EXP-00022_*.md |
| EXP-00023 | G10 carry, 96 months | 10 bps | 96 | +0.18%/mo (t=1.14); maxDD -13.5% | REJECT | neg_results/EXP-00023_*.md |
| EXP-00024 carry-vol | carry-vol EUR/GBP/AUD/NZD | 10 bps | — | net Sharpe 0.30/0.13/0.46/0.13 (avg 0.26) | REJECT | neg_results/EXP-00024_vol_carry.md |
| EXP-00024 COT | 8 FX, weekly 2013-2026 | 10 bps | 4,664 | top-bottom -0.29%/mo (t=-3.57); contrarian +0.19%/mo | REFINE (sign-inconsistent) | results/EXP-00024_cot_positioning.md |
| EXP-00025 | 6 traderdev families ×2 pairs ×1h/4h, 12mo Dukascopy | real spread +0.5bps slip +0.2bps comm | — | **F1 4h: EURUSD +71.8 pips (84tr), GBPUSD +336.5 (79tr)**; all other family/frame cells negative | F1-4h CANDIDATE | results/EXP-00025_traderdev_families.json |
| EXP-00026 | cross-pair MR 4h | — | — | coint p=0.54 | HALT_NOT_COINTEGRATED | results/EXP-000026_crosspair_mr.json |
| EXP-00027 | 8 signal classes, 2 pairs, 4h | 0.8 pips RT | 644/pair | **0/16 survive**; best bbw_exp_cov +0.87% (S 0.12) | REJECT | results/traderdev_fx_evidence_screen.json |
| EXP-00031 | ema9-vwap canonical repro 4h | IBKR Tier-1 $2min, 0.20bps, sided quotes | EUR 17 IS/11 OOS; GBP 13/13 | EUR OOS +0.01%, Sharpe 0.03, net -$78.98; GBP OOS +0.20%, Sharpe 0.66, net +$253.75 | NOT ELIGIBLE | results/EXP-00031-canonical-fx-reproduction.md |
| FX-001 / FX-002 | MAE reversal / Asian compression | — | — | Case D mechanism failure (wilcoxon p=0.967); Case C spurious (OOS p=0.95) | REJECT | results/FX-00*-evidence-bundle.json |
| 15-concept screen | EURUSD+GBPUSD 4h | ≥200 pips/yr kill | — | **0/15 survive** | sealed | scripts/screening/results.json |

TITAN's own diagnosis of FX: "The expected per-trade edge (approx. 0–2 pips) is consumed
entirely by spread (0.6+ pips) and commission floors ($2.00/side)"
(research/forex_research/WHY_OUR_FOREX_SYSTEM_IS_NOT_CREATING_ALPHA.md:7).

### Crypto (ADR-029, all sealed absorbing negative)

| ID | Hypothesis | Result | Binding cause |
|---|---|---|---|
| CRYPTO-001 | funding/basis | +$482 net IS+OOS but unharvestable at VIP0 taker (10+5 bps) | execution-constrained (costs) |
| CRYPTO-002 | funding+OI deleveraging | 6 IS trades all lost, -$990; 0 OOS | mechanism failure |
| CRYPTO-003 | OFI | 0 trades from 37 IS/3 OOS events (latency decay 250-500ms) | latency/speed |
| CRYPTO-004 | maker basis carry | maker beat taker but failed net carry hurdle | costs |
| CRYPTO-005 | two-sided spread capture | net edge **-2.02 to -2.04 bps/fill**; 2bps maker fee ≈ 40× harvestable half-spread (~0.05 bps) | costs |
| CRYPTO-006 | mid-liquidity band | G2b FAIL 10/20; corr(half_spread, net_edge)=0.967 | costs |
| CRYPTO-007 | maker-rebate feasibility | in-flight | — |

### Equities (ADR-030)

| ID | Strategy | OOS | Verdict |
|---|---|---|---|
| EQ-001 | momentum | Sharpe 0.70 (<1.0 gate), DD 8.30% | negative_result |
| EQ-002 | 5-day reversal | Sharpe -0.17, turnover 414%/mo | negative_result |
| EQ-003 | vol-adj momentum | Sharpe 0.47 | negative_result |
| EQ-005 | (best numeric) | OOS Sharpe 1.63 but 33.86% DD, redundant vs baseline | negative_result |
| EQ-007 | PEAD | OOS Sharpe 1.2485 but fails rank-IC/turnover/replication | negative_result |
| EQ-Micro-001 | — | OOS Sharpe -32.47 | negative_result |

### Gold / macro

- P2 macro-momentum (DFII10+DBC): OOS ann 0.94%, Sharpe 0.178, PF 1.073, maxDD 8.41% → FAIL (3/4 kill criteria).
- P4 multi-TF confluence: gated Sharpe 14.5 vs ungated 19.2 — gate DEGRADES performance; Sharpes flagged as drift artefacts. FAIL.
- REGIME_TEST 27y: TSM GBP flips sign post-2010; carry insignificant both regimes; XS momentum nets +0.02-0.08%.

### Equities backtest summary (context)

SPY daily ma-crossover 2020-24: +2.27% vs B&H 81.06%. Mean-reversion +1.39% (Sharpe
0.65). Everything intraday ≈ 0 or negative.

---

## 2. Cause attribution (A–M), with evidence

| Cause | Verdict | Evidence |
|---|---|---|
| **A. No signal edge (primary)** | **CONFIRMED — dominant** | ~40 experiments, 0 survivors after realistic costs; the only promoted effect (EXP-00017) failed its own OOS retest; the only net-positive candidate (traderdev F1-4h) is +71.8/+336.5 pips/yr on one window and fails the gate; project's own terminal verdict (ALPHA_SEARCH_TERMINAL_REPORT.md:14-15) |
| **B. Weak implementation** | CONFIRMED — contributes | cert-gate crash kills engine backtests AND paper; ReplayEngine same-bar fills; 4 divergent cost models; Path-1 gate bypass |
| **C. Excessive costs** | CONFIRMED — co-dominant with A | FX diagnosis (edge 0-2 pips < spread 0.6+ pips + $2 commission floor); crypto fee-tier analyses; EXP-00022 net 0.00% vs gross +0.10% |
| **D. Overly restrictive risk controls** | REJECTED | crypto execution_constrained outcomes are research-gate verdicts about fees/latency, not risk-gate rejections; risk gate never saw a crypto order. Risk defaults would admit small orders. (Two config miswires exist — see Risk audit — but they don't explain the results.) |
| **E. Position-sizing problems** | LIKELY minor | fixed-fractional sizing is sane; paper_session.py caps gross at 1× capital; no evidence sizing caused the negative results |
| **F. Poor execution simulation** | CONFIRMED — contributes to false confidence | ReplayEngine defaults 0.0/0.0 bps costs; same-bar close fills; EXP-00020: in-sample +6.25 pips/trade vs real-engine -20.00 pips/trade (rolling threshold) — simulation optimism proven |
| **G. Data problems** | CONFIRMED — contributes to false negatives | midpoint-only FX (no bid/ask on disk; spreads assumed 0.10/0.50 bps not measured), 1-year window, 6 corrupt FRED files, no multi-year 1h/4h → the best candidate cannot be properly validated |
| **H. Regime mismatch** | LIKELY partial | REGIME_TEST: TSM sign flip post-2010; but carry insignificant in BOTH regimes |
| **I. Overfitting** | CONFIRMED — system has leaks | OOS→stability-gate leak; best-IS selection over 16-81 combos with OOS Sharpe ≥ 0.0; freeze violated (EXP-00031); BUT the leaks mostly risk false POSITIVES — they did not create false profits here |
| **J. Poor portfolio construction** | NOT APPLICABLE yet | nothing is qualified, so nothing to combine; HRP allocator exists but is dead code |
| **K. Insufficient diversification** | CONFIRMED — structural | entire alpha search is 1-2 pairs at a time (EURUSD/GBPUSD), 1 year, 1 market per family; cross-market charter exists but only just opened |
| **L. Insufficient research** | PARTIALLY REJECTED | 40 experiments is not "insufficient effort"; but breadth was narrow (liquid OHLCV directional/regime/macro only) and depth was blocked by data (no bid/ask, no multi-year intraday) |
| **M. Other: the trading loop is structurally dead** | **CONFIRMED — the second bottleneck** | even a qualified strategy could not trade: no certificate issuance, no session init in entrypoint, no research feedback wiring. The system cannot LEARN from operation because operation cannot happen. |

## 3. Ranked conclusions

1. **Primary cause: no demonstrable post-cost edge in the searched space (A + C).** The
   evidence is unusually strong because the negative results are cost-aware, pre-registered,
   and absorbing — the searches were done honestly enough to trust their verdicts.
2. **Second cause: the learning loop is broken at the promotion→execution seam (M + B).**
   The cert gate is default-deny with no issuance path; paper crashes; engine backtests
   crash; the green test suite masks it (conftest.py:76-85). Research never receives a
   single real execution datum.
3. **Contributing: validation leaks (I) and data poverty (G)** — the two things that would
   matter most once a candidate appears: TITAN can currently neither trust a positive
   (leaks + same-bar fills + Path-1 bypass) nor validate a marginal one (no fresh OOS data;
   freeze unenforced and violated).
4. **Not the cause: risk controls (D), AI absence, Rust/Python boundary, governance effort.**

## 4. What this means

TITAN is not "unprofitable because of bad luck in live trading." It is non-profitable
because (a) it has honestly demonstrated its current hypothesis space contains no
harvestable edge at retail costs, and (b) the machinery that would let it search further
*operationally* (paper trading, research feedback) is broken at the one seam nobody tested
honestly. There is no evidence anywhere in the repo that a profitable live/paper trade has
ever been executed by the current code.

---

# SECOND-AUDIT ADDENDUM — the instrument could not measure, and here is the arithmetic

This section was produced by a second, independent audit that traced the *research* path rather
than the execution path. It exists because **§"WHY ARE STRATEGIES NOT PRODUCING RESULTS" above
treats the negative record as sound evidence. That is the disputed point, and the evidence below
is the counter-case.** Both positions are preserved; neither is deleted.

## A. The measurement instrument has five independently sufficient defects

Each is sufficient on its own to make "0 survivors" uninformative. Full locations and
verification in `BUG_AND_RELIABILITY_REPORT.md` §1b.

| # | Defect | Consequence |
|---|---|---|
| 1 | `screen.py:40-61` never exits a position | **1 trade per hypothesis.** Verified: `results.json` has `"trades": 1` in every cell. The "0/15 concepts" row is void |
| 2 | `replicated` hard-wired `False` | **Zero survivors is a constant.** CRYPTO-001 passed 4/5 gates; EQ-007 passed 5/9 |
| 3 | `validator.py:265` cannot see failed gates | EXP-00017 and EXP-00019 both committed `"decision": "promote"` with failing gates |
| 4 | `cost_bps = 10.0` labelled "~1 pip" | 10–100× overstated; used **only** on the studies that failed. Killed EXP-00022 (t=2.67, 8y) at 0.00% |
| 5 | No `UNDERPOWERED` verdict | 17 of 21 results are **unmeasured**, not refuted |

## B. The power arithmetic — why "rejected" mostly meant "not measured"

Per **Lo (2002)**, `SE(SR_ann) = sqrt((1 + 0.5*SR^2) / T_years)`. This is bounded below by
`1/sqrt(T_years)` **regardless of trade count.** One year of data cannot resolve a Sharpe below
~1.0; two years cannot resolve below ~0.7.

| Experiment | T (yr) | SE(SR_ann) | 95% CI on its own reported Sharpe |
|---|---|---|---|
| EXP-00031 (canonical FX, 11 trades) | 0.41 | **1.56** | EUR 0.03 → [−3.03, +3.09]; GBP 0.66 → [−2.40, +3.72] |
| EXP-00027 (16-cell 4h screen) | 0.41 | **1.84** | hurdle 0.45 = **0.24 SE from zero** |
| EXP-00025 F1 (163 trades) | 1.00 | **1.15** | 0.80 → **[−1.45, +3.05]** |
| EQ-001 / 003 / 006 / 007 | 2.0 | **0.94** | EQ-007 1.25 → **[−0.60, +3.10]** |
| FX-001 (best-powered FX study) | 2.0 | **0.71** | 0.68 → [−0.71, +2.07] — **~16% power** |
| EXP-00023 (G10 carry, t=1.14) | 8.0 | **0.37** | 0.40 → [−0.32, +1.12]; **27% power vs SR=0.5** |

**A true Sharpe of 1.0 and a true Sharpe of 0.0 are statistically indistinguishable on this
evidence.** The project's frozen "≥60 trades" gate was set for the wrong failure mode: at
σ/μ = 1.5, `t = sqrt(60)/1.5 = 5.16` — **9 trades** would suffice. Real trailing-stop FX trades
ran at **σ/μ ≈ 16**, where no trade count inside a 12-month window helps. And per R11 the gate
was evaluated against **bar count**, so it never bound at all.

## C. The cost-constant correction, in full

| Experiment | Gross | Coded cost | Net as recorded | Net at realistic cost |
|---|---|---|---|---|
| **EXP-00022** G10 CS momentum | +5.4%/yr, t=2.67, 8y | 5.20%/yr (10 bps × 52) | **0.00%** | **+4.36 to +4.88%/yr, SR 0.48–0.54** |
| EXP-00023 G10 carry | +2.2%/yr, t=1.14 | 10 bps/leg/mo | rejected | rejected on 27% power, not on the cost |
| EXP-00025 F1@4h | +408.3 pips / 163 trades | **0.9 bp — correct** | candidate | unchanged |

The same repository uses **0.9 bp** (`run_traderdev_families.py:23-24`) and **20 bp**
(`validator.py:214`) for the same instrument in the same month. **The 20 bp figure was applied
to the studies that produced nulls.** Four studies with a *correct* cost model produced the two
best artifacts, the highest-Sharpe equities result, and the one sound falsification. Four
studies with the 10–20 bp constant produced four nulls. **The correlation between cost constant
and outcome is perfect, and it runs in the direction that manufactures nulls.**

Realistic reference points (measured, 2026-09-29):
- Dukascopy EUR/USD H1 tick, 2020-2024, 21,890 bars: **mean 0.18 pips, p90 0.30**
  (raw/ECN lower bound) — https://pkg.go.dev/github.com/rustyeddy/trader
- FX-Brokers.info EU study 2026 (25 brokers, funded accounts): Exness Raw 0.17 pips + $7
  commission = **$8.65/lot** — https://fx-brokers.info/research/spread-study-2026
- UltimateBrokerList Q1 2026: **$6–$18 all-in per 24h round turn**; overnight swap
  **−$5.50 to −$9.80**/std lot/night — https://ultimatebrokerlist.com/real-cost-trading-eurusd

**Recommended:** 0.8–1.5 pips RT (raw/ECN) to 1.5–2.5 pips (CFD), slippage 0.3 median /
1.0–1.5 p95, swap 0.55–0.98 pip-equivalents/night. **Require survival at 4×.**

## D. The strongest cell in the archive — and it is the project's own

`research/results/EXP-00025_traderdev_families.json`, 24 cells, decoded in full:

| Family | Pair | Frame | Trades | Net pips | Avg/trade |
|---|---|---|---|---|---|
| **F1_ema9_vwap** | **EURUSD** | **4h** | **84** | **+71.8** | **+0.86** |
| F2_ema20_60 | EURUSD | 4h | *1* | +99.6 | +99.62 |
| **F3_st_double** | **EURUSD** | **4h** | **49** | **+60.2** | **+1.23** |
| **F1_ema9_vwap** | **GBPUSD** | **4h** | **79** | **+336.5** | **+4.26** |
| *(all 12 cells at 1h)* | | 1h | 2–299 | **every one negative** | |

**The structure, which no memo in the repo records:**
- **0 of 12** 1h cells are positive. **4 of 12** 4h cells are positive — and all positives are 4h.
- Of 4h cells with n ≥ 49, **3 of 8** are positive.
- F1@4h is positive on **both pairs simultaneously** — a single-pair lucky window cannot do that.
- It was modelled with the **correct** cost schedule (0.9 bp RT).
- TITAN's own memo already records it correctly
  (`research/neg_results/EXP-00025_traderdev_families.md`):
  *"F1_ema9_vwap 4h pooled +408.3 pips (84+79 trades) — NET POSITIVE… **Decision: F1_ema9_vwap
  @4h is a CANDIDATE**"* — and notes it fails only *"not quarterly-stable on both pairs"*
  (EURUSD 2/4 quarters, GBPUSD 3/4 — with four quarters, 2/4 is one trade).

**It is not significant and must not be treated as an edge.** Pooled 163 trades, mean
+2.50 pips/trade; trailing exit is 2×ATR(14) on 4h EURUSD (σ ≈ 40–70 pips):

| σ (pips) | t | p (2-sided) |
|---|---|---|
| 25 | 1.28 | 0.201 |
| 40 | 0.80 | 0.424 |
| 55 | 0.58 | 0.561 |
| 70 | 0.46 | 0.648 |

σ is **estimated from trailing-stop geometry, not measured** (the artifact has no `pnl_list`).
Lo 95% CI at SR 0.80: **[−1.45, +3.05]**.

**The finding is about the process, not the strategy:** a candidate that the project itself
labelled `CANDIDATE` was closed by **EXP-00031** — a long-only, `trail_mult = 3.0`-instead-of-
`2.0×ATR-14`, different-fee "reproduction" producing 54 records where the original produced 163.
**A candidate was killed by a non-comparable artifact, not by a test.**

## E. What survives both audits

Genuinely sound regardless of the disagreement:

- **EXP-00016** — intraday momentum falsified. IC −0.0834, n = 12,384, bootstrap CI
  [−0.102, −0.067], consistent across 3 temporal thirds and 2 pairs. **A real negative result.**
- **EXP-00017 retest** — the one promoted effect correctly failed honest OOS (IC 0.121 → 0.053;
  0.098 → 0.038), and the script correctly notes the effect was never OOS-validated before
  promotion and that its target (forward |return|) **is not a tradable signal**.
- **CRYPTO-006** — maker capture, 4,872,006 fills, real Binance maker schedule, edge
  **0.157 bps**. **Well powered, and it found no edge.** A sound negative.
- **EXP-00026** — halted for cause (not cointegrated, p = 0.54).
- **P2** — gold macro-momentum FAIL, 3/4 gates. Survives its own inflationary bug (R17).

**Five sound results. Fifteen void, unmeasured, or underpowered — all recorded as rejections.**

## F. The reconciliation, stated plainly

| Position | Claim | Status |
|---|---|---|
| First audit | The negative record is **not evidence of absence**; the instrument could not measure | Supported by §A–D above |
| Second audit | The negative record is **honest evidence of absence** at retail costs | Weakened by §A–D, but the underlying economic argument (expected edge below spread + commission floor) is not refuted |
| **Merged position** | **Unknown — and currently undecidable with the data in the repo** | — |

**Both audits agree on the actionable consequence, and it does not require resolving the
disagreement:** the instrument must be repaired before any verdict is credible, and the highest-
value single test is a **pre-registered re-run of F1_ema9_vwap 4h on a virgin window with
measured costs**. If the market genuinely has no edge there, that test returns a null on a
*defensible* instrument. If it does, TITAN recovers its first real candidate. **Either outcome
converts the disagreement into a decision — which is the only way out of it.**
