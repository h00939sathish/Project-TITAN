from abc import ABC, abstractmethod
from typing import Any

from titan._core import ApprovedOrderIntent, BrokerPosition, Money

from ._broker_types import (
    AdapterHealth,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)


class BrokerAdapter(ABC):
    """Canonical broker adapter interface.

    All broker implementations (live, simulated, backtest) must implement
    these methods so that PaperTradingEngine can remain adapter-agnostic.
    """

    @abstractmethod
    def authenticate(self) -> Session: ...

    @abstractmethod
    def heartbeat(self) -> AdapterHealth: ...

    @abstractmethod
    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement: ...

    @abstractmethod
    def positions(self, account_id: str) -> BrokerPositionSnapshot: ...

    @abstractmethod
    def holdings(self, account_id: str) -> BrokerBalanceSnapshot: ...

    @abstractmethod
    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement: ...

    @abstractmethod
    def tick(self, order_id: str) -> Any: ...


    def save_order_count_state(self) -> dict:
        return {}

    def restore_order_count_state(self, state: dict) -> None:
        pass
