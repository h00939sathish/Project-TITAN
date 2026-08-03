from titan._core import (
    Instrument, InstrumentId, ContractType, Money, RiskConfig, TradeIntent,
)
from titan.execution.engine import PaperConfig, PaperTradingEngine
from titan.execution.simulated_adapter import SimulatedAdapter
from datetime import datetime, timezone


def _config() -> PaperConfig:
    risk_config = RiskConfig(
        ["ES"],
        Money("50000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
    )
    return PaperConfig(risk_config=risk_config, state_path="")


def _intent(side="BUY", quantity="1", price="1500.00") -> TradeIntent:
    return TradeIntent(
        "test", "", "test-1", "ES", side, quantity, "LIMIT", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(), price=price,
    )


class TestInstrumentValidation:
    def test_valid_order_passes_validation(self):
        engine = PaperTradingEngine(_config(), SimulatedAdapter())
        instr = Instrument(InstrumentId("ES", "CME"), "0.25", 1, "50", ContractType.Future, "USD", 2)
        engine.register_instrument(instr, "ES")
        engine.start()
        result = engine.submit_intent(_intent("BUY", "1", "1500.00"))
        assert result.accepted

    def test_bad_tick_rejected(self):
        engine = PaperTradingEngine(_config(), SimulatedAdapter())
        instr = Instrument(InstrumentId("ES", "CME"), "0.25", 1, "50", ContractType.Future, "USD", 2)
        engine.register_instrument(instr, "ES")
        engine.start()
        result = engine.submit_intent(_intent("BUY", "1", "1500.10"))
        assert not result.accepted
        assert "tick" in result.rejection_reason

    def test_bad_lot_rejected(self):
        engine = PaperTradingEngine(_config(), SimulatedAdapter())
        instr = Instrument(InstrumentId("ES", "CME"), "0.25", 100, "50", ContractType.Future, "USD", 2)
        engine.register_instrument(instr, "ES")
        engine.start()
        result = engine.submit_intent(_intent("BUY", "55", "1500.00"))
        assert not result.accepted
        assert "step" in result.rejection_reason

    def test_unregistered_instrument_rejected(self):
        engine = PaperTradingEngine(_config(), SimulatedAdapter())
        engine.start()
        result = engine.submit_intent(_intent("BUY", "1", "1500.00"))
        assert not result.accepted
        assert "not registered" in result.rejection_reason
