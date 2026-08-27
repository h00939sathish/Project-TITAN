# Specification & Governance Mining Report — Project TITAN / Profit-Engine-AI (v2.0)

> **Agent Directory:** `D:\projects\Project TITAN\.agents\explorer_survey_2`  
> **Role:** Specification & Governance Miner  
> **Date:** 2026-08-18  
> **Target Subsystem:** Entire Project TITAN Repository (`D:\projects\Project TITAN`) and Foundational R&D Evidence (`D:\projects`)  
> **Governing Standards:** `AGENTS.md`, `OPERATING_PRINCIPLES.md`, `AI_GOVERNANCE.md`, `RISK_POLICY.md`, `TESTING_STANDARD.md`, `specifications/`, `docs/adr/`

---

## 1. Observation

A systematic forensic survey of all repository governance contracts, architectural decision records (ADRs), formal specifications, comparative research documents, schema contracts, and implementation sources was conducted.

### 1.1 Document Sources & Exact Evidence Observed

1. **Constitutional & Governance Core Documents (`D:\projects\Project TITAN/`):**
   - `AGENTS.md` (lines 1–54): Established the non-negotiable constitution. Rule 2: Research/advisory components cannot invoke broker, order, portfolio, risk-override, or secret management. Rule 6: Enforces Canonical Simulation Evidence (ADR-031) with immutable cost models, quote-sided fills, IBKR $2.00 minimum fees, slippage impact, and data manifests (`can_qualify=False` for bar-close constant-bps). Rule 7: Absorbing Negative Results (ADR-029, ADR-030) — failed hypotheses terminate permanently; post-hoc lookback mining is strictly forbidden. Rule 8: Mandatory categorization into *Mechanism Failure* vs. *Execution-Constrained Rejection*.
   - `OPERATING_PRINCIPLES.md` (lines 1–46): Non-negotiable principles: Evidence over opinion; Reliability over novelty; AI proposes, deterministic systems decide; Capital never delegated to a model; One source of truth for material state; No frictionless backtests. Defined the 4 continuous loops: Research, Architecture, Implementation, Evolution.
   - `AI_GOVERNANCE.md` (lines 1–36): AI is advisory only. Forbidden: holding broker credentials, signing orders, modifying portfolio/balances, evaluating hard risk limits, releasing halts, self-issuing `PromotionCertificate`s, modifying production configuration.
   - `RISK_POLICY.md` (lines 1–46): Risk is a deterministic veto function. Pipeline: `TradeIntent → schema/integrity → strategy eligibility → market-data freshness → order limits → position/exposure → portfolio/drawdown → liquidity/impact → broker/session health → approved intent or reasoned rejection`. Kill switch is persistent, fail-closed, and never auto-resets. Release from `HALTED` requires broker reconciliation, root-cause assessment, verified control health, approved remediation, and **two authorized human approvals**.
   - `TESTING_STANDARD.md` (lines 1–41): Test layers required: Unit, Integration, Universe & Data Contract, Replay/regression, Canonical Simulation, Walk-forward/Monte Carlo, Paper trading, Chaos/recovery, Performance. Invariants: rejected intents never reach broker; kill switch cannot auto-reset; simulations fail closed on unverified data digests.
   - `PROJECT_TITAN.md` (lines 1–54): System boundaries and 5 core objectives (Equities/ETFs research, structured hypothesis pre-registration with absorbing negative results, canonical cost validation, human-approved risk-gated live deployment with cryptographic certificates, continuous learning without autonomous capital changes).
   - `docs/RESEARCH_CONSTITUTION.md` (lines 1–239): Generation 1 (Platform construction complete) vs Generation 2 (Alpha Discovery active). Frozen infrastructure scope. 6-dimension Evidence Quality Index (EQI: Reproducibility, Replication, Statistical Robustness, Economic Plausibility, Execution Realism, Documentation). Mandatory 3D Replication (Instrument, Time Period, Market Regime).
   - `docs/MECHANISM_REGISTRY.md` (lines 1–140): Mechanism Evidence Index (MEI) formula: $\text{MEI} = 0.30 \cdot \text{Replication} + 0.25 \cdot \text{StatSupport} + 0.20 \cdot \text{Stability} + 0.15 \cdot \text{Plausibility} + 0.10 \cdot \text{Generalization}$. Status thresholds: 0.00-0.25 (Retired), 0.26-0.50 (Exploratory), 0.51-0.75 (Active), 0.76-0.90 (Strong Evidence), 0.91-1.00 (Established Mechanism with 6-condition milestone gate).
   - `docs/CANONICAL_RESEARCH_QUESTIONS.md` (lines 1–74): Registered RQs: `RQ-001` (Opening Auction Imbalance), `RQ-002` (Volatility Compression), `RQ-003` (Execution Microstructure), `RQ-004` (Intraday Sector Leadership), `RQ-005` (Regime-Dependent Momentum), `RQ-006` (Cross-Asset Dislocations), `RQ-007` (Event-Driven Fundamental). Liquid-OHLCV single-pair directional search class is permanently closed per `ALPHA_SEARCH_TERMINAL_REPORT.md`.

2. **Foundational Comparative R&D Reports (`D:\projects/`):**
   - `EXECUTIVE_SUMMARY.md`: Evaluated 7 repos; verdict to adapt core microkernel and reconciliation from NautilusTrader, indicators from Jesse, risk architecture from new trade, AI advisory reflection from LLM_trader, and broker connectors from Fincept; strictly avoid LLM-as-risk-manager and unconstrained provider proliferation.
   - `HOSTILE_REVIEW.md` (lines 1–307): Seven devil's advocate challenges highlighting LGPL risks, Windows latency/uvloop constraints, 4 P0 bugs in new trade (auto-reset kill switch, race conditions), LLM single-pair crypto limits, and integration cost underestimations. Revised build posture: borrow design patterns and implement clean-room Python/Rust core rather than blindly copying unverified external dependencies.
   - `FINCEPT_DELTA_REPORT.md` (lines 1–121): Upstream v4.2.0 audit confirming desktop-only Qt constraints, DataHub pub/sub, and hardened CI/CD.
   - `ADOPTION_DECISIONS.md` (lines 1–802): Component-level adoption matrix: Adopted Nautilus message hierarchy and 3-state TradingState machine (`ACTIVE`, `REDUCING`, `HALTED`), 3-interval reconciliation engine (`inflight`, `open`, `positions`), outbox persistence from Fincept, and Monte Carlo VaR with Cholesky from TRADE.
   - `FAILURE_ANALYSIS.md` (lines 1–703): 8-dimension risk audit across all 7 repositories detailing the "exists but not wired" recurring defect.

3. **Architecture Decision Records (`D:\projects\Project TITAN\docs\adr/`):**
   - `ADR-0001`: Specification-first implementation discipline (6-condition implementation gate).
   - `ADR-0002`: Rust deterministic execution core (`core/src/`) + Python strategy/platform plane (`src/titan/`) via PyO3/maturin. Clean-room implementation, no GPL/LGPL code copying.
   - `ADR-0003`: Canonical JSON events with JSON Schema; SQLite append-only event store (`EventStore`); deterministic replay by construction.
   - `ADR-0004`: Risk, halt, recovery, and reconciliation invariants. Risk gate is sole path from `TradeIntent` to `ApprovedOrderIntent`. Fail-closed kill switch.
   - `ADR-0005`: Simulation fidelity. Bar-conservative fills default; quote-based fill opt-in; strict determinism.
   - `ADR-0006`: Paper broker certification. Simulated adapter first, paper adapter second, no live credentials.
   - `ADR-0007`: AI advisory policy. AI deferred until paper path is proven; strictly advisory; no LLMs on the capital path.
   - `ADR-018`: IBKR paper forex execution behind dedicated broker boundary (`CASH`/`IDEALPRO`, micro-lot 1,000 units, ConId mapping).
   - `ADR-019`: Kill-switch release requires dual approved-human authorization (`ReleaseAuthorization` record with nonces, expiry, rationale, assessment) and verified realtime feed health (`FeedHealthVerdict`).
   - `ADR-020`: Fail-closed recovery and explicit session initialization (`SessionInitialization` via `initialize_new_session` with 2 distinct approvers, bounded TTL $\le 24$h; unreadable/empty state fails closed to `Triggered`/`Halted`).
   - `ADR-021`: Strategy exits expressed at intent layer (`stop_price`, `take_profit_price`, `trailing` controller `(activation_distance, trail_distance)`).
   - `ADR-022`: Qualification is DB-gated. Removed baked-in `qualified_variants` from `registrations.py`; research DB (`qualifications` table) is the single source of truth (SSOT).
   - `ADR-023`: Promotion gates fail closed (enforces F1 non-self-referential replication, F3 real stored surface metrics, F7 signal exception propagation).
   - `ADR-024`: Stored promotion-gate surface metrics schema (`plateau_stability`, `plateau_coverage`, `replication_sharpe`, `max_correlation` columns in `qualifications`).
   - `ADR-025`: 4h shadow-trade evidence path via 1h BarAggregator + cointegration-gated screening (Engle-Granger cointegration pre-gate).
   - `ADR-026`: EXP-00017 2-fold OOS failure and data freeze (data exhaustion on 2025-08..2026-07 FX window; no further mining on this slice).
   - `ADR-028`: Execution integrity, signed promotion certificates (`PromotionCertificateRegistry` with Ed25519 signature binding strategy, parameters, dataset digests, cost model digests, and 2 human signers), layered shadow isolation, and canonical sizing (`Sizer`).
   - `ADR-029`: Bounded crypto market-structure research program (24/7 venue-aware simulator, pre-registered funding/basis/OI hypotheses, absorbing negative results).
   - `ADR-030`: US Equities & ETFs cross-sectional factor research program (`EQ-001` Momentum 12-1M, `EQ-002` Short-Term Reversal 5D, `EQ-003` Vol-Adjusted Low-Vol; dollar-neutral / beta-neutral quantile spreads; short borrow and commission fees).
   - `ADR-031`: Canonical FX simulation evidence (admit FX promotion evidence ONLY from immutable `FxCostModel` with USD ticket fee minimum $2.00, quote-sided fills; `BAR_NEXT_OPEN` tagged lower-fidelity and non-qualifying).

4. **Formal Specifications (`D:\projects\Project TITAN\specifications/`):**
   - `Governance.spec.md`, `Risk.spec.md`, `Broker.spec.md`, `Execution.spec.md`, `Order.spec.md`, `TradeIntent.spec.md`, `StrategyRuntime.spec.md`, `CryptoResearch.spec.md`, `EquitiesFactorResearch.spec.md`, `Replay.spec.md`, `Money.spec.md`, `MarketEvent.spec.md`, `Portfolio.spec.md`, `SpotMetal.spec.md`, `Forex.spec.md`, `FeatureGraph.spec.md`, `FAILURE_MATRIX.md`, `PERFORMANCE_SPEC.md`.

5. **JSON Schema Contracts (`D:\projects\Project TITAN\contracts/`):**
   - `trade-intent-v1.schema.json`
   - `approved-order-intent-v1.schema.json`
   - `risk-decision-v1.schema.json`
   - `crypto-market-event-v1.schema.json`
   - `event-envelope-v1.schema.json`

---

## 2. Logic Chain

1. **From Constitution to Execution Invariants:**
   - Observations in `AGENTS.md` and `AI_GOVERNANCE.md` dictate that AI models and research pipelines are strictly untrusted, advisory entities.
   - Therefore, no model output or strategy code may directly place orders, hold broker credentials, or alter state.
   - All strategy proposals must be transformed into typed `TradeIntent` messages, pass through the deterministic `RiskGate` pipeline (schema, certificate, eligibility, freshness, order limits, exposure, drawdown, liquidity, broker health), and yield an `ApprovedOrderIntent` before reaching an adapter.

2. **From R&D Failure Modes to Gate Enforcement:**
   - Observations in `FAILURE_ANALYSIS.md` and `HOSTILE_REVIEW.md` revealed recurring industry failure modes: unwired circuit breakers, auto-resetting kill switches, frictionless backtest snooping, and unverified data.
   - Consequently, Project TITAN introduced ADR-019 (dual-human signed `ReleaseAuthorization` + `FeedHealthVerdict`), ADR-020 (fail-closed recovery without automatic bootstrap + explicit `SessionInitialization`), ADR-028 (cryptographic promotion certificates with Ed25519 keys), and ADR-031 (mandatory institutional cost accounting with ticket minima and quote-sided fills).

3. **From Research Alpha Exhaustion to Cross-Sectional & Structural Programs:**
   - Observations in `ALPHA_SEARCH_TERMINAL_REPORT.md` and ADR-026 proved that single-pair liquid-OHLCV directional indicators produce zero out-of-sample alpha after realistic spreads and transaction costs.
   - Therefore, ADR-029 (Crypto Market Structure) and ADR-030 (US Equities Cross-Sectional Factors) were enacted to pivot research into structural edges (funding rates, open interest, cross-sectional dollar-neutral long/short factor portfolios).
   - Under ADR-029, ADR-030, and AGENTS.md Rule 7, all experiments are pre-registered with frozen holdouts. Any out-of-sample failure transitions permanently into an absorbing `negative_result` state categorized as *Mechanism Failure* or *Execution-Constrained Rejection*.

---

## 3. Features Discovered & Complete Specifications Catalog

### 3.1 Features Discovered Table

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Governance | Implementation Gate | Enforces 6 strict prerequisites (Spec, ADR, Tests, Verification, Rollback, Monitoring) before code merge | PR / Subsystem proposal | Release clearance / gate verdict | Rejects unwired or unverified code | `AGENTS.md:47-55`, `ADR-0001` |
| 2 | Governance | AI Advisory Boundary | Strict isolation of AI models from execution, credentials, and risk override | Prompts, market facts, evidence | Advisory proposals, hypotheses, reflections | Deterministic validators override invalid AI outputs; fails closed | `AI_GOVERNANCE.md`, `ADR-0007` |
| 3 | Governance | Mechanism Registry & MEI | Quantitative tracking of economic mechanisms via decomposed MEI index (0.00 to 1.00) | Experiment evidence bundles | MEI score, status (Retired, Exploratory, Active, Strong, Established) | Relegates disproven mechanisms to terminal Retired state | `docs/MECHANISM_REGISTRY.md` |
| 4 | Governance | 3D Replication Framework | Mandates multi-dimensional validation across Instrument, Time Period, and Regime | Candidate return series | 3D validation pass/fail | Fails closed on self-referential or single-window runs (ADR-023 F1) | `docs/RESEARCH_CONSTITUTION.md §7` |
| 5 | Governance | Absorbing Negative Results | Terminal failure recording without post-hoc lookback parameter tuning | Failed OOS backtest / walk-forward | Immutable negative result record in chronicle | Prevents publication bias and parameter snooping | `AGENTS.md Rule 7`, `ADR-029`, `ADR-030` |
| 6 | Data Pipeline | SHA-256 Manifest Tracking | Full cryptographic provenance binding raw files, adjustments, and date bounds | Raw CSV/Parquet files | `DataManifest` / `FactorManifest` with SHA-256 digest | Rejects orphan events, corrupt files, or checksum mismatches | `src/titan/data/manifest.py`, `ADR-028` |
| 7 | Data Pipeline | Market Data Quarantine & Gap Detection | Validates record schemas, detects business day & intraday gaps, handles delistings | Raw market data records | `QuarantineReport`, filtered valid records | Isolates bad rows into quarantine without crashing ingestion | `src/titan/data/quality.py` |
| 8 | Data Pipeline | Calendar Engine Suite | Exchange-aware trading calendars for NYSE/NASDAQ, Forex, Spot Metals, and 24/7 Crypto | Timestamps, market sessions | Session open/close status, valid trading flags | Rejects out-of-session data or invalid holiday bars | `src/titan/data/calendar*.py` |
| 9 | Research | Hypothesis Pre-Registration | Pre-specifies parameter surfaces, partitions, metrics, and kill criteria before evaluation | JSON pre-registration schema (`EQ-00X-prereg.json`) | Hash-locked pre-registration artifact | Rejects OOS runs if parameter hash differs from registered manifest | `ADR-029`, `ADR-030`, `EquitiesFactorResearch.spec.md` |
| 10 | Research | Cross-Sectional Factor Engine | Computes point-in-time percentile rankings and dollar-neutral ($G=1.0$ or $2.0$) quantile portfolios | Daily price matrices, universe membership | $T \times N$ factor scores, target weights $\mathbf{w}_t$ | Rejects non-dollar-neutral allocations ($|\sum w_i| > 10^{-6}$) | `ADR-030`, `src/titan/research/equities_factor_screen.py` |
| 11 | Research | 1h→4h Bar Aggregator | UTC 00/04/08/12/16/20 aligned deterministic bar aggregator for 4h shadow trade accrual | 1h closed bars | 4h aggregated OHLCV bars | Rejects misaligned bars; flushes only on completed 4h boundaries | `ADR-025`, `src/titan/strategies/bar_aggregator.py` |
| 12 | Research | Cointegration Pre-Screening | Engle-Granger and ADF tests on asset spreads prior to mean-reversion screening | Cross-asset price series | Cointegration test statistics and p-values | Halts screening if non-cointegrated (prevents spurious edge mining) | `ADR-025`, `docs/synthesis/RQ-002_synthesis.md` |
| 13 | Simulation | Institutional Cost Models | Immutable venue cost calculators (`FxCostModel`, `CryptoCostModel`, `FactorCostModel`) | Orders, notional, quote snapshots | Exact commissions, ticket minima, spread, slippage, short borrow | Rejects cost-free simulations; non-canonical models cannot qualify | `ADR-031`, `src/titan/backtest/*costs.py` |
| 14 | Simulation | Quote-Sided Fill Engine | Simulates fills against opposing top-of-book (Buy at Ask, Sell at Bid) with adverse slippage | Pending orders, quote events | Executed `BrokerFill` events with fee attribution | Flags bar-close fills as lower-fidelity (`can_qualify=False`) | `ADR-031`, `src/titan/backtest/fills.py` |
| 15 | Simulation | Deterministic Event Replay | Replays market events through identical Rust/Python risk, order, and portfolio contracts | Historical event log / Parquet | Emitted event stream, PnL attribution | Halts on illegal state transitions; byte-for-byte replay determinism | `Replay.spec.md`, `ADR-0003`, `ADR-0005` |
| 16 | Risk Engine | Deterministic 9-Stage Gate | Evaluates intents through typed, versioned pre-trade validation rules | `TradeIntent` | `RiskDecision` (ACCEPTED / REJECTED + reason codes) | Rejects on any check breach; short-circuits to fail closed | `Risk.spec.md`, `core/src/risk.rs` |
| 17 | Risk Engine | 3-Level Trading State Machine | Enforces operational boundaries: `ACTIVE`, `REDUCING` (position reduction only), `HALTED` | Risk breaches, operator actions | State change events | Blocks all new orders in HALTED; permits only de-risking in REDUCING | `Risk.spec.md`, `ADR-0004` |
| 18 | Risk Engine | Persistent Fail-Closed Kill Switch | State-backed kill switch (`ARMED`, `TRIGGERED`, `RELEASING`, `RELEASED`) | Operator trigger, drift, circuit breaker | Blocks order routing, cancels open orders | Never auto-resets; missing state starts in HALTED/TRIGGERED | `RISK_POLICY.md`, `ADR-0004`, `ADR-020` |
| 19 | Risk Engine | Dual-Human Release Gate | Requires two distinct authorized human signatures, nonces, and verified feed health | `ReleaseAuthorization` JSON, feed status | Release clearance or typed refusal | Refuses on expired, replayed, incomplete auth or stale market data | `ADR-019`, `src/titan/risk/release_authorization.py` |
| 20 | Risk Engine | Explicit Session Initialization | Replaces automatic bootstrap; requires 2 authorized humans to arm fresh environment | `SessionInitialization` JSON | `SessionInitialized` event | Refuses if risk state exists or authorization invalid; default is HALTED | `ADR-020`, `src/titan/risk/session_initialization.py` |
| 21 | Risk Engine | Feed Health Monitor | Evaluates market data freshness, bar advancement, and instrument coverage | `TWSRealtimeFeed` / Market feed | `FeedHealthVerdict` (healthy, stale, absent, recovering) | Fails closed; blocks kill-switch release if data is stale | `ADR-019`, `src/titan/data/feed_health.py` |
| 22 | Execution | Canonical Sizer | Computes deterministic lot sizes from equity, allocation pct, price, and conversion rates | Equity, allocation %, price, FX rate | `SizingResult` (integer quantity, is_tradable) | Rejects underfunded minimum lots, stale FX rates, or invalid prices | `ADR-028`, `src/titan/strategies/sizing.py` |
| 23 | Execution | Ed25519 Promotion Certificate | Cryptographically validates execution authority before order ingress | `Certificate` + public key hex | Validated certificate ref | Rejects unsigned, expired, revoked, or parameter-mismatched intents | `ADR-028`, `src/titan/research/promotion_certificate.py`|
| 24 | Execution | Exit-Bearing Intent Contract | Embeds protective stop-loss, take-profit, and ratcheting trailing stops into intents | `TradeIntent` with exit fields | Broker stop/trail orders (`STP`/`TRAIL`) | Rejects invalid trailing distances (`activation < trail`) | `ADR-021`, `src/titan/strategies/bridge.py` |
| 25 | Execution | Multi-Timeframe Runtime Evaluator | Dispatches market events to strategies matching explicit `TriggerSpec(event, timeframe)` | `MarketEvent` (5m, 15m, 1h, 1d) | `TradeProposal` per strategy-instrument | State isolation per timeframe; prevents cross-timeframe state bleed | `StrategyRuntime.spec.md`, `src/titan/runtime/evaluator.py` |
| 26 | Execution | IBKR TWS Paper Adapter | Interfaces with IBKR TWS (port 7497) or Gateway (port 8874) for equities and forex | `ApprovedOrderIntent` | Broker acknowledgements, fills, position reports | Fails closed on live ports; maps ConIds and reconciles truth | `ADR-018`, `src/titan/execution/ibkr_adapter.py` |
| 27 | Execution | Order State Machine & UNKNOWN State | Deterministic order aggregate managing lifecycle with `UNKNOWN` quarantine state | Commands, broker callbacks | Lifecycle events (`OrderSubmitted` .. `OrderFilled`) | Marks timeouts as UNKNOWN; halts duplicate orders pending reconcile | `Order.spec.md`, `core/src/orders.rs` |
| 28 | Execution | 3-Interval Reconciliation Engine | Reconciles local event store with broker truth across inflight, open orders, and positions | `BrokerTruthSnapshot` | `ReconciliationResult` (Match, Warning, Critical) | Critical drift triggers kill switch and halts routing immediately | `ADR-0004`, `core/src/reconciliation.rs` |
| 29 | Storage | SQLite Event Store (`EventStore`) | Append-only transactional store for envelopes, aggregates, and audit logs | `EventEnvelope` | Persisted event sequence, aggregate replay stream | Rejects duplicate message IDs; write failures abort command | `ADR-0003`, `core/src/event_store.rs` |
| 30 | Storage | Research Database (`ResearchDB`) | SQLite database tracking runs, tags, qualifications, audits, and shadow events | Simulation results, gate evaluations | Persisted qualifications, shadow records | SSOT for qualification; enforces DB schema migration (ADR-024) | `ADR-022`, `ADR-024`, `src/titan/research/db.py` |

---

### 3.2 Edge Cases & Observed System Behaviors

| # | Feature | Input / Condition | Observed Behavior & Contract Requirement |
|---|---------|-------------------|------------------------------------------|
| 1 | `RiskGate` | Unreadable, missing, or deleted SQLite risk state on system restart | Fails closed: starts in `Triggered` / `Halted` state; refuses to route any orders until explicitly initialized (`ADR-020`). |
| 2 | `PaperTradingEngine` | Bare `release_kill_switch.signal` file present without `ReleaseAuthorization` | Refuses release (`release_not_authorized`); remains in `Halted`. Signal file is a transport hint, not an authorization (`ADR-019`). |
| 3 | `ReleaseAuthorization` | Authorization record presented with fewer than 2 distinct non-blank approvers | Validation fails (`authorization_incomplete`); kill switch remains engaged (`ADR-019`). |
| 4 | `ReleaseAuthorization` | Replay of previously accepted nonce | Validation fails (`authorization_replayed`); logged to durable audit log; state remains untouched (`ADR-019`). |
| 5 | `SessionInitialization` | `initialize_new_session` called on a database where risk state already exists | Refuses with `initialization_conflicts_with_existing_state`; cannot be used to circumvent kill switch release discipline (`ADR-020`). |
| 6 | `SessionInitialization` | Expiry set beyond 24 hours ($>86,400$ seconds) from validation time | Refuses with `initialization_expiry_unbounded`; prevents long-lived authorization vulnerability (`ADR-020`). |
| 7 | `PromotionCertificate` | `TradeIntent` received with forged, altered, or expired Ed25519 signature | Execution engine raises `ValueError("Forged signature" / "Certificate is expired")`; intent is immediately rejected as Unauthorized (`ADR-028`). |
| 8 | `Sizer` | Account equity cannot fund a single minimum lot ($< \text{minimum\_quantity}$) | Returns `SizingResult(0, False, "Allocation cannot fund minimum lot")`; never forces a fractional or rounded-up minimum order (`ADR-028`). |
| 9 | `Sizer` | Currency conversion rate timestamp older than `data_freshness_threshold_ms` (5000ms) | Returns `SizingResult(0, False, "Market data is stale")`; halts trade emission fail-closed (`ADR-028`). |
| 10 | `PromotionGate` | Evaluation supplied with identical object or identical experiment ID for primary and replication | Fails closed with `replication_passed=False` and `confidence="LOW"` (prevents self-referential correlation cheat, `ADR-023 F1`). |
| 11 | `PromotionGate` | Strategy metric missing from `qualifications` columns (only present in free-text `notes`) | Gate fails closed; free-text regex parsing is permanently removed (`ADR-023 F3`, `ADR-024`). |
| 12 | `PromotionGate` | Strategy signal function raises an unhandled exception during backtest | Exception propagates up; halts gate evaluation rather than defaulting to flat zero-return series (`ADR-023 F7`). |
| 13 | `IBKRPaperAdapter` | Connection attempted against live port (7496 / 4001) instead of paper port (7497 / 8874) | Adapter constructor throws error and refuses initialization (`ADR-0006`, `ADR-018`). |
| 14 | `IBKRPaperAdapter` | FX order submitted with quantity not an integer multiple of 1,000 units | Instrument validation rejects intent before adapter dispatch (`Forex.spec.md`, `ADR-018`). |
| 15 | `ExecutionEngine` | Order submission request times out with no broker acknowledgement | Order transitions to `UNKNOWN` state; duplicate submissions blocked until reconciliation queries broker truth (`Order.spec.md`). |
| 16 | `ReconciliationEngine` | Broker position or cash balance differs from internal projection by $> \text{threshold}$ | Flags `Critical` drift; triggers kill switch, sets trading state to `HALTED`, and logs snapshot diffs (`ADR-0004`, `FAILURE_MATRIX.md`). |
| 17 | `FeatureGraph` | Tick event received for an instrument that previously ingested `BarClosed` events | Raises `SourceConsistencyError`; prevents mixing derived and external data sources for the same symbol (`FeatureGraph.spec.md`). |
| 18 | `BarAggregator` | Unaligned 1h bar received (not at UTC 00, 04, 08, 12, 16, 20) | Aggregates internally into the running 4h window; emits completed 4h bar strictly when full 4-bar window closes (`ADR-025`). |
| 19 | `CrossSectionalFactor` | Quantile weight vector has non-zero net dollar exposure ($|\sum w_i| > 10^{-6}$) | Fails normalization validation; rejects weight allocation (`EquitiesFactorResearch.spec.md`). |
| 20 | `CointegrationScreen` | Pair spread exhibits Engle-Granger $p > 0.05$ or non-stationary ADF statistic | Screening halts immediately; marks strategy as rejected (prevents mining non-stationary spreads, `ADR-025`). |
| 21 | `FxCostModel` | Simulation attempted without specifying `FxCostModel` or using bar-close constant bps | Model marked non-canonical; simulation engine tags result with `can_qualify=False`; promotion gate rejects (`ADR-031`). |
| 22 | `CryptoSimulator` | Order-flow event stream contains decreasing `sequence` or timestamp regression | Dataset quarantined; daily data slice invalidated fail-closed (`CryptoResearch.spec.md`). |

---

## 4. Requirements Specification Catalog (R1 to R6 Mapping)

### Requirement R1: Ground-Truth Code & Database Audit

```
Audited Boundaries:
├── core/src/                 (Rust deterministic core: types, orders, risk, portfolio, reconciliation)
├── src/titan/                (Python strategy, runtime, research, backtest, data, execution)
├── .titan_state.db           (SQLite event store: orders, risk snapshots, session audit logs)
└── research_data/
    └── titan_research.db     (SQLite research DB: runs, tags, qualifications, shadow events)
```

1. **State Store & Event Audit:**
   - `.titan_state.db` contains the immutable event log. The table schema includes `message_id` (UUID v7), `aggregate_id`, `aggregate_type`, `message_type`, `occurred_at`, `payload_json`, and `payload_digest`.
   - Legacy state migrations must be transactional and idempotent.
   - Any unreadable or corrupt event store causes the system to start in `Triggered`/`Halted` state (ADR-020).

2. **Research DB Audit & Legacy Qualification Retirement:**
   - `titan_research.db` holds `runs`, `qualifications`, `qualifications_audit`, `ensemble_runs`, `run_tags`, and `shadow_events`.
   - Under ADR-028 and ADR-022, all legacy `QUALIFIED` rows in `qualifications` must be retired into `qualifications_audit` with reason `Terminal report: structural integrity and cost-model violations`.
   - `qualifications` table schema must strictly contain: `strategy_id`, `version`, `status`, `backtest_sharpe`, `wf_sharpe`, `paper_trades`, `backtest_return`, `wf_return`, `max_dd_pct`, `qualified_at`, `notes`, `plateau_stability`, `plateau_coverage`, `replication_sharpe`, `max_correlation` (ADR-024).

3. **Failure Categorization Framework (AGENTS.md Rule 8 & ADR-029/030):**
   - Every failed experiment or negative result MUST be classified into one of two mutually exclusive categories:
     - **Mechanism Failure (`mechanism_failure`):** The underlying theory has no predictive alpha, information coefficient is statistically insignificant ($p > 0.05$), or the empirical relationship is directionally inverted across validation folds.
     - **Execution-Constrained Rejection (`execution_constrained`):** A gross economic transfer or alpha signal exists in frictionless price series, but realistic market frictions (bid-ask spread crossing, slippage impact, short borrow fees, and broker ticket minima) exceed the gross yield.
   - Negative results require `failure_mode`, `failure_mode_basis`, and `failure_mode_confidence` (`high` or `medium` with `disambiguation`).

---

### Requirement R2: Point-in-Time Data Ingestion & Quality Pipeline

1. **Cryptographic Data Manifests (`DataManifest` / `FactorManifest`):**
   - Ingestion requires a committed JSON manifest capturing:
     - `source_path`, `source_checksum` (SHA-256), `instrument_id`, `date_from`, `date_to`, `record_count`, `applied_adjustments` (split/dividend/delisting), `schema_version`, and `created_at`.
   - `compute_digest()` produces a SHA-256 hash of sorted key-value pairs. Orphan events or unverified digests cause immediate run rejection.

2. **Survivorship Bias & Corporate Actions:**
   - Equities data pipeline must enforce point-in-time universe selection (e.g. S&P 500 constituents and 90-day ADV as of inception date, including historical delistings, acquisitions, and bankruptcies).
   - Normalization pipeline (`src/titan/data/quality.py`) supports `pass_through_unknown=True` to retain delisted symbols without dropping them.
   - Splits and dividends are processed as explicit chronological events: splits adjust quantity and basis without PnL change; dividends generate cash movement events with realized PnL impact (`CorporateActions` in `src/titan/backtest/corporate_actions.py`).

3. **Quarantine & Gap Detection:**
   - Multi-layer validation via `validate_and_quarantine()`:
     - Schema and tick-alignment validation.
     - Duplicate timestamp detection per instrument.
     - Business day gap detection (flags weekday session gaps while recognizing valid weekend/holiday closures).
     - Intraday gap detection (quarantines gaps exceeding $5\times$ the expected bar interval).

4. **Multi-Asset Calendar Engines:**
   - Exchange calendars: NYSE/NASDAQ (`calendar.py`), Forex 24/5 (`calendar_forex.py`), Spot Metals (`calendar_spot_metals.py`), and Crypto 24/7/365 (`calendar_crypto.py`).

---

### Requirement R3: Strategy Development & Hypothesis Pre-Registration

1. **Pre-Registration Discipline & Schema:**
   - All research experiments must be pre-registered in immutable JSON artifacts (`EQ-00X-prereg.json` or `CR-00X-prereg.json`) prior to touching out-of-sample data.
   - Pre-registration binds: hypothesis ID, economic mechanism description, universe definition, lookback windows, factor ranking formulas, quantile thresholds, rebalance frequency, cost model parameters, in-sample/out-of-sample partition boundaries, and pass/fail thresholds.
   - Pre-registration SHA-256 hash is computed and stored. The simulation harness asserts that the OOS run hash matches the pre-registration hash.

2. **Mandatory 3D Replication Protocol:**
   - Strategies must pass independent replication across three orthogonal dimensions:
     1. **Instrument Replication:** Signal holds across multiple independent assets in the universe.
     2. **Time Period Replication:** Out-of-sample walk-forward stability across non-overlapping date folds.
     3. **Market Regime Replication:** Verified stability in Bull, Bear, High Volatility, Low Volatility, and Sideways market regimes.
   - Rejects identical-provenance returns (ADR-023 F1).

3. **Absorbing Negative Result Protocol:**
   - Failed hypotheses transition to permanent, absorbing `negative_result` records.
   - Lookback mining or post-hoc parameter tweaking on failed runs is forbidden. Testing an alternative mechanism requires registering a new canonical hypothesis ID (e.g. `EQ-001` $\rightarrow$ `EQ-002`).

4. **Mechanism Registry & MEI Tracking:**
   - MEI updates follow: $\text{MEI} = 0.30 \cdot \text{Replication} + 0.25 \cdot \text{StatSupport} + 0.20 \cdot \text{Stability} + 0.15 \cdot \text{Plausibility} + 0.10 \cdot \text{Generalization}$.
   - Milestone Gate for `Established Mechanism` ($\text{MEI} \ge 0.91$) requires satisfying all 6 constitutional conditions.

---

### Requirement R4: Canonical Cost-Aware Simulation Engine

1. **Immutable Cost Models (ADR-031):**
   - **`FxCostModel`:** USD-account, USD-quoted FX pairs. Commission calculated as $\max(\text{notional\_usd} \times \frac{\text{commission\_bps}}{10\,000}, \text{minimum\_commission\_usd})$ where IBKR standard minimum is $\$2.00$.
   - **`CryptoCostModel`:** Maker/taker fee tiers, 8-hour funding rate payments, liquidation penalties, and contract multipliers.
   - **`FactorCostModel`:** IBKR equity tier ($\$0.005/\text{share}$, $\$1.00$ minimum), $1.0\text{ bps}$ half-spread, $0.5\text{ bps}$ market impact slippage, and $50\text{ bps}$ annualized short borrow accrual.

2. **Execution Timing & Fill Realism:**
   - Signal calculated on bar $t$ produces a pending order executed on bar $t+1$.
   - **`QUOTE_NEXT_EVENT`:** Highest fidelity mode filling Buy orders at Ask and Sell orders at Bid.
   - **`BAR_NEXT_OPEN`:** Bar-open fill with explicit synthetic adverse spread and slippage. Must be tagged `can_qualify=False` for promotion gates. Bar-close constant-bps fills are strictly forbidden for qualification.

3. **Attribution & Plateau Validation:**
   - Simulation output must produce granular attribution: `gross_pnl`, `commissions`, `spread_cost`, `slippage_cost`, `borrow_fees`, `turnover`, `net_pnl`, `net_sharpe`, `max_drawdown`.
   - Parameter stability requires evaluating contiguous parameter surfaces: minimum plateau stability $\ge 0.70$, plateau coverage $\ge 0.20$.

---

### Requirement R5: Deterministic Risk Gates & Paper Ingress

1. **Risk Gate Pipeline Order (`Risk.spec.md` & `core/src/risk.rs`):**
   $$\text{TradeIntent} \longrightarrow \text{Schema/Integrity} \longrightarrow \text{Certificate Verification} \longrightarrow \text{Strategy Eligibility} \longrightarrow \text{Data Freshness} \longrightarrow \text{Order Limits} \longrightarrow \text{Position/Exposure} \longrightarrow \text{Portfolio Drawdown} \longrightarrow \text{Liquidity/Impact} \longrightarrow \text{Broker/Session Health} \longrightarrow \text{ApprovedOrderIntent}$$

2. **State Machines & Kill Switch:**
   - **Trading States:** `ACTIVE` (normal routing), `REDUCING` (only position-reducing orders permitted), `HALTED` (all routing blocked).
   - **Kill Switch States:** `ARMED` $\rightarrow$ `TRIGGERED` $\rightarrow$ `RELEASING` $\rightarrow$ `RELEASED`. Never auto-resets.
   - Missing, deleted, or unreadable state database defaults to `Triggered`/`Halted` (ADR-020).

3. **Dual-Human Release & Session Initialization (ADR-019, ADR-020):**
   - Release requires `ReleaseAuthorization` JSON containing: 2 authorized human signatures, correlation ID, root-cause assessment, remediation reference, bounded expiry, and replay-protection nonce.
   - Release gate evaluates `FeedHealthVerdict` from `TWSRealtimeFeed` (`feed_stale`, `feed_absent`, `bar_not_advancing`, `instrument_uncovered`). Stalled feeds block release.
   - Fresh paper environments are initialized using `SessionInitialization` via `python scripts/init_session.py` with 2 distinct approvers (max TTL 24h).

4. **IBKR Paper Ingress (TWS Port 7497):**
   - Dedicated paper-port validation (TWS 7497, Gateway 8874). Live ports (7496/4001) are hard-rejected.
   - Forex pairs routed as `CASH` on `IDEALPRO` with 1,000-unit micro-lots. Equities routed as `STK` on `SMART`/`ARCA`.
   - All runtime intents require signed Ed25519 execution certificates (`PromotionCertificate`). Unsigned intents or shadow proposals are blocked at ingress.

5. **Order State Machine & Reconciliation Engine:**
   - Order aggregate lifecycle: `NEW` $\rightarrow$ `VALIDATED` $\rightarrow$ `SUBMITTED` $\rightarrow$ `ACKNOWLEDGED` $\rightarrow$ `PARTIALLY_FILLED` $\rightarrow$ `FILLED` / `CANCELLED` / `EXPIRED`.
   - Ambiguous or timed-out orders transition to `UNKNOWN`. No resubmission is allowed until 3-interval reconciliation (`inflight`, `open`, `positions`) resolves broker truth. Critical drift ($>\text{threshold}$) halts routing immediately.

---

### Requirement R6: Staged Deployment & Live Governance

1. **4-Stage Capital Progression:**
   $$\text{Simulation (Replay/WFO)} \longrightarrow \text{Paper Trading (TWS 7497)} \longrightarrow \text{Restricted Live (Strict Limits)} \longrightarrow \text{Scaled Live (Scaled Capital)}$$
   - Progression between stages requires human sign-off, recorded reconciliation evidence, and cryptographic certificate issuance. Positive backtests or LLM recommendations are legally and operationally insufficient.

2. **Cryptographic Promotion Certificates (ADR-028):**
   - Issued as canonical JSON with SHA-256 digest and Ed25519 signature.
   - Binds: strategy ID, version, parameter snapshot, allowed instruments, timeframes, environment (`PAPER` / `LIVE`), dataset digests, cost model digests, sizing parameters, out-of-sample evidence hash, expiry timestamp, and two authorized human approver IDs.
   - Loaded into `PromotionCertificateRegistry`. Verified fail-closed on every intent submission.

3. **6-Condition Implementation Gate (AGENTS.md & ADR-0001):**
   Before any production deployment or code promotion:
   1. *Specification exists:* Accepted `.spec.md` in `specifications/`.
   2. *ADR accepted:* Consequential decision record ratified per `ADR.md`.
   3. *Tests written:* Unit, contract, and integration tests for every state transition and failure mode.
   4. *Verification defined:* Acceptance criteria measurable and tested.
   5. *Rollback defined:* Documented zero-data-loss rollback procedure.
   6. *Monitoring defined:* Telemetry metrics, alerts, and SLOs specified.

4. **Live Trading Authority Boundaries:**
   - AI models and research agents must never hold broker credentials, place orders, route capital, modify balances, override risk limits, or self-issue certificates.

---

## 5. Caveats

1. **Hardware & Environment Specifics:** Execution and replay latency benchmarks in `PERFORMANCE_SPEC.md` (<50µs risk gate, <100µs submit persist) assume dedicated x86_64 hardware and compiled native Rust extensions (`_core.pyd`). Python fallback mode provides identical deterministic logic but higher latency.
2. **Broker API Limitations:** IBKR TWS paper accounts simulate execution and margin against live market data streams, but execution fills on paper can differ from real-world limit book queues. Paper fills should be reconciled continuously against simulated quote-sided models.
3. **Data Licensing:** Historical tick data and intraday order flow for crypto and equities require licensed data providers. Research data fixtures in `research_data/` must adhere to committed data manifests.

---

## 6. Conclusion

Project TITAN possesses a complete, rigorous, and institutionally hardened governance and specification foundation. The constitutional boundary between untrusted advisory research (AI/Python) and deterministic execution (Rust/SQLite) is fully formalized across 26 ADRs, 22 formal specifications, and strict JSON contracts. 

The previous alpha-search directional search class is cleanly terminated per `ALPHA_SEARCH_TERMINAL_REPORT.md` and ADR-026. The platform is primed for Generation 2 (Alpha Discovery v2.0), operating across US Equities Cross-Sectional Factors (ADR-030), Crypto Market Structure (ADR-029), and Canonical FX Cost-Aware Simulations (ADR-031), governed by fail-closed risk gates, dual-human authorization (ADR-019, ADR-020), and cryptographic promotion certificates (ADR-028).

---

## 7. Verification Method

To independently verify the facts, contracts, and specifications documented in this report:

1. **Inspect Core Governance & Constitutions:**
   ```pwsh
   # Verify constitutional rules and implementation gates
   Get-Content "D:\projects\Project TITAN\AGENTS.md" | Select-String -Pattern "Rule", "gate"
   Get-Content "D:\projects\Project TITAN\RISK_POLICY.md" | Select-String -Pattern "Kill switch", "Controls"
   Get-Content "D:\projects\Project TITAN\AI_GOVERNANCE.md" | Select-String -Pattern "Authority boundary"
   ```

2. **Verify ADR Ratifications:**
   ```pwsh
   # Confirm acceptance of ADR-028, ADR-029, ADR-030, ADR-031
   Get-Content "D:\projects\Project TITAN\docs\adr\ADR-028-execution-integrity-and-sizing.md" | Select-String "Status:"
   Get-Content "D:\projects\Project TITAN\docs\adr\ADR-029-crypto-market-structure-research.md" | Select-String "Status:"
   Get-Content "D:\projects\Project TITAN\docs\adr\ADR-030-equities-cross-sectional-factor-research.md" | Select-String "Status:"
   Get-Content "D:\projects\Project TITAN\docs\adr\ADR-031-canonical-fx-simulation-evidence.md" | Select-String "Status:"
   ```

3. **Verify Formal Specifications & Contracts:**
   ```pwsh
   # Check specification files and JSON schema definitions
   Get-ChildItem "D:\projects\Project TITAN\specifications"
   Get-ChildItem "D:\projects\Project TITAN\contracts"
   ```

4. **Execute Test Suite Invariants:**
   ```pwsh
   # Run pytest on the full research, risk, and strategy test suites
   pytest tests/research/ tests/risk/ tests/strategies/ tests/execution/ -v
   ```

5. **Invalidation Conditions:**
   - Any modification to `AGENTS.md` or `RISK_POLICY.md` without Architecture Council and Risk Owner approval invalidates this catalog.
   - Any inclusion of unversioned, frictionless constant-bps backtests as promotion evidence invalidates qualification authority under ADR-031.
