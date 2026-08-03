"""Live operational tests against real TWS (paper, port 7497).

Run:  python scripts/ops_test_live.py

Tests (each uses its own API client id — does not touch the live session):
  T1  Disconnect/reconnect: force a client disconnect, verify heartbeat fails,
      then ensure_connected() re-establishes and broker queries work.
  T2  External cancellation: place a small order through the adapter, cancel it
      from an independent ibapi client (equivalent to a TWS UI cancel), verify
      the adapter's tick() sees the terminal status.
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from titan._core import ApprovedOrderIntent
from titan.execution._broker_types import BrokerOrderId
from titan.execution.ibkr_adapter import IBKRPaperAdapter

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}", flush=True)


# ── T1: disconnect / reconnect ───────────────────────────────────────────────
def test_reconnect() -> None:
    print("T1 disconnect/reconnect", flush=True)
    adapter = IBKRPaperAdapter(client_id=165, account_id="DUQ284074")
    adapter.authenticate()
    check("T1 authenticate", adapter.heartbeat().connected)

    # Simulate a dropped connection (what a TWS restart / network drop does).
    adapter._client.disconnect()
    time.sleep(1.0)
    check("T1 heartbeat detects disconnect", not adapter.heartbeat().connected)

    ok = adapter.ensure_connected()
    check("T1 ensure_connected reconnects", ok)
    if ok:
        pos = adapter.positions("DUQ284074")
        check("T1 broker queries work after reconnect", pos.positions is not None)
        bal = adapter.holdings("DUQ284074")
        check("T1 holdings work after reconnect", float(bal.cash.amount) > 0)
    try:
        adapter._client.disconnect()
    except Exception:
        pass


# ── T2: external cancellation detection ──────────────────────────────────────
class RawCancelClient(EWrapper, EClient):
    """Minimal client used to cancel an order like the TWS UI would."""

    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.ready = threading.Event()

    def nextValidId(self, orderId: int) -> None:
        self.ready.set()

    def error(self, reqId, errorTime=-1, errorCode=0, errorString="", advancedOrderRejectJson=""):
        if errorCode not in (2104, 2106, 2158, 2159):
            print(f"  [cancel-client Err {errorCode}] {errorString}", flush=True)


def test_external_cancel() -> None:
    print("T2 external cancellation (broker-side cancel observed via poll)", flush=True)
    adapter = IBKRPaperAdapter(client_id=166, account_id="DUQ284074")
    adapter.authenticate()

    intent = ApprovedOrderIntent(
        risk_decision_id="ops-test-2",
        intent_id="ops-test-2",
        client_order_id="ops-test-2",
        instrument_id="XLF",
        side="BUY",
        quantity="1",
        order_type="LIMIT",
        time_in_force="DAY",
        risk_profile_version="1.0.0",
        price="1.00",  # far from market: the order rests and cannot fill
    )
    ack = adapter.place_order(intent)
    check("T2 order placed", ack.accepted, f"status={ack.order_status}")
    if not ack.accepted:
        return

    oid = int(ack.broker_order_id.id)
    client_order_id = "ops-test-2"

    # Terminate the order at the broker (the engine's cancel path — equivalent
    # to a TWS UI cancel for the purposes of the poll loop). Note: TWS does not
    # let a *different* API client cancel another client's order (err 10147),
    # so the pure "UI cancel" case is covered by the unit test that injects a
    # Cancelled status into tick().
    cancel_ack = adapter.cancel(BrokerOrderId(id=str(oid)))
    check("T2 broker accepted cancel", cancel_ack.accepted)
    print(f"  sent cancel for order {oid}", flush=True)

    # The adapter's poll should observe the terminal status.
    deadline = time.monotonic() + 15
    seen = None
    while time.monotonic() < deadline:
        status = adapter.tick(client_order_id)
        if status is not None and status.status in (
            "Cancelled", "Rejected", "Inactive", "ApiCancelled", "Filled",
        ):
            seen = status
            break
        time.sleep(1.0)
    check("T2 tick() observes terminal status after cancel",
          seen is not None, f"status={seen.status if seen else 'None'}")
    if seen is not None and seen.status not in ("Filled",):
        check("T2 no phantom fill from cancelled order", int(seen.filled_quantity or 0) == 0)
    # Cleanup: if anything filled (preview account), flatten it so the test
    # leaves no position behind.
    try:
        pos = adapter.positions("DUQ284074")
        for p in pos.positions:
            if p.instrument_id == "XLF":
                close_intent = ApprovedOrderIntent(
                    risk_decision_id="ops-test-cleanup",
                    intent_id="ops-test-cleanup",
                    client_order_id="ops-test-cleanup",
                    instrument_id="XLF",
                    side="SELL",
                    quantity=str(p.quantity),
                    order_type="MARKET",
                    time_in_force="DAY",
                    risk_profile_version="1.0.0",
                    price="60",
                )
                adapter.place_order(close_intent)
                print(f"  cleanup: flattened XLF {p.quantity}", flush=True)
    except Exception as e:
        print(f"  cleanup skipped: {e}", flush=True)
    try:
        adapter._client.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    test_reconnect()
    test_external_cancel()
    print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===", flush=True)
    for f in FAIL:
        print(f"  FAILED: {f}", flush=True)
    sys.exit(1 if FAIL else 0)
