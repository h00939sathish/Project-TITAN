# NEGATIVE RESULT — EXP-00016: Intraday momentum (12h -> 1h) in EURUSD/GBPUSD

- **Hypothesis:** Trailing 12h return predicts next 1h return (intraday analog of
  time-series momentum, MOP 2012).
- **Dataset:** tws_5m_v1 (TWS real 5-min bars, MIDPOINT, 2026-06-01 -> 2026-07-31).
- **Result:** IC **negative and significant** on both pairs:
  EURUSD IC=-0.083 (p<0.001, n=12,384), GBPUSD IC=-0.030 (p<0.001, n=12,384),
  cross-instrument consistency 100%. Bootstrap CI fully negative both pairs.
- **Decision:** REJECT (high confidence) — hypothesis FALSIFIED; evidence supports
  the OPPOSITE direction (intraday mean reversion at 12h/1h scale).
- **Failure type:** Directional falsification (significant opposite-sign effect).
- **Reusable features:** return_144 (12h), forward_return_12 (1h) — the reversal
  signal is a candidate follow-up (EXP-00019) with explicit cost modeling.
- **Follow-up:** Test the reversal direction as its own hypothesis; check whether
  the effect survives ~1 pip round-trip costs and whether it is tradable.
