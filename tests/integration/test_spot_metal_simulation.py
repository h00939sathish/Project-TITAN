"""Integration test: spot metal simulation boundary."""
from datetime import datetime, timezone

from titan._core import Money, ReconciliationConfig, RiskConfig, TradeIntent

from titan.data.spot_metals import spot_metal_instrument
from titan.execution import PaperConfig, PaperTradingEngine, SimulatedAdapter
from tests.fixtures.session_init import initialize_fresh


def test_engine_rejects_unregistered_xauusd():
    """Submitting an intent for XAUUSD without registering it is rejected."""
    risk = RiskConfig(
        [], Money("100000", "USD"), 100, 100,
        Money("1000000", "USD"), 0.10, Money("5000", "USD"), 5000, 60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(),
        currency="USD", starting_capital="100000", account_id="gold-test-1",
        state_path="",
    )
    engine = PaperTradingEngine(config, SimulatedAdapter())
    initialize_fresh(engine)
    engine.start()


    intent = TradeIntent(
        strategy_id="test", strategy_package_digest="v1",
        account_id="gold-test-1", instrument_id="XAUUSD",
        side="BUY", quantity="1", order_type="MARKET",
        time_in_force="DAY", risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    certificate_ref="test-cert",
    )
    result = engine.submit_intent(intent)
    assert not result.accepted
    assert "not registered" in result.rejection_reason.lower()


def test_xauusd_round_trip_with_simulated_adapter():
    """BUY 1 then SELL 1 XAUUSD through SimulatedAdapter works end to end."""
    inst = spot_metal_instrument("XAUUSD")
    assert inst is not None

    risk = RiskConfig(
        [], Money("100000", "USD"), 100, 100,
        Money("1000000", "USD"), 0.10, Money("5000", "USD"), 5000, 60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(),
        currency="USD", starting_capital="100000", account_id="gold-test-2",
        state_path="",
    )
    engine = PaperTradingEngine(config, SimulatedAdapter())
    engine.register_instrument(inst)
    initialize_fresh(engine)
    engine.start()
    engine._last_prices["XAUUSD"] = "2350.00"


    intent = TradeIntent(
        strategy_id="test", strategy_package_digest="v1",
        account_id="gold-test-2", instrument_id="XAUUSD",
        side="BUY", quantity="1", order_type="MARKET",
        time_in_force="DAY", risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    certificate_ref="test-cert",
    )
    result = engine.submit_intent(intent)
    assert result.accepted, f"Buy rejected: {result.rejection_reason}"
    assert result.fills

    # Close position
    intent2 = TradeIntent(
        strategy_id="test", strategy_package_digest="v1",
        account_id="gold-test-2", instrument_id="XAUUSD",
        side="SELL", quantity="1", order_type="MARKET",
        time_in_force="DAY", risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    certificate_ref="test-cert",
    )
    result2 = engine.submit_intent(intent2)
    assert result2.accepted, f"Sell rejected: {result2.rejection_reason}"

    pos = engine.portfolio.get_position("XAUUSD")
    assert pos is None or pos.quantity == 0, f"Expected flat, got qty={pos.quantity}"


def test_xauusd_backtest_round_trip_is_flat_and_reproducible():
    from scripts.backtest_spot_gold import run_spot_gold_backtest
    first = run_spot_gold_backtest()
    second = run_spot_gold_backtest()
    assert first["final_position"] == 0
    assert first == second
