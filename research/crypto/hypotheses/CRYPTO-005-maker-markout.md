# CRYPTO-005: Passive Two-Sided Spread Capture (Markout Feasibility) (Pre-Registration)

- **Hypothesis ID:** `CRYPTO-005`
- **Governing ADRs:** ADR-029 (crypto market-structure program), ADR-031 (Canonical Simulation Costs).
- **Instruments:** `BTCUSDT`, `ETHUSDT` (Binance USDⓈ-M perpetual).
- **Status:** Probe-gated rejection (2026-09-20). IS-month feasibility probe failed the §1 acquisition gate; see §6. Signal and parameters were frozen before any OOS read; OOS was never run.
- **Distinctness:** Mechanism revenue is **spread capture** (compensation for resting liquidity). NOT CRYPTO-003 (directional OFI signal, taker execution — execution-constrained rejection). NOT CRYPTO-004 (funding/basis carry with maker execution — negative_result). No prior hypothesis models markout-adverse-selection as the object of study.

---

## 1. Economic mechanism & causal theory

**Mechanism:** Market makers earn the quoted spread by resting passive limit orders that aggressive takers cross. The revenue per round-trip is approximately one half-spread; the cost is adverse selection — post-fill drift of the mid against the filled side — plus maker fees. If, conditional on a top-of-book aggressor trade, `half_spread > markout(h) + maker_fee` on a sustained basis, genuine maker edge exists at that horizon.

**Scientific question:** On BTCUSDT/ETHUSDT USDⓈ-M, does post-fill markout at horizons h ∈ {1s, 5s, 60s} remain below (half-spread − maker fee) on the non-overlapping-trade basis, net of an inventory penalty, out-of-sample?

**Data-availability note (honest constraint):** Binance Vision publishes **no historical L2/depth for USDⓈ-M futures** (verified 2026-09-20; `bookDepth` exists only for spot). This study therefore uses the standard trade-tape proxy: `is_bestpk=true` aggressor trades define top-of-book and maker fill events; mid trajectory is the price path of subsequent aggressor trades. This proxy **overestimates** maker profitability (no queue priority, no cancel-out dynamics, no quote latency). Under the ADR-029 fail-closed rule: **if the proxy cannot make spread capture net-positive, the hypothesis is rejected; the proxy cannot certify promotion, only a future shadow paper phase could.**

## 2. Signal & frozen parameters

See `CRYPTO-005-prereg.json`. Summary:

- Entry: post bid and ask one tick inside the last top-of-book whenever both sides quote; fill occurs at aggressor trade price when the tape crosses the posted side (maker fee 0.020% `binance_usdt_vip0_2026-08-14` label).
- Revenue per fill: `half_spread = (p_buy_best − p_sell_best) / 2` at the prevailing top-of-book before the fill.
- Adverse-selection cost: `markout(h)` = signed mid drift against the fill at h ∈ {1, 5, 60} s.
- Inventory penalty: `inventory_penalty_bps` charged per unit normalized inventory per minute held (frozen value in JSON).
- Kill criteria (all must hold on IS AND OOS; frozen): mean net edge per fill > 0 with block-bootstrap 95% lower bound > 0 at h=60s; ≥ 1,000 fills/month/symbol; concentration of PnL in < 30% of days disqualifies.

## 3. Partitions

- In-sample: 2024-01-01 → 2025-08-31. OOS: 2025-09-01 → 2026-02-28 (read exactly once, after IS seal). Feasibility probes may use in-sample months only.

## 4. Data contract

- `data.binance.vision` daily um aggTrades zips (24 contiguous months: 2024-01 → 2025-12, minimum for IS+OOS as registered), SHA-256 manifest per ADR-031; sequence-valid, gap-counted; venue TZ UTC.
- Schema note (verified 2026-09-20): um aggTrades columns are `agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker` — **no `is_bestpk`** (spot-only). Top-of-book is reconstructed by aggressor-side reversal; half-spread proxy = |price(reversal) − last opposite-aggressor price|. This strengthens the overestimation caveat in §1: reversals miss sub-trade-tick spread.
- Acquisition: `scripts/download_binance_trades.py` (already exists; range-parameterized). Probe (exploratory, `can_qualify=False`): `research/crypto/mm_feasibility_probe.py`.

## 5. Terminal outcomes

Either (a) negative_result recorded under ADR-029 (absorbing), or (b) a candidate eligible for a separate shadow-only deployment proposal (new ADR required; no paper/live authority by this record).

## 6. Probe outcome — IS-month acquisition gate: REJECTED (2026-09-20)

Exploratory feasibility probe (`can_qualify=False`) run on in-sample data only, per §3. Two independent windows, BTCUSDT um aggTrades:

| window | trades | fills | half-spread | maker fee | markout60s | net edge/fill | LB95 | win% |
|---|---|---|---|---|---|---|---|---|
| 2024-06-01..03 | 2,077,364 | 583,047 | — | — | — | −2.02 bps | −2.02 bps | 1.0% |
| 2024-06-03..09 | 6,204,463 | 1,792,129 | $0.334 | $14.04 | −$0.43 | −2.04 bps | −2.05 bps | 1.4% |

Net edge is negative with a block-bootstrap lower bound far below zero at every horizon. The binding term is the **maker fee (~2.1 bps)**: it is roughly **40× the captured half-spread (~0.05 bps)**. Markout is even slightly favourable (price drifts toward the resting side), so adverse selection is not what kills this — cost is. The §1 fail-closed rule triggers: *the proxy cannot make spread capture net-positive → the hypothesis is rejected.* The 14-month IS+OOS download and shadow phase are therefore **not** run; that is the purpose of the cheap probe.

**Failure classification (AGENTS rule 8): Execution-Constrained Rejection, not Mechanism Failure.** The liquidity-provision mechanism is not disproven — gross spread capture and markout behave as theory predicts; the VIP0 2 bps maker fee simply exceeds the harvestable top-of-book spread on the deepest crypto pair. Any follow-up must be a **distinct pre-registered hypothesis** (e.g. `CRYPTO-006`) modelling a materially different economic regime — a negotiated VIP tier with a maker **rebate**, or a wider-spread/less-liquid instrument where quoted spread clears the fee — which is legitimate alternative-mechanism investigation, not post-hoc parameter mining of a dead signal (ADR-029/030).

**Scope of the absorbing record:** CRYPTO-005-*as-registered* (VIP0 maker fee, top-of-book reversal proxy) terminates here. Because the probe is an exploratory acquisition gate and never reached the OOS partition, this is recorded as a **probe-gated rejection**, distinct from a §5(a) OOS `negative_result`. The proxy additionally cannot measure quoted spread faithfully without depth data (§4), which is a measurement limitation, not evidence for promotion.
