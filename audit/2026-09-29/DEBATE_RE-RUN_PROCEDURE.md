# DEBATE RE-RUN PROCEDURE — Council Adjudication Record

**Date:** 2026-09-29
**Topic:** Post-fix re-run procedure — which experiments get re-run after the instrument
fixes, on which virgin windows, with which binding preregistered thresholds.
**Format:** 3-round council debate via the second brain (deliberation room
`t-20260929-2d18c4`, workspace `titan`).
**Voices:** builder (qoder), planner (codex), reviewer (agy), chair (hermes); moderator
qoder. Round 3 was the chair's adjudication, relayed with moderator corrections.
**Status:** CONCLUDED 3/3 rounds. The procedure below is binding for every future
TITAN re-run decision and supersedes any conflicting wording in
`TITAN_NEXT_ACTIONS.md` (both copies) and `secondary/TITAN_NEXT_ACTIONS.md` §9/§9b.

## 1. Convergence record (all four voices agreed; not reopenable)

| # | Subject | Adjudicated outcome |
|---|---------|---------------------|
| 1 | EQ-002-core7 re-run | **REJECTED — sealed.** 24 obs / 7 names can never reach \|t\| ≥ 3.90 at the 546-trial census alpha (α = 9.2e-05). |
| 2 | EXP-00022 | **CONFIRMATION test** (hypothesis sourced from literature — Menkhoff et al. 2012 — not from TITAN's own data). Prereg: window **2018-08..2025-07** (7 pre-freeze years, n ≈ 353), **t ≥ 1.30**, **net Sharpe ≥ 0.45**, N ≥ 300, SE(SR) ≤ 0.40, costs **measured** from the new pull (no assumed bps), pass = survival at 2× and 4× measured cost. Seal if t < 1.00 or net ≤ 0. No promotion basis regardless. |
| 3 | 15 traderdev concepts | **VOID (instrument), not disproven.** Re-runnable only as a NEW programme with FDR control on virgin data. |
| 4 | Diagnostics vs verdicts | Diagnostic re-runs on the known (frozen) window are admissible **only** as instrument validation, never as verdicts. Verdict = virgin window only. |
| 5 | Frozen window | Ratified maintainer rule: no verdict on the frozen 2025-08..2026-07 window, ever (ADR-026). |

## 2. The one open question and its ruling: F1@4h window length

**Facts.** F1 = traderdev EMA9×VWAP 4h. Original evaluation on the frozen window:
EURUSD +71.8 pips / 84 trades, GBPUSD +336.5 pips / 79 trades, t ≈ 0.46–1.28,
Lo 95% CI [−1.45, +3.05] — UNDERPOWERED, not refuted. Repo data reality
(verified 2026-09-29): **zero virgin FX years in the repo** —
`research/fx_clean_5m/EURUSD.json` and `fx_clean_daily` both span exactly
2025-08-01..2026-07-31 (the frozen window); `research/tws_daily/` (EXP-00022's
8-year series) is absent. Any virgin window requires the R1 Dukascopy pull.

**Positions tabled.** CODEX: ≥12 fully virgin years at census alpha (t ≥ 3.90),
net Sharpe ≥ 1.15 (12y → SE = 1/√12 = 0.289 → t = 1.15/0.289 = 3.98, jointly
attainable); if untouched history cannot be demonstrated, do not rerun. AGY: ≥4
virgin years (2020-08..2024-07), SE(SR) ≤ 0.50, pooled N ≥ 200 trades. HERMES:
3 virgin years (2021-08..2024-07), n_min ≥ 300 obs / ≥ 200 trades.

**Selection-on-sample logic (decisive).** Unlike EXP-00022, the F1 hypothesis was
selected **from TITAN's own 16-cell screen results on the frozen window** (the
"CANDIDATE" memo was written from frozen-window numbers). A hypothesis selected
by data-mining one sample carries the full census alpha on any virgin verdict —
the single-test alpha does not transfer. Hence the census bar t ≥ 3.90 governs,
and the arithmetic then fixes the window: at Sharpe ≥ 1.15, T ≥ (3.90/1.15)² ≈
11.5 years → **≥ 12 years**.

**Arithmetic on the ratified "12-month" wording.** SE(SR) = 1/√1 = 1.0 on a
12-month span, so census t ≥ 3.90 would require Sharpe ≥ 3.90 (and even a
single-test t ≥ 2.0 requires Sharpe ≥ 2.0). A 12-month virgin span can only ever
be DIAGNOSTIC; the ratified wording and any verdict ambition were arithmetically
incompatible. (The chair's round-3 attempt to "correct" this arithmetic was
self-contradictory and is rejected; the moderator's arithmetic stands.)

### CHAIR'S FINAL RULING (with moderator corrections, both binding)

1. **F1@4h verdict-grade re-run:** ≥ 12 fully virgin years at census alpha
   (t ≥ 3.90), net Sharpe ≥ 1.15, costs measured from the R1 pull, pass requires
   survival at 2× and 4× measured cost. Preregistered before the pull.
2. **The ratified "virgin 12-month Dukascopy span" is DEMOTED** to
   instrument-validation diagnostic only. It cannot produce a verdict.
3. **Fallback:** if the R1 pull cannot demonstrate ≥ 12 untouched years, F1@4h is
   recorded **VOID (instrument)** — no verdict re-run; the diagnostic continues.
4. **Moderator correction to the chair's example span:** the chair wrote
   "2015-08..2027-07", which contains the frozen window and future months —
   rejected. The operative rule is 12 fully virgin years; a conforming example is
   **2013-08..2025-07** (Dukascopy history reaches ~2003+, so the span is pullable).

## 3. The complete post-fix re-run procedure (binding)

Order of operations after the instrument fixes (F2 → D → C → F4 → A → B → E → F1
→ F3 → R1 → R2 → R3 per `TITAN_NEXT_ACTIONS.md`):

1. **Fix the instruments.** (F2/D/C/F4 — the risk-miswire, cost-basis, gate and
   paper-seam repairs.) Then run **diagnostics on the known window only** to
   validate the instruments; results are recorded as "instrument validated" and
   are **inadmissible as verdicts**.
2. **Pull virgin data (R1).** Dukascopy 1m bid/ask, free tier, ~2003+ available.
   Two mandatory products: (a) the EXP-00022 daily series → **2018-08..2025-07**;
   (b) a 12-year 4h span → **2013-08..2025-07** for F1@4h. Measure bid/ask costs
   from this pull — no assumed bps anywhere in the prereg.
3. **EQ-002-core7:** sealed. Not re-run, not mentioned as pending.
4. **EXP-00022 (CONFIRMATION):** preregistered thresholds t ≥ 1.30, net Sharpe ≥
   0.45, N ≥ 300, SE(SR) ≤ 0.40, survival at 2×/4× measured cost. Seal if
   t < 1.00 or net ≤ 0. Expected t ≈ 1.4 under the corrected prior (net Sharpe ≈
   0.50 on 7 pre-freeze years) with 95% CI ≈ [−0.2, +1.2] including zero — this
   re-run is **seal-or-quarantine, not confirmation**; the FX programme is not
   reopened by it under any reachable threshold.
5. **F1@4h (VERDICT-grade):** 12 virgin years, census alpha t ≥ 3.90, net Sharpe
   ≥ 1.15, measured costs, 2×/4× survival. If the 12-year span cannot be
   demonstrated → VOID (instrument), no verdict re-run.
6. **15 concepts:** VOID (instrument), not disproven. Only re-runnable as a new
   FDR-controlled programme on virgin data, with a new prereg.
7. **Verdict discipline:** no verdict on the frozen window; no verdict on any
   window any TITAN experiment has seen; diagnostic ≠ verdict — never both
   questions on one window.

## 4. Wording reconciliation required

| Location | Current wording | Amended to |
|---|---|---|
| `TITAN_NEXT_ACTIONS.md` (R2 block) | "F1@4h runs on a virgin 12-month Dukascopy span" | "F1@4h verdict re-run requires ≥12 fully virgin years (e.g. 2013-08..2025-07) at census alpha t ≥ 3.90 / net Sharpe ≥ 1.15; the 12-month span is diagnostic-only. If ≥12 untouched years cannot be demonstrated: VOID (instrument)." |
| `secondary/TITAN_NEXT_ACTIONS.md` §9/§9b Window row | 12-month span binding | same amendment |
| Any "0/15 concepts" phrasing in terminal reports | — | "VOID (instrument), not disproven" |

## 5. Record

Round transcripts: `/tmp/council-round{1,2,3}-{codex,agy,hermes}.txt`,
`/tmp/council-round1-builder-qoder.txt`, `/tmp/council-round2-objections.md`,
`/tmp/council-round3-brief.md`. Deliberation room `t-20260929-2d18c4` (titan),
resolved 2026-09-29.
