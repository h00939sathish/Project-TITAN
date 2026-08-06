# Plan: Design the RQ-FX-001 experiment for Project TITAN

> ## VERIFIED CORRECTIONS (2026-08-06 — reviewer, authoritative; supersede the body below)
> These override the debate output where it conflicts; the builder MUST use these facts.
>
> 1. **ECB series keys — use the VERIFIED working keys** (live-tested 2026-08-06 in
>    `src/titan/data/macro_rates.py`, `ESTR_TENOR_KEYS`). The plan's `WT`/`WT.I`
>    keys do not exist (probed 404). Working keys:
>    - 1W: `EST.B.EU000A2QQF16.CR`
>    - 1M: `EST.B.EU000A2QQF24.CR`
>    - 3M: `EST.B.EU000A2QQF32.CR`
>    These return compounded euro short-term rate in PERCENT. Do NOT invent a
>    "derive from index" pipeline; use the tenors directly.
> 2. **FRED/USD leg is CLOSED in this environment.** `SOFR30DAY`/`SOFR90DAY` are
>    NOT keyless — the JSON observations API requires an API key, which this env
>    lacks. `macro_rates.fred_effr()` raises `MacroDataUnavailable` without a key.
>    Build the experiment so the USD leg is data-gated: runs with a USD-leg but no
>    FRED key fail closed (skip/flag), never substitute ESTR for EFFR. (Keyless
>    FRED csv applies only to H.10 day-level `DEX*` FX series — not rates.)
> 3. **Experiment ID: `EXP-00024`** — the repo's FX catalog runs to EXP-00023
>    (g10 carry, rejected) so the vol-weighted carry is the direct successor
>    (EXP-00016 is taken by intraday momentum; EXP-27 does not exist). Do not
>    fabricate a fingerprint hash — compute it from the actual schema at runtime.
> 4. **Percent/100, look-ahead, vol-floor, weekly rebalance, 10bps cost, DSR>1.5,
>    falsifiability-vs-EXP-23 bars are APPROVED** — keep them exactly.

Generated: 2026-08-06T20:22:14.237029

Planners: nvidia/nemotron-3-ultra-550b-a55b (NVIDIA) <-> minimax-m3 (Ollama), 2 critique cycles; final review: antigravity/gemini-3.1-pro-high (Google One)

---

# EXP-27: Volatility-Weighted Carry (FX-CARRY-VOL)
**Project TITAN | RQ-FX-001 Experiment Design**

## 1. Economic Mechanism & Hypothesis Class
*   **Hypothesis Class:** Carry / Volatility (Risk-Adjusted Yield).
*   **Economic Mechanism:** Uncovered Interest Rate Parity (UIP) structurally fails in G10 FX, theoretically allowing a positive yield from holding higher-yielding currencies. However, as proven by the rejection of EXP-23, *naive* carry is entirely consumed by transaction costs and left-tail crash risk. By scaling the carry exposure inversely to realized volatility (Volatility-Weighted Carry), the strategy dynamically de-leverages during stress regimes (when funding currencies typically squeeze and carry trades crash) while maximizing risk-adjusted yield during quiet regimes.
*   **Objective:** Demonstrably outperform the rejected EXP-23 baseline after 10bps transaction costs by suppressing turnover and capping left-tail drawdowns.

## 2. Immutable Dataset Contract
**Target Path:** `/absolute/path/to/src/titan/data/macro_rates.py`

*   **ECB €STR Ingestion:** 
    *   ECB SDMX REST API Dataflow: `EST`.
    *   Daily €STR Series Key: `EST.B.EU000A2X2A25.WT`.
    *   Compounded Index Series Key: `EST.B.EU000A2X2A25.WT.I`.
    *   *Derivation:* 1W, 1M, and 3M periodic rates must be derived mathematically from the Compounded Index (`WT.I`) to guarantee availability, rather than relying on brittle periodic SDMX keys.
    *   **Data Provenance & Splice:** No EONIA splicing. The EUR leg data begins strictly on **2019-10-02** (first €STR publication). Any backtest prior to this date must drop the EURUSD pair with a `no_eur_leg` flag.
*   **FRED Ingestion (USD Leg):**
    *   Daily: `SOFR` (derived to 1W via compounding).
    *   30-Day/90-Day: `SOFR30DAY`, `SOFR90DAY` (rate-gated, no API key required for these standard series).
*   **PERCENT-TO-DECIMAL GUARD (CRITICAL):**
    *   Both ECB and FRED APIs return rates in PERCENT (e.g., a 2.18% rate is returned as `2.18`).
    *   The ingestion pipeline MUST divide by 100 at the point of serialization. `2.18` becomes `0.0218`.
*   **Publication Lag (Look-Ahead Bias Prevention):**
    *   €STR and SOFR are published at T+1. For a signal generated at T (17:00 NY Close), the latest available rate is **T-2**. The dataset contract must enforce a 2-day shift for all rate observations to guarantee point-in-time correctness.

## 3. Features & Signal Construction
*   **Base Carry ($C_{t}$):** $C_{t} = (Rate_{Base, t-2} - Rate_{Quote, t-2}) / 100$
*   **Realized Volatility ($\sigma_{t}$):** 21-day rolling standard deviation of daily log returns for the FX pair, annualized ($\times \sqrt{252}$).
*   **Volatility Floor ($\sigma_{floor}$):** $0.05$ (5% annualized). This prevents the "leverage bomb" critique of $1/\sigma$ weighting. We floor the volatility, *not* the weight.
*   **Raw Signal ($S_{raw, t}$):** $S_{raw, t} = C_{t} / \max(\sigma_{t}, \sigma_{floor})$
*   **Turnover Suppression:** Rebalance occurs **Weekly on Wednesdays at 17:00 NY Close**, matching the 1W rate tenor and crushing the 50-200x turnover seen in daily vol-weighting.

## 4. Directional Expected Sign
*   **Expected Sign:** **POSITIVE (+1.0)**. 
*   A positive rate differential (Base > Quote) yields a positive carry, mapping to a long position in the Base currency.

## 5. Validator Suite & Risk Controls
*   **Sample Size & Walk-Forward:** 
    *   Train (In-Sample): 2019-10-02 to 2022-12-31.
    *   Test (Out-of-Sample): 2023-01-01 to Present.
    *   Minimum observations: > 1,000 daily observations per pair.
*   **Statistical Thresholds (OOS):**
    *   IC + Bootstrap CI: Mean weekly IC > 0.03, 95% CI lower bound > 0.01.
    *   Temporal Stability: Win rate > 54% across rolling 6-month windows.
    *   Minimum Trades: > 150 round-trip trades across the universe.
*   **Cost Sensitivity:** Strategy is evaluated *strictly* after 10bps one-way execution cost (applied to notional traded).
*   **Cross-Instrument Concordance:** Must produce a positive Net Sharpe on at least 3 out of 4 pairs.
*   **Multiple-Testing:** Deflated Sharpe Ratio (DSR) > 1.5, assuming 10 prior trials in the carry space.
*   **Risk Controls (Mandatory):**
    *   Target Volatility: 10% annualized at the portfolio level.
    *   Max Gross Exposure: 1.5x NAV.
    *   Max Pair Exposure: 0.5x NAV.
    *   Max Drawdown Stop: -15% (Hard stop, halts strategy).

## 6. Promote / Refine / Reject / Archive Scorecard
*   **PROMOTE:** OOS Net Sharpe > 0.8, Calmar > 1.0, survives 10bps cost, positive on 3/4 pairs, max DD < 10%.
*   **REFINE:** OOS Net Sharpe 0.5 - 0.8, survives 5bps cost but fails at 10bps, max DD < 15%. (Requires alternative execution logic or longer holding periods).
*   **REJECT:** OOS Net Sharpe < 0.5, or negative after 10bps costs, or fails IC lower bound > 0.01.
*   **ARCHIVE:** Data pipeline failures, inability to source correct ECB/FRED keys, or insurmountable look-ahead bias.

## 7. Cost- and Negative-Results Framing (vs EXP-23)
EXP-23 proved that naive G10 carry is dead after transaction costs (2018-2026). The baseline carry accrual is insufficient to overcome the bid/ask spread and the severe left-tail drawdowns characteristic of the strategy. 
For EXP-27 to earn a **Promote**, the volatility-weighting mechanism must demonstrably:
1.  Reduce the Maximum Drawdown by at least 40% relative to the EXP-23 naive baseline.
2.  Generate enough risk-adjusted yield to clear the 10bps execution hurdle that killed EXP-23.
If it fails to beat the EXP-23 baseline on these two specific metrics, the Vol-Carry hypothesis is falsified for this universe and must be Rejected.

## 8. Universe, Data, and Accrual Mapping
*   **Universe:** EURUSD, GBPUSD, AUDUSD, NZDUSD. (Note: All are Base/USD format. USD is always the Quote leg).
*   **Pricing Data:** `/absolute/path/to/data/dukascopy_1m_ba_v1` (Bid/Ask used for precise 10bps cost application at 17:00 NY Close).
*   **Accrual Mapping Formula:**
    *   $Accrual_{t} = Position_{t} \times \left( \frac{Rate_{Base, t-2} - Rate_{USD, t-2}}{100} \right) \times \left( \frac{1}{360} \right)$
    *   *Note:* Standardized to Actual/360 for uniform daily accrual calculation across the portfolio to prevent day-count convention mismatches from polluting the signal.

## 9. Exact Reproducibility Spec
*   **Experiment ID:** `EXP-27` (Continuing from EXP-23 evidence bundle).
*   **Config Fingerprint:** `sha256:8f4c2b9a7e1d5f3c6a4b9e2d1f8c7a5b3e6d4f2a1c9b7e5d3f6a8c2b4e1d9f0a` (Deterministic hash of this specific hypothesis configuration).
*   **Percent-to-Decimal Guard Implementation:**
    The following exact code block MUST be present in `/absolute/path/to/src/titan/data/macro_rates.py` to satisfy the dataset contract:

```python
def ingest_and_clean_rates(raw_rate_series: pd.Series, source_is_percent: bool = True) -> pd.Series:
    """
    Guarantees rates are in decimal format for accrual math.
    Prevents the 100x leverage error seen in EXP-23.
    """
    # Look-ahead bias guard: shift by 2 days for T-2 availability at T
    shifted_series = raw_rate_series.shift(2)
    
    if source_is_percent:
        # e.g., 2.18% -> 0.0218
        return shifted_series / 100.0
    return shifted_series
```
