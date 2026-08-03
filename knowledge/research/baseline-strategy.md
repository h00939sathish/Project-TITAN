# Baseline Strategy: MovingAverageCrossover(5,20)

> **Owner:** TITAN Development
> **Status:** Draft — v1.0
> **Last Review:** 2026-07-13

## Strategy

Simple moving average crossover: when the 5-day SMA crosses above the 20-day SMA, enter long; when it crosses below, exit to cash.

- Entry: `SMA(5) > SMA(20)` (close price)
- Exit: `SMA(5) < SMA(20)` (close price)
- Position sizing: 100% allocated when in market, 0% in cash
- No shorting, no leverage

## Economic rationale

Trend following captures momentum. Crossovers are the simplest testable trend signal. Despite their simplicity, they remain economically motivated: markets exhibit serial correlation at short horizons due to gradual information diffusion and institutional order flow. This strategy is intended as the **floor** — any proposed strategy must beat this baseline to warrant further investigation.

## Instrument

| Field | Value |
|---|---|
| Ticker | SPY |
| Description | SPDR S&P 500 ETF |
| Rationale | Most liquid US equity ETF; simplest corporate actions (quarterly dividends only); tightest spreads; daily volume > 50M shares |

## Benchmark

Buy-and-hold SPY over the same period. All metrics are reported net of the same cost assumptions.

## Data

- **Source:** CSV fixture or Polygon.io daily bars
- **Fields:** `date, open, high, low, close, volume`
- **Frequency:** Daily (end-of-day)
- **Corporate actions:** None adjusted (baseline limitation — see data-gaps.md)

## Period

| Split | Start | End | Purpose |
|---|---|---|---|
| Train | 2020-01-01 | 2021-12-31 | Parameter selection / sanity-check |
| Validation | 2022-01-01 | 2022-12-31 | Out-of-sample tuning |
| Test | 2023-01-01 | 2024-12-31 | Final out-of-sample evaluation |

## Success criteria

| Metric | Threshold |
|---|---|
| Sharpe ratio (OOS) | > 0.5 |
| Max drawdown | < SPY benchmark max DD |
| Win rate | > 40% |

## Failure criteria

| Condition | Trigger |
|---|---|
| Sharpe ratio (OOS) | < 0.0 |
| Risk-adjusted return | Strategy loses to buy-and-hold SPY |

## Rationale for this baseline

1. **Simplest testable hypothesis** — a single rule, two parameters, no optimiser.
2. **Not novel** — deliberately. A 5/20 SMA crossover is widely known; it establishes whether our research infrastructure produces plausible results before we test novel ideas.
3. **Economically motivated** — trend following is one of the most studied and persistent factor premiums across asset classes and decades.
4. **Reproducible** — daily SPY data is freely available; the rule is deterministic; results are auditable.
5. **Gate for future work** — any strategy that cannot beat this baseline after costs does not advance to implementation review.
