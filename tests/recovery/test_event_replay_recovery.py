import pytest
import json
from titan._core import EventStore, EventEnvelope, Money, PortfolioEngine
from titan.recovery.restart import (
    recover_from_event_store,
    replay_portfolio_events,
    reconcile_on_boot,
    transition_on_boot,
)
from titan.execution.simulated_adapter import SimulatedAdapter

@pytest.fixture
def temp_store_path(tmp_path):
    return str(tmp_path / "test_recovery_event_store.db")


def test_replay_portfolio_events_reconstructs_positions(temp_store_path):
    store = EventStore(temp_store_path)
    
    # Append OrderFilled events
    fill_payload_1 = json.dumps({
        "client_order_id": "client-ord-1",
        "instrument_id": "SPY",
        "side": "BUY",
        "filled_quantity": 100,
        "fill_price": "450.00",
    })
    fill_payload_2 = json.dumps({
        "client_order_id": "client-ord-2",
        "instrument_id": "SPY",
        "side": "SELL",
        "filled_quantity": 40,
        "fill_price": "455.00",
    })
    
    store.append(EventEnvelope("OrderFilled", "Execution", "client-ord-1", "test_python", fill_payload_1))
    store.append(EventEnvelope("OrderFilled", "Execution", "client-ord-2", "test_python", fill_payload_2))

    portfolio = PortfolioEngine("USD", Money("100000", "USD"))
    replayed_count = replay_portfolio_events(store, portfolio)

    assert replayed_count == 2
    pos = portfolio.get_position("SPY")
    assert pos is not None
    assert pos.quantity == 60
    assert str(pos.side).upper() == "LONG"


def test_recover_from_event_store_and_boot_reconciliation(temp_store_path):
    # Setup initial session, write events to store
    store = EventStore(temp_store_path)
    fill_payload = json.dumps({
        "client_order_id": "client-ord-1",
        "instrument_id": "AAPL",
        "side": "BUY",
        "filled_quantity": 50,
        "fill_price": "180.00",
    })
    store.append(EventEnvelope("OrderFilled", "Execution", "client-ord-1", "test_python", fill_payload))
    store.close()

    # Recover from process crash
    state = recover_from_event_store(temp_store_path)
    restored_portfolio = state["portfolio"]
    restored_risk_gate = state["risk_gate"]
    recon_engine = state["recon_engine"]

    pos = restored_portfolio.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == 50

    # Simulate matching adapter position
    adapter = SimulatedAdapter()
    adapter.submit_order("client-ord-1", "AAPL", "buy", 50, "180.00")

    recon_res = reconcile_on_boot(restored_portfolio, adapter, recon_engine)
    status = transition_on_boot(recon_res, restored_risk_gate)

    assert recon_res["has_drift"] is False
    assert status == "ACTIVE"


