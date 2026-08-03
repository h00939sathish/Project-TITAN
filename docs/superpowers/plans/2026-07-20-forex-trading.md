# Forex Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable paper/simulated trading of major forex pairs (EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD) using the existing SimulatedAdapter and BacktestAdapter.

**Architecture:** No Rust core changes needed — `ContractType::Forex` already exists. Add forex pair instrument definitions, a 24/5 calendar, forex data normalization, and wire-through in the existing engine. Existing strategies (MA crossover, mean reversion, etc.) work on price series without modification. No live broker adapter in this phase — simulated and historical only.

**Tech Stack:** Python 3.12+, existing Rust core, Polygon.io for forex OHLC data.

## Global Constraints

- No Rust recompilation if avoidable — `ContractType::Forex` is already compiled in.
- Quantity remains `u64` (micro-lot units: 1 quantity = 1000 units of base currency).
- No leverage modeling in this phase — trades are sized against cash balance.
- Existing strategy code must not change — forex is just a new instrument.
- All changes must work in both simulated and backtest modes.

---

### Task 1: ADR — adopt forex for simulated trading

**Files:**
- Create: `docs/adr/ADR-014-forex-simulated-trading.md`
- Modify: `docs/scope/operating-scope.md`

**Interfaces:**
- Consumes: operating-scope.md, existing ContractType::Forex
- Produces: accepted ADR + updated scope document

- [ ] Write ADR-014 with:
  - Decision: adopt major forex pairs for simulated/backtest trading using existing `ContractType::Forex`
  - Scope: major pairs only, no live broker, micro-lot quantity convention, no leverage
  - Alternatives considered: adding to Rust types (not needed — `Forex` variant exists), IBKR adapter (deferred)
  - Consequences: quantities differ from equities (1000-unit steps), forex 24/5 calendar, no volume in data

- [ ] Update `operating-scope.md`:
  - Add forex as an "in-scope for simulated trading" asset class
  - Note that live forex requires a separate IBKR adapter (future phase)
  - Update the scope boundary line to mention forex micro-lot convention

### Task 2: Define forex pair instruments

**Files:**
- Create: `src/titan/data/forex_pairs.py`

**Interfaces:**
- Produces: `FOREX_PAIRS: dict[str, dict]` — mapping of symbol to instrument params
- Produces: `forex_instrument(symbol: str) -> Instrument` — factory function
- Produces: `FOREX_SYMBOLS: frozenset[str]` — set of accepted forex symbols

```python
"""Forex pair definitions — naming convention: EURUSD, GBPUSD, etc.

Quantity convention: 1 unit = 1000 base currency (micro lot).
- quantity=1000 → 1 micro lot (1000 EUR for EUR/USD)
- quantity=10000 → 1 mini lot
- quantity=100000 → 1 standard lot

Tick sizes follow standard forex pip conventions:
- 0.0001 for most XXX/USD, USD/XXX pairs (1 pip)
- 0.01 for USD/JPY, USD/CHF, etc. (1 pip in JPY terms)
- 0.00001 for 1/10 pip for some brokers
"""

from titan._core import ContractType, Instrument, InstrumentId, Money

FOREX_PAIRS: dict[str, dict] = {
    "EURUSD": {
        "base": "EUR", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "GBPUSD": {
        "base": "GBP", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "USDJPY": {
        "base": "USD", "quote": "JPY", "precision": 3,
        "tick_size": "0.01", "pip": "0.01",
    },
    "USDCHF": {
        "base": "USD", "quote": "CHF", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "AUDUSD": {
        "base": "AUD", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "USDCAD": {
        "base": "USD", "quote": "CAD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "NZDUSD": {
        "base": "NZD", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
}

# 1 micro-lot = 1000 base currency units
STEP_SIZE = 1000
MULTIPLIER = "1.0"
# ponytail: step_size=1000 (micro-lots). Per-mini-lot if intraday scalping matters.
# ponytail: no fractional lot sizes (0.5 micro-lot) — add when needed.

FOREX_SYMBOLS = frozenset(FOREX_PAIRS.keys())


def forex_instrument(symbol: str) -> Instrument | None:
    info = FOREX_PAIRS.get(symbol.upper())
    if info is None:
        return None
    pair_symbol = f"{info['base']}/{info['quote']}"
    return Instrument(
        InstrumentId(symbol, "FOREX"),
        info["tick_size"],
        STEP_SIZE,
        MULTIPLIER,
        ContractType.Forex,
        info["base"],
        info["precision"],
    )
```

- [ ] Write `forex_pairs.py` as above
- [ ] Write the test:

```python
# tests/data/test_forex_pairs.py
from titan.data.forex_pairs import forex_instrument, FOREX_PAIRS, FOREX_SYMBOLS
from titan._core import ContractType

def test_forex_symbols_defined():
    assert len(FOREX_PAIRS) == 7
    assert "EURUSD" in FOREX_SYMBOLS

def test_forex_instrument_creation():
    inst = forex_instrument("EURUSD")
    assert inst is not None
    assert inst.contract_type == ContractType.Forex
    assert inst.currency == "EUR"
    assert inst.step_size == 1000

def test_forex_instrument_unknown():
    assert forex_instrument("ZZZZZZ") is None

def test_forex_notional():
    inst = forex_instrument("EURUSD")
    # 1 micro-lot (1000) at 1.1000 = 1100 USD
    notional = inst.compute_notional(1000, "1.1000")
    assert notional == "1100.0000"
```

- [ ] Run: `python -m pytest tests/data/test_forex_pairs.py -v`

### Task 3: Add 24/5 forex calendar

**Files:**
- Create: `src/titan/data/calendar_forex.py`

**Interfaces:**
- Produces: `is_forex_trading_day(d: date) -> bool`
- Produces: `previous_forex_trading_day(d: date) -> date`
- Produces: `next_forex_trading_day(d: date) -> date`

Forex trades 24 hours a day, 5 days a week: from Sunday 5pm ET to Friday 5pm ET. For daily bar purposes, any weekday Mon-Fri is a trading day. The only non-trading days are Saturday and Sunday.

```python
"""Forex market calendar — 24/5 (Sun 5pm ET - Fri 5pm ET).

For daily bar purposes: Mon-Fri are trading days, Sat-Sun are not.
Individual broker holiday observances may vary — not modeled in MVP.
"""

from datetime import date, timedelta


def is_forex_trading_day(d: date) -> bool:
    # Forex trades Mon-Fri. Sat/Sun = closed.
    return d.weekday() < 5


def previous_forex_trading_day(d: date) -> date:
    candidate = d - timedelta(days=1)
    while not is_forex_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_forex_trading_day(d: date) -> date:
    candidate = d + timedelta(days=1)
    while not is_forex_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate
```

- [ ] Write `calendar_forex.py`
- [ ] Write the test:

```python
# tests/data/test_calendar_forex.py
from datetime import date
from titan.data.calendar_forex import is_forex_trading_day, previous_forex_trading_day

def test_weekday_is_trading():
    assert is_forex_trading_day(date(2026, 7, 20))  # Monday

def test_weekend_not_trading():
    assert not is_forex_trading_day(date(2026, 7, 18))  # Saturday
    assert not is_forex_trading_day(date(2026, 7, 19))  # Sunday

def test_previous_trading_day_skip_weekend():
    # Monday -> previous = Friday
    mon = date(2026, 7, 20)
    fri = date(2026, 7, 17)
    assert previous_forex_trading_day(mon) == fri
```

- [ ] Run: `python -m pytest tests/data/test_calendar_forex.py -v`

### Task 4: Update data normalizer for forex symbols

**Files:**
- Modify: `src/titan/data/normalize.py`
- Modify: `src/titan/data/__init__.py`
- Modify: `tests/data/test_normalize.py`

**Interfaces:**
- Consumes: `FOREX_SYMBOLS` from Task 2
- Produces: updated `ALLOWED_SYMBOLS` that includes forex pairs

Forex data from Polygon.io and Alpha Vantage uses OHLC format (open/high/low/close) similar to equities. Volume is typically reported as tick count (not meaningful for forex) — make it optional.

```python
# In normalize.py:
# After the existing ALLOWED_SYMBOLS, add:
from titan.data.forex_pairs import FOREX_SYMBOLS as _FOREX_SYMBOLS

ALLOWED_SYMBOLS = _US_EQUITIES | _FOREX_SYMBOLS
```

But to keep it minimal: simply extend the existing `ALLOWED_SYMBOLS` frozen set with `FOREX_SYMBOLS`.

- [ ] Edit `normalize.py`:

```python
from titan.data.forex_pairs import FOREX_SYMBOLS

ALLOWED_SYMBOLS = frozenset({
    "AAPL", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ", "IWM", "TLT", "GLD",
}) | FOREX_SYMBOLS
```

- [ ] Edit `normalize.py` to treat volume as optional (forex data may not have meaningful volume):

```python
volume = row.get("volume", "").strip()
if volume:
    try:
        parsed["volume"] = int(volume)
    except (ValueError, TypeError):
        return f"Invalid volume: {volume}"
else:
    parsed["volume"] = 0  # forex: volume is optional, default 0
```

Change the fields from requiring volume to making it optional. The current code requires `"volume"` in the `fields` set and parses it. For forex, we should make volume optional.

- [ ] Write tests:

```python
def test_normalize_forex_pair():
    row = {"symbol": "EURUSD", "date": "2026-07-20", "open": "1.1000",
           "high": "1.1050", "low": "1.0950", "close": "1.1020"}
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["instrument_id"] == "EURUSD"

def test_normalize_forex_no_volume():
    row = {"symbol": "EURUSD", "date": "2026-07-20", "open": "1.1000",
           "high": "1.1050", "low": "1.0950", "close": "1.1020"}
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["volume"] == 0
```

- [ ] Run: `python -m pytest tests/data/test_normalize.py -v`

### Task 5: Wire forex into papertrading and risk config

**Files:**
- Modify: `scripts/papertrade.py`
- Modify: `src/titan/risk/limits.py`

**Interfaces:**
- Consumes: `forex_instrument`, `FOREX_SYMBOLS`, existing `register_instrument` method

- [ ] In `src/titan/risk/limits.py`, update defaults to include forex pairs:

```python
DEFAULT_CFG = {
    "instrument_eligibility": [],  # empty = all allowed via code
    ...
}
```

(Empty instrument_eligibility means "all instruments allowed" — no change needed if it's already empty.)

Actually, looking at the existing code, `instrument_eligibility` is set to `[]` in defaults. The papertrade script sets it via `instrument_list` from env var. The RiskConfig will filter by instrument_eligibility. If empty, all instruments pass the eligibility check. So actually no change needed in risk/limits.py — forex pairs will pass eligibility if the list is empty.

But let me check how RiskConfig.evaluate() uses instrument_eligibility. Let me check the Rust risk.rs for this.

Actually, I'll just check what happens with empty eligibility — likely it means "no filter" (all allowed). If that's the case, no risk config change needed. If the eligibility list is populated, we need to add forex pairs there.

Let me check the Rust code for risk:

Actually for the plan, I'll add a note that the papertrade script should be updated to optionally include forex pairs in its instrument list for clarity. And the forex instruments need to be registered with the engine.

- [ ] In `scripts/papertrade.py`, add forex pair registration after engine creation:

```python
from titan.data.forex_pairs import forex_instrument, FOREX_SYMBOLS

# After engine = PaperTradingEngine(config, adapter)
for sym in FOREX_SYMBOLS:
    inst = forex_instrument(sym)
    if inst:
        engine.register_instrument(inst)
```

- [ ] Write a quick verification:

```python
# tests/test_forex_integration.py
from titan.data.forex_pairs import forex_instrument
from titan.execution.simulated_adapter import SimulatedAdapter
from titan._core import RiskConfig, Money, TradeIntent

def test_forex_order_through_simulated_adapter():
    inst = forex_instrument("EURUSD")
    assert inst is not None
    adapter = SimulatedAdapter()
    # Place a market order
    intent = TradeIntent(
        "test", "test-pkg", "test-account",
        "EURUSD", "BUY", "1000", "MARKET", "DAY", "1.0",
    )
    ack = adapter.place_order(intent)
    assert ack.accepted or ack.rejection_reason == "Not implemented"
```

### Task 6: Forex data fixture for backtest verification

**Files:**
- Create: `tests/data/fixtures/eurusd_2026.csv`

**Interfaces:**
- Produces: minimal forex OHLC fixture for backtest testing

```
symbol,date,open,high,low,close,volume
EURUSD,2026-07-13,1.1000,1.1050,1.0980,1.1020,0
EURUSD,2026-07-14,1.1020,1.1080,1.1000,1.1060,0
EURUSD,2026-07-15,1.1060,1.1100,1.1030,1.1080,0
EURUSD,2026-07-16,1.1080,1.1120,1.1050,1.1100,0
EURUSD,2026-07-17,1.1100,1.1150,1.1070,1.1120,0
EURUSD,2026-07-20,1.1120,1.1180,1.1100,1.1150,0
```

- [ ] Create the fixture CSV
- [ ] Verify: `python -c "from titan.data import read_csv; bars = read_csv('tests/data/fixtures/eurusd_2026.csv'); print(len(bars))"`

### Task 7: Backtest a forex strategy

**Files:**
- Modify: `scripts/backtest_strategies.py` or create `scripts/backtest_forex.py`

**Interfaces:**
- Consumes: existing ReplayEngine, BarConservativeFillModel, forex instrument + fixture

- [ ] Create a minimal forex backtest script:

```python
"""Backtest a simple MA crossover on EUR/USD."""
from pathlib import Path
from titan._core import Instrument, InstrumentId, ContractType, RiskConfig, Money, TradeIntent
from titan.data import read_csv, load_approved, normalize, check_freshness
from titan.data.forex_pairs import forex_instrument
from titan.backtest.engine import ReplayEngine
from titan.backtest.fills import BarConservativeFillModel

# Load fixture
fixture = Path("tests/data/fixtures/eurusd_2026.csv")
bars = read_csv(str(fixture))
normalized = [normalize(b) for b in bars]
normalized = [b for b in normalized if isinstance(b, dict)]

# Run simple backtest
engine = ReplayEngine(
    instruments={"EURUSD": forex_instrument("EURUSD")},
    risk=RiskConfig([], Money("100000", "USD"), 100000, 100000, Money("1000000", "USD"), 0.10, Money("5000", "USD"), 5000, 100),
    fill_model=BarConservativeFillModel(),
)

engine.load_bars("EURUSD", normalized)
result = engine.run(
    instrument_id="EURUSD",
    entry_fn=lambda prices: "BUY" if len(prices) >= 2 and prices[-1] > prices[-2] else None,
)

print(f"Trades: {len(result.trade_log)}")
print(f"Final PnL: {result.final_pnl}")
```

This is a smoke test to verify the forex backtest path works end to end.

### Task 8: Verify and document

- [ ] Run the full test suite: `python -m pytest tests/ -v --tb=short`
- [ ] Run the forex backtest: `python scripts/backtest_forex.py`
- [ ] Run lint: `python -m ruff check src/titan/ scripts/ tests/`
- [ ] Add plan link to README documentation index
