"""Contract tests for IBKRPaperAdapter.

Uses mocked ibapi EClient to avoid requiring a TWS/Gateway connection.
The mock controls what the EWrapper callbacks deliver, keeping tests
deterministic and fast.
"""

import threading

from unittest.mock import MagicMock, patch

import pytest

from titan._core import ApprovedOrderIntent
from titan.execution._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    BrokerBalanceSnapshot,
    CancellationAcknowledgement,
)
from titan.execution.ibkr_adapter import (
    IBKRPaperAdapter,
    TWS_PAPER_PORT,
    GATEWAY_PAPER_PORT,
)


class TestIBKRAdapterConstruction:
    """Tests for adapter initialization and port validation."""

    def test_accepts_tws_paper_port(self):
        adapter = IBKRPaperAdapter(port=TWS_PAPER_PORT)
        assert adapter._port == TWS_PAPER_PORT

    def test_accepts_gateway_paper_port(self):
        adapter = IBKRPaperAdapter(port=GATEWAY_PAPER_PORT)
        assert adapter._port == GATEWAY_PAPER_PORT

    def test_rejects_live_tws_port(self):
        with pytest.raises(ValueError, match="paper"):
            IBKRPaperAdapter(port=7496)

    def test_defaults_to_tws_paper_port(self):
        adapter = IBKRPaperAdapter()
        assert adapter._port == TWS_PAPER_PORT

    def test_rejects_live_account_id_prefix(self):
        with pytest.raises(ValueError, match="safeguard violation"):
            IBKRPaperAdapter(account_id="U1234567")

    def test_accepts_paper_account_id_prefix(self):
        adapter = IBKRPaperAdapter(account_id="DU1234567")
        assert adapter._account_id == "DU1234567"

    def test_rejects_paper_mode_false(self):
        with pytest.raises(ValueError, match="requires paper_mode=True"):
            IBKRPaperAdapter(paper_mode=False)


class TestIBKRAdapterContract:
    """Tests for the static contract-building helper."""

    def test_build_default_stock_contract(self):
        contract = IBKRPaperAdapter._contract("AAPL")
        assert contract.symbol == "AAPL"
        assert contract.secType == "STK"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"

    def test_strips_dot_suffix(self):
        contract = IBKRPaperAdapter._contract("SPY.ARCA")
        assert contract.symbol == "SPY"

    def test_uppercases_symbol(self):
        contract = IBKRPaperAdapter._contract("aapl")
        assert contract.symbol == "AAPL"

    def test_build_forex_contract(self):
        contract = IBKRPaperAdapter._contract("EURUSD")
        assert contract.symbol == "EUR"
        assert contract.secType == "CASH"
        assert contract.exchange == "IDEALPRO"
        assert contract.currency == "USD"

    def test_build_forex_contract_with_suffix(self):
        contract = IBKRPaperAdapter._contract("GBPUSD.IDEALPRO")
        assert contract.symbol == "GBP"
        assert contract.secType == "CASH"
        assert contract.exchange == "IDEALPRO"
        assert contract.currency == "USD"


class TestIBKRAdapterOrderId:
    """Tests for the local order ID counter."""

    def test_starts_from_wrapper_value(self):
        adapter = IBKRPaperAdapter()
        adapter._wrapper.next_oid = 100
        assert adapter._order_id() == 100
        assert adapter._wrapper.next_oid == 101

    def test_defaults_to_one(self):
        adapter = IBKRPaperAdapter()
        adapter._wrapper.next_oid = None
        assert adapter._order_id() == 1

    def test_increments(self):
        adapter = IBKRPaperAdapter()
        adapter._wrapper.next_oid = 5
        assert adapter._order_id() == 5
        assert adapter._order_id() == 6
        assert adapter._order_id() == 7


class TestIBKRAdapterHeartbeat:
    """Tests for heartbeat without a connection."""

    def setup_method(self):
        self.adapter = IBKRPaperAdapter()

    def test_heartbeat_disconnected(self):
        health = self.adapter.heartbeat()
        assert health.connected is False
        assert health.session_state == AdapterSessionState.DISCONNECTED

    def test_heartbeat_reports_degradation_on_exception(self):
        self.adapter._connected = True
        self.adapter._client.isConnected = MagicMock(side_effect=RuntimeError("Boom"))
        health = self.adapter.heartbeat()
        assert health.connected is False
        assert len(health.degradation) > 0


class TestIBKRAdapterPlaceOrder:
    """Tests for order placement (mocked EClient)."""

    def setup_method(self):
        self.adapter = IBKRPaperAdapter()

    def test_rejects_order_when_not_connected(self):
        intent = ApprovedOrderIntent(
            risk_decision_id="rd-1", intent_id="int-1", client_order_id="co-1",
            instrument_id="AAPL", side="BUY", quantity="1", order_type="MARKET",
            time_in_force="DAY", risk_profile_version="v1", price=None, stop_price=None,
        )
        result = self.adapter.place_order(intent)
        assert result.accepted is False
        assert "Not connected" in result.rejection_reason


class TestIBKRAdapterCancel:
    """Tests for cancel without a connection."""

    def setup_method(self):
        self.adapter = IBKRPaperAdapter()

    def test_cancel_rejected_when_not_connected(self):
        order_id = BrokerOrderId(id="101")
        result = self.adapter.cancel(order_id)
        assert result.accepted is False
        assert result.broker_order_id.id == "101"

    def test_cancel_accepted_with_mock(self):
        self.adapter._connected = True
        self.adapter._client.cancelOrder = MagicMock()
        order_id = BrokerOrderId(id="102")
        result = self.adapter.cancel(order_id)
        assert result.accepted is True
        # ibapi 9.81 cancelOrder(orderId, orderCancel) — the OrderCancel arg is
        # required; without it TWS errors 10147 and the cancel silently no-ops.
        self.adapter._client.cancelOrder.assert_called_once()
        args = self.adapter._client.cancelOrder.call_args[0]
        assert args[0] == 102


class TestIBKRAdapterPositions:
    """Tests for positions query without a connection."""

    def setup_method(self):
        self.adapter = IBKRPaperAdapter()

    def test_raises_when_not_connected(self):
        # Fail-closed contract: never return a silent empty snapshot when
        # disconnected — the engine would reconcile against "flat" and either
        # phantom-drift (kill switch) or miss a real position.
        with pytest.raises(AdapterError, match="not fully connected"):
            self.adapter.positions("acc-1")


class TestIBKRAdapterHoldings:
    """Tests for holdings query without a connection."""

    def setup_method(self):
        self.adapter = IBKRPaperAdapter()

    def test_raises_when_not_connected(self):
        # Same fail-closed contract as positions(): a zero-cash snapshot on a
        # disconnected client produced phantom 100% cash drift and kill-switch
        # triggers in the live system.
        with pytest.raises(AdapterError, match="not fully connected"):
            self.adapter.holdings("acc-1")


class TestIBKRAdapterEndToEndMock:
    """End-to-end mock test that simulates a full ibapi lifecycle.

    Patches EClient.connect at the CLASS level — authenticate() recreates the
    client in its candidate-id reconnect loop, so instance-level patches are
    bypassed and would connect to a real TWS. The mock fires the expected
    callbacks on the newly-created wrapper.
    """

    def test_authenticate_sets_session(self):
        from titan.execution import ibkr_adapter as ibkr_mod

        adapter = IBKRPaperAdapter()

        def fake_connect(client, host, port, cid):
            client.wrapper.managedAccounts("DU1234567")
            client.wrapper.nextValidId(100)

        with patch.object(ibkr_mod.EClient, "connect", fake_connect):
            with patch.object(ibkr_mod.EClient, "run"):
                session = adapter.authenticate()
                assert session.state == AdapterSessionState.CONNECTED
                assert adapter._connected is True
                assert adapter._account_id == "DU1234567"

    def test_authenticate_raises_on_timeout(self):
        from titan.execution import ibkr_adapter as ibkr_mod

        adapter = IBKRPaperAdapter(connect_timeout=0.1)

        with patch.object(ibkr_mod.EClient, "connect"):
            with patch.object(ibkr_mod.EClient, "disconnect"):
                with pytest.raises(AdapterError, match="authentication timeout"):
                    adapter.authenticate()

    def test_full_lifecycle(self):
        adapter = IBKRPaperAdapter()

        # authenticate() REBUILDS _wrapper and _client for every candidate
        # client id (ibkr_adapter.py:190-213), so patching adapter._client /
        # adapter._wrapper beforehand never takes effect — the fresh EClient
        # and _IBKRWrapper replace them before connect(). Patch EClient at the
        # module level and have connect() fire the wrapper callbacks that set
        # accounts_ready / oid_ready on the wrapper instance authenticate()
        # passes into the EClient constructor.
        import titan.execution.ibkr_adapter as ibkr_mod

        def _fire_callbacks_on_connect(*args, **kwargs):
            wrapper = ibkr_mod.EClient.call_args.args[0]
            wrapper.managedAccounts("DU1234567")
            wrapper.nextValidId(100)

        with patch.object(ibkr_mod, "EClient") as mock_ec:
            mock_ec.return_value.connect.side_effect = _fire_callbacks_on_connect
            mock_ec.return_value.isConnected.return_value = True

            session = adapter.authenticate()
            assert session.state == AdapterSessionState.CONNECTED

            health = adapter.heartbeat()
            assert health.connected is True

    def test_place_order_with_mock(self):
        adapter = IBKRPaperAdapter()
        adapter._connected = True

        with patch.object(adapter._client, "placeOrder") as mock_place:
            intent = ApprovedOrderIntent(
                risk_decision_id="rd-1", intent_id="int-1", client_order_id="co-1",
                instrument_id="AAPL", side="BUY", quantity="100", order_type="MARKET",
                time_in_force="DAY", risk_profile_version="v1", price=None, stop_price=None,
            )
            result = adapter.place_order(intent)
            mock_place.assert_called_once()
            assert result.accepted is True


class TestIBKRAdapterExitBrackets:
    """P1 D2: bracket exits are DISABLED pending OCA implementation.

    Independent stop/target/trail children can EACH fill after the entry
    (no OCA group cancels siblings), overselling the position 2-3x. The
    adapter must hard-reject every intent carrying exit specifications and
    place NOTHING on the wire — fail closed.
    """

    def _connected_adapter(self, entitlements=None):
        from titan._core import ApprovedOrderIntent as AOI
        adapter = IBKRPaperAdapter(entitlements=entitlements)
        adapter._connected = True
        adapter._client.placeOrder = MagicMock()
        adapter._client.isConnected = MagicMock(return_value=True)
        # wrapper plumbing used by place_order (dicts initialized by _IBKRWrapper)
        adapter._wrapper._client_by_oid = {}
        adapter._wrapper._order_meta = {}
        adapter._wrapper._order_events = {}
        adapter._wrapper._order_results = {}
        adapter._wrapper.next_oid = 1000
        return adapter

    def _intent(self, **kw):
        from titan._core import ApprovedOrderIntent as AOI, TrailingConfig
        base = dict(
            risk_decision_id="rd-1", intent_id="int-1", client_order_id="co-1",
            instrument_id="EURUSD", side="BUY", quantity="10000",
            order_type="MARKET", time_in_force="DAY", risk_profile_version="v1",
            price="1.10", stop_price=None, take_profit_price=None,
            trailing=None,
        )
        base.update(kw)
        return AOI(**base)

    def _arm(self, adapter):
        """Pre-fire the fill event + result so place_order's bounded wait returns."""
        oid = adapter._wrapper.next_oid
        adapter._wrapper._order_events[oid] = threading.Event()
        adapter._wrapper._order_events[oid].set()
        adapter._wrapper._order_results[oid] = ("Filled", 1.10, 10000, 0.0)

    def _assert_rejected_no_wire(self, adapter, intent):
        result = adapter.place_order(intent)
        assert result.accepted is False
        assert "bracket" in (result.rejection_reason or "").lower()
        assert adapter._client.placeOrder.call_args_list == []

    def test_stop_maps_to_stp_child(self):
        adapter = self._connected_adapter()
        self._assert_rejected_no_wire(adapter, self._intent(stop_price="1.09"))

    def test_take_profit_maps_to_lmt_child(self):
        adapter = self._connected_adapter()
        self._assert_rejected_no_wire(
            adapter, self._intent(stop_price="1.09", take_profit_price="1.12"))

    def test_trailing_maps_to_trail_when_entitled(self):
        from titan._core import TrailingConfig
        adapter = self._connected_adapter(entitlements={"TRAIL"})
        self._assert_rejected_no_wire(
            adapter, self._intent(stop_price="1.09",
                                  trailing=TrailingConfig("2.0", "1.0")))

    def test_trailing_rejected_without_entitlement(self):
        from titan._core import TrailingConfig
        adapter = self._connected_adapter(entitlements=set())  # no TRAIL
        self._assert_rejected_no_wire(
            adapter, self._intent(stop_price="1.09",
                                  trailing=TrailingConfig("2.0", "1.0")))

    def test_no_children_without_exits(self):
        adapter = self._connected_adapter()
        intent = self._intent()
        self._arm(adapter)
        adapter.place_order(intent)
        orders = [c.args[2] for c in adapter._client.placeOrder.call_args_list]
        child_types = [o.orderType for o in orders if o.orderType in ("STP", "TRAIL")]
        assert child_types == [], "no protective children for a bare entry"
