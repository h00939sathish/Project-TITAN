"""TITAN execution layer — simulated and live adapters."""

from ._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerFill,
    BrokerFillSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    InstrumentSet,
    OrderAmendment,
    OrderResult,
    QueryWindow,
    QuoteSnapshot,
    ReconciliationCursor,
    Session,
)
from .alpaca_adapter import AlpacaAdapter, create_broker_paper_adapter
from .engine import PaperConfig, PaperTradingEngine, EngineStatus
from .fincept_adapter import FinceptBrokerAdapter
from .simulated_adapter import SimFillQuality, SimOrderState, SimulatedAdapter

__all__ = [
    "AdapterError",
    "AdapterHealth",
    "AdapterSessionState",
    "AlpacaAdapter",
    "create_broker_paper_adapter",
    "BrokerBalanceSnapshot",
    "BrokerFill",
    "BrokerFillSnapshot",
    "BrokerOrderAcknowledgement",
    "BrokerOrderId",
    "BrokerOrderSnapshot",
    "BrokerOrderStatus",
    "BrokerPositionSnapshot",
    "CancellationAcknowledgement",
    "EngineStatus",
    "FinceptBrokerAdapter",
    "InstrumentSet",
    "OrderAmendment",
    "OrderResult",
    "PaperConfig",
    "PaperTradingEngine",
    "QueryWindow",
    "QuoteSnapshot",
    "ReconciliationCursor",
    "Session",
    "SimFillQuality",
    "SimOrderState",
    "SimulatedAdapter",
]
