# Live Data Pipeline Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Polygon.io-based data fetcher for forex and spot-gold daily OHLC bars, enabling live-ish data ingestion without manual CSV creation.

**Architecture:** One new `polygon_feed.py` module following the same pattern as `alpaca_feed.py` — fetch bars, normalize, return approved data source. Multi-symbol support via a simple batch loop.

**Tech Stack:** Python 3.12+, `polygon-api-client` (or direct REST if already available), existing pipeline modules.

## Global Constraints

- The `polygon-api-client` package is NOT currently a dependency — add it if needed, or use direct REST.
- API key from env var `POLYGON_API_KEY`.
- Forex symbols use the format `C:EUR/USD` in Polygon's REST API.
- XAUUSD uses `C:XAU/USD`.
- Daily bars only (1-day aggregation).
- Must integrate with the existing pipeline (normalize → approved → engine).

---

### Task 1: Polygon forex/gold daily-bar fetcher

**File:** `src/titan/data/polygon_feed.py`

Module with:
- `PolygonFeed` class (or module-level functions) that fetches daily OHLC bars for a given symbol
- Support for forex pairs (EURUSD → `C:EUR/USD`) and gold (XAUUSD → `C:XAU/USD`)
- Returns data compatible with `normalize_row` and `load_approved`
- API key from `POLYGON_API_KEY` env var
- Error handling for missing key, network failure, empty response

### Task 2: Multi-symbol batch fetch

**File:** `src/titan/data/polygon_feed.py` (same file)

Function `fetch_batch(symbols: list[str], days: int) -> dict[str, ApprovedDataSource]` that fetches multiple symbols and returns a dict keyed by symbol.

### Task 3: Integration test

**File:** `tests/data/test_polygon_feed.py`

Test that:
- `fetch_daily_bars("EURUSD", 5)` returns a list of dicts with expected fields
- `fetch_batch` returns all requested symbols
- Empty/invalid symbols return empty or raise
- (SKIP if POLYGON_API_KEY not set — network-dependent)

### Task 4: Wire into backtest script

Update `scripts/backtest_forex.py` and `scripts/backtest_spot_gold.py` to accept an optional `--live-data` flag that fetches from Polygon instead of the fixture CSV.
