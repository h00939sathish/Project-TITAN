"""Deterministic replay: normalized data → fills → portfolio → same results twice."""

from titan._core import (
    Money, PortfolioEngine,
)
from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.clock import ReplayClock

SAMPLE_BARS = [
    {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150, "high": 152, "low": 149, "close": 151.50, "volume": 1000000},
    {"instrument_id": "AAPL", "timestamp": "2026-01-03T00:00:00", "open": 151.50, "high": 153.50, "low": 150.50, "close": 152.75, "volume": 1200000},
    {"instrument_id": "AAPL", "timestamp": "2026-01-06T00:00:00", "open": 152.75, "high": 155, "low": 151, "close": 154.25, "volume": 900000},
]


class TestDeterministicReplay:
    def test_replay_produces_identical_results(self):
        """Run the same replay twice → identical fills, cash, positions."""
        def run():
            portfolio = PortfolioEngine("USD", Money("100000", "USD"))
            model = BarConservativeFillModel(slippage_bps=0.5, commission_bps=1.0)
            clock = ReplayClock()

            for bar in SAMPLE_BARS:
                clock.advance_to(bar["timestamp"])

                # Fill at the bar
                fill = model.fill(bar, "buy", 10)
                portfolio.apply_fill(
                    bar["instrument_id"],
                    "buy",
                    fill.fill_quantity,
                    Money(str(int(fill.fill_price)), "USD"),
                )

            return {
                "cash": portfolio.get_cash_balance().amount,
                "position_qty": portfolio.get_position("AAPL").quantity if portfolio.get_position("AAPL") else 0,
                "realized_pnl": portfolio.get_realized_pnl().amount,
                "total_exposure": portfolio.total_gross_exposure().amount,
            }

        result1 = run()
        result2 = run()
        assert result1 == result2

    def test_replay_deterministic_across_runs(self):
        """Run twice in the same test → identical."""
        results = []
        for _ in range(3):
            portfolio = PortfolioEngine("USD", Money("100000", "USD"))
            clock = ReplayClock()
            for bar in SAMPLE_BARS:
                clock.advance_to(bar["timestamp"])
                portfolio.apply_fill(bar["instrument_id"], "buy", 10, Money(str(int(bar["close"])), "USD"))
            results.append(portfolio.get_cash_balance().amount)
        assert results[0] == results[1] == results[2]

    def test_replay_with_sell(self):
        """Buy then sell → correct cash and position."""
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        model = BarConservativeFillModel()

        # Buy at first bar
        bar1 = SAMPLE_BARS[0]
        fill1 = model.fill(bar1, "buy", 100)
        portfolio.apply_fill("AAPL", "buy", fill1.fill_quantity, Money(str(int(fill1.fill_price)), "USD"))

        # Sell at second bar
        bar2 = SAMPLE_BARS[1]
        fill2 = model.fill(bar2, "sell", 100)
        portfolio.apply_fill("AAPL", "sell", fill2.fill_quantity, Money(str(int(fill2.fill_price)), "USD"))

        pos = portfolio.get_position("AAPL")
        assert pos is None or pos.side.__str__() == "Flat"
        # Cash should be high due to offsetting trades
        cash_amount = int(portfolio.get_cash_balance().amount)
        assert cash_amount > 0


class TestStrategyDrivenReplay:
    def test_ma_strategy_drives_replay(self):
        from datetime import datetime, timezone
        from titan.strategies.moving_average import MovingAverageCrossover
        from titan._core import (
            PortfolioEngine, Money, RiskGate, RiskConfig, TradeIntent,
        )

        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        config = RiskConfig([], Money("1000000", "USD"), 1000, 5000,
                            Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000, 100)
        gate = RiskGate(config)
        now = datetime.now(timezone.utc).isoformat()

        bars = [
            {"close": 100}, {"close": 101}, {"close": 99},
            {"close": 102}, {"close": 105}, {"close": 108},
        ]
        trades = 0
        for bar in bars:
            signal = strat.update(bar["close"])
            if signal:
                intent = TradeIntent(
                    strategy_id="ma-test",
                    strategy_package_digest="",
                    account_id="paper-1",
                    instrument_id="AAPL",
                    side=signal,
                    quantity="10",
                    order_type="LIMIT",
                    time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp=now,
                    price=str(int(bar["close"])),
                )
                verdict = gate.evaluate(intent, None, None, None, None, None)
                if verdict.accepted:
                    portfolio.apply_fill("AAPL", signal.lower(), 10,
                                         Money(str(int(bar["close"])), "USD"))
                    trades += 1

        assert trades > 0
        pos = portfolio.get_position("AAPL")
        cash = int(portfolio.get_cash_balance().amount)
        assert cash > 0


def test_identical_inputs_produce_identical_cost_attribution_and_digest():
    from titan.backtest.fx_costs import FxCostModel
    from titan.research.harness import run_backtest_result, make_ma_signal_fn

    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
    bars = [
        {
            "timestamp": f"2026-01-01T{i:04d}",
            "open": 1.1000 + i * 0.0005,
            "high": 1.1010 + i * 0.0005,
            "low": 1.0990 + i * 0.0005,
            "close": 1.1000 + i * 0.0005,
            "ask": 1.1001 + i * 0.0005,
            "bid": 1.0999 + i * 0.0005,
        }
        for i in range(50)
    ]
    params = {"fast": 3, "slow": 10}

    first = run_backtest_result(bars, params, make_ma_signal_fn, cost_model=cost_model)
    second = run_backtest_result(bars, params, make_ma_signal_fn, cost_model=cost_model)

    assert first.evidence_artifact is not None
    assert first.evidence_artifact == second.evidence_artifact
    assert first.cost_model_digest == second.cost_model_digest

