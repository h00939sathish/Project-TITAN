# NEGATIVE RESULT BATCH — EXP-00025: trader.dev strategy families on FX

# Hypothesis
24 strategies inventoried from the trader.dev MCP server (user's own account,
PLAN GATE approved) collapse into 6 distinct signal/exit families (12mo real
Dukascopy 1m bid/ask for EURUSD + GBPUSD, resampled to 1h/4h). Test whether any
family yields robust, net-of-cost positive returns suitable for TITAN FX.

# Result (real fills, real spread + 0.5bps slippage + 0.2bps commission)

Family identity:
  F1 ema9_vwap    — EMA9 cross VWAP + ATR trailing          (trader.dev dominant)
  F2 ema20_60     — EMA20/60 cross + 2.5/11% SL/TP
  F3 st_double    — double SuperTrend (13/3 + 65/3) flip
  F4 st_vol_trail — SuperTrend flip + vol filter + max(ST, entry-2ATR) trail
  F5 spectral     — trend-centroid filter + EMA20/60 cross + SL/TP
  F6 adx_vwap     — EMA9xVW + ADX>=18 + SMA200 filter + ATR trail + hard SL

Aggregate net pips (2 pairs, both timeframes, pooled trades):
  F5_spectral      -       -863.3 pips / 10 trades
  F4_st_vol_trail  -      -1039.1 pips / 258 trades
  F3_st_double     -      -1327.8 pips / 427 trades
  F2_ema20_60      -      -1407.9 pips /  11 trades
  F6_adx_vwap      -      -1716.2 pips / 508 trades
  F1_ema9_vwap     -      -1895.8 pips / 758 trades   (but 1m timeframe dominates the pool; see split)

F1 split:
  1h pooled  -1895.8 pips (bleeds - unreliable at fast scale)
  4h pooled  +408.3 pips  (84+79 trades)   <- NET POSITIVE on the main pair band
     EURUSD 4h: +71.8 pips (84 tr), only 2/4 quarters positive
     GBPUSD 4h: +336.5 pips (79 tr), 3/4 quarters positive

# Vol-regime gating (combine with PROMOTED vol-clustering EXP-00017):
  POOLED @4h: base +408.3 -> gate-LB40 -13.3 (hurts GBP: 2/4) -> gate-LB168 +673.5 (3/4)
  EURUSD improves to 3/4 under LB40; GBPUSD needs LB168 for 3/4. No single
  gate-clearing parameterization; the edge neither collapses nor robustly clears.

# Decision: F1_ema9_vwap @4h is a CANDIDATE (net positive on the primary FX
pairs at the 4h scale); all other families are REJECTED as strategies for TITAN
FX. F1 does NOT clear the promotion gate (not quarterly-stable on both pairs,
parameter- and timeframe-sensitive). It may be run in paper/replay only, never
as a promoted production factor without further validation (walk-forward +
feed robustness).

# Failure attribution:
- The trader.dev families were all authored on crypto perpetuals (BTC/ETH/SOL/
  AVAX/SEI/PEPE @ 15m-4h), which are 24/7 with no broker spread cost model done
  — their edge is a 2025-2026 perps beta artifact, not transferable FX alpha.
- On FX at honest retail costs, the same indicator logic read as noise after
  spreads: 6 families, all sub-benchmark, win rates 2-40% with mean-reversion
  lean against trend on the trailing legs.
- Consistent with TITAN's prior EXP-016..024: no transferable directional FX
  alpha found from externally-ported crypto strategies. Only local, internally
  verified effects (vol clustering EXP-017) have survived.

# Assets produced
research/run_traderdev_families.py      — 6-family FX port harness (real bid/ask)
research/validate_traderdev_f1.py        — quarterly/cost/long-short/regime checks
research/results/EXP-00025_traderdev_families.json — full per-run evidence
~/traderdev_strategies/*.json            — all 24 source Pine scripts (inventory)