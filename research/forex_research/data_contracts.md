# FX Research — Dataset Contracts

Per the Research OS, every dataset is versioned and immutable. Experiments pin to a contract id.

## TWS 5-min RTH/24h history (pull_tws_history.py)

| Field | Value |
|---|---|
| contract_id | tws_5m_v1 |
| source | IBKR TWS paper (port 7497), reqHistoricalData |
| symbols | EURUSD, GBPUSD (CASH/IDEALPRO, MIDPOINT), SPY/QQQ/IWM/AAPL/MSFT/XLF/XLK (TRADES) |
| bar_size | 5 mins |
| duration | 2 M (2026-06-01 → 2026-07-31) |
| useRTH | 1 (equities: RTH only; forex returned 24h) |
| prices | OHLCV; **forex = MIDPOINT** (no bid/ask!) |
| files | research/tws_history/{SYMBOL}.json |
| notes | 3,276 bars/equity; 12,540 bars/forex pair. Midpoint data → the midpoint illusion applies: spreads must be modeled separately in any backtest (see landscape notes). Weekend gaps present. |

## Dukascopy 1-min bid/ask (pull_dukascopy_1m.py)

| Field | Value |
|---|---|
| contract_id | dukascopy_1m_ba_v1 |
| source | Dukascopy public datafeed (datafeed.dukascopy.com), bi5 hour-ticks, LZMA |
| symbols | EURUSD, GBPUSD (CASH, bid+ask) |
| frequency | 1 min (aggregated from ticks) |
| span | 2026-06-01 → 2026-07-31 (all weekdays covered, ~20h/day) |
| bars | EURUSD 64,295; GBPUSD 64,186 |
| files | research/dukascopy_1m_ba/{SYMBOL}.json |
| fields | timestamp (ISO UTC, minute start), o/h/l/c_ask, o/h/l/c_bid, n (ticks) |
| notes | REAL spreads: EURUSD avg 0.45 / median 0.30 pips; GBPUSD avg 1.02 / median 0.70 pips. TWS-mid vs DK-mid mean |diff| 1.55 pips at matched 5-min marks (timestamp offset + source pool). |

## Observed data profile (tws_5m_v1)

- EURUSD avg 5-min bar range: 2.84 pips; GBPUSD 3.80 pips
- Peak volatility hours UTC: 12:00–15:00 (London/NY overlap); EURUSD 14:00 avg 4.2 pips
- Forex bars cover all 24 UTC hours (thin overnight sessions included)

## Known limitations

- Only 2 months — enough for profiling/experiments, not for stable strategy validation (min 1-2 years needed)
- Midpoint: no spread/slippage info; realistic costs must be assumed (EURUSD retail ~0.5-1.0 pip)
- Single paper-account feed; timestamps UTC, formatDate=2 epoch
