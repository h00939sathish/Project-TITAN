# CRYPTO-003 — Order-flow / liquidity imbalance

- **Status:** Preregistered. Active under ADR-029.
- **Economic Mechanism:** Aggressive taker volume imbalances ($OFI = \frac{V_{buy} - V_{sell}}{V_{buy} + V_{sell}}$) create short-term directional momentum by consuming top-of-book depth.
- **Quantitative Hypothesis:**
  - When rolling Order Flow Imbalance over `rolling_window_trades` exceeds `+ofi_threshold`, enter LONG perpetual with a declared execution delay (`decay_delay_ms`) and participation limit (`participation_cap = 0.05`).
  - When $OFI$ drops below `-ofi_threshold`, enter SHORT perpetual.
  - Evaluate edge decay against latency (250ms -> 500ms) and taker fee friction (5 bps per turn).
- **Mandatory Rules:**
  - Uses only sequence-valid `TRADE` events with strict monotonic sequence numbers.
  - Fails closed if any sequence regressions or gap anomalies occur.
  - Frozen parameters in `CRYPTO-003-prereg.json` cannot be edited during or after OOS evaluation.
