### Task E2: Certify SimulatedAdapter as paper adapter

**Files:**
- Create: `tests/adapters/__init__.py`
- Create: `tests/adapters/test_simulated_adapter_contract.py`
- Create: `docs/runbooks/paper-session.md`

**Full implementation is in the plan doc:**
D:\projects\Project TITAN\docs\superpowers\plans\2026-07-13-phase-e-strategy-and-paper.md

Read the "Task E2" section for complete code.

**Key tests to write in `test_simulated_adapter_contract.py`:**

```python
from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality

class TestSimulatedAdapterContract:
    """Proves the adapter meets the broker adapter contract per Broker.spec.md."""

    def setup_method(self):
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)

    def test_submit_and_fill(self):
        order = self.adapter.submit_order("ord-1", "AAPL", "buy", 100, "150.00")
        assert order.status == "filled"
        assert order.filled_quantity == 100

    def test_submit_and_reject(self):
        self.adapter.set_default_fill_quality(SimFillQuality.REJECT)
        order = self.adapter.submit_order("ord-2", "AAPL", "buy", 100, "150.00")
        assert order.status == "rejected"

    # ... 10 more tests for partial fill, timeout, cancel, open/filled tracking, etc.
```

**Plus these contract tests:**
- `test_partial_fill_then_full` — PARTIAL_THEN_FILL → partially filled → tick → filled
- `test_timeout_simulated` — TIMEOUT → pending (simulates UNKNOWN)
- `test_never_fill` — stays pending forever
- `test_cancel_pending` — can cancel pending/partial orders
- `test_cancel_filled_order_fails` — returns False
- `test_open_orders` — open orders tracked
- `test_filled_orders` — filled orders tracked
- `test_get_order_nonexistent` — returns None
- `test_multiple_independent_orders` — different instruments, different fill qualities

**Create `docs/runbooks/paper-session.md`** with session management, kill switch drill, reconciliation drill, incident response steps.

**Working dir:** D:\projects\Project TITAN
**Python:** `.venv\Scripts\python.exe`

**Exit:** `python -m pytest tests/adapters/ -v` passes. Full suite still green.
