"""Integration test: forex trading through SimulatedAdapter."""

from datetime import datetime, timezone

from titan._core import ContractType, Money, ReconciliationConfig, RiskConfig, TradeIntent

from titan.data.forex_pairs import FOREX_SYMBOLS, forex_instrument
from titan.execution import PaperConfig, PaperTradingEngine, SimulatedAdapter


def test_forex_instrument_registration():
    """All USD-quote forex pairs produce valid instruments (gold = 1 oz step)."""
    for sym in FOREX_SYMBOLS:
        inst = forex_instrument(sym)
        assert inst is not None, f"Failed to create instrument for {sym}"
        expected_step = 1 if sym == "XAUUSD" else 1000
        assert inst.step_size == expected_step, f"{sym} step_size != {expected_step}"
        assert inst.contract_type == ContractType.Forex, f"{sym} contract_type != Forex"


def test_forex_market_order_through_engine():
    """Submit a EUR/USD market order through SimulatedAdapter + engine."""
    inst = forex_instrument("EURUSD")
    assert inst is not None

    risk = RiskConfig(
        [],  # empty = all instruments eligible
        Money("100000", "USD"),
        100000,
        100000,
        Money("1000000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(
            critical_drift_fraction=0.05,
            warning_drift_fraction=0.01,
        ),
        currency="USD",
        starting_capital="100000",
        account_id="forex-test-1",
        state_path="",
    )

    engine = PaperTradingEngine(config, SimulatedAdapter())
    engine.register_instrument(inst)

    # Register a price so risk checks pass
    engine._last_prices["EURUSD"] = "1.1000"

    intent = TradeIntent(
        strategy_id="test",
        strategy_package_digest="test-pkg",
        account_id="forex-test-1",
        instrument_id="EURUSD",
        side="BUY",
        quantity="1000",
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    result = engine.submit_intent(intent)
    assert result.accepted, f"Order rejected: {result.rejection_reason}"
    assert result.fills, "Expected at least one fill"
    assert len(result.fills) >= 1
    fill = result.fills[0]
    assert fill.instrument_id == "EURUSD"
    assert fill.side.upper() == "BUY"
