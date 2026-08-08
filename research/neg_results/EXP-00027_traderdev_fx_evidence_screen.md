# NEGATIVE RESULT — TraderDev FX-major evidence screen (0/16)

- **Hypothesis (debated plan traderdev-fx-import.md):** Public marketplace
  strategies on the 8 FX majors (4,337 total; top-5/pair) contain signal
  structures that clear TITAN's frozen kill criteria on real data — i.e. the
  marketplace is a source of NEW alpha beyond the closed 40-experiment search.
- **Protocol (debated, Decision A):** NEVER trust marketplace backtests
  (survivorship + lookahead + unknown-cost + parameter opacity). Re-implement
  the signal STRUCTURES natively; run on TITAN's real cost-aware engine with
  frozen criteria: ann ret >4%, OOS Sharpe >0.45, PF >1.2, maxDD <20% @10% vol,
  power >=60 trades; WF-v2 anchored 2-fold; no tuning, no second passes.
- **Dataset:** Dukascopy 1m->4h EURUSD + GBPUSD, 2025-08..2026-07 (the only
  pairs with full local data; AUDUSD ~1mo insufficient, other 6 pairs no data
  — recorded as data-unavailable, not tested).
- **Signals re-implemented natively (8 structural classes):** EMA200+ATR-range
  filter (marketplace top EURUSD 1h), BBW-exp+CoV gate (marketplace novel
  class), EMA-cross trend, Donchian breakout, RSI-2 reversion, MACD momentum,
  Bollinger break, session-time EMA.
- **Result (cost 0.8 pips RT, vol-scaled, anchored 2-fold OOS):**

| Signal | EURUSD | GBPUSD |
|---|---|---|
| ema200_atr_range | -0.91% / S -0.85 | +0.31% / S 0.20 |
| bbw_exp_cov | +0.87% / S 0.12 | -2.25% / S -0.24 |
| ema_cross_trend | -3.31% / S -0.39 | -8.29% / S -0.86 |
| donchian_breakout | -7.44% / S -0.86 | +3.09% / S 0.32 |
| rsi2_reversion | -14.99% / S -3.04 | -2.14% / S -0.37 |
| macd_momentum | -4.83% / S -0.57 | +1.82% / S 0.19 |
| bollinger_break | -1.37% / S -1.07 | -3.50% / S -2.33 |
| session_ema | -12.94% / S -2.58 | -15.18% / S -2.52 |

  **0 of 16 survive the frozen gate.**

- **Methodological integrity note (critical):** an INITIAL run produced a
  phantom PASS (EMA200+ATR "Sharpe 2.6, PF 2.5, both pairs") caused by a
  same-bar lookahead bug in the backtest (flip bars credited the full bar
  return before the position was held; strategy was in-market only 2-8% of
  bars). The bug was caught by a sanity check (impossible PnL given 2-8%
  exposure), fixed, and the corrected screen is 0/16. **The phantom was never
  reported as a survivor** — this is the frozen-discipline process working.
- **Decision:** REJECT. Marketplace FX-major signal structures do not survive
  honest costs on real data — consistent with the closed alpha search (0
  survivors across 6 axes). External leaderboard backtests are not a source of
  transferable alpha for TITAN.
- **Biases documented (Decision C):** survivorship (only current winners
  listed), leaderboard lookahead, parameter opacity (fork.json auth-gated),
  asset-class mismatch (most marketplace strategies are crypto/equity signals),
  rate-limiting on the source API (throttling documented).
- **Reusable assets:** `source_traderdev_fx.py` (API sourcing), 
  `traderdev_fx_screen.py` (native re-implementation + corrected cost-aware
  backtest), `results/traderdev_fx_evidence_screen.json`.