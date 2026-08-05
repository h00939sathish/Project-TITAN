# Hypothesis: Time-series momentum on SPY

**id:** 2026-07-13-momentum-spy
**title:** A 20-day time-series momentum strategy on SPY generates positive risk-adjusted returns after costs
**economic_rationale:** Time-series momentum captures persistent directional trends by going long when the N-day return is positive and short when negative. This is economically distinct from both the MA crossover (which uses two moving averages and only goes long) and mean reversion (which bets against the trend). Time-series momentum can profit from both uptrends and downtrends. The 20-day lookback balances sensitivity (captures short-term trends) with noise reduction.
**strategy_id:** time-series-momentum
**strategy_params:** lookback=20
**instrument:** SPY
**universe:** SPY only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**expected_trade_frequency:** ~10-20 transitions/year (trend changes several times per year)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:**
**success_criteria:
- Sharpe > 0.3 OOS
- Max drawdown < SPY benchmark max drawdown OOS
- Win rate > 40% OOS
- Minimum 30 OOS trades (gate)
**failure_criteria:
- Sharpe < 0 OOS
- Strategy loses to buy-and-hold (SPY) on risk-adjusted basis OOS
- Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**notes:** First test of time-series momentum family on SPY. Uses the new TimeSeriesMomentum strategy registered as time-series-momentum v1.0.0. This is a long/short strategy — distinct from all prior hypotheses (which are long-only).
