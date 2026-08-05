# Hypothesis: Time-series momentum replication on QQQ

**id:** 2026-07-13-momentum-qqq-replication
**title:** Replication of 20-day time-series momentum on QQQ — an independent, predeclared dataset
**economic_rationale:** Time-series momentum should generalize across US equity ETFs because trend persistence is a market-structural property. QQQ (Nasdaq-100) has stronger trends than SPY but also higher volatility and sharper reversals, providing a more demanding test. This is a pure replication with unchanged parameters, preregistered before any QQQ momentum results are observed.
**strategy_id:** time-series-momentum
**strategy_params:** lookback=20
**instrument:** QQQ
**universe:** QQQ only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**expected_trade_frequency:** ~10-20 transitions/year (same as SPY)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:**
**success_criteria:
- Sharpe > 0.3 OOS
- Max drawdown < QQQ benchmark max drawdown OOS
- Win rate > 40% OOS
- Minimum 30 OOS trades (gate)
**failure_criteria:
- Sharpe < 0 OOS
- Strategy loses to buy-and-hold (QQQ) on risk-adjusted basis OOS
- Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**notes:** Exact replication of SPY momentum test. No parameters changed. No QQQ momentum results have been observed at time of preregistration.
