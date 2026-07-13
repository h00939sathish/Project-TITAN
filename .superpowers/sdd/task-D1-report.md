# Task D1 Report — File-based data pipeline

## What was implemented

- **`src/titan/data/__init__.py`** — package init
- **`src/titan/data/ingest.py`** — `checksum()` (SHA-256), `read_csv()`, `read_parquet()` with `IngestMetadata` dataclass
- **`src/titan/data/normalize.py`** — `VENDOR_SYMBOL_MAP`, `normalize_row()` with validation for unknown symbol, invalid date, invalid numeric fields, low > high, close outside [low, high], negative volume
- **`src/titan/data/quality.py`** — `QuarantineReport` dataclass, `validate_and_quarantine()` with duplicate detection by (instrument_id, timestamp)
- **`tests/data/__init__.py`** — package init
- **`tests/data/test_pipeline.py`** — 13 tests covering ingest, normalize, quality, and end-to-end pipeline
- **`tests/fixtures/market/__init__.py`** — package init
- **`tests/fixtures/market/sample_ohlcv.csv`** — 6-row valid OHLCV fixture (AAPL + MSFT)
- **`tests/fixtures/market/sample_corrupted.csv`** — 2-row corrupted fixture (bad date)

## Test results

- `python -m pytest tests/data/ -v` — **13 passed**
- `python -m pytest tests/ -v` — **80 passed** (full suite green)

## Issues

- Initial run had 1 failure: `test_negative_volume` — `int("-100")` does not raise in Python. Fixed by adding explicit `if parsed["volume"] < 0` check in `normalize_row()` before the low > high check.
