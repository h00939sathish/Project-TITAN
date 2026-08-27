# FX Alpha Diagnosis & Profitability Roadmap

- **Date:** 2026-08-26 (rev 2)
- **Author:** ox-alpha (orchestrated research pass: local evidence audit + market regime scan + independent GitHub falsification survey)
- **Status:** Revised after adversarial review — pending Risk Owner acceptance
- **Review history:** rev 1 REJECTED by final reviewer (agy, gemini-3.7-flash-high) with 8 findings; all incorporated below. Review log in §6.
- **Depends On:** [ADR-018](../../docs/adr/ADR-018-ibkr-paper-forex-execution.md) (Accepted), [ADR-031](../../docs/adr/ADR-031-canonical-fx-simulation-evidence.md), [ADR-029/030](../../docs/adr/) (absorbing negatives), [MECHANISM_REGISTRY.md](../../docs/MECHANISM_REGISTRY.md)
- **Supersedes:** nothing; complements [01_landscape.md](./01_landscape.md)

## 1. Why we are NOT creating alpha today

### 1.1 What we already falsified (absorbed, permanent)

| ID | Mechanism | Verdict | Evidence |
|---|---|---|---|
| FX-001 | Passive MAE excursion reversal (EURUSD London) | **Case D — Mechanism Failure** | MAE/MFE ratio 0.97x IS / 0.89x OOS, Wilcoxon p≈0.81–0.97. OOS Sharpe 0.60 < 0.80 gate; timestamp-matched random baseline scored 0.84 |
| FX-002 | Asian compression → London expansion | **Case C — Spurious** | Gate 1 inverted: compressed days have *smaller* London ranges (−4.3 pips OOS, p=0.95) |

Per ADR-029 these are dead. Any new work must be a **distinct pre-registered mechanism**, not parameter mining on these corpses.

### 1.2 Structural causes

1. **Wrong horizon.** Both attempts were intraday session-mechanics trades on majors. Round-trip cost hurdle ≈ spread (~0.6–1.0 pip) + $2.00/side commission floor + slippage ⇒ ~2–3 pips gross expectancy required *before* any edge matters.
2. **Wrong regime fit.** Tested mechanisms were volatility-*expansion* plays. The live regime (§2) is compression/carry-dominant. We paid per-trade premium in an environment paying coupon.
3. **Cost-model blind spot.** `FxCostModel` v1 has **no swap/overnight financing**, and `quote_currency` is hard-locked `"USD"` ⇒ USDJPY unsimulable ⇒ the currently-dominant FX premium cannot be measured canonically.
4. **Sample starvation via single-pair testing.** EURUSD-only designs are underpowered (random baseline outscored FX-001).

### 1.3 Independent corroboration (GitHub falsification survey)

| Project | Finding |
|---|---|
| bek01/forex-trading-bot | EWMAC daily trend FX majors 2020–26 "fails every pass criterion"; carry blocked by *no historical swap data* (same blocker as ours) |
| smsabeidi/hft | Three families falsified incl. pooled TSMOM EURUSD+GBPUSD+AUDUSD 2021–26: −$40.04/trade, t=−4.48; triggered their own track-change rule |
| ZaidHaddad6/forex-trading-research | 4 retail strategies: zero with t≥2 after 1.6 pip round-trip costs |
| Mohammed-AB/forex-strategy-lab | Anti-overfitting-by-design research engine; reports losers truthfully |

Consensus: intraday/technical retail families on majors die after costs; the two families with peer-reviewed multi-decade evidence are **CARRY** and **CROSS-SECTIONAL CURRENCY MOMENTUM** — both requiring exactly what TITAN lacks today (swap-points data; multi-pair, dollar-aware construction).

## 2. Current market regime (August 2026)

Sources: Convera monthly outlook (Aug 2026), SureShotFX desk notes (Aug 3), DailyForex (Aug 21), CCYFX carry-risk note (Mar 2026).

- Carry dominates 2026: wide policy differentials + low realized vol; ranges stable; episodic unwind risk (Aug-2024 JPY unwind as template; BoJ normalizing toward 1.0%, Fed 3.50–3.75% hold w/ hawkish dissents, ECB bias to hike).
- Levels: DXY ≈ 101 rangebound; EURUSD ≈ 1.15 (1.1324–1.16); GBPUSD ≈ 1.33; USDJPY ≈ 158–161 grind higher, intervention-sensitive above 160.
- Implication: strategies paid by *time* (swap, slow trend) fit; per-trade expansion bursts do not. **Regime observation motivates research priority only — it may not parameterize hypotheses (see §3.B).**

## 3. Profitability path

### Phase A — Infrastructure

| # | Item | Detail |
|---|---|---|
| A1 | `FxCostModel` v2 | Immutable `swap_long_bps_day`, `swap_short_bps_day`, plus a **per-pair rollover convention table** (triple-swap day varies by settlement convention: most pairs Wed→Thu ×3; USDCAD T+1 rolls triple Thu→Fri — rev-1 finding #7). All inside `digest()`. |
| A2 | Unlock non-USD quotes | Relax `quote_currency` guard with explicit conversion-leg costing; enables USDJPY, USDCHF, USDCAD. |
| A3 | Historical swap points — HARD GATE | Dukascopy publishes historical swap points; same provenance/manifest machinery as our 1m bid/ask pull. **FX-003 may not run without real dated swap series.** Static/synthetic swap schedules are permitted ONLY for sensitivity analyses flagged `can_qualify=False` (ADR-031): carry P&L driven by rate differentials makes static schedules evidence-invalidating (rev-1 finding #2). |
| A4 | Multi-pair universe | EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD (+ crosses derived from pairs, never from unverified feeds). |

### Phase B0 — Mechanism registry prerequisites (before any prereg JSON)

Add to `MECHANISM_REGISTRY.md` (Architecture Council action):
- **M-CARRY** — causal model: uncovered-interest-parity violations pay drift to yield differential holders; PnL = swap accrual ± spot drift; lineage: Burnside et al. (2011), Lustig-Roussanov-Verdelhan (2011).
- **M-XMOM** — causal model: slow information diffusion across currencies produces 3–12m relative-value continuation at currency level; lineage: Menkhoff-Taylor-Sarno-Faust (2012). **Currency-level, dollar-neutralized** — NOT pair-level sorting (rev-1 finding #1).

### Phase B1 — FX-003 preregistration (M-CARRY)

Daily bars, G10-7 universe. Long high-swap / short low-swap legs per pair where the pair's own swap term is favorable; portfolio vol-targeted.

Frozen ex ante (in `FX-003-prereg.json`, no post-hoc edits):
- Position rule: hold swap-positive side of each pair when its 20d realized-vol filter passes; filters' percentile thresholds calibrated **on IS data only** (2021–2024), then frozen.
- Sizing: inverse-vol weights, 10% annualized portfolio vol target.
- **Statistical power plan:** primary endpoint = mean daily net return t-stat over ≥18-month OOS window (2024H2–2026), block-bootstrap (10k, 5-day blocks) CI; secondary: Sharpe ≥ 0.80 gate retained. Daily granularity avoids the N=24 monthly-starvation failure mode (rev-1 finding #3).
- Gates: Q1 descriptive swap-adjusted drift sign (IS); **Q2 null = entry-timing shuffle that PRESERVES swap accrual** — tests whether conditioning adds value beyond passive carry exposure (rev-1 finding #6); Q3 fill/accessibility at daily granularity incl. rollover-cost reality; Q4 net-of-all-costs OOS hurdle.
- Event-risk handling: JPY-short exposure caps are a **standing RISK_POLICY control owned by the Risk Owner** (intervention tail is structural since 2022, knowable ex ante), NOT a hypothesis parameter (rev-1 finding #4).

### Phase B2 — FX-004 preregistration (M-XMOM, dollar-neutralized)

**Currency-level momentum**: decompose each pair's return into leg returns via log-linearization against the 7-currency set; score each currency's 3m/6m/12m trailing return vs the cross-currency average; **freeze an equal-weight composite of exactly {3m, 6m, 12m}** (rev-1 finding #5 — no selectable range). Portfolio holds long/short currency baskets with the **aggregate USD beta constrained to zero every rebalance** (weekly), so the strategy cannot collapse into dollar TSMOM — the family already falsified (rev-1 finding #1).

Its own gates (not imported from FX-003):
- Q1: cross-sectional dispersion in IS currency-level momentum scores exists and is persistent (autocorrelation of ranks).
- Q2: monotonicity — top-basket minus bottom-basket IS spread > 0 with rank ordering.
- Q3: tradability — turnover-implied costs under FxCostModel v2 with conversion legs.
- Q4: net OOS hurdle — daily-return t-stat (block bootstrap) + Sharpe ≥ 0.80, ≥18-month OOS, identical power discipline to FX-003.

### Honest expectation setting

Nothing here guarantees profit. Base rate from every honest survey: most mechanisms fail. If both FX-003 and FX-004 fail OOS, that is decisive: exit FX alpha work entirely (track-level decision) rather than iterate.

## 4. Immediate actionable sequence

1. Risk Owner: accept/reject this roadmap (esp. A3 hard gate + B0 registry additions).
2. Build A1+A2+A3+A4 (engineering; testable; no market exposure).
3. Architecture Council: ratify M-CARRY / M-XMOM registry entries.
4. Freeze FX-003 prereg JSON → IS calibration → freeze → OOS run.
5. Freeze FX-004 prereg JSON → same discipline.

## 5. What we deliberately will NOT do

- Re-mine FX-001/FX-002 parameters (ADR-029).
- Qualify any carry result from synthetic swap schedules (`can_qualify=False`).
- Run pair-ranked momentum that is secretly a dollar bet.
- Intrabar/session scalping families on majors (three independent falsifications including ours).

## 6. Adversarial review log

**Rev 1 → Rev 2.** Final reviewer: agy (gemini-3.7-flash-high). Verdict: **REJECT**, 8 findings. Disposition: #1 dollar-confounding → §B2 dollar-beta-zero constraint; #2 static-swap fallback → A3 hard gate, synthetic schedules demoted to `can_qualify=False`; #3 monthly starvation → daily-return endpoints + power plan; #4 hindsight gates → IS-only calibration, JPY cap moved to RISK_POLICY; #5 open lookback range → frozen {3,6,12}m composite; #6 baseline/gate incoherence → timing-shuffle null for FX-003, dedicated gates for FX-004; #7 rollover convention error → per-pair convention table in A1; #8 registry violation → new Phase B0 gating all preregistrations.
