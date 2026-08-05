# PROJECT TITAN — INSTITUTIONAL FOREX RISK MANAGEMENT FRAMEWORK

> **Owner:** Chief Risk Officer & Risk Architecture Council  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Deterministic Risk Engine (Rust Core)  
> **Governance Enforcement:** [RISK_POLICY.md](file:///d:/projects/Project%20TITAN/RISK_POLICY.md) — Zero Unsigned Order Submissions

---

## 1. Multi-Tier Risk Architecture

Project TITAN enforces a multi-layered risk model designed to prevent capital depletion, kill-switch resets, position drift, and catastrophic drawdown.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROJECT TITAN RUST CORE RISK GATE                        │
└─────────────────────────────────────────────────────────────────────────────┘
  Layer 1: Hard Capital & Position Limits
    ├── Max Single-Trade Risk Limit: 1.0% of Total Portfolio Equity
    ├── Max Portfolio Gross Leverage: 3.0x Net Asset Value (NAV)
    └── Max Asset Class Concentration: 30% per currency pair (e.g. EURUSD)

  Layer 2: Tail-Risk & Dynamic Sizing Engine
    ├── Volatility-Adjusted Kelly Sizing (Half-Kelly Fraction f* = 0.5)
    ├── Extreme Value Theory (EVT) VaR (99% 1-Day Confidence)
    └── Conditional Value-at-Risk (CVaR / Expected Shortfall)

  Layer 3: Hardware Kill Switch & State Machine
    ├── Daily Drawdown Hard Stop: 2.0% Daily Loss → Auto-Trigger Kill Switch
    ├── Max Peak-to-Trough Drawdown: 6.0% Total Loss → System Halt
    └── Non-Resettable Circuit Breaker: Manual Human Approval Required for Reset
```

---

## 2. Quantitative Position Sizing & Portfolio Optimization

### 2.1 Volatility-Adjusted Fractional Kelly Sizing
The optimal allocation fraction $f^*$ for a currency strategy is determined via the Kelly Criterion, scaled by a conservative fractional multiplier ($\gamma = 0.5$ Half-Kelly) to prevent over-betting under parameter estimation error:

\[
f^* = \gamma \cdot \frac{\mu - r}{\sigma^2}
\]

Where:
- $\mu$ is the expected strategy return.
- $r$ is the risk-free rate.
- $\sigma^2$ is the variance of strategy returns.

### 2.2 Extreme Value Theory (EVT) VaR & CVaR
Standard normal Value-at-Risk (VaR) severely underestimates fat-tailed FX crash risk. TITAN models extreme tail returns using the Generalized Pareto Distribution (GPD):

\[
F_\xi(x) = 1 - \left( 1 + \frac{\xi x}{\beta} \right)^{-1/\xi}
\]

- **CVaR (Expected Shortfall):** Represents the expected loss given that the loss exceeds the $99\%$ VaR threshold:
  \[
  \text{CVaR}_{\alpha} = \mathbb{E}[L \mid L \ge \text{VaR}_{\alpha}]
  \]
- **Enforcement:** If portfolio 1-day CVaR exceeds **3.5% of NAV**, the Rust risk gate automatically scales down new order quantities by $50\%$.

---

## 3. Micro-Lot Forex Sizing & Multi-Currency Account Realities

### 3.1 Standard Sizing Units
- **Base Unit Sizing:** In TITAN, 1 lot = 1 micro-lot = 1,000 base currency units.
- **Notional Conversion:**
  - `EURUSD BUY 1000`: €1,000 notional $\approx \$1,090$ USD buying power required.
  - `GBPUSD BUY 1000`: £1,000 notional $\approx \$1,280$ USD buying power required.

### 3.2 Account Buying Power Safeguards (Error 201 Prevention)
In an INR-denominated or USD-negative account:
- `BUY` orders require available positive USD buying power. If buying power is insufficient, IBKR TWS returns **Error 201**.
- TITAN's risk engine catches Error 201, logs a clean `OrderState::Rejected` transition, updates the rejection counter, and preserves **zero position drift** (`drift = 0`).
- Short sales (`SELL` orders) generate USD cash proceeds upon fill, enabling USD cash accumulation to fund subsequent long positions.

---

## 4. Hardware Kill Switch & Fail-Closed Safeguards

```
              ┌──────────────────────────────────────────────┐
              │           TRADING STATE: ACTIVE              │
              └──────────────────────┬───────────────────────┘
                                     │
           Trigger Event:            │
           - Daily Loss > 2.0%       │
           - Reconcile Drift > 0.01  │
           - TWS Disconnect > 10s    │
                                     ▼
              ┌──────────────────────────────────────────────┐
              │          TRADING STATE: HALTED               │
              │         (Kill Switch Triggered)              │
              └──────────────────────┬───────────────────────┘
                                     │
                                     │ Manual Human Verification
                                     │ & Reconcile Gate Clearance
                                     ▼
              ┌──────────────────────────────────────────────┐
              │          TRADING STATE: RELEASED             │
              └──────────────────────────────────────────────┘
```

1. **Deterministic Enforcement:** Implemented in Rust core (`core/src/risk.rs`). Cannot be bypassed by Python or AI advisory layers.
2. **Auto-Reset Prohibition:** Once triggered, the kill switch **MUST NEVER auto-reset**. Re-activation requires an explicit human operator command following full reconciliation.

---

## 5. References & Risk Policy Directives

1. **McNeil, A. J., Frey, R., & Embrechts, P. (2015).** *Quantitative Risk Management: Concepts, Techniques and Tools.* Princeton University Press.
2. **Lopez de Prado, M. (2018).** *Advances in Financial Machine Learning.* John Wiley & Sons.
3. **Project TITAN Risk Policy.** [RISK_POLICY.md](file:///d:/projects/Project%20TITAN/RISK_POLICY.md).
4. **Rust Core Risk Implementation.** [core/src/risk.rs](file:///d:/projects/Project%20TITAN/core/src/risk.rs).
