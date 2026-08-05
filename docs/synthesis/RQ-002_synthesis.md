# RQ-002 Research Synthesis Report — Volatility Compression & Directional Expansion

> **Canonical Research Question:** RQ-002  
> **Status:** Active Research Program (Refinement Phase)  
> **Owner:** TITAN Research OS  
> **Mechanism Registry References:** `M-004`, `M-005`  
> **Last Updated:** 2026-07-30  

---

## 1. Research Question Maturity (RQM) Scorecard

| Dimension | Metric / Status |
|---|---|
| **Experiments Completed** | 1 (EXP-00011) |
| **Independent Replications** | 1 (SPY + EURUSD Multi-Asset Verification in EXP-00011) |
| **Retired Mechanisms** | 1 (`M-004`: Unconditional ATR Compression Expansion — EXP-00011) |
| **Active Mechanisms** | 1 (`M-005`: Volume-Catalyzed Compression Expansion — Planned EXP-00012) |
| **Mechanism Confidence** | 🔴 **Low** (Unconditional ATR compression is equilibrium drift, not expansion) |
| **Evidence Stability** | 🟢 **High** (396 events across SPY & EURUSD confirm naive ATR failure) |
| **Portfolio Relevance** | Unknown |

---

## 2. Mechanism Evidence Index (MEI) Summary

| Mechanism ID | Mechanism Name | Status | MEI Score | Supporting / Contradicting Evidence |
|---|---|---|---|---|
| **`M-004`** | Unconditional ATR Compression Expansion | 🔴 Retired | **0.05** | EXP-00011 (SPY 27.1% OOS / EURUSD 7.8% OOS across 396 events) |
| **`M-005`** | Volume-Catalyzed Compression Expansion | 🟡 Planned | **0.50** | Theoretical microstructure model (EXP-00012 planned) |

---

## 3. Executive Summary & Progression

```text
EXP-00011 (M-004 Naive ATR Compression) ──► REJECTED (27.1% SPY / 7.8% EURUSD OOS Success)
   │
   ├── Key Finding: ATR compression alone produces muted drift (0.64x–1.13x ATR), not explosive expansion.
   ▼
EXP-00012 (M-005 Volume Shock Catalyst)  ──► PLANNED
```

---

## 4. What We Now Know (Established Empirical Facts)

1. **ATR Compression Alone (`M-004`) is Non-Predictive:** Low volatility (ATR in bottom 25th percentile) is an equilibrium state, not a spring-loaded expansion guarantee. High Evidence Stability (396 events).
2. **Expansion Magnitude is Muted:** Breakouts from naive ATR compression yield only 0.64x to 1.13x ATR expansion, failing the 2.0x target threshold across both equities and forex.

---

## 5. Artifact References

- Mechanism Registry: [`docs/MECHANISM_REGISTRY.md`](../MECHANISM_REGISTRY.md)
- EXP-00011 Journal: [`research/journal/EXP-00011_journal.md`](../../research/journal/EXP-00011_journal.md)
- EXP-00011 Evidence Bundle: [`research/experiments/EXP-00011_evidence_bundle.json`](../../research/experiments/EXP-00011_evidence_bundle.json)
