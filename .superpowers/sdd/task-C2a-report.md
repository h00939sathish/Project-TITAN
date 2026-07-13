# Task C2a Report: Rust Portfolio Projection

**Status:** DONE

## Summary

Implemented the `portfolio` module with position lifecycle tracking, cash management, PnL tracking, and snapshot generation.

## What Was Implemented

### Types
- **`PositionSide`** — enum (`Flat`, `Long`, `Short`) with PyO3 `eq_int`
- **`Position`** — struct with `instrument_id`, `side`, `quantity`, `cost_basis`
- **`PortfolioSnapshot`** — struct with `gross_exposure`, `drawdown_fraction`, `daily_realized_loss`, `position_size`
- **`PortfolioEngine`** — main engine with `positions: HashMap<String, Position>`, `cash_balance`, `base_currency`, `realized_pnl`

### Methods
- `new(base_currency, initial_cash)` — constructor
- `apply_fill(instrument_id, side, quantity, price)` — full position lifecycle (Long/Short/Flat transitions, weighted avg cost basis, PnL realization)
- `get_position(instrument_id)` — query single position
- `get_cash_balance()` / `get_realized_pnl()` — balance queries
- `get_unrealized_pnl(instrument_id, current_price)` — mark-to-market
- `total_gross_exposure()` — sum of position values
- `get_snapshot()` — current state snapshot

### Position Lifecycle Covered
- Flat → Long (buy fill)
- Flat → Short (sell fill)
- Long → Long (add to position, weighted avg cost)
- Long → Flat (sell to zero)
- Long → Short (sell exceeds position)
- Short → Short (add to short)
- Short → Flat (cover to zero)
- Short → Long (cover exceeds position)

## TDD Evidence

### RED Phase
Wrote 22 tests covering all lifecycle transitions, error cases, and edge cases before full implementation:

| Test | Status |
|---|---|
| `test_buy_open_long` | ✅ |
| `test_sell_open_short` | ✅ |
| `test_buy_add_to_long` | ✅ |
| `test_sell_reduce_long_to_flat` | ✅ |
| `test_sell_reduce_long_to_short` | ✅ (initially failed — PnL computed on full sell qty instead of position size; fixed) |
| `test_buy_reduce_short_to_flat` | ✅ |
| `test_buy_reduce_short_to_long` | ✅ (initially failed — same PnL bug as above; fixed) |
| `test_cash_balance_updates` | ✅ |
| `test_realized_pnl` | ✅ |
| `test_gross_exposure` | ✅ |
| `test_get_position_not_found` | ✅ |
| `test_get_snapshot` | ✅ |
| `test_unrealized_pnl_long` | ✅ |
| `test_unrealized_pnl_short` | ✅ |
| `test_unrealized_pnl_no_position_returns_error` | ✅ |
| `test_invalid_side_returns_error` | ✅ |
| `test_zero_quantity_returns_error` | ✅ |
| `test_multiple_instruments_tracked_independently` | ✅ |

### GREEN Phase
- Fixed PnL calculation on cross-through fills (was using `quantity` instead of `quantity.min(pos.quantity)`)
- Fixed `Default` derive on `PortfolioSnapshot` (Money doesn't impl Default)
- Fixed `PyErr::new` for PyO3 0.29's two-generic-param API
- Added `from_py_object` to suppress PyO3 deprecation warnings
- Fixed pre-existing duplicate `set_trading_state` in risk.rs (auto-generated setter via `#[pyo3(get, set)]` conflicted with manual method)

## Files Changed

| File | Change |
|---|---|
| `core/src/portfolio.rs` | **Created** — 444 lines: types, engine, tests |
| `core/src/lib.rs` | **Modified** — added `mod portfolio` and 4 class registrations |
| `core/src/risk.rs` | **Modified** — removed `set` from `#[pyo3(get, set)]` on `trading_state` to fix duplicate setter |

## Test Results

```
test result: ok. 54 passed; 0 failed
```

All 54 tests pass: 22 portfolio + 12 orders + 20 risk.

## Clippy

Clean for portfolio.rs. 6 pre-existing warnings in risk.rs (collapsible_if, redundant_closure).

## Python Smoke Test

```python
import titan._core as c
e = c.PortfolioEngine('USD', c.Money('100000', 'USD'))
e.apply_fill('AAPL', 'buy', 100, c.Money('50', 'USD'))
p = e.get_position('AAPL')
# Position: Long 100 @ 50 USD
# Cash: 95000 USD
```

## Self-Review Findings

1. **Per-unit cost basis** — `cost_basis` stores per-unit average price, not total cost. Weighted average formula `(old_cost * old_qty + new_price * new_qty) / (old_qty + new_qty)` works correctly with this interpretation.
2. **Integer division** — Weighted average uses integer division (truncation). Acceptable for MVP per brief.
3. **PnL on cross-through fills** — Initial bug where PnL was computed on the full fill quantity instead of being capped at the existing position size. Fixed with `quantity.min(pos.quantity)`.
4. **Money parsing** — `parse_amount` uses `parse::<i64>().expect(...)` which panics on invalid strings. Safe for internal usage with validated input.
5. **Gross exposure** — Uses cost basis as proxy price since current market prices aren't tracked in the engine.
6. **PortfolioSnapshot.position_size** — Set to `positions.len()` (number of tracked instruments) since `get_snapshot()` takes no parameters. The spec note "for the instrument being checked" indicates future parameterization.

## Issues

- RiskGate in risk.rs had a pre-existing duplicate `set_trading_state` (auto-generated `#[pyo3(set)]` vs manual method). Fixed by removing `set` from the field attribute. The manual method provides validation via `TradingState::transition`.
- PyO3 0.29 API changes: `PyErr::new<T>` → `PyErr::new<T, A>`, and new `from_py_object`/`skip_from_py_object` requirement.
