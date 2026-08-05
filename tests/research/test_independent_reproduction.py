"""Independent reproduction: verify deterministic results and sensitivity."""

from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.results import BacktestResult

SAMPLE_BARS = [
    {"instrument_id": "SPY", "timestamp": "2020-01-02", "open": 322.0, "high": 324.0, "low": 320.0, "close": 323.0, "volume": 80_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-03", "open": 323.0, "high": 325.0, "low": 321.0, "close": 324.0, "volume": 75_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-06", "open": 324.0, "high": 327.0, "low": 322.0, "close": 326.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-07", "open": 326.0, "high": 328.0, "low": 324.0, "close": 327.0, "volume": 65_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-08", "open": 327.0, "high": 329.0, "low": 325.0, "close": 328.0, "volume": 68_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-09", "open": 328.0, "high": 330.0, "low": 326.0, "close": 329.0, "volume": 72_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-10", "open": 329.0, "high": 331.0, "low": 327.0, "close": 330.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-13", "open": 330.0, "high": 332.0, "low": 328.0, "close": 331.0, "volume": 68_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-14", "open": 331.0, "high": 333.0, "low": 329.0, "close": 332.0, "volume": 66_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-15", "open": 332.0, "high": 334.0, "low": 330.0, "close": 333.0, "volume": 64_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-16", "open": 333.0, "high": 335.0, "low": 331.0, "close": 334.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-17", "open": 334.0, "high": 336.0, "low": 332.0, "close": 335.0, "volume": 85_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-20", "open": 335.0, "high": 337.0, "low": 333.0, "close": 336.0, "volume": 60_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-21", "open": 336.0, "high": 338.0, "low": 334.0, "close": 337.0, "volume": 72_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-22", "open": 337.0, "high": 339.0, "low": 335.0, "close": 338.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-23", "open": 338.0, "high": 340.0, "low": 336.0, "close": 337.0, "volume": 65_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-24", "open": 337.0, "high": 339.0, "low": 335.0, "close": 336.0, "volume": 68_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-27", "open": 336.0, "high": 338.0, "low": 330.0, "close": 332.0, "volume": 90_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-28", "open": 332.0, "high": 335.0, "low": 331.0, "close": 334.0, "volume": 75_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-29", "open": 334.0, "high": 336.0, "low": 332.0, "close": 333.0, "volume": 65_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-30", "open": 333.0, "high": 335.0, "low": 331.0, "close": 334.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-01-31", "open": 334.0, "high": 336.0, "low": 330.0, "close": 331.0, "volume": 80_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-03", "open": 331.0, "high": 333.0, "low": 328.0, "close": 330.0, "volume": 78_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-04", "open": 330.0, "high": 334.0, "low": 329.0, "close": 333.0, "volume": 72_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-05", "open": 333.0, "high": 337.0, "low": 332.0, "close": 336.0, "volume": 75_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-06", "open": 336.0, "high": 338.0, "low": 334.0, "close": 337.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-07", "open": 337.0, "high": 338.0, "low": 334.0, "close": 335.0, "volume": 65_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-10", "open": 335.0, "high": 338.0, "low": 333.0, "close": 337.0, "volume": 65_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-11", "open": 337.0, "high": 339.0, "low": 336.0, "close": 338.0, "volume": 62_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-12", "open": 338.0, "high": 340.0, "low": 337.0, "close": 339.0, "volume": 68_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-13", "open": 339.0, "high": 340.0, "low": 336.0, "close": 337.0, "volume": 66_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-14", "open": 337.0, "high": 340.0, "low": 336.0, "close": 338.0, "volume": 60_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-17", "open": 338.0, "high": 340.0, "low": 336.0, "close": 339.0, "volume": 55_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-18", "open": 339.0, "high": 340.0, "low": 336.0, "close": 337.0, "volume": 62_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-19", "open": 338.0, "high": 340.0, "low": 337.0, "close": 339.0, "volume": 58_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-20", "open": 339.0, "high": 341.0, "low": 336.0, "close": 337.0, "volume": 70_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-21", "open": 337.0, "high": 339.0, "low": 334.0, "close": 335.0, "volume": 75_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-24", "open": 335.0, "high": 336.0, "low": 320.0, "close": 322.0, "volume": 180_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-25", "open": 322.0, "high": 326.0, "low": 316.0, "close": 318.0, "volume": 200_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-26", "open": 318.0, "high": 322.0, "low": 315.0, "close": 316.0, "volume": 190_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-27", "open": 316.0, "high": 320.0, "low": 310.0, "close": 311.0, "volume": 220_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-02-28", "open": 311.0, "high": 315.0, "low": 295.0, "close": 304.0, "volume": 300_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-03-02", "open": 304.0, "high": 315.0, "low": 302.0, "close": 314.0, "volume": 250_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-03-03", "open": 314.0, "high": 318.0, "low": 305.0, "close": 308.0, "volume": 240_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-03-04", "open": 308.0, "high": 315.0, "low": 306.0, "close": 313.0, "volume": 200_000_000},
    {"instrument_id": "SPY", "timestamp": "2020-03-05", "open": 313.0, "high": 315.0, "low": 305.0, "close": 307.0, "volume": 210_000_000},
]

INITIAL_CAPITAL = 100_000.0


def run_backtest(bars):
    strat = __import__("titan.strategies.moving_average", fromlist=["MovingAverageCrossover"]).MovingAverageCrossover(
        fast_period=5, slow_period=20
    )
    model = BarConservativeFillModel(slippage_bps=0.5, commission_bps=1.0)
    cash = INITIAL_CAPITAL
    position = 0.0
    position_cost = 0.0
    in_position = False
    equity_curve = [INITIAL_CAPITAL]
    trades = []
    for bar in bars:
        signal = strat.update(bar["close"])
        if signal == "BUY" and not in_position:
            fill = model.fill(bar, "buy", 10)
            cost = fill.fill_cost + fill.commission
            if cost <= cash:
                cash -= cost
                position = fill.fill_quantity
                position_cost = fill.fill_cost
                in_position = True
                trades.append({"pnl": 0.0, "commission": fill.commission, "side": "buy",
                               "price": fill.fill_price, "qty": fill.fill_quantity})
        elif signal == "SELL" and in_position:
            fill = model.fill(bar, "sell", int(position))
            proceeds = fill.fill_cost - fill.commission
            pnl = proceeds - position_cost
            cash += proceeds
            trades[-1]["pnl"] = pnl
            trades.append({"pnl": pnl, "commission": fill.commission, "side": "sell",
                           "price": fill.fill_price, "qty": fill.fill_quantity})
            position = 0.0
            in_position = False
        mtm = cash + (position * bar["close"]) if in_position else cash
        equity_curve.append(mtm)
    return BacktestResult.compute(equity_curve, trades)


class TestIndependentReproduction:
    def test_identical_inputs_identical_results(self):
        """Two runs with same data and parameters produce byte-identical results."""
        r1 = run_backtest(SAMPLE_BARS)
        r2 = run_backtest(SAMPLE_BARS)
        assert r1.total_return_pct == r2.total_return_pct
        assert r1.sharpe_ratio == r2.sharpe_ratio
        assert r1.max_drawdown_pct == r2.max_drawdown_pct
        assert r1.total_trades == r2.total_trades
        assert r1.win_rate == r2.win_rate

    def test_deterministic_across_three_runs(self):
        """Three sequential runs produce identical results."""
        results = [run_backtest(SAMPLE_BARS) for _ in range(3)]
        for i in range(1, 3):
            assert results[0].total_return_pct == results[i].total_return_pct
            assert results[0].sharpe_ratio == results[i].sharpe_ratio

    def test_shuffled_data_differs(self):
        """Reversing data order produces different results (sanity)."""
        r_normal = run_backtest(SAMPLE_BARS)
        r_reversed = run_backtest(list(reversed(SAMPLE_BARS)))
        # Reversed data changes the price sequence, so results must differ
        assert not (
            r_normal.total_return_pct == r_reversed.total_return_pct
            and r_normal.total_trades == r_reversed.total_trades
            and r_normal.sharpe_ratio == r_reversed.sharpe_ratio
        ), "Reversed data should produce different results"

    def test_different_parameters_different_results(self):
        """Different MA periods produce different results."""
        strat1 = __import__("titan.strategies.moving_average", fromlist=["MovingAverageCrossover"]).MovingAverageCrossover(
            fast_period=5, slow_period=20
        )
        strat2 = __import__("titan.strategies.moving_average", fromlist=["MovingAverageCrossover"]).MovingAverageCrossover(
            fast_period=10, slow_period=30
        )
        model = BarConservativeFillModel()

        def run_with_strat(strat):
            cash = INITIAL_CAPITAL
            pos = 0.0
            pos_cost = 0.0
            in_pos = False
            eq = [INITIAL_CAPITAL]
            trades = []
            for bar in SAMPLE_BARS:
                sig = strat.update(bar["close"])
                if sig == "BUY" and not in_pos:
                    fill = model.fill(bar, "buy", 10)
                    if fill.fill_cost + fill.commission <= cash:
                        cash -= fill.fill_cost + fill.commission
                        pos = fill.fill_quantity
                        pos_cost = fill.fill_cost
                        in_pos = True
                        trades.append({"pnl": 0.0, "commission": fill.commission})
                elif sig == "SELL" and in_pos:
                    fill = model.fill(bar, "sell", int(pos))
                    pnl = (fill.fill_cost - fill.commission) - pos_cost
                    trades[-1]["pnl"] = pnl
                    cash += fill.fill_cost - fill.commission
                    pos = 0.0
                    in_pos = False
                eq.append(cash + (pos * bar["close"]) if in_pos else cash)
            return BacktestResult.compute(eq, trades)

        r1 = run_with_strat(strat1)
        r2 = run_with_strat(strat2)
        assert r1.total_trades != r2.total_trades or r1.total_return_pct != r2.total_return_pct

    def test_enhanced_metrics_are_populated(self):
        """All BacktestResult fields are populated after compute()."""
        result = run_backtest(SAMPLE_BARS)
        assert hasattr(result, "volatility_annual_pct")
        assert hasattr(result, "hit_rate_pct")
        assert hasattr(result, "tail_loss_pct")
        assert hasattr(result, "avg_exposure_pct")
        assert hasattr(result, "capacity_proxy")
        assert hasattr(result, "calmar_ratio")
        assert hasattr(result, "profit_factor")
