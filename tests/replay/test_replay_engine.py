from dataclasses import dataclass
from titan.backtest.engine import ReplayEngine


SAMPLE_BARS = [
    {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00Z", "open": 150, "high": 152, "low": 149, "close": 151.50, "volume": 1000000},
    {"instrument_id": "AAPL", "timestamp": "2026-01-03T00:00:00Z", "open": 151.50, "high": 153.50, "low": 150.50, "close": 152.75, "volume": 1200000},
    {"instrument_id": "AAPL", "timestamp": "2026-01-06T00:00:00Z", "open": 152.75, "high": 155, "low": 151, "close": 154.25, "volume": 900000},
]


class _AlwaysBuy:
    def update(self, price: float) -> str | None:
        return "BUY"


class _AlwaysSell:
    def update(self, price: float) -> str | None:
        return "SELL"


class TestReplayEngine:
    def test_run_with_buy_strategy(self):
        engine = ReplayEngine(_AlwaysBuy(), SAMPLE_BARS)
        result = engine.run()
        assert result.bars_processed == len(SAMPLE_BARS)
        assert result.trades > 0
        assert float(result.final_cash) > 0

    def test_run_with_sell_strategy(self):
        engine = ReplayEngine(_AlwaysSell(), SAMPLE_BARS)
        result = engine.run()
        assert result.bars_processed == len(SAMPLE_BARS)

    def test_run_with_no_bars(self):
        engine = ReplayEngine(_AlwaysBuy(), [])
        result = engine.run()
        assert result.bars_processed == 0
        assert result.trades == 0
        assert result.final_cash == "0"

    def test_run_tracks_bar_results(self):
        engine = ReplayEngine(_AlwaysBuy(), SAMPLE_BARS)
        result = engine.run()
        assert len(result.bar_results) == len(SAMPLE_BARS)
        for br in result.bar_results:
            assert br.instrument_id == "AAPL"

    def test_replay_deterministic(self):
        results = []
        for _ in range(3):
            engine = ReplayEngine(_AlwaysBuy(), SAMPLE_BARS)
            results.append(engine.run().final_cash)
        assert results[0] == results[1] == results[2]

    def test_moving_average_strategy(self):
        from titan.strategies.moving_average import MovingAverageCrossover
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        # Build enough bars for the MA to produce signals
        bars = [
            {"instrument_id": "AAPL", "timestamp": f"2026-01-{i:02d}T00:00:00Z",
             "open": 100, "high": 101, "low": 99, "close": c, "volume": 1000000}
            for i, c in enumerate([100, 101, 99, 102, 105, 108, 107, 110, 112, 115], 1)
        ]
        engine = ReplayEngine(strat, bars)
        result = engine.run()
        assert result.bars_processed > 0
        assert float(result.final_cash) > 0
