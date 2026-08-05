# Phase I-B — Real Data Pipeline

> **Goal:** Run the MA(5,20) baseline experiment on versioned, corporate-action-adjusted real data with a fixed out-of-sample period.
> **Exit gate:** The baseline experiment is recorded in the registry with a data_digest, CA adjustment applied, and results that survive adversarial review.

## Tasks

| Task | Description | Type | Dependencies |
|---|---|---|---|
| **I-B1** | Data manifest system — link file checksums → experiment records | Code | None |
| **I-B2** | Corporate actions module — split/dividend adjustments | Code | None |
| **I-B3** | Real SPY data fixture — 1260 daily bars (2020-01-01 to 2024-12-31) | Data | None |
| **I-B4** | Update validate.py — data manifest, CA, fixed OOS period 2023-2024 | Code | I-B1, I-B2, I-B3 |
| **I-B5** | Run baseline experiment and record in registry | Data | I-B4 |

## Constraints

- No credentials in code, docs, or test fixtures
- SPY fixture is synthetic/approximate (for pipeline testing, not trading)
- All data files tracked with SHA-256 in manifests
- Negative results are preserved

---

### I-B1: Data manifest

**Create:** `src/titan/data/manifest.py`

A `DataManifest` that:
- Records source, checksum, date range, instrument_id, record_count, applied_adjustments
- Can be serialized/loaded from JSON
- Hashes to produce a `data_digest` for the experiment registry
- Ties the data file to the processing parameters (which CA adjustments were applied)

**Also create:** `tests/data/test_manifest.py`

### I-B2: Corporate actions

**Create:** `src/titan/backtest/corporate_actions.py`

A `CorporateActionsDB` that:
- Stores split events (date, instrument, ratio) and dividend events (date, instrument, amount)
- `adjust_bars(bars)` — backward-adjusts prices for splits, subtracts dividends
- `register_split(date, instrument, ratio)` and `register_dividend(date, instrument, amount)`

Include the AAPL 4:1 split (2020-08-31, ratio=4) and common dividend events.

**Also create:** `tests/backtest/test_corporate_actions.py` — replace the misleadingly named test file

### I-B3: SPY data fixture

**Create:** `tests/fixtures/market/spy_2020_2024.csv`

Synthetic SPY daily bars from 2020-01-02 to 2024-12-31 (~1260 rows). Based on approximate SPY levels through major regimes:
- 2020-01: ~322, COVID crash to ~223 (Mar 23), recovery to ~370 (Dec)
- 2021: 370 → 470 (steady uptrend)
- 2022: 470 → 360 (bear market)
- 2023: 360 → 470 (recovery)
- 2024: 470 → 585 (uptrend)

Each row: `symbol,date,open,high,low,close,volume`

### I-B4: Update validation pipeline

**Modify:** `scripts/validate.py`

Changes:
1. Accept `--data` argument for CSV path
2. Read data, compute checksum, create DataManifest
3. Apply CA adjustments before backtest
4. Fixed OOS period: train 2020-2022, test 2023-2024
5. Run MA(5,20) baseline + benchmark + walk-forward + perturbation + MC + fee stress
6. Output experiment record with data_digest

### I-B5: Run experiment

Execute: `python scripts/validate.py --data tests/fixtures/market/spy_2020_2024.csv`

Record results in `knowledge/research/experiments/2026-07-13-ma-crossover-baseline.md` (overwrite the synthetic-run version).
