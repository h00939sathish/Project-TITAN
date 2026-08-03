"""Broker timeout during order submit — AdapterError raised, reconcile resolves."""
import pytest
from titan._core import ApprovedOrderIntent, Side, PortfolioEngine, Money, ReconciliationEngine, ReconciliationConfig

from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality
from titan.execution._broker_types import AdapterError


class TestBrokerTimeoutSubmit:
    def test_timeout_submit_raises_error(self):
        adapter = SimulatedAdapter()
        adapter.set_default_fill_quality(SimFillQuality.TIMEOUT)
        intent = ApprovedOrderIntent(
            risk_decision_id="rd-1",
            intent_id="int-1",
            client_order_id="ord-timeout-1",
            instrument_id="AAPL",
            side="BUY",

            quantity="100",
            order_type="LIMIT",
            time_in_force="DAY",
            risk_profile_version="1.0",
            price="150",

            stop_price=None,
        )
        with pytest.raises(AdapterError, match="timeout") as exc:
            adapter.place_order(intent)
        assert "timeout" in exc.value.classification

    def test_reconcile_clean_after_timeout(self):
        adapter = SimulatedAdapter()
        adapter.set_default_fill_quality(SimFillQuality.TIMEOUT)
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        intent = ApprovedOrderIntent(
            risk_decision_id="rd-2",
            intent_id="int-2",
            client_order_id="ord-to-2",
            instrument_id="AAPL",
            side="BUY",

            quantity="100",
            order_type="LIMIT",
            time_in_force="DAY",
            risk_profile_version="1.0",
            price="150",

            stop_price=None,
        )
        with pytest.raises(AdapterError):
            adapter.place_order(intent)


        # Reconcile: broker has no position (order never reached broker)
        broker_positions = []
        recon = ReconciliationEngine(
            ReconciliationConfig(warning_drift_fraction=0.01, critical_drift_fraction=0.05)
        )
        result = recon.compare(
            portfolio=portfolio,
            broker_positions=broker_positions,
            broker_cash=Money("100000", "USD"),
        )
        assert result.position_drifts == [], f"Expected clean reconciliation, got drifts: {result.position_drifts}"
