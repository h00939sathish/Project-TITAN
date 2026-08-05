# Phase J — 90-Day Paper Operation

> **Status:** ACTIVE
> **Start:** 2026-07-14
> **End:** 2026-10-11
> **Owner:** Architecture Council
> **Goal:** Prove the TITAN platform can operate unattended for 90 calendar days in paper mode, producing auditable records of every state transition and surviving failures without data loss.

## Success Criteria

All six must pass for Phase J to be considered complete:

| # | Criterion | Evidence |
|---|---|---|
| 1 | **90 days uptime** — no unrecoverable crash that requires manual state rebuild | Session heartbeat log shows <1h gap between heartbeats for entire duration |
| 2 | **Deterministic replay** — any 24h window can be replayed from the event store and produce identical portfolio state | Event store replay test against random windows passes |
| 3 | **Zero silent data loss** — every intent, fill, reconciliation, and state mutation is logged | Log file count matches expected event count; no gaps in sequence |
| 4 | **Failure injection survivability** — all failure matrix scenarios (timeout, drift, clock skew, store corruption, kill switch) recover without manual intervention | Weekly failure drill passes per FAILURE_MATRIX.md |
| 5 | **Monotonic metric coverage** — all 18 defined metrics are non-decreasing/accurate across the full 90 days | Metrics dump at day 90 shows consistent counters |
| 6 | **Phase K ready** — a go/no-go report exists with reconciliation drift analysis, risk gate statistics, and a recommendation for Phase K (restricted live) | Phase K readiness document reviewed by Architecture Council |

## Architecture

```
┌─────────────────────────────────────────────────┐
│               Session Runner                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Strategy  │  │ Reconcile│  │ Metrics/Log   │  │
│  │ Loop 60s  │  │ Loop 5m  │  │ Persist 15m   │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│       │              │               │          │
└───────┼──────────────┼───────────────┼──────────┘
        │              │               │
        ▼              ▼               ▼
┌──────────────────────────────────────────────────┐
│            Approved Data Source                  │
│  load_approved()  →  market calendar             │
│  freshness check  →  manifest validation         │
└────────────────────┬─────────────────────────────┘
                     │ loaded bars
                     ▼
┌─────────────────────────────────────────────────┐
│              PaperTradingEngine                  │
│  RiskGate → SimulatedAdapter → PortfolioEngine  │
│         ↓              ↓              ↓          │
│    StructuredLogger   MetricsRegistry  State File│
└─────────────────────────────────────────────────┘
```

### Component responsibilities

- **Session Runner** (`scripts/paper_session.py`): Orchestrates the 90-day loop. Runs strategy evaluation every 60s, reconciliation every 5min, metrics dump every 15min. Handles SIGINT/SIGTERM for graceful shutdown.
- **PaperTradingEngine**: Executes the intent pipeline. Logs every state transition. Increments metrics counters. Persists state to JSON snapshot on every mutation.
- **StructuredLogger**: JSON-structured log output to both stdout and rotating file.
- **MetricsRegistry**: In-memory counters/gauges, dumped to JSON file every 15min by the session runner.
- **SimulatedAdapter**: Deterministic fill simulation. No external dependencies.

## Runbook

### Starting a session

```powershell
# Default: strategies on SPY, QQQ with synthetic prices
python scripts/paper_session.py

# Strict preflight — requires approved data, fail-closed
python scripts/paper_session.py --mode paper-preflight --data-file tests/fixtures/market/spy_2020_2024.csv --instruments SPY

# Market status check
python scripts/paper_session.py --status-only
```

### Monitoring

```powershell
# Live metrics
python -c "from titan.operations._metrics_integration import get_registry; import json; print(json.dumps(get_registry().snapshot(), indent=2))"

# Health check
python -c "from titan.operations.telemetry import HealthReporter; hr = HealthReporter(); h = hr.health(); print(h.to_dict())"

# Engine status (from saved state)
python -c "
import json
s = json.load(open('.titan_state.json'))
print(f'Cash: {s[\"portfolio\"][\"cash\"][\"amount\"]} {s[\"portfolio\"][\"cash\"][\"currency\"]}')
print(f'Positions: {len(s[\"portfolio\"][\"positions\"])}')
print(f'Orders: {len(s[\"order_states\"])}')
print(f'Intents: {s[\"intent_counter\"]}')
"
```

### Daily checks

1. Check log file for ERROR/CRITICAL entries: `grep CRITICAL titan-*.log`
2. Verify metrics file exists and is recent: `ls -la metrics-*.json`
3. Check state file is non-empty: `ls -la .titan_state.json`
4. Run `python scripts/paper_session.py --status-only` for quick health
5. Verify data freshness: `python -c "from titan.data.freshness import check_freshness; from titan.data.manifest import DataManifest; import json; m = DataManifest.from_json(open('manifest.json').read()); r = check_freshness(m); print('Fresh' if r.fresh else f'STALE: {r.reason}')"`

### Weekly drills

Per FAILURE_MATRIX.md, run weekly:
```powershell
pytest tests/failure_matrix/ -v
```
Document any failures in `docs/phase-j/incidents/`.

### Emergency procedures

| Situation | Action |
|---|---|
| State file corrupted | Stop runner. Restore from backup or EventStore replay: `python -m titan.cli recovery restart` |
| Kill switch triggered | Investigate cause. Run reconciliation. Release with two-person approval: `python -m titan.cli risk release` |
| Runner crash | Verify state file integrity. Restart: `python scripts/paper_session.py` |
| Disk full | Archive old logs. Ensure at least 500MB free for state + logs |
| Data staleness | Restart runner with fresh data file |

## Dashboard (Console)

Session runner prints a dashboard line every 60s:

```
[2026-07-14T12:00:00Z] ♥ uptime=2d3h intents=147 fills=142 rej=5 drift=0 kw=0 prices=2/2 cash=100000 pv=100500 data=2026-07-13 log=45MB
```

| Field | Description |
|---|---|
| ♥ | System state: ♥=Active, ⚠=Degraded, ☠=Halted |
| uptime | Session uptime |
| intents | Total intents evaluated |
| fills | Total fills applied |
| rej | Total intents rejected |
| drift | Current drift count (warning) |
| kw | Kill switch state: 0=released, 1=initiated, 2=engaged |
| prices | Live prices / eligible instruments |
| cash | Cash balance |
| pv | Portfolio value |
| data | Latest bar date in approved data source (if loaded) |
| log | Log file size |

## Metrics Tracked

All 18 metrics from `_metrics_integration.py` are dumped every 15min to `metrics-<date>.json`.

Key metrics for go/no-go decision at day 90:
- `intents_evaluated` — total trading activity
- `intents_rejected` — risk gate rejection rate (should be <30%)
- `orders_filled` — execution success rate
- `orders_unknown` — should be 0
- `drift_count_critical` — should be 0

## Phase K Go/No-Go

At day 85, the Architecture Council reviews:
1. This document with all 6 success criteria evaluated
2. Metrics dump from entire 90 days
3. All incident reports from `docs/phase-j/incidents/`
4. Reconciliation drift log
5. Risk gate statistics (rejection reasons breakdown)
6. Recommendation for Phase K (restricted live with real Alpaca credentials)
