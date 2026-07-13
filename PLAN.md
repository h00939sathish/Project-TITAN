# Project TITAN Solo-Developer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a paper-only, deterministic vertical slice that can replay market data, issue a strategy intent, enforce risk, simulate execution, persist/recover state, and reconcile it before any live broker or AI capability is introduced.

**Architecture:** Rust (via PyO3/maturin) provides the deterministic execution core — event store, order state machine, risk gate, portfolio projection, reconciliation engine, and broker adapter trait. Python provides the flexible outer layers — strategy logic, data orchestration, CLI, backtest configuration, and test harnesses. Rust types are compiled into native Python extensions; the two languages share a single process. Each stage must preserve the same contracts from replay through paper operation.

**Tech Stack:** Python 3.12+, Pydantic v2, Rust 1.80+ (edition 2024), PyO3/maturin, pytest, Ruff, mypy, clippy, SQLite, DuckDB, Parquet/Arrow, GitHub Actions.

## Global Constraints

- Paper operation only until the live-readiness gate in `DEPLOYMENT.md` is met.
- AI has no broker, execution, risk, portfolio, secret, or deployment authority.
- The risk gate is the sole path from `TradeIntent` to `ApprovedOrderIntent`.
- Kill-switch state is persistent, fail-closed, manually released, and tested through the route that sends orders.
- All economic facts are immutable events with a schema version and correlation identifier.
- No repository code is copied until its license, compatibility, maintenance, and security posture are approved by ADR.
- Every safety control is exercised by an end-to-end failure test; a class that is not invoked is not a control.
- Rust is the execution core from day one. Python owns the flexible outer layers (strategy logic, data orchestration, CLI, test harnesses). This split is ratified in ADR-0002.
- No subsystem is implemented unless: specification exists, ADR accepted, tests written, verification defined, rollback defined, monitoring defined.
- Specifications precede all code. Phase -1 requires every subsystem spec, performance budget, failure matrix, and versioning policy before a single Rust or Python file is written.

---

## Why this replaces the proposed plan

The proposed plan correctly prioritizes the deterministic capital path. It is changed in five ways:

1. **Rust is the execution core, not a deferred optimization.** PyO3/maturin compiles Rust domain types, event store, state machines, risk gate, reconciliation, and broker adapter trait into native Python extensions. ADR-0002 ratifies this architecture and its license posture.
2. **Specifications precede all code.** Phase -1 requires every subsystem spec (interface, state machine, errors, metrics, config), a performance spec, a failure matrix, a versioning policy, knowledge management structure, and operational readiness criteria before code is written.
3. **The first deliverable is a paper-only vertical slice.** Build event, state, risk, execution, recovery, data replay, and strategy behavior together—not a large core before it sees market data.
4. **AI is deferred until paper operations are stable.** It has no value if the deterministic research/validation path is not yet trustworthy.
5. **A live broker is not a Phase E default.** First prove paper operation with a broker sandbox or market-data feed; live credentials and capital remain outside this plan.

## Target layout

```text
Project TITAN/
├── specifications/            # Phase -1: all subsystem specifications
│   ├── Money.spec.md
│   ├── Order.spec.md
│   ├── Portfolio.spec.md
│   ├── TradeIntent.spec.md
│   ├── Execution.spec.md
│   ├── Risk.spec.md
│   ├── Broker.spec.md
│   ├── Replay.spec.md
│   ├── contracts/             # cross-reference to machine-readable schemas
│   ├── PERFORMANCE_SPEC.md    # p99 budgets per subsystem
│   ├── FAILURE_MATRIX.md      # failure → behavior → recovery → verification
│   ├── VERSIONING.md          # independent version policy
│   ├── ORR-checklist.md       # Operational Readiness Review gates
│   └── PAT-checklist.md       # Production Acceptance Test gates
├── contracts/                 # JSON Schemas and golden contract fixtures (machine-readable)
├── core/                      # Rust crate (PyO3/maturin) — compiled to native extension
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs             # PyO3 entry point
│   │   ├── types.rs           # Money, Quantity, Price, InstrumentId, OrderSide, etc.
│   │   ├── messages.rs        # EventEnvelope, TradeIntent, RiskDecision
│   │   ├── event_store.rs     # SQLite append-only log with replay
│   │   ├── orders.rs          # Order state machine
│   │   ├── risk.rs            # Deterministic gate, limits, kill switch
│   │   ├── portfolio.rs       # Event-driven position/PnL projection
│   │   ├── reconciliation.rs  # Broker truth comparison
│   │   └── adapters.rs        # Broker adapter trait
│   └── tests/
├── src/titan/                  # Python package (formerly src/titan/)
│   ├── __init__.py
│   ├── cli.py                 # CLI entry point
│   ├── data/                  # ingest, normalize, quality, features (Python)
│   ├── backtest/              # replay clock, fill models, WFO, MC (Python orchestration)
│   ├── strategies/            # package manifest and runtime (Python)
│   └── operations/            # configuration, logging, health (Python)
├── knowledge/                 # institutional memory (Phase -1 structure)
│   ├── decisions/             # ADRs + RFCs (symlink to docs/adr)
│   ├── research/              # hypotheses, experiments, evidence records
│   ├── incidents/             # post-mortems, timeline, corrective actions
│   ├── experiments/           # run results, parameters, metrics
│   ├── rejected-ideas/        # why something was rejected (prevent repeat work)
│   └── benchmarks/            # performance baselines and profiles
├── tests/                     # Python integration, replay, chaos tests
├── docs/adr/                  # accepted implementation ADRs
├── docs/runbooks/             # operational runbooks
├── scripts/                   # local developer commands only
└── Project TITAN/*.md         # current handbook; migrate only via a dedicated ADR
```

---

## Phase -1 — Foundational Specifications (2–3 weeks)

**Principle:** No code until specs exist. Every subsystem, performance target, failure mode, and versioning rule is specified before implementation begins. Specifications are living documents — updated when a material decision changes, never without an ADR.

### Task -1.1: Establish specifications directory and conventions

**Files:**
- Create: `specifications/README.md`
- Create: `docs/adr/ADR-0001-spec-first-discipline.md`

- [x] Define the spec template: each `.spec.md` contains Purpose, Boundary/Ownership, Inputs, Outputs, Commands (send), Events (emit), State machine (Mermaid), Dependencies, Error taxonomy, Metrics, Configuration schema, Performance budget reference, Failure behavior reference.
- [x] Record ADR-0001 ratifying spec-first discipline: no implementation task opens until its specification is accepted.

**Exit evidence:** `specifications/README.md` defines the template; ADR-0001 is Accepted.

### Task -1.2: Write subsystem specifications

**Files:**
- Create: `specifications/Money.spec.md`
- Create: `specifications/Order.spec.md`
- Create: `specifications/Portfolio.spec.md`
- Create: `specifications/TradeIntent.spec.md`
- Create: `specifications/Execution.spec.md`
- Create: `specifications/Risk.spec.md`
- Create: `specifications/Broker.spec.md`
- Create: `specifications/Replay.spec.md`

Each spec contains:
- **Purpose** — one-paragraph reason this subsystem exists
- **Boundary / Ownership** — what it owns, what it delegates
- **Inputs** — event/command types it consumes
- **Outputs** — event/command types it emits
- **Commands** — typed request messages it accepts
- **Events** — typed fact messages it emits
- **State machine** — Mermaid diagram of legal states and transitions
- **Dependencies** — which other subsystems it calls
- **Error taxonomy** — retryable, terminal, data-quality, risk, operational error classes
- **Metrics** — every metric name, type, and semantic meaning
- **Configuration** — every config key, type, default, and validation rule
- **Performance budget** — reference to PERFORMANCE_SPEC.md line item
- **Failure behavior** — reference to FAILURE_MATRIX.md line item

- [x] Write Money.spec.md (decimal arithmetic, rounding modes, currency, precision rules, fixed-point representation, comparison, arithmetic operations)
- [x] Write Order.spec.md (state machine with Mermaid: NEW → VALIDATED → SUBMITTED → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED, plus REJECTED, CANCELLED, EXPIRED, UNKNOWN; idempotency key lifecycle; amendments; cancellation)
- [x] Write Portfolio.spec.md (position tracking, realized/unrealized PnL, cash balance, exposure, margin, valuation method, corporate actions, multi-currency)
- [x] Write TradeIntent.spec.md (schema, required fields, provenance chain, expiry rules, rejection reason taxonomy)
- [x] Write Execution.spec.md (order lifecycle service, durable outbox, adapter contract interface, timeout/retry policies, UNKNOWN state handling)
- [x] Write Risk.spec.md (pipeline: schema → eligibility → freshness → limits → exposure → drawdown → liquidity → broker health → decision; trading state machine with Mermaid: ACTIVE / REDUCING / HALTED; kill switch state machine with Mermaid: ARMED / TRIGGERED / RELEASING / RELEASED)
- [x] Write Broker.spec.md (session lifecycle with Mermaid: DISCONNECTED → CONNECTING → AUTHENTICATING → CONNECTED → EXPIRING → RECONNECTING; adapter method signatures; reconciliation cursor)
- [x] Write Replay.spec.md (clock advancement by event time, fill model taxonomy, corporate action sequencing, result metrics, determinism invariants)

**Exit evidence:** 8 `.spec.md` files, each reviewed and internally consistent.

### Task -1.3: Write cross-cutting specifications

**Files:**
- Create: `specifications/PERFORMANCE_SPEC.md`
- Create: `specifications/FAILURE_MATRIX.md`
- Create: `specifications/VERSIONING.md`
- Create: `specifications/ORR-checklist.md`
- Create: `specifications/PAT-checklist.md`
- Create: `specifications/contracts/README.md`

- [x] PERFORMANCE_SPEC.md: define p99 latency budgets for Risk gate (<50μs), Execution order lifecycle (<100μs), Event store read/write (<1ms), Replay throughput (1M events <15s). Define measurement methodology, hardware baseline, workload characterization.
- [x] FAILURE_MATRIX.md: table of every failure mode — Broker Disconnect, Broker Timeout, Duplicate Fill, Clock Drift, DB Corruption, Replay Failure, Authentication Expiry, Kill-Switch Trigger, Reconciliation Drift, Stale Market Data, Configuration Load Failure. Each row: failure, trigger condition, expected behavior, recovery action, verification test.
- [x] VERSIONING.md: independent versioning policy for message schemas (major.minor), event contracts, strategy packages, configuration (content-addressed), model prompts, broker adapters, and data contracts. Compatibility windows, deprecation procedure.
- [x] ORR-checklist.md: Operational Readiness Review checklist covering architecture, performance vs budget, risk controls, monitoring/alerting, recovery procedures, testing coverage, security review, runbook completeness, sign-off requirements.
- [x] PAT-checklist.md: Production Acceptance Test checklist covering deployment artifact install, clean start, restart recovery, config validation, secret resolution, telemetry emission, health endpoint, broker reconnect, kill-switch persist, reconciliation drift detection.
- [x] specifications/contracts/README.md: explains that human-readable contract specs live here; machine-readable JSON Schemas live in `contracts/` at repo root. Links between the two are maintained by CI.

**Exit evidence:** all 6 cross-cutting specification files written and internally consistent.

### Task -1.4: Establish knowledge management structure

**Files:**
- Create: `knowledge/README.md`
- Create: `knowledge/research/.gitkeep`
- Create: `knowledge/incidents/.gitkeep`
- Create: `knowledge/experiments/.gitkeep`
- Create: `knowledge/rejected-ideas/.gitkeep`
- Create: `knowledge/benchmarks/.gitkeep`

- [x] Define knowledge/ convention in README: what goes where, naming, required metadata (date, author, status for decisions).
- [x] `knowledge/decisions/` is a symlink or pointer to `docs/adr/` (authoritative location).

**Exit evidence:** `knowledge/` directory with README and stubs; team understands where each knowledge artifact lives.

### Task -1.5: Ratify Phase -1 specifications as ADRs

**Files:**
- Create: `docs/adr/ADR-0001-spec-first-discipline.md` (Accepted)
- Create: `docs/adr/ADR-0002-runtime-and-license.md` (Accepted — Rust+PyO3, license posture)
- Create: `docs/adr/ADR-0003-events-and-replay.md` (Accepted)
- Create: `docs/adr/ADR-0004-risk-and-recovery.md` (Accepted)
- Create: `docs/adr/ADR-0005-simulation-fidelity.md` (Accepted)
- Create: `docs/adr/ADR-0006-paper-broker-certification.md` (Accepted)
- Create: `docs/adr/ADR-0007-ai-advisory-policy.md` (Accepted — deferred until after Phase F)

- [x] Each ADR follows the `ADR.md` template and cites `EVIDENCE_SYNTHESIS.md`.
- [x] Each ADR names its specification file as the design authority.
- [x] Review all seven ADRs.

**Exit evidence:** 7 `Accepted` ADRs; no unresolved authority boundary or license question. Phase -1 complete.

---

## Phase A — Binding decisions and bootstrap (1–2 weeks)

### Task A1: (covered by Phase -1.5 — ADRs already ratified)

No additional task — Phase -1.5 produces the ADRs originally planned here. Phase A picks up with toolchain.

### Task A2: Initialize reproducible Rust + Python project

**Files:**
- Create: `pyproject.toml`, `core/Cargo.toml`, `.gitignore`, `.github/workflows/ci.yml`
- Create: `core/src/lib.rs`, `core/src/types.rs`
- Create: `src/titan/__init__.py`, `src/titan/cli.py`
- Create: `tests/test_smoke.py`

- [x] Initialize Rust crate with PyO3/maturin under `core/`; `maturin develop` builds the native extension.
- [x] Implement first Rust domain types (`Money`, `Quantity`, `Price`, `Side`) exposed to Python.
- [x] Define Python package, lint/type/test commands (Rust: `cargo check`, `clippy`, `test`; Python: `pytest`, `ruff`, `mypy`).
- [x] Add CLI that prints version string (from Rust core) and does not read credentials.
- [x] Add CI for both Rust and Python checks.
- [x] Run all checks locally before enabling CI.

**Exit evidence:** clean checkout runs `maturin develop`; Rust types importable from Python; CI executes Rust and Python checks.

---

## Phase B — Contracts, facts, and recovery (2–3 weeks)

**Spec authority:** `specifications/Money.spec.md`, `specifications/Order.spec.md`, `specifications/TradeIntent.spec.md`, `specifications/PERFORMANCE_SPEC.md`, `specifications/VERSIONING.md`

### Task B1: Publish canonical schemas and domain types

**Files:**
- Create: `contracts/event-envelope-v1.schema.json`
- Create: `contracts/trade-intent-v1.schema.json`
- Create: `contracts/risk-decision-v1.schema.json`
- Create: `core/src/types.rs`, `core/src/messages.rs`
- Create: `tests/contracts/test_message_schemas.py`

**Produces:** Rust types for `EventEnvelope`, `TradeIntent`, `RiskDecision`, `ApprovedOrderIntent` (exposed via PyO3); each includes message id, type, schema version, timestamps, correlation/causation ids, aggregate identity, and configuration digest. JSON Schemas define the wire format; Rust types enforce it at the boundary.

- [ ] Write golden valid and invalid JSON fixtures for each schema.
- [ ] Implement Rust structs with `serde` + PyO3 bindings that reject missing identity, invalid decimal strings, unsupported schema versions, and malformed timestamps.
- [ ] Test JSON round-trip and schema/Rust-type agreement from Python.

**Exit evidence:** every canonical message round-trips without loss; invalid payloads are rejected with stable reason codes. Rust types are importable from Python tests.

### Task B2: Implement event store and order state machine

**Files:**
- Create: `core/src/event_store.rs`, `core/src/orders.rs`
- Create: `tests/core/test_event_store.py`, `tests/core/test_order_states.py`

**Produces:** SQLite append-only store (Rust via `rusqlite`) keyed by `message_id`; deterministic replay by aggregate; `NEW`, `VALIDATED`, `SUBMITTED`, `ACKNOWLEDGED`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_PENDING`, `CANCELLED`, `REJECTED`, `EXPIRED`, and `UNKNOWN` states. Conforms to `specifications/Order.spec.md`.

- [ ] Test duplicate event insertion, restart/replay, illegal transition rejection, and ambiguity transition to `UNKNOWN` from Python.
- [ ] Persist original event JSON plus schema version; projections must rebuild from facts.
- [ ] Test that replayed aggregate state exactly matches the original state.

**Exit evidence:** restart produces byte-for-byte equivalent event history and equivalent aggregate state. Event store and state machine run in Rust, callable from Python via PyO3.

---

## Phase C — Deterministic paper capital path (3–4 weeks)

**Spec authority:** `specifications/Risk.spec.md`, `specifications/Execution.spec.md`, `specifications/Portfolio.spec.md`, `specifications/TradeIntent.spec.md`, `specifications/FAILURE_MATRIX.md`

### Task C1: Build fail-closed risk and trading-state control

**Files:**
- Create: `core/src/risk.rs`, `core/src/kill_switch.rs`
- Create: `src/titan/risk/limits.py` (Python configuration loader passes typed limits to Rust)
- Create: `tests/risk/test_gate.py`, `tests/risk/test_kill_switch.py`

**Produces:** deterministic evaluation pipeline (Rust) with Python-configurable limits; persistent `ACTIVE`/`REDUCING`/`HALTED` state. Conforms to `specifications/Risk.spec.md`.

- [ ] Implement integrity, freshness, instrument, quantity/notional, position/exposure, drawdown, and broker-health checks with versioned reason codes.
- [ ] Persist kill-switch state in SQLite; default to halted when state is unreadable or unavailable.
- [ ] Require explicit authenticated operator release interface, represented initially by a local audited CLI action with no automatic reset.
- [ ] Test that rejected or halted intents cannot reach any adapter call.
- [ ] Validate p99 risk-gate latency against PERFORMANCE_SPEC.md budget.

**Exit evidence:** an end-to-end test proves a halted system and every rejected intent produce zero broker calls. Latency meets budget.

### Task C2: Add simulated execution, portfolio projection, and reconciliation

**Files:**
- Create: `core/src/portfolio.rs`, `core/src/reconciliation.rs`
- Create: `src/titan/execution/simulated_adapter.py` (Python adapter calls Rust core)
- Create: `tests/integration/test_paper_vertical_slice.py`, `tests/chaos/test_recovery.py`

**Produces:** Rust-driven position/cash/PnL projection and reconciliation engine; Python simulated adapter for deterministic fills. Conforms to `specifications/Portfolio.spec.md`, `specifications/Execution.spec.md`.

- [ ] Simulate acknowledgement, partial fill, fill, reject, timeout, and disconnected/ambiguous submit response.
- [ ] Ensure an ambiguous request is recorded as `UNKNOWN` and reconciled before reattempting.
- [ ] Test duplicate fills, process restart, storage failure, stale data, reconciliation drift, and kill-switch action during an active lifecycle.
- [ ] Validate each failure mode against FAILURE_MATRIX.md expected behavior.

**Exit evidence:** `TradeIntent → RiskDecision → simulated execution → Fill → portfolio → reconciliation` is replayable, idempotent, and safe under injected failures. Every FAILURE_MATRIX.md scenario has a passing test.

---

## Phase D — Data and replay validation (3–4 weeks)

**Spec authority:** `specifications/Replay.spec.md`, `specifications/PERFORMANCE_SPEC.md`

### Task D1: Implement file-based data pipeline

**Files:**
- Create: `src/titan/data/ingest.py`, `src/titan/data/normalize.py`, `src/titan/data/quality.py`
- Create: `tests/data/test_pipeline.py`, `tests/fixtures/market/`

- [ ] Accept versioned CSV/Parquet input only; preserve raw source checksum and ingest metadata.
- [ ] Normalize vendor symbol, UTC timestamp, decimals, currency, and canonical instrument id.
- [ ] Quarantine invalid schema, duplicate, out-of-range, crossed-quote, or stale records with reason codes.
- [ ] Write normalized Parquet partitions and manifest under the documented lake layout.

**Exit evidence:** one known fixture is ingested, normalized, quarantined when corrupted, and read back with its lineage intact.

### Task D2: Implement deterministic replay/backtest baseline

**Files:**
- Create: `src/titan/backtest/clock.py`, `src/titan/backtest/fills.py`, `src/titan/backtest/results.py`
- Create: `tests/replay/test_deterministic_replay.py`, `tests/backtest/test_corporate_actions.py`

- [ ] Replay normalized events by event time through the same strategy-intent, risk, execution, and portfolio contracts.
- [ ] Implement bar-conservative fills, fees, configured slippage, splits, dividends, and symbol-change events.
- [ ] Record data/config/strategy/fill-model versions with return, drawdown, turnover, cost, and fill metrics.
- [ ] Validate replay throughput against PERFORMANCE_SPEC.md budget (1M events <15s).
- [ ] Defer order-book simulation and impact calibration until this baseline has golden replay coverage.

**Exit evidence:** identical fixture and package digest produce identical fills, positions, PnL, and metrics across runs. Throughput meets budget.

---

## Phase E — Strategy and paper operation (3–5 weeks)

**Spec authority:** `specifications/Broker.spec.md`, `specifications/PAT-checklist.md`

### Task E1: Add a minimal versioned strategy package

**Files:**
- Create: `src/titan/strategies/manifest.py`, `src/titan/strategies/runtime.py`
- Create: `tests/strategies/test_moving_average_package.py`

- [ ] Define manifest fields: package id/version/digest, data requirements, parameter schema, universe, risk profile, expiry, and fixtures.
- [ ] Implement one deterministic moving-average-cross strategy solely to prove the interface.
- [ ] Reject stale data, unknown instruments, invalid package digest, and unsupported parameter values before intent emission.
- [ ] Run the package through replay and the paper vertical slice.

**Exit evidence:** strategy package provenance is present on every intent and no strategy imports broker or portfolio code.

### Task E2: Certify one paper integration

**Files:**
- Create: `src/titan/adapters/<chosen_adapter>/`, `docs/runbooks/paper-session.md`
- Create: `tests/adapters/test_<chosen_adapter>_contract.py`

- [ ] Select a broker/data provider in ADR-0006 based on sandbox quality, API stability, instrument coverage, rate limits, and credential model.
- [ ] Implement read-only market data plus a sandbox/paper order path only if the provider supports it; otherwise continue with the simulated adapter.
- [ ] Exercise authentication expiry, heartbeat, reconnect, rate-limit, partial-fill, restart, and reconciliation scenarios.
- [ ] Run the PAT-checklist.md against the deployment artifact.
- [ ] Run a 14-day paper session with daily reconciliation review and incident log.

**Exit evidence:** PAT passes. No unresolved critical drift, all adapter scenarios pass, and halt/recovery drill succeeds.

---

## Phase F — Operations, ORR, and promotion gate (2–3 weeks)

**Spec authority:** `specifications/ORR-checklist.md`, `specifications/FAILURE_MATRIX.md`

### Task F1: Establish operating evidence

**Files:**
- Create: `src/titan/operations/telemetry.py`, `docs/runbooks/incident.md`
- Create: `tests/operations/test_health_and_alerts.py`

- [ ] Emit structured logs, correlation ids, event lag, risk-rejection, adapter-health, kill-switch, and reconciliation-drift metrics.
- [ ] Add health endpoints that report degraded/halted state without exposing secrets.
- [ ] Conduct and document broker-disconnect, state-store loss, and material-drift drills.
- [ ] Review all incidents against the documentation/ADR update policy.
- [ ] Log each drill and incident result in `knowledge/incidents/`.

**Exit evidence:** dashboards and runbooks enable an operator to detect, halt, recover, and explain a simulated incident.

### Task F2: Conduct Operational Readiness Review

- [ ] Walk through `ORR-checklist.md` with all items verified or waived by ADR.
- [ ] Compare measured latency, event volume, memory, developer load, and paper-operation findings with ADR-0002's budget.
- [ ] Identify any Rust hot-path components whose performance profile does not meet the accepted budget; prioritize those for optimization in the next cycle.
- [ ] Evaluate whether the Rust/Python boundary is well-placed: are there Python-convenience code paths that should be pushed into Rust for safety or performance reasons? Are there Rust components whose flexibility would improve by moving to Python?
- [ ] Live capital, multi-broker expansion, order-book simulation, optimizer ensembles, and AI remain out of scope until this gate is accepted.

**Exit evidence:** signed-off ORR. Evidence-backed assessment of the Rust/Python boundary quality and an optimization priority list.

---

## Phase G — Cross-Cutting Hardening (3–4 weeks)

**Spec authority:** `specifications/ORR-checklist.md`, `specifications/PERFORMANCE_SPEC.md`, `specifications/FAILURE_MATRIX.md`, `specifications/Risk.spec.md`

**Goal:** Close the highest-priority gaps identified in the Phase F ORR: state persistence, structured logging, metrics emission, FAILURE_MATRIX test coverage, recovery automation, and performance benchmarking.

**Exit evidence:** All ORR-MON, ORR-REC, ORR-RISK-03, and ORR-TST-01 items resolved or explicitly deferred with ADR. Benchmark baselines recorded in `knowledge/benchmarks/`.

### Task G1: Kill-switch and trading-state persistence

**Files:**
- Modify: `core/src/risk.rs`
- Modify: `core/src/messages.rs`
- Modify: `core/src/event_store.rs`
- Create: `tests/risk/test_state_persistence.py`

- [ ] Define `RiskStateSnapshot` event in messages.rs carrying kill-switch state, trading state, and timestamp.
- [ ] Add `persist_state()` and `restore_state()` methods to `RiskGate` that write/read `RiskStateSnapshot` via the event store.
- [ ] On restart, load persisted state before accepting any intents; if state is unreadable or missing, default to HALTED (fail-closed).
- [ ] Add Rust tests for persist/restore lifecycle (trigger → persist → restart → verify halted).
- [ ] Add Python integration test: trigger kill switch, simulate restart, verify routing blocked.
- [ ] Document restart behavior in incident runbook.

**Exit evidence:** Kill switch state survives Python process restart. HALTED default on unreadable state. Integration test passes.

### Task G2: Structured logging wired into runtime

**Files:**
- Modify: `src/titan/operations/telemetry.py`
- Create: `src/titan/operations/logging.py`
- Modify: `src/titan/cli.py`
- Create: `tests/operations/test_logging.py`

- [ ] Add `LogEvent` dataclass with correlation_id, causation_id, component, severity, message, timestamp.
- [ ] Add `StructuredLogger` that writes JSON lines to stdout with configurable minimum severity level.
- [ ] Wire `StructuredLogger` into the risk gate call path (log each evaluate() call with verdict and reason).
- [ ] Wire `StructuredLogger` into the adapter call path (log submit, fill, reject, timeout, cancel events).
- [ ] Wire `StructuredLogger` into the reconciliation call path (log drift detection).
- [ ] Wire `StructuredLogger` into the HealthReporter health() method.
- [ ] Add pytest fixture that captures structured log output and verifies format.
- [ ] Add tests for: correlation_id threading, severity filtering, JSON output format, missing-field handling.

**Exit evidence:** Running the vertical slice integration test produces JSON-structured logs with correlation_ids tracing each intent through risk → execution → fill → reconciliation. Tests verify log format and content.

### Task G3: Metrics emission from risk gate, execution, and portfolio

**Files:**
- Create: `src/titan/operations/metrics.py`
- Modify: `src/titan/cli.py`
- Create: `tests/operations/test_metrics.py`

- [ ] Define metric types: Counter, Gauge, Histogram with name, value, tags, timestamp.
- [ ] Add `MetricsRegistry` as a singleton that stores in-memory metric state and supports snapshot/dump.
- [ ] Wire counter metrics into risk gate: `intents_evaluated`, `intents_rejected`, `kill_switch_triggered`, `trading_state_changed`.
- [ ] Wire counter/gauge metrics into portfolio: `positions_open`, `gross_exposure`, `cash_balance` (via Python wrapper).
- [ ] Wire counter metrics into execution: `orders_submitted`, `orders_filled`, `orders_rejected`, `orders_cancelled`, `orders_unknown`.
- [ ] Wire gauge metrics into reconciliation: `drift_count_warning`, `drift_count_critical`, `last_reconciliation_age_seconds`.
- [ ] Wire gauge metric into health reporter: `system_state` (ACTIVE/REDUCING/HALTED/DEGRADED as numeric).
- [ ] Add `titan.cli metrics dump` command that prints all metrics as JSON.
- [ ] Add `titan.cli metrics health` command that assesses system health from metrics (risk working? orders progressing? broker truth match?).
- [ ] Add tests: counter increments, gauge updates, registry snapshot, CLI output format.

**Exit evidence:** After running the vertical slice integration test, `titan.cli metrics dump` shows non-zero metrics for intents, fills, portfolio state, and reconciliation status. CLI health command reflects system state.

### Task G4: FAILURE_MATRIX test coverage

**Files:**
- Create: `tests/failure_matrix/__init__.py`
- Create: `tests/failure_matrix/test_broker_timeout_submit.py`
- Create: `tests/failure_matrix/test_broker_timeout_cancel.py`
- Create: `tests/failure_matrix/test_duplicate_fill.py`
- Create: `tests/failure_matrix/test_event_store_write_failure.py`
- Create: `tests/failure_matrix/test_event_store_corruption.py`
- Create: `tests/failure_matrix/test_clock_drift.py`
- Create: `tests/failure_matrix/test_config_load_failure.py`
- Modify: `core/src/event_store.rs` (if needed for fault injection)

Each test verifies the expected behavior and recovery from the FAILURE_MATRIX row.

- [ ] **Broker timeout (submit):** Configure SimulatedAdapter with TIMEOUT quality; submit order; verify order transitions to UNKNOWN; verify reconcile resolves the state.
- [ ] **Broker timeout (cancel):** Submit fillable order, cancel, inject timeout on cancel; verify no retry; verify reconcile resolves.
- [ ] **Duplicate fill:** Send identical fill event twice via PortfolioEngine; verify portfolio projection is unchanged; verify duplicate-warning event emitted.
- [ ] **Event store write failure:** Mock SQLite write to return error; verify command is rejected; verify error is not swallowed.
- [ ] **Event store corruption:** Simulate corrupt SQLite file; verify detection fails closed; verify operator can diagnose.
- [ ] **Clock drift:** Inject clock jump in test clock; verify new intents rejected during drift; verify halt; verify reconcile catches anomalies.
- [ ] **Configuration load failure:** Deploy bad config file; verify startup failure with descriptive error.

**Exit evidence:** `pytest tests/failure_matrix/ -v` passes all 7 tests. Each test verifies the expected failure behavior and recovery path. FAILURE_MATRIX.md coverage increases from 3/14 rows to 10/14 rows.

### Task G5: Recovery automation — restart and reconcile

**Files:**
- Create: `src/titan/recovery/__init__.py`
- Create: `src/titan/recovery/restart.py`
- Create: `src/titan/recovery/reconcile_on_boot.py`
- Create: `tests/recovery/test_restart.py`
- Modify: `docs/runbooks/paper-session.md`
- Modify: `docs/runbooks/incident.md`

- [ ] Implement `recover_from_event_store()` that replays all events and rebuilds OrderStateMachine, PortfolioEngine, RiskGate state.
- [ ] Implement `reconcile_on_boot(simulated_adapter, portfolio_engine, reconciliation_engine)` that compares rebuilt portfolio with adapter's open orders and fills, then reports drift.
- [ ] Implement `transition_on_boot()` that moves system to ACTIVE only if reconciliation is clean (no critical drift); otherwise transitions to HALTED.
- [ ] Add `titan.cli recovery restart` command that performs the full boot sequence.
- [ ] Add integration test: record events in a session, simulate restart, run recovery, verify positions and risk state match pre-restart.
- [ ] Add integration test: inject drift before restart, verify system starts in HALTED.
- [ ] Update paper-session.md: add "Restarting a session" section covering recovery command and verification steps.
- [ ] Update incident.md: add event store loss recovery procedure referencing recovery commands.

**Exit evidence:** `titan.cli recovery restart` replays events, reconciles, and transitions to ACTIVE or HALTED based on drift. Integration tests verify both clean and drifted restarts.

### Task G6: Benchmark harness and performance baselines

**Files:**
- Create: `scripts/bench.py`
- Create: `knowledge/benchmarks/bench-risk-gate.md`
- Create: `knowledge/benchmarks/bench-event-store.md`
- Create: `knowledge/benchmarks/bench-replay.md`

- [ ] Write `scripts/bench.py` as a reusable benchmark runner that measures p99 latency and throughput for a given subsystem.
- [ ] **Risk gate benchmark:** Measure p99 evaluate() latency over 10,000 calls (50th-percentile arrival rate). Record result in `knowledge/benchmarks/bench-risk-gate.md`.
- [ ] **Event store benchmark:** Measure sequential append throughput (target >50,000 events/s). Measure single-aggregate replay from 10k events (target <5 ms). Record in `knowledge/benchmarks/bench-event-store.md`.
- [ ] **Replay benchmark:** Measure replay throughput for 100k bar-level events (target <15s for 1M). Record in `knowledge/benchmarks/bench-replay.md`.
- [ ] For each benchmark, include: date, hardware spec, commit SHA, seed, dataset size, raw results, and comparison to PERFORMANCE_SPEC.md budget.
- [ ] If any budget is not met, record the gap and estimate the optimization required.
- [ ] Document benchmark reproduction steps.

**Exit evidence:** Three benchmark documents in `knowledge/benchmarks/` with measured performance against all 12 budgets from PERFORMANCE_SPEC.md. Reproduction steps recorded. Any budget gaps identified for future optimization.

### Solo-developer estimate addition

Phase G adds approximately 3–4 weeks to the total plan at full time, or 6–8 weeks at 15–20 hours/week.

## Deferred work

AI advisory, vector memory, additional brokers, ensemble allocation, Monte Carlo/optimization, order-book simulation, multi-account live trading, and restricted-live promotion follow only after Phase G. Their requirements remain in the handbook and in `specifications/` but are not MVP commitments.

## Solo-developer estimate

At full time, Phases -1 through G are approximately 22–33 weeks. At 15–20 hours/week, plan for 14–20 months. Rust and spec-first discipline add front-loaded overhead that pays back in reduced rework and integration time. This estimate intentionally excludes live capital and broad AI/plug-in scope; adding them before the paper gate would invalidate the safety and time assumptions.
