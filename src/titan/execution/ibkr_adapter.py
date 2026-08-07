"""IBKR paper adapter wrapping ibapi behind TITAN's BrokerAdapter.

Connects to TWS (port 7497) or IB Gateway (port 8874) paper account.
Routes all orders through PaperTradingEngine.submit_intent — never direct.
"""

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.wrapper import EWrapper

from titan._core import ApprovedOrderIntent, BrokerPosition, Money
from titan.data.forex_pairs import FOREX_PAIRS

from ._broker_adapter import BrokerAdapter
from ._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)

TWS_PAPER_PORT = 7497
GATEWAY_PAPER_PORT = 8874

# ibapi informational errors we ignore
_INFO_ERROR_CODES = {2104, 2105, 2106, 2107, 2108, 2158}


class _IBKRWrapper(EWrapper):
    """Synchronous wrapper converting ibapi callbacks to blocking results."""

    def __init__(self) -> None:
        super().__init__()
        self.accounts_ready = threading.Event()
        self.accounts: list[str] = []
        self.next_oid: Optional[int] = None
        self.oid_ready = threading.Event()

        self._errors: list[tuple[int, int, str]] = []
        self._error_ready = threading.Event()

        self._positions: list[BrokerPosition] = []
        self._positions_ready = threading.Event()

        self._summary: dict[str, str] = {}
        self._summary_ready = threading.Event()

        self._order_results: dict[int, tuple[str, float, float, float]] = {}
        self._order_events: dict[int, threading.Event] = {}
        # broker order id (int) -> titan client_order_id, and order metadata for
        # status polling (instrument/side/quantity). Registered at place_order.
        self._client_by_oid: dict[int, str] = {}
        self._order_meta: dict[int, dict] = {}

    def nextValidId(self, orderId: int) -> None:
        self.next_oid = orderId
        self.oid_ready.set()

    def managedAccounts(self, accountsList: str) -> None:
        self.accounts = accountsList.split(",") if accountsList else []
        self.accounts_ready.set()

    def connectionClosed(self) -> None:
        pass

    def error(self, reqId: int, errorTime: int = -1, errorCode: int = 0, errorString: str = "", advancedOrderRejectJson: str = "") -> None:
        if errorCode in _INFO_ERROR_CODES:
            return
        self._errors.append((reqId, errorCode, errorString))
        self._error_ready.set()

    def position(self, account: str, contract: Contract, pos: float, avgCost: float) -> None:
        if pos == 0:
            return
        direction = "SELL" if pos < 0 else "BUY"
        sym = contract.symbol or ""
        if contract.secType == "CASH" and contract.currency:
            sym = f"{sym}{contract.currency}"
        self._positions.append(BrokerPosition(
            instrument_id=sym,
            side=direction,
            quantity=int(abs(pos)),
        ))

    def positionEnd(self) -> None:
        self._positions_ready.set()

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:
        self._summary[tag] = value

    def accountSummaryEnd(self, reqId: int) -> None:
        self._summary_ready.set()

    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float,
                    avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
                    clientId: int, whyHeld: str, mktCapPrice: float) -> None:
        # Store UNCONDITIONALLY — the engine's fill poll reads the latest status
        # even after place_order returned (async fills, external cancels from the
        # TWS UI, partial fills). Previously this only stored when a waiter was
        # registered, so late status changes were silently dropped.
        self._order_results[orderId] = (status, filled, remaining, avgFillPrice)
        event = self._order_events.get(orderId)
        if event:
            event.set()


class IBKRPaperAdapter(BrokerAdapter):
    """IBKR paper adapter.

    Connects to a locally running TWS/IB Gateway paper account. Requires
    the ``ibapi`` package installed. Paper-only: port is locked to TWS 7497
    or Gateway 8874.
    """

    @staticmethod
    def _is_paper_account(account_id: str) -> bool:
        if not account_id:
            return False
        acc = account_id.strip().upper()
        # IBKR Paper account prefixes: DU (Individual Paper), DF (Financial Advisor Paper), PAPER, S (Simulated)
        return acc.startswith("DU") or acc.startswith("DF") or acc.startswith("PAPER") or acc.startswith("S") or acc.startswith("SIM")

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = TWS_PAPER_PORT,
        client_id: int = 1,
        account_id: Optional[str] = None,
        connect_timeout: float = 15.0,
        fill_timeout: float = 12.0,
        paper_mode: bool = True,
    ) -> None:
        if not paper_mode:
            raise ValueError("IBKRPaperAdapter requires paper_mode=True to prevent live routing")
        if port not in (TWS_PAPER_PORT, GATEWAY_PAPER_PORT):
            raise ValueError(f"IBKRPaperAdapter accepts paper TWS/Gateway ports only (7497 or 8874), got port={port}")
        if account_id and not self._is_paper_account(account_id):
            raise ValueError(
                f"IBKRPaperAdapter account_id safeguard violation: '{account_id}' does not have an IBKR paper account prefix (DU/DF/PAPER/S)."
            )

        self._paper_mode = paper_mode
        self._host = host
        self._port = port
        self._client_id = client_id
        self._account_id = account_id
        self._connect_timeout = connect_timeout
        self._fill_timeout = fill_timeout

        self._wrapper = _IBKRWrapper()
        self._client = EClient(self._wrapper)
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[Session] = None

    def authenticate(self) -> Session:
        if self._connected and self._session:
            return self._session

        candidate_ids = [self._client_id, 2, 3, 5, 10]
        connected = False

        for cid in candidate_ids:
            self._client_id = cid
            self._wrapper = _IBKRWrapper()
            self._client = EClient(self._wrapper)
            try:
                self._client.connect(self._host, self._port, self._client_id)
                self._thread = threading.Thread(target=self._client.run, daemon=True)
                self._thread.start()

                got_acc = self._wrapper.accounts_ready.wait(timeout=3.0)
                got_oid = self._wrapper.oid_ready.wait(timeout=3.0)

                if got_acc and got_oid:
                    connected = True
                    break
                self._client.disconnect()
            except Exception:
                pass

        if not connected:
            raise AdapterError("IBKR authentication timeout: failed to receive accounts or order ID", "authentication")

        self._connected = True

        if not self._account_id and self._wrapper.accounts:
            paper_accs = [acc for acc in self._wrapper.accounts if self._is_paper_account(acc)]
            if not paper_accs:
                self._client.disconnect()
                raise AdapterError(
                    f"IBKR SAFEGUARD VIOLATION: Discovered accounts {self._wrapper.accounts} are not paper accounts (DU/DF/PAPER prefix required). Disconnecting to protect live capital.",
                    "authentication",
                )
            self._account_id = paper_accs[0]

        if not self._account_id or not self._is_paper_account(self._account_id):
            self._client.disconnect()
            raise AdapterError(
                f"IBKR SAFEGUARD VIOLATION: Account '{self._account_id}' failed paper account verification. Disconnecting to protect live capital.",
                "authentication",
            )

        print(f"[IBKR SAFEGUARD PASSED] Verified Paper Environment: Port={self._port}, Account={self._account_id}, PaperMode=True")

        session = Session(
            session_id=str(uuid.uuid4()),
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._session = session
        return session

    def heartbeat(self) -> AdapterHealth:
        try:
            connected = self._client.isConnected() if self._connected else False
            if connected:
                return AdapterHealth(connected=True, session_state=AdapterSessionState.CONNECTED)
            return AdapterHealth(
                connected=False,
                session_state=AdapterSessionState.DISCONNECTED,
                degradation=["IBKR client disconnected"],
            )
        except Exception as e:
            return AdapterHealth(
                connected=False,
                session_state=AdapterSessionState.DISCONNECTED,
                degradation=[str(e)],
            )

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        if not self._connected:
            return BrokerOrderAcknowledgement(accepted=False, rejection_reason="Not connected to IBKR")

        try:
            oid = self._order_id()
            contract = self._contract(str(intent.instrument_id))
            order = Order()
            order.action = "BUY" if str(intent.side).upper() == "BUY" else "SELL"
            order.totalQuantity = int(str(intent.quantity))
            order.orderType = "LMT" if str(intent.order_type).upper() == "LIMIT" else "MKT"
            if order.orderType == "LMT":
                order.lmtPrice = float(str(intent.price)) if intent.price else 0.0
            order.tif = "DAY"
            order.orderId = oid
            if self._account_id:
                order.account = self._account_id

            # ADR-021: protective stop from the intent. Paper adapter is
            # guaranteed by construction (paper_mode enforced in __init__), so
            # mapping the intent's stop_price to an IBKR STP child is safe. The
            # parent stays the entry order; the STP is attached as a child so a
            # fill of the parent arms it (bracket semantics). take_profit_price
            # / trailing require ApprovedOrderIntent to carry them (Rust
            # extension, documented in ADR-021 spec follow-up) — until then they
            # are intentionally NOT silently dropped: the entry still places.
            if intent.stop_price:
                stop_child = Order()
                stop_child.action = "SELL" if str(intent.side).upper() == "BUY" else "BUY"
                stop_child.totalQuantity = int(str(intent.quantity))
                stop_child.orderType = "STP"
                stop_child.auxPrice = float(str(intent.stop_price))
                stop_child.tif = "GTC"
                stop_child.parentId = oid
                stop_child.orderId = self._order_id()
                stop_child.account = self._account_id
                self._client.placeOrder(stop_child.orderId, contract, stop_child)

            # Track the client order for async status polling (tick/ensure_connected)
            self._wrapper._client_by_oid[oid] = str(intent.client_order_id)
            self._wrapper._order_meta[oid] = {
                "instrument_id": str(intent.instrument_id),
                "side": str(intent.side),
                "quantity": str(intent.quantity),
            }

            event = threading.Event()
            self._wrapper._order_events[oid] = event

            self._client.placeOrder(oid, contract, order)

            # Wait (bounded) for a terminal status (Filled/Rejected/Cancelled/Inactive),
            # not the first intermediate callback (Submitted/PreSubmitted). Fast fills
            # are captured synchronously; anything still working is left pending for
            # poll_fills to absorb via tick() — the order is NEVER assumed dead.
            terminal = {"Filled", "Rejected", "Cancelled", "Inactive", "ApiCancelled", "ApiRejected"}
            deadline = time.monotonic() + self._fill_timeout
            while time.monotonic() < deadline:
                event.wait(timeout=min(1.0, max(0.05, deadline - time.monotonic())))
                result = self._wrapper._order_results.get(oid)
                if result and result[0] in terminal:
                    break

            self._wrapper._order_events.pop(oid, None)
            result = self._wrapper._order_results.get(oid)
            if result:
                status, filled, remaining, avg_price = result
                return BrokerOrderAcknowledgement(
                    accepted=status not in ("Rejected", "Cancelled", "Inactive", "ApiCancelled", "ApiRejected"),
                    broker_order_id=BrokerOrderId(id=str(oid)),
                    fill_price=str(avg_price) if avg_price and float(avg_price) > 0 else None,
                    fill_quantity=str(int(filled)) if filled and int(filled) > 0 else None,
                    order_status=status,
                )
            return BrokerOrderAcknowledgement(
                accepted=True,
                broker_order_id=BrokerOrderId(id=str(oid)),
                order_status="Submitted",
            )
        except Exception as e:
            return BrokerOrderAcknowledgement(accepted=False, rejection_reason=f"IBKR place_order failed: {e}")

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        if not self._connected or self._client.serverVersion() is None:
            raise AdapterError("IBKR positions() called while not fully connected", "connection")
        self._wrapper._positions.clear()
        self._wrapper._positions_ready.clear()
        self._client.reqPositions()
        if not self._wrapper._positions_ready.wait(timeout=10.0):
            # Do NOT return a silent empty snapshot — an empty result is
            # indistinguishable from "flat" and would produce a phantom
            # critical drift in reconciliation. Raise so callers treat the
            # broker as unavailable (fail closed) instead.
            raise AdapterError("IBKR positions() timed out waiting for positionEnd", "timeout")
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=list(self._wrapper._positions),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        if not self._connected or self._client.serverVersion() is None:
            raise AdapterError("IBKR holdings() called while not fully connected", "connection")
        self._wrapper._summary.clear()
        self._wrapper._summary_ready.clear()
        self._client.reqAccountSummary(
            1, "All", "TotalCashValue,NetLiquidation,AvailableFunds,BuyingPower,GrossPositionValue",
        )
        if not self._wrapper._summary_ready.wait(timeout=10.0):
            self._client.cancelAccountSummary(1)
            # Do NOT fall back to Money("0") — a zero balance would read as a
            # 100% cash drift in reconciliation. Raise so the caller treats
            # the broker as unavailable instead.
            raise AdapterError("IBKR holdings() timed out waiting for account summary", "timeout")
        self._client.cancelAccountSummary(1)

        d = self._wrapper._summary
        cash = Money(d.get("TotalCashValue", "0"), "USD")
        equity = Money(d.get("NetLiquidation", "0"), "USD")
        bp = Money(d.get("BuyingPower", "0"), "USD")

        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=cash,
            portfolio_value=equity,
            buying_power=bp,
            equity=equity,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        if not self._connected:
            return CancellationAcknowledgement(accepted=False, broker_order_id=order_id)
        try:
            from ibapi.order_cancel import OrderCancel
            self._client.cancelOrder(int(order_id.id), OrderCancel())
            return CancellationAcknowledgement(accepted=True, broker_order_id=order_id)
        except Exception as e:
            if self._connected:
                print(f"[ibkr] cancel failed for {order_id.id}: {e}", flush=True)
            return CancellationAcknowledgement(accepted=False, broker_order_id=order_id)

    def tick(self, order_id: str) -> Optional[BrokerOrderStatus]:
        """Return the latest broker status for a client order, or None if unknown.

        Reads the orderStatus callbacks TWS keeps pushing for this client's
        orders (async fills, partial fills, external cancels/modifies from the
        TWS UI). The engine's fill-poll loop calls this every ~1s.
        """
        if not self._connected:
            return None
        oid = next((o for o, c in self._wrapper._client_by_oid.items() if c == order_id), None)
        if oid is None:
            return None
        result = self._wrapper._order_results.get(oid)
        if result is None:
            return None
        status, filled, remaining, avg_price = result
        meta = self._wrapper._order_meta.get(oid, {})
        return BrokerOrderStatus(
            order_id=BrokerOrderId(id=str(oid)),
            instrument_id=meta.get("instrument_id", ""),
            side=meta.get("side", ""),
            quantity=meta.get("quantity", "0"),
            filled_quantity=str(int(filled)) if filled else "0",
            price=str(avg_price) if avg_price and float(avg_price) > 0 else None,
            status=status,
            created_at="",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def ensure_connected(self, force: bool = False) -> bool:
        """Re-establish the TWS connection if it dropped (TWS restart, timeout).

        With force=True, reset an existing connection first — used to recover
        from the TWS "API wedge" where account queries (reqPositions /
        reqAccountSummary) stall while market data keeps flowing. A fresh
        connection clears it.

        Returns True if connected afterwards (with the handshake complete).
        """
        if (not force and self._connected and self._client.isConnected()
                and self._client.serverVersion() is not None):
            return True
        # The cached _connected/_session are stale after a client disconnect —
        # reset them so authenticate() actually reconnects instead of returning
        # the dead session.
        try:
            if self._connected:
                self._client.disconnect()
        except Exception:
            pass
        self._connected = False
        self._session = None
        try:
            self.authenticate()
        except Exception:
            return False
        if not self._connected:
            return False
        # Wait for the connection handshake to complete (serverVersion set).
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self._client.serverVersion() is not None:
                return True
            time.sleep(0.25)
        return False


    def _order_id(self) -> int:
        oid = self._wrapper.next_oid or 1
        self._wrapper.next_oid = oid + 1
        return oid

    @staticmethod
    def _contract(instrument_id: str) -> Contract:
        contract = Contract()
        clean = instrument_id.split(".")[0].upper() if "." in instrument_id else instrument_id.upper()
        clean = clean.replace("/", "").replace("_", "")

        if clean in FOREX_PAIRS:
            info = FOREX_PAIRS[clean]
            contract.symbol = info["base"]
            contract.secType = "CASH"
            contract.exchange = "IDEALPRO"
            contract.currency = info["quote"]
        else:
            contract.symbol = clean
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
        return contract
