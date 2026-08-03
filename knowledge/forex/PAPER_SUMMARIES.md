# PROJECT TITAN — INDIVIDUAL PAPER SUMMARIES & TITAN MAPPING

> **Owner:** Academic Research Analyst & Quantitative Strategy Team  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Research Corpus  
> **Structure:** Paper Citation ➔ Key Findings ➔ Methodology ➔ Limitations ➔ TITAN Code Implementation Mapping

---

## 1. Summary Matrix of Primary Papers

### Paper 1: Time Series Momentum (Moskowitz, Ooi, Pedersen, 2012)
- **Citation:** Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). Time series momentum. *Journal of Financial Economics*, 104(2), 228-250.
- **Key Findings:** 
  1. Strong positive autocorrelation in returns over 1 to 12-month lookbacks.
  2. Returns revert over longer 3 to 5-year horizons.
  3. Provides "crisis alpha" (positive returns during tail market crashes).
- **Methodology:** Portfolio returns constructed by going long assets with positive 12-month trailing return and short assets with negative 12-month return, scaled by ex-ante volatility.
- **Limitations:** Suffers whipsaws during choppy, sideways range-bound market regimes.
- **TITAN Implementation Mapping:**
  - **Module:** [paper_session.py](file:///d:/projects/Project%20TITAN/scripts/paper_session.py#L580-L588)
  - **Active Strategy ID:** `ma-crossover` (configured in `session_config.json`)
  - **Indicator:** `ma-crossover` with daily / 5-min intraday bar feeds.

---

### Paper 2: Carry Trades and Global FX Volatility (Menkhoff et al., 2012)
- **Citation:** Menkhoff, L., Sarno, L., Schmeling, M., & Schrimpf, A. (2012). Carry trades and global foreign exchange volatility. *Journal of Finance*, 67(2), 681-718.
- **Key Findings:**
  1. High-interest-rate currencies deliver high average returns because they carry high risk of losses during global market distress.
  2. Global FX volatility risk ($\text{VXY}$) explains the cross-section of carry trade returns.
- **Methodology:** Sorted 48 currencies into 5 portfolios based on forward discount; regressed excess returns against global FX volatility innovation factor.
- **Limitations:** Requires reliable real-time volatility index data and central bank rate-differential feeds.
- **TITAN Implementation Mapping:**
  - **Module:** [forex_pairs.py](file:///d:/projects/Project%20TITAN/src/titan/data/forex_pairs.py)
  - **Status:** ⏳ Design Intent / Backlog (`RQ-FX-001` — requires yield-differential data feed ingestion).

---

### Paper 3: Flow Toxicity and Liquidity in a High-Frequency World (Easley et al., 2012)
- **Citation:** Easley, D., Lopez de Prado, M. M., & O'Hara, M. (2012). Flow toxicity and liquidity in a high-frequency world. *The Review of Financial Studies*, 25(5), 1457-1493.
- **Key Findings:**
  1. Introduces VPIN (Volume-Synchronized Probability of Toxicity) to measure adverse selection in high-frequency order flow.
  2. Spikes in VPIN precede market flash crashes and extreme liquidity drops.
- **Methodology:** Calculates volume-based imbalance buckets over trade data.
- **Limitations:** Requires clean tick-by-tick order volume data.
- **TITAN Implementation Mapping:**
  - **Module:** [MARKET_MICROSTRUCTURE.md](file:///d:/projects/Project%20TITAN/knowledge/forex/MARKET_MICROSTRUCTURE.md#L22)
  - **Status:** ⏳ Specification Phase (`RQ-FX-003`).

---

### Paper 4: Optimal Execution of Portfolio Transactions (Almgren & Chriss, 2000)
- **Citation:** Almgren, R., & Chriss, N. (2000). Optimal execution of portfolio transactions. *Journal of Risk*, 3, 5-40.
- **Key Findings:**
  1. Solves the optimal execution trajectory balancing market impact against volatility risk.
  2. Proves that optimal execution without alpha signals is a deterministic linear TWAP trajectory.
- **Methodology:** Mean-variance optimization on trade trajectories using permanent and temporary market impact parameters.
- **Limitations:** Assumes static volatility and constant market depth.
- **TITAN Implementation Mapping:**
  - **Module:** [twap.py](file:///d:/projects/Project%20TITAN/src/titan/execution/twap.py)
  - **Execution Slicer:** `TWAPExecutor` automatically splits orders $> 50$ micro-lots.
  - **Status:** ✅ Active in Code.

---

## 2. Summary Table of Implementation Links

| Paper Short Name | Primary Contribution | TITAN Subsystem Target | Validation Status |
| :--- | :--- | :--- | :--- |
| **Moskowitz et al. (2012)** | Time-Series Momentum | `paper_session.py` (`ma-crossover`) | ✅ Active in Paper Trading |
| **Menkhoff et al. (2012)** | Volatility-Filtered Carry | `forex_pairs.py` (`FX-CARRY-VOL`) | ⏳ Design Intent / Backlog (`RQ-FX-001`) |
| **Easley et al. (2012)** | VPIN Order Flow Toxicity | `MARKET_MICROSTRUCTURE.md` | ⏳ Specification Phase (`RQ-FX-003`) |
| **Almgren & Chriss (2000)** | Optimal TWAP Execution | `twap.py` (`TWAPExecutor`) | ✅ Active in Code |
| **Lopez de Prado (2018)** | Purged Cross-Validation | `qualification.py` (`QualificationEngine`) | ✅ Active in Code |

