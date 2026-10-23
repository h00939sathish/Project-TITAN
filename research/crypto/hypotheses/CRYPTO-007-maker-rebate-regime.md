# CRYPTO-007 — Maker-Rebate Fee Regime: Feasibility Frontier

- **Status:** Analysed, verdict recorded 2026-09-22. **Not rejected on the
  pre-registered structural test — but not promoted, and recommended against
  pursuit as a trading hypothesis for reasons given in §4.**
- **Governing ADRs:** ADR-029, ADR-030
- **Follows:** CRYPTO-006 (probe-gated rejection at G2b)
- **Registered before computing:** `CRYPTO-007-prereg.json`, frozen 11:05Z
- **Session:** brain `s-20260922-7f009c`, agent `qoder_titan`

## 1. Design

Only the maker fee changes. Universe, quote policy, fill rule, markout horizon,
notional and participation cap are inherited unchanged from CRYPTO-006.

Because the fee enters **additively** and does not interact with spread or
markout, the whole per-fill distribution shifts rigidly:
`median(net @ f) = median(net @ 2bps) + (2 - f)`, and identically for any fixed
quantile including a bootstrap lower bound. So the break-even maker fee is
exactly `f_be = observed_statistic + 2.0`, derivable from the sealed CRYPTO-006
artefact. **No market data was re-downloaded and the OOS partition was not
read.** No credentials were used.

## 2. Result — the predicted contradiction did not materialise

| Gate | Frozen form | Observed | |
| --- | --- | --- | --- |
| R1 | >= 50% positive gross at zero fee | **100%** (20/20) | PASS |
| R2 | corr(f_be, attainable 30d volume) <= **-0.50** | Pearson **-0.379**, Spearman -0.441 | **FAIL** |
| R3 | >= 1 depth-capable symbol with f_be_lb95 > 0 | 4: ATOM, PEOPLE, STEEM, SUSHI | PASS |

`verdict = NO_STRUCTURAL_CONTRADICTION_VERIFY_SCHEDULE_WITH_ACCOUNT_ACCESS`.

**My own recorded prior was wrong.** CRYPTO-007 §expected_outcome predicted
rejection via an attainment contradiction. It is reported as a fail, not
re-specified: a global correlation was under-powered for a relation that is
monotone in rank but strongly non-linear. The contradiction is *local* — the
thinnest names (OGN needs fee < 13.2 bps, C98 < 12.4) need the deepest cuts and
can generate the least volume ($8-10M/30d) — but diluting it across 20 symbols
produced -0.38. Changing the statistic now to recover a rejection would be the
exact post-hoc move the constitution forbids, so the gate stands as failed.

## 3. The frontier, in bps of maker fee

Names still negative at VIP0 (2.0 bps) need only a **small cut**: min 0.15,
median **0.90**, max 1.40 bps. A **rebate is not required** — this is the
substantive answer to the question asked.

| symbol | 90d vol | max attainable 30d vol | f_be median | f_be LB95 | depth-capable | cut needed | value of cut / month |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OGNUSDT | $1.51B | $10.0M | 8.45 | 13.17 | . | none | — |
| C98USDT | $1.32B | $8.8M | 7.93 | 12.36 | . | none | — |
| ONEUSDT | $2.78B | $18.5M | 4.80 | 8.06 | . | none | — |
| ZILUSDT | $2.15B | $14.4M | 4.37 | 6.74 | . | none | — |
| **PEOPLEUSDT** | **$7.11B** | $47.4M | 3.39 | **4.73** | **Y** | **none — already +LB95 at VIP0** | — |
| DASHUSDT | $2.21B | $14.8M | 4.36 | 4.01 | . | none | — |
| QTUMUSDT | $4.96B | $33.0M | 2.45 | 3.14 | . | none | — |
| ROSE / XVS / MINA / XAI | 1.4-2.4B | $9.6-16.1M | 2.03-3.23 | 1.85-2.80 | . | 0.15-0.15 | — |
| **ATOMUSDT** | **$9.05B** | $60.4M | 1.32 | **1.68** | **Y** | **0.32 bps** | ~$1,938 |
| BLUR / STEEM / SUSHI | 3.1-8.3B | $20.7-55.2M | 1.43-1.60 | 1.11-1.41 | STEEM,SUSHI Y | 0.59-0.89 | ~$2,870 / $4,893 |
| POLYX / CHZ / AUCTION / CFX / NEO | 1.75-4.3B | $11.7-28.6M | 0.98-1.66 | 0.60-1.09 | . | 0.91-1.40 | — |

Best-case monthly fee saving across **all** depth-capable names: **~$9,700**.
Total attainable 30-day volume across the entire band: **$489M** ($204M from
depth-capable names alone).

## 4. Why this is nonetheless recommended against pursuit

**(a) Every f_be here is an upper bound, and the required cuts are smaller than
the bias that inflates them.** The reversal proxy overstates half-spread, so
true f_be is strictly lower than tabulated. The depth-capable names need cuts
of **0.32-0.89 bps** to flip. The proxy's unquantified overstatement is plausibly
of that order or larger, since even a one-tick error at these spread widths is
comparable. The decision is therefore **dominated by the measurement error, not
by the fee**: an instrument whose bias exceeds the size of the effect being
sought cannot settle this, at any fee tier.

**(b) The prize is the same order as the strategy's own PnL.** ~$9.7k/month of
fee saving against a most-trustworthy edge worth ~$3.1k/month (PEOPLE, §10.2b
of CRYPTO-006). Qualifying for a tier requires holding volume at the 2%
participation ceiling continuously, and the model books those fills as
impact-free. Impact cost of tier-chasing at that intensity plausibly exceeds
the saving, which is unmodelled in the wrong direction.

**(c) The schedule is not verifiable from here, and that is itself a finding.**
Binance fee pages are JS-gated (WebFetch returned no content) and
`GET /fapi/v1/commissionRate` is signed `USER_DATA` (401). **Even the account's
own current tier cannot be read without credentials.** Any VIP table I wrote
down would be unverified, so none is load-bearing here; the monotone-volume
property is the only schedule fact relied on.

**(d) Rebate terms are promotional and revocable.** An edge whose sign depends
on a negotiated marketing tier is not a durable edge; the venue can withdraw it
unilaterally. This is an execution-assumption fragility, not a statistical one.

## 5. Verdict and lifecycle

Fee-regime change **does not** rescue the mechanism in any way that is
decidable with current instrumentation. Lifecycle position: **RESEARCH ->
SUSPEND**, not RETIRE, because §2 established that no structural contradiction
exists and PEOPLEUSDT is positive at VIP0 — the door is genuinely open, it
simply cannot be walked through without better data or account access.

What would actually change this, in order of cost:
1. **Authoritative fee schedule + own current tier** via authenticated
   `commissionRate` — a human decision about credentials. Resolves (c).
2. **Historical L2 depth** to replace the reversal proxy — resolves (a), and is
   the only item that can move the *sign*, so it dominates (1).
3. A **queue-position-explicit** fill model, which CRYPTO-006 §10.4 also named.

Nothing is promoted; `qualified_variants` unchanged; no capital, paper or live
instance. No self-promotion: this record requires Architecture Council
countersignature to move at all.

## 6. Reproduction

- `research/crypto/c007_rebate_feasibility.py` — reads only
  `research/crypto/results/CRYPTO-006-probe.json`, deterministic, no network.
- `research/crypto/results/CRYPTO-007-rebate-feasibility.json` — frontier and gates.
