# ADDENDUM to EXP-00033 — volume-source diagnostic (DRAFT, owner review)

**This addendum does not amend the sealed EXP-00033 result.** Verdict REJECT stands.

## Purpose

EXP-00033 recorded a caveat: VWAP weights were tick counts in the tuning window and
vendor bid-candle volume in the prior window. This addendum records what a diagnostic
measured about that difference.

## What was measured

- Source of the figures below: [comparison-timestamp-corrected-20261029.json](../evidence/volume_source_20261029/comparison-timestamp-corrected-20261029.json),
  SHA256 `6dd59ed6e1c1abaf191160d4a5258359e454dfaad4a3a4018e909579e5fbac3d`, produced by
  the unmodified comparison script over a copy of the same rows with corrected
  timestamps.
- Superseded for minute-level figures: [comparison-full-0714.json](../evidence/volume_source_20261029/comparison-full-0714.json),
  SHA256 `608d7a4bfc02494d279aac58b0af3122a898d35736b51fede8547720a16c00b0`, generated
  2026-10-29T07:14:25Z. The tick files it read carried a stamping defect from the
  downloader (`scripts/pull_dukascopy_1m.py`): within each hour, timestamps were the
  bar's ordinal (00, 01, 02...) rather than its true minute, on 6.4% of EURUSD rows and
  7.6% of GBPUSD rows. OHLC, tick counts, row counts and day coverage were unaffected.
  Its minute-level statistics (coverage, tick-only/vendor-only counts, native BID OHLC
  mismatches, 1m correlations, 1m vendor/tick ratio extremes) were artifacts of the
  defect and must not be cited. The files on disk have not been relabelled.
- [verification-full-0714.json](../evidence/volume_source_20261029/verification-full-0714.json)
  was reconstructed from the same mislabelled input, so it confirms internal
  consistency of that report, not correct labels.
- Window: 2025-08-01..2026-07-31, the F1 tuning year. The report labels it
  "exhausted tuning year, NOT new OOS". It is diagnostic-only (`can_qualify: false`).
- Frozen F1 settings (EMA 9, VWAP 120, ATR 14, trail 2.0), 240m bars. Both arms use
  tick BID OHLC; only volume differs (tick count vs vendor BID candle volume).
- Acquisition complete: 313/313 days per pair, no failures.

## Results (EURUSD / GBPUSD)

| Measure | EURUSD | GBPUSD |
|---|---|---|
| Matched minutes, share of tick minutes | 100.00% | 100.00% |
| Volume correlation, 4h (Pearson / Spearman) | 0.978 / 0.971 | 0.898 / 0.945 |
| Vendor volume per tick, 4h median | 1.54 | 1.16 |
| |VWAP difference| median / p95 / max (pips) | 0.86 / 3.50 / 7.37 | 1.08 / 5.07 / 13.12 |
| EMA-side disagreement | 8/1490 (0.54%) | 6/1490 (0.40%) |
| Signal disagreement | 12/1490 (0.81%) | 10/1490 (0.67%) |
| Position disagreement, all post-warmup bars | 8/1490 (0.54%) | 5/1490 (0.34%) |
| Position disagreement, bars active in either arm | 8/386 (2.07%) | 5/333 (1.50%) |

## What this supports

Within the tuning year, switching the volume source changed F1's position on
0.34-0.54% of bars (1.5-2.1% of bars active in either arm), with a median VWAP shift of
about one pip. Vendor volume is a float averaging 1.2-1.5x tick count; the scale
cancels in a VWAP ratio, so the relevant property is the within-window distribution.

## What this does not support

- It did not evaluate 2022-08..2025-07 and does not measure whether the
  tick-to-vendor relationship drifts across years.
- It contains no returns, Sharpe, IC or turnover.
- It makes no statement about why EXP-00033's IC or turnover criteria failed.

## Effect on EXP-00033

None. The caveat is quantified for the tuning year only; the REJECT decision and the
reported figures are unchanged. EXP-00033's cost basis is governed by ADR-036; this
addendum adds no cost analysis.

## Follow-up

`research/PREREG_volume_source_signal_robustness_2019-2022.md` (draft): a retrospective
signal-robustness study on previously inspected history, not fresh OOS.
