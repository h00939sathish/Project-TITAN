import hashlib
import json
from datetime import datetime, timezone

import pytest

from titan.runtime.events import MarketEvent
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


@pytest.fixture
def proposal_factory():
    class _Factory:
        _counter = 0

        def ai_trade_proposal(self) -> MarketEvent:
            self._counter += 1
            now = datetime.now(timezone.utc)
            payload = {
                "proposal_id": f"prop-{self._counter}",
                "strategy_id": "ai-advisor",
                "producer_kind": "ai_advisory",
                "instrument_id": "SPY",
                "side": "BUY",
                "quantity": 100,
                "price": 100.0,
                "timeframe": Timeframe.FIVE_MINUTES,
                "close_timestamp": now.isoformat(),
                "rationale_digest": "abc123",
                "sources": [],
            }
            return MarketEvent(
                message_id=f"prop-msg-{self._counter}",
                causation_id=f"cause-{self._counter}",
                correlation_id=f"corr-{self._counter}",
                occurred_at=now,
                received_at=now,
                schema_version=1,
                source="ai-advisor",
                event_type="AdvisoryProposal",
                instrument_id="SPY",
                payload=payload,
                payload_digest=hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            )

    return _Factory()


@pytest.fixture
def heartbeat_factory():
    class _Factory:
        _counter = 0

        def create(self) -> MarketEvent:
            self._counter += 1
            now = datetime.now(timezone.utc)
            payload = {"status": "ok"}
            return MarketEvent(
                message_id=f"hb-{self._counter}",
                causation_id=f"cause-hb-{self._counter}",
                correlation_id=f"corr-hb-{self._counter}",
                occurred_at=now,
                received_at=now,
                schema_version=1,
                source="system",
                event_type="Heartbeat",
                instrument_id="",
                payload=payload,
                payload_digest=hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            )

    return _Factory()


@pytest.fixture
def evaluator() -> RuntimeEvaluator:
    return RuntimeEvaluator()
