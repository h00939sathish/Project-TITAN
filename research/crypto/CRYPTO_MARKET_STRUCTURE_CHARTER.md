# Crypto Market-Structure Discovery Charter

- **Status:** Active — research-only; authorized by ADR-029 (Accepted 2026-08-14)
- **Scope:** BTC and ETH spot/perpetual data; no orders, credentials, broker/exchange adapters, or paper trading

## Objective

Determine whether a structural crypto signal survives complete venue costs and independent out-of-sample testing. A profitable result is not assumed.

## Data contract

The source manifest must state: venue, product/symbol, spot or perpetual contract specification, quote currency, tick/lot/min-notional precision, UTC timestamp semantics, source URL/licence, retrieval timestamp, checksum, data gaps/corrections, and coverage dates. Perpetual data must include funding rate/payment timestamps and convention; order-flow studies require trades/quotes or L2 updates with sequence semantics.

Minimum admissible data: 24 contiguous months, 24/7 coverage, a documented outage/gap rate, point-in-time constituent history for cross-sectional work, and a frozen holdout segment not used to choose parameters.

## Candidate hypotheses

1. **Funding/basis cross-section:** neutralize directional beta with spot/perpetual or long-short construction; test whether extreme, persistent funding/basis compensates all carrying and execution costs.
2. **Funding plus open-interest deleveraging:** test whether a pre-defined extreme in funding and open-interest change predicts post-event return/reversal after accounting for the entry delay and liquidation tail.
3. **Order-flow/liquidity imbalance:** test only with sequence-valid trade/quote or order-book data; quantify the edge decay by delay and participation.

No moving-average, RSI, VWAP, breakout, or parameter sweep may be promoted as a crypto hypothesis without a separate economic mechanism and preregistered evidence record.

## Mandatory cost model

Every result reports gross return and separate net effects for bid/ask spread, maker/taker fees, funding, borrow, slippage/impact, partial or unfilled orders, latency, and contract/currency conversion. A bar-close constant-bps fill is labelled exploratory only and cannot qualify a candidate.

## Frozen decision gates

- Pre-register universe, signal, parameters, cost assumptions, position/participation caps, and IS/OOS partition before OOS evaluation.
- OOS net Sharpe must be positive; signal IC must be positive in at least 70% of non-overlapping OOS windows; no single instrument may contribute more than 35% of cumulative net PnL.
- Candidate capacity must remain positive under a predeclared adverse fee/spread/funding scenario.
- Replicate on an independent period or venue before a shadow-only proposal.

## Terminal rule

If no hypothesis clears all gates, write a negative-result report and stop this program. A candidate clearing the gates may request a later shadow-only ADR; it receives no execution authority from this charter.
