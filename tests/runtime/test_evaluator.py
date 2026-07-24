from titan.runtime.events import (
    StrategyDefinition,
    TriggerSpec,
)
from titan.strategies.timeframes import Timeframe


def test_only_declared_five_minute_bar_triggers_a_strategy(evaluator, event_factory):
    definition = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(
            event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES
        ),
        context=(Timeframe.ONE_HOUR, Timeframe.ONE_DAY),
    )
    evaluator.register(definition)
    evaluator.on_market_event(event_factory.bar_closed(Timeframe.ONE_HOUR))
    assert evaluator.evaluations == []
    evaluator.on_market_event(event_factory.bar_closed(Timeframe.FIVE_MINUTES))
    assert evaluator.evaluations == [("ma-crossover", Timeframe.FIVE_MINUTES)]


def test_advisory_producer_cannot_emit_trade_intent(evaluator, proposal_factory):
    proposal = proposal_factory.ai_trade_proposal()
    result = evaluator.on_market_event(proposal)
    assert result.trade_intents == []
    assert result.proposal_validation is not None
    assert result.proposal_validation.status == "PENDING_DETERMINISTIC_VALIDATION"


def test_heartbeat_routing(evaluator, event_factory, heartbeat_factory):
    definition = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(
            event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES
        ),
    )
    evaluator.register(definition)
    result = evaluator.on_market_event(heartbeat_factory.create())
    assert result.proposals == []
    assert evaluator.evaluations == []


def test_multiple_strategies_different_triggers(evaluator, event_factory):
    ma_def = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(
            event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES
        ),
    )
    boll_def = StrategyDefinition(
        strategy_id="bollinger",
        trigger=TriggerSpec(
            event_type="BarClosed", timeframe=Timeframe.ONE_HOUR
        ),
    )
    evaluator.register(ma_def)
    evaluator.register(boll_def)

    evaluator.on_market_event(event_factory.bar_closed(Timeframe.FIVE_MINUTES))
    assert ("ma-crossover", Timeframe.FIVE_MINUTES) in evaluator.evaluations
    assert ("bollinger", Timeframe.ONE_HOUR) not in evaluator.evaluations

    evaluator.on_market_event(event_factory.bar_closed(Timeframe.ONE_HOUR))
    assert ("bollinger", Timeframe.ONE_HOUR) in evaluator.evaluations


def test_empty_evaluator_returns_no_proposals(evaluator, event_factory):
    result = evaluator.on_market_event(
        event_factory.bar_closed(Timeframe.FIVE_MINUTES)
    )
    assert result.proposals == []
    assert evaluator.evaluations == []


def test_strategy_not_triggered_by_different_event_type(evaluator, event_factory):
    definition = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(
            event_type="CorporateAction", timeframe=Timeframe.ONE_DAY
        ),
    )
    evaluator.register(definition)
    result = evaluator.on_market_event(
        event_factory.bar_closed(Timeframe.ONE_DAY)
    )
    assert result.proposals == []


def test_registered_strategy_produces_proposal_with_correct_fields(evaluator, event_factory):
    definition = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(
            event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES
        ),
    )
    evaluator.register(definition)
    result = evaluator.on_market_event(
        event_factory.bar_closed(Timeframe.FIVE_MINUTES, instrument_id="AAPL", close=150.0)
    )
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.strategy_id == "ma-crossover"
    assert proposal.instrument_id == "AAPL"
    assert proposal.price == 150.0
    assert proposal.timeframe == Timeframe.FIVE_MINUTES
