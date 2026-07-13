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

**What to implement (exact code in the plan doc):**

Read: D:\projects\Project TITAN\docs\superpowers\plans\2026-07-13-phase-d-data-and-replay.md
The "Task D2" section has complete code for every file.

**Key points:**

1. **`src/titan/backtest/clock.py`** — `ReplayClock` dataclass with `timestamp`, `event_index`, `advance_to(timestamp)`, `current_time` property

2. **`src/titan/backtest/fills.py`** — `FillResult` dataclass, `BarConservativeFillModel` class with `fill(bar, side, quantity)`:
   - Buy: fill_price = close + slippage (close * slippage_bps / 10000)
   - Sell: fill_price = close - slippage
   - commission = fill_cost * commission_bps / 10000
   - Round to 2 decimal places

3. **`src/titan/backtest/results.py`** — `BacktestResult` dataclass with `compute(equity_curve, trades)` static method:
   - total_return, max_drawdown, sharpe (annualized, daily returns * sqrt(252)), win_rate, total_commission

4. **`tests/backtest/test_corporate_actions.py`** — Fill model tests:
   - Buy fill has slippage added
   - Sell fill has slippage subtracted
   - Zero commission model
   - Deterministic: same inputs → same outputs

5. **`tests/replay/test_deterministic_replay.py`** — Core replay tests:
   - Uses `PortfolioEngine` from Rust core
   - Uses `BarConservativeFillModel` from fills
   - 3 test bars for AAPL
   - `test_replay_produces_identical_results` — run twice, compare cash/position/pnl/exposure
   - `test_replay_deterministic_across_runs` — 3 runs produce same cash
   - `test_replay_with_sell` — buy then sell, verify flat position and cash > 0

**Important for Money compatibility:**
- PortfolioEngine.apply_fill() expects Money with integer amount strings
- Use `Money(str(int(fill_price)), "USD")` to avoid decimal strings
- Default fill amounts: use `close` rounded to int for the price string

**Exit:** `python -m pytest tests/replay/ tests/backtest/ -v` passes. `python -m pytest tests/ -v` all pass.

Working dir: D:\projects\Project TITAN
Python: `.venv\Scripts\python.exe`
