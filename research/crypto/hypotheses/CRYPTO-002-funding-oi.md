# CRYPTO-002 — Funding + open-interest deleveraging

- **Status:** Preregistered. Active under ADR-029.
- **Economic Mechanism:** Extreme positive (negative) funding rates reflect one-sided speculative positioning. When accompanied by a sharp change in Open Interest (spike indicating exhaustion buildup, or sharp drop indicating liquidation cascade completion), price tends to experience a post-deleveraging reversal.
- **Hypothesis Formulation:**
  - Enter SHORT perp when 8h funding exceeds `funding_abs_threshold` and OI expanded rapidly over `oi_lookback_intervals`.
  - Enter LONG perp when 8h funding is negative beyond `-funding_abs_threshold` and OI collapsed or expanded rapidly into a squeeze.
  - Sizing is 1 unit (hedged with spot or directionally traded under declared cost model).
- **Mandatory Rules:**
  - Preregistered parameters in `CRYPTO-002-prereg.json` are frozen before OOS read.
  - Complete attribution includes taker fees, bid/ask spread, funding, slippage, and adverse stress multipliers.
  - If any gate fails on OOS, output an absorbing `negative_result` record without re-tuning.
