# NEGATIVE/MARGINAL RESULT — EXP-00022: Cross-sectional G10 currency momentum

- **Hypothesis:** Ranking 9 G10 currencies by trailing 1m/3m return vs USD and
  going long top tercile / short bottom tercile earns a positive, cost-surviving
  spread (Menkhoff et al. 2012 replication).
- **Dataset:** research/tws_daily (Yahoo CCY, 2,083 common trading days,
  2018-07-30 -> 2026-07-30), 9 currencies.
- **Results:**
  | lookback | rebalance | n | gross/period | t | win | net (10bps/leg) |
  |---|---|---|---|---|---|---|
  | 1m | weekly | 412 | +0.10% (+5.4%/yr) | 2.67 | 59% | **+0.00% (zero)** |
  | 1m | monthly | 98 | -0.20% (-2.4%/yr) | -1.27 | 46% | negative |
  | 3m | weekly | 404 | +0.04% (+1.9%/yr) | 0.71 | 50% | negative |
  | 3m | monthly | 96 | -0.27% (-3.3%/yr) | -1.38 | 50% | negative |
- **Decision:** REJECT (as a tradeable effect). The only significant cell
  (1m/weekly, t=2.67) nets exactly zero at 10bps/leg and only +2.6 to +3.9%/yr
  net at institutional 5-2.5bps/leg — marginal and frequency-fragile.
- **Failure type:** Cost sensitivity (effect real but smaller than execution
  costs) + regime (monthly rebalances negative in 2018-2026).
- **Consistency:** Matches EXP-00021 (daily TSM weak/absent) and EXP-00016/19
  (intraday momentum falsified). The momentum family across horizons and forms
  shows no exploitable edge in this data.
- **Reusable assets:** G10 daily basket (9 pairs, 8y), currency-return sign
  convention (XXXUSD + / USDXXX -), tercile spread machinery.
- **Next questions:** Carry (needs rate differentials — FRED pull); vol-scaling
  layer on EXP-00017 (the only PROMOTED effect); or accept the regime is thin.
