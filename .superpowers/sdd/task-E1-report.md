# Task E1 Report — Minimal versioned strategy package

**Status:** DONE

**Changes made:**

| File | Action |
|---|---|
| `src/titan/strategies/__init__.py` | Created |
| `src/titan/strategies/manifest.py` | Created — frozen `StrategyManifest` dataclass with `compute_digest()`, `verify()` |
| `src/titan/strategies/runtime.py` | Created — `StrategyRuntime` with `register()`, `emit_intent()`, rejection logic |
| `src/titan/strategies/moving_average.py` | Created — `MovingAverageCrossover` pure-calculation strategy |
| `tests/strategies/__init__.py` | Created |
| `tests/strategies/test_moving_average_package.py` | Created — 12 tests (manifest, MA crossover, runtime) |
| `tests/replay/test_deterministic_replay.py` | Appended `TestStrategyDrivenReplay` class |

**Test data corrections (plan doc test data didn't produce intended crossovers):**
- BUY test: `[100, 101, 102, 103, 104, 105]` → `[100, 90, 80, 85, 90, 95]` (dip then rise)
- SELL test: `[105, 104, 103, 102, 101, 100]` → `[100, 90, 100, 110, 100, 90]` (rise then fall)
- No-signal test: `[100, 101, 100, 101, 100, 101]` → `[100, 100, 100, 100, 100, 100]` (flat)
- Replay test bars adjusted to produce a BUY at step 5
- Runtime test digest fixed: inner/outer manifest universes must match

**Test results:**

| Suite | Result |
|---|---|
| `tests/strategies/` | 12/12 passed |
| `tests/replay/` | 4/4 passed |
| Full suite (`tests/`) | 111/111 passed |
