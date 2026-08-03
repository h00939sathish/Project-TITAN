"""Contract tests for AlpacaAdapter — uses mocked Alpaca TradingClient."""

from datetime import datetime, timezone
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
    InstrumentSet,
    OrderAmendment,
    QueryWindow,
)
from titan.execution.alpaca_adapter import AlpacaAdapter


@pytest.fixture
def mock_alpaca_client():
    """Create a mock TradingClient for isolated adapter tests."""
    with patch("titan.execution.alpaca_adapter.TradingClient") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


class TestAlpacaAdapterConstruction:
    """Tests for adapter initialization and credential handling."""

    def test_raises_without_credentials(self):
        with pytest.raises(AdapterError, match="not configured"):
            AlpacaAdapter(api_key="", secret_key="")

    def test_raises_with_missing_secret(self):
        with pytest.raises(AdapterError, match="not configured"):
            AlpacaAdapter(api_key="key", secret_key="")

    def test_raises_with_missing_key(self):
        with pytest.raises(AdapterError, match="not configured"):
            AlpacaAdapter(api_key="", secret_key="secret")

    def test_accepts_explicit_credentials(self, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = MagicMock(
            status="ACTIVE",
        )
        adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")
        session = adapter.authenticate()
        assert session.state == AdapterSessionState.CONNECTED

    def test_defaults_to_paper(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        assert adapter._paper is True

    def test_custom_base_url(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s", base_url="https://paper-api.alpaca.markets")
        assert adapter._base_url == "https://paper-api.alpaca.markets"


class TestAlpacaAdapterAuthenticate:
    """Tests for the authenticate / heartbeat / refresh lifecycle."""

    def setup_method(self):
        self.adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")

    def test_authenticate_connects(self, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = MagicMock(status="ACTIVE")
        session = self.adapter.authenticate()
        assert session.state == AdapterSessionState.CONNECTED

    def test_authenticate_creates_session(self, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = MagicMock(status="ACTIVE")
        session = self.adapter.authenticate()
        assert session.session_id is not None
        assert session.created_at is not None

    def test_authenticate_failure_raises(self, mock_alpaca_client):
        mock_alpaca_client.get_account.side_effect = RuntimeError("API unreachable")
        with pytest.raises(AdapterError, match="Authentication failed"):
            self.adapter.authenticate()

    def test_refresh_returns_new_session(self, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = MagicMock(status="ACTIVE")
        s1 = self.adapter.authenticate()
        s2 = self.adapter.refresh(s1)
        assert s2.session_id != s1.session_id

    def test_heartbeat_connected(self, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = MagicMock(status="ACTIVE")
        self.adapter.authenticate()
        health = self.adapter.heartbeat()
        assert health.connected is True

    def test_heartbeat_disconnected(self):
        health = self.adapter.heartbeat()
        assert health.connected is False
        assert health.session_state == AdapterSessionState.DISCONNECTED

    def test_heartbeat_reports_degradation(self, mock_alpaca_client):
        mock_alpaca_client.get_account.side_effect = RuntimeError("Rate limited")
        self.adapter._client = mock_alpaca_client
        health = self.adapter.heartbeat()
        assert health.connected is False
        assert len(health.degradation) > 0


class TestAlpacaAdapterPlaceOrder:
    """Tests for order placement with all order types."""

    def setup_method(self):
        self.adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")
        self.mock_order = MagicMock()
        self.mock_order.id = "uuid-1234"
        self._session_patch = patch.object(AlpacaAdapter, '_in_regular_session', return_value=True)
        self._session_patch.start()

    def teardown_method(self):
        self._session_patch.stop()

    def _make_intent(self, **overrides) -> ApprovedOrderIntent:
        params = dict(
            risk_decision_id="rd-1",
            intent_id="int-1",
            client_order_id="co-1",
            instrument_id="AAPL",
            side="BUY",
            quantity="100",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="v1",
            price=None,
            stop_price=None,
        )
        params.update(overrides)
        return ApprovedOrderIntent(**params)

    def test_place_market_order(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.return_value = self.mock_order
        intent = self._make_intent()
        result = self.adapter.place_order(intent)
        assert result.accepted is True
        assert result.broker_order_id is not None
        assert result.broker_order_id.id == "uuid-1234"

    def test_place_limit_order(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.return_value = self.mock_order
        intent = self._make_intent(order_type="LIMIT", price="150.00")
        result = self.adapter.place_order(intent)
        assert result.accepted is True

    def test_place_stop_order(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.return_value = self.mock_order
        intent = self._make_intent(order_type="STOP", stop_price="145.00")
        result = self.adapter.place_order(intent)
        assert result.accepted is True

    def test_place_stop_limit_order(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.return_value = self.mock_order
        intent = self._make_intent(order_type="STOP_LIMIT", stop_price="145.00", price="146.00")
        result = self.adapter.place_order(intent)
        assert result.accepted is True

    def test_order_rejected_by_broker(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.side_effect = RuntimeError("Insufficient buying power")
        intent = self._make_intent()
        result = self.adapter.place_order(intent)
        assert result.accepted is False
        assert "Insufficient" in result.rejection_reason

    def test_sell_order(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.return_value = self.mock_order
        intent = self._make_intent(side="SELL")
        result = self.adapter.place_order(intent)
        assert result.accepted is True

    def test_unsupported_order_type(self, mock_alpaca_client):
        intent = self._make_intent(order_type="TRAILING_STOP")
        result = self.adapter.place_order(intent)
        assert result.accepted is False

    def test_client_order_id_passed_through(self, mock_alpaca_client):
        mock_alpaca_client.submit_order.return_value = self.mock_order
        intent = self._make_intent()
        self.adapter.place_order(intent)
        call_kwargs = mock_alpaca_client.submit_order.call_args[0][0]
        assert call_kwargs.client_order_id == "co-1"


class TestAlpacaAdapterCancelModify:
    """Tests for cancel and modify operations."""

    def setup_method(self):
        self.adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")
        self.order_id = BrokerOrderId(id="uuid-5678")

    def test_cancel_accepted(self, mock_alpaca_client):
        mock_alpaca_client.cancel_order_by_id.return_value = None
        result = self.adapter.cancel(self.order_id)
        assert result.accepted is True
        assert result.broker_order_id.id == "uuid-5678"

    def test_cancel_failure(self, mock_alpaca_client):
        mock_alpaca_client.cancel_order_by_id.side_effect = RuntimeError("Order not found")
        result = self.adapter.cancel(self.order_id)
        assert result.accepted is False

    def test_modify_accepted(self, mock_alpaca_client):
        mock_alpaca_client.replace_order_by_id.return_value = MagicMock(id="uuid-9999")
        amendment = OrderAmendment(quantity="200")
        result = self.adapter.modify(self.order_id, amendment)
        assert result.accepted is True
        assert result.broker_order_id.id == "uuid-9999"

    def test_modify_failure(self, mock_alpaca_client):
        mock_alpaca_client.replace_order_by_id.side_effect = RuntimeError("Invalid amendment")
        amendment = OrderAmendment(price="999")
        result = self.adapter.modify(self.order_id, amendment)
        assert result.accepted is False


class TestAlpacaAdapterQueries:
    """Tests for position, balance, order, and fill queries."""

    def setup_method(self):
        self.adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")
        self.account_id = "test-account-1"

    def test_positions_empty(self, mock_alpaca_client):
        mock_alpaca_client.get_all_positions.return_value = []
        snapshot = self.adapter.positions(self.account_id)
        assert isinstance(snapshot, BrokerPositionSnapshot)
        assert snapshot.positions == []

    def test_positions_with_data(self, mock_alpaca_client):
        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_alpaca_client.get_all_positions.return_value = [mock_position]

        snapshot = self.adapter.positions(self.account_id)
        assert len(snapshot.positions) == 1
        assert snapshot.positions[0].instrument_id == "AAPL"
        assert snapshot.positions[0].quantity == 100

    def test_positions_short(self, mock_alpaca_client):
        mock_position = MagicMock()
        mock_position.symbol = "SPY"
        mock_position.side = "short"
        mock_position.qty = "50"
        mock_alpaca_client.get_all_positions.return_value = [mock_position]

        snapshot = self.adapter.positions(self.account_id)
        assert snapshot.positions[0].side == "SELL"
        assert snapshot.positions[0].quantity == 50

    def test_positions_failure(self, mock_alpaca_client):
        mock_alpaca_client.get_all_positions.side_effect = RuntimeError("Network error")
        with pytest.raises(AdapterError, match="Failed to fetch positions"):
            self.adapter.positions(self.account_id)

    def test_holdings(self, mock_alpaca_client):
        mock_account = MagicMock()
        mock_account.cash = "50000"
        mock_account.portfolio_value = "150000"
        mock_account.buying_power = "100000"
        mock_account.equity = "150000"
        mock_account.currency = "USD"
        mock_alpaca_client.get_account.return_value = mock_account

        snapshot = self.adapter.holdings(self.account_id)
        assert isinstance(snapshot, BrokerBalanceSnapshot)
        assert snapshot.account_id == self.account_id
        assert snapshot.currency == "USD"

    def test_holdings_failure(self, mock_alpaca_client):
        mock_alpaca_client.get_account.side_effect = RuntimeError("API error")
        with pytest.raises(AdapterError, match="Failed to fetch holdings"):
            self.adapter.holdings(self.account_id)

    def test_queries_not_implemented(self, mock_alpaca_client):
        with pytest.raises(AdapterError, match="not yet implemented"):
            self.adapter.quotes(InstrumentSet(instrument_ids=["AAPL"]))

    def test_orders(self, mock_alpaca_client):
        mock_order = MagicMock()
        mock_order.id = "ord-1"
        mock_order.symbol = "AAPL"
        mock_order.side = "buy"
        mock_order.qty = "100"
        mock_order.filled_qty = "50"
        mock_order.limit_price = "150.00"
        mock_order.status = MagicMock(value="partially_filled")
        mock_order.created_at = "2026-07-14T00:00:00Z"
        mock_order.updated_at = "2026-07-14T01:00:00Z"
        mock_alpaca_client.get_orders.return_value = [mock_order]

        window = QueryWindow(start="2026-07-01T00:00:00Z", end="2026-07-14T23:59:59Z")
        snapshot = self.adapter.orders(self.account_id, window)
        assert len(snapshot.orders) == 1
        assert snapshot.orders[0].instrument_id == "AAPL"
        assert snapshot.orders[0].status == "partially_filled"

    def test_fills(self, mock_alpaca_client):
        mock_activity = MagicMock()
        mock_activity.id = "fill-1"
        mock_activity.order_id = "ord-1"
        mock_activity.symbol = "AAPL"
        mock_activity.side = "buy"
        mock_activity.qty = "100"
        mock_activity.price = "150.00"
        mock_activity.fees = "1.50"
        mock_activity.transaction_time = "2026-07-14T00:00:00Z"
        mock_alpaca_client.get_account_activities.return_value = [mock_activity]

        window = QueryWindow(start="2026-07-01T00:00:00Z", end="2026-07-14T23:59:59Z")
        snapshot = self.adapter.fills(self.account_id, window)
        assert len(snapshot.fills) == 1
        assert snapshot.fills[0].instrument_id == "AAPL"
        assert snapshot.fills[0].quantity == "100"


class TestAlpacaAdapterSessionLifecycle:
    """Tests covering the session lifecycle per Broker.spec.md state diagram."""

    def setup_method(self):
        self.adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")

    def test_disconnected_before_authenticate(self):
        assert self.adapter._session is None

    def test_disconnected_to_connected(self, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = MagicMock(status="ACTIVE")
        session = self.adapter.authenticate()
        assert session.state == AdapterSessionState.CONNECTED

    def test_auth_failure_stays_disconnected(self, mock_alpaca_client):
        mock_alpaca_client.get_account.side_effect = RuntimeError("Invalid credentials")
        with pytest.raises(AdapterError):
            self.adapter.authenticate()
        assert self.adapter._session.state == AdapterSessionState.DISCONNECTED


class TestAlpacaAdapterSessionHours:
    """Tests for US regular-session gate and daily order limits."""

    def setup_method(self):
        self.adapter = AlpacaAdapter(api_key="test_key", secret_key="test_secret")

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_rejects_outside_session_weekend(self, mock_dt):
        # Sunday 12:00 UTC → outside session (weekend)
        mock_dt.now.return_value = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        assert self.adapter._in_regular_session() is False

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_rejects_early_morning_edt(self, mock_dt):
        # Wednesday 11:00 UTC = 7:00 AM EDT → before open
        mock_dt.now.return_value = datetime(2026, 7, 15, 11, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        assert self.adapter._in_regular_session() is False

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_accepts_session_hours_edt(self, mock_dt):
        # Wednesday 14:00 UTC = 10:00 AM EDT → in session
        mock_dt.now.return_value = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        assert self.adapter._in_regular_session() is True

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_rejects_after_close_edt(self, mock_dt):
        # Wednesday 21:00 UTC = 5:00 PM EDT → after close
        mock_dt.now.return_value = datetime(2026, 7, 15, 21, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        assert self.adapter._in_regular_session() is False

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_accepts_session_hours_est(self, mock_dt):
        # January Wednesday 15:00 UTC = 10:00 AM EST → in session
        mock_dt.now.return_value = datetime(2026, 1, 14, 15, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        assert self.adapter._in_regular_session() is True

    def test_check_daily_order_limit_under_limit(self):
        result = self.adapter._check_daily_order_limit()
        assert result is None

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_check_daily_order_limit_exceeded(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        self.adapter._max_daily_orders = 1
        self.adapter._daily_order_date = "2026-07-15"
        self.adapter._daily_order_count = 1
        result = self.adapter._check_daily_order_limit()
        assert result is not None
        assert result.accepted is False
        assert "Daily order limit" in result.rejection_reason

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_place_order_rejected_outside_session(self, mock_dt, mock_alpaca_client):
        # Wednesday 11:00 UTC = 7:00 AM EDT → before open
        mock_dt.now.return_value = datetime(2026, 7, 15, 11, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        mock_dt.date.today.return_value = mock_dt.now.return_value.date()
        mock_alpaca_client.submit_order.return_value = MagicMock(id="uuid-1234")

        intent = ApprovedOrderIntent(
            risk_decision_id="rd-1", intent_id="int-1", client_order_id="co-1",
            instrument_id="AAPL", side="BUY", quantity="1", order_type="MARKET",
            time_in_force="DAY", risk_profile_version="v1", price=None, stop_price=None,
        )
        result = self.adapter.place_order(intent)
        assert result.accepted is False
        assert "outside US regular session" in result.rejection_reason

    @patch("titan.execution.alpaca_adapter.datetime")
    def test_daily_order_limit_reached(self, mock_dt, mock_alpaca_client):
        # Wednesday 14:00 UTC = 10:00 AM EDT → in session
        mock_dt.now.return_value = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw) if a else mock_dt.now.return_value
        mock_dt.date.today.return_value = mock_dt.now.return_value.date()
        mock_alpaca_client.submit_order.return_value = MagicMock(id="uuid-1234")

        # Fill the daily limit
        adapter = AlpacaAdapter(api_key="test_key", secret_key="test_key")
        adapter._max_daily_orders = 2
        for i in range(2):
            intent = ApprovedOrderIntent(
                risk_decision_id="rd-1", intent_id=f"int-{i}", client_order_id=f"co-{i}",
                instrument_id="AAPL", side="BUY", quantity="1", order_type="MARKET",
                time_in_force="DAY", risk_profile_version="v1", price=None, stop_price=None,
            )
            result = adapter.place_order(intent)
            assert result.accepted is True

        # Third order exceeds limit
        overflow = ApprovedOrderIntent(
            risk_decision_id="rd-1", intent_id="int-3", client_order_id="co-3",
            instrument_id="AAPL", side="BUY", quantity="1", order_type="MARKET",
            time_in_force="DAY", risk_profile_version="v1", price=None, stop_price=None,
        )
        result = adapter.place_order(overflow)
        assert result.accepted is False
        assert "Daily order limit" in result.rejection_reason
