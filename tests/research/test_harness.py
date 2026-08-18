"""Tests for validation-harness acceptance criteria."""

from titan.backtest.results import BacktestResult
from titan.research.gate import check_min_trades
from titan.research.harness import evaluate_success_criteria
from titan.research.hypothesis import Hypothesis


def _hypothesis_with_minimum_trade_criterion() -> Hypothesis:
    return Hypothesis(
        id="test-minimum-trades",
        title="Minimum-trades criterion",
        economic_rationale="Verify textual trade criteria remain enforceable.",
        strategy_id="volatility-regime",
        strategy_params={"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
        instrument="TEST",
        universe="TEST only",
        calendar="2020-01-01 to 2024-12-31",
        train_period="2020-01-01 to 2022-12-31",
        test_period="2023-01-01 to 2024-12-31",
        success_criteria=[
            "Sharpe > 0.3 OOS",
            "Max drawdown < benchmark max drawdown OOS",
            "Win rate > 40% OOS",
            "Minimum 30 OOS trades",
        ],
        failure_criteria=[],
        costs="1.0 bps commission, 0.5 bps slippage",
        expected_trade_frequency="At least 30 OOS trades",
        sample_adequacy_policy="Path A",
    )


def test_minimum_oos_trade_criterion_rejects_29_trades_when_gate_is_overridden():
    """The textual criterion remains enforced even when a gate is passed."""
    candidate = BacktestResult(
        sharpe_ratio=0.8,
        max_drawdown_pct=1.0,
        win_rate=60.0,
        total_trades=29,
    )
    benchmark = BacktestResult(max_drawdown_pct=2.0)

    assert evaluate_success_criteria(
        _hypothesis_with_minimum_trade_criterion(),
        candidate,
        benchmark,
        check_min_trades(29, override_doc="preregistered-path-b-evidence.md"),
    ) is False


def test_signal_from_bar_t_fills_no_earlier_than_bar_t_plus_1_open():
    from titan.backtest.fx_costs import FxCostModel
    from titan.research.harness import StrategyRunner

    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="BAR_NEXT_OPEN")
    runner = StrategyRunner(
        lambda bar: "BUY" if bar.get("timestamp") == "t0" else None,
        cost_model=cost_model,
    )
    bars = [
        {"timestamp": "t0", "open": 1.00, "close": 1.00},
        {"timestamp": "t1", "open": 1.10, "close": 1.15},
    ]
    _, trades = runner.run(bars)
    assert len(trades) == 1
    assert trades[0]["timestamp"] == "t1"
    assert trades[0]["price"] >= 1.10


def test_run_backtest_result_uses_the_supplied_model_not_defaults():
    from titan.backtest.fx_costs import FxCostModel
    from titan.research.harness import run_backtest_result

    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
    bars = [
        {
            "timestamp": f"t{i}",
            "open": 1.0 + i * 0.01,
            "close": 1.0 + i * 0.01,
            "ask": 1.0 + i * 0.01 + 0.0001,
            "bid": 1.0 + i * 0.01 - 0.0001,
        }
        for i in range(10)
    ]
    result = run_backtest_result(
        bars,
        {},
        signal_factory=lambda p: (lambda b: "BUY" if b["timestamp"] == "t1" else "SELL" if b["timestamp"] == "t5" else None),
        cost_model=cost_model,
    )
    assert result.cost_model_digest == cost_model.digest()


