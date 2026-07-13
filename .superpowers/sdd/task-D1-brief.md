### Task D1: File-based data pipeline

**Files:**
- Create: `src/titan/data/__init__.py`
- Create: `src/titan/data/ingest.py`
- Create: `src/titan/data/normalize.py`
- Create: `src/titan/data/quality.py`
- Create: `tests/data/__init__.py`
- Create: `tests/data/test_pipeline.py`
- Create: `tests/fixtures/market/__init__.py`
- Create: `tests/fixtures/market/sample_ohlcv.csv`
- Create: `tests/fixtures/market/sample_corrupted.csv`

**What to implement:**

1. **`tests/fixtures/market/sample_ohlcv.csv`** with exactly:
```
symbol,date,open,high,low,close,volume
AAPL,2026-01-02,150.00,152.00,149.50,151.00,1000000
AAPL,2026-01-03,151.00,153.50,150.00,152.50,1200000
AAPL,2026-01-06,152.50,155.00,151.00,154.00,900000
MSFT,2026-01-02,400.00,405.00,398.00,402.00,800000
MSFT,2026-01-03,402.00,408.00,401.00,407.00,950000
MSFT,2026-01-06,407.00,410.00,405.00,409.00,700000
```

2. **`tests/fixtures/market/sample_corrupted.csv`** with a bad date row:
```
symbol,date,open,high,low,close,volume
AAPL,2026-01-02,150.00,152.00,149.50,151.00,1000000
AAPL,not-a-date,151.00,153.50,150.00,152.50,1200000
```

3. **`src/titan/data/ingest.py`** — Ingestion:
   - `checksum(path) -> str` — SHA-256 hex digest of a file
   - `read_csv(path) -> list[dict]` — read CSV via csv.DictReader, empty list if file missing
   - `read_parquet(path) -> list[dict]` — read Parquet via pyarrow, return as list of dicts

4. **`src/titan/data/normalize.py`** — Normalization:
   - `VENDOR_SYMBOL_MAP` — dict mapping AAPL/MSFT/GOOGL/AMZN to canonical uppercase
   - `normalize_row(row, source="csv") -> dict | str` — returns normalized dict or error string
   - Checks: unknown symbol, invalid date (%Y-%m-%d), invalid numeric fields, low > high (crossed quote), close outside [low, high], negative volume

5. **`src/titan/data/quality.py`** — Quality:
   - `QuarantineReport` dataclass with total_records, passed, quarantined list
   - `validate_and_quarantine(records, normalize_fn) -> (report, good_records)` — runs rows through normalize, quarantines failures and duplicates by (instrument_id, timestamp)

6. **`tests/data/test_pipeline.py`** — Tests covering:
   - Ingest: checksum format, CSV read, missing file returns empty
   - Normalize: valid row, unknown symbol, bad date, crossed quote, close out of range, negative volume
   - Quality: all valid, quarantines bad rows, duplicate quarantine
   - End-to-end: fixture file → ingest → normalize → quarantine → 6 good records

**Exit:** `python -m pytest tests/data/ -v` passes all tests.

**Working directory:** D:\projects\Project TITAN
**Python:** `.venv\Scripts\python.exe`
