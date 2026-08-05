"""Tests for research metrics and gates."""

from titan.research.gate import check_min_trades
from titan.research.metrics import (
    block_bootstrap,
    compute_cagr,
    compute_exposure,
    compute_turnover,
    identify_regimes,
)


class TestGate:
    def test_passes_with_enough_trades(self):
        result = check_min_trades(50, minimum=30)
        assert result.passed is True
        assert result.trade_count == 50

    def test_fails_with_few_trades(self):
        result = check_min_trades(5, minimum=30)
        assert result.passed is False

    def test_passes_with_override_doc(self):
        result = check_min_trades(5, minimum=30, override_doc="docs/low-turnover-reason.md")
        assert result.passed is True
        assert result.override_doc != ""

    def test_default_minimum(self):
        from titan.research.gate import MIN_OOS_TRADES_DEFAULT
        assert MIN_OOS_TRADES_DEFAULT == 30


class TestMetrics:
    def test_cagr_compounds_equity_over_multiple_periods(self):
        assert compute_cagr([100.0, 110.0, 121.0], periods_per_year=1) == 10.0

    def test_turnover_no_trades(self):
        result = compute_turnover([], 100_000)
        assert result["total_turnover_pct"] == 0.0

    def test_turnover_with_trades(self):
        trades = [
            {"side": "buy", "qty": 10, "price": 100.0, "commission": 0.0},
            {"side": "sell", "qty": 10, "price": 105.0, "commission": 0.0},
        ]
        result = compute_turnover(trades, 100_000)
        assert result["total_turnover_pct"] > 0

    def test_exposure_no_bars(self):
        result = compute_exposure([], [], [])
        assert result["time_in_market_pct"] == 0.0

    def test_block_bootstrap_few_trades(self):
        trades = [{"pnl": 100}, {"pnl": -50}]
        result = block_bootstrap(trades, n_simulations=10, block_size=2)
        assert "mean" in result

    def test_block_bootstrap_empty(self):
        result = block_bootstrap([], n_simulations=10)
        assert result["mean"] == 0.0

    def test_identify_regimes_short_series(self):
        bars = [{"close": 100.0} for _ in range(50)]
        regimes = identify_regimes(bars)
        assert len(regimes) == 50
        assert all(r["regime"] == "unknown" for r in regimes)

    def test_identify_regimes_long_series(self):
        bars = [{"close": 100.0 + i * 0.5} for i in range(500)]
        regimes = identify_regimes(bars)
        assert len(regimes) == 500
        # Most bars should be bull (rising prices)
        bull_count = sum(1 for r in regimes if r["regime"] == "bull")
        assert bull_count > 200
