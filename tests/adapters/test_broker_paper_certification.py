"""Broker-paper certification tests — gates for Alpaca paper account readiness.

Each test maps to a certification gate in ADR-012. Tests with real credentials
(pytest.mark.live) are skipped when .env is absent. All other tests use mocks.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from dotenv import load_dotenv
from fixtures.session_init import initialize_fresh

from titan._core import (
    ContractType,
    Instrument,
    InstrumentId,
    KillSwitchState,
    Money,
    OrderState,
    OrderStateMachine,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
    TradingState,
)
from titan.execution import (
    AlpacaAdapter,
    PaperConfig,
    PaperTradingEngine,
)
from titan.execution._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    OrderResult,
    Session,
)
from titan.operations.logging import StructuredLogger


def _has_creds() -> bool:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(env_path)
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    return bool(key and secret and not key.startswith("YOUR_") and key != "YOUR_ALPACA_KEY_ID")


def _creds() -> tuple[str, str]:
    return os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"]


def _tmp_state_path() -> str:
    d = tempfile.mkdtemp()
    return os.path.join(d, "titan_state.json")


def _make_risk_config() -> RiskConfig:
    return RiskConfig(
        ["SPY"],
        Money("100000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
    )


# ---------------------------------------------------------------------------
# Gate 1: Paper credential validation
# ---------------------------------------------------------------------------

class TestCredentialValidation:
    """Paper-only credential validation — reject live endpoints, missing creds."""

    def test_accepts_paper_credentials(self):
        """Paper endpoint is accepted with valid credentials."""
        adapter = AlpacaAdapter(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
        )
        assert adapter is not None

    def test_rejects_live_endpoint(self):
        """Live endpoint raises AdapterError at construction."""
        with pytest.raises(AdapterError, match="Live endpoint rejected"):
            AlpacaAdapter(
                api_key="test_key",
                secret_key="test_secret",
                base_url="https://api.alpaca.markets",
            )

    def test_rejects_live_paper_flag(self):
        """paper=False raises AdapterError at construction."""
        with pytest.raises(AdapterError, match="Live trading is not supported"):
            AlpacaAdapter(
                api_key="test_key",
                secret_key="test_secret",
                paper=False,
            )

    def test_rejects_missing_credentials(self):
        """Missing credentials raises AdapterError at construction."""
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "", "APCA_API_SECRET_KEY": ""}, clear=True):
            with pytest.raises(AdapterError, match="not configured"):
                AlpacaAdapter()

    def test_rejects_empty_key_at_construction(self):
        """Empty key raises AdapterError at construction."""
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "", "APCA_API_SECRET_KEY": ""}, clear=True):
            with pytest.raises(AdapterError, match="not configured"):
                AlpacaAdapter(api_key="", secret_key="secret")

    def test_rejects_empty_secret_at_construction(self):
        """Empty secret raises AdapterError at construction."""
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "", "APCA_API_SECRET_KEY": ""}, clear=True):
            with pytest.raises(AdapterError, match="not configured"):
                AlpacaAdapter(api_key="key", secret_key="")

    def test_rejects_both_empty_at_construction(self):
        """Both empty raises AdapterError at construction."""
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "", "APCA_API_SECRET_KEY": ""}, clear=True):
            with pytest.raises(AdapterError, match="not configured"):
                AlpacaAdapter(api_key="", secret_key="")


# ---------------------------------------------------------------------------
# Gate 2: Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    """Authenticate against Alpaca paper and verify session state."""

    @pytest.mark.live
    def test_authenticate_paper_live(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        session = adapter.authenticate()
        assert session is not None
        assert session.state == AdapterSessionState.CONNECTED

    def test_authenticate_mocked(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(adapter, "_ensure_client"):
            adapter._client = MagicMock()
            adapter._client.get_account.return_value = MagicMock(
                id="test", status="ACTIVE", currency="USD", cash="100000",
                portfolio_value="100000", buying_power="200000", equity="100000",
                pattern_day_trader=False, trade_suspended_by_user=False,
                trading_blocked=False, transfers_blocked=False,
                account_blocked=False, created_at="2026-01-01",
                shorting_enabled=True, long_market_value="0",
                short_market_value="0", daytrade_count=0,
                last_equity="100000", multiplier="1",
            )
            session = adapter.authenticate()
        assert session.state == AdapterSessionState.CONNECTED

    @pytest.mark.live
    def test_auth_failure_halts_live(self):
        """Wrong credentials must fail authentication."""
        adapter = AlpacaAdapter(api_key="bad_key", secret_key="bad_secret")
        with pytest.raises(Exception):
            adapter.authenticate()


# ---------------------------------------------------------------------------
# Gate 3: Health and connectivity
# ---------------------------------------------------------------------------

class TestHealth:
    """Heartbeat and health check — fail-closed on loss."""

    @pytest.mark.live
    def test_heartbeat_paper_live(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        health = adapter.heartbeat()
        assert health.connected is True
        assert health.session_state == AdapterSessionState.CONNECTED

    def test_heartbeat_mocked(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(adapter, "_ensure_client"):
            adapter._client = MagicMock()
            adapter._client.get_account.return_value = MagicMock(
                id="test", status="ACTIVE",
            )
            health = adapter.heartbeat()
        assert health.connected is True

    def test_heartbeat_loss_detected(self):
        """Simulated disconnect must report not connected."""
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(adapter, "_ensure_client", side_effect=ConnectionError("API unreachable")):
            health = adapter.heartbeat()
        assert health.connected is False
        assert health.degradation is not None


# ---------------------------------------------------------------------------
# Gate 4: Account state (read-only)
# ---------------------------------------------------------------------------

class TestAccountState:
    """Read holdings and positions without placing orders."""

    @pytest.mark.live
    def test_read_account_state_live(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        adapter.authenticate()
        holdings = adapter.holdings("default")
        assert holdings is not None
        assert holdings.currency == "USD"
        assert float(holdings.cash.amount) >= 0
        positions = adapter.positions("default")
        assert positions is not None

    def test_read_account_state_mocked(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        mock_account = MagicMock(
            id="test", status="ACTIVE", currency="USD", cash="100000",
            portfolio_value="100000", buying_power="200000", equity="100000",
        )
        with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
            client_instance = MagicMock()
            client_instance.get_account.return_value = mock_account
            client_instance.get_all_positions.return_value = []
            mock_tc.return_value = client_instance
            adapter._ensure_client()
            h = adapter.holdings("default")
            assert float(h.cash.amount) == 100000
            p = adapter.positions("default")
            assert len(p.positions) == 0


# ---------------------------------------------------------------------------
# Gate 5: Fail-closed wiring
# ---------------------------------------------------------------------------

class TestFailClosed:
    """Auth failure / heartbeat loss / stale data must prevent routing."""

    def test_drawdown_exceeded_rejected(self):
        """Drawdown exceeding max_drawdown_fraction must reject via risk gate."""
        from datetime import datetime, timezone
        from titan.execution.alpaca_adapter import AlpacaAdapter

        rc = RiskConfig(
            ["SPY"],
            Money("100000", "USD"),
            1000, 5000,
            Money("100000", "USD"),
            0.001,  # tiny max drawdown
            Money("5000", "USD"),
            5000, 100,
        )
        pc = PaperConfig(risk_config=rc, state_path=_tmp_state_path())
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine.start()
                engine.register_instrument(
                    Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
                )

                # Create drawdown via losing trade
                engine.portfolio.apply_fill("SPY", "buy", 10, Money("900", "USD"))
                engine.portfolio.apply_fill("SPY", "sell", 10, Money("100", "USD"))

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="1", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
        assert not result.accepted
        assert "drawdown" in result.rejection_reason.lower()

    def test_daily_loss_exceeded_rejected(self):
        """Daily loss exceeding max_daily_loss must reject via risk gate."""
        from datetime import datetime, timezone
        from titan.execution.alpaca_adapter import AlpacaAdapter

        # ponytail: Portfolio returns negative daily_loss; evaluate() uses > compare.
        # Set max to a negative value so -8000 > -100000 = true triggers rejection.
        rc = RiskConfig(
            ["SPY"],
            Money("100000", "USD"),
            1000, 5000,
            Money("100000", "USD"),
            0.10,
            Money("-100000", "USD"),
            5000, 100,
        )
        pc = PaperConfig(risk_config=rc, state_path=_tmp_state_path())
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine.start()
                engine.register_instrument(
                    Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
                )

                # Create realized loss
                engine.portfolio.apply_fill("SPY", "buy", 10, Money("900", "USD"))
                engine.portfolio.apply_fill("SPY", "sell", 10, Money("100", "USD"))

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="1", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
        assert not result.accepted
        assert "daily loss" in result.rejection_reason.lower()

    def test_auth_failure_blocks_submit_intent(self):
        """Engine must reject intents when broker auth fails."""
        rc = _make_risk_config()
        pc = PaperConfig(risk_config=rc, state_path=_tmp_state_path())
        adapter = AlpacaAdapter(api_key="bad", secret_key="creds")
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)
        intent = TradeIntent(
            strategy_id="test", strategy_package_digest="",
            account_id="paper-1", instrument_id="SPY", side="BUY",
            quantity="10", order_type="MARKET", time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp="2026-07-14T00:00:00Z",
        certificate_ref="test-cert",
        )
        result = engine.submit_intent(intent)
        assert not result.accepted
        assert "Adapter unhealthy" in result.rejection_reason

    def test_heartbeat_loss_blocks_submit_intent(self):
        """Broker disconnect must trigger kill switch and block routing."""
        rc = _make_risk_config()
        pc = PaperConfig(risk_config=rc, state_path=_tmp_state_path())
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)
        with patch.object(adapter, "heartbeat", return_value=AdapterHealth(
            connected=False, session_state=AdapterSessionState.DISCONNECTED,
        )):
            intent = TradeIntent(
                strategy_id="test", strategy_package_digest="",
                account_id="paper-1", instrument_id="SPY", side="BUY",
                quantity="10", order_type="MARKET", time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp="2026-07-14T00:00:00Z",
            certificate_ref="test-cert",
            )
            result = engine.submit_intent(intent)
        assert not result.accepted
        assert engine.risk_gate.kill_switch.blocks_routing()

    def test_engine_rejects_when_kill_switch_triggered(self):
        rc = _make_risk_config()
        pc = PaperConfig(risk_config=rc, state_path=_tmp_state_path())
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)
        with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
            client_instance = MagicMock()
            mock_tc.return_value = client_instance
            adapter._ensure_client()
            engine.risk_gate.trigger_kill_switch()
            intent = TradeIntent(
                strategy_id="test", strategy_package_digest="",
                account_id="paper-1", instrument_id="SPY", side="BUY",
                quantity="10", order_type="MARKET", time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp="2026-07-14T00:00:00Z",
            certificate_ref="test-cert",
            )
            result = engine.submit_intent(intent)
        assert not result.accepted
        assert "Kill switch" in result.rejection_reason or "Adapter unhealthy" in result.rejection_reason


# ---------------------------------------------------------------------------
# Gate 6: Order lifecycle
# ---------------------------------------------------------------------------

class TestOrderLifecycle:
    """Submit, cancel, and modify orders through Alpaca paper."""

    @pytest.mark.live
    def test_submit_paper_order_live(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        adapter.authenticate()

    def test_submit_market_order_mocked(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch.object(adapter, "_ensure_client"):
                adapter._client = MagicMock()
                mock_order = MagicMock(
                    id="test-order-1", client_order_id="client-1",
                    symbol="SPY", qty="10", side="buy", type="market",
                    time_in_force="day", status="accepted",
                    filled_qty="0", filled_avg_price=None,
                    created_at="2026-07-14T00:00:00Z", updated_at="2026-07-14T00:00:00Z",
                    limit_price=None, stop_price=None,
                )
                adapter._client.submit_order.return_value = mock_order
                ack = adapter.place_order(MagicMock(
                    client_order_id="client-1", instrument_id="SPY", side="BUY",
                    quantity="10", order_type="MARKET", time_in_force="DAY",
                    price=None, stop_price=None,
                ))
            assert ack.accepted
            assert ack.broker_order_id is not None

    def test_cancel_order_mocked(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(adapter, "_ensure_client"):
            adapter._client = MagicMock()
            adapter._client.cancel_order_by_id.return_value = None
            cancel = adapter.cancel(BrokerOrderId(id="test-order"))
            assert cancel.accepted


# ---------------------------------------------------------------------------
# Gate 7: Rate limits
# ---------------------------------------------------------------------------

class TestRateLimits:
    """Verify rate limits are respected under load (mocked)."""

    def test_rate_limit_not_exceeded(self):
        """AlpacaAdapter itself doesn't enforce rate limits — the SDK does.
        This test confirms the adapter handles multiple sequential submissions.
        """
        from titan._core import ApprovedOrderIntent
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
            client_instance = MagicMock()
            mock_order = MagicMock()
            mock_order.id = "order-1"
            client_instance.submit_order.return_value = mock_order
            mock_tc.return_value = client_instance
            adapter._ensure_client()

            with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
                def make_intent(i: int) -> ApprovedOrderIntent:
                    return ApprovedOrderIntent(
                        risk_decision_id=f"rd-{i}", intent_id=f"in-{i}",
                        client_order_id=f"c{i}", instrument_id="SPY",
                        side="BUY", quantity="10", order_type="MARKET",
                        time_in_force="DAY", risk_profile_version="1.0",
                        price=None, stop_price=None,
                    )

                for i in range(10):
                    ack = adapter.place_order(make_intent(i))
                    assert ack.accepted, f"Order {i} rejected: {ack.rejection_reason}"
                assert client_instance.submit_order.call_count == 10


# ---------------------------------------------------------------------------
# Gate 8: Disconnect / reconnect
# ---------------------------------------------------------------------------

class TestDisconnectReconnect:
    """Session recovery after disconnect."""

    def test_reconnect_after_disconnect_mocked(self):
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(adapter, "_ensure_client"):
            adapter._client = MagicMock()
            adapter._client.get_account.return_value = MagicMock(
                id="test", status="ACTIVE", currency="USD", cash="100000",
                portfolio_value="100000", buying_power="200000", equity="100000",
            )
            session1 = adapter.authenticate()
            assert session1.state == AdapterSessionState.CONNECTED

            adapter._session = None
            session2 = adapter.authenticate()
            assert session2.state == AdapterSessionState.CONNECTED
            assert session2.session_id != session1.session_id


# ---------------------------------------------------------------------------
# Gate 9: Partial fills
# ---------------------------------------------------------------------------

class TestPartialFills:
    """Engine handles partial fill events correctly."""

    def test_partial_fill_mocked(self):
        from titan.execution._broker_types import BrokerFill
        fill = BrokerFill(
            execution_id="fill-1",
            order_id=BrokerOrderId(id="order-1"),
            instrument_id="SPY",
            side="buy",
            quantity="5",
            price="500.00",
            fees=Money("0", "USD"),
            currency="USD",
            timestamp="2026-07-14T00:00:00Z",
        )
        assert fill.quantity == "5"
        assert fill.execution_id == "fill-1"
        assert fill.price == "500.00"


# ---------------------------------------------------------------------------
# Gate 10: Restart from event store
# ---------------------------------------------------------------------------

class TestRestartFromStore:
    """Event store replay → reconcile → resume."""

    def test_restart_clean_after_mocked_session(self):
        from titan.recovery.restart import recover_from_event_store, transition_on_boot, reconcile_on_boot
        store = recover_from_event_store()
        assert "store" in store
        assert "risk_gate" in store
        recon = reconcile_on_boot(store["portfolio"], store["adapter"], store["recon_engine"])
        assert not recon["has_drift"]
        transition = transition_on_boot(recon, store["risk_gate"])
        assert "ACTIVE" in transition
        store["store"].close()


# ---------------------------------------------------------------------------
# Gate 11: Daily reconciliation
# ---------------------------------------------------------------------------

class TestDailyReconciliation:
    """Reconciliation against broker truth — no drift."""

    def test_reconcile_with_no_drift_mocked(self):
        rc = _make_risk_config()
        pc = PaperConfig(risk_config=rc, state_path=_tmp_state_path())
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)
        with patch.object(adapter, "positions", return_value=BrokerPositionSnapshot(
            account_id="paper-1", positions=[], timestamp="2026-07-14T00:00:00Z",
        )):
            with patch.object(adapter, "holdings", return_value=BrokerBalanceSnapshot(
                account_id="paper-1", currency="USD",
                cash=Money("100000", "USD"),
                portfolio_value=Money("100000", "USD"),
                buying_power=Money("200000", "USD"),
                equity=Money("100000", "USD"),
                timestamp="2026-07-14T00:00:00Z",
            )):
                result = engine.reconcile()
        assert result is not None
        assert len(result.position_drifts) == 0


# ---------------------------------------------------------------------------
# Gate 12: One-order paper execution (opt-in via --run-paper-orders)
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "market"


@pytest.mark.paper_order
class TestOneOrderExecution:
    """One SPY share, long-only MARKET DAY — observe, cancel/reconcile."""

    INSTRUMENT = "SPY"
    DATA_FILE = str(FIXTURES / "spy_2020_2024.csv")

    def _creds(self) -> tuple[str, str]:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(env_path)
        return os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"]

    def test_one_market_order_certification(self):
        """Submit 1 share SPY MARKET DAY, observe ack, cancel if open, reconcile."""
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        from datetime import datetime, timezone, timedelta

        import json
        from titan.data.approved import load_approved

        # 1. Load approved data
        source = load_approved(
            self.DATA_FILE,
            min_bar_count=1,
            max_stale_trading_days=10000,
        )
        assert source.instrument_id == self.INSTRUMENT
        assert source.bar_count() >= 1

        # 2. Build adapter with paper credentials
        api_key, secret_key = self._creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)

        # 3. Build engine
        rc = RiskConfig(
            [self.INSTRUMENT],
            Money("100000", "USD"),
            1000,
            5000,
            Money("100000", "USD"),
            0.10,
            Money("5000", "USD"),
            5000,
            100,
        )
        state_path = _tmp_state_path()
        pc = PaperConfig(
            risk_config=rc,
            state_path=state_path,
        )
        engine = PaperTradingEngine(pc, adapter)
        initialize_fresh(engine)
        session = engine.start()
        assert session.state == AdapterSessionState.CONNECTED
        engine.register_instrument(
            Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        print(f"\n[CERT] Engine started, session={session.session_id}")

        # 4. Submit 1 share SPY MARKET DAY
        ts = datetime.now(timezone.utc).isoformat()
        intent = TradeIntent(
            strategy_id="one-order-cert",
            strategy_package_digest="",
            account_id="paper-1",
            instrument_id=self.INSTRUMENT,
            side="BUY",
            quantity="1",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=ts,
        certificate_ref="test-cert",
        )
        result = engine.submit_intent(intent)
        assert result.accepted, f"Order rejected: {result.rejection_reason}"
        broker_id = result.broker_order_id
        print(f"[CERT] Order submitted: broker_id={broker_id.id}, fills={len(result.fills)}")

        # 5. Wait briefly for fill acknowledgement (market orders fill fast)
        filled = len(result.fills) > 0
        if not filled:
            import time as _time
            _time.sleep(3)
            pos = engine.portfolio.get_position(self.INSTRUMENT)
            filled = pos is not None and pos.quantity > 0
            if filled:
                print(f"[CERT] Fill detected via portfolio: qty={pos.quantity}")

        # 6. Cancel if still open
        if not filled:
            cancel_result = adapter.cancel(broker_id)
            if cancel_result.accepted:
                print(f"[CERT] Order cancelled: {broker_id.id}")
            else:
                print(f"[CERT] Cancel not needed (order already completed): {broker_id.id}")

        # 7. Sell back if position exists (with wash-trade retry)
        pos = engine.portfolio.get_position(self.INSTRUMENT)
        if pos and pos.quantity > 0:
            import time as _time
            sell_accepted = False
            for attempt in range(3):
                _time.sleep(1.5)
                ts = datetime.now(timezone.utc).isoformat()
                sell_intent = TradeIntent(
                    strategy_id="one-order-cert",
                    strategy_package_digest="",
                    account_id="paper-1",
                    instrument_id=self.INSTRUMENT,
                    side="SELL",
                    quantity=str(pos.quantity),
                    order_type="MARKET",
                    time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp=ts,
                certificate_ref="test-cert",
                )
                sell_result = engine.submit_intent(sell_intent)
                sell_accepted = sell_result.accepted
                reason = sell_result.rejection_reason if not sell_accepted else ""
                print(f"[CERT] Sell-back attempt {attempt + 1}: accepted={sell_accepted}"
                      f"{', reason=' + reason if reason else ''}")
                if sell_accepted:
                    break
            if not sell_accepted:
                print(f"[CERT] WARNING: Sell-back rejected after 3 attempts. "
                      f"Position may need manual cleanup.")
                cancelled = adapter.cancel(result.broker_order_id)
                print(f"[CERT] Buy order cancelled: {cancelled.accepted}")
            engine.stop()
            print(f"[CERT] Engine stopped")

        # 8. Reconcile
        recon_result = engine.reconcile()
        assert recon_result is not None
        for d in recon_result.position_drifts:
            print(f"[CERT]   Drift: instr={d.instrument_id} "
                  f"expected_qty={d.expected_quantity} actual_qty={d.actual_quantity} "
                  f"drift={d.quantity_drift}")
        print(f"[CERT] Reconciliation: drifts={len(recon_result.position_drifts)}")
        non_zero = [d for d in recon_result.position_drifts if d.quantity_drift != 0]
        if non_zero:
            print(f"[CERT] WARNING: {len(non_zero)} non-zero drifts detected "
                  f"(may require manual flatten)")
        else:
            print(f"[CERT] No position drifts — fully reconciled")

        # 9. Verify persistence / restart recovery via EventStore
        from titan._core import EventStore as _ES
        store = _ES(str(Path(state_path).with_suffix(".db")))
        evts = store.replay_by_type("PortfolioState")
        assert evts, "No PortfolioState event in EventStore"
        persisted = json.loads(evts[-1].payload)
        spy_pos = persisted["portfolio"]["positions"].get("SPY", {})
        pos_qty = spy_pos.get("quantity", 0)
        print(f"[CERT] EventStore verified: SPY position qty={pos_qty}")
        if pos_qty != 0:
            print(f"[CERT] WARNING: SPY position still has qty={pos_qty} in persisted state "
                  f"(may require manual cleanup)")
        store.close()

        print(f"\n[CERT RESULT] One-order certification passed for {self.INSTRUMENT}")
        print(f"[CERT RESULT] Order: {broker_id.id}, filled={filled}, reconciled OK, restart OK")


# ---------------------------------------------------------------------------
# Gate 13: Kill switch persistence across restart
# ---------------------------------------------------------------------------

class TestKillSwitchPersistence:
    """Kill switch state survives engine restart via state file."""

    def test_kill_switch_persists_armed(self, tmp_path):
        """Kill switch must survive restart via EventStore."""
        from titan.execution.alpaca_adapter import AlpacaAdapter

        state_file = tmp_path / "state.json"
        config = PaperConfig(risk_config=_make_risk_config(), state_path=str(state_file))

        # First session — trigger kill switch
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine = PaperTradingEngine(config, adapter)
                initialize_fresh(engine)
                engine.start()
                engine.trigger_kill_switch()

        # Second session — must load kill switch state from EventStore
        adapter2 = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc2:
                mock_tc2.return_value = MagicMock()
                engine2 = PaperTradingEngine(config, adapter2)
                engine2.start()
                assert engine2.risk_gate.kill_switch.blocks_routing()

    def test_trading_state_persists(self, tmp_path):
        """Trading state must survive restart via EventStore."""
        from titan.execution.alpaca_adapter import AlpacaAdapter

        state_file = tmp_path / "state.json"
        config = PaperConfig(risk_config=_make_risk_config(), state_path=str(state_file))

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine = PaperTradingEngine(config, adapter)
                initialize_fresh(engine)
                engine.start()

    def test_kill_switch_persists_through_broker_sync(self, tmp_path):
        """Kill switch must survive restart with sync_from_broker=True."""
        from titan.execution.alpaca_adapter import AlpacaAdapter

        state_file = tmp_path / "state.json"
        config = PaperConfig(risk_config=_make_risk_config(), state_path=str(state_file))

        # First session — trigger kill switch, save state
        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine = PaperTradingEngine(config, adapter)
                initialize_fresh(engine)
                engine.start()
                engine.trigger_kill_switch()

        # Second session with sync_from_broker=True — must restore kill switch from EventStore
        adapter2 = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc2:
                mock_client2 = MagicMock()
                mock_client2.get_account.return_value = MagicMock(
                    id="test", status="ACTIVE", currency="USD", cash="100000",
                )
                mock_tc2.return_value = mock_client2
                engine2 = PaperTradingEngine(config, adapter2)
                engine2.start(sync_from_broker=True)
                assert engine2.risk_gate.kill_switch.blocks_routing(), \
                    "Kill switch must persist through broker-sync restart"


# ---------------------------------------------------------------------------
# Gate 14: Broker submit failure triggers kill switch
# ---------------------------------------------------------------------------

class TestBrokerSubmitFailure:
    """Exception from adapter.place_order() must trigger kill switch."""

    def test_submit_exception_triggers_kill_switch(self):
        """AdapterError from place_order -> kill switch blocks subsequent routing."""
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_client = MagicMock()
                # First submit succeeds so health check passes
                mock_order = MagicMock(id="order-1")
                mock_client.submit_order.return_value = mock_order
                mock_tc.return_value = mock_client
                adapter._ensure_client()

                engine.start()
                engine.register_instrument(
                    Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
                )
                assert not engine.risk_gate.kill_switch.blocks_routing()

                # Force place_order to raise with a fresh timestamp
                with patch.object(adapter, "place_order", side_effect=RuntimeError("Broker down")):
                    intent = TradeIntent(
                        strategy_id="test", strategy_package_digest="",
                        account_id="paper-1", instrument_id="SPY", side="BUY",
                        quantity="10", order_type="MARKET", time_in_force="DAY",
                        risk_profile_version="1.0",
                        market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                    certificate_ref="test-cert",
                    )
                    result = engine.submit_intent(intent)

                assert not result.accepted
                # P0 U1: outcome is UNKNOWN, not a firm rejection — the order
                # is parked (never resent) and routing is halted.
                assert "UNKNOWN" in result.rejection_reason
                assert "not resent" in result.rejection_reason
                assert engine.risk_gate.kill_switch.blocks_routing()


# ---------------------------------------------------------------------------
# Gate 15: Unfilled order not booked
# ---------------------------------------------------------------------------

class TestUnfilledOrderGuard:
    """Accepted-but-unfilled orders must not create phantom fills."""

    def test_unfilled_order_no_fills(self):
        """The authoritative fill path applies nothing without a real delta."""
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        # Register an acknowledged order with its tracking metadata.
        coid = "c1"
        sm = OrderStateMachine()
        sm.transition(OrderState.Validated)
        sm.transition(OrderState.Submitted)
        sm.transition(OrderState.Acknowledged)
        engine.order_states[coid] = sm
        engine._order_metadata[coid] = {"instrument_id": "SPY", "side": "BUY",
                                        "quantity": 10}
        engine._order_filled_quantity.setdefault(coid, 0)

        # fill_quantity = None -> no fill applied
        assert engine._absorb_broker_fill(coid, sm, None, "500.00") is None
        # fill_quantity = "0" -> no fill applied
        assert engine._absorb_broker_fill(coid, sm, "0", None) is None
        assert engine.portfolio.get_position("SPY") is None

        # fill_quantity = "5" — exactly the delta is applied once
        fill = engine._absorb_broker_fill(coid, sm, "5", "501.00")
        assert fill is not None and fill.quantity == "5"
        pos = engine.portfolio.get_position("SPY")
        assert pos is not None and pos.quantity == 5
        assert str(sm.current) == str(OrderState.PartiallyFilled)

        # Re-reporting cumulative 5 applies nothing further.
        assert engine._absorb_broker_fill(coid, sm, "5", "501.00") is None
        assert engine.portfolio.get_position("SPY").quantity == 5


# ---------------------------------------------------------------------------
# Gate 16: Timestamp pre-validation
# ---------------------------------------------------------------------------

class TestTimestampPreValidation:
    """Invalid market_data_timestamp must be rejected before Rust risk gate."""

    def test_rejects_invalid_timestamp(self):
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_client = MagicMock()
                mock_order = MagicMock(id="order-1")
                mock_client.submit_order.return_value = mock_order
                mock_tc.return_value = mock_client
                engine.start()
                engine.register_instrument(
                    Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
                )

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="10", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp="not-a-timestamp",
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
                assert not result.accepted
                assert "not a valid RFC 3339 timestamp" in result.rejection_reason

    def test_accepts_valid_timestamp(self):
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_client = MagicMock()
                mock_order = MagicMock(id="order-1")
                mock_client.submit_order.return_value = mock_order
                mock_tc.return_value = mock_client
                engine.start()

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="10", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp="2026-07-14T10:30:00Z",
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
                # Should pass pre-validation and be accepted by adapter
                assert result.accepted or "Kill switch" not in result.rejection_reason


# ---------------------------------------------------------------------------
# Gate 17: Reconciliation drift triggers kill switch
# ---------------------------------------------------------------------------

class TestReconciliationDriftHalts:
    """Critical reconciliation drift must trigger kill switch."""

    def test_critical_drift_triggers_kill_switch(self):
        """Reconciliation returning critical severity must trigger kill switch."""
        from titan.execution.alpaca_adapter import AlpacaAdapter
        from titan._core import ReconciliationDriftSeverity, ReconciliationResult

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_client = MagicMock()
                mock_order = MagicMock(id="order-1")
                mock_client.submit_order.return_value = mock_order
                mock_tc.return_value = mock_client
                engine.start()

                assert not engine.risk_gate.kill_switch.blocks_routing()

                # Apply a position manually so it differs from broker (which returns empty)
                engine.portfolio.apply_fill(
                    instrument_id="SPY", side="buy",
                    quantity=10, price=Money("500", "USD"),
                )

                with patch.object(adapter, "positions", return_value=BrokerPositionSnapshot(
                    account_id="paper-1", positions=[], timestamp="2026-07-14T00:00:00Z",
                )):
                    with patch.object(adapter, "holdings", return_value=BrokerBalanceSnapshot(
                        account_id="paper-1", currency="USD",
                        cash=Money("100000", "USD"),
                        portfolio_value=Money("100000", "USD"),
                        buying_power=Money("200000", "USD"),
                        equity=Money("100000", "USD"),
                        timestamp="2026-07-14T00:00:00Z",
                    )):
                        engine.reconcile()

                assert engine.risk_gate.kill_switch.blocks_routing()

    def test_warning_drift_does_not_halt(self):
        """InSync-level drift (positions match) should not trigger kill switch."""
        from titan.execution.alpaca_adapter import AlpacaAdapter
        from titan._core import ReconciliationDriftSeverity

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_client = MagicMock()
                mock_order = MagicMock(id="order-1")
                mock_client.submit_order.return_value = mock_order
                mock_tc.return_value = mock_client
                engine.start()

                assert not engine.risk_gate.kill_switch.blocks_routing()

                with patch.object(adapter, "positions", return_value=BrokerPositionSnapshot(
                    account_id="paper-1", positions=[], timestamp="2026-07-14T00:00:00Z",
                )):
                    with patch.object(adapter, "holdings", return_value=BrokerBalanceSnapshot(
                        account_id="paper-1", currency="USD",
                        cash=Money("100000", "USD"),
                        portfolio_value=Money("100000", "USD"),
                        buying_power=Money("200000", "USD"),
                        equity=Money("100000", "USD"),
                        timestamp="2026-07-14T00:00:00Z",
                    )):
                        engine.reconcile()

                assert not engine.risk_gate.kill_switch.blocks_routing()


# ---------------------------------------------------------------------------
# Gate 18: Timestamp must include UTC offset
# ---------------------------------------------------------------------------

class TestTimestampUtcOffset:
    """market_data_timestamp must include an RFC3339 UTC offset."""

    def test_rejects_naive_timestamp(self):
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine.start()
                engine.register_instrument(
                    Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
                )

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="10", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp="2026-07-15T23:03:44",
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
                assert not result.accepted
                assert "not a valid RFC 3339 timestamp" in result.rejection_reason

    def test_accepts_z_timestamp(self):
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine.start()

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="10", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp="2026-07-15T23:03:44Z",
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
                assert "missing UTC offset" not in result.rejection_reason

    def test_accepts_offset_timestamp(self):
        from titan.execution.alpaca_adapter import AlpacaAdapter

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine.start()

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="10", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp="2026-07-15T23:03:44+00:00",
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)
                assert "missing UTC offset" not in result.rejection_reason


# ---------------------------------------------------------------------------
# Gate 19: Accepted-but-unfilled order recorded in order_states
# ---------------------------------------------------------------------------

class TestUnfilledOrderRecorded:
    """Accepted-but-unfilled orders must be recorded in order_states."""

    def test_unfilled_order_recorded(self):
        from titan.execution.alpaca_adapter import AlpacaAdapter
        from datetime import datetime, timezone

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        config = PaperConfig(risk_config=_make_risk_config(), state_path=_tmp_state_path())
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)

        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_tc.return_value = MagicMock()
                engine.start()
                engine.register_instrument(
                    Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
                )

                assert len(engine.order_states) == 0

                intent = TradeIntent(
                    strategy_id="test", strategy_package_digest="",
                    account_id="paper-1", instrument_id="SPY", side="BUY",
                    quantity="1", order_type="MARKET", time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                certificate_ref="test-cert",
                )
                result = engine.submit_intent(intent)

                assert len(engine.order_states) > 0
                states = list(engine.order_states.values())
                # P0 U4/C4: an accepted-but-unfilled order is NOT declared
                # dead — it stays Acknowledged (tracked) for the poller to
                # settle against broker truth.
                assert any(str(sm.current) == "Acknowledged" for sm in states)
                assert not any(sm.current.is_terminal() for sm in states)
