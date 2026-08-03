# Intraday Research Backtests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acquire timestamped 5-minute SPY and EUR/USD research bars, aggregate them reproducibly into 15-minute and hourly datasets, and run non-routing strategy backtests.

**Architecture:** The downloader writes immutable source CSVs plus derived timeframe CSVs into a dated research directory. Every derived bar is built only from complete source bars; the generic strategy harness consumes each CSV without a broker or execution adapter.

**Tech Stack:** Python, Alpaca market-data API, yfinance research feed, pandas, CSV, existing TITAN strategy harness.

## Global Constraints

- Research only: no TWS, IBKR, paper-order, or live-order calls.
- Use 5-minute source data; derive 15-minute and 1-hour bars from it rather than mixing vendors/timeframes.
- Label EUR/USD Yahoo data as unapproved research data; it cannot qualify a trading strategy.
- Preserve UTC timestamps, source, date range, row count, and SHA-256 in a manifest.

---

### Task 1: Acquire and aggregate source data

**Files:**
- Create: `scripts/fetch_intraday_research_data.py`
- Create: `research/intraday_backtests/2026-07-29/*.csv`
- Create: `research/intraday_backtests/2026-07-29/manifest.json`

- [ ] Fetch SPY 5-minute IEX bars with the existing Alpaca environment credentials and EUR/USD 5-minute bars from yfinance.
- [ ] Reject empty, duplicate, non-monotonic, or non-UTC source bars.
- [ ] Aggregate full 5-minute buckets into 15-minute and hourly OHLCV bars and write source, coverage, and checksums to the manifest.

### Task 2: Run the four timeframe studies

**Files:**
- Create: `research/intraday_backtests/2026-07-29/results.json`

- [ ] Run `scripts/backtest_strategies.py` for SPY and EUR/USD at 5m, 15m, and 1h, with the existing five strategy defaults.
- [ ] Run the existing daily fixture backtests separately; do not relabel an intraday bar as daily.
- [ ] Record command, source, row count, coverage, and output in `results.json`.

### Task 3: Validate evidence boundaries

- [ ] Confirm each output has a non-zero bar count and an expected UTC range.
- [ ] Confirm no result is presented as a promotion decision, qualification result, or evidence for paper routing.

## Self-review

- The plan obtains one base frequency and derives all intraday comparisons consistently.
- It keeps source provenance and the unapproved-forex limitation visible.
- It contains no broker order path.

