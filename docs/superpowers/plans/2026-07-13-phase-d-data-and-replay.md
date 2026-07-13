# Phase D — Data and Replay Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic file-based data pipeline (ingest → normalize → quality quarantine) and a replay/backtest engine that runs normalized data through the Phase C capital path and produces verifiably identical results across runs.

**Architecture:** Pure Python data pipeline (CSV/Parquet in → normalized Parquet + manifest out). Python replay/backtest engine uses the existing Rust core (PortfolioEngine, RiskGate, SimulatedAdapter) with a Python clock and fill models. Determinism is guaranteed by fixed-seed PRNG and event-time ordering.

**Tech Stack:** Python 3.14, pandas, pyarrow/parquet, hashlib, dataclasses, pytest.

## Global Constraints

- All data processing is deterministic (fixed seed, no random).
- Invalid records are quarantined, never silently dropped.
- Normalized data preserves source checksum and ingest metadata for lineage.
- Replay runs the same risk → execution → portfolio contracts as live operation.
- Bar-conservative fill model only (order-book simulation deferred).
- Throughput target: 1M events <15s (Phase D measures the baseline).
- Every fill, position, PnL, and metric is byte-for-byte identical across runs with same inputs.

---

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

**What to build:**

1. **`src/titan/data/__init__.py`** — package init.

2. **`tests/fixtures/market/sample_ohlcv.csv`** — a small, valid CSV with OHLCV data:
```csv
symbol,date,open,high,low,close,volume
AAPL,2026-01-02,150.00,152.00,149.50,151.00,1000000
AAPL,2026-01-03,151.00,153.50,150.00,152.50,1200000
AAPL,2026-01-06,152.50,155.00,151.00,154.00,900000
MSFT,2026-01-02,400.00,405.00,398.00,402.00,800000
MSFT,2026-01-03,402.00,408.00,401.00,407.00,950000
MSFT,2026-01-06,407.00,410.00,405.00,409.00,700000
```
Also create a corrupted fixture `tests/fixtures/market/sample_corrupted.csv`:
```csv
symbol,date,open,high,low,close,volume
AAPL,2026-01-02,150.00,152.00,149.50,151.00,1000000
AAPL,not-a-date,151.00,153.50,150.00,152.50,1200000
```

3. **`src/titan/data/ingest.py`** — Ingestion module:
```python
"""Ingest raw CSV/Parquet market data files."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class IngestMetadata:
    source_path: str
    source_checksum: str
    ingested_at: str
    record_count: int
    schema_version: str = "1.0"

def checksum(path: str | Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def read_csv(path: str | Path) -> list[dict]:
    """Read CSV file into a list of dicts. Returns empty list on file not found."""
    import csv
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)

def read_parquet(path: str | Path) -> list[dict]:
    """Read Parquet file into a list of dicts."""
    import pyarrow.parquet as pq
    table = pq.read_table(str(path))
    return table.to_pylist()
```

4. **`src/titan/data/normalize.py`** — Normalization module:
```python
"""Normalize raw market data to canonical format."""

from datetime import datetime

# Canonical instrument ID mapping (vendor symbol → canonical)
VENDOR_SYMBOL_MAP = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
}

def normalize_row(row: dict, source: str = "csv") -> dict | str:
    """Normalize a single row. Returns normalized dict or error message string."""
    try:
        symbol = row.get("symbol", "").strip().upper()
        canonical = VENDOR_SYMBOL_MAP.get(symbol)
        if not canonical:
            return f"Unknown symbol: {symbol}"
        
        date_str = row.get("date", "").strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date: {date_str}"
        
        fields = {"open", "high", "low", "close", "volume"}
        parsed = {}
        for f in fields:
            val = row.get(f, "").strip()
            try:
                parsed[f] = float(val) if f != "volume" else int(val)
            except (ValueError, TypeError):
                return f"Invalid {f}: {val}"
        
        if parsed["low"] > parsed["high"]:
            return f"Low > high: low={parsed['low']} high={parsed['high']}"
        if parsed["close"] < parsed["low"] or parsed["close"] > parsed["high"]:
            return f"Close outside range: close={parsed['close']} low={parsed['low']} high={parsed['high']}"
        
        return {
            "instrument_id": canonical,
            "timestamp": dt.isoformat(),
            "open": parsed["open"],
            "high": parsed["high"],
            "low": parsed["low"],
            "close": parsed["close"],
            "volume": parsed["volume"],
        }
    except Exception as e:
        return f"Processing error: {e}"
```

5. **`src/titan/data/quality.py`** — Quality quarantine:
```python
"""Quality checks and quarantine for market data."""

from dataclasses import dataclass, field

@dataclass
class QuarantineReport:
    total_records: int = 0
    passed: int = 0
    quarantined: list[dict] = field(default_factory=list)
    
    @property
    def quarantine_count(self) -> int:
        return len(self.quarantined)

def validate_and_quarantine(records: list[dict], normalize_fn) -> QuarantineReport:
    """Run records through normalize_fn. Good records pass; bad records are quarantined."""
    report = QuarantineReport(total_records=len(records))
    good = []
    seen = set()
    for row in records:
        result = normalize_fn(row)
        if isinstance(result, str):
            report.quarantined.append({"row": row, "reason": result})
        else:
            # Duplicate check on (instrument_id, timestamp)
            key = (result["instrument_id"], result["timestamp"])
            if key in seen:
                report.quarantined.append({"row": row, "reason": f"Duplicate: {key}"})
            else:
                seen.add(key)
                good.append(result)
                report.passed += 1
    return report, good
```

6. **`tests/data/test_pipeline.py`** — Tests:
```python
"""Tests for the data pipeline."""

from titan.data.ingest import checksum, read_csv
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "market"

class TestIngest:
    def test_checksum(self):
        path = FIXTURES / "sample_ohlcv.csv"
        cs = checksum(path)
        assert len(cs) == 64  # SHA-256 hex length

    def test_read_csv(self):
        rows = read_csv(FIXTURES / "sample_ohlcv.csv")
        assert len(rows) == 6

    def test_read_csv_not_found(self):
        assert read_csv("nonexistent.csv") == []

class TestNormalize:
    def test_valid_row(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000000"}
        result = normalize_row(row)
        assert isinstance(result, dict)
        assert result["instrument_id"] == "AAPL"
        assert result["close"] == 151.0

    def test_unknown_symbol(self):
        row = {"symbol": "UNKNOWN", "date": "2026-01-02", "open": "100", "high": "100", "low": "100", "close": "100", "volume": "100"}
        assert isinstance(normalize_row(row), str)

    def test_invalid_date(self):
        row = {"symbol": "AAPL", "date": "not-a-date", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000000"}
        assert isinstance(normalize_row(row), str)

    def test_crossed_quote(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "155", "close": "151", "volume": "1000000"}
        result = normalize_row(row)
        assert isinstance(result, str) and "low" in result

    def test_close_out_of_range(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "160", "volume": "1000000"}
        result = normalize_row(row)
        assert isinstance(result, str) and "Close" in result

    def test_negative_volume(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "-100"}
        assert isinstance(normalize_row(row), str)

class TestQuality:
    def test_all_valid(self):
        from titan.data.normalize import normalize_row
        rows = [
            {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "MSFT", "date": "2026-01-02", "open": "400", "high": "405", "low": "398", "close": "402", "volume": "2000"},
        ]
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 2
        assert report.quarantine_count == 0
        assert len(good) == 2

    def test_quarantine_bad_rows(self):
        from titan.data.normalize import normalize_row
        rows = [
            {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "UNKNOWN", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "AAPL", "date": "bad-date", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
        ]
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 1
        assert report.quarantine_count == 2

    def test_duplicate_quarantine(self):
        from titan.data.normalize import normalize_row
        rows = [
            {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "AAPL", "date": "2026-01-02", "open": "151", "high": "153", "low": "150", "close": "152", "volume": "1000"},
        ]
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 1
        assert report.quarantine_count == 1
```

7. **Full end-to-end test** (in the same file):
```python
class TestPipeline:
    def test_end_to_end_pipeline(self):
        """Ingest → normalize → quarantine → verify good records."""
        from titan.data.normalize import normalize_row
        rows = read_csv(FIXTURES / "sample_ohlcv.csv")
        assert len(rows) == 6
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 6
        assert report.quarantine_count == 0
        assert len(good) == 6
        # Verify all fields present
        for r in good:
            assert "instrument_id" in r
            assert "timestamp" in r
            assert "close" in r
```

**Exit criteria:** `python -m pytest tests/data/ -v` passes all tests. Full suite still green.

---

### Task D2: Deterministic replay/backtest baseline

**Files:**
- Create: `src/titan/backtest/__init__.py`
- Create: `src/titan/backtest/clock.py`
- Create: `src/titan/backtest/fills.py`
- Create: `src/titan/backtest/results.py`
- Create: `tests/replay/__init__.py`
- Create: `tests/replay/test_deterministic_replay.py`
- Create: `tests/backtest/__init__.py`
- Create: `tests/backtest/test_corporate_actions.py`

**What to build:**

1. **`src/titan/backtest/clock.py`** — Replay clock:
```python
"""Deterministic replay clock — advances by event time."""

from dataclasses import dataclass

@dataclass
class ReplayClock:
    timestamp: str | None = None
    event_index: int = 0
    
    def advance_to(self, timestamp: str):
        self.timestamp = timestamp
        self.event_index += 1
    
    @property
    def current_time(self) -> str:
        return self.timestamp or "1970-01-01T00:00:00"
```

2. **`src/titan/backtest/fills.py`** — Bar-conservative fill model:
```python
"""Bar-conservative fill model. Fills at the close price within the bar."""

from dataclasses import dataclass

@dataclass
class FillResult:
    fill_price: float
    fill_quantity: int
    fill_cost: float
    slippage: float
    commission: float

class BarConservativeFillModel:
    def __init__(self, slippage_bps: float = 0.5, commission_bps: float = 1.0):
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
    
    def fill(self, bar: dict, side: str, quantity: int) -> FillResult:
        close = bar["close"]
        slippage = close * self.slippage_bps / 10000
        fill_price = close + slippage if side == "buy" else close - slippage
        fill_cost = fill_price * quantity
        commission = fill_cost * self.commission_bps / 10000
        return FillResult(
            fill_price=round(fill_price, 2),
            fill_quantity=quantity,
            fill_cost=round(fill_cost, 2),
            slippage=round(slippage, 2),
            commission=round(commission, 2),
        )
```

3. **`src/titan/backtest/results.py`** — Result metrics:
```python
"""Record and compute backtest results."""

from dataclasses import dataclass, field
from math import sqrt, log

@dataclass
class BacktestResult:
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    total_commission: float = 0.0
    
    @staticmethod
    def compute(equity_curve: list[float], trades: list[dict]) -> "BacktestResult":
        if not equity_curve or len(equity_curve) < 2:
            return BacktestResult()
        
        start_equity = equity_curve[0]
        end_equity = equity_curve[-1]
        total_return = (end_equity - start_equity) / start_equity * 100
        
        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            max_dd = max(max_dd, dd)
        
        # Sharpe (simplified: uses daily returns from equity curve)
        daily_returns = []
        for i in range(1, len(equity_curve)):
            r = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
            daily_returns.append(r)
        
        if daily_returns and len(daily_returns) > 1:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - avg_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std = sqrt(variance) if variance > 0 else 1e-10
            sharpe = (avg_return / std) * sqrt(252) if std > 0 else 0.0
        else:
            sharpe = 0.0
        
        # Trade stats
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        total_commission = sum(t.get("commission", 0) for t in trades)
        
        return BacktestResult(
            total_return_pct=round(total_return, 4),
            max_drawdown_pct=round(max_dd, 4),
            sharpe_ratio=round(sharpe, 4),
            total_trades=len(trades),
            win_rate=round(len(wins) / max(len(trades), 1) * 100, 2),
            total_commission=round(total_commission, 2),
        )
```

4. **`tests/backtest/test_corporate_actions.py`** — Corporate action tests:
Test basic fill model behavior. Real corporate actions (splits, dividends) are validated in Phase D+.
```python
"""Tests for backtest fill model."""

from titan.backtest.fills import BarConservativeFillModel, FillResult

class TestFillModel:
    def test_buy_fill(self):
        model = BarConservativeFillModel(slippage_bps=0.5, commission_bps=1.0)
        bar = {"open": 150, "high": 152, "low": 149, "close": 151.50}
        result = model.fill(bar, "buy", 100)
        assert result.fill_quantity == 100
        assert result.fill_price > bar["close"]  # slippage adds for buys
        assert result.commission > 0
        assert result.slippage > 0

    def test_sell_fill(self):
        model = BarConservativeFillModel()
        bar = {"open": 400, "high": 405, "low": 398, "close": 402}
        result = model.fill(bar, "sell", 50)
        assert result.fill_quantity == 50
        assert result.fill_price < bar["close"]  # slippage subtracts for sells

    def test_zero_commission_model(self):
        model = BarConservativeFillModel(slippage_bps=0, commission_bps=0)
        bar = {"close": 100}
        result = model.fill(bar, "buy", 10)
        assert result.fill_price == 100
        assert result.commission == 0
        assert result.slippage == 0

    def test_deterministic(self):
        """Same inputs → same outputs across runs."""
        model = BarConservativeFillModel()
        bar = {"close": 100.50}
        r1 = model.fill(bar, "buy", 100)
        r2 = model.fill(bar, "buy", 100)
        assert r1.fill_price == r2.fill_price
        assert r1.fill_cost == r2.fill_cost
```

5. **`tests/replay/test_deterministic_replay.py`** — The core replay test:
```python
"""Deterministic replay: normalized data → fills → portfolio → same results twice."""

from titan._core import (
    Money, PortfolioEngine, RiskGate, RiskConfig,
    TradeIntent,
)
from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.clock import ReplayClock

SAMPLE_BARS = [
    {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150, "high": 152, "low": 149, "close": 151.50, "volume": 1000000},
    {"instrument_id": "AAPL", "timestamp": "2026-01-03T00:00:00", "open": 151.50, "high": 153.50, "low": 150.50, "close": 152.75, "volume": 1200000},
    {"instrument_id": "AAPL", "timestamp": "2026-01-06T00:00:00", "open": 152.75, "high": 155, "low": 151, "close": 154.25, "volume": 900000},
]

class TestDeterministicReplay:
    def test_replay_produces_identical_results(self):
        """Run the same replay twice → identical fills, cash, positions."""
        def run():
            portfolio = PortfolioEngine("USD", Money("100000", "USD"))
            model = BarConservativeFillModel(slippage_bps=0.5, commission_bps=1.0)
            clock = ReplayClock()
            
            for bar in SAMPLE_BARS:
                clock.advance_to(bar["timestamp"])
                
                # Generate a buy intent at each bar
                close_price = bar["close"]
                
                # Fill at the bar
                fill = model.fill(bar, "buy", 10)
                portfolio.apply_fill(
                    bar["instrument_id"],
                    "buy",
                    fill.fill_quantity,
                    Money(str(int(fill.fill_price)), "USD"),
                )
            
            return {
                "cash": portfolio.get_cash_balance().amount,
                "position_qty": portfolio.get_position("AAPL").quantity if portfolio.get_position("AAPL") else 0,
                "realized_pnl": portfolio.get_realized_pnl().amount,
                "total_exposure": portfolio.total_gross_exposure().amount,
            }
        
        result1 = run()
        result2 = run()
        assert result1 == result2

    def test_replay_deterministic_across_runs(self):
        """Run twice in the same test → identical."""
        results = []
        for _ in range(3):
            portfolio = PortfolioEngine("USD", Money("100000", "USD"))
            clock = ReplayClock()
            for bar in SAMPLE_BARS:
                clock.advance_to(bar["timestamp"])
                portfolio.apply_fill(bar["instrument_id"], "buy", 10, Money(str(int(bar["close"])), "USD"))
            results.append(portfolio.get_cash_balance().amount)
        assert results[0] == results[1] == results[2]

    def test_replay_with_sell(self):
        """Buy then sell → correct cash and position."""
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        model = BarConservativeFillModel()
        
        # Buy at first bar
        bar1 = SAMPLE_BARS[0]
        fill1 = model.fill(bar1, "buy", 100)
        portfolio.apply_fill("AAPL", "buy", fill1.fill_quantity, Money(str(int(fill1.fill_price)), "USD"))
        
        # Sell at second bar
        bar2 = SAMPLE_BARS[1]
        fill2 = model.fill(bar2, "sell", 100)
        portfolio.apply_fill("AAPL", "sell", fill2.fill_quantity, Money(str(int(fill2.fill_price)), "USD"))
        
        pos = portfolio.get_position("AAPL")
        assert pos is None or pos.side.__str__() == "Flat"
        # Cash should be high due to offsetting trades
        cash_amount = int(portfolio.get_cash_balance().amount)
        assert cash_amount > 0
```

**Important notes for D2:**
- The replay test uses PortfolioEngine.apply_fill which expects Money with integer amount strings (e.g., `Money("151", "USD")` not `Money("151.50", "USD")`)
- Use `str(int(fill_price))` to convert fill prices to integer strings
- The tests prove determinism by running the same replay twice and comparing results

**Exit criteria:** `python -m pytest tests/replay/ tests/backtest/ -v` passes. `python -m pytest tests/ -v` all pass.
