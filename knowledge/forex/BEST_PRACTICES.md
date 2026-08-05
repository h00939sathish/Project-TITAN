# PROJECT TITAN — QUANTITATIVE FOREX RESEARCH & TRADING BEST PRACTICES

> **Owner:** Head of Systematic Trading & Quality Assurance Lead  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Quantitative Research & Production Operations  
> **Core Mandate:** Mandatory reproducible research, deterministic execution, exhaustive logging.

---

## 1. Quantitative Research Best Practices

1. **Zero Look-Ahead & Point-in-Time Data:** All historical features, macroeconomic releases, and indicator values MUST be strictly aligned to point-in-time availability ($t$). Never use data published at $t+1$ to make decisions at $t$.
2. **Multiple Testing Correction:** When screening hundreds of parameter combinations or features, apply **White's Reality Check (WRC)** or **Deflated Sharpe Ratio (DSR)** to eliminate false discovery bias:
   \[
   \text{DSR} = \text{PSR} \left( \sqrt{V} \left( \gamma_3 \frac{\text{SR}}{2} - \gamma_4 \frac{\text{SR}^2}{4} \right) \right)
   \]
3. **Out-of-Sample Walk-Forward Validation:** Test strategies across expanding or sliding walk-forward windows ($70\%$ in-sample optimization, $30\%$ out-of-sample holdout test).

---

## 2. Production Trading & Execution Best Practices

1. **Hardware Kill Switch Integrity:** The Rust core kill switch MUST remain wired directly into the order routing path (`submit_intent`). Auto-resets are strictly prohibited.
2. **Reconciliation & State Synchronization:** Perform periodic position and cash balance reconciliation against broker truth every 60 seconds (`engine.reconcile()`). If position drift occurs ($\text{drift} > 0$), trip the kill switch immediately.
3. **HMAC Risk Tokens:** Every approved order intent MUST carry an HMAC-SHA256 risk token signed with `TITAN_RISK_SECRET_KEY`. Unsigned or invalid orders are rejected fail-closed.
4. **Order Slicing for Large Quantities:** Orders exceeding $50$ micro-lots MUST be split via `TWAPExecutor` to avoid temporary market impact and broker rate limit rejections.

---

## 3. Structural Anti-Patterns (What TITAN Explicitly Rejects)

❌ **Grid / Martingale Sizing:** Never double down on losing positions. Position sizing must decrease during drawdowns, not increase.  
❌ **Un-Sliced Market Orders:** Never send massive market orders directly to the ECN without checking book depth and applying TWAP/VWAP slicing.  
❌ **Silent Exception Swallowing:** Never mask broker network timeouts or rejection errors with silent try/except blocks. Fail-closed and trip the kill switch.  
❌ **AI-Controlled Order Execution:** Never allow LLM or probabilistic models to submit orders directly to a broker. All AI components must remain strictly advisory.

---

## 4. References & Operational Standards

1. **Project TITAN Operating Principles.** [OPERATING_PRINCIPLES.md](file:///d:/projects/Project%20TITAN/OPERATING_PRINCIPLES.md).
2. **Project TITAN Agent Constitution.** [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md).
3. **Project TITAN Risk Policy.** [RISK_POLICY.md](file:///d:/projects/Project%20TITAN/RISK_POLICY.md).
