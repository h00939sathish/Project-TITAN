# NEGATIVE RESULT — EXP-00026: Cross-pair mean reversion on EURUSD/GBPUSD

- **Hypothesis:** The EURUSD–GBPUSD pair trade (EURGBP cross) mean-reverts;
  trading the z-score spread yields positive net pips after costs. Structurally
  different from the directional-FX screens (predicts convergence, not
  direction).
- **Protocol:** Multi-model debated (search-broadening-screen.md): screen the
  real EURGBP cross (1× cost), Engle-Granger cointegration pre-gate, 2-fold
  anchored walk-forward, contiguous-surface protocol, calm-vol gate REJECTED.
- **Dataset:** Dukascopy 1m->4h EURUSD + GBPUSD, 2025-08..2026-07 (~1,510
  usable bars after 252 burn-in).
- **Result — HALT at the cointegration pre-gate:**
  - Engle-Granger coint (full window, log prices): **p = 0.54** (> 0.05)
    → not cointegrated → the spread mean-reversion is NOT a stationary,
    tradeable relationship over this window.
  - ADF on the log EUR/GBP spread: p = 0.28 (non-stationary). Price spread:
    p = 0.20 (non-stationary).
  - **Therefore the parameter surface and walk-forward were never run** for
    the full window. Earlier solo screening showing ~+535 pips/yr on a
    Z-score spread was a **spurious edge on a non-stationary series** — the
    gate exists to catch exactly this.
- **Decision:** REJECT/HALT (protocol-mandated). Do not trade cross-pair MR on
  this pair spread.
- **Regime nuance (follow-up hypothesis, NOT a promotion claim):** cointegration
  was regime-dependent — first half 2025-08..2026-01 cointegrated (p=0.003),
  second half 2026-02..2026-07 NOT (p=0.66). That is evidence of a **regime
  change in the relationship**, not a stable edge. Any future test must
  establish stationarity per regime BEFORE trading, on fresh data.
- **Failure type:** Non-stationary spread / relationship breakdown.
  Consistent with the broader finding — no transferable FX alpha survives
  honest evaluation (EXP-00016..26 all REJECTED; only vol-clustering EXP-00017
  is promoted).
- **Reusable assets:** EURGBP cross derivation, Engle-Granger + ADF gate,
  contiguous-surface protocol, 2-fold anchored WF framework.