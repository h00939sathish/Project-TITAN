# CRYPTO-006 — Maker Spread Capture on a Mid-Liquidity Perp Band

- **Status:** Pre-registered (frozen 2026-09-22, before any spread measurement)
- **Governing ADRs:** ADR-029 (crypto research program), ADR-031 (data manifests), ADR-030/029 (absorbing negative results)
- **Charter scope:** `research/crypto/CRYPTO_MARKET_STRUCTURE_CHARTER.md` candidate #3 (order-flow / liquidity imbalance, sequence-valid data only)
- **Authority:** research-only. No orders, credentials, broker adapters, paper or live instances. `can_qualify = false` at the probe stage.
- **Session:** brain `s-20260922-db6e58`, agent `qoder_titan`

---

## 1. Why this is a distinct hypothesis and not a retune

CRYPTO-005 (`CRYPTO-005-maker-markout.md` §6) terminated with an
**Execution-Constrained Rejection, not Mechanism Failure**. Its own words:

> The liquidity-provision mechanism is not disproven — gross spread capture and
> markout behave as theory predicts; the VIP0 2 bps maker fee simply exceeds the
> harvestable top-of-book spread on the deepest crypto pair.

It prescribed the follow-up: a **different instrument** where quoted spread
clears the fee. This record is that follow-up.

The **single variable** is the liquidity tier of the instrument. Quote policy,
fill rule, fee tier, markout horizons, notional and participation cap are held
**identical to CRYPTO-005** so that a result here is attributable to regime,
not to modelling change. The exclusion registry bars reopening *directional
OHLCV* and *bar-close constant-bps* families; this is neither — it is a
liquidity-provision revenue object on sequence-valid trade data.

**Honest prior, recorded before measurement:** on BTCUSDT the fee/spread ratio
was ~40x. For the mid band to clear, harvestable half-spread must scale up by
roughly that much (from ~0.05 bps to > ~2 bps). Mid-cap perp quoted spreads are
plausibly 5-30 bps, so this is *borderline*, and the ex-ante expectation leans
toward rejection. That is a reason to run a cheap gate, not a reason to skip it.

## 2. Hypothesis

On Binance USDT-margined perpetual futures in a **mid-liquidity volume band**
(ranks 51-150 by trailing quote volume, top 50 excluded), passively quoting
both sides one tick inside the reconstructed top of book earns a gross
half-spread that exceeds the 2 bps VIP0 maker fee plus 60 s markout, net of
participation limits — i.e. liquidity-provision compensation is positive after
realistic execution cost on instruments whose spread is structurally wider than
the toll.

## 3. Universe rule — frozen, ex-ante, price-independent

Deterministic; contains **no** spread, return or edge information, so the band
cannot be selected on the outcome it is being tested for.

1. Snapshot `GET https://fapi.binance.com/fapi/v1/exchangeInfo` (public, keyless).
   Retrieval timestamp + SHA-256 recorded in the manifest.
2. Keep `status == TRADING`, `contractType == PERPETUAL`, `quoteAsset == USDT`.
3. Keep only symbols listed **>= 12 months** before the probe window start
   (`onboardDate <= 2024-03-10`), so none is in its illiquid listing ramp.
4. Exclude pegged / fiat-quoted base assets (USDC, FDUSD, TUSD, DAI, USDE,
   USDF, BUSD, EUR, TRY, BRL, ARS and any base flagged as a stablecoin in the
   venue `underlyingSubType`). Their "spread" is a peg artifact, not a
   liquidity-provision premium.
5. Rank by **trailing 90-day quote volume** summed from daily klines over
   `2024-12-01 .. 2025-02-28` — strictly before the probe month, so no
   look-ahead into the measurement window.
6. **Band = ranks 51-150.** Ranks 1-50 are excluded: that is the CRYPTO-005
   regime, already measured as fee-dominated.
7. Sample **20 symbols by uniform stride** across the sorted band
   (`band[i * floor(len/20)]`, i = 0..19). Uniform stride, not a filter:
   no discretion to pick plausible-looking names.

## 4. Economic model — held identical to CRYPTO-005

| Element | Value |
| --- | --- |
| Quote policy | post both sides one tick inside reconstructed top of book |
| Fill rule | maker fill at aggressor trade price when tape crosses the posted side |
| Tick / min-notional | venue `tickSize` and `MIN_NOTIONAL` from the frozen snapshot |
| Quote notional | 1,000 USD per side |
| Participation cap | 2% of the traded quantity at the print |
| Maker fee | 0.0002 (2 bps) per filled side, VIP0, no BNB discount, no rebate |
| Markout horizons | 1 s, 5 s, 60 s from fill |
| Top-of-book | aggressor-side reversal reconstruction (no historical depth on Vision) |

`net_edge_bps_per_fill = captured_half_spread_bps - maker_fee_bps + markout60_bps`

`markout60_bps` is signed positive when price drifts in the resting inventory's
favour, consistent with the sign convention that produced CRYPTO-005's -2.04 bps.

## 5. Probe window

`2025-03-10 .. 2025-03-16` (7 contiguous days), inside the CRYPTO-005
in-sample partition (`2024-01-01 .. 2025-08-31`). The OOS partition
(`2025-09-01 .. 2026-02-28`) is **not read** by this probe and stays sealed.

## 6. Frozen gate criteria — the probe escalates only if ALL hold

- **G1 structural:** captured half-spread alone (before markout, before fee
  relief) exceeds the 2 bps maker fee for **>= 50%** of sampled symbols. The
  spread must be bigger than the toll before any markout luck is admitted.
- **G2 net:** median net edge per fill > 0 across symbols, and the per-symbol
  block-bootstrap 95% lower bound > 0 at h = 60 s for **>= 60%** of symbols.
- **G3 capacity:** >= 1,000 fills/month/symbol (>= 230 fills over the 7 days).
  A wide spread nobody crosses is not an edge.
- **G4 concentration:** PnL not derived from < 30% of probe days.
- **G5 realism:** every quote respects venue `tickSize` and `MIN_NOTIONAL`;
  fills capped at 2% participation.

Any failure => `probe_gated_rejection`, no OOS read, no download expansion.

## 7. Fail-closed proxy rule (inherited, restated because it decides outcomes)

The reversal proxy **overestimates** maker PnL: it cannot see sub-trade
quoted spread, queue position, cancel latency, or queue jump. Therefore:

- **proxy-negative => reject**, and that rejection is evidence-grade.
- **proxy-positive => certifies nothing.** It only justifies one human cost
  decision: buying historical L2 depth from a paid venue, since Binance Vision
  publishes only `aggTrades`/`trades`/`klines` and has **no** `bookTicker` or
  `depth` history (verified 2026-09-22 against the S3 listing for
  `data/spot/monthly/`).

## 8. Terminal outcomes

(a) `probe_gated_rejection` recorded, classified per AGENTS rule 8, and the
liquidity-provision class on this band is absorbed; or
(b) a gate-passing result that triggers a **separate** proposal for paid L2
acquisition and a shadow-only deployment — new ADR, Architecture Council
countersignature, no paper or live authority granted by this record.

No agent may self-promote. Promotion certificates are not issuable by the
author of a hypothesis.

## 9. Provenance / reproduction

- `research/crypto/manifests/binance_vision_widescap_v1.json` — frozen universe,
  snapshot hashes, per-file SHA-256.
- `research/crypto/c006_spread_probe.py` — deterministic, seedless, in-sample only.
- `research/crypto/results/CRYPTO-006-probe.json` — machine outcome.

## 10. Probe outcome — REJECTED at gate G2 (2026-09-22)

Ran the frozen protocol unmodified after registration. Band resolved to 186
eligible perps, ranks 51-150, uniform stride, 20 symbols: ATOM, SUSHI, PEOPLE,
STEEM, QTUM, CHZ, NEO, CFX, AUCTION, BLUR, ONE, XAI, DASH, ZIL, MINA, ROSE,
POLYX, OGN, XVS, C98. Window 2025-03-10..16 (IS only; **OOS partition never
opened**).

| Gate | Threshold | Observed | |
| --- | --- | --- | --- |
| G1 spread > fee | >= 50% of symbols | **70%** (14/20) | PASS |
| G2a median net edge > 0 | > 0 | +0.157 bps | PASS |
| G2b bootstrap LB95 > 0 | >= 60% of symbols | **50%** (10/20) | **FAIL** |
| G3 capacity | >= 50% of symbols >= 230 fills | 100% | PASS (weak, see 10.3) |
| G4 day concentration | >= 50% | 90% | PASS |
| G5 execution realism | tick/min-notional | held | PASS |

`outcome = probe_gated_rejection`. G2b is a **boundary** failure (10 of 20
against a threshold of 12). The threshold was frozen at 0.60 before measurement
precisely so this gap could not be closed retrospectively; it is not moved.

### 10.1 What the probe did confirm

CRYPTO-005's diagnosis transfers. Harvestable spread is **130x larger** on this
band than on BTCUSDT (median of medians 2.39 bps vs 0.018 bps), so the 2 bps
VIP0 maker fee stops being mechanically binding for 70% of the band. On the
deepest pair the fee was 40x the spread; here the spread clears the fee. The
fee/spread ratio was indeed the binding constraint, not the
liquidity-provision mechanism.

Reproduction check: re-measuring BTCUSDT with this probe's code gives mean net
edge **-2.07 bps** against CRYPTO-005's sealed **-2.04 bps**. Independent
agreement within 0.03 bps, which validates the implementation for *relative*
comparison across instrument tiers.

### 10.2 Why the positive half is not an edge — the instrument bias is the signal

`corr(median_half_spread_bps, mean_net_edge_bps) = **0.967**` across the 20
symbols. A near-perfect monotone relation between an outcome and the quantity
the proxy is *structurally biased in proportion to* is not strong evidence for
the mechanism; it is the signature of measuring the bias itself.

The proxy infers top-of-book from trade reversals. On a thin book a reversal
gap is largely **price impact and tick discretisation, not a reclaimable
quoted spread** — and it inflates in direct proportion to how thin the book is.
The peripherally positive names are exactly where that inflation is worst:

| | LB95 > 0 group | LB95 <= 0 group |
| --- | --- | --- |
| symbols | 10 | 10 |
| median 90d quote volume | **$2.10B** | **$3.81B** |
| median fills / 7d | 98,585 | 356,902 |

The apparent edge sits **mostly** in the illiquid half of the band, and the
deep names are predominantly negative:

| | LB95 > 0 group | LB95 <= 0 group |
| --- | --- | --- |
| symbols | 10 | 10 |
| median 90d quote volume | **$2.10B** | **$3.81B** |
| median fills / 7d | 98,585 | 356,902 |

`corr(illiquidity_rank, net_edge) = 0.489` — same tendency by a second,
independent axis.

**CORRECTION (2026-09-22, made during CRYPTO-007).** An earlier draft of this
section asserted that the *entire* edge sat in the illiquid half and that
"every name with real depth is net negative". That is **false**, and it was
wrong in the direction that flattered the rejection. **PEOPLEUSDT** — 90d quote
volume **$7.11B**, the second-largest in the band, and 2.4x the band median —
is net **positive** with **LB95 = +2.727 bps**. It is the single most credible
measurement in this study, because the reversal proxy's upward bias grows with
thinness and PEOPLE is the least thin of the positives. Names that do satisfy
the depth test and are negative: ATOM ($9.05B, −0.321), SUSHI ($8.28B,
−0.886), STEEM ($6.11B, −0.704). The defensible statement is therefore
*predominantly*, not *entirely*.

This correction does **not** reopen the verdict: G2b failed at 10/20 against a
frozen threshold of 12, and one large-cap positive does not supply the missing
two symbols. It does mean CRYPTO-006 understated the strength of the mechanism,
and it is the reason CRYPTO-007 was worth running at all.

### 10.2b Absolute scale, which the bps view hides

PEOPLEUSDT's net PnL was **$730.88 over 7 days** on ~$335k/day of size-clipped
turning over (0.42% of its daily volume, inside the 2% cap). The most
trustworthy surviving edge in the study is therefore worth roughly **$3.1k per
month**. Any follow-up must be judged against that magnitude, not against the
bps figures.

### 10.3 G3 passing is not evidence of capacity

G3 tests fill *count*, and the proxy over-counts fills by construction (§7).
It passes 100% and that should be read as an artifact of the instrument, not as
capacity demonstrated. Recorded so no later reader cites G3 as a passed
feasibility result.

### 10.4 Classification and the escalation decision

**AGENTS rule 8 classification: `execution_constrained_rejection` with a
`measurement_limited` qualifier.** The liquidity-provision mechanism is *not*
disproven — G1 supports it. What fails is the claim that its compensation
clears cost on instruments that can absorb capital.

Recommending **against** escalating to paid historical L2, which is the only
route §8(b) allowed. Reasoning, stated so it can be attacked: L2 depth would
sharpen the *gross spread* term — the one term the proxy already overstates —
so its expected effect is to move net edge **down** and confirm this rejection.
It cannot repair G2b, the binding failure, because G2b is a robustness test on a
quantity whose bias direction matches its sign. Spending to buy confirmation of
a rejection is not research. This is a human cost decision, not mine to make.

**Absorbing scope:** CRYPTO-006 *as registered* (reversal proxy, ranks 51-150,
VIP0 maker fee) is absorbed. Two follow-ups would be legitimate distinct
hypotheses, neither a retune of this one, and neither endorsed by this record:
(a) a **fee-regime** hypothesis on a maker-*rebate* tier, which changes the
economics rather than the measurement; (b) a **queue-position-explicit**
L2 hypothesis with fill counts derived from book dynamics instead of tape
reversals, which fixes the instrument that defeated this probe.

**Portfolio effect: no change.** Nothing qualifies; `qualified_variants`
unchanged; no capital deployed, no paper or live instance created. Consistent
with the promotion gate's record — it has now refused 41 candidates.

