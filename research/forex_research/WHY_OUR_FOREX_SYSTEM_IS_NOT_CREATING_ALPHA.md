# WHY OUR FOREX SYSTEM IS NOT CREATING ALPHA

Here is the evidence showing where the current system loses its edge, here are the hypotheses that could explain it, here is how we tested them, here are the results, and here is what has enough evidence to move forward.

**1. Current system diagnosis**
The Hermes FX system is structurally mismatched to the current market. We are attempting to run intraday volatility-expansion technicals (FX-001 MAE Reversal, FX-002 London Expansion) in a market dominated by low-volatility carry phenomena. Our strategy incurs per-trade friction in an environment that heavily rewards time-based yield holding. The expected per-trade edge (approx. 0–2 pips) is consumed entirely by spread (0.6+ pips) and commission floors ($2.00/side).

**2. Biggest weaknesses**
Our infrastructure assumes a zero-financing (no-swap) cost model. `FxCostModel` v1 explicitly lacks `swap_long_bps_day` parameters and restricts `quote_currency` to "USD" (verified: `fx_costs.py:33`). This makes the simulator structurally incapable of evaluating carry mechanisms honestly — a prerequisite for any basket/carry research. Historical note for accuracy: carry *was* explored via rate differentials and rejected on its own evidence (EXP-00023/24 — mechanical accrual, no UIP spot anomaly), so cost-model blindness is not why carry failed; it is why carry cannot currently be *re-tested properly* as a basket strategy.

**3. Biggest sources of wasted trades**
Intraday mean-reversion and "session boundary" trades without conditionality. The data shows MAE/MFE ratios of 0.89x OOS on the active strategies, with a timestamp-matched random baseline outscoring the logic (0.84 Sharpe vs 0.60 Sharpe). We bleed capital purely to broker commissions and slippage by executing zero-edge setups.

**4. Best-performing symbols**
Only EURUSD and GBPUSD have ever been traded or tested here — there is **no trade history for any other pair**, so no "best performer" claim beyond these two is admissible. Within the tested universe, **EURUSD outperformed GBPUSD** on cost grounds (avg spread 0.45 vs 1.02 pips — `data_contracts.md`); every concept still failed on both. USD/JPY and GBP/JPY are *candidates* for a future basket universe (current divergence regime), not evidence.

**5. Worst-performing symbols**
**EUR/USD intraday mechanisms** were the most thoroughly falsified (FX-001 Case D, FX-002 Case C). Caveat: with only two pairs tested, symbol attribution is confounded with strategy attribution.

**6. Best market regimes**
The current market is fundamentally a **Carry-Dominant Compression Regime** (wide central bank divergence, low realized volatility, persistent trend for yield). Time-based holding periods and structural yield trades excel here.

**7. Worst market regimes**
Our current strategies fail severely during **Low Volatility / Rangebound** environments. They rely on expected average daily ranges (ATR thresholds) functioning as expansion triggers, which currently act as false positives, grinding out fractional wins surrounded by continuous transaction decay.

**8. Best timeframes**
Daily (D1). Moving away from intraday noise is strictly required. The transaction hurdle rate is overcome only when target macro moves expand well beyond the bid/ask spread, which demands multi-day hold times.

**9. Worst timeframes**
Tick, 1-minute, and 5-minute. Execution latency and realistic swap/slippage combinations destroy all theoretical edge on these granularities.

**10. Execution problems**
The assumption of symmetric, zero-slip limit fills. The `FxCostModel` v1 cannot price the nightly rollover swap mechanics (triple swap days, T+1/T+2 settlement quirks), leading to totally inaccurate intraday-to-swing P&L mapping.

**11. Risk-management problems**
Our architecture handles position sizing well via the deterministic Rust limits, but it completely misses structural regime risks like Central Bank intervention (e.g., BoJ JPY interventions). Risk management must implement explicit currency-level exposure caps (e.g., dollar-beta-neutrality).

**12. Data problems**
Total lack of point-in-time historical swap arrays (e.g., Dukascopy/IBKR historical points). You cannot test Carry mechanisms without knowing exactly what the overnight financing credits/debits were. Single-pair EURUSD data also causes severe sample starvation.

**13. Strategy problems**
We ran parameter-mining on single-pair corpses (FX-001/FX-002) expecting parameter tweaks to produce alpha. We are optimizing noise. The strategies demand directional predictive capabilities exceeding our model's capacity while carrying zero baseline risk premium compensation.

**14. Architecture problems**
There is no autonomous reflection loop mutating live strategy parameters in this codebase (Hermes is the operator's agent framework, not part of the trading path) — strategy evolution runs through pre-registered experiments and the promotion gate, which is correct. The real architecture defect is the simulation layer: `FxCostModel` is hardcoded to USD-quoted pairs (`fx_costs.py:33`) with no swap accounting, breaking all JPY, CHF, and CAD cross modeling before any basket strategy can even be simulated honestly.

**15. False-alpha risks**
Hindsight parameter fitting on ATR thresholds. The system tuned `VolatiltyRegime` median parameters on in-sample data and suffered immediate out-of-sample decay because the thresholds simply overfit the 2021–2023 expansionary cycles. Using static synthetic swap rates instead of actual historical swap lines will manufacture false carry PnL.

**16. Current market opportunities**
Cross-Sectional Currency Momentum (XMOM) and Volatility-Filtered Carry (M-CARRY). Verified August-2026 regime (MUFG 8/24, GlobalMacroInsights 8/17): Fed holding 3.50–3.75% under Warsh; **ECB HIKING** (2.25% June, September hike broadly priced); BoJ normalizing (57% Sept-hike pricing). Multi-polar tightening across ~2/3 of 32 tracked swap markets is structurally raising G10 dispersion — favorable terrain for cross-sectional models. **Tail warning:** yen-carry is crowded near BoJ intervention territory (USD/JPY ~159; intervention risk >160) — any M-CARRY design must cap or tail-hedge JPY funding legs.

**17. Most promising improvements**
Upgrading `FxCostModel` to v2 (to include triple-swap tables, explicit rollover convention handling, and non-USD quote conversion legs) and shifting our signal engine to score cross-sectional currency baskets instead of independent isolated pairs.

**18. Improvements that should NOT be made**
Adding more standard technical indicators to FX-001/FX-002. Do not employ Machine Learning to parse 1m bars for EUR/USD. The per-trade friction barrier makes scaling intraday retail mechanics statistically dead. Do not parameter tweak past failures.

**19. Relevant GitHub projects**
*(2026-08-26 verification pass: two previously cited repositories could not be verified and were removed per AGENTS.md rule 5.)*
- `Mohammed-AB/forex-strategy-lab` — verified real; anti-overfitting-by-design research engine (walk-forward + Monte-Carlo gauntlets, reports losers plainly). Methodology reference, not edge.
- `nautilus_trader` / `jesse` — already-absorbed architecture references (event-driven core, indicators/validation patterns).
- Note: no verified public repository demonstrates working post-cost FX alpha; absence of such repos is itself consistent with §0.

**20. Relevant research papers**
- *Burnside, Eichenbaum, Kleshchelski, Rebelo (2011)*: "The Returns to Currency Speculation" (Carry).
- *Lustig, Roussanov, Verdelhan (2011)*: "Common Risk Factors in Currency Markets".
- *Menkhoff, Sarno, Schmeling, Schrimpf (2012)*: "Currency Momentum Strategies". (Shows cross-sectional momentum holds robustly against factor models).

**21. New strategies worth testing**
*(IDs continue the registered sequence; landscape §5's provisional FX-003..006 slots were never registered, so FX-003 is free.)*
- **FX-003 (M-CARRY)**: Long high-swap / short low-swap currency baskets gated by an inverse-volatility filter, sized for 10% annualized target vol.
- **FX-004 (M-XMOM)**: Currency-level momentum (log-linearized leg performance) ranked against a 7-currency set. Long top baskets / short bottom baskets with an aggregate USD-beta constrained strictly to zero.
- **Sequencing constraint (ADR-029 discipline):** one hypothesis at a time — FX-003 registers and runs to its gates *before* FX-004 preregisters. Also note prior evidence: EXP-00023/24 found no UIP *spot* anomaly using rate differentials; M-CARRY must therefore justify why basket construction + vol-gating + true swap data differ materially from what was already rejected, in the prereg itself.

**22. Recommended experiments**
- **Exp-FX-003-PreReg**: Implement `FxCostModel` v2 handling historical Dukascopy swap points. Build the block-bootstrap pipeline for testing M-CARRY on D1 bars over 2018-2026.
- **Exp-FX-004-BetaNeutral** *(blocked until FX-003 resolves)*: Build the cross-sectional ranking engine. Use exactly {3m, 6m, 12m} static equal weight formation periods (frozen to prevent lookback data mining).

**23. 60-day paper-testing candidates**
Currently: NONE. No system meets the criteria required for 60-day paper promotion yet. Both FX-003 and FX-004 must pass rigorously coded IS-validation and OOS-hurdle gates outlined in the Phase B testing roadmap before seeing a paper trading endpoint.

**24. Strategies that should be discarded**
- FX-001: Passive MAE excursion reversal (EURUSD) — `Case D Mechanism Failure`; all four decision gates failed; underperformed a timestamp-matched random-entry control.
- FX-002: Asian compression → London expansion — `Case C Spurious`; Gate 1 failed via Welch's t-test (compressed-day London ranges were *smaller*, p=0.95–0.98 OOS); Gate 3 failed vs random direction.

**25. Final recommended architecture**
A total transition from a highly coupled, single-pair technical indicator suite toward a multi-pair, portfolio-centric quantitative model. 
- **Data Engine**: Must ingest genuine point-in-time swap/rollover points daily.
- **Simulation**: Must include `FxCostModel` v2 with conversion legs for cross-currency and inverse quotes.
- **Execution**: Focus on D1 Market-On-Open/Close implementation, driving execution costs downward.
- **Risk Pipeline**: Absolute prohibition on net-unhedged USD directional clustering unless expressly targeted; strict JPY-intervention-risk downside caps enforced at the Risk Engine level.