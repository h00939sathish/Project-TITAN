# STRATEGY GAP ANALYSIS — 2026-09-29

What TITAN's research capability supports today, per strategy family, with the next
required experiment for each. Status scale: NONE / TOOLING / SEARCHED / SEARCHED-REJECTED
/ CANDIDATE / QUALIFIED.

---

## 1. Family inventory

| Family | Status | Evidence | Limitation | Research maturity | Next required experiment |
|---|---|---|---|---|---|
| Trend following | SEARCHED-REJECTED (FX/equities) | EXP-00016, EQ-001, REGIME_TEST (TSM sign flip post-2010), P4 | 1-2 pairs, 1y, 4h/1h, midpoint data | Mature, closed on evidence | None in current class — only on virgin multi-year data with measured spreads |
| Momentum (TSM/XS) | SEARCHED-REJECTED | EXP-00016/21/22 (net 0.00% vs gross +0.10%), EQ-001/003 | same as above; turnover kills equities variant (414%/mo EQ-002) | Mature, closed | XS momentum across ≥10 FX pairs or equities universe — the class was only tested on 2 pairs / small universes |
| Breakout (ORB) | TOOLING, 0 trades | orb.py registered; 0 trades in every per-timeframe run | volume filter meaningless on tick-count "volume" (FX) | Immature — never actually traded | Fix volume proxy, then one honest ORB run on equity 5m with real volume |
| Mean reversion | SEARCHED-REJECTED | EXP-00019 (only EURUSD short-rally leg +0.58 pips net), EXP-00026 (not cointegrated), EXP-00027 (0/16), EQ-002 | edge ≈ spread; commission floors | Mature, closed | Cross-sectional MR (rank-reversal) on ≥20-name equity universe — never tested |
| Volatility (VRP/selling vol) | TOOLING only | volatility_regime.py is a filter, not a VRP strategy; no options data | no options/IV data at all | None | Defer — requires options data; no cheap source with expected value proven |
| Carry | SEARCHED-REJECTED | EXP-00023 (t=1.14), EXP-00024 carry-vol (avg Sharpe 0.26), REGIME_TEST (insignificant both regimes) | 1y FX carry; NZD leg broken by corrupt FRED file | Mature, closed | None — closed on evidence |
| Statistical arbitrage | TOOLING, 1 test | EXP-00026 cross-pair MR: coint p=0.54 → HALT | single pair test | Immature | Multi-pair cointegration panel (≥6 pairs, multi-year 4h) — data permitting |
| Pairs / relative value | NOT TESTED | no code beyond cross-pair MR | — | None | Only after multi-year data exists |
| Market making | SEARCHED-REJECTED (crypto) | CRYPTO-005 (-2.02 to -2.04 bps/fill), CRYPTO-006 | retail fee tiers: maker fee ≈ 40× harvestable half-spread | Mature, closed | None at retail fees; revisit only with maker-rebate access (CRYPTO-007 in-flight) |
| Macro | SEARCHED-REJECTED | P2 gold FAIL; EXP-00024 COT sign-inconsistent; charter CM-001 opened | monthly data, 1 asset | Mature, closed for tested variants | CM-001 macro-surprise transmission (pre-registered, Sharpe ≥1.20 gates) |
| Order flow (OFI) | SEARCHED-REJECTED | CRYPTO-003: 0 trades, latency decay 250-500ms | latency; retail API | Mature, closed | None — infrastructure-bound, not idea-bound |
| Session effects | SEARCHED-REJECTED | EXP-00018 (IC ≈ 0), FX-002 (spurious), EXP-00019's only positive leg IS a session effect (12-16 UTC) | 1y window | Mature for tested forms | The 12-16 UTC short-rally leg on fresh data with measured spreads — cheapest surviving lead |
| Cross-asset | TOOLING only | CROSS_MARKET_ALPHA_CHARTER (new); EQ-007 PEAD failed gates | no multi-asset execution evidence | Immature | CM-001 as pre-registered |
| Regime-aware | SEARCHED-REJECTED | EXP-00015 (gated Sharpe 0.73 vs ungated 3.76 — gate HURT), P4 (gating degraded both pairs) | regime classifier dead in production | Mature for the tested gating form | Regime CONDITIONING (train/validate per regime) rather than gating on/off |
| Machine learning | NONE | no ML strategy code; regime_classifier exists but is test-only | — | None | One supervised model on the equities universe (cross-sectional) — the only ML form the data can support |
| Reinforcement learning | NONE | no RL code | — | None | Defer — external evidence (FinRL) shows no verified post-cost edge; expensive and unverifiable here |
| Hybrid / ensemble | TOOLING | ensemble.py, allocator.py, hrp_allocator.py exist — dead in production | nothing qualified to combine | Tooling only | Wire after ≥2 qualified strategies (currently 0) |

## 2. Is TITAN searching broadly enough?

**No — but not because of effort (40 experiments is substantial).** The search space was
narrow in three dimensions:
1. **Universe width**: almost everything is EURUSD/GBPUSD single-pair, or SPY alone.
   Cross-sectional FX (10+ pairs) and cross-sectional equities (the bread-and-butter of the
   factor literature) were barely touched — EQ-00x used small universes, FX XS momentum
   (EXP-00022) was tested but only 1m/week horizon.
2. **Data depth**: no bid/ask, no order book, no multi-year intraday → the entire
   microstructure class (spread capture, liquidity provision, flow) was untestable except
   via crypto, where retail fees killed it.
3. **Time**: one 12-month window that the project itself declared tuning-seen
   (EXHAUSTION_MEMO.md:47-49), then kept reusing post-freeze (EXP-00031).

The charter's absorbing exclusion registry (CROSS_MARKET_ALPHA_CHARTER.md:23-31) correctly
bans re-searching the exhausted classes. The gap is not strategy ideas — it is the data
and plumbing to test the NEXT class (cross-sectional) honestly.

## 3. The one candidate worth preserving

traderdev-ema9-vwap 4h (Pine v6 port, ATR trailing stop): +71.8 pips EURUSD / +336.5 pips
GBPUSD over 12 months, cost-aware, 2-3 of 4 quarters positive. Its honest reproduction
(EXP-00031, canonical IBKR costs) fails the multi-pair consistency hurdle (EUR OOS Sharpe
0.03 vs GBP 0.66) — correctly NOT promoted. The only question that matters: is the 4h
family a real effect on a DIFFERENT 12-month window? That question cannot be answered with
current data (longest 1h series on disk: ~3 weeks).

## 4. Bottom line

TITAN has searched one corner of the strategy space (liquid-OHLCV directional/regime/macro
on 1-2 pairs) to honest exhaustion, and proven that corner empty at retail costs. The next
searches — cross-sectional FX/equities, the one surviving session effect, and the 4h
candidate on fresh data — are all blocked by the same two things: data and a working
promotion→paper loop. Strategy ideas are NOT the current bottleneck; data and the broken
execution seam are.
