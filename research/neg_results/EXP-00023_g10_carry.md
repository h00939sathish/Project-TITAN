# NEGATIVE RESULT — EXP-00023: Cross-sectional G10 carry trade (8y, 7 currencies)

- **Hypothesis:** Long high-rate / short low-rate G10 currencies earns positive
  total return (Lustig-Roussanov-Verdelhan 2011; Menkhoff et al. 2012).
- **Dataset:** research/tws_daily (Yahoo CCY, 8y daily) + research/fred policy
  rates (DFF, ECBDFR, IRSTCI01*). 7 currencies (CHF/SEK/NZD excluded — FRED
  rate series discontinued). 96 monthly rebalances, 2018-07 -> 2026-06.
- **Results:**
  - Total (spot + accrual): +0.18%/mo (+2.2%/yr), t=1.14, win 57%, maxDD -13.5%
  - Spot only (UIP violation): +0.06%/mo (+0.7%/yr), t=0.38 — absent
  - Accrual: +0.12%/mo (+1.4%/yr) — mechanical rate differential only
- **Decision:** REJECT (no statistically significant edge). The only return is
  the mechanical interest accrual; the UIP-violation spot anomaly does not
  appear in this window.
- **Failure type:** Regime (post-2008 carry compression; 2020-22 rate cycles);
  spot anomaly absent.
- **Consistency:** Completes the family sweep — momentum (EXP-00016/21/22),
  reversal (EXP-00019/20), carry (EXP-00023): no directional FX alpha survives
  honest evaluation in this data. Volatility clustering (EXP-00017) remains the
  only promoted effect.
- **Reusable assets:** FRED rate puller, monthly rate-bucket alignment, carry
  spread machinery (7-currency universe, accrual-correct).
- **Next questions:** none within classic single/basket FX directional alpha;
  pivot to vol-scaling risk layer (EXP-00017) and/or microstructure/flow
  features (OFI — needs tick data with volume, Dukascopy ticks now available).
