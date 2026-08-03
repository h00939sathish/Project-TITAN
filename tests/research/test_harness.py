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
