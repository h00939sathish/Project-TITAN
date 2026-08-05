# XAUUSD Spot Gold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `XAUUSD` as a USD-quoted spot-gold instrument for deterministic simulated and backtest research only.

**Architecture:** Gold is a spot-metal instrument, not a forex pair. The Rust core receives an explicit `Commodity` contract type; Python supplies the XAUUSD instrument definition and a 24/5 daily-bar calendar. The execution engine must require instrument registration, and the Alpaca paper CLI must not offer this instrument, preserving the no-broker boundary.

**Tech Stack:** Rust/PyO3 core, Python 3.12+, pytest, ruff.

## Global Constraints

- `XAUUSD` means one troy ounce of spot gold quoted in USD; `quantity=1` is one ounce and `step_size=1`.
- Price precision and tick size are `0.01` USD per troy ounce for this simulation contract.
- Simulation and backtest only; no live or Alpaca-paper routing.
- USD cash/PnL accounting is permitted only because the quote currency is USD; cross-currency forex accounting remains out of scope.
- No leverage, no financing/rollover, and no short opening; a sell may only reduce a long position.
- The specification and ADR must be accepted by the Architecture Council and Risk Owner before implementation begins.

---

### Task 1: Define and approve the spot-metal boundary

**Files:**
- Create: `specifications/SpotMetal.spec.md`
- Create: `docs/adr/ADR-015-xauusd-simulated-spot-gold.md`
- Modify: `specifications/README.md`

**Interfaces:**
- Consumes: `specifications/Money.spec.md`, `specifications/Portfolio.spec.md`, `specifications/Risk.spec.md`, `docs/adr/ADR-014-forex-simulated-trading.md`
- Produces: the accepted XAUUSD contract, failure behavior, metrics, rollback, and approval record required before code changes

- [ ] **Step 1: Write the specification as Proposed**

Specify `XAUUSD` as a `Commodity` contract whose unit is one troy ounce, quote currency is USD, tick is `0.01`, and quantity step is `1`. Define the only legal environments as simulated adapter and backtest adapter. Require rejection when an instrument is unregistered, an adapter does not declare commodity support, an opening sell is attempted, data is stale, or a price is not tick-aligned. Define metrics `spot_metal.intents_total`, `spot_metal.rejections_total`, and `spot_metal.positions_ounces`; require a reject/alert on an unavailable session calendar or price.

- [ ] **Step 2: Write ADR-015 as Proposed**

Record the decision to use a new `ContractType::Commodity` rather than `Forex` or `Stock`; the USD quote-currency limitation; the simulation-only adapter boundary; a licensed/approved data-source requirement; deterministic fixture/backtest evidence; rollback by removing registration and blocking commodity intents; and retirement if a live adapter or margin/financing model is introduced.

- [ ] **Step 3: Obtain approval before production code**

Required approval: Architecture Council and Risk Owner. Change both documents from `Proposed` to `Accepted` only after the accountable approvers authorize the stated scope.

### Task 2: Extend the typed core contract

**Files:**
- Modify: `core/src/types.rs`
- Modify: `core/src/lib.rs` only if the PyO3 export requires it
- Test: `tests/data/test_spot_metals.py`

**Interfaces:**
- Consumes: approved `SpotMetal.spec.md`
- Produces: `ContractType.Commodity` exposed through `titan._core`

- [ ] **Step 1: Write the failing Python binding test**

```python
from titan._core import ContractType


def test_commodity_contract_type_is_exposed():
    assert str(ContractType.Commodity) == "Commodity"
```

- [ ] **Step 2: Verify the test fails because the variant is absent**

Run: `python -m pytest tests/data/test_spot_metals.py::test_commodity_contract_type_is_exposed -q`

Expected: failure naming the missing `Commodity` attribute.

- [ ] **Step 3: Add the minimal Rust enum variant**

Add `Commodity` to `ContractType` in `core/src/types.rs`. Do not change order, portfolio, or risk calculations in this task.

- [ ] **Step 4: Verify the binding test and core tests pass**

Run: `python -m pytest tests/data/test_spot_metals.py::test_commodity_contract_type_is_exposed -q; cargo test --manifest-path core/Cargo.toml`

Expected: the Python test and all Rust core tests pass.

### Task 3: Add the XAUUSD instrument and normalization contract

**Files:**
- Create: `src/titan/data/spot_metals.py`
- Modify: `src/titan/data/normalize.py`
- Modify: `src/titan/data/__init__.py`
- Test: `tests/data/test_spot_metals.py`
- Test: `tests/data/test_normalize.py`

**Interfaces:**
- Produces: `SPOT_METAL_SYMBOLS: frozenset[str]` containing `"XAUUSD"` and `spot_metal_instrument(symbol: str) -> Instrument | None`

- [ ] **Step 1: Write failing instrument tests**

```python
from titan._core import ContractType
from titan.data.spot_metals import SPOT_METAL_SYMBOLS, spot_metal_instrument


def test_xauusd_instrument_uses_the_simulation_contract():
    instrument = spot_metal_instrument("xauusd")
    assert instrument is not None
    assert str(instrument.instrument_id) == "XAUUSD.SPOT"
    assert instrument.contract_type == ContractType.Commodity
    assert instrument.currency == "USD"
    assert instrument.step_size == 1
    assert instrument.is_price_aligned("2350.01")
    assert not instrument.is_price_aligned("2350.001")


def test_spot_metal_factory_rejects_unknown_symbol():
    assert spot_metal_instrument("XAGUSD") is None
```

- [ ] **Step 2: Verify the tests fail because the module is absent**

Run: `python -m pytest tests/data/test_spot_metals.py -q`

Expected: import failure for `titan.data.spot_metals`.

- [ ] **Step 3: Implement only the defined instrument factory**

Create `spot_metals.py` with `SPOT_METALS = {"XAUUSD": {"base": "XAU", "quote": "USD", "precision": 2, "tick_size": "0.01"}}`, `SPOT_METAL_SYMBOLS`, and the factory. Use `InstrumentId("XAUUSD", "SPOT")`, `step_size=1`, `multiplier="1.0"`, `ContractType.Commodity`, and currency `"USD"`. Canonicalize the returned symbol with `symbol.upper()`.

- [ ] **Step 4: Add the failing normalizer acceptance test**

```python
def test_normalize_xauusd_without_volume():
    result = normalize_row({
        "symbol": "XAUUSD", "date": "2026-07-20",
        "open": "2348.00", "high": "2355.00",
        "low": "2345.00", "close": "2350.25",
    })
    assert result["instrument_id"] == "XAUUSD"
    assert result["volume"] == 0
```

- [ ] **Step 5: Verify the normalizer test fails as an unknown symbol**

Run: `python -m pytest tests/data/test_normalize.py::test_normalize_xauusd_without_volume -q`

Expected: assertion failure because `normalize_row` returns `"Unknown symbol: XAUUSD"`.

- [ ] **Step 6: Add XAUUSD to the canonical allowed-symbol set and exports**

Union `SPOT_METAL_SYMBOLS` into `ALLOWED_SYMBOLS` and export the factory/constants from `titan.data`. Do not make volume optional for all symbols; retain the current normalizer behavior of defaulting an absent volume to zero and document it as unavailable volume rather than traded volume.

- [ ] **Step 7: Verify data tests pass**

Run: `python -m pytest tests/data/test_spot_metals.py tests/data/test_normalize.py -q`

Expected: all selected data tests pass.

### Task 4: Add a spot-gold daily-bar calendar

**Files:**
- Create: `src/titan/data/calendar_spot_metals.py`
- Test: `tests/data/test_calendar_spot_metals.py`

**Interfaces:**
- Produces: `is_spot_metal_trading_day(d: date) -> bool`, `previous_spot_metal_trading_day(d: date) -> date`, `next_spot_metal_trading_day(d: date) -> date`

- [ ] **Step 1: Write failing weekend-boundary tests**

```python
from datetime import date
from titan.data.calendar_spot_metals import (
    is_spot_metal_trading_day,
    next_spot_metal_trading_day,
)


def test_spot_gold_daily_bars_trade_on_weekdays():
    assert is_spot_metal_trading_day(date(2026, 7, 20))
    assert not is_spot_metal_trading_day(date(2026, 7, 18))


def test_next_spot_gold_trading_day_skips_the_weekend():
    assert next_spot_metal_trading_day(date(2026, 7, 17)) == date(2026, 7, 20)
```

- [ ] **Step 2: Verify the calendar tests fail because the module is absent**

Run: `python -m pytest tests/data/test_calendar_spot_metals.py -q`

Expected: import failure for `titan.data.calendar_spot_metals`.

- [ ] **Step 3: Implement the daily-bar calendar**

Implement weekday-only daily-bar helpers, explicitly documenting that intraday Sunday-open, Friday-close, daily maintenance breaks, and venue holidays are not modeled and therefore intraday trading is unsupported.

- [ ] **Step 4: Verify the calendar tests pass**

Run: `python -m pytest tests/data/test_calendar_spot_metals.py -q`

Expected: all tests pass.

### Task 5: Enforce the simulation-only execution boundary

**Files:**
- Modify: `src/titan/execution/engine.py`
- Modify: `scripts/papertrade.py`
- Test: `tests/adapters/test_instrument_validation.py`
- Test: `tests/integration/test_spot_metal_simulation.py`

**Interfaces:**
- Consumes: registered instrument map and the simulated/backtest adapter types
- Produces: a reasoned rejection before any adapter call for an unknown instrument or commodity instrument routed through `AlpacaAdapter`

- [ ] **Step 1: Write the failing unknown-instrument rejection test**

```python
def test_engine_rejects_unregistered_instrument_before_adapter_routing(engine, intent):
    result = engine.submit_intent(intent(instrument_id="XAUUSD", quantity="1"))
    assert not result.accepted
    assert result.rejection_reason == "Instrument is not registered: XAUUSD"
```

- [ ] **Step 2: Verify the test fails because routing currently permits an unregistered ID**

Run: `python -m pytest tests/adapters/test_instrument_validation.py::test_engine_rejects_unregistered_instrument_before_adapter_routing -q`

Expected: assertion failure showing that the intent passed the registration check.

- [ ] **Step 3: Require a registered instrument in `submit_intent`**

Reject when `self.instruments.get(str(intent.instrument_id))` is missing. Retain the existing tick/step validation for registered instruments.

- [ ] **Step 4: Write the failing Alpaca-boundary and simulation-round-trip tests**

```python
def test_alpaca_paper_cli_never_registers_xauusd(monkeypatch):
    monkeypatch.setenv("PAPER_FOREX_ENABLED", "true")
    engine = _build_engine_for_test_with_fake_alpaca_credentials()
    assert "XAUUSD" not in engine.instruments


def test_xauusd_round_trip_uses_only_simulated_adapter(tmp_path):
    engine = make_simulated_engine(state_path=tmp_path / "state.json")
    engine.register_instrument(spot_metal_instrument("XAUUSD"))
    # submit BUY 1 then SELL 1 with fresh USD prices
    assert engine.portfolio.get_position("XAUUSD").quantity == 0
```

- [ ] **Step 5: Verify the tests fail for the missing registration enforcement and missing gold implementation**

Run: `python -m pytest tests/adapters/test_instrument_validation.py tests/integration/test_spot_metal_simulation.py -q`

Expected: the new assertions fail before the implementation is added.

- [ ] **Step 6: Implement the boundary**

Do not add `XAUUSD` to `scripts/papertrade.py`; that CLI always constructs `AlpacaAdapter`. Create the integration test’s `PaperTradingEngine` directly with `SimulatedAdapter` and an isolated `state_path`. Add an explicit commodity rejection in `AlpacaAdapter` at the earliest contract-aware boundary when adapter capabilities are added; until then, the required-registration check and absence of registration in the CLI prevent routing.

- [ ] **Step 7: Verify the execution-boundary tests pass**

Run: `python -m pytest tests/adapters/test_instrument_validation.py tests/integration/test_spot_metal_simulation.py -q`

Expected: all selected tests pass and no test calls a networked broker.

### Task 6: Create deterministic backtest evidence and documentation

**Files:**
- Create: `tests/data/fixtures/xauusd_2026.csv`
- Create: `scripts/backtest_spot_gold.py`
- Modify: `docs/scope/operating-scope.md`
- Modify: `README.md`

**Interfaces:**
- Produces: deterministic XAUUSD round-trip output with zero final position and USD-denominated PnL

- [ ] **Step 1: Write a failing deterministic backtest test**

```python
def test_xauusd_backtest_round_trip_is_flat_and_reproducible(tmp_path):
    first = run_spot_gold_backtest(state_path=tmp_path / "first.json")
    second = run_spot_gold_backtest(state_path=tmp_path / "second.json")
    assert first["final_position"] == 0
    assert first == second
```

- [ ] **Step 2: Verify the test fails because the backtest entry point is absent**

Run: `python -m pytest tests/integration/test_spot_metal_simulation.py::test_xauusd_backtest_round_trip_is_flat_and_reproducible -q`

Expected: import failure for `run_spot_gold_backtest`.

- [ ] **Step 3: Implement an isolated backtest script and fixture**

Use a six-bar weekday fixture with `XAUUSD` prices, a `BacktestAdapter`, a `PaperConfig` with the supplied `state_path`, and a BUY-then-SELL sequence of one ounce. Return `trades`, `rejected`, `final_cash`, and `final_position`; never write to the repository’s default `.titan_state.json`.

- [ ] **Step 4: Update scope and README**

Add a spot-gold boundary: `XAUUSD` only, deterministic simulation/backtest only, USD quote currency, one-ounce steps, no leverage/financing/short opening, daily weekday bars, and no Alpaca or live execution. Link ADR-015, `SpotMetal.spec.md`, and the backtest command.

- [ ] **Step 5: Verify repeatability**

Run: `python -m pytest tests/integration/test_spot_metal_simulation.py -q; python scripts/backtest_spot_gold.py; python scripts/backtest_spot_gold.py`

Expected: integration tests pass; both script runs report two accepted trades, zero final position, and identical final cash.

### Task 7: Run required verification

**Files:**
- Verify only

- [ ] **Step 1: Run affected and full Python suites**

Run: `python -m pytest tests/data tests/adapters tests/integration -q`

Expected: zero failures.

- [ ] **Step 2: Run Rust and lint checks**

Run: `cargo test --manifest-path core/Cargo.toml; python -m ruff check src/titan scripts tests`

Expected: zero failures and zero lint diagnostics.

- [ ] **Step 3: Record acceptance evidence**

Attach the exact command output, fixture checksum, code revision, and approved ADR/spec references to the task record. Do not promote the feature to paper/live trading.

## Self-review

- Spec coverage: tasks 1–7 cover contract typing, data, calendar, execution boundary, deterministic validation, rollback, monitoring, and documentation.
- Placeholder scan: none.
- Type consistency: the plan uses `ContractType.Commodity`, `spot_metal_instrument`, `SPOT_METAL_SYMBOLS`, and `run_spot_gold_backtest` consistently.
