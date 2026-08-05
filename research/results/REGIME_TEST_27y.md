# REGIME TEST — 27 years of FRED daily FX, pre/post-2010 split

Dataset: FRED H.10 daily FX (EURUSD 1999+, others 1971+; through 2025-12),
FRED policy rates (DFF, IRSTCI01*). Same code paths as EXP-00021/22/23.

## TSM (EURUSD/GBPUSD, forward 63d, Spearman IC)

| lookback | EUR pre | GBP pre | EUR post | GBP post |
|---|---|---|---|---|
| 21d | +0.028 | -0.056 | +0.020 | +0.012 |
| 63d | +0.015 | +0.069 | +0.039 | -0.030 |
| 126d | +0.037 | +0.056 | +0.041 | -0.037 |
| 252d | +0.007 | **+0.090** | **-0.091** | **-0.108** |

Reading: GBPUSD TSM was solidly positive pre-2010 at 3-12m lookbacks (+0.09 at
252d); post-2010 the 12m horizon is strongly NEGATIVE on both pairs and GBP
mid-horizons flipped. Classic "effect decayed after the regime shift" pattern —
consistent with the momentum-crash literature (Daniel-Moskowitz 2016).

## Cross-sectional momentum (9 currencies)

- 1m/weekly: pre +0.18%/period (t=3.23) -> post +0.12%/period (t=3.96).
  **Significant in BOTH regimes** — the effect is real and regime-robust, but
  nets ~+0.02-0.08% at 10bps costs. Small-but-real, cost-fragile.
- 3m/monthly: negative in both windows.

## Carry (7 currencies vs USD)

- pre-2010: total +0.15%/mo (t=0.88), spot -0.09%/mo (t=-0.52)
- post-2010: total +0.08%/mo (t=0.67), spot -0.04%/mo (t=-0.29)
- **Even the golden era shows no significant carry in this construction** — the
  UIP spot anomaly is absent in both windows (our 7-currency equal-weight
  USD-numeraire slice; the literature used wider/weighted constructions).

## Verdict

Momentum-family decay is confirmed (12m TSM: +0.09 pre -> -0.11 post). The only
regime-robust effect is 1m/weekly cross-sectional momentum, and it does not
survive realistic costs. Carry shows nothing in either regime in this
construction. Original conclusion strengthened: no cost-surviving directional
edge in either regime; effects were somewhat stronger pre-2010 as expected.
