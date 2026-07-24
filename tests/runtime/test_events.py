from datetime import datetime, timezone

import pytest

from titan.runtime.events import (
    DecisionTrace,
    EvaluationResult,
    MarketEvent,
    ProposalValidation,
    StrategyDefinition,
    TradeProposal,
    TriggerSpec,
)
from titan.strategies.timeframes import Timeframe


def test_event_ordering():
    t1 = datetime(2026, 7, 24, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 7, 24, 10, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 7, 24, 9, 55, 0, tzinfo=timezone.utc)

    def make(ts: datetime) -> MarketEvent:
        return MarketEvent(
            message_id=f"msg-{ts.timestamp()}",
            causation_id="c1",
            correlation_id="c1",
            occurred_at=ts,
            received_at=ts,
            schema_version=1,
            source="test",
            event_type="BarClosed",
            instrument_id="SPY",
            payload={"timeframe": Timeframe.ONE_DAY, "close": 100.0},
            payload_digest="dummy",
        )

    e1, e2, e3 = make(t1), make(t2), make(t3)
    events = [e1, e2, e3]
    sorted_events = sorted(events, key=lambda e: e.occurred_at)
    assert sorted_events[0].occurred_at == t3
    assert sorted_events[1].occurred_at == t1
    assert sorted_events[2].occurred_at == t2


def test_duplicate_message_rejection(evaluator, event_factory):
    event = event_factory.bar_closed(Timeframe.FIVE_MINUTES)
    definition = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES),
    )
    evaluator.register(definition)
    result1 = evaluator.on_market_event(event)
    assert len(result1.proposals) > 0
    result2 = evaluator.on_market_event(event)
    assert result2.proposals == []


def test_malformed_schema_handling(evaluator):
    now = datetime.now(timezone.utc)
    bad_event = MarketEvent(
        message_id="bad-1",
        causation_id="c1",
        correlation_id="c1",
        occurred_at=now,
        received_at=now,
        schema_version=1,
        source="test",
        event_type="UnknownType",
        instrument_id="SPY",
        payload={},
        payload_digest="",
    )
    result = evaluator.on_market_event(bad_event)
    assert result.proposals == []


def test_advisory_proposal_event_creation():
    now = datetime.now(timezone.utc)
    event = MarketEvent(
        message_id="prop-1",
        causation_id="cause-1",
        correlation_id="corr-1",
        occurred_at=now,
        received_at=now,
        schema_version=1,
        source="ai-advisor",
        event_type="AdvisoryProposal",
        instrument_id="SPY",
        payload={"proposal_id": "p1", "side": "BUY", "quantity": 100},
        payload_digest="abc",
    )
    assert event.event_type == "AdvisoryProposal"
    assert event.payload["proposal_id"] == "p1"


def test_bar_closed_event_creation():
    now = datetime.now(timezone.utc)
    event = MarketEvent(
        message_id="bar-1",
        causation_id="cause-1",
        correlation_id="corr-1",
        occurred_at=now,
        received_at=now,
        schema_version=1,
        source="test",
        event_type="BarClosed",
        instrument_id="SPY",
        payload={"timeframe": Timeframe.FIVE_MINUTES, "close": 100.5},
        payload_digest="abc",
    )
    assert event.event_type == "BarClosed"
    assert event.payload["timeframe"] == Timeframe.FIVE_MINUTES


def test_trade_proposal_creation():
    now = datetime.now(timezone.utc)
    proposal = TradeProposal(
        proposal_id="tp-1",
        strategy_id="ma-crossover",
        producer_kind="strategy",
        instrument_id="SPY",
        side="BUY",
        quantity=100.0,
        price=100.5,
        timeframe=Timeframe.FIVE_MINUTES,
        close_timestamp=now,
        rationale_digest="abc123",
        sources=["bar-1"],
    )
    assert proposal.side == "BUY"
    assert proposal.timeframe == Timeframe.FIVE_MINUTES


def test_decision_trace_append():
    trace = DecisionTrace()
    trace.entries.append({"stage": "market_event_received", "message_id": "m1"})
    trace.entries.append({"stage": "strategy_evaluated", "strategy_id": "ma-crossover"})
    assert len(trace.entries) == 2
    assert trace.entries[0]["stage"] == "market_event_received"


def test_strategy_definition_context_defaults():
    spec = TriggerSpec(event_type="BarClosed", timeframe=Timeframe.ONE_DAY)
    definition = StrategyDefinition(
        strategy_id="test",
        trigger=spec,
    )
    assert definition.context == ()


def test_trigger_spec_mismatch(evaluator, event_factory):
    definition = StrategyDefinition(
        strategy_id="hourly-only",
        trigger=TriggerSpec(event_type="BarClosed", timeframe=Timeframe.ONE_HOUR),
    )
    evaluator.register(definition)
    result = evaluator.on_market_event(
        event_factory.bar_closed(Timeframe.FIVE_MINUTES)
    )
    assert result.proposals == []
    assert evaluator.evaluations == []
