# PREREGISTRATION (DRAFT) — Volume-source signal robustness, EMA9/VWAP120 on EURUSD + GBPUSD

**Status:** DRAFT. Not frozen until the owner confirms every value marked `[CONFIRM]`
and fills the freeze block (section 11). No new data may be acquired before freeze.

**Study type:** RETROSPECTIVE signal-robustness study on previously inspected market
history. It is **not fresh out-of-sample**, makes **no performance claim**, and is
**not** a WF-v2 candidate evaluation (WF-v2 sections 3 and 4 do not apply). It does not
amend `research/protocol_WF_v2_PRE_FROZEN.md` or the sealed EXP-00033 result.

## 1. Question

Are tick-count volume and Dukascopy vendor BID-candle volume interchangeable as the
weights of the 120-bar close-weighted VWAP used by the F1 signal
(`traderdev_ema9vwap`), at the signal and position level, within pre-declared
engineering tolerances? These are engineering tolerances, not economic materiality
claims. A PASS does not establish negligible performance impact.

## 2. Data window and prior exposure

- Window: 2019-08-01 .. 2022-07-31 (UTC), EURUSD and GBPUSD, 240-minute bars.
- Known prior exposure of this period (the period is NOT untouched):
  - EXP-00024:7-19, evaluations of EURUSD/GBPUSD/AUDUSD/NZDUSD over 2018-07..2026-07
  - EXP-00022:6-14, overlapping momentum screens
  - FX-001:14-34, EURUSD descriptive and trading results using 2021-2024. The
    archived figures came from a data configuration that no longer exists (an earlier
    `dukascopy_1m_ba_prior/` was deleted 2026-10-21 and rebuilt 2026-10-27 from a
    different source), so they cannot be reproduced on today's inputs; the reported
    2021-2024 exposure is taken as stated.
- None of these is known to have run the raw-tick vs vendor-volume comparison. That is
  not proof it was never run.
- Pairs are fixed to EURUSD and GBPUSD. No pair may be added after freeze.

## 3. Frozen implementation

- Strategy settings: EMA 9, VWAP 120 (close-weighted, all-zero volume falls back to
  SMA), ATR 14, trail multiplier 2.0, timeframe 240 min, pip size 0.0001.
- Design identical to the tuning-year diagnostic (timestamp-corrected report
  `comparison-timestamp-corrected-20261029.json`; the original `comparison-full-0714.json`
  is superseded for minute-level figures): both
  arms use tick BID OHLC; only volume `n` differs (accepted tick count vs vendor BID
  candle volume); inner join on UTC minute; unmatched minutes excluded, never filled;
  first 120 4h bars excluded from sensitivity statistics.
- The strategy, resampler and fetch-decoder hashes must match the `provenance.code`
  block of the corrected report, or be re-recorded in the detached manifest (section 11).
  The study's own analysis code (ATR14 on the common price, block bootstrap, event
  matching, 2019-2022 window handling) does not exist yet and must be written and
  pinned in that manifest before freeze. Any code change after freeze invalidates the
  study.

## 4. Pilot disclosure

The tuning-year diagnostic (2025-08..2026-07) was observed before the thresholds below
were fixed. Its per-pair values (EURUSD / GBPUSD), taken from the timestamp-corrected
report (the on-disk tuning-year files still carry the stamping defect):

| Statistic | EURUSD | GBPUSD |
|---|---|---|
| Position disagreement, share of bars active in either arm | 8/386 = 2.07% | 5/333 = 1.50% |
| Signal disagreement, share of bars with a signal in either arm | 12/64 = 18.75% | 10/54 = 18.52% |
| |VWAP difference| p95 (pips; ATR-normalized value not in that report) | 3.50 | 5.07 |

On this pilot the point estimates for T2 and T3 exceed their thresholds on both pairs.
That is not a formal FAIL: both pilot pairs have fewer than 100 union-signal bars (64,
54) and fewer than 600 union-active bars (386, 333), so section 6 would classify both
criteria INCONCLUSIVE. The pilot is not the test window, so this does not breach
preregistration. Scaling the pilot counts by the roughly threefold longer window, if
rates were similar, gives about 190 / 160 union-signal bars and 1,150 / 1,000
union-active bars, which would meet the information requirements; the verdict would
then follow the bounds, and point estimates above threshold would lead to
NOT-WITHIN-TOLERANCE. T1 cannot be evaluated from the pilot report because it did
not record ATR. The thresholds are fixed as written (owner decision); the objective
is measurement, not a passing result.

## 5. Statistics and thresholds (per pair)

Let post-warmup 4h bars be the evaluation set.

- **T1 (VWAP gap):** p95 over bars of |VWAP_vendor - VWAP_tick| / ATR14_common, where
  ATR14_common is Wilder ATR(14) on the common tick-BID 4h OHLC. Threshold: <= 5%.
  Quantile by linear interpolation at (n-1)p.
- **T2 (position):** bars where position differs / bars where either arm holds a
  nonzero position. Threshold: <= 1%.
- **T3 (signal):** bars where signal differs / bars where either arm emits a signal.
  Threshold: <= 5%.
- **Secondary, descriptive only, no decision weight:** event-matched signal agreement
  with +/-1-bar tolerance; EMA-side disagreement; vendor/tick ratio distribution;
  monthly breakdown of T2 and T3. Event matching is deterministic: a signal event is a
  bar with a non-null BUY or SELL signal in an arm; process tick-arm events in
  chronological order; match each to the earliest unused vendor-arm event of the same
  direction at offset 0, else -1, else +1 bars; matching is one-to-one; unmatched
  events from either arm count as disagreements. No randomness.

## 6. Uncertainty and decision rule

Bars are serially dependent (120-bar VWAP memory, persistent positions), so iid
intervals are not allowed.

- Dependence-aware bounds: moving-block bootstrap over post-warmup bars, block length
  240 bars (2 x VWAP window) `[CONFIRM]`, 10,000 resamples, fixed seed recorded at
  freeze. Ratio statistics (T2, T3) resample numerator and denominator jointly. Block
  lengths 120 and 480 are reported as sensitivity only.
- Per criterion per pair, with one-sided bounds `[CONFIRM]`:
  - PASS: 95% upper bound <= threshold. The overall verdict requires all six cells to
    PASS (an intersection test), so no further adjustment applies to PASS.
  - FAIL: lower bound > threshold at the Bonferroni-adjusted one-sided level 0.05/6
    (99.17% bound), because declaring FAIL on any of six cells is a union decision and
    unadjusted per-cell bounds would not control erroneous FAIL declarations.
  - INCONCLUSIVE: otherwise, or if an information requirement is unmet.
- **Information requirements** `[CONFIRM]`, per pair: union-signal bars >= 100;
  union-active bars >= 600; matched-minute share of tick minutes >= 99%; at least 33
  of 36 months with complete data; precision (upper bound minus point estimate) <= 50%
  of the threshold. Any unmet requirement makes that criterion INCONCLUSIVE.
  A complete month is a UTC calendar month in which every day that has tick input is
  present in the manifest, validated, and not partial, aborted or malformed. Days with
  low vendor coverage (section 7) do not by themselves make a month incomplete.
  Zero denominators: an observed zero denominator makes the criterion INCONCLUSIVE; a
  bootstrap resample with a zero denominator is discarded and counted, and more than
  1% discarded makes the criterion INCONCLUSIVE. A zero ATR on a post-warmup bar is a
  data-quality abort.
- **Overall verdict:** WITHIN-TOLERANCE only if all six criterion-pair cells PASS.
  NOT-WITHIN-TOLERANCE if any cell FAILs (takes precedence). Otherwise INCONCLUSIVE.
  Insufficient precision is never reported as agreement.

## 7. Data quality rules (fixed in advance)

- A day with tick data and an empty vendor response, or any malformed or unavailable
  day, aborts the run; the failure report cannot stand in for a comparison.
- Days where the vendor returns a small fraction of tick-covered minutes (EXP-00033
  recorded 1 bar/day for EURUSD on 2024-12-02..06) are not dropped. They are listed,
  and a secondary analysis excluding days with vendor coverage under 50% of tick
  minutes is reported without decision weight.
- Minute-label integrity: for every bar, the timestamp's minute must equal the stored
  true-minute field. Any mismatch aborts the run (the signature of the stamping defect
  found in `pull_dukascopy_1m.py`).
- No synthetic data to fill gaps.

## 8. Execution

- Prerequisite, before any bulk acquisition: correct the tick downloader (a tick must
  be stamped into the minute it occurred in, not a sparse-minute bucket start;
  partial-day acceptance and resume handling must reject or complete partial days) and
  run only a tightly bounded feasibility probe that the owner has explicitly
  permitted. The full three-year pull is out of scope until the study is frozen.
- Acquire tick-derived 1m BID bars with tick counts and vendor candles for the window;
  write per-day SHA256 manifests; freeze the manifests before analysis.
- Run the comparison once. Re-run only for infrastructure failure; archive every
  failure report.
- No parameter, threshold, window, pair or statistic may change after data
  acquisition begins. Deviations void the study.

## 9. Out of scope

No returns, Sharpe, IC, turnover or cost analysis; no promotion input; no effect on
the F1 family closure or the EXP-00033 verdict.

## 10. Reporting

State the verdict, all six cells with point estimates and bounds, whether each
information requirement was met, the pilot-versus-test comparison, and the label
"retrospective, previously inspected history, not fresh OOS".

## 11. Freeze (detached manifest)

A file cannot contain its own hash, so freeze values live in a detached manifest,
`research/PREREG_volume_source_signal_robustness_2019-2022.FREEZE.json`, created at
freeze. It records: owner approval and date; sha256 of this file; hashes of the
strategy, resampler, fetch decoder and the new study analysis code; the bootstrap
seed; the data manifests' hashes; and the ADR reference, if governance requires one
for a study outside WF-v2. The manifest's own hash is recorded outside it (the freeze
commit or tag id, and the ADR). Nothing is frozen until it exists.

## 12. Open items before freeze

1. Write and pin the study analysis code (ATR14 on the common price, block bootstrap,
   deterministic event matching, 2019-2022 window).
2. Correct the tick downloader and its partial-day and resume handling.
3. Owner-permitted bounded feasibility probe (not the full download).
4. Confirm every `[CONFIRM]` value.
