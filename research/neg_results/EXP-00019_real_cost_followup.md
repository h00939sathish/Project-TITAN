# EXP-00019 follow-up — real-cost reversal economics (dukascopy_1m_ba_v1)

Replaces the assumed 1.0-pip RT with ACTUAL bid/ask execution (sell at bid, buy
back at ask for shorts; buy at ask, sell at bid for longs), 1h hold, 12h
lookback, 1-min bars. 2026-06-01 -> 2026-07-31.

| Pair | Window | n | Q1 gross | Q5 gross | Gross TB | SHORT-rally net | LONG-dip net |
|---|---|---|---|---|---|---|---|
| EURUSD | full-day | 63,515 | -0.78 | +0.10 | +0.89 | **+0.58** | -0.11 |
| EURUSD | 12-16 UTC | 10,799 | -2.07 | +0.66 | +2.73 | **+1.95** | +0.54 |
| GBPUSD | full-day | 63,406 | -0.21 | -0.06 | +0.15 | -0.18 | -0.47 |
| GBPUSD | 12-16 UTC | 10,799 | -0.36 | -0.72 | -0.35 | +0.12 | -0.95 |

Figures in pips, net of the REAL spread (no extra slippage modeled).

## Verdict

- The reversal signal survives real costs on ONE leg: **shorting 12h rallies on
  EURUSD** (+0.58 pips net full-day; +1.95 pips net in the London/NY overlap).
- The long-dip leg does NOT pay (asymmetry: rallies pull back, dips don't bounce).
- GBPUSD shows no tradable reversal after real spreads.
- Status: REFINE — 1 pair, 1 leg, 1 window, 2 months. Needs: longer history,
  the full experiment validators on the 1-min dataset, and a strategy-level
  test (entry rules, sizing, rollover for holds crossing 21:00 UTC) before any
  promotion. Not a tradeable strategy yet.
