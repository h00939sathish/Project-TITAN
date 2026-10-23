# STRATEGY GAP ANALYSIS

**Date:** 2026-09-29. Does TITAN search broadly enough for edge? **Yes in hypothesis count,
no in measurement quality.** 40+ experiments, ~546 distinct trials, 6 structural axes,
2 asset classes, then 2 post-pivot programs. Hypothesis generation is *not* the shortage.

## Hypothesis class inventory

| Class | Status | Evidence | Limitation | Maturity | Next required experiment |
|---|---|---|---|---|---|
| **Trend following / momentum** | Tested, **void** | EXP-00022 (t=2.67, 8y, killed by 10 bps cost) · EXP-00016 (falsified, n=12,384) · EQ-001 (SR 0.700, 13 ETFs) | EXP-00022's cost constant; 12-month 4h FX | **Low** | **Re-run EXP-00022 at 1–2 bps. Highest-value single experiment in the repo.** |
| **EMA×VWAP hybrid (F1)** | Tested, **then closed without a test** | **F1@4h: EURUSD +71.8 pips/84 trades AND GBPUSD +336.5 pips/79 trades, both positive; 0 of 12 cells positive at 1h** | Closed by EXP-00031 — a long-only, differently-parameterised "reproduction" (54 records vs 163). **t ≈ 0.46–1.28; Lo CI [−1.45, +3.05]** | **Medium** | **Powered re-test with `pnl_list` emitted, DSR + PBO, 3+ years if data allows** |
| **Time-series momentum (TSM)** | Tested, **void** | EXP-00016 (falsified, valid) · EXP-00021 (G10 daily, weak) | EXP-00016's finding is sound and should stand | **Medium** | None. EXP-00016 is a valid negative. |
| **Breakout / Donchian** | Tested, **void** | EXP-00027 (`donchian` cell SR 0.36, SE 1.84) | 644 OOS bars; `sqrt(252)` on 4h bars | **Low** | Re-run with `periods_per_year=1610` and real trade counts |
| **Mean reversion** | Tested, **void** | EQ-002 (SR −0.840, 13 ETFs) · **EQ-002-core7 (SR +0.486, `"verdict":"candidate"`)** · EXP-00020 (n=10) | EQ-002-core7 has IS SR **−0.0296** and rank-IC t≈1.78, p≈0.09 | **Low** | Significance-test EQ-002-core7. It is the only un-rejected artifact and was never tested |
| **Volatility** | Tested, **killed correctly** | EXP-00017 → retest IC 0.121→0.053 | **Target (forward \|ret\|) is not a tradable signal** — knowing magnitude ≠ direction | **Medium** | None. Correctly closed. |
| **Carry** | Tested, **void** | EXP-00023 (t=1.14, **27% power**) · EXP-00024 (vol-scaled, SR 0.13–0.46) | 10 bps/leg vs realistic 1 bp; 27% power | **Low** | Re-run at realistic costs. Literature carry Sharpe 0.5–1.0 sits **inside** the 95% CI [−0.32, +1.12] |
| **Statistical arb / pairs** | Tested, **correctly halted** | EXP-00026 — not cointegrated (p=0.54) | n/a | **Medium** | None. Correct halt. |
| **Relative value / cross-asset** | **Not tested** | PIVOT_DECISION.md:20 lists it as an open avenue | No data acquired | **None** | Acquire before backtesting (per the project's own rule) |
| **Market making** | Tested, **correctly rejected** | CRYPTO-006: 4,872,006 fills, real maker schedule, **edge 0.157 bps** | n/a | **Medium** | None. **This is the best-powered experiment in the repo and it found no edge.** |
| **Rebate regime** | Tested, feasibility-rejected | CRYPTO-007: `depth_capable: false` for **all** symbols | no depth data | **Low** | Needs L2 depth data |
| **Macro** | Tested, **void** | P2 (XAU + DFII10 + DBC): ann 1.49%, SR 0.31, PF 1.14, 3/4 killed | Cost **under**-charged 2–5× (flatters P2) ⇒ FAIL is robust | **Medium** | None. P2's failure survives its own bug. |
| **Order flow / microstructure** | **NOT TESTED** | ALPHA_SEARCH_TERMINAL_REPORT.md:73 — *"requires tick data; declined by budget"* | No tick/L2 in the runtime | **None** | The only class with theorized non-zero alpha |
| **Session effects** | **NOT ACTUALLY TESTED** | `traderdev_fx_screen.py:210-228` `sig_session_ema` derives session from **bar index mod 6**, not timestamps | **Not a session filter** | **None** | Fix to use timestamps, then test properly |
| **Cross-asset** | Not tested | — | No data | **None** | — |
| **Regime-aware** | Tested, **void** | P4: Sharpe 19.25/21.13 — **metric broken**; EXP-00017 regime framing invalid | `p4:139` overlapping cumulative returns | **None** | Fix `p4:139` before drawing any conclusion |
| **Event-driven / fundamental** | Tested, **most interesting** | **EQ-007 PEAD: OOS SR 1.249, DD 10.1%, monotonic quantiles, positive adverse-cost** | 5/9 gates; turnover cap 0.15 breached at 0.181; rank-IC-fraction is a coin flip | **Medium** | **Re-test PEAD with the turnover cap as a sizing variable, not a rejection criterion** |
| **ML** | **ABSENT** | No ML model anywhere in the codebase | — | **None** | Not required yet. Evidence first. |
| **RL** | **ABSENT** | Nothing | — | **None** | **DO NOT BUILD.** No data pipeline, no stats layer, no running runtime. |
| **Hybrid** | **ABSENT** | — | — | **None** | Not required |

## Is TITAN searching broadly enough?

**Broadly: yes.** 6 structural axes, 2 asset classes, 2 post-pivot programs, ~546 trials, and a
genuinely disciplined pre-registration culture. It has **not** been lazy about hypotheses.

**Narrowly: no.** Two structural weaknesses:

1. **Sample, not variety.** 546 trials across **3 datasets and 2 distinct OOS windows**
   (`tws_5m_v1` 2026-06→07, `dukascopy_1m_ba` 2025-08→2026-07, `tws_daily` 2018-2026). Per
   Bailey et al., a 2-year backtest admits **≤7 variants**; TITAN ran ~198 on a 12-month window.
   The exposure is not diversity, it is **re-mining the same window**.

2. **Classes blocked by a data constraint, not an economic one.** Order flow, market
   microstructure, and session effects are exactly the classes the project's own
   `PIVOT_DECISION.md:20-21` identifies as having "theorized non-zero alpha" — and all three
   were skipped for **budget** (`ALPHA_SEARCH_TERMINAL_REPORT.md:73`). That is the wrong reason
   to skip the only classes left.

## The critical distinction: rejected-for-cause vs. unmeasured

| Result | Status | Reason sound? |
|---|---|---|
| **EXP-00016** intraday momentum falsified | **Rejected for cause** | **YES.** n=12,384, bootstrap CI [−0.102,−0.067], consistent across 3 thirds and 2 pairs |
| **EXP-00017 retest** vol-clustering | **Rejected for cause** | **YES.** Failed honest OOS; correctly identified as not a tradable target |
| **CRYPTO-006** maker capture | **Rejected for cause** | **YES.** 4.87M fills, real maker schedule, edge 0.157 bps |
| **EXP-00026** pairs | **Halted for cause** | **YES.** Not cointegrated (p=0.54) |
| **P2** gold macro-momentum | **Rejected for cause** | **YES.** 3/4 gates; survives even its own inflationary bug |
| **EXP-00022** G10 momentum | **REJECTED ON A UNITS ERROR** | **NO** — 10 bps ≠ 1 pip |
| **EXP-00023/24** carry | **UNDERPOWERED** | **NO** — 27% power; CI includes the literature value |
| **EXP-00025 F1** EMA9×VWAP | **UNDERPOWERED** | **NO** — SE(SR)=1.15, CI [−1.45, +3.05] |
| **EXP-00027** 16-cell FX screen | **UNDERPOWERED** | **NO** — SE(SR)=1.84; power gate evaluated on bars |
| **EXP-00031** canonical FX | **NO INFORMATION** | **NO** — SE(SR)=1.56; 11 trades; long-only harness |
| **EQ-001/003/006/007/008** equities | **UNDERPOWERED** | **NO** — SE(SR)=0.94 over T=2y |
| **P4** multi-TF confluence | **VOID** | **NO** — Sharpe 19.25 is impossible |
| **screen.py 15 concepts** | **VOID** | **NO** — 1 trade per hypothesis |
| **CRYPTO-001/002/003** | **EMPTY** | **NO** — n=1, n=0, n=0; `replicated` hard-wired False |
| **EQ-Micro-001** | **VOID** | **NO** — Sharpe −32.47, DD 99.9% |

**3 results of 21 are sound rejections. 1 is a sound halt. 17 are unmeasured or void.**

## What TITAN is missing, strategically

1. **A single class that has never been properly tested: event-driven / fundamental.** EQ-007
   (PEAD) is the highest-Sharpe artifact in the entire archive (1.249) and it was rejected
   partly on a gate that is a **coin flip** (`rank_ic_fraction`, `P(≥15/24 | true 0.70) = 0.847`)
   and partly on a **post-hoc tightened** criterion (EQ-008's prereg explicitly records that
   EQ-007 "showed massive economic edge"). This is the class with the clearest causal
   mechanism in the whole book.
2. **Session effects** — "tested" but the implementation is `i % 6`, not a clock.
3. **Order flow / microstructure** — skipped for budget, not economics. Osler (NY Fed SR 125)
   documents that stop-loss and take-profit orders are **5–10% of total FX deal flow** and
   cluster at round numbers, causing price cascades. That is a *mechanism*, and it is
   reproducible from tick data.
4. **A method for saying "unmeasured" instead of "rejected."** The single most damaging
   missing capability. See `UNDERENGINEERING_REPORT.md`.

## The mechanism question: does any hypothesis have a defensible edge mechanism?

| Hypothesis | Stated mechanism | Does the measurement support it? |
|---|---|---|
| EXP-00017 vol-clustering | Volatility is persistent and forecastable | **Measured a non-tradable target** (magnitude, not direction). Mechanism untested |
| EXP-00022 FX momentum | Cross-sectional currency momentum — a documented anomaly (Menkhoff et al. 2012) | **t = 2.67 over 8 years IS support.** The mechanism is real; the cost constant killed it |
| **F1 EMA9×VWAP @4h** | Trend/mean hybrid on a 4h horizon; frame-dependence implies an execution-horizon mechanism (spread-to-signal ratio, trailing geometry) | **Partial.** Positive on 2 independent pairs, negative on all 12 1h cells, correctly costed — but **t ≈ 0.46–1.28 is not significant.** The *pattern* is suggestive; the *magnitude* is unproven |
| CRYPTO-006 maker capture | Passive fills earn the spread; the edge is the rebate/spread capture | **4.87M fills say the edge is 0.157 bps.** Mechanism tested and rejected on evidence |
| EQ-007 PEAD | Post-earnings-announcement drift — one of the best-documented anomalies in equities | **OOS SR 1.249, DD 10.1%, monotonic quantiles, positive adverse-cost.** Support exists but is **not significant** (SE 0.94) |
| P2 gold macro-mom | Real-rate and dollar drives gold | ann 1.49%, SR 0.31, PF 1.14. **Too weak to support** |

**Verdict:** two hypotheses have both a documented mechanism and a *statistically significant*
measurement — **EXP-00022, FX cross-sectional momentum** (t = 2.67 over 8 years, rejected on a
units error) — and one, **F1 EMA9×VWAP @4h**, has a suggestive *pattern* (positive on two pairs,
frame-dependently, correctly costed) that is **not yet significant** and was closed by a
non-comparable artifact. **Those are where the next experiments start.**
