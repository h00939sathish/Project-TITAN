# FX Trading — Research Landscape

> Status: v1, 2026-08-01. Every citation below was **verified** on this date via
> arXiv API or Crossref (DOI/SSRN/NBER IDs). No unverified references are included.
> Purpose: evidence base for the TITAN FX research pipeline (EURUSD/GBPUSD,
> tws_5m_v1 dataset). Maps to Research OS: hypothesis classes -> experiments.

---

## 0. Executive summary

1. **The strongest, most robust FX evidence is trend/momentum** (time-series momentum and
   currency momentum), with documented Sharpe ratios ~0.5–1.0 after costs in
   published samples spanning decades. It is the family most suitable for a small
   systematic account, and it is *not* what we were running (5/20 MA cross is a
   crude cousin of this family with no published evidence).
2. **Carry has real evidence but crash risk** (2008–09, 2015 CHF) — needs vol/risk
   management or it will periodically destroy a small account. Carry is also
   rate-differential data we don't have yet.
3. **Mean reversion in FX is weak/unreliable** at daily+ horizons; intraday
   reversion exists in microstructure but is dominated by costs for retail size.
4. **Intraday seasonality is real and robust** (London/NY overlap; U-shaped vol;
   announcement spikes) — useful for *scheduling* trades and vol conditioning,
   not as a standalone alpha.
5. **LLM/multi-agent trading frameworks are research workflow tools, not edge** —
   no verified evidence they beat simple baselines out-of-sample after costs.
   Our AGENTS.md already treats TradingAgents as research-only. Correct.
6. **The #1 practical error we're exposed to: the midpoint illusion.** Our TWS FX
   data is MIDPOINT. Every backtest must add explicit spread + slippage or it
   will systematically flatter results (and our 5-min bars avg only 2.8–3.8 pips
   range vs ~0.5–1.0 pip spread — costs are 20–35% of bar range).

---

## 1. FX market structure & execution reality (practitioner layer)

### Who trades, and what that means for us
- Interbank/ECN (EBS, Reuters Matching): the real market. Spreads EURUSD ~0.1–0.3
  pip for $1m+ tickets. Retail brokers quote wider (0.5–1.5 pips EURUSD, more in
  illiquid hours).
- Retail order flow is largely B-book (broker internalizes, may not hit the real
  market) or A-book (passes to liquidity providers). IBKR is A-book/ECN-style —
  our fills are closer to real market prices than a dealing-desk broker, but we
  still pay the retail spread + commission.
- IBKR FX: CASH contracts on IDEALPRO, commission ≈ $2 per $100k notional
  (0.2 bps) + the live spread. Our paper account shows the same spread dynamics.

### Sessions and liquidity (our own data confirms)
- Peak volatility 12:00–15:00 UTC (London/NY overlap) — our EURUSD 5-min bars
  show avg range 4.2 pips at 14:00 UTC vs ~2 pips in Asia hours.
- Tokyo session (00:00–08:00 UTC): thinner, slower, wider effective spreads.
- **Practical rule: trade only 12:00–16:00 UTC for FX** unless the hypothesis
  specifically concerns overnight/Asia behavior. This alone cuts cost drag.

### Rollover/swap
- Positions held past 21:00 UTC (5pm ET) accrue/pay swap based on the interest
  differential (carry!). EURUSD ~0–2 pips/day either direction depending on
  rates. For intraday strategies holding < 1 session, ignore; for multi-day,
  must model — it's the mechanism behind the carry trade.

### The midpoint illusion (critical)
- Backtests computed on MIDPOINT data assume you transact at mid. Real fills:
  buy at ask, sell at bid. EURUSD mid-minus-trade ≈ half-spread ≈ 0.3–0.7 pip
  round trip, plus commission.
- A 5-min bar with 2.84 pips average range: half-spread is ~10–20% of the move.
  Strategies capturing < 1–2 pips per trade are dead on arrival after costs.
- **Rule for our pipeline: every experiment on tws_5m_v1 must subtract a
  configurable spread (default 1.0 pip round trip EURUSD, 1.2 GBPUSD) + 0.2 bps
  commission, and the Validator's cost-sensitivity gate (10bps RT) applies.**

### Data sources for honest research (verified URLs exist / public)
- **Dukascopy** tick data (free, real bid/ask): `dukascopy.com` — the standard
  free source for true tick + bid/ask history. (Need to check download tooling.)
- **histdata.com** — free 1-min bid/ask and tick M1 data per pair.
- **IBKR TWS reqHistoricalData** — what we have: 5-min OHLC, MIDPOINT for CASH.
- **yfinance / Yahoo** — OHLC, no reliable bid/ask; fine for daily features.
- **FRED** — interest rates, CPI, term spreads (macro features for carry/vol).
- Next step for our pipeline: pull Dukascopy 1-min bid/ask for EURUSD/GBPUSD
  2025–2026 → contract tws_5m_v1 is a *profiling* dataset; the *validation*
  dataset must have bid/ask.

---

## 2. Strategy families — evidence table

| Family | Mechanism | Key papers (verified) | Reported effect | Robust? | Implementation notes for us |
|---|---|---|---|---|---|
| **Time-series momentum / trend** | Past returns predict future returns (positive autocorr. at 1–12m) | Moskowitz-Ooi-Pedersen 2012 (SSRN 2089463); Hurst-Ooi-Pedersen 2017 (SSRN 2993026) | TSM: 58 markets 1880–2009, Sharpe ≈ 0.7–1.0 net; trend-following CTA factors 1880–2016 Sharpe ≈ 0.8–1.0, 30% of period negative | **Robust** across markets/centuries; crashes rare but exist (2009) | Needs 1–12 *month* lookbacks — needs daily data + multi-month history. Not 5-min. This is the #1 candidate family for our research. |
| **FX momentum (cross-sectional)** | Currency winners keep winning over 1–12 months | Menkhoff et al. 2012 (SSRN 1773543); Okunev-White 2001 (SSRN 264574) | Momentum portfolio of 20-48 currencies: ~8–12%/yr, Sharpe ≈ 0.6–1.0; FX momentum strongest at 1-month lookback | **Robust** across samples; survives costs in institutional samples | Needs a *basket* of currencies (we have 2). Cross-sectional = universe matters. With 2 pairs it degenerates to TSM on 2 legs. |
| **Carry** | High-rate currencies earn premium + crash risk | Lustig-Roussanov-Verdelhan 2011 (NBER w14082); Menkhoff et al. 2012 (DOI 10.1111/j.1540-6261.2012.01728.x); Koijen et al. 2018 (NBER w19325); BNP 2008 (NBER w14473) | HML carry Sharpe ≈ 0.5–0.9; but skewness strongly negative: -30%+ in 2008–09 | **Robust but crash-prone** — must be vol-managed or small | Needs interest-rate differentials (FRED data). 2008-style crash = account killer at retail leverage. |
| **Volatility-managed variants** | Scale position by inverse realized vol | Moreira-Muir 2017 (NBER w22208) | Improves Sharpe ~30–60% on momentum/value/carry; reduces left tail | **Robust** — works across asset classes | Directly applicable: scale FX positions by realized vol (we have vol data). Cheap, high-value feature. |
| **Value (FX)** | Cheap currencies (PPP deviations) appreciate | Asness-Moskowitz-Pedersen 2013 (SSRN 1363476) | Value-momentum combo in FX: Sharpe ≈ 1.0+ (global multi-asset) | Robust in sample; slow (yearly rebalance) | Needs long history + PPP data. Research-stage only. |
| **Mean reversion (daily+)** | Deviations from equilibrium revert | Weak/contested; no canonical verified FX paper found in this sweep (Sager-Taylor results are announcement/microstructure) | Mixed at best | **Weak** | Skip as primary alpha; use only as a secondary filter. |
| **Intraday seasonality/microstructure** | U-shaped intraday vol; announcement spikes; London/NY overlap | Andersen-Bollerslev 1998 (NBER w5783) | Intraday FX vol strongly U-shaped; announcements spike vol 2–5x | **Very robust** | Use for *scheduling* (trade 12–16 UTC) and *vol conditioning*, not standalone alpha. |
| **Momentum crashes / death periods** | Negative results & regime breaks | Daniel-Moskowitz 2016 (NBER w20439); Asness-Frazzini-Moskowitz 2014 (SSRN 2435323) | Momentum loses badly in rebounds from crashes (1932, 2009); carry crashes 2008–09 | Warning, not a strategy | Expect & survive: vol-scaling + position caps + the kill switch are the answer. |

### The 10 most important papers (all verified)
1. Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, JFE — https://doi.org/10.2139/ssrn.2089463
2. Hurst, Ooi & Pedersen (2017), *A Century of Evidence on Trend-Following Investing* — https://doi.org/10.2139/ssrn.2993026
3. Menkhoff, Sarno, Schmeling & Schrimpf (2012), *Carry Trades and Global Foreign Exchange Volatility*, JF — https://doi.org/10.1111/j.1540-6261.2012.01728.x
4. Menkhoff, Sarno, Schmeling & Schrimpf (2012), *Currency Momentum Strategies*, JFE — https://doi.org/10.2139/ssrn.1773543
5. Lustig, Roussanov & Verdelhan (2011), *Common Risk Factors in Currency Markets*, RFS — https://doi.org/10.3386/w14082
6. Brunnermeier, Nagel & Pedersen (2008), *Carry Trades and Currency Crashes*, JFE — https://doi.org/10.3386/w14473
7. Koijen, Moskowitz, Pedersen & Vrugt (2018), *Carry*, JFE — https://doi.org/10.3386/w19325
8. Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*, JF — https://doi.org/10.2139/ssrn.1363476
9. Moreira & Muir (2017), *Volatility-Managed Portfolios*, JF — https://doi.org/10.3386/w22208
10. Daniel & Moskowitz (2016), *Momentum Crashes*, JFE — https://doi.org/10.3386/w20439

---

## 3. AI/LLM/ML trading agents — architecture survey (all arXiv IDs verified)

| Framework | arXiv | Architecture | Credibility of reported results |
|---|---|---|---|
| TradingAgents | 2412.20138 | Multi-LLM-agent debate: analyst, researcher, trader, risk roles; layer-wise (research→decision→trading→risk) | Backtest on 2022–2024 SPY/QQQ; **no costs, no OOS discipline, no baseline comparison rigor** → treat as research-workflow inspiration only (per AGENTS.md) |
| FinAgent (Multimodal Foundation Agent) | 2402.18485 | Tool-augmented multimodal agent (text+visual+financial data), memory, diversified reasoning | Stock backtests w/ some baselines; still backtest-only, costs unclear |
| FinGPT | 2306.06031 | Open-source financial LLM family (LoRA fine-tunes for sentiment etc.) | Useful as a *sentiment feature generator*, not a trader |
| TradingGPT | 2309.03736 | Multi-agent w/ layered memory + distinct characters | Backtest-only, small samples |
| FinMem | 2311.13743 | LLM agent w/ layered memory (working/episodic/semantic) for trading decisions | Backtest-only |
| Alpha-GPT 2.0 | 2402.09746 | Human-in-the-loop alpha mining: LLM generates candidate alphas → validation | Interesting workflow: LLM as alpha-idea generator, quant validation downstream. Aligns with our research pipeline! |
| FinRL | 2011.09607 | Deep RL (PPO/SAC/DQN) library for trading | RL trading consistently fails to beat baselines in honest replications; sensitive to hyperparams |
| LLM & financial sentiment | 2503.03612 | Analysis of what LLMs measure as "sentiment" | Highlights that LLM sentiment is poorly defined/validated — feature, not alpha |
| DNN time-series momentum | 1904.04912 | Neural net enhancement of TSM | Modest gains vs classic TSM; useful reference for ML-on-FX |

### Verdict on agents
- **Adopt (architecture):** role decomposition (research→decision→risk), layered
  memory/journaling, and Alpha-GPT-style "LLM proposes, quant validates" — as
  research workflow, matching our Experiment→Evidence→Validator loop.
- **Adopt (feature):** LLM sentiment as an experiment feature (FinGPT-style),
  only through the standard validator (IC, stability, cost sensitivity).
- **Reject (as edge):** any LLM/agent "trading signal" claimed without
  out-of-sample costs-included evidence. No verified paper in this sweep shows
  such evidence. Our deterministic pipeline + human-approved promotion stands.

---

## 4. Honest-backtest checklist for our FX pipeline

1. **Bid/ask data**: upgrade tws_5m_v1 → Dukascopy/histdata 1-min bid/ask for
   EURUSD/GBPUSD. Until then, all experiments on midpoint data MUST subtract the
   spread config (default 1.0 pip RT EURUSD, 1.2 GBPUSD).
2. **Cost model**: spread + 0.2 bps IBKR commission + rollover for >1-session holds.
   Validator's 10bps RT gate applies to every experiment.
3. **Session filter**: default trade window 12:00–16:00 UTC (London/NY). Report
   results for the full day AND the filtered window separately.
4. **Sample**: 2 months (tws_5m_v1) is profiling-only. Pull ≥ 2 years of
   1-min/5-min data before any Promote decision. Validator requires ≥100 samples
   and 3-period temporal stability — 2 months of 5-min bars is ~2,400 RTH bars
   per pair, enough for *experiments*, not for *promotion*.
5. **Position sizing**: consistent notional risk per position (e.g., 2–5% of
   equity) across asset classes — fix the 1-share-vs-1000-unit inconsistency.
6. **Vol scaling**: apply inverse realized-vol scaling (Moreira-Muir) as a default
   risk layer; the engine's position caps + kill switch handle the crash leg.
7. **Expectation**: published FX strategy Sharpes (0.5–1.0) are institutional,
   diversified, often multi-decade. A 2-pair, 2-month, retail-cost system should
   expect materially lower — and the Neg Results Library is the honest home for
   most early attempts.

---

## 5. Candidate experiments (mapped to Research OS, ready to run on tws_5m_v1)

| EXP | Hypothesis class | Question | Features | Target | Notes |
|---|---|---|---|---|---|
| FX-001 | Trend (TSM) | Does intraday/1h momentum (e.g., 12h return) predict next-bar/next-session EURUSD return after costs? | return_12h, return_1h_slope | fwd_return_1h / fwd_session | Profiling on 5-min; if IC survives → pull longer data |
| FX-002 | Volatility | Does realized vol (1h/4h) predict next-session vol (vol clustering)? | rv_1h, rv_4h, hour-of-day | next_session_rv | Robust per literature; feeds vol-scaling layer |
| FX-003 | Calendar/session | Are London/NY-overlap bar returns systematically different (mean, vol, sign)? | hour_utc, session flags | bar_return | Andersen-Bollerslev-consistent; cheap, high-confidence |
| FX-004 | Vol-managed trend | Does vol-scaling improve FX-001's risk-adjusted return (Moreira-Muir test)? | scaled signal | risk_adj_ret | The "free lunch" of the literature |
| FX-005 | Carry | Does the EURUSD/GBPUSD rate differential predict multi-day direction? | rate_diff (FRED), rollover | fwd_return_5d | Needs FRED data pull; crash-risk awareness |
| FX-006 | Mean reversion | Do large intraday deviations (z-score vs 1h mean) revert within 1h? | z_score_1h | fwd_return_1h | Expected negative; files a Neg Result either way |

**First three are runnable TODAY on tws_5m_v1.** FX-001 is the priority — it
tests the family the literature says is strongest, at a horizon we can execute.

---

## 6. Open questions / next actions

1. Pull bid/ask data (Dukascopy/histdata) → tws_1m_ba_v1 contract for EURUSD/GBPUSD.
2. Pull FRED rate differentials (ECB/Fed/BoE policy rates) for carry features.
3. Run FX-001..003 as the first registered experiments in the Research OS.
4. Re-run the ma-crossover sweep ONLY to file its negative result properly
   (the 5/20 MA cross is not a published strategy; it's a crude TSM proxy).
