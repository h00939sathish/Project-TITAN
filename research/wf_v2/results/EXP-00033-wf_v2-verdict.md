# WF-v2 verdict — EXP-00033: FAIL

- Question: Does the registered traderdev-ema9-vwap candidate keep a positive, cost-surviving edge on data it was never tuned on? EXP-00025 found the F1 family net positive at 4h on EURUSD + GBPUSD (+408.3 pips pooled) but only over the 12 months the port was tuned on, and the promotion gate recorded walk_forward as UNMET for that reason. The 2D surface has no compact plateau and the two pairs favour different corners. WF-v2 runs the frozen parameters over 2022-08..2025-07.
- Protocol: research/protocol_WF_v2_PRE_FROZEN.md (sha256 a524427b2e8b)
- Strategy: `traderdev-ema9-vwap` {"atr_period": 14, "ema_period": 9, "trail_mult": 2.0, "vwap_period": 120}, long_short
- Window: 2022-08..2025-07, 240m bars, dataset `dukascopy_1m_ba_prior`
- Evidence record: research/evidence/EXP-00033.json
- Mechanism: none registered
- Bundle: EXP-00033-wf_v2-bundle.json (generated 2026-10-29T06:49:46Z)

## EURUSD — FAIL

Data: research/dukascopy_1m_ba_prior/EURUSD.json (sha256 48f719fc2dda), 4818 bars, missing-tick rate 2.03%. 7/30 test windows passed.

| Criterion | Value | Threshold | Result |
|---|---|---|---|
| window_pass_rate | 0.2333 | >= 0.7 | FAIL |
| mean_sharpe | 0.0376 | > 0 | PASS |
| mean_ic | -0.0052 | > 0 | FAIL |
| annual_turnover | 97.8656 | <= 60.0 | FAIL |
| net_oos_return | 0.0306 | > 0 | PASS |

Execution check (ReplayEngine, non-gating): {"bars_processed": 4818, "rejected_intents": 0, "trades": 149}

## GBPUSD — FAIL

Data: research/dukascopy_1m_ba_prior/GBPUSD.json (sha256 396a611bad6c), 4842 bars, missing-tick rate 1.41%. 4/30 test windows passed.

| Criterion | Value | Threshold | Result |
|---|---|---|---|
| window_pass_rate | 0.1333 | >= 0.7 | FAIL |
| mean_sharpe | -1.0382 | > 0 | FAIL |
| mean_ic | -0.0325 | > 0 | FAIL |
| annual_turnover | 91.8396 | <= 60.0 | FAIL |
| net_oos_return | -0.0554 | > 0 | FAIL |

Execution check (ReplayEngine, non-gating): {"bars_processed": 4842, "rejected_intents": 0, "trades": 147}

## Decision (protocol section 7)

FAIL: no promotion. Record a sealed negative in research/neg_results/ and do not loop on this strategy and data.

## Interpretation applied

- **folds**: Test month k for every k >= 6; train = months [0, k). Parameters are frozen, so train is indicator warm-up only; signals are computed causally in one pass, which equals re-running on each expanding train.
- **window_pass**: Sharpe > 0.0 and Spearman IC(position at bar close, next-bar return) > 0.02; an undefined Sharpe or IC fails the window.
- **aggregate_pass**: Window pass rate >= 0.70, mean Sharpe > 0 and mean IC > 0 (undefined values count as 0).
- **turnover**: Sum of |position change| x leverage over OOS bars, annualized (one-way traded notional / NAV). Ratified in ADR-036.
- **costs**: Screen engine: 0.8e-4 of price per round trip, charged as half per unit of leveraged notional traded on each bar where the position changes (a flip pays a full round trip), and that bar earns no return; 10% vol target at an assumed 8% vol. Ratified in ADR-036.
- **returns**: Shorts earn the negative of the bar return (fixed in the screen as well). Ratified in ADR-036.
- **prices**: Bid OHLC resampled from 1m bars; the screen engine has no separate spread term. Ratified in ADR-036.
- **missing_ticks**: Expected minutes are all minutes except Fri 22:00 to Sun 22:00 UTC. DST and holidays are not modelled, which overstates the missing rate.
- **positions**: Position after each bar close. A strategy that reports its own held position (signal_fn.position()) is read directly, so BUY/SELL used as exits stay exits; otherwise BUY = long and SELL = short (long_short) or flat (long_flat). long_flat floors a reported short at flat. Stops act at bar-close granularity. ADR-038.
- **regime_pivot**: At least one CENTRAL_BANK_PIVOTS date inside the window.
- **multi_instrument**: Every instrument must pass on its own.
- **verdict**: PASS only if every instrument passes every criterion; anything else is FAIL.
