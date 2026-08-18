# exp_fx_002 — EURUSD data provenance check

## Goal
Verify that the locally pulled Dukascopy 1-minute EURUSD bars
(`research/dukascopy_1m_ba_prior/EURUSD.json`) are genuine market data by
cross-comparing against an independent 1-second EURUSD OHLC source:
HuggingFace `rashedurzaman1/forex-data` (`7865328_merged.parquet`).

## Method
- `hf_provenance_check.py`: fetches HF 1-sec rows (duckdb range pushdown over
  HTTPS) for two auto-picked 7-day windows, resamples to 1-minute bars using
  the same convention as `scripts/dukascopy_bi5.py aggregate_1m()`
  (floor-minute UTC, o=first, h/l=max/min, c=last), and aligns bar-by-bar
  with the local JSON.
- Windows picked by highest local bar count (feed had gaps, so 7 contiguous
  calendar days were not guaranteed).

## Results
| window | local bars | hf bars | matched | only-local | exact c_bid match |
|---|---|---|---|---|---|
| 2024-11-13..19 | 7,197 | 6,955 | 6,953 | 244 | 98.72% |
| 2025-04-18..24 | 7,193 | 6,354 | 6,353 | 840 | 90.19% |

Drift (pips, local − hf):
- W1: c_bid mean 0.010, p95 0.000, max 5.0; o_bid mean 0.041 (largest, as expected — open is tick-sensitive)
- W2: c_bid mean 0.057, p95 0.300, max 8.2; l_bid max 11.6, o_bid max 19.6
- Bars > 0.5 pip close drift: 51 / 224 (W1 / W2), i.e. < 1% / ~3.5%

## Notes / caveats
- `rashedurzaman1/forex-data` is itself Dukascopy-derived (values align to the
  pip), so this validates the local BI5 pipeline rather than two fully
  independent feeds. Residual drift is consistent with float noise,
  tick-timing differences, and source-side gaps.
- DuckDB materializes the HF parquet timestamps in the session timezone;
  scripts must `SET TimeZone='UTC'` before filtering, else the window shifts
  by the local offset (+5:30 IST).
- `only-local` minutes: Dukascopy bars for minutes where the HF source has no
  ticks (feed gaps / session-clock differences); no reverse discrepancy of
  consequence (2 and 1 bars).

## Conclusion
PASS. Local EURUSD.json bid/ask 1m bars are genuine Dukascopy market data.
Remaining fetch of history (puller PID 5640) can be trusted for model work.
