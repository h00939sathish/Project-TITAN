# Task 1 Report: Derive simulated broker truth from filled orders

## What was implemented

Implemented `positions()` and `holdings()` on `SimulatedAdapter` to derive position and balance snapshots from filled order state rather than returning empty/hardcoded values.

- **`positions()`**: Aggregates all orders where `filled_quantity > 0`, nets buy/sell by instrument, emits `BrokerPosition` with `"LONG"` or `"SHORT"` side.
- **`holdings()`**: Starts cash at `Decimal("100000")`, subtracts `price * qty` for buys, adds for sells. Returns `BrokerBalanceSnapshot` with cash/portfolio_value/buying_power/equity all set to the computed cash.

## TDD Evidence

### RED (before implementation)
```
$ python -m pytest -q tests/adapters/test_simulated_adapter_contract.py::TestSimulatedAdapterContract::test_snapshots_reflect_filled_buy_and_sell
F
FAILED tests/adapters/test_simulated_adapter_contract.py::TestSimulatedAdapterContract::test_snapshots_reflect_filled_buy_and_sell
assert 0 == 1  (positions was empty)
```

### GREEN (after implementation)
```
$ python -m pytest -q tests/adapters/test_simulated_adapter_contract.py
12 passed
```

## Files changed

| File | Change |
|------|--------|
| `src/titan/execution/simulated_adapter.py` | Added `Decimal` import; implemented `positions()` with netting logic; implemented `holdings()` with cash arithmetic. |
| `tests/adapters/test_simulated_adapter_contract.py` | Added `test_snapshots_reflect_filled_buy_and_sell`. |

## Self-review findings

- **Edge case — zero filled orders**: Both methods correctly skip orders with `filled_quantity <= 0`, so an empty `_orders` dict returns empty positions and starting cash.
- **Rejects/timeouts/cancels**: These orders never get `filled_quantity > 0`, so they are correctly excluded from both aggregation and cash calculation.
- **Partial fills**: `PARTIAL_THEN_FULL` orders are considered based on `filled_quantity > 0` — already tested by existing tests.
- **LONG vs SHORT**: Net quantity per instrument: positive = LONG, negative = SHORT. Zero-quantity instruments are excluded.
- **Cash precision**: Uses `Decimal` for intermediate arithmetic, `str()` conversion for `Money` constructor — matches the contract's expected `"91200.00"` format.

## Concerns

None. All 12 existing tests pass; the new test asserts the correct derived values.
