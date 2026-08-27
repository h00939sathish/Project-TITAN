# FX-002: Asian-Session Compression to London Volatility Expansion (Pre-Registration)

- **Hypothesis ID:** `FX-002`
- **Governing ADRs:** ADR-014 (Forex Simulation), ADR-018 (IBKR Execution), ADR-031 (Canonical FX Simulation Costs).
- **Mechanism Ref:** `M-006` (Session-Transition Volatility Expansion)
- **Status:** Sealed Pre-Registration (Evaluated across `EURUSD` and `GBPUSD`).

---

## 1. Economic Mechanism & Research Questions

**Mechanism:** During the Asian session (00:00–07:00 UTC), lower global turnover and localized price discovery frequently confine trading to a narrow, compressed equilibrium. When European and UK interbank trading desks open at 07:00 UTC, the sudden influx of institutional liquidity triggers directional order-flow expansion out of the overnight equilibrium.

**Scientific Questions:**
1. Does a compressed Asian session precede elevated realized London session volatility?
2. Does the compression filter provide demonstrable value-add over trading breakouts unconditionally?
3. Does the directional breakout rule outperform an exposure-matched random direction entry executed at the exact same breakout timestamp?
4. Can the strategy generate positive net expectancy after institutional IBKR costs ($4.00 round-trip ticket minimum and top-of-book market fills)?

---

## 2. Frozen Execution & Disambiguation Rules

- **Instrument:** `EURUSD` (Primary) and `GBPUSD` (Replication) from Dukascopy 1-minute Point-in-Time Bid/Ask data.
- **Asian Session Window:** 00:00 to 06:59 UTC (7 hours / 420 1-minute bars).
  - $\text{High}_{\text{Asia}} = \max_{00:00..06:59}(\text{Ask}_t)$
  - $\text{Low}_{\text{Asia}} = \min_{00:00..06:59}(\text{Bid}_t)$
  - $\text{Range}_{\text{Asia}} = \text{High}_{\text{Asia}} - \text{Low}_{\text{Asia}}$
  - $\text{Baseline}_{20\text{d}} = \text{Rolling 20-Day Median}(\text{Range}_{\text{Asia}})$ (strictly lagged through yesterday $t-1$).
  - **Compression Trigger:** $\text{Range}_{\text{Asia}} < 0.75 \times \text{Baseline}_{20\text{d}}$.
- **London Breakout Window (07:00 to 10:00 UTC):**
  - **Long Entry:** First 1-minute bar $t \in [07:00, 10:00]$ where $\text{Ask}_t > \text{High}_{\text{Asia}}$.
  - **Short Entry:** First 1-minute bar $t \in [07:00, 10:00]$ where $\text{Bid}_t < \text{Low}_{\text{Asia}}$.
  - **Simultaneous Breakout Disambiguation:** If a single 1-minute bar exhibits $\text{High}_{\text{Ask}} > \text{High}_{\text{Asia}}$ AND $\text{Low}_{\text{Bid}} < \text{Low}_{\text{Asia}}$ simultaneously $\implies$ Mark **`AMBIGUOUS / NO_TRADE`** (prevents tick-ordering speculation).
  - **No-Trade Rule:** If no breakout occurs by 10:00 UTC, session is marked `NO_TRADE` ($0.0$ realized PnL).
- **Trade Management & Collision Rules:**
  - **Trade Sizing:** $100,000$ base units ($1.0$ standard lot).
  - **Stop Loss:** Opposite boundary of the Asian Range ($\text{Low}_{\text{Asia}}$ for Longs, $\text{High}_{\text{Asia}}$ for Shorts).
  - **Take Profit:** $2.0 \times \text{Range}_{\text{Asia}}$ above/below entry price.
  - **Stop/Target Collision Disambiguation:** If both Stop Loss and Take Profit are touched within the exact same 1-minute bar $\implies$ Pessimistic convention: **Assume `STOP_LOSS` hit first**.
  - **Time Exit:** Mandatory market close at **15:00 UTC** (London close) if neither stop nor target has been hit.

---

## 3. Institutional Cost Model (ADR-031 Canonical)

- **Commission:** $0.20\text{ bps}$ with a **strict $\$2.00$ minimum ticket fee per order ($\mathbf{\$4.00 \text{ round-trip minimum}}$)**:
  $$\text{Fee}_{\text{side}} = \max(\$2.00, \text{Notional} \times 0.000020)$$
- **Fill Mechanics:** Quote-sided top-of-book market entry and exit $+$ $0.10\text{ bps}$ adverse slippage.

---

## 4. Partitions & Rigorous Control Baselines

- **Partitions:**
  - **In-Sample (IS):** 2021-08-02 to 2024-07-31 (36 months).
  - **Out-of-Sample (OOS):** 2024-08-01 to 2026-07-31 (24 months, sealed).
- **Control Baselines:**
  1. **Unconditioned Asian Breakout Baseline:** Breakout rules applied across all sessions regardless of the compression trigger.
  2. **Timestamp-Matched Random Direction Baseline:** On compressed days with a valid breakout, enter at the *exact same breakout timestamp* with a randomly assigned 50/50 Long/Short direction, applying identical stop, target, and 15:00 UTC exit rules ($N=500$ Monte Carlo).

---

## 5. Four Decoupled Acceptance Gates

| Gate | Acceptance Criteria | Failure Action |
|---|---|---|
| **Gate 1: Volatility Expansion (Phenomenon)** | London realized range on compressed days $>$ non-compressed days (Welch's $t$-test $p < 0.05$) | Absorbing `negative_result` |
| **Gate 2: Compression Value-Add (Filter)** | Compressed Breakout Sharpe exceeds Unconditioned Breakout Sharpe by $\ge +0.30$ | Absorbing `negative_result` |
| **Gate 3: Timestamp-Matched Random Superiority (Direction)** | Net expectancy exceeds Timestamp-Matched Random Direction baseline ($p < 0.05$) | Absorbing `negative_result` |
| **Gate 4: Net Economic Hurdle (Profitability)** | OOS Net Sharpe $\ge 0.80$, Net Expectancy $\ge 2.0\text{ pips/trade}$, Max DD $\le 15.0\%$ | Absorbing `negative_result` |

If any gate fails, `FX-002` terminates permanently as an absorbing `negative_result`.
