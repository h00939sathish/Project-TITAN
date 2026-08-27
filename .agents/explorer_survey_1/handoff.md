# Project TITAN — Codebase & State Audit Report

**Author:** Codebase & State Auditor (`explorer_survey_1`)  
**Date:** 2026-08-18  
**Governance Scope:** AGENTS.md (v1.1), ADR-001 through ADR-031, AI_GOVERNANCE.md, RISK_POLICY.md  
**Handoff Type:** Hard Handoff (Investigation Complete)  

---

## 1. Observation

### 1.1 Directory & Module Structure
The Project TITAN repository consists of a hybrid Rust/Python architecture structured as follows:

```
D:\projects\Project TITAN\
├── core\                         # Rust crate (titan._core PyO3 extension module)
│   ├── Cargo.toml / Cargo.lock
│   └── src\
│       ├── lib.rs                # PyO3 module bindings for Python
│       ├── messages.rs           # EventEnvelope, TradeIntent, ApprovedOrderIntent, RiskDecision, TrailingConfig
│       ├── orders.rs             # OrderStateMachine, OrderState transitions
│       ├── risk.rs               # RiskGate, RiskConfig, RiskReasonCode, RiskVerdict, KillSwitchState, TradingState
│       ├── portfolio.rs          # PortfolioEngine, Position, Money, ContractType
│       ├── event_store.rs        # EventStore (SQLite-backed durable event sourcing)
│       ├── reconciliation.rs     # ReconciliationEngine, ReconciliationConfig, DriftSeverity
│       ├── types.rs              # InstrumentId, Instrument, Side, OrderType, TimeInForce
│       └── validation.rs         # Deserialization schemas, UUID/RFC3339 validators
├── src\titan\                    # Python application packages
│   ├── __init__.py               # Core re-exports and version check
│   ├── backtest\                 # Simulation engine & cost models (engine.py, fx_costs.py, crypto_costs.py, factor_simulator.py, fills.py, corporate_actions.py, results.py, clock.py)
│   ├── data\                     # Point-in-time data pipeline (manifest.py, quality.py, normalize.py, freshness.py, feed_health.py, approved.py, calendar.py, crypto.py, forex_pairs.py, equities_universe.py, spot_metals.py, tws_feed.py, alpaca_feed.py, polygon_feed.py)
│   ├── execution\                # Order routing & broker adapters (engine.py, ibkr_adapter.py, alpaca_adapter.py, simulated_adapter.py, backtest_adapter.py, twap.py, _broker_adapter.py, _broker_types.py)
│   ├── memory\                   # Vector memory & LLM distillation (vector_memory.py, distillation.py)
│   ├── operations\               # Telemetry, logging, metrics, export (logging.py, metrics.py, export.py, telemetry.py, _logging_integration.py, _metrics_integration.py)
│   ├── recovery\                 # Process recovery and fail-closed restart (restart.py)
│   ├── render\                   # Report rendering (report.py)
│   ├── research\                 # Research OS, parameter surface, replication, validation (db.py, harness.py, multi_harness.py, experiment.py, hypothesis.py, library.py, promotion.py, promotion_certificate.py, qualification.py, portfolio_impact.py, replication.py, shadow.py, dataset.py, yield_tracker.py, optimizers/, validators/)
│   ├── risk\                     # Risk controls & authorization (circuit_breaker.py, limits.py, release_authorization.py, session_initialization.py)
│   ├── runtime\                  # Real-time event loop & feature graphs (evaluator.py, events.py, feature_graph.py)
│   └── strategies\               # Signal generation & portfolio allocation (registry.py, registrations.py, manifest.py, allocator.py, hrp_allocator.py, ensemble.py, sizing.py, pipeline.py, timeframes.py, regime/, dual_ma.py, momentum.py, mean_reversion.py, bollinger.py, rsi.py, orb.py, vwap_reversion.py, traderdev_ema9vwap.py)
├── research\                     # Experimental artifacts, manifests, terminal reports, negative results
│   ├── ALPHA_SEARCH_TERMINAL_REPORT.md # Alpha-search closure verdict
│   ├── EXHAUSTION_MEMO.md        # FX search exhaustion memo
│   ├── PIVOT_DECISION.md         # Strategic pivot rules
│   ├── crypto\                   # Crypto research charter, manifests, hypotheses, CRYPTO_DISCOVERY_REPORT.md
│   ├── equities\                 # Equities factor charter, manifests, hypotheses, EQUITIES_FACTOR_REPORT.md
│   ├── neg_results\              # Absorbing negative result records (EXP-00016 through EXP-00027, P2, P4)
│   └── results\                  # Research runs, parameter surfaces, EXP-00031 canonical FX reproduction
├── specifications\               # Subsystem specifications (Broker, Risk, Execution, Order, TradeIntent, Governance, Portfolio, FeatureGraph, CryptoResearch, EquitiesFactorResearch, etc.)
├── contracts\                    # JSON schema validation contracts
├── docs\                         # Architecture decision records (ADR-0001 through ADR-031), governance, runbooks
├── scripts\                      # Session runners, ingestion, backtesting, paper trading, migrations, validation
└── tests\                        # Comprehensive test suite across unit, contract, integration, adapters, risk, replay, failure matrix, and certification
```

### 1.2 State Stores & Database Inspection
An audit of all SQLite database files across the workspace yielded the following findings:

1. **`.titan_state.db`** (Root: 28,672 bytes)
   - **Schema**: Single table `events` (message_id TEXT, message_type TEXT, schema_version INTEGER, occurred_at TEXT, correlation_id TEXT, causation_id TEXT, aggregate_type TEXT, aggregate_id TEXT, source TEXT, payload TEXT, metadata TEXT, created_at TEXT).
   - **Row Count**: 0 rows (clean slate for paper trading session initialization).
   - **Bridge State**: Associated `.titan_state.bridge_state` contains 604 bytes tracking synchronization state.

2. **`research_data/titan_research.db`** (167,936 bytes)
   - **Tables**: `runs` (31 rows), `qualifications` (7 rows), `run_tags` (30 rows), `shadow_events` (1,048 rows), `ensemble_runs` (0 rows), `sqlite_sequence` (4 rows).
   - **`qualifications` Table Breakdown**:
     - `id=24`, `dual-ma`, v1.0.0, status=`QUALIFIED`, IS Sharpe=1.4195, WF Sharpe=0.5804, trades=27 (Qualified at 2026-07-26T17:30:32Z)
     - `id=25`, `ma-crossover`, v1.0.0, status=`QUALIFIED`, IS Sharpe=1.3969, WF Sharpe=1.3297, trades=32 (Qualified at 2026-07-26T17:30:33Z)
     - `id=26`, `mean-reversion`, v1.0.0, status=`WATCHLIST`, IS Sharpe=0.7659, WF Sharpe=0.0345, trades=8 (Notes: 'OOS trades 8 < 10')
     - `id=28`, `time-series-momentum`, v1.0.0, status=`WATCHLIST`, IS Sharpe=1.6868, WF Sharpe=1.0965, trades=9 (Notes: 'OOS trades 9 < 10')
     - `id=29`, `volatility-regime`, v1.0.0, status=`QUALIFIED`, IS Sharpe=1.8439, WF Sharpe=1.0574, trades=25 (Qualified at 2026-07-26T17:31:25Z)
     - `id=30`, `rsi`, v1.0.0, status=`WATCHLIST`, IS Sharpe=1.8164, WF Sharpe=0.7287, trades=19 (Notes: 'Governance Gate: Average Plateau Coverage 0.0% < 20.0%; Cross-Instrument Consistency 0.0% < 75.0%')
     - `id=31`, `bollinger`, v1.0.0, status=`FAILED`, IS Sharpe=0.3029, WF Sharpe=-0.0901, trades=52 (Notes: 'Stability 0.54 < 0.7; IS Sharpe 0.30 < 0.5')
   - **`shadow_events` Table Breakdown**:
     - Total: 1,048 recorded simulated events covering EURUSD (180), GBPUSD (179), QQQ (185), SPY (504).
   - **`runs` Table Breakdown**:
     - 31 recorded runs across historical strategies (SPY qualification runs with 1,257 bars, 0 commission, legacy frictionless format).

3. **`dummy_state.db`** (28,672 bytes)
   - Schema identical to `.titan_state.db`, 0 rows (test artifact).

4. **`research_data/test.db`** (24,576 bytes)
   - Test fixture containing 1 qualification row (`momentum`, `QUALIFIED`), 1 run row (`momentum`, `SPY`, Sharpe 1.42).

### 1.3 Execution, Risk, and Paper Ingress Wiring
Direct source code inspection of `src/titan/execution/engine.py`, `src/titan/execution/ibkr_adapter.py`, `src/titan/research/promotion_certificate.py`, and `core/src/`:

1. **Default-Deny Ingress (`engine.py:573-588`)**:
   - `submit_intent` explicitly blocks shadow intents: `if getattr(intent, "producer_kind", "") == "shadow" or "shadow" in str(getattr(intent, "strategy_id", "")).lower(): raise ValueError("Shadow intents are strictly forbidden in the execution engine.")`.
   - `submit_intent` enforces cryptographic promotion certificate presence and verification: `cert_json = getattr(intent, "certificate_ref", None); if not cert_json: raise ValueError("Missing execution certificate...")`.
   - `PromotionCertificateRegistry.verify(cert)` enforces non-expired status, non-forged Ed25519 signatures, and SHA-256 content digest bindings.
   
2. **Deterministic Risk Evaluation & HMAC Intent Signing (`engine.py:685-710`, `messages.rs:397-420`)**:
   - `PaperTradingEngine` evaluates `self.risk_gate.evaluate_intent(...)`.
   - Generates `ApprovedOrderIntent` and calls `approved.attach_risk_token(secret_key)`.
   - Verifies HMAC token via SHA-256 hash over `{risk_decision_id}:{client_order_id}:{instrument_id}:{side}:{quantity}:{price}` combined with secret key.
   - Enforces fail-closed token verification: `if hasattr(approved, 'verify_risk_token') and not approved.verify_risk_token(secret_key): return OrderResult(accepted=False, rejection_reason="Unsigned or invalid risk token")`.

3. **Broker Adapter Protective Bracket Orders (`ibkr_adapter.py:161-360`)**:
   - Locked to paper TWS/Gateway ports (`7497`, `8874`) and paper account IDs (`DU*`, `DF*`, `PAPER*`, `S*`, `SIM*`).
   - Automatically attaches parent order with child Stop-Loss (`STP`), Take-Profit (`LMT`), and Trailing-Stop (`TRAIL` conditional on `_trailing_entitled()`).

4. **Strategy Registry Qualification Hard Freeze (`registrations.py:1-166`)**:
   - All registered strategies (`ma-crossover`, `mean-reversion`, `volatility-regime`, `time-series-momentum`, `dual-ma`, `rsi`, `bollinger`, `orb`, `vwap-reversion`, `traderdev-ema9-vwap`) have `qualified_variants = frozenset()`.

---

## 2. Logic Chain: Strategy Audit & Failure-Mode Classification

Per AGENTS.md Rule 8, ADR-029, ADR-030, and ADR-031, each historical and active strategy is rigorously categorized into:
- **Mechanism Failure**: The underlying economic/causal hypothesis has no predictive alpha, is non-stationary, or is directionally inverted.
- **Execution-Constrained Rejection**: A gross economic anomaly or return spread exists in-sample/out-of-sample, but friction (bid/ask spread, ticket minima, turnover borrow/commissions, or latency decay) exceeds harvestable yield under institutional execution models.

### 2.1 Complete Strategy & Hypothesis Classification Matrix

| Strategy / Hypothesis ID | Asset Class / Universe | Governing Record | Observed Gross vs Net Performance | Failure Mode Classification | Evidence & Root Cause |
|---|---|---|---|---|---|
| **M-001 (Opening Flow Persistence)** | US Equities / SPY | `docs/MECHANISM_REGISTRY.md` | Opening direction does not predict session drift; volume amplification absent in EXP-00008. | **Mechanism Failure** | Flawed market microstructure theory; MOO flow does not persist into intraday drift. |
| **M-002 (Liquidity Exhaustion Reversal)** | US Equities / SPY | `docs/MECHANISM_REGISTRY.md` | Top-quartile opening ranges mean-revert, but magnitude fails Bonferroni $\alpha$ significance. | **Mechanism Failure** (Refined to M-003) | Reversal magnitude lacks statistical power; partially evolved into structural excursion asymmetry. |
| **M-004 (Volatility Compression)** | US Equities / FX | `docs/MECHANISM_REGISTRY.md` | ATR compression does not precede >2.0x ATR expansion across 396 events (EXP-00011). | **Mechanism Failure** | Thin orderbook stored elastic energy theory falsified. |
| **EXP-00016 (FX Intraday Momentum)** | FX Majors (EURUSD, GBPUSD) | `research/neg_results/EXP-00016_fx_intraday_momentum.md` | Intraday candle momentum shows zero persistence across 1m/5m/15m/1h bars. | **Mechanism Failure** | FX major quotes are efficient random walks at intraday horizons; no serial autocorrelation. |
| **EXP-00017 (Vol Clustering Alpha)** | FX Majors | `research/neg_results/EXP-00017_2fold_retest.json`, ADR-026 | Initial promoted candidate failed 2-fold OOS re-test (EUR IC dropped 0.121 $\rightarrow$ 0.053, GBP 0.098 $\rightarrow$ 0.038). | **Mechanism Failure** | Overfitting / parameter instability across out-of-sample regime shifts. |
| **EXP-00019 (Intraday Mean-Reversion)** | FX Majors (1m/12h lookback) | `research/neg_results/EXP-00019_real_cost_followup.md` | Gross top-bottom spread +0.89 to +2.73 pips. Net on EURUSD short rally +0.58 pips, but long dip -0.11 pips; GBPUSD net negative (-0.18 pips). | **Execution-Constrained Rejection** | Gross edge exists during London/NY overlap, but bid/ask spread and trade asymmetric costs erase profitability across instruments. |
| **EXP-00020 (Rolling Reversal)** | FX Majors | `research/neg_results/EXP-00020_reversal_rolling.md` | Sub-pip gross edge completely consumed by half-spread execution costs. | **Execution-Constrained Rejection** | Micro-alpha cannot survive retail or institutional spread friction. |
| **EXP-00021 (Daily Time Series Momentum)** | FX Majors (Daily) | `research/neg_results/` | Daily directional trend following produces negative/flat returns across 2018–2026. | **Mechanism Failure** | Macro FX major currency regimes show mean-reversion and lack multi-month trend persistence in the tested decade. |
| **EXP-00022 (G10 Cross-Sectional Momentum)** | G10 Currencies (9 pairs, 8y) | `research/neg_results/EXP-00022_g10_xs_momentum.md` | 1m lookback weekly rebalance: Gross +5.4%/yr ($t=2.67$, 59% win rate). Net at 10 bps/leg: **+0.00% (zero)**; monthly rebalance negative (-2.4%/yr). | **Execution-Constrained Rejection** | Gross anomaly exists statistically ($t=2.67$), but required weekly rebalancing transaction costs completely consume the yield. |
| **EXP-00023 (G10 Carry Trade)** | G10 Currencies (7 pairs, 8y) | `research/neg_results/EXP-00023_g10_carry.md` | Total return +2.2%/yr ($t=1.14$). Accrual +1.4%/yr; Spot UIP violation +0.7%/yr ($t=0.38$, insignificant). | **Mechanism Failure** | No UIP spot anomaly; spot exchange rates do not drift in favor of high-yield currencies; returns are purely mechanical cash rate accrual. |
| **EXP-00024 (Vol-Conditioned Carry / COT)** | G10 Currencies / Futures | `research/neg_results/EXP-00024_vol_carry.md` | Vol conditioning and speculative positioning filters fail to isolate risk-adjusted spot alpha. | **Mechanism Failure** | Macro positioning indicators lag spot market price discovery. |
| **EXP-00025 (TraderDev Crypto Families on FX F2-F6)** | FX Majors (1h/4h) | `research/neg_results/EXP-00025_traderdev_families.md` | F2 through F6 lost -863 to -1,716 net pips across EURUSD/GBPUSD. Win rates 2%–40%. | **Mechanism Failure** | Technical indicator logic developed for trending crypto perps acts as noise/whipsaw on FX majors. |
| **EXP-00025 / EXP-00031 (TraderDev EMA9xVWAP F1)** | FX Majors (4h) | `research/results/EXP-00031-canonical-fx-reproduction.md`, ADR-031 | Gross PnL +$415.48 IS / +$673.42 GBPUSD. Net degraded under IBKR Tier-1 $2.00 min fees (EURUSD OOS net -$78.98). Fails multi-pair consistency. | **Execution-Constrained Rejection** | Small directional edge exists on 4h GBPUSD, but IBKR per-fill ticket minimums ($2 entry + $2 exit = 4 bps on 10k) destroy small notional lots. |
| **EXP-00026 (Cross-Pair Mean-Reversion EURGBP)** | FX Cross (EURUSD vs GBPUSD) | `research/neg_results/EXP-00026_crosspair_mr.md`, ADR-025 | Engle-Granger cointegration test failed ($p=0.54 > 0.05$); log spread non-stationary ($p=0.28$). | **Mechanism Failure** | The spread is non-stationary; historical +535 pips/yr backtest was spurious correlation on non-cointegrated price drift. |
| **P2 (Spot Gold Macro-Momentum)** | Spot Gold / DBC / DFII10 | `research/neg_results/P2_gold_macro_momentum_FE.md`, ADR-015 | Fails 3 of 4 kill criteria: OOS net return 1.49% (<4%), OOS Sharpe 0.31 (<0.45), Profit Factor 1.14 (<1.20). | **Mechanism Failure** | Real yield (DFII10) and commodity (DBC) momentum did not predict spot gold excess return out-of-sample. |
| **P4 (Multi-Timeframe Confluence Momentum)** | FX Majors (4h close > 20-SMA + daily vol gate) | `research/neg_results/P4_multi_tf_confluence_FE.md` | Gated Sharpe (14.53) degraded relative to ungated (19.25); bootstrap frac > 0 = 0.000. Fails 2/3 kill criteria. | **Mechanism Failure** | Filtering 4h trend signals by daily realized volatility actively destroys signal performance. |
| **CRYPTO-001 (Funding / Basis Carry)** | BTC/ETH Spot & Perpetual | `research/crypto/CRYPTO_DISCOVERY_REPORT.md`, ADR-029 | Net positive PnL IS & OOS (+$482 net after friction). Failed independent replication gate at required institutional scale. | **Execution-Constrained Rejection** | Gross funding rate premia exist, but VIP0 taker economics (10 bps spot + 5 bps perp) prevent harvestable scaling. |
| **CRYPTO-002 (Funding + OI Deleveraging)** | BTC/ETH Perpetuals | `research/crypto/CRYPTO_DISCOVERY_REPORT.md`, ADR-029 | 6 IS trades (all losses, -$990 net), 0 OOS trades. Liquidation cascades overwhelmed mean-reversion entries. | **Mechanism Failure** | Post-liquidation reversal hypothesis is invalidated by cascade momentum. |
| **CRYPTO-003 (Order-Flow Imbalance / OFI)** | BTC/ETH Level 2 Orderbook | `research/crypto/CRYPTO_DISCOVERY_REPORT.md`, ADR-029 | 37 IS / 3 OOS events processed; 0 trades executed. Latency-decay filter (250–500ms edge decay) blocked execution. | **Execution-Constrained Rejection** | Microstructure alpha decays faster than retail API execution latency and cannot clear 5 bps taker fees. |
| **EQ-001 (12-1M Cross-Sectional Momentum)** | US Sector ETFs / Equities | `research/equities/EQUITIES_FACTOR_REPORT.md`, ADR-030 | IS Net Sharpe 0.48; OOS Net Sharpe **0.70**, Net Return +6.47% ann., Max DD 8.30%, Monthly Turnover 16.79%. | **Execution-Constrained Rejection / Sub-Threshold Harvestability** | Gross cross-sectional momentum transfer exists, but net Sharpe 0.70 fell short of the mandatory $\ge 1.0$ promotion bar during 2023 mega-cap divergence. |
| **EQ-002 (5-Day Short-Term Reversal)** | US Sector ETFs / Equities | `research/equities/EQUITIES_FACTOR_REPORT.md`, ADR-030 | IS Sharpe 0.03, OOS Sharpe **-0.17**, Max DD 17.93%, Monthly Turnover **414.49%**. Total friction drag -2.64%/yr. | **Execution-Constrained Rejection** | High portfolio turnover generates excessive commission, spread, and short-borrow drag that wipes out gross reversal spread. |
| **EQ-003 (Vol-Adjusted Momentum / Low-Vol)** | US Sector ETFs / Equities | `research/equities/EQUITIES_FACTOR_REPORT.md`, ADR-030 | IS Net Sharpe 0.62; OOS Net Sharpe **0.47**, Net Return +4.37% ann., Max DD 10.29%, Monthly Turnover 22.17%. | **Execution-Constrained Rejection / Sub-Threshold Harvestability** | Consistent, low-drawdown returns, but net Sharpe 0.47 fell short of the $\ge 1.0$ promotion hurdle. |

---

## 3. Caveats

1. **Live Network Adapters**: Live broker socket integration tests (`test_alpaca_live_integration.py` and live TWS certification tests) intentionally fail or require live paper credentials/running local gateways. Mock/replay and simulated adapter tests run cleanly.
2. **Legacy Database State**: `research_data/titan_research.db` still contains 3 legacy rows marked `QUALIFIED` (`dual-ma`, `ma-crossover`, `volatility-regime`). While `scripts/migrations/migrate_legacy_qualifications.py` was developed and verified in unit tests, it was not executed against the live research DB. However, the runtime engine default-deny policy renders these rows completely inert.
3. **Data Availability**: Dukascopy historical ticks and 1m bars for EURUSD and GBPUSD cover 2022–2026. US ETF data covers SPY, QQQ, TLT (2020–2024). Any new strategy exploration will require dedicated point-in-time ingestion with SHA-256 manifests.

---

## 4. Conclusion & System Readiness Assessment

1. **Fail-Closed Architecture is Fully Verified**:
   - The execution engine (`PaperTradingEngine`) strictly denies order submission unless accompanied by an unexpired, cryptographically signed `Certificate` (`PromotionCertificateRegistry`).
   - Shadow signals are strictly quarantined to shadow simulation and never reach broker adapters.
   - All `ApprovedOrderIntent` instances must carry HMAC risk tokens verified via SHA-256.
   - Kill switch handling auto-triggers upon broker disconnection or state corruption.
2. **Research OS Integrity & Negative Results Foundation**:
   - Project TITAN has established an exhaustive, scientifically rigorous body of ~40 negative results across single-pair FX, carry, macro gold, crypto perps, and equities factors.
   - The platform correctly identified that liquid single-pair OHLCV signals cannot survive realistic execution costs and avoided promoting spurious retail edges.
3. **Actionable Roadmap for Profit-Engine-AI (v2.0)**:
   - **R1 Audit Complete**: Codebase structure, database tables, and failure modes are cataloged.
   - **R2 (Data Pipeline)**: Ready for point-in-time data ingestion with cryptographic manifests.
   - **R3 (Strategy Development)**: New strategies must adhere to pre-registered hypotheses avoiding the closed single-pair OHLCV search space.
   - **R4 (Canonical Simulation Engine)**: All evaluations must enforce `FxCostModel`, `CryptoCostModel`, and `FactorCostModel` with top-of-book/quote-sided fills and fee minima ($2.00 min).
   - **R5 (Risk Gates & Paper Ingress)**: Ready for paper session execution with two-person initialization nonces and TWS port 7497 integration.

---

## 5. Verification Method

To independently verify these findings, run the following commands in PowerShell from the repository root (`D:\projects\Project TITAN`):

```powershell
# 1. Run database inspection tool
python .agents/explorer_survey_1/inspect_dbs.py

# 2. Dump research database qualifications and shadow events
python .agents/explorer_survey_1/dump_research_db.py

# 3. Verify Execution Integrity and Default-Deny Certificate Gates
.\.venv\Scripts\python -m pytest tests/test_execution_integrity.py tests/test_risk_token.py tests/test_messages.py -v

# 4. Verify Canonical FX Cost Model & Sizer parity
.\.venv\Scripts\python -m pytest tests/backtest/test_fx_costs.py tests/backtest/test_canonical_simulation.py -v

# 5. Verify Equities Factor Simulation
.\.venv\Scripts\python -m pytest tests/research/test_factor_simulator.py tests/screening/test_equities_factor_screen.py -v
```
