### Task E1: Minimal versioned strategy package

**Files:**
- Create: `src/titan/strategies/__init__.py`
- Create: `src/titan/strategies/manifest.py`
- Create: `src/titan/strategies/runtime.py`
- Create: `src/titan/strategies/moving_average.py`
- Create: `tests/strategies/__init__.py`
- Create: `tests/strategies/test_moving_average_package.py`

**Full implementation is in the plan doc:**
D:\projects\Project TITAN\docs\superpowers\plans\2026-07-13-phase-e-strategy-and-paper.md

Read the "Task E1" section for complete code for every file.

**Key responsibilities:**

1. **`manifest.py`** — `StrategyManifest` frozen dataclass with `package_id`, `package_version`, `package_digest`, `data_requirements`, `parameter_schema`, `universe`, `risk_profile_version`, `expiry`, `fixture_refs`. Methods: `compute_digest()` (SHA-256 of identity + requirements + universe), `verify()` (checks stored digest matches computed).

2. **`runtime.py`** — `StrategyRuntime` class with `register(strategy_id, strategy, manifest)` and `emit_intent(strategy_id, instrument_id, side, ...) -> TradeIntent`. Rejects: unknown strategy, bad digest, instrument not in universe.

3. **`moving_average.py`** — `MovingAverageCrossover` with `fast_period`, `slow_period`, `update(close_price) -> str | None` (returns "BUY"/"SELL"/None). Pure calculation, no I/O.

4. **Tests** — manifest digest computation and verification, MA crossover signals (buy, sell, no signal), runtime registration and intent emission with rejection cases, and a strategy-driven replay test appended to `tests/replay/test_deterministic_replay.py`.

**Important notes:**
- `emit_intent()` calls `TradeIntent(strategy_id, package_digest, account_id, instrument_id, side, quantity, order_type, time_in_force, risk_profile_version, price=price, stop_price=stop_price)`
- TradeIntent takes `quantity: str` and `price: str | None`
- The strategy MUST NOT import broker, portfolio, risk, or execution modules

**Working dir:** D:\projects\Project TITAN
**Python:** `.venv\Scripts\python.exe`

**Exit:** `python -m pytest tests/strategies/ -v` passes. Full suite still green.
