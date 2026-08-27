# E2E Test Infra: Profit-Engine-AI (v2.0) on Project TITAN

## Test Philosophy
- **Opaque-box & Requirement-driven**: Derived directly from `ORIGINAL_REQUEST.md`, `AGENTS.md`, and system specifications without coupling to internal private implementations.
- **Methodology**: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Simulation.
- **Invariants Verified**:
  1. Default-Deny execution ingress strictly blocks uncertified or shadow intents.
  2. Institutional transaction costs (ADR-031 $2.00 fee minimum, borrow rates, taker fees) are rigorously deducted.
  3. Pre-registered hypotheses failing out-of-sample tests terminate into absorbing negative results.
  4. Deterministic risk gates veto invalid orders before broker routing.
  5. HMAC risk tokens are verified on all approved orders.
  6. Two-human authorization nonces and verified feed health are required for session release.

---

## Feature Inventory & Test Coverage Mapping

| # | Feature Area | Requirement Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Real-World) |
|---|--------------|-------------------|:-----------------:|:-----------------:|:-----------------:|:-------------------:|
| 1 | **Code & DB Audit (R1)** | ORIGINAL_REQUEST §R1, AGENTS.md Rule 8 | 5 tests | 5 tests | ✓ | ✓ |
| 2 | **PIT Data Ingestion & Quality (R2)** | ORIGINAL_REQUEST §R2, ADR-028 | 5 tests | 5 tests | ✓ | ✓ |
| 3 | **SHA-256 Manifests & Provenance (R2)** | ORIGINAL_REQUEST §R2, ADR-028 | 5 tests | 5 tests | ✓ | ✓ |
| 4 | **Corporate Actions & Survivorship (R2)** | ORIGINAL_REQUEST §R2, ADR-030 | 5 tests | 5 tests | ✓ | ✓ |
| 5 | **Hypothesis Pre-Registration (R3)** | ORIGINAL_REQUEST §R3, ADR-029/030 | 5 tests | 5 tests | ✓ | ✓ |
| 6 | **Absorbing Negative Results (R3)** | ORIGINAL_REQUEST §R3, ADR-029/030 | 5 tests | 5 tests | ✓ | ✓ |
| 7 | **Canonical Cost Accounting (R4)** | ORIGINAL_REQUEST §R4, ADR-031 | 5 tests | 5 tests | ✓ | ✓ |
| 8 | **Quote-Sided Fills & Metrics (R4)** | ORIGINAL_REQUEST §R4, ADR-005/031 | 5 tests | 5 tests | ✓ | ✓ |
| 9 | **Default-Deny & Cert Gate (R5)** | ORIGINAL_REQUEST §R5, ADR-028 | 5 tests | 5 tests | ✓ | ✓ |
| 10 | **Deterministic Risk & HMAC Signing (R5)** | ORIGINAL_REQUEST §R5, RISK_POLICY | 5 tests | 5 tests | ✓ | ✓ |
| 11 | **IBKR TWS 7497 Paper Ingress (R5)** | ORIGINAL_REQUEST §R5, ADR-018 | 5 tests | 5 tests | ✓ | ✓ |
| 12 | **Staged Deployment & Governance (R6)** | ORIGINAL_REQUEST §R6, ADR-019/020 | 5 tests | 5 tests | ✓ | ✓ |

---

## Test Architecture & Tier Breakdown

### Tier 1: Feature Coverage
- **Goal**: Verify each of the 12 core features in isolation with representative valid inputs.
- **Coverage**: $\ge 60$ test cases ($12 \times 5$).
- **Test Categories**:
  - `test_audit_failure_categorization` (Mechanism vs Execution-Constrained classification).
  - `test_manifest_checksum_generation` (SHA-256 hashing on CSV/Parquet).
  - `test_quarantine_error_isolation` (Isolates bad OHLCV rows).
  - `test_corporate_actions_backward_adjustment` (Splits/dividends adjustment parity).
  - `test_hypothesis_preregistration_validation` (Schema and parameter validation).
  - `test_absorbing_negative_result_transition` (Permanent terminal transition).
  - `test_fx_cost_model_minimum_fee` ($2.00 IBKR ticket minimum on micro-lots).
  - `test_factor_cost_model_short_borrow` (50 bps daily borrow accrual).
  - `test_quote_sided_fill_timing` (Evaluation on $t$, fill on $t+1$ ask/bid).
  - `test_default_deny_uncertified_rejection` (Rejects uncertified intent).
  - `test_risk_gate_hmac_signing` (Verifies SHA-256 token attachment and match).
  - `test_session_initialization_dual_approvers` (2-person nonce validation).

### Tier 2: Boundary & Corner Cases
- **Goal**: Verify system stability under edge conditions, malformed inputs, extreme values, and sudden faults.
- **Coverage**: $\ge 60$ test cases ($12 \times 5$).
- **Test Categories**:
  - Empty data files, single-row files, and zero-volume periods.
  - Price envelope violations (`low > high`, negative close, non-monotonic timestamps).
  - Large splits (100:1 reverse split, 1:100 forward split) and dividend larger than share price.
  - Expired Ed25519 certificates, forged signatures, and mismatched dataset hashes.
  - Feed health disconnect storms, stale watermarks (>2 days), and missing calendar sessions.
  - Zero/negative cash balance, maximum drawdown limit boundary, and max lot size clamping.
  - Kill-switch auto-trigger on corrupted state and refusal to auto-reset.

### Tier 3: Cross-Feature Combinations (Pairwise Interaction)
- **Goal**: Verify end-to-end data flow between interconnected subsystems.
- **Coverage**: $\ge 20$ pairwise combinatorial scenarios.
- **Scenarios**:
  - PIT Data Ingestion $\rightarrow$ Corporate Action Adjustment $\rightarrow$ Factor Simulator $\rightarrow$ Absorbing Negative Result Chronicle.
  - Pre-registered Hypothesis $\rightarrow$ Canonical FX Cost Simulation $\rightarrow$ Ed25519 Promotion Certificate $\rightarrow$ Default-Deny Execution Engine.
  - Streaming TWS Feed $\rightarrow$ Feed Health Evaluator $\rightarrow$ Deterministic Risk Gate $\rightarrow$ HMAC Risk Token $\rightarrow$ IBKR Bracket Order Adapter.
  - Halted System State $\rightarrow$ Dual-Human Release Authorization $\rightarrow$ Feed Health Verification $\rightarrow$ Active Trading State Recovery.

### Tier 4: Real-World Application Scenarios
- **Goal**: Holistic multi-asset trading day simulations and market stress events.
- **Coverage**: $\ge 8$ comprehensive end-to-end workloads.
- **Scenarios**:
  1. **Full Equities Quantile Factor Lifecycle**: Ingest 50-stock universe, adjust splits/dividends, generate SHA-256 manifest, run dollar-neutral 12-1M factor backtest with IBKR Pro fees and borrow, verify metrics and negative result recording.
  2. **Canonical Multi-Pair FX Simulation**: Ingest EURUSD/GBPUSD tick data, apply `FxCostModel` with $2.00 ticket minimums and `QUOTE_NEXT_EVENT` top-of-book fills, verify net PnL degradation against gross.
  3. **Crypto Perpetual Funding Carry Lifecycle**: Ingest 24/7 Binance VIP0 market structure data, simulate funding cashflows and taker fees, enforce default-deny broker boundary.
  4. **End-to-End Paper Trading Session Ingress**: Issue cryptographically signed `PromotionCertificate`, initialize session with dual approvers, stream live bars via TWS feed, evaluate 9-stage `RiskGate`, attach HMAC risk tokens, emit IBKR bracket orders, and persist events to `.titan_state.db`.
  5. **Emergency Circuit Breaker & Dual-Human Recovery**: Trigger portfolio drawdown breach, verify immediate transition to `TradingState::Halted`, attempt unauthorized reset (rejected), execute dual-human `ReleaseAuthorization` with fresh feed health, verify safe recovery to `TradingState::Active`.

---

## Acceptance Criteria
- Full test suite passes 100% with exit code 0.
- Zero integrity violations (no mocking of risk gates, no bypassed certificates, no hardcoded backtest returns).
- Forensic audit reports CLEAN.
