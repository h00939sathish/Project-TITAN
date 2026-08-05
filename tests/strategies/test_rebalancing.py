"""Unit tests for Portfolio Rebalancing & Weight Target Engine."""

from datetime import datetime, timezone
import pytest

from titan.strategies.rebalancing import (
    RebalanceCalculator,
    RebalanceConfig,
    RebalanceIntent,
)


class TestRebalanceCalculator:
    def test_rebalance_from_cash_only(self):
        calc = RebalanceCalculator(RebalanceConfig(rebalance_threshold_pct=1.0, min_trade_notional=50.0))

        current_positions = {}
        current_prices = {"AAPL": 150.0, "MSFT": 300.0}
        target_weights = {"AAPL": 0.60, "MSFT": 0.40}
        cash = 10000.0  # $10,000 cash

        intents = calc.compute_rebalance_intents(current_positions, current_prices, target_weights, cash)
        assert len(intents) == 2

        aapl = next(i for i in intents if i.instrument_id == "AAPL")
        msft = next(i for i in intents if i.instrument_id == "MSFT")

        assert aapl.side == "BUY"
        assert msft.side == "BUY"
        assert aapl.quantity > 0
        assert msft.quantity > 0

    def test_drift_threshold_filtering(self):
        calc = RebalanceCalculator(RebalanceConfig(rebalance_threshold_pct=5.0))  # 5% threshold

        # Current portfolio equity: $10,000 (AAPL $5,200 = 52%, cash $4,800)
        current_positions = {"AAPL": 52}
        current_prices = {"AAPL": 100.0}
        target_weights = {"AAPL": 0.50}  # Target 50% (drift is 2%, below 5% threshold)
        cash = 4800.0

        intents = calc.compute_rebalance_intents(current_positions, current_prices, target_weights, cash)
        assert len(intents) == 0  # Ignored due to drift threshold

    def test_min_trade_notional_filtering(self):
        calc = RebalanceCalculator(RebalanceConfig(rebalance_threshold_pct=0.1, min_trade_notional=500.0, cash_buffer_pct=0.0))


        current_positions = {"AAPL": 100}
        current_prices = {"AAPL": 100.0}
        target_weights = {"AAPL": 0.995}  # Small diff under $500 notional
        cash = 0.0

        intents = calc.compute_rebalance_intents(current_positions, current_prices, target_weights, cash)
        assert len(intents) == 0

    def test_to_trade_intents_conversion(self):
        calc = RebalanceCalculator()
        rebalance_intents = [
            RebalanceIntent(
                instrument_id="AAPL",
                side="BUY",
                quantity=10,
                target_weight=0.5,
                current_weight=0.0,
                estimated_notional=1500.0,
            )
        ]
        prices = {"AAPL": 150.0}
        now_iso = datetime.now(timezone.utc).isoformat()

        trade_intents = calc.to_trade_intents(rebalance_intents, prices, now_iso)
        assert len(trade_intents) == 1
        ti = trade_intents[0]
        assert ti.instrument_id == "AAPL"
        assert ti.side == "BUY"
        assert ti.quantity == "10"
