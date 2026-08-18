"""Tests for Continuous Rolling / Expanding Walk-Forward Optimization (WFO) Engine."""

import pytest
from titan.research.walkforward import (
    WalkForwardConfig,
    WalkForwardOptimizer,
    WalkForwardWindow,
    generate_windows,
)
from titan.strategies.moving_average import MovingAverageCrossover


def _make_dummy_bars(n: int = 500) -> list[dict]:
    """Generates synthetic trend-and-reversal bar series for testing."""
    bars = []
    price = 100.0
    for i in range(n):
        # Create clear directional regimes
        if (i // 50) % 2 == 0:
            price += 1.0
        else:
            price -= 0.8
        bars.append({
            "timestamp": f"2026-01-01T{i:04d}",
            "open": price - 0.2,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000,
        })
    return bars


def _ma_factory(params: dict):
    strat = MovingAverageCrossover(
        fast_period=params.get("fast", 5),
        slow_period=params.get("slow", 20),
    )
    def signal_fn(bar):
        return strat.update(bar["close"])
    signal_fn.strat = strat
    return signal_fn


class TestWindowGeneration:
    def test_rolling_windows_count_and_indices(self):
        bars = _make_dummy_bars(300)
        config = WalkForwardConfig(train_size=100, test_size=50, step_size=50, window_type="rolling")
        windows = generate_windows(bars, config)

        assert len(windows) == 4  # (300 - 150) // 50 + 1 = 4
        assert windows[0].window_id == 0
        assert len(windows[0].train_bars) == 100
        assert len(windows[0].test_bars) == 50
        assert windows[1].train_bars[0] == bars[50]

    def test_expanding_windows(self):
        bars = _make_dummy_bars(300)
        config = WalkForwardConfig(train_size=100, test_size=50, step_size=50, window_type="expanding")
        windows = generate_windows(bars, config)

        assert len(windows) == 4
        assert len(windows[0].train_bars) == 100
        assert len(windows[1].train_bars) == 150
        assert len(windows[2].train_bars) == 200

    def test_insufficient_bars_raises_value_error(self):
        bars = _make_dummy_bars(50)
        config = WalkForwardConfig(train_size=100, test_size=50)
        with pytest.raises(ValueError, match="Insufficient bars"):
            generate_windows(bars, config)


class TestWalkForwardOptimizer:
    def test_optimize_window_selects_best_params(self):
        bars = _make_dummy_bars(200)
        optimizer = WalkForwardOptimizer()
        param_grid = {"fast": [3, 5], "slow": [15, 20]}

        best_params, best_result, score = optimizer.optimize_window(
            bars, _ma_factory, param_grid, target_metric="sharpe"
        )
        assert "fast" in best_params
        assert "slow" in best_params
        assert best_result is not None

    def test_full_walk_forward_run_produces_result_and_wfe(self):
        bars = _make_dummy_bars(400)
        config = WalkForwardConfig(
            train_size=100,
            test_size=50,
            step_size=50,
            window_type="rolling",
            param_grid={"fast": [3, 5], "slow": [15, 20]},
            target_metric="sharpe",
            min_wfe_threshold=0.30,
            min_trades=2,
        )

        optimizer = WalkForwardOptimizer()
        res = optimizer.run(bars, _ma_factory, config)

        assert len(res.step_results) == 6
        assert res.summary["num_windows"] == 6
        assert isinstance(res.wfe, float)
        assert len(res.stitched_oos_equity) > 0
        assert isinstance(res.passed_gate, bool)


def test_walk_forward_propagates_one_exact_cost_model_to_every_window():
    from titan.research.harness import walk_forward
    from titan.backtest.fx_costs import FxCostModel

    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="BAR_NEXT_OPEN")
    bars = [
        {"timestamp": f"2026-01-01T{i:04d}", "open": 100.0, "close": 100.0 + (i % 5)}
        for i in range(400)
    ]
    results = walk_forward(bars, {}, cost_model=cost_model)
    assert len(results) > 0
    assert {r.cost_model_digest for r in results} == {cost_model.digest()}


