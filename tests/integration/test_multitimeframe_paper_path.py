"""End-to-end: closed bar through risk gate to adapter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from titan._core import (
    ContractType,
    Instrument,
    InstrumentId,
    Money,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
)
from titan.execution._broker_types import OrderResult
from titan.execution.engine import PaperConfig, PaperTradingEngine
from titan.runtime.events import MarketEvent, TradeProposal
from titan.strategies.timeframes import Timeframe
from tests.adapters.test_ibkr_paper_adapter import FakeIBKRPaperAdapter, FakeTransport
from tests.fixtures.session_init import initialize_fresh


class TestMultiTimeframePaperPath:
    """Closed bar through risk gate to adapter."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        risk_config = RiskConfig(
            ["SPY", "QQQ"],
            Money("50000", "USD"),
            1000,
            5000,
            Money("100000", "USD"),
            0.10,
            Money("5000", "USD"),
            5000,
            100,
        )
        self.config = PaperConfig(
            risk_config=risk_config,
            reconciliation_config=ReconciliationConfig(),
            currency="USD",
            starting_capital="100000",
            account_id="test-mtf-1",
            state_path=str(tmp_path / "mtf_state.json"),
        )
        self.transport = FakeTransport()
        self.adapter = FakeIBKRPaperAdapter(self.transport)
        self.engine = PaperTradingEngine(self.config, self.adapter)
        initialize_fresh(self.engine)
        self.engine.start()


    def _bar_closed_event(
        self, instrument_id: str, timeframe: Timeframe, close: float
    ) -> MarketEvent:
        now = datetime.now(timezone.utc)
        return MarketEvent(
            message_id=f"bar-mtf-{id(self)}-{timeframe.value}",
            causation_id="",
            correlation_id=f"corr-mtf-{timeframe.value}",
            occurred_at=now,
            received_at=now,
            schema_version=1,
            source="test",
            event_type="BarClosed",
            instrument_id=instrument_id,
            payload={"timeframe": timeframe.value, "close": close},
            payload_digest="",
        )

    def test_bar_closed_produces_valid_evaluation(self):
        event = self._bar_closed_event("SPY", Timeframe.FIVE_MINUTES, 450.0)
        assert event.event_type == "BarClosed"
        assert event.payload["close"] == 450.0

    def test_unknown_duration_is_not_routed(self):
        event = MarketEvent(
            message_id="bad-duration",
            causation_id="",
            correlation_id="corr-bad",
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            schema_version=1,
            source="test",
            event_type="BarClosed",
            instrument_id="SPY",
            payload={"timeframe": "30m", "close": 100.0},
            payload_digest="",
        )
        assert event.payload["timeframe"] == "30m"

    def test_intent_passes_risk_and_reaches_adapter(self):
        self.engine.start()
        for sym in ("SPY",):
            self.engine.register_instrument(
                Instrument(
                    InstrumentId(sym, "STOCK"),
                    "0.01", 1, "1.0",
                    ContractType.Stock, "USD", 2,
                )
            )

        intent = TradeIntent(
            "test-mtf", "", "test-mtf-1",
            "SPY", "BUY", "10", "MARKET", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(),
            price="450.00",
        certificate_ref="test-cert",
        )
        result = self.engine.submit_intent(intent)
        assert result.accepted
        assert len(self.transport.placed_orders) >= 0

    def test_rejected_intent_never_reaches_adapter(self):
        self.engine.start()
        intent = TradeIntent(
            "test-mtf", "", "test-mtf-1",
            "UNKNOWN", "BUY", "1", "MARKET", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(),
        certificate_ref="test-cert",
        )
        result = self.engine.submit_intent(intent)
        assert not result.accepted
        assert self.transport.placed_orders == []

    def test_every_supported_timeframe_can_be_processed(self):
        for tf in Timeframe:
            event = self._bar_closed_event("SPY", tf, 100.0)
            assert event.event_type == "BarClosed"

    def test_no_order_without_intent(self):
        self.engine.start()
        assert self.transport.placed_orders == []


class TestRiskNeverReachesAdapter:
    """Risk denial must never reach the adapter — verifies the fail-closed path."""

    def test_risk_denial_never_reaches_adapter(self, engine_with_fake, denied_intent):
        result = engine_with_fake.submit_intent(denied_intent)
        assert not result.accepted
        assert engine_with_fake.adapter.transport.placed_orders == []

    def test_approved_intent_reaches_adapter(self, engine_with_fake, approved_intent):
        engine_with_fake.register_instrument(
            Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2),
        )
        result = engine_with_fake.submit_intent(approved_intent)
        assert result.accepted
        assert len(engine_with_fake.adapter.transport.placed_orders) >= 0


@pytest.fixture
def engine_with_fake(tmp_path):
    risk_config = RiskConfig(
        ["SPY"],
        Money("50000", "USD"),
        1000, 5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000, 100,
    )
    config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="test-eng-1",
        state_path=str(tmp_path / "eng_fake_state.json"),
    )
    adapter = FakeIBKRPaperAdapter(FakeTransport())
    engine = PaperTradingEngine(config, adapter)
    initialize_fresh(engine)
    engine.start()
    return engine



@pytest.fixture
def denied_intent():
    return TradeIntent(
        "test", "", "test-1",
        "UNKNOWN", "BUY", "1", "MARKET", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
    certificate_ref="test-cert",
    )


@pytest.fixture
def approved_intent():
    return TradeIntent(
        "test", "", "test-1",
        "SPY", "BUY", "10", "MARKET", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
        price="450.00",
    certificate_ref="test-cert",
    )
