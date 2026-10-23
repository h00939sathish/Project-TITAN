# EXECUTION ECONOMICS

**Date:** 2026-09-29. *Is execution strong enough to preserve strategy edge?*

## Headline

**Execution is not TITAN's bottleneck. It is one of its best-engineered layers — and it was
applied in the wrong direction.** The measured finding is that **costs were over-stated by
10–100× on the studies that produced negative results**, while two studies that modelled
costs correctly (`run_traderdev_families.py`, `p4_multi_tf_confluence.py`) were the two most
interesting results in the archive.

The brief asks: *does TITAN spend more effort protecting execution than measuring how execution
affects strategy economics?* **Yes — and it never completed the measurement.**

## 1. Execution layer inventory

| Component | Status | Evidence |
|---|---|---|
| Order state machine (20 edges) | **Real** | `core/src/orders.rs:74`; mutation M15 (trailing-stop direction) **killed** |
| Fill absorption (single delta path) | **Real, idempotent** | `engine.py:638-739`; `delta <= 0` no-op `:658`; `test_duplicate_fill.py` |
| Fill pricing | **Real** | `backtest/fills.py:24`; mutation M3 (slippage sign) **killed** |
| Market impact | **Absent** | `Risk.spec.md` documents "liquidity/impact" — **not in `risk.rs:283-319`** |
| Queue position | **Absent** | No queue model. `hftbacktest/src/backtest/models/queue.rs:1130` is the reference |
| Latency model | **Absent** | No feed-latency or order-latency simulation |
| Partial fills | **Absent** | `_absorb_broker_fill` handles cumulative deltas, but the sim produces full fills |
| Rejected orders | **Partial** | `result.accepted` handled `paper_session.py:915-921` — never exercised |
| Broker constraints | **Thin** | IBKR/Alpaca adapters real; Fincept a **stub** (`fincept_native` import fails) |
| Financing / overnight | **In risk, absent in research** | `check_overnight_financing` in the risk path; **no swap series in the harness** |
| Reconciliation | **Real** | `reconciliation.rs:131`; kill-switch on Critical `engine.py:1377-1385` |
| Order latency metrics | **Never written** | `order_latency_seconds` in `operations/export.py:79`, written by nothing |

## 2. The cost-assumption audit — the actual economics

| Site | Assumed | Realistic | Ratio | Direction vs. finding |
|---|---|---|---|---|
| `validator.py:194,214` `check_cost_sensitivity(cost_bps=10.0)` → `gross − 2×0.001` | **20 bps = 20 pips RT** | 0.8–1.5 pips RT | **13–25×** | **destroys edge** |
| `run_fx_experiments.py:10-11` comment *"cost_bps=10 (~1 pip retail round trip)"* | 10 bps | 1 bp = 1 pip | **10×** | **units error** |
| `run_exp22_xs_momentum.py:26,78,82` | 10 bps/period = **5.20%/yr** | 0.52–1.04%/yr | 5–10× | **killed t=2.67 over 8 years** |
| `run_exp23_carry.py:29,104` · `run_exp_00024_carry_vol.py:34` · `run_regime_test.py:27` | 10 bps/leg/mo | ~1 bp | 10× | killed carry |
| `run_exp21_tsm_daily.py:69` | 10 bps | 0.2–1 bp | 10–50× | killed TSM daily |
| `promotion.py:79,101` `cost_bps=1.5`, **zero spread** | 1.5 bp | + spread | under | gate Sharpe is drift |
| `p2_gold_macro_momentum.py:32` 1 bp, charged once per event `:121,124` | 1 bp one side | XAU 2–5 bp RT | **2–5× under** | **flatters P2** |
| **`run_traderdev_families.py:23-24`** real b/a + 0.5 + 0.2 bp | ~0.9 bp RT | ✓ | **1×** | **CORRECT** |
| **`p4_multi_tf_confluence.py:38`** 0.4 pip/side | 0.8 pip RT | ✓ | **1×** | **CORRECT** |
| `traderdev_fx_screen.py:38` 0.8 pip RT, charged `COST_RT/2` per **flip** `:318` | 0.4 pip/flip | 0.8 pip/flip | **2× under** | leaks (L1) |
| `crypto_costs.py:11` Binance VIP0 taker + spread + impact | correct | ✓ | 1× | **CORRECT** |

**The decisive internal contradiction:** the same repository, the same instrument, the same
month: **0.9 bp** in `run_traderdev_families.py:23` and **20 bp** in `validator.py:214`.
The 20 bp figure was used on the studies that produced negative results.

## 3. What realistic FX costs actually are (verified 2026-09-29)

**Measured from tick data — use these:**
- Dukascopy EUR/USD H1, 2020-01→2024-12, 21,890 bars: **mean 0.18 pips, p90 0.30, max 2.10**
  (raw/ECN feed, so a *lower bound* for a customer account).
  https://pkg.go.dev/github.com/rustyeddy/trader
- `Vibe-Trading/agent/backtest/engines/forex.py:25-40` spread table (pips):
  EUR/USD 1.0 · GBP/USD 1.2 · USD/JPY 1.0 · USD/CHF 1.3 · AUD/USD 1.2 · USD/CAD 1.5 ·
  NZD/USD 1.5 · EUR/GBP 1.5 · EUR/JPY 1.5 · GBP/JPY 2.5 · **XAU/USD 3.2 (Dukascopy-measured)**.
  Its own comment is the right epistemic posture: *"the rest are typical retail quotes and
  should be overridden if you have better data."*
- Slippage default 0.3 pips beyond spread; `_DEFAULT_SPREAD_PIPS = 2.0`.

**Broker surveys (biased — use as an upper bound):**
- FX-Brokers.info EU study 2026 (25 brokers, 2026-04-01): Exness Raw 0.17 pips + $7 commission
  = **$8.65/lot**; *"spreads widen by an average of 114% during the Asian session."*
  https://fx-brokers.info/research/spread-study-2026
- UltimateBrokerList Q1 2026 (12 brokers): **$6–$18 all-in for a 24h round turn**; *"slippage
  of 0.5 to 1.5 pips on a market order during a volatile session is not unusual."*
  Overnight swap: **−$5.50 to −$9.80** per std lot per night. https://ultimatebrokerlist.com/real-cost-trading-eurusd
- VT Markets (2026-06-05): retail EUR/USD **0.7–1.0 pips**; *"add a 10–20% buffer."*
  https://www.vtmarkets.com/en-ca/discover/the-true-cost-of-a-trade-spread-swap-and-commission

**Academic — mechanism, not level:**
- **Osler (NY Fed SR 125):** stop-loss/take-profit orders are **5–10% of total FX deal flow**;
  *"at levels ending in 10, roughly 4.5 percent of all stop-loss buy orders are executed"* —
  stops **cluster at round numbers and cascade**.
  https://fraser.stlouisfed.org/files/docs/publications/frbnysr/frbny_sr125.pdf
- **Osler (2002):** stop-loss clustering is *"a significant source of excess kurtosis in
  exchange rates."* https://faculty.georgetown.edu/evansm1/New%20Micro/osler1.pdf
  **This is the single most important citation for any FX slippage model.** A uniform-slippage
  assumption is wrong precisely on the orders retail FX systems are most full of — and excess
  kurtosis feeds directly into the DSR kurtosis term in the statistics layer TITAN lacks.

**Recommendation:** all-in RT **0.8–1.5 pips** (raw/ECN) to **1.5–2.5 pips** (CFD), slippage
0.3 median / 1.0–1.5 p95, swap 0.55–0.98 pip-equivalents per night. Run sensitivity at
**1× / 2× / 4×** and require survival at 4×. Then **replace with your own broker's tick data** —
the only number that matters, and the one no repository can supply.

## 4. Signal edge vs. transaction cost vs. execution drag

| Experiment | Gross edge | Coded cost | Net | Verdict |
|---|---|---|---|---|
| **EXP-00022** G10 CS momentum | **+5.4%/yr (t=2.67, 8y)** | 5.20%/yr (10 bps) | **0.00%** | **Edge exists. Cost constant killed it.** At 1–2 bps → **+4.4 to +4.9%/yr, SR 0.48–0.54** |
| **EXP-00025 F1** EMA9×VWAP | +408.3 pips / 163 trades (2.51/trade) | 0.9 bp ✓ | SR 0.80 | **Cost model correct. Under-powered (SE 1.15).** |
| **P4** 20-SMA + vol gate | SR 19.25 (impossible) | 0.8 pip ✓ | — | **Cost model correct. Metric broken.** |
| **CRYPTO-006** maker capture | 4.87M fills | real maker schedule ✓ | **edge 0.157 bps** | **Cost model correct. Genuinely no edge.** |
| **EXP-00016** intraday momentum | IC −0.0834 | 10 bps | n/a | **Cost irrelevant — the effect is negative, not cost-killed** |
| **EXP-00031** canonical FX | 11 trades | IBKR ✓ | SR 0.03/0.66 | **Cost model correct. Zero information (SE 1.56).** |
| **EQ-007** PEAD | SR 1.249 net | IBKR ETF ✓ | positive adverse-cost | **Cost model correct. Under-powered (SE 0.94).** |

**Pattern:** the four studies with **correct** cost models produced the two best artifacts
(EXP-00025, CRYPTO-006), the highest-Sharpe equities result (EQ-007), and the one sound
falsification (EXP-00016). **Every study with a 10–20 bp cost constant produced a null.**

**That is a confound, not a coincidence.** The cost constant and the outcome are perfectly
correlated across the evidence base, and the correlation runs in the direction that
manufactures nulls.

## 5. The unfalsifiable gate

`promotion.py:79,101` — `cost_bps = 1.5`, **zero spread**, long/flat only
(`sig == "BUY"` → long, `"SELL"` → flat), positions derived from registry params.
`ema9vwap_promotion_report.md:35-43` **self-discloses** that this inflates Sharpe to
**5.93 / 7.13** versus the real **+71.8 / +336.5 pips**.

Good that it was disclosed. **The gate still consumed the inflated number.** A gate that knows
its own input is wrong and proceeds anyway is worse than a gate that is honestly wrong, because
it creates the appearance of rigour.

## 6. Verdict

| Question | Answer |
|---|---|
| Is execution strong enough to preserve edge? | **Yes** — the execution layer is one of the best in the repo. `rust_decimal`, idempotent fill absorption, a 20-edge state machine, reconciliation, mutation-resistant. **Not a bottleneck.** |
| Does execution cost modelling destroy edge? | **Yes — this is the single most expensive defect in the repo.** 10–100× overstatement on the failing studies, and a documented 0.9 bp vs 20 bp contradiction inside one repository. |
| Is execution *simulated* adequately? | **No** — no queue, no latency, no partial fills, no market impact, no stop-loss clustering. But TITAN is daily/4h, so this is **low priority**. `hftbacktest` is the reference if it ever matters. |
| Is TITAN over-investing in execution vs. measuring its economics? | **Yes.** IBKR + Alpaca + a Fincept stub + a Prometheus exporter, against **one cost constant that was never calibrated to a single real quote.** |
| Is execution drag being measured at all? | **No.** `order_latency_seconds` is defined and never written. No fill-slippage attribution, no adverse-selection measurement, no capacity curve beyond a weak `capacity_proxy` (`results.py:73` = avg trade value / avg equity). |

**The corrective is small and specific:** one cost schedule, one source, cited; per-instrument;
with sensitivity required at 4×; and the gate must consume the same schedule as the research.
