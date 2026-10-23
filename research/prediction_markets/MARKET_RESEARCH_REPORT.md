# Prediction Markets (Polymarket) — Market Research Report

- **Loop phase:** 1 — Market discovery (Research loop)
- **Date:** 2026-10-16
- **Status:** Discovery only. No hypothesis pre-registered, no simulation executed, no edge claimed.
- **Trigger:** owner surfaced an external maker-rebate paper-bot guide; checked against the CRYPTO-005 follow-up clause before any build decision.

## 1. Why this venue is in scope

CRYPTO-005 (sealed 2026-09-20) terminated as a probe-gated **execution-constrained rejection**: the VIP0 maker fee (~2.1 bps) was ~40x the captured half-spread (~0.05 bps) on BTCUSDT top-of-book. Its decision record names two legitimate follow-ups, both requiring a **new** pre-registered hypothesis: a maker-rebate fee tier, or a wider-spread instrument.

Polymarket inverts the binding cost term:

- Maker fee = 0 (verified in official fee documentation, 2026-10-16).
- Maker rebates >= 0: daily payouts funded from taker fees, category rebate 15–25%.
- Quoted spreads are wide relative to crypto: a 1c spread on a ~50c contract is ~100 bps half-spread — roughly 2,000x CRYPTO-005's captured half-spread (order-of-magnitude comparison; fill-rate/queue differences ignored).

This does not establish that an edge exists. It establishes that the specific cost term that killed CRYPTO-005 does not bind here, so the venue passes the Phase-1 plausibility screen and is admissible for a governed probe.

## 2. Verified venue mechanics (official sources, fetched 2026-10-16)

Fee model: `fee = C x feeRate x p x (1 - p)`, where C = contracts (shares), p = price in dollars (binary contract settles at $1).

| Category | Taker feeRate | Maker rebate |
|---|---|---|
| Crypto | 0.07 | 20% |
| Sports (incl. esports) | 0.05 | 15% |
| Finance, Politics, Tech, Mentions | 0.04 | 25% |
| Economics, Culture, Weather, Other | 0.05 | 25% |
| Geopolitics | 0 (fee-free) | none |

Rebate mechanics (per official docs and help center):

- A rebate pool is funded from that category's collected taker fees.
- A maker's share: `(your_fee_equivalent / total_fee_equivalent) * rebate_pool`, where `fee_equivalent = C x feeRate x p x (1 - p)` over that maker's **filled maker orders** (totals computed per market).
- Paid daily; minimum accrual threshold $1.

Program risk: docs state rebate percentages, eligibility, and pool rules "may change over time". Payout currency unconfirmed — one docs page says **pUSD**, the help center say**s USDC** (open item, resolve before modeling).

## 3. Live liquidity probe (2026-10-16, public gamma API, read-only)

| Market (category) | 24h volume | Liquidity | bid/ask |
|---|---|---|---|
| Lula 2026 (politics) | $1.3M | $734k | 0.22 / 0.23 |
| Medvedev–Paul (sports) | $1.1M | $339k | 0.999 / 1.00 |
| Fed cut 50bps (economics) | $1.0M | $1.4M | 0.001 / 0.002 |
| Fed no change (economics) | $779k | $461k | 0.86 / 0.87 |
| Flávio Bolsonaro 2026 (politics) | $523k | $762k | 0.776 / 0.778 |
| 100T vs G2 (esports) | $449k | $65k | 0.49 / 0.50 |

All six probed markets report `feeType` = fee-enabled (rebate-eligible). Note the near-0/near-1 longshot books where `p x (1 - p)` and therefore rebate accrual collapses; accrual is maximized near p = 0.5.

Read-only public endpoints reachable today: gamma-api (market metadata incl. `clobTokenIds`, `feeType`, `spread`, `bestBid`, `bestAsk`), CLOB public book (live), data-api trades tape (observed fields: proxyWallet, side, asset, conditionId, size, price, timestamp, outcome, outcomeIndex, ... — **no explicit maker/taker attribution observed; open item**).

## 4. Data-admissibility screen (ADR-029 / ADR-031)

1. Live public order book: available (read-only).
2. Historical order book: **unavailable** — CLOB `/orderbook-history` stopped returning new data after 2026-02-20 (third-party report; official confirmation and archive-extent check pending).
3. Trade tape: available; maker/taker attribution not evident.
4. Consequence: any historical study is a **tape-based top-of-book proxy** — the same structural situation as CRYPTO-005's Binance Vision constraint. Fail-closed rule applies: a proxy study can **reject**, but cannot **certify** (`can_qualify = false`). Certification requires a forward read-only shadow collector (precedent: ADR-032 crypto shadow pattern).

## 5. Phase-1 admission questions — preliminary answers

| Question | Preliminary answer |
|---|---|
| 1. Reliable data? | Partial — live book yes; historical L2 no → probe-gated only (see §4) |
| 2. Costs measurable? | Yes — fee curve and rebate formula documented; program terms mutable |
| 3. Sufficient liquidity? | Partial — top markets at $0.45M–1.3M daily support retail-scale capacity; depth beyond top-of-book unverified |
| 4. Execution modellable? | Candidate — maker fill model (tape-crossed fills, queue position), leg/inventory risk, markout; same fail-closed structure as CRYPTO-005 probe |
| 5. Demonstrable edge? | Untested — Phases 3–8 territory; nothing claimed here |
| 6. Diversification? | Unknown — event-driven resolution payoff; assess at Phase 9 if ever reached |
| 7. Complexity justified? | Deferred — new collector and resolution handling required; decide at pre-registration review |

## 6. Corrections to the source guide (verified vs. claimed)

1. **The `$0.97` two-legged example is a taker trade and is likely fee-negative on fee-enabled markets.** Both legs pay taker fees: politics at p~0.485 ≈ 2 x 1.0c = 2.0c; crypto-category ≈ 2 x 1.75c = 3.5c. A 3c gross edge can be materially reduced or erased. **Rebates accrue only to makers** — the taker executing this pair receives nothing back.
2. The coherent monetization is **passive two-sided maker quoting** (spread capture + rebate share), a structurally different trade from the guide's snapshot example.
3. "USDC rebates" — one official page now says pUSD; help center says USDC. Do not hard-code; verify first.
4. The "$465K" headline is a third-party case study the guide itself disclaims. It is **not evidence** under TITAN rules.
5. The guide's risk list (partial fills, stale data, leg risk, kill switch) aligns with TITAN standards; its beginner defaults ($10 max order) are toy-scale. Any real pre-registration must set capacity per Phase 6 rules.

## 7. Preliminary economics sketch (illustrative arithmetic ONLY — not evidence)

Crypto-category market at p = 0.5, per share:

- Taker fee: 0.07 x 0.25 = 1.75c (paid by the taker, not by a maker).
- Maker fee: 0.
- Sole-maker rebate upper bound (zero competition): 20% x 1.75c = 0.35c/share.
- Half-spread capture (quoting inside a 1c spread): ~0.25–0.5c/share, conditional on fill.

CRYPTO-005 comparison: net −2.04 bps/fill, with the fee term **subtractive at ~40x the spread**. Here the spread and rebate terms are additive; the binding new risks are adverse selection (markout), inventory/leg risk, rebate-pool dilution by competing makers, resolution/oracle risk, and market rotation (finite market lifetimes).

## 8. Decision / disposition

- **Disposition:** conditionally admissible to Phase 3 as a new pre-registered hypothesis (proposed ID `PRED-001`, subject to registry confirmation). No simulation, no promotion path, no capital authority granted.
- **A `PRED-001` pre-registration must freeze:** markout-based probe design mirroring `research/crypto/mm_feasibility_probe.py` (fail-closed: proxy-negative rejects; proxy-positive certifies nothing without shadow phase); IS window from archived tape if it exists; forward shadow-collector requirements; cost model from §2 with rebate assumption defaulted to 0 (Safe mode) and pooled-share treated as a sensitivity, never a base case.
- **Open items before pre-reg drafting:** (a) official confirmation of `/orderbook-history` status and archive extent; (b) payout currency pUSD vs USDC; (c) tape maker/taker attribution feasibility; (d) rebate pool formation details; (e) other venues (Kalshi etc.) out of scope unless separately screened.
- **Rejected alternatives:** building the guide's standalone beginner bot as a TITAN artifact (ungoverned, toy-scale, redundant next to a governed probe); the guide's taker two-legged arb as stated (fee-negative on fee-enabled markets, §6.1).

Sources fetched 2026-10-16: docs.polymarket.com/programs/maker-rebates; docs.polymarket.com/trading/fees; help.polymarket.com maker-rebates article; gamma-api.polymarket.com (live probe); data-api.polymarket.com (live probe); nautilus_trader issue #3635 (orderbook-history status).
