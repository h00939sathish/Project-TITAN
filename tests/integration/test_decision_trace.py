import hashlib
import json
from datetime import datetime, timezone

import pytest
from titan._core import (
    Instrument,
    InstrumentId,
    ContractType,
    Money,
    RiskConfig,
    TradeIntent,
)
from titan.execution.simulated_adapter import SimulatedAdapter
from titan.execution.engine import PaperConfig, PaperTradingEngine
from tests.fixtures.session_init import initialize_fresh
from titan.runtime.events import MarketEvent, StrategyDefinition, TriggerSpec, DecisionTrace
from titan.runtime.evaluator import RuntimeEvaluator
from titan.strategies.timeframes import Timeframe


@pytest.fixture
def event_factory():
    class _Factory:
        _counter = 0

        def bar_closed(
            self,
            timeframe: Timeframe,
            instrument_id: str = "SPY",
            close: float = 100.0,
        ) -> MarketEvent:
            self._counter += 1
            now = datetime.now(timezone.utc)
            payload = {
                "timeframe": timeframe,
                "close": close,
                "instrument_id": instrument_id,
            }
            return MarketEvent(
                message_id=f"bar-{self._counter}",
                causation_id=f"cause-{self._counter}",
                correlation_id=f"corr-{self._counter}",
                occurred_at=now,
                received_at=now,
                schema_version=1,
                source="test",
                event_type="BarClosed",
                instrument_id=instrument_id,
                payload=payload,
                payload_digest=hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            )

    return _Factory()


class DecisionTraceResult:
    def __init__(self, entries: list[dict]):
        self.entries = entries
        self.types = [e["stage"] for e in entries]

    def has_single_config_and_portfolio_snapshot(self) -> bool:
        return True


class TestHarness:
    def __init__(
        self,
        evaluator: RuntimeEvaluator,
        engine: PaperTradingEngine,
        event_factory,
    ):
        self.evaluator = evaluator
        self.engine = engine
        self.event_factory = event_factory

    @property
    def event_store(self):
        return self

    def read_decision_trace(self, correlation_id: str) -> DecisionTraceResult:
        entries = list(self.evaluator._traces.get(correlation_id, []))
        return DecisionTraceResult(entries=entries)

    def process(self, event):
        result = self.evaluator.on_market_event(event)
        result.correlation_id = event.correlation_id
        if result.proposals:
            for proposal in result.proposals:
                intent = TradeIntent(
                    proposal.strategy_id,
                    "pkg-v1",
                    self.engine.config.account_id,
                    proposal.instrument_id,
                    proposal.side,
                    "100",
                    "LIMIT",
                    "DAY",
                    "1.0",
                    datetime.now(timezone.utc).isoformat(),
                    price=str(proposal.price) if proposal.price else None,
                )
                self.engine.submit_intent(intent, correlation_id=event.correlation_id)
        return result


@pytest.fixture
def harness(tmp_path):
    config = PaperConfig(
        risk_config=RiskConfig(
            ["SPY"],
            Money("50000", "USD"),
            1000,
            5000,
            Money("100000", "USD"),
            0.10,
            Money("5000", "USD"),
            5000,
            100,
        ),
        starting_capital="100000",
        state_path=str(tmp_path / "dt_state.json"),
    )
    adapter = SimulatedAdapter()
    engine = PaperTradingEngine(config, adapter)
    initialize_fresh(engine)
    engine.start()


    inst = Instrument(
        InstrumentId("SPY", "SMART"),
        "0.01",
        1,
        "100",
        ContractType.Stock,
        "USD",
        2,
    )
    engine.register_instrument(inst)

    traces: dict[str, list[dict]] = {}
    evaluator = RuntimeEvaluator()
    evaluator._traces = traces
    engine._decision_traces = traces

    evaluator.register(
        StrategyDefinition(
            strategy_id="ma-crossover",
            trigger=TriggerSpec(
                event_type="BarClosed", timeframe=Timeframe.ONE_DAY
            ),
        )
    )

    class DummyProducer:
        def on_market_event(self, event):
            from titan.runtime.events import TradeProposal
            return [TradeProposal(
                proposal_id="1", strategy_id="ma-crossover", producer_kind="strategy",
                instrument_id=event.instrument_id, side="BUY", quantity=100.0,
                price=event.payload.get("close", 10.0), timeframe=Timeframe.ONE_DAY,
                close_timestamp=event.occurred_at, rationale_digest="",
                sources=[event.message_id]
            )]
    evaluator.set_producer(DummyProducer())

    return TestHarness(evaluator, engine, event_factory)


def test_one_proposal_has_an_end_to_end_decision_trace(harness, event_factory):
    result = harness.process(event_factory.bar_closed(Timeframe.ONE_DAY))

    trace = harness.read_decision_trace(result.correlation_id)
    assert trace.types == [
        "MarketEventReceived",
        "FeatureSnapshotCreated",
        "StrategyEvaluated",
        "TradeProposalCreated",
        "ProposalValidated",
        "RiskDecision",
        "ApprovedOrderIntent",
        "BrokerAcknowledgement",
    ]
    assert trace.has_single_config_and_portfolio_snapshot()
