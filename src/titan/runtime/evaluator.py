import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from titan.runtime.events import (
    DecisionTrace,
    EvaluationResult,
    MarketEvent,
    ProposalValidation,
    StrategyDefinition,
    TradeProposal,
)
from titan.strategies.timeframes import Timeframe


@dataclass
class RuntimeEvaluator:
    _definitions: dict[str, StrategyDefinition] = field(default_factory=dict)
    _evaluations: list[tuple[str, Timeframe]] = field(default_factory=list)
    _seen_message_ids: set[str] = field(default_factory=set)
    _traces: dict[str, list[dict]] = field(default_factory=dict)
    _producer: object | None = None

    @property
    def evaluations(self) -> list[tuple[str, Timeframe]]:
        return list(self._evaluations)

    def register(self, definition: StrategyDefinition) -> None:
        self._definitions[definition.strategy_id] = definition

    def set_producer(self, producer: object) -> None:
        self._producer = producer

    def _trace(self, correlation_id: str, stage: str, details: dict | None = None) -> None:
        if correlation_id not in self._traces:
            self._traces[correlation_id] = []
        self._traces[correlation_id].append(
            {"stage": stage, **(details or {})}
        )

    def on_market_event(self, event: MarketEvent) -> EvaluationResult:
        self._trace(event.correlation_id, "MarketEventReceived",
                     {"message_id": event.message_id, "event_type": event.event_type})

        if event.message_id in self._seen_message_ids:
            return EvaluationResult(proposals=[])
        self._seen_message_ids.add(event.message_id)

        if event.event_type == "Heartbeat":
            return EvaluationResult(proposals=[])

        if event.event_type == "AdvisoryProposal":
            self._trace(event.correlation_id, "FeatureSnapshotCreated")
            self._trace(event.correlation_id, "StrategyEvaluated")
            self._trace(event.correlation_id, "TradeProposalCreated")
            self._trace(event.correlation_id, "ProposalValidated",
                         {"status": "PENDING_DETERMINISTIC_VALIDATION"})
            return EvaluationResult(
                proposals=[],
                trade_intents=[],
                proposal_validation=ProposalValidation(
                    status="PENDING_DETERMINISTIC_VALIDATION",
                    proposal_id=event.payload.get("proposal_id", ""),
                ),
            )

        event_timeframe = event.payload.get("timeframe")
        if event_timeframe is None:
            return EvaluationResult(proposals=[])

        self._trace(event.correlation_id, "FeatureSnapshotCreated",
                     {"timeframe": str(event_timeframe) if event_timeframe else None})

        proposals: list[TradeProposal] = []
        for defn in self._definitions.values():
            if (
                defn.trigger.event_type == event.event_type
                and defn.trigger.timeframe == event_timeframe
            ):
                self._evaluations.append((defn.strategy_id, event_timeframe))

        if self._producer is not None:
            proposals = list(self._producer.on_market_event(event) or [])

        self._trace(event.correlation_id, "StrategyEvaluated")
        self._trace(event.correlation_id, "TradeProposalCreated",
                     {"proposal_count": len(proposals)})
        self._trace(event.correlation_id, "ProposalValidated",
                     {"status": "VALIDATED", "proposal_count": len(proposals)})

        return EvaluationResult(proposals=proposals)

    def get_trace(self, correlation_id: str) -> DecisionTrace:
        return DecisionTrace(entries=list(self._traces.get(correlation_id, [])))
