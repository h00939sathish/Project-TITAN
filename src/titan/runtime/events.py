from dataclasses import dataclass, field
from datetime import datetime

from titan.strategies.timeframes import Timeframe


@dataclass
class MarketEvent:
    message_id: str
    causation_id: str
    correlation_id: str
    occurred_at: datetime
    received_at: datetime
    schema_version: int
    source: str
    event_type: str
    instrument_id: str
    payload: dict
    payload_digest: str


@dataclass
class TradeProposal:
    proposal_id: str
    strategy_id: str
    producer_kind: str
    instrument_id: str
    side: str
    quantity: float
    price: float
    timeframe: Timeframe
    close_timestamp: datetime
    rationale_digest: str
    sources: list[str]


@dataclass
class TriggerSpec:
    event_type: str
    timeframe: Timeframe


@dataclass
class StrategyDefinition:
    strategy_id: str
    trigger: TriggerSpec
    context: tuple[Timeframe, ...] = ()
    params: dict = field(default_factory=dict)


@dataclass
class DecisionTrace:
    entries: list[dict] = field(default_factory=list)


@dataclass
class ProposalValidation:
    status: str
    proposal_id: str = ""


@dataclass
class EvaluationResult:
    proposals: list[TradeProposal] = field(default_factory=list)
    trade_intents: list = field(default_factory=list)
    proposal_validation: ProposalValidation | None = None
