# Paper Session Runbook

> **Purpose:** Operate a paper trading session using the SimulatedAdapter.
> **No real capital is at risk.**

## Prerequisites

- Python 3.14+ with titan package installed
- No broker credentials required (SimulatedAdapter is in-memory)

## Starting a session

```bash
python -m titan.cli risk status
# Expected: Trading state: Active, Kill switch: Armed
```

## Running the replay pipeline

```bash
python -m pytest tests/integration/test_paper_vertical_slice.py -v
```

## Kill switch drill

1. Trigger kill switch:
```python
from titan._core import RiskConfig, RiskGate
gate = RiskGate(RiskConfig(...))
gate.trigger_kill_switch()
```
2. Verify routing blocked: `gate.evaluate(intent)` returns rejected.
3. Release: `gate.release_initiated()` → `gate.release_completed()`
4. Verify routing resumes.

## Reconciliation drill

1. Apply fills to PortfolioEngine.
2. Create BrokerPosition with intentional drift.
3. Run ReconciliationEngine.compare() — verify drift detected.

## Restarting a session

```bash
python -m titan.cli recovery restart
```

Expected output:
```
Recovering from event store...
Reconciling...
Reconciliation clean
Drift count: 0
System state: ACTIVE
```

If drift is detected, the system starts in HALTED. Investigate drift before releasing.

## Session end

- Close all Python processes.
- Verify no state files remain.

## Incident response

If unexpected behavior occurs:
1. Halt: trigger kill switch.
2. Collect logs and state.
3. Document in knowledge/incidents/.
