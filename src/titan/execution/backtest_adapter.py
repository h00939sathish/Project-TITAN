import uuid
from datetime import datetime, timezone

from titan._core import ApprovedOrderIntent, Money

from ..backtest.clock import ReplayClock
from ..backtest.fills import BarConservativeFillModel, FillResult
from ._broker_adapter import BrokerAdapter
from ._broker_types import (
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)


class BacktestAdapter(BrokerAdapter):
    def __init__(
        self,
        bars: list[dict],
        fill_model: BarConservativeFillModel | None = None,
        clock: ReplayClock | None = None,
    ):
        self._bars = list(bars)
        self._current_bar: dict | None = None
        self._fill_model = fill_model or BarConservativeFillModel()
        self._clock = clock or ReplayClock()

    def advance_to(self, bar: dict) -> None:
        self._current_bar = bar
        self._clock.advance_to(bar["timestamp"])

    @property
    def clock(self) -> ReplayClock:
        return self._clock

    def authenticate(self) -> Session:
        return Session(
            session_id=str(uuid.uuid4()),
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def heartbeat(self) -> AdapterHealth:
        return AdapterHealth(connected=True, session_state=AdapterSessionState.CONNECTED)

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        if self._current_bar is None:
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason="No bar data available",
            )

        side = "buy" if intent.side and intent.side.lower() in ("buy", "long") else "sell"
        quantity = int(intent.quantity)
        bar = self._current_bar
        # A MARKET order carrying an explicit price is a simulation-computed
        # execution level -- the protective-exit price ReplayEngine derives from
        # the stop/TP level or the gap open. Fill from that level so the trigger
        # price is not silently replaced by the bar close. Substituting the bar
        # (rather than returning the level outright) keeps slippage and
        # commission flowing through the single deterministic fill model, so a
        # stop still slips adversely. LIMIT orders are ordinary strategy
        # signals and keep the bar-conservative model.
        if str(intent.order_type).upper() == "MARKET" and intent.price:
            bar = {**bar, "close": str(intent.price)}
        fill: FillResult = self._fill_model.fill(bar, side, quantity)

        return BrokerOrderAcknowledgement(
            accepted=True,
            broker_order_id=BrokerOrderId(id=str(id(intent))),
            fill_price=str(fill.fill_price),
            fill_quantity=str(fill.fill_quantity),
        )

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=Money("100000", "USD"),
            portfolio_value=Money("100000", "USD"),
            buying_power=Money("100000", "USD"),
            equity=Money("100000", "USD"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        return CancellationAcknowledgement(accepted=True, broker_order_id=order_id)

    def tick(self, order_id: str) -> None:
        return None

