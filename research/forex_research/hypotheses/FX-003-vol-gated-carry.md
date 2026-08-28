# Hypothesis FX-003: M-CARRY (Volatility-Gated Basket Carry)

## Objective
To capture robust alpha via point-in-time overnight yield (swap and financing carry), shielded by cross-asset regime classification (Inverse Volatility gating).

## Rationale
The primary driver of the Forex engine's failure was trading intra-day noise configurations inside of a strictly "Carry-Dominant Compression Regime." The current 2026 reality exhibits multi-polar tightening (central bank divergence). Our `FxCostModel` natively integrates Wednesday T+2 triple settlement swaps, allowing us to explicitly farm positive carry. By running this as a daily (D1) frequency basket rather than single-pair EUR/USD high-frequency scalping, we inherently reduce the $2 per-side ticket commission barrier. 

Because standard carry acts like picking up pennies in front of a steamroller (left-tail crash risk during events, e.g. BoJ interventions), we append a Volatility Gate.

## The Mechanism
1. **The Core Screener**: Each day at New York Close (17:00 EST), calculate the 1-day normalized swap points for every major cross (e.g. AUD/JPY, NZD/CHF, USD/CHF).
2. **Basket Formulation**: Go net long the top 3 (highest positive carry), go net short the bottom 3 (most negative carry) strictly constrained to Dollar-Beta-Neutrality (zero aggregate directional USD exposure).
3. **Volatility Filter**: If the 20-period ATR of the basket surges above the 80th-percentile lookback matrix, reduce or kill the positional exposure immediately (flatten out). Carry dies in high vol.
4. **Target Weighting**: Size components inversely to their variance to target exactly 10% annualized volatility.

## Validation Method
Run a unified walk-forward through `ReplayEngine` starting from 2018 up to Aug 2026. The test cannot qualify for Phase C (Paper Trading) unless it produces a Sharpe ratio > 0.8 net of IBKR Tier 1 minimums ($2 per trade) AND handles negative rollover weeks accurately.
