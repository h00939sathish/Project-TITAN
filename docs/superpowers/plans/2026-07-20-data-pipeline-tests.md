# Data Pipeline Integration Tests Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Add end-to-end integration tests that run a fixture CSV through the full data pipeline (ingest → normalize → quality → manifest → freshness → approved) and into the engine.

**Architecture:** One test file exercising the live pipeline against existing fixtures. No new fixtures, no pipeline code changes.

**Tech Stack:** Python 3.12+, pytest, existing pipeline modules.

## Global Constraints

- No changes to pipeline code — tests only.
- Use only existing fixtures (eurusd_2026.csv, xauusd_2026.csv, plus one equity fixture).

---

### Task 1: Pipeline round-trip tests

**File:** `tests/integration/test_data_pipeline.py`

One test per asset class (forex, gold, equity) that:
1. Reads fixture CSV via `read_csv`
2. Normalizes via `normalize_row`
3. Validates via `validate_and_quarantine`
4. Creates a `DataManifest` via `create_from_bars`
5. Calls `check_freshness`
6. Loads via `load_approved`
7. Feeds bars into a `PaperTradingEngine` with the correct instrument registered
8. Submits a market order and verifies it fills

And one test that verifies bad data is quarantined.

### Task 2: Verify

Run: `python -m pytest tests/integration/test_data_pipeline.py -v`
