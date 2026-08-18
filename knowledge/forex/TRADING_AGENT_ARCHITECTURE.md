# PROJECT TITAN — TRADING AGENT ARCHITECTURE & ADVISORY BOUNDARIES

> **Owner:** Autonomous Systems Lead & Risk Authority Council  
> **Status:** Active — Institutional Knowledge Base v1.1  
> **Last Review:** 2026-08-18  
> **Target System:** Project TITAN Agent Harness & Advisory Layer  
> **Governance Enforcement:** [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md) — Mandatory Deterministic Execution Boundaries

---

## 1. System Boundary Architecture & AI Authority Matrix

Project TITAN enforces strict isolation between probabilistic AI advisory agents and deterministic risk/execution engines.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PROBABILISTIC / ADVISORY AGENT LAYER                   │
│                                                                             │
│   ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────────┐ │
│   │ Hypothesis Agent    │  │ Feature Discovery   │  │ Reflection Agent   │ │
│   │ (LLM / Research)    │  │ (ML / TFT / XGB)    │  │ (Post-Trade Analysis)│
│   └──────────┬──────────┘  └──────────┬──────────┘  └─────────┬──────────┘ │
└──────────────┼────────────────────────┼───────────────────────┼─────────────┘
               │ Proposed Parameters    │ Feature Weights       │ Insights
               ▼                        ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 DETERMINISTIC VALIDATION & PROMOTION GATE                   │
│   Canonical Simulator (Fx/Crypto/Factor Cost Models) & `PromotionGate`      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ PromotionCertificate (digest + certificate_ref)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 DETERMINISTIC EXECUTION & RISK ENGINE (Rust / PyO3)          │
│                                                                             │
│   ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────────┐ │
│   │ Rust Risk Gate      │  │ Portfolio Engine    │  │ Reconciliation     │ │
│   │ (certificate_ref)   │  │ (Position / Cash)   │  │ (Broker vs Local)  │ │
│   └──────────┬──────────┘  └──────────┬──────────┘  └─────────┬──────────┘ │
└──────────────┼────────────────────────┼───────────────────────┼─────────────┘
               │ Signed Approved Order  │ Cash / Buying Power   │ Audit Logs
               ▼                        ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BROKER ADAPTER & ORDER ROUTING (IBKR / TWS)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 AI Authority Matrix (Constitutionally Enforced)

| Function | AI / LLM Allowed | Deterministic Engine Required | Governance Rule |
| :--- | :--- | :--- | :--- |
| **Strategy Hypothesis Drafting** | ✅ YES | ❌ NO | Advisory research workflow only |
| **Parameter Feature Discovery** | ✅ YES | ❌ NO | Requires backtest qualification gate |
| **Post-Trade Reflection** | ✅ YES | ❌ NO | Logs post-trade insights; cannot alter active state |
| **Promotion Certificate Issuance** | ❌ NO | ✅ YES | **FORBIDDEN:** Only deterministic `PromotionGate` issues certificates |
| **Order Placement & Routing** | ❌ NO | ✅ YES | **FORBIDDEN:** AI must NEVER place or route orders |
| **Risk Limit Enforcement** | ❌ NO | ✅ YES | **FORBIDDEN:** Hard risk limits enforced strictly in Rust |
| **Kill Switch Control** | ❌ NO | ✅ YES | Auto-halts on anomaly; auto-reset is strictly forbidden |
| **Broker Account Credentials** | ❌ NO | ✅ YES | Secrets isolated in secure env / OS keychains |

---

## 2. Taxonomy of Trading Agent Designs

### 2.1 Rule-Based Deterministic Agents
- **Characteristics:** Static conditional logic (`if SMA_50 > SMA_200: BUY`).
- **Strengths:** 100% predictable, zero inference latency, fully verifiable.
- **Weaknesses:** Rigid, incapable of adapting to regime shifts.

### 2.2 Statistical & Quantitative Agents
- **Characteristics:** Cointegration filters, Kalman filter dynamic hedge ratios, GARCH volatility forecasting.
- **Strengths:** Mathematically grounded, handles noisy time series effectively.
- **Weaknesses:** Sensitive to structural breaks in macro regimes.

### 2.3 Machine Learning (ML) & Reinforcement Learning (RL) Agents
- **Characteristics:** Temporal Fusion Transformers (TFT), XGBoost, Proximal Policy Optimization (PPO).
- **Strengths:** High capacity for complex pattern extraction in multi-asset feature spaces.
- **Weaknesses:** Overfitting risk, opacity (black-box), non-stationary regime degradation.

### 2.4 LLM-Assisted & Multi-Agent Advisory Systems
- **Characteristics:** Multi-agent collaboration (Research Agent, Code Reviewer, Risk Auditor).
- **TITAN Rule:** Used exclusively for **offline research loops** (`OPERATING_PRINCIPLES.md`). Output artifacts must pass the 6-step Implementation Gate before code merge.

---

## 3. The 6-Step Implementation Gate for Agent Promotion

No strategy candidate or agent logic may enter live paper or production execution unless all six conditions are satisfied:

1. **Specification Exists:** Accepted `.spec.md` defining boundary, state transitions, and metrics.
2. **ADR Accepted:** Architecture Decision Record ratified per `docs/adr/`.
3. **Tests Written:** Unit, contract, and integration tests covering every state transition and failure mode.
4. **Verification Defined:** Quantitative acceptance criteria recorded in task definition.
5. **Rollback Defined:** Documented zero-data-loss rollback procedure.
6. **Monitoring Defined:** Prometheus/OpenTelemetry metrics and alerts configured.

---

## 4. References & Agent Architecture Directives

1. **Project TITAN Agent Constitution.** [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md).
2. **Operating Principles & Research Loops.** [OPERATING_PRINCIPLES.md](file:///d:/projects/Project%20TITAN/OPERATING_PRINCIPLES.md).
3. **Execution Integrity & Sizing.** [ADR-028](file:///d:/projects/Project%20TITAN/docs/adr/ADR-028-execution-integrity-and-sizing.md).
4. **Canonical FX Simulation Evidence.** [ADR-031](file:///d:/projects/Project%20TITAN/docs/adr/ADR-031-canonical-fx-simulation-evidence.md).
5. **Rust Core Risk Gate.** [core/src/risk.rs](file:///d:/projects/Project%20TITAN/core/src/risk.rs).
6. **Trade Intent Specification.** [specifications/TradeIntent.spec.md](file:///d:/projects/Project%20TITAN/specifications/TradeIntent.spec.md).

