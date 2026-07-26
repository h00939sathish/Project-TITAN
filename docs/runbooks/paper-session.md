# Paper Session Runbook

> **Purpose:** Operate a paper trading session with multi-timeframe evaluation.
> No real capital is at risk.

## Prerequisites

- Python 3.14+ with titan package installed
- For SimulatedAdapter: no broker credentials required
- For IBKR paper: TWS or IB Gateway running with paper account configured (port 7497 or 8874)

## Starting a session

### Simulated (no broker)

```bash
python scripts/paper_session.py
```

### IBKR paper

```bash
python scripts/ibkr_paper_session.py
```

## Multi-timeframe monitoring

Each strategy declares its trigger timeframe. When a bar closes on timeframe T,
only strategies triggered by T evaluate. Monitor per-timeframe metrics:

- `evaluations.<timeframe>` — bars evaluated per timeframe
- `proposals.<timeframe>` — proposals created per timeframe
- `accepted.<timeframe>` — intents accepted per timeframe
- `lag.<timeframe>` — event lag per timeframe

Expected: every subscribed timeframe receives evaluations during regular
session hours. Zero evaluations in an expected session triggers an alert.

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

## Reconciliation readiness gate

Before enabling a paper strategy, record a successful reconciliation whose position and cash snapshots come from the configured adapter. A missing or failed snapshot is a HALTED condition; do not replace it with portfolio state.

## Restarting a session

```bash
python scripts/paper_session.py
```

Expected output after warmup:
```
System state: ACTIVE
```

If drift is detected, the system starts in HALTED. Investigate drift before releasing.

## Session end

- Close all Python processes.
- Verify no state files remain (or archive them for audit).

## Incident response

If unexpected behavior occurs:
1. Halt: trigger kill switch.
2. Collect logs and state.
3. Document in knowledge/incidents/.
