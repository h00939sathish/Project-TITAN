# PROJECT TITAN — FOREX MARKET MICROSTRUCTURE & PRICE DISCOVERY

> **Owner:** Microstructure Research Group & Execution Architecture Council  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN High-Frequency Signal Engine & Order Routing Core  
> **Evidence Priority:** Tier 1 Academic (Journal of Finance, JFE, Econometrica) & Tier 2 Microstructure Evidence (EBS, Refinitiv, LMAX)

---

## 1. High-Frequency Quote Formation & Order Book Dynamics

In electronic FX markets (ECNs like EBS, Refinitiv Matching, and LMAX), price discovery is driven by continuous limit order book (LOB) interactions between market makers, market takers, and algorithmic execution algorithms.

```
                  LIMIT ORDER BOOK (LOB) ARCHITECTURE
                  
        ASK / OFFER SIDE (Sellers)
        Level 3:  1.08530  │  5,000,000 EUR  │  Non-Bank MM B
        Level 2:  1.08525  │  2,500,000 EUR  │  Tier-1 Bank A
        Level 1:  1.08520  │  1,000,000 EUR  │  EBS Top of Book (BEST ASK)
        ───────────────────────────────────────────────────────────── SPREAD = 0.00005 (0.5 pips)
        Level 1:  1.08515  │  1,500,000 EUR  │  LMAX Top of Book (BEST BID)
        Level 2:  1.08510  │  3,000,000 EUR  │  Non-Bank MM A
        Level 3:  1.08505  │  7,000,000 EUR  │  Tier-1 Bank C
        BID SIDE (Buyers)
```

### 1.1 Order Flow Information Content & Hasbrouck Decomposition
Per Hasbrouck (1991), price movements are decomposed into a permanent structural component (driven by unobserved fundamental information contained in order flow) and a transient noise component (driven by inventory control and microstructure friction):

\[
p_t = m_t + s_t
\]
\[
m_t = m_{t-1} + w_t, \quad w_t = \lambda \cdot y_t + \epsilon_t
\]

Where:
- $m_t$ is the fundamental efficient price (random walk).
- $s_t$ is the transient microstructure noise (bid-ask bounce).
- $y_t$ is the net order flow imbalance (signed volume).
- $\lambda$ is **Kyle's Lambda** measuring market impact per unit of net order flow.

---

## 2. Order Flow Imbalance (OFI) & Toxicity Measurement (VPIN)

### 2.1 Order Flow Imbalance (OFI) Formula
OFI quantifies the net supply and demand pressure at the top-of-book levels over a discrete time window $[t-1, t]$:

\[
\text{OFI}_t = \Delta L_{t}^B - \Delta L_{t}^A
\]

Where:
- $\Delta L_{t}^B = q_t^B \cdot \mathbf{1}_{\{p_t^B \ge p_{t-1}^B\}} - q_{t-1}^B \cdot \mathbf{1}_{\{p_t^B \le p_{t-1}^B\}}$
- $\Delta L_{t}^A = q_t^A \cdot \mathbf{1}_{\{p_t^A \le p_{t-1}^A\}} - q_{t-1}^A \cdot \mathbf{1}_{\{p_t^A \ge p_{t-1}^A\}}$

### 2.2 Volume-Synchronized Probability of Toxicity (VPIN)
VPIN (Easley, Lopez de Prado, O'Hara, 2012) measures informed trading intensity in high-frequency FX order flow. It partitions volume into equal-sized volume buckets $V$:

\[
\text{VPIN} = \frac{\sum_{\tau=1}^N |V_\tau^B - V_\tau^S|}{N \times V}
\]

Where:
- $V_\tau^B$ and $V_\tau^S$ represent buy-initiated and sell-initiated volume in bucket $\tau$.
- **Trading Threshold:** When $\text{VPIN} > 0.75$, toxicity is high, indicating market maker inventory stress, widening spreads, and heightened probability of execution slippage.

---

## 3. Market Impact & Slippage Modeling

### 3.1 Almgren-Chriss Optimal Execution & Market Impact
Market impact of an order of size $V$ executed over time $T$ is decomposed into permanent impact $\gamma(V)$ and temporary impact $\eta(v)$:

\[
S(t) = S_0 + \gamma \int_0^t v(s) ds + \eta(v(t)) + \sigma W(t)
\]

- **Permanent Impact ($\gamma$):** Linear in trade size; shifts the mid-price permanently for all subsequent market participants.
- **Temporary Impact ($\eta$):** Non-linear power law ($\eta(v) \propto v^\alpha$, where $\alpha \approx 0.5$ square-root law); dissipates after order completion.

### 3.2 TITAN Slippage Model for FX Paper Simulation
In TITAN's PyO3 execution engine, expected slippage $\Delta P$ for an order of quantity $Q$ is calculated as:

\[
\Delta P = \frac{1}{2} \text{Spread} + \kappa \cdot \left( \frac{Q}{\text{ADV}_{15m}} \right)^{0.5} \cdot \sigma_{15m}
\]

Where:
- $\kappa \approx 0.1$ is the empirical impact coefficient.
- $\text{ADV}_{15m}$ is the 15-minute average daily volume.
- $\sigma_{15m}$ is the 15-minute realized volatility.

---

## 4. Fixing Mechanics: WMR 4 PM London Fix Dynamics

### 4.1 The Benchmark Fixing Window
The WM/Reuters 4:00 PM London Fix is the global benchmark exchange rate used by index providers, pension funds, corporate treasuries, and portfolio managers to value multi-currency portfolios.

```
                       WMR 4 PM LONDON FIX WINDOW (5-MIN)
                       
   3:57:30 PM                    4:00:00 PM                    4:02:30 PM
  ──────┬────────────────────────────┼────────────────────────────┬──────
        │   Window Open              │    FIX PRICE STAMPED       │   Window Close
        └────────────────────────────┴────────────────────────────┘
        Order Flow Accumulation: Corporate hedging, Index Rebalancing,
        and Institutional Fixing Orders (MOC - Market-on-Close).
```

### 4.2 Fix Manipulation & Structural Order Flow Signals
- **Fix Ramp Dynamics:** Portfolio managers submit "Market-on-Fix" orders. Dealers aggregate net order imbalance and pre-hedge in the 15 minutes leading into 3:57:30 PM.
- **Trading Opportunity (RQ-FX-002):** Statistically significant momentum persistence exists during 3:45 PM – 4:00 PM ET, followed by a sharp mean-reverting snapback between 4:02 PM – 4:15 PM ET when dealer pre-hedging unwinds.

---

## 5. References & Academic Microstructure Evidence

1. **Hasbrouck, J. (1991).** Measuring the information content of stock trades. *Journal of Finance*, 46(1), 179-207.
2. **Easley, D., Lopez de Prado, M. M., & O'Hara, M. (2012).** Flow toxicity and liquidity in a high-frequency world. *The Review of Financial Studies*, 25(5), 1457-1493.
3. **Almgren, R., & Chriss, N. (2000).** Optimal execution of portfolio transactions. *Journal of Risk*, 3, 5-40.
4. **Banti, C., & Phylaktis, K. (2015).** FX market liquidity, systemic risk and profitability. *Journal of International Money and Finance*, 59, 279-298.
5. **Project TITAN Risk Policy.** [RISK_POLICY.md](file:///d:/projects/Project%20TITAN/RISK_POLICY.md).
