# TITAN Quantitative Research OS — Research Operating Constitution & Roadmap

> **Owner:** Chief Research Architect & Risk Owner  
> **Status:** Ratified — v1.0 Complete (Architecture Freeze & G2 Alpha Discovery Edition)  
> **Last Review:** 2026-07-30  

---

## Preamble

> *"TITAN exists to transform market hypotheses into reproducible evidence. Software is the instrument, not the objective. Every experiment—whether it confirms or rejects a hypothesis—expands the platform's understanding of financial markets. Capital is committed only after evidence survives statistical scrutiny, independent replication, governance review, and realistic execution validation. The success of TITAN will be measured not by the number of strategies it contains, but by the quality, durability, and reproducibility of the knowledge it produces."*

---

## 1. Generation 1 (G1) vs Generation 2 (G2)

* **G1 — Platform Construction (COMPLETED):**  
  Built a trustworthy machine for producing evidence (Data Contracts, Feature Store, Governance, Replication Engine, Portfolio Evaluator, Architecture Freeze).
* **G2 — Alpha Discovery Program (ACTIVE NOW):**  
  Discovers robust market edges. Deliverables are no longer software code; deliverables are **Validated Hypotheses, Replicated Evidence, Documented Rejections, and Portfolio Improvements**.

---

## 2. Definition of "Done"

A sprint or work cycle is successful **only** if it produces one of these outcomes:
1. **A replicated piece of evidence** (Dual-experiment 3D replication).
2. **A high-quality rejection** with documented reasons and archived evidence.
3. **A promotion to WATCHLIST or QUALIFIED** fully supported by constitutional requirements.

*Everything else is supporting work.*

---

## 3. Freeze Scope & Architecture Decision Record (ADR) Gate

### Explicitly Frozen Infrastructure
- Research infrastructure (`optimizers/`, `validators/`)
- Experiment framework (`experiment.py`, `harness.py`)
- Governance workflow (`evidence_bundle.py`, `gate.py`)
- Evidence bundle schema (`EXP-XXXXX_evidence_bundle.json`)
- This Research Operating Constitution

> **The ADR Requirement Gate:**  
> Any proposed modification to frozen infrastructure requires an accepted **Architecture Decision Record (ADR)** demonstrating an explicit, unresolvable bottleneck in the research process.

### Allowed Active Evolution (Research Outputs)
- New hypotheses & preregistrations
- New datasets & data contracts
- New economically motivated features
- Execution cost models (validated by TWS paper telemetry)
- Research journals & scorecards
- Portfolio construction & tail-risk research

---

## 4. Research Review Board

During G2, project reviews are **Research Review Boards**, not implementation milestone reviews. Every review answers five questions:

1. **What did we learn?** — Not: *What did we build?*
2. **Which hypotheses were disproven?** — Negative evidence is still progress.
3. **Which findings replicated?** — Replication is stronger evidence than a single large Sharpe ratio.
4. **Which ideas deserve more capital?** — Capital includes: engineering time, compute, market data, paper trading allocation.
5. **What changed our understanding of markets?** — This is the closing section of every review.

---

## 5. Evidence Quality Index (EQI)

EQI is published as **six independent dimensions**, not one aggregate score. This makes weaknesses immediately visible without hiding them behind an average.

| Dimension | Description | Example Score |
|---|---|---|
| **Reproducibility** | Code & data hash determinism; identical re-run produces identical output | 0.98 |
| **Replication** | 3D multi-dimensional validation pass (instrument, time period, regime) | 0.82 |
| **Statistical Robustness** | Multiple testing correction, confidence bounds, effect sizes | 0.91 |
| **Economic Plausibility** | Validated structural market mechanism driving the signal | 0.87 |
| **Execution Realism** | Spread, slippage, latency, and market-impact modeling | 0.76 |
| **Documentation** | Archived evidence bundle, journal entry, and governance record | 1.00 |

---

## 6. Research Journal

Every experiment must produce a standardized narrative **Research Journal** entry at `research/journal/EXP-XXXXX_journal.md`. All journals follow the same structure:

1. **Hypothesis** — The precise claim being tested.
2. **Economic Mechanism** — The structural market behavior that would make this signal exist.
3. **Prediction** — The measurable outcome expected if the hypothesis is correct.
4. **Methodology** — Instruments, timeframes, train/validation split, statistical tests.
5. **Result** — Quantitative findings: Sharpe, hit rate, drawdown, p-values, confidence intervals.
6. **Unexpected Observations** — Anything that contradicted prior assumptions or revealed new structure.
7. **What We Now Believe** — Updated understanding of the market behavior under study.
8. **Next Experiment** — What follow-up investigation is warranted (or why none is needed).
9. **Decision** — `PROMOTED` / `REFINED` / `REJECTED` with governance justification.

See template: [`research/journal/TEMPLATE.md`](../research/journal/TEMPLATE.md)

---

## 7. The Four Constitutional Principles

### Principle 1: Research Over Features
Every task must answer one question:  
> *"Will this increase our ability to discover or validate alpha?"*  
If the answer is no, it will not be prioritized.

### Principle 2: Knowledge is the Product
The primary deliverable is **Evidence**—every well-tested, rejected hypothesis adds permanent value to platform knowledge.

### Principle 3: Mandatory 3D Replication Before Promotion
A strategy will **never** be promoted to `QUALIFIED` based on a single experiment.  
Replication is required across **three distinct dimensions**:
1. **Instrument Replication:** Shared behavior across multiple asset classes/tickers.
2. **Time Period Replication:** Out-of-sample walk-forward stability across non-overlapping dates.
3. **Market Regime Replication:** Verified stability in high-volatility, low-volatility, bull, bear, and sideways regimes.

### Principle 4: Statistical Integrity
No claim of alpha may be accepted unless the supporting evidence demonstrates statistical robustness appropriate to the research question:
- **Multiple Testing Correction:** False Discovery Rate (FDR) / Bonferroni adjustments when evaluating parameter surfaces or feature spaces.
- **Predefined Criteria:** Preregistered acceptance and rejection thresholds before execution.
- **Confidence Intervals & Effect Sizes:** Reporting point estimates with uncertainty bounds and effect sizes.
- **Preservation of Negative Results:** Every failed experiment is permanently archived to prevent publication bias and redundant re-testing.

### Principle 5: Evidence-Driven Architecture Expansion
Every new architectural proposal must demonstrate that it removes a bottleneck observed during actual research execution, not a hypothetical future need. The architecture of the research OS is frozen; future progress comes from executing research, not from adding governance layers.

---

## 8. The Alpha Discovery Program Charter

### Canonical Research Questions
Durable scientific inquiries that spawn multiple hypotheses over time are registered in [`docs/CANONICAL_RESEARCH_QUESTIONS.md`](CANONICAL_RESEARCH_QUESTIONS.md).

### Research Lifecycle States

```text
Proposed ──► Prioritized ──► Implemented ──► Experimented ──► Evidence Produced ──► Replicated ──► Governance Review ──► WATCHLIST ──► Paper Validation ──► QUALIFIED
```

### Program Allocation (25–50 Hypotheses)
- **40% Market Microstructure:** Opening auction imbalances, order flow toxicity, bid-ask dynamics.
- **25% Regime-Dependent Behavior:** Volatility compression, regime shifts, tail-risk behavior.
- **20% Execution Research:** Slippage vs midpoint, fill quality, latency sensitivity.
- **15% Cross-Sectional & Sector Effects:** Intraday sector rotation leading index performance (`SPY`, `QQQ`).

### Expected Outcome Distribution
After the first 25–50 hypotheses, a healthy research program should produce an outcome distribution such as:

```text
Hypotheses Proposed:      50
Completed:                47
Rejected:                 36
Refined:                   8
Promoted:                  3
```

A low promotion rate with strict governance is a sign of strength, not failure. It indicates the platform is filtering aggressively rather than accumulating weak ideas.

### Alpha Discovery Program Success Criteria
At the end of the first batch, the review focuses on outcomes, not activity:
1. Which categories produced the strongest evidence?
2. Which hypotheses consistently failed?
3. Which failures revealed flaws in our assumptions?
4. Which ideas merit deeper investigation?
5. Which strategies improved the overall portfolio rather than only standalone metrics?

The goal is to improve the quality of future hypotheses, not simply to count promotions.

---

## 9. G2 Risk Register

Architecture is no longer the primary risk. The following four risks are continuously monitored during G2:

| Risk | Description | Mitigation |
|---|---|---|
| **Data Quality** | Missing data, corporate actions, survivorship bias, timestamp alignment, and execution data integrity can invalidate otherwise sound research. | Dataset contracts, hash-verified ingestion, gap detection, and explicit data-quality EQI dimension. |
| **Economic Validity** | Every hypothesis must have a plausible mechanism explaining why the edge might exist and why it could persist despite competition. | Mandatory economic rationale field, Principle 1 review, and Research Review Board Question 5. |
| **Execution Realism** | Paper-trading telemetry must continually test whether modeled costs, slippage, and latency remain representative of achievable execution. | TWS paper-trade reconciliation, execution EQI dimension, and 20% Execution Research allocation. |
| **Model Decay** | Even replicated findings can weaken over time. | Treat decay as a research signal, not simply a failure. Continuous monitoring of QUALIFIED strategies; degradation triggers re-evaluation through the governance lifecycle. |

---

## 10. Learning Efficiency

### What G2 Optimizes For

G2 does **not** optimize for:
- number of experiments,
- number of promoted strategies,
- number of hypotheses.

G2 optimizes for **learning efficiency**. The internal question after each research cycle is:

> *"Did this cycle improve our ability to ask better questions?"*

If the answer is yes — even after mostly rejected hypotheses — the program is progressing.

### Engineering-to-Research Ratio

**Operational guideline:** For every hour spent modifying the research platform, spend at least ten hours executing, analyzing, replicating, and documenting research. This reflects the reality that the platform's future value now depends far more on the quality of its evidence than on additional engineering.

### One-Year Expectations

After one year of disciplined execution, the Alpha Discovery Program should produce:
- A substantial library of rejected hypotheses with reusable evidence.
- A smaller set of replicated economic mechanisms.
- A handful of portfolio-worthy candidates.
- Improved hypothesis generation based on accumulated knowledge rather than intuition.
- A research process that becomes more efficient because each experiment informs the next.

---

## 11. The Defining Question

The transition from G1 to G2 represents a fundamental change in what TITAN is trying to answer:

> **G1:** *Can we build a trustworthy quantitative research operating system?*
>
> **G2:** *Can that operating system produce durable, reproducible, economically grounded knowledge about financial markets?*

The next 6–12 months will answer the second question. If the research process remains as disciplined as the architecture, that answer will be determined by evidence rather than optimism — which is exactly what the platform was designed to achieve.

### When Does Generation 3 Begin?

G3 is **not** defined by elapsed time. G3 begins only when TITAN reaches a qualitative change in capability — specifically, when the platform can consistently generate and validate new hypotheses faster or more effectively *because of the knowledge accumulated during G2*, not because of additional framework engineering. Until that threshold is crossed, G2 remains the appropriate focus.

---

## Architectural Record

> *Project TITAN Generation 1 is complete. The platform has established a stable constitutional framework for quantitative research, including governance, statistical standards, replication policy, portfolio evaluation, and institutional knowledge management. Future progress is expected to come primarily from the discovery and validation of economically grounded hypotheses rather than additional infrastructure. Generation 2 begins with the Alpha Discovery Program, where success will be determined by the quality, reproducibility, and portfolio relevance of the evidence produced.*
>
> *From this point on, architecture reviews should become infrequent. The primary artifacts worth reviewing are experiment designs, evidence bundles, replication results, research journals, and annual retrospectives. If the constitution is doing its job, those artifacts — not the codebase — will become the principal record of TITAN's progress.*
>
> — ADR-001, 2026-07-30
