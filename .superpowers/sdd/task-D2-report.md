# Task D2 — Deterministic Replay/Backtest Baseline: Report

**Status:** DONE

**Test summary:** 87/87 passed — all suite tests green, including 7 new replay/backtest tests.

## Created files

| File | Purpose |
|---|---|
| `src/titan/backtest/__init__.py` | Package init |
| `src/titan/backtest/clock.py` | `ReplayClock` — deterministic event-time clock |
| `src/titan/backtest/fills.py` | `BarConservativeFillModel` + `FillResult` — slippage/commission fills |
| `src/titan/backtest/results.py` | `BacktestResult` — return, drawdown, sharpe, win rate, commission |
| `tests/replay/__init__.py` | Package init |
| `tests/replay/test_deterministic_replay.py` | 3 tests: identical replay, deterministic across runs, buy/sell cycle |
| `tests/backtest/__init__.py` | Package init |
| `tests/backtest/test_corporate_actions.py` | 4 tests: buy fill, sell fill, zero commission, deterministic fill |

## Verification

- `python -m pytest tests/replay/ tests/backtest/ -v` → **7 passed**
- `python -m pytest tests/ -v` → **87 passed**

## Key design notes

- `Money` constructed with `str(int(price))` to match Rust `_core` i64 parsing (no decimal strings).
- Fill model is bar-conservative: fills at close ± slippage, commission deducted.
- `BacktestResult.compute()` uses sample-variance Sharpe with `sqrt(252)` annualization.
- Replay tests prove byte-identical results across multiple runs with same inputs.
