# NEGATIVE RESULT — EXP-00024: Volatility-Weighted Carry (FX-CARRY-VOL)

- **Hypothesis:** Inverse-volatility weighting rescues G10 carry after costs. The
  naive monthly carry (EXP-00023, 2018-07..2026-06) was REJECTED — only mechanical
  accrual, no UIP spot anomaly. Vol-weighting should de-lever during stress and
  reduce drawdown enough to keep the accrual edge alive.
- **Dataset:** research/tws_daily (uncertain daily closes, 2018-07..2026-07) +
  research/fred rates (DFF USD daily; ECBDFR EUR; IRSTCI01{GB,AU,NZ} monthly),
  all percent->decimal /100. EURUSD, GBPUSD, AUDUSD, NZDUSD.
- **Mechanism:** carry c_t = (base_rate_T2 − USD_rate_T2)/100; sigma_t = 21d
  annualized daily vol floored 0.05; w = sign(c)·min(1, |c|/sigma); weekly Wed
  rebalance; net = w·spot + w·c·(1/360) accrual − 10bps on rebalanced notional;
  T-2 point-in-time (no look-ahead).
- **Results (after 10bps):** all pairs positive but weak net Sharpe —
  EURUSD 0.30, GBPUSD 0.13, AUDUSD 0.46, NZDUSD 0.13 (avg **0.26**; Promote bar
  >0.8). **mean maxDD collapsed to 2.1% avg (vs EXP-23 −13.5%) — a real 85%
  drawdown reduction.** But **temporal stability 0/4** (first/second-half sign
  flips) and avg carry spreads NEGATIVE for 3/4 (USD yield exceeded base legs
  most of 2018-26).
- **Decision:** REJECT (fails the falsifiable EXP-00023-beating bar). The robust
  takeaway is REGIME: vol-scaling does not add alpha; it only transforms risk
  (big drawdown cut). The yield differential was negative for most of the window,
  so the "carry" the strategy harvested was an interest differential that the
  2018-26 USD-high-rate regime made structurally unfavorable.
- **Failure type:** Regime (post-2022 USD rate premia) + no UIP spot anomaly.
- **Consistency:** reinforces EXP-00023 — no directional FX alpha survives honest
  evaluation (momentum 00016/21/22, reversal 00019/20, carry 00023/24). Volatility
  clustering (EXP-00017) remains the only promoted effect.
- **Reusable assets:** USD-pair daily closes + FRED/USD/EUR/GBP/AU/NZ short-term
  rate alignment, weekly vol-scaled carry builder, T-2 point-in-time harness,
  Run EXP-00024 script (`research/run_exp_00024_carry_vol.py`), cost_ bits s
  execution, 10bps rebar gate.
- **Next:** do not chase carry in this regime; pivot to vol-scaling of the
  PROMOTED volatility-clustering effect (EXP-00017) and/or OFI microstructure
  (Dukascopy ticks now downloaded for EURUSD/GBPUSD/ AUD/NZD).