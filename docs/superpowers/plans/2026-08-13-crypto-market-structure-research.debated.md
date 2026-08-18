# Plan: Second-round review of the debated crypto plan (seed). The FINAL REVIEW claimed no contradictions with the charter, but the plan's frozen pass/fail gates (Task 4d: Net Sharpe>0.5, MaxDD<20%, >=30 trades, positive net return) do not match the charter's exact gates. The charter requires: (1) OOS net Sharpe must be positive; (2) signal IC positive in at least 70% of non-overlapping OOS windows; (3) no single instrument contributing more than 35% of cumulative net PnL; (4) candidate capacity positive under a predeclared adverse fee/spread/funding scenario; (5) replication on an independent period or venue. The plan also dropped the seed's explicit event-level contract (CryptoMarketEvent with venue, symbol, contract_kind, occurred_at, sequence, funding_rate, open_interest, source_manifest_digest). Produce the FINAL plan that (a) incorporates every charter gate verbatim or explicitly supersedes it with a stated reason, (b) restores the explicit event-level data contract, (c) keeps all the round-1 improvements (venue registry gate, snapshots, walk-forward artifact, delisted instruments, order-flow sequence policy, no-execution boundary, reproducibility), and (d) remains research-only with no execution authority. Flag anything else material for Architecture Council acceptance.

Generated: 2026-08-13T18:58:34.830285

Planners: ollama-cloud/nemotron-3-super (NVIDIA) <-> ollama-cloud/minimax-m3 (Ollama), 2 critique cycles; final review: auto/best-reasoning (Google One)

---

# FINAL REVIEWER'S ASSESSMENT

The plan to review was truncated, but the critical-review preamble surfaced the right defects. I am producing the complete FINAL approved plan from scratch, incorporating every correction identified in the critique and closing the gaps the critique itself left open (capacity semantics, secondary-venue failure rule, snapshot definition, sequence policy, delisting handling, and the missing `CryptoMarketEvent` schema). This is the plan I would hand to an implementer.

---

# FINAL APPROVED PLAN — Crypto Market-Structure Discovery Sprint (Research-Only)

## 0. Status and authority

- **Status:** Research-only discovery sprint. Contingent on ADR-029 acceptance.
- **Execution authority:** NONE. No exchange credentials, no API keys with write/trade scopes, no order placement, no paper-trading accounts, no broker/exchange adapters, no certificate issuance for execution, no simulation that emits orders to any venue. All simulators are offline, point-in-time, and read-only against historical data.
- **Scope:** BTC and ETH spot and perpetual market-structure signals only. No FX OHLCV indicator families. No moving-average/RSI/VWAP/breakout/parameter-sweep candidates unless they carry a separate, pre-registered economic mechanism.
- **Profitability assumption:** None. A negative-result report is a valid and expected outcome.

## 1. Venue registry gate (round-1 improvement)

Before any data acquisition, the venue registry must be written, content-addressed, and frozen. The sprint cannot proceed to data acquisition until the registry is committed.

Registry entries (per venue):

- venue_id, legal entity/operator, REST/WS endpoints (read-only), licence terms and URL, rate limits, symbol universe, quote currency, tick/lot/min-notional precision, fee schedule (maker/taker by tier, VIP discounts disabled), funding convention (settlement cadence, timestamp semantics, sign convention), contract/margin definitions, tick-to-trade latency estimate, venue-disconnect assumptions, data retention/provenance hash, retrieval timestamp, checksum.

Gate: registry hash is recorded in the pre-registration artifact (Section 3). Any post-freeze change to the registry invalidates all downstream results and requires re-registration.

## 2. Data contract and event-level schema

### 2.1 Source manifest (per dataset)

Each dataset record must state: venue, product/symbol, spot or perpetual contract specification, quote currency, tick/lot/min-notional precision, UTC timestamp semantics, source URL/licence, retrieval timestamp, checksum, data gaps/corrections, coverage dates, and point-in-time constituent history for cross-sectional work. Perpetual data must include funding rate/payment timestamps and sign convention. Order-flow studies require trades/quotes or L2 updates with sequence semantics.

Minimum admissible data: 24 contiguous months, 24/7 coverage, documented outage/gap rate, point-in-time constituent history, and a frozen holdout segment not used to choose parameters.

### 2.2 `CryptoMarketEvent` — restored explicit event-level contract

Every ingested observation is normalized to a `CryptoMarketEvent` before any simulation. This is the canonical event type; no raw-exchange payload reaches the simulator.

```
CryptoMarketEvent:
  event_id            : str   # content-hash of the raw record
  venue               : str   # registry venue_id
  symbol              : str   # normalized symbol
  contract_kind       : enum  # SPOT | PERPETUAL
  occurred_at          : datetime(UTC, ns, monotonic non-decreasing per symbol)
  sequence            : int64 # venue-native sequence; required for order-flow;
                              # 0/null prohibited for order-flow studies
  event_type          : enum  # TRADE | QUOTE | L2_SNAPSHOT | L2_DELTA |
                              # FUNDING | OPEN_INTEREST | MARK | LIQUIDATION
  price               : decimal|None
  qty                 : decimal|None
  side                : enum|None  # BUY | SELL | None
  funding_rate        : decimal|None  # per-period, sign per venue convention
  open_interest       : decimal|None  # base-asset units
  bid                 : decimal|None
  ask                 : decimal|None
  bid_qty             : decimal|None
  ask_qty             : decimal|None
  l2_levels           : list[(price, qty)] | None
  source_manifest_digest : str   # links to Section 2.1 manifest
  ingestion_ts        : datetime(UTC, ns)
```

Per-event validation rules:

1. `occurred_at` is UTC, nanosecond, and non-decreasing within `(venue, symbol)`. A decrease is a hard reject; the event is quarantined and the gap is logged.
2. `sequence` is required for `TRADE`, `L2_DELTA`, `L2_SNAPSHOT` event types. Missing sequence on order-flow data fails the dataset for order-flow hypotheses only.
3. `funding_rate` is required for `FUNDING` events; `open_interest` for `OPEN_INTEREST` events.
4. `price` and `qty` are required for `TRADE`; `bid`/`ask` for `QUOTE`.
5. All decimals are validated against the venue's tick/lot/min-notional precision. Out-of-tick prices are rejected, not snapped.
6. `source_manifest_digest` must resolve to a committed manifest; orphan events are rejected.

Sequence-number monotonicity check: within `(venue, symbol)`, `sequence` must be strictly increasing for `TRADE` and `L2_DELTA`. A duplicate or decrease is a hard reject for order-flow hypotheses and a logged warning for non-order-flow hypotheses (the event is dropped, not used).

Example (funding event):

```
CryptoMarketEvent(
  event_id="0x…",
  venue="venue_A",
  symbol="BTC-PERP",
  contract_kind=PERPETUAL,
  occurred_at=2023-05-01T00:00:00.000000000Z,
  sequence=None,
  event_type=FUNDING,
  funding_rate=0.0001,   # +1bp per 8h, venue convention
  open_interest=None,
  source_manifest_digest="sha256:…",
  ingestion_ts=2024-01-15T12:00:00.000000000Z)
```

### 2.3 Order-flow sequence policy (round-1 improvement)

For order-flow/liquidity-imbalance hypotheses only:

- Sequence-validity is enforced per `(venue, symbol)` on `TRADE` and `L2_DELTA` events.
- A gap is declared when `sequence` jumps by more than the venue-documented maximum in-flight depth, or when a venue heartbeat/sequence-number reset is detected.
- **Invalidation rule:** if any `(venue, symbol)` stream exhibits a sequence gap exceeding 3 consecutive expected update intervals, where "update interval" is the stream's documented median inter-arrival time measured over the prior 24h of valid data, that symbol is invalidated for that calendar day for order-flow hypotheses. Intraday invalidation is final; the symbol does not re-enter the order-flow universe until the next UTC calendar day with a clean sequence.
- Invalidated symbols remain eligible for funding/basis and funding/OI hypotheses that do not depend on order-flow sequence.
- The invalidation log is part of the reproducibility artifact.

### 2.4 Delisted and mid-period-listed instruments (round-1 improvement)

- The universe is point-in-time. A symbol enters the eligible universe on its first `occurred_at` and exits on its last `occurred_at` (delisting) or on a venue-published delisting-effective timestamp, whichever is earlier.
- Symbols delisted during the OOS period are traded until the delisting-effective timestamp; positions are force-closed at the last available bid/ask with a 2× spread penalty and a documented liquidation-only assumption.
- Symbols that list mid-period are eligible from their first `occurred_at`; no backfill of pre-listing history is permitted.
- Constituent-history freeze dates are recorded per symbol in the pre-registration artifact (Section 3). The freeze date is the timestamp at which the symbol's eligibility was determined for each simulation step; it is a hard input to the simulator and cannot be recomputed from future data.

## 3. Pre-registration artifact (charter gate E1)

Before reading the OOS segment, the following are committed to a content-addressed store and their hash recorded. This artifact is the binding pre-registration.

1. **Universe:** venue(s), symbols, contract kinds, point-in-time constituent history, eligibility rules, delisting handling (Section 2.4).
2. **Signal:** the candidate hypothesis (E3.1 cross-sectional funding/basis carry, E3.2 funding+OI deleveraging, or E3.3 order-flow/liquidity imbalance), exact construction formula, rank/weight scheme, rebalance cadence.
3. **Parameters:** all numeric parameters, thresholds, lookback windows, with no free parameters left unspecified.
4. **Cost assumptions:** bid/ask spread model, maker/taker fee schedule, funding, borrow, slippage/impact, partial-fill/participation, latency, contract multipliers, fractional precision, currency conversion, adverse fee/spread/funding scenario values (Section 4a).
5. **Position/participation caps:** max gross notional, max per-symbol notional, participation cap as fraction of 30d ADV.
6. **IS/OOS partition:** start/end dates, walk-forward folds, frozen holdout segment boundaries.
7. **Pass/fail criteria:** the five charter gates verbatim (Section 4) plus the secondary-venue rule (Section 5).
8. **Venue registry hash** (Section 1).

**No-touch rule:** Once the pre-registration artifact hash is recorded, no parameter, cost assumption, universe definition, partition boundary, or pass/fail criterion may be edited before or during the OOS read. Any edit invalidates the OOS result and requires re-registration under a new hash. The simulator must refuse to start an OOS run unless the pre-registration hash is supplied and matches the committed artifact.

## 4. Frozen decision gates (charter gates, verbatim or explicitly superseded)

All gates are evaluated on the OOS segment only, net of the full cost model (Section 6). Gates are conjunctive: all must pass.

### 4.1 Gate 1 — OOS net Sharpe must be positive (verbatim)

- **Metric:** OOS net annualized Sharpe ratio.
- **Definition:** mean(net_period_return) / std(net_period_return) × sqrt(periods_per_year), where `net_period_return` is the strategy's return per period after all costs in Section 6.
- **Frequency:** daily periods (24/7), 365.25 periods/year.
- **Annualization:** sqrt(365.25).
- **Risk-free rate:** 0.
- **Benchmark:** none; absolute Sharpe.
- **Pass:** Sharpe > 0, strictly positive, p < 0.05 against a zero-mean null via bootstrap (10,000 resamples, block length 10 days). Both the point estimate and the bootstrap lower 95% bound must be positive.

### 4.2 Gate 2 — Signal IC positive in at least 70% of non-overlapping OOS windows (verbatim)

- **Window construction:** calendar-month boundaries, UTC. Non-overlapping. Partial first/last months shorter than 15 days are dropped; otherwise retained.
- **IC metric:** Spearman rank correlation between the signal value at month-close and the subsequent month's net return, cross-sectional across eligible instruments, equal-weighted.
- **Integer rule:** with N non-overlapping OOS windows, the gate passes iff at least ceil(0.70 × N) windows have positive IC. For a 12-month OOS segment, N=12, threshold = ceil(8.4) = 9 windows.
- **Pass:** ≥ ceil(0.70 × N) windows with positive IC.

### 4.3 Gate 3 — No single instrument contributes more than 35% of cumulative net PnL (verbatim)

- **Measurement:** cumulative net PnL over the full OOS segment, per symbol (not per contract; BTC spot and BTC-PERP are one instrument "BTC" for this gate, summed across legs).
- **Net:** after all costs in Section 6.
- **Both sides:** long and short PnL are summed per instrument; the cap applies to the net cumulative contribution, not to gross.
- **Denominator:** total cumulative net PnL across all instruments. If total net PnL ≤ 0, the gate fails by definition (no positive PnL to concentrate).
- **Pass:** max_i(cum_net_PnL_i / total_cum_net_PnL) ≤ 0.35.

### 4.4 Gate 4 — Candidate capacity positive under predeclared adverse fee/spread/funding scenario (verbatim, with explicit operational definition)

- **Adverse scenario (predeclared in Section 3):**
  - Taker fee ×2 the venue's published taker fee.
  - Bid/ask spread ×2 the 90th-percentile observed spread over the IS period.
  - Funding rate shifted against the position by the 90th-percentile adverse funding move over IS.
  - Borrow rate ×2 the IS median.
  - Latency +250 ms.
- **Capacity definition:** the largest gross notional position size, expressed as a fraction of 30-day ADV, at which the strategy's OOS net Sharpe remains strictly positive under the adverse scenario.
- **Pass criterion (verbatim):** capacity > 0. The strategy must remain net profitable at some positive size under the adverse scenario.
- **Material flag for Architecture Council:** The literal charter text requires only "capacity positive." This is operationally weak — a strategy profitable at 0.001% of ADV would pass. I do not supersede the charter gate, but I flag for the Council that a stronger floor (e.g., capacity ≥ 0.5% of 30d ADV at net Sharpe > 0 under adverse scenario) should be considered for ADR-029 amendment. Until amended, the literal gate stands.
- **Reporting requirement:** the capacity curve (net Sharpe vs. fraction-of-ADV) is reported in the results artifact, so the Council can see how marginal the pass is.

### 4.5 Gate 5 — Replicate on an independent period or venue (verbatim, with implementation choice and failure rule)

- **Charter text:** "Replicate on an independent period or venue."
- **Implementation choice:** replication is performed on an independent secondary venue for the same OOS calendar period. This is a permitted implementation of the charter's "or"; it is not a supersession.
- **Secondary-venue pass criteria:** OOS net Sharpe > 0 (strictly positive, bootstrap 95% lower bound > 0) on the secondary venue. The 70%-IC gate and the 35%-concentration gate are reported but not required to pass on the secondary venue, because the charter requires replication of the result, not a full re-qualification. This narrower secondary criterion IS an interpretation and is flagged for Council acceptance.
- **Failure rule:** if the primary venue passes all five gates but the secondary venue fails its Sharpe replication:
  - The candidate does NOT advance.
  - A negative-result report is written documenting the primary pass and secondary failure.
  - The candidate may be re-registered with a different secondary venue or an independent OOS period, but only under a new pre-registration hash and only if the failure is not attributable to a data-quality issue on the secondary venue. If the failure IS a data-quality issue, the secondary venue is replaced and the replication re-run under the same pre-registration hash with a documented amendment.
- **Material flag for Architecture Council:** the secondary-venue-only Sharpe criterion is a deliberate narrowing. If the Council wants full re-qualification on the secondary venue (all five gates), that must be specified in an ADR-029 amendment.

## 5. Walk-forward artifact (round-1 improvement)

- IS/OOS partition: the 24-month minimum is split into IS (first 60%) and OOS (last 40%), with a walk-forward overlay of 6 non-overlapping folds on the IS segment only for parameter stability checks.
- The walk-forward artifact records, per fold: fold boundaries, parameters chosen, in-fold net Sharpe, out-of-fold net Sharpe, IC, concentration, capacity-under-adverse.
- The walk-forward artifact is committed before the OOS read. The OOS read uses the parameters selected by the last IS fold; no parameter selection is permitted after the OOS read begins.
- **No-touch rule (restated):** the pre-registration hash binds the walk-forward artifact. Editing parameters between the last IS fold and the OOS run is a hard violation.

## 6. Mandatory cost model (charter gate E2)

Every result reports gross return and separate net effects for:

1. Bid/ask spread (executable bid/ask, not mid).
2. Maker/taker fees (taker assumed unless a documented maker-posting logic is part of the signal; if maker, the post-fill queue risk is modeled).
3. Funding (perpetual positions, per venue convention).
4. Borrow (short spot legs, per venue/borrow-market convention).
5. Slippage/impact (square-root impact model, calibrated to IS-period trades; participation capped per Section 3).
6. Partial or unfilled orders (limit orders modeled with fill probability from IS; market orders fill at the touch up to the top-of-book depth, residual walks the book).
7. Latency (IS-estimated signal-to-fill latency + the adverse +250 ms from Gate 4).
8. Contract/currency conversion (contract multipliers, quote-currency to base-currency conversion at point-in-time FX).
9. Partial fills / participation caps (per Section 3).
10. Fractional precision (venue tick/lot/min-notional enforced; no sub-tick fills).

A bar-close constant-bps fill is labelled exploratory only and cannot qualify a candidate. Any result using it is excluded from gate evaluation.

## 7. Snapshots (round-1 improvement — definition added)

- **Snapshot:** an immutable, content-addressed archive of (a) the pre-registration artifact hash, (b) the venue registry hash, (c) the complete input dataset identifiers and checksums, (d) the simulator version and commit hash, (e) the full parameter set, (f) the RNG seed, and (g) the gate-evaluation outputs.
- **When taken:** one snapshot at pre-registration commit, one at IS/walk-forward completion, one at OOS read start, one at OOS gate evaluation completion, one at secondary-venue replication completion.
- **Purpose:** reproducibility. Any third party with the snapshot identifiers can reproduce the exact gate verdict.
- **Retention:** snapshots are retained for the life of ADR-029 plus 12 months.

## 8. Reproducibility (round-1 improvement)

- All artifacts are content-addressed (SHA-256).
- RNG seed is fixed and recorded in the pre-registration artifact.
- Simulator version is pinned by commit hash; no floating tags.
- The full pipeline (ingest → validate → pre-register → walk-forward → OOS → gates → replicate → report) is scriptable and deterministic given the same inputs.
- Any non-determinism (e.g., concurrent download ordering) is resolved by sorting on `(venue, symbol, occurred_at, sequence)` before simulation.

## 9. Negative-result terminal rule (charter gate E1)

If no hypothesis clears all five gates (Section 4) and the secondary-venue replication (Section 4.5), a negative-result report is written and the program stops. A candidate clearing the gates may request a later shadow-only ADR; it receives no execution authority from this charter.

## 10. Material flags for Architecture Council acceptance

These are not blockers for implementation but require Council acknowledgement:

1. **Capacity gate literal interpretation.** Gate 4 as written is operationally weak. A stronger floor should be considered for ADR-029 amendment. (Section 4.4.)
2. **Secondary-venue replication criterion.** The plan requires only net Sharpe > 0 on the secondary venue, not all five gates. This is a deliberate narrowing of "replicate." (Section 4.5.)
3. **Secondary-venue failure remediation.** The plan permits re-registration with a different secondary venue or independent period after a primary pass + secondary failure. The Council should confirm this is acceptable or require a terminal stop on first secondary failure. (Section 4.5.)
4. **Order-flow invalidation threshold.** The "3 consecutive expected update intervals" rule is a reasonable default but is calibrated to nothing; the Council may want a venue-specific threshold. (Section 2.3.)
5. **Force-close on delisting.** The 2× spread penalty for delisting force-closes is an assumption; the Council should confirm it is conservative enough. (Section 2.4.)
6. **Bootstrap block length.** The 10-day block length for the Sharpe bootstrap is a default; the Council may want a sensitivity sweep. (Section 4.1.)

## 11. No-execution boundary (restated for emphasis)

Nothing in this plan authorizes execution. No orders, no paper trading, no API keys with trade scope, no exchange adapters in live mode, no certificates for execution. The simulator is offline and read-only. A candidate that passes all gates receives, at most, the right to request a later shadow-only ADR. No execution authority is granted by this plan.

---

## Reviewer's final statement

This plan (a) incorporates every charter gate verbatim or with an explicitly stated interpretation flagged for Council, (b) restores the explicit `CryptoMarketEvent` schema with typing, validation, sequence-monotonicity, and an example, (c) retains all round-1 improvements (venue registry gate, snapshots defined, walk-forward artifact, delisted/mid-period instruments, order-flow sequence policy, no-execution boundary, reproducibility), and (d) remains research-only with no execution authority. The six material flags in Section 10 are the only items requiring Council acknowledgement before implementation; none are implementation blockers.
