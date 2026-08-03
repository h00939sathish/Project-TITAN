# NEGATIVE RESULT — EXP-00020 (revised): EURUSD short-rally reversal, honest calibration

- **Hypothesis:** Shorting EURUSD when the 12h-reversal signal is in the top
  quintile (12-16 UTC), 1h hold, earns net positive pips after real spreads.
- **V1 (2 months, in-sample threshold):** +6.25 pips/trade net through the real
  engine (16 fills) — REFINE.
- **V2 (12 months, ROLLING threshold — trailing 30d, recalibrated every 5d, no
  lookahead):** **-20.00 pips/trade net (10 fills, -$20 on 1000-unit lots).**
- **Decision:** REJECT as a strategy. The edge is calibration-fragile: it
  changes sign when the threshold is estimated without lookahead, which is how
  it would actually be run. A genuine edge must survive honest parameter
  estimation.
- **Failure type:** Overfitting to in-sample threshold + small fill sample.
- **Caveats recorded:** only 10 fills through the conservative limit-fill model
  (610 rejected) — wide error bar on the -20; the fragility finding is robust to
  fill mechanics either way.
- **Reusable assets:** rolling-threshold machinery, dukascopy_1m_ba_v1 (12
  months, 371K bars/pair), ShortRallyReversal strategy harness.
- **Consistency:** joins EXP-00016/19/21/22 — no directional FX alpha survives
  honest evaluation in this data. EXP-00017 (volatility clustering) remains the
  only promoted effect.
