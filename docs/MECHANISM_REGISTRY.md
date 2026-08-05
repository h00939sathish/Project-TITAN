# TITAN Mechanism Registry

> **Status:** Ratified — v3.0 Final (Framework Freeze Edition)  
> **Owner:** TITAN Research OS  
> **Last Updated:** 2026-07-30  

---

## Overview
The **Mechanism Registry** tracks economic mechanisms underlying market behavior independently of individual experiments or trading rules. Experiments accumulate evidence to update the **Mechanism Evidence Index (MEI)** for each structural mechanism based on objective, decomposed evidence criteria.

---

## 1. MEI Transition Thresholds & Milestone Criteria

Status transitions are governed deterministically by the composite **Mechanism Evidence Index (MEI)** score:

| MEI Range | Status | Governance & Operational Lifecycle Action |
|---|---|---|
| **`0.00 – 0.25`** | 🔴 **Retired** | Disproven; terminal negative state; no further research capital |
| **`0.26 – 0.50`** | ⚪ **Planned / Exploratory** | Theoretical or un-tested model; initial experiment design |
| **`0.51 – 0.75`** | 🟡 **Active** | Supported by exploratory evidence; active experimentation |
| **`0.76 – 0.90`** | 🟢 **Strong Evidence** | Replicated cross-asset empirical regularity; monitoring mode |
| **`0.91 – 1.00`** | 💎 **Established Mechanism** | Proven causal mechanism; terminal positive state; portfolio deployment |

> ### 💎 Milestone Gate: First Established Mechanism (MEI ≥ 0.91)
> To cross from `Strong Evidence` to `Established Mechanism`, a mechanism must satisfy all 6 conditions (necessary, reviewed by Governance Board):
> 1. Multi-asset independent replication (minimum 2 asset classes).
> 2. Walk-forward stability across non-overlapping market regimes (Bull, Bear, Volatile, Sideways).
> 3. Disambiguation from competing candidate causal mechanisms via explicit hypothesis testing.
> 4. All preregistered predictions confirmed across independent datasets.
> 5. Contradictory & Uncertainty Register actively investigated with no unaddressed invalidations.
> 6. Demonstrated practical utility in a downstream capability (e.g. execution timing, tail risk, or alpha generation).

---

## 2. Semantic Versioning Conventions

- **Major (`v2.0`):** Fundamental change to the core economic mechanism or causal model.
- **Minor (`v1.1`):** Refined predictions, scope, or parameter bounds with the same core mechanism.
- **Patch (`v1.0.1`):** Documentation, metadata, or scoring corrections only.

---

## 3. Decomposed MEI & Revalidation Status

$$\text{MEI} = 0.30 \cdot \text{Replication} + 0.25 \cdot \text{StatSupport} + 0.20 \cdot \text{Stability} + 0.15 \cdot \text{Plausibility} + 0.10 \cdot \text{Generalization}$$

**Revalidation Status:**
- `1.00`: Verified within last 90 days (Current)
- `0.75`: Verified within last 180 days (Active)
- `0.50`: Verified within last 365 days (Triggers revalidation flag)

---

## 4. Registered Economic Mechanisms

### `M-001` (v1.0): Institutional Flow Persistence
* **Canonical RQ:** `RQ-001` (Opening Auction Imbalance Dynamics)
* **Status:** 🔴 **Retired** (MEI = 0.10, Revalidation = 1.00)
* **Scientific Lineage:** Root mechanism under `RQ-001`. Disproven in `EXP-00008` $\longrightarrow$ Seeded `M-002`.
* **Observed Phenomenon:** Intraday price drift following opening range.
* **Candidate Causal Mechanism:** MOO order flow persistence. (Disproven)
* **Decomposed MEI Breakdown:**
  * Replication (30%): `0.00` | StatSupport (25%): `0.10` | Stability (20%): `0.10` | Plausibility (15%): `0.30` | Generalization (10%): `0.10`
* **Prediction Record:**
  * ✗ Opening direction predicts session drift (Disproven in EXP-00008)
  * ✗ High-volume opens amplify continuation (Disproven in EXP-00008)

---

### `M-002` (v1.1): Opening Liquidity Exhaustion
* **Canonical RQ:** `RQ-001` (Opening Auction Imbalance Dynamics)
* **Status:** 🟡 **Active** (MEI = 0.65, Revalidation = 1.00)
* **Scientific Lineage:** Evolved from `M-001` rejection in `EXP-00008` $\longrightarrow$ Tested in `EXP-00009` $\longrightarrow$ Refined into `M-003`.
* **Observed Phenomenon:** Large opening ranges reverse more frequently than small opening ranges.
* **Candidate Causal Mechanism:** Aggressive MOO flow consumes opening liquidity; contrarian flow mean-reverts price once execution completes.
* **Decomposed MEI Breakdown:**
  * Replication (30%): `0.60` | StatSupport (25%): `0.60` | Stability (20%): `0.70` | Plausibility (15%): `0.85` | Generalization (10%): `0.50`
* **Prediction Record:**
  * ✓ Top-quartile opening ranges reverse more frequently than bottom-quartile (Confirmed in EXP-00009)
  * ✗ Opening range magnitude correlates with reversal magnitude (Failed Bonferroni α in EXP-00009)
  * □ High-volume + large-range opens show highest reversal rate (Pending 100+ session data)

---

### `M-003` (v1.0): Structural Excursion Asymmetry (MAE > MFE)
* **Canonical RQ:** `RQ-001` $\longrightarrow$ **Feeds `RQ-003`** (Execution Microstructure) & **`RQ-005`** (Regimes)
* **Status:** 🟢 **Strong Evidence** (MEI = 0.85, Revalidation = 1.00)
* **Scientific Lineage:** Unconditional structural refinement from `M-002` in `EXP-00010`.
* **Observed Phenomenon (Confirmed):** Intraday price travels significantly further against the opening direction (MAE) than it extends with it (MFE) across equities and forex.

#### Competing Candidate Causal Mechanisms Comparison

| Candidate Causal Model | Supporting Evidence | Contradicting Evidence | Confidence Level | Current Status |
|---|---|---|---|---|
| **1. Market Maker Inventory Rebalancing** | Moderate (EXP-00010 73.3% morning concentration) | Limited | Medium-High | **Primary Lead** |
| **2. Liquidity Replenishment & Book Rebuilding** | Moderate (MAE > MFE across SPY & EURUSD) | Unknown | Medium | Active Alternative |
| **3. Institutional VWAP Completion** | Weak (Needs intraday volume profile analysis) | Unknown | Low | Secondary |
| **4. Intraday Risk Transfer & Hedging Friction** | Preliminary | Unknown | Low | Secondary |

#### Mechanism Validation Matrix (`M-003`)

| Preregistered Prediction | SPY | EURUSD | Futures | Bull | Bear | High Vol | Low Vol |
|---|---|---|---|---|---|---|---|
| **MAE > MFE Ratio > 1.0** | ✅ (1.45x) | ✅ (5.25x) | □ | □ | □ | □ | □ |
| **Morning Concentration (> 70%)** | ✅ (73.3%) | ✅ (100%) | □ | □ | □ | □ | □ |
| **Execution Alpha via Limit Timing** | □ | □ | □ | □ | □ | □ | □ |

---

### `M-004` (v1.0): Unconditional Volatility Compression Expansion
* **Canonical RQ:** `RQ-002` (Volatility Compression & Directional Expansion)
* **Status:** 🔴 **Retired** (MEI = 0.05, Revalidation = 1.00)
* **Scientific Lineage:** Root mechanism under `RQ-002`. Disproven in `EXP-00011` $\longrightarrow$ Seeded `M-005`.
* **Observed Phenomenon:** Volatility compression.
* **Candidate Causal Mechanism:** Stored elastic energy in thin orderbook. (Disproven)
* **Prediction Record:**
  * ✗ ATR compression in bottom 25th percentile precedes > 2.0x ATR expansion (Disproven in EXP-00011 across 396 events)

---

### `M-005` (v1.0): Volume-Catalyzed Compression Expansion
* **Canonical RQ:** `RQ-002` (Volatility Compression & Directional Expansion)
* **Status:** ⚪ **Planned / Exploratory** (MEI = 0.50, Revalidation = 1.00)
* **Scientific Lineage:** Evolution from `M-004` rejection in `EXP-00011`.
* **Observed Phenomenon:** Volatility compression followed by volume shock.
* **Candidate Causal Mechanism:** Volume shock sweeps thin orderbook following inventory accumulation.
* **Prediction Record:**
  * □ Volume shock catalyst converts muted compression into clean > 2.0x ATR expansion (Pending EXP-00012)

---

## 5. Next Program Target: Research Corpus 1.0

The Knowledge Architecture framework is **FROZEN**. All future engineering capacity is dedicated strictly to executing experiments toward **Research Corpus 1.0**:
- **Target:** 25–30 completed experiments across `RQ-001` through `RQ-005`.
- **Target:** 5–8 mature mechanisms registered.
- **Target:** At least 1 mechanism evaluated at the `Established Mechanism` Milestone Gate.
