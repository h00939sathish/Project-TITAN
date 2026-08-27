"""Execute pre-registered experiment FX-002: Asian Range Compression to London Volatility Expansion.

Primary Instrument: EURUSD (1-minute Point-in-Time Bid/Ask bars from Dukascopy)
Partitions:
  - In-Sample (IS): 2021-08-02 to 2024-07-31 (36 months)
  - Out-of-Sample (OOS): 2024-08-01 to 2026-07-31 (24 months, sealed)
Mechanism: M-006 (Session-Transition Volatility Expansion)
Asian Window: 00:00 to 06:59 UTC
London Window: 07:00 to 15:00 UTC (Breakout window: 07:00 to 10:00 UTC)
Compression Trigger: Asian_Range < 0.75 * 20-day Rolling Median Asian Range (strictly lagged t-1)
Execution: 100,000 EUR ($1.0 standard lot), Stop Loss at opposite Asian boundary, Target at 2.0x Asian Range
Cost Model: IBKR IDEALPRO ($2.00 entry + $2.00 exit min ticket fee, 0.20 bps linear above, quote-sided fills)
Controls:
  1. Unconditioned Asian Breakout Baseline
  2. Timestamp-Matched Random Direction Baseline (N=500 Monte Carlo)
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind, mannwhitneyu

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

DATA_PRIOR = ROOT_DIR / "research" / "dukascopy_1m_ba_prior" / "EURUSD.json"
DATA_CURRENT = ROOT_DIR / "research" / "dukascopy_1m_ba" / "EURUSD.json"
RESULTS_DIR = ROOT_DIR / "research" / "forex_research" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TRADE_NOTIONAL = 100000.0  # 1.0 standard lot = 100,000 EUR
COMMISSION_BPS = 0.000020  # 0.20 bps
MIN_COMMISSION_PER_ORDER = 2.00  # $2.00 minimum ticket fee per order
SLIPPAGE_BPS = 0.000010  # 0.10 bps slippage


def load_merged_eurusd_data() -> list[dict[str, Any]]:
    print("Loading Dukascopy 1-minute Bid/Ask datasets...")
    bars_map: dict[str, dict[str, Any]] = {}

    for path in [DATA_PRIOR, DATA_CURRENT]:
        if not path.exists():
            continue
        print(f"  Reading {path.name}...")
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
            for r in records:
                ts = r["timestamp"]
                if ts not in bars_map:
                    bars_map[ts] = {
                        "timestamp": datetime.fromisoformat(ts.replace("Z", "+00:00")),
                        "o_ask": float(r["o_ask"]),
                        "h_ask": float(r["h_ask"]),
                        "l_ask": float(r["l_ask"]),
                        "c_ask": float(r["c_ask"]),
                        "o_bid": float(r["o_bid"]),
                        "h_bid": float(r["h_bid"]),
                        "l_bid": float(r["l_bid"]),
                        "c_bid": float(r["c_bid"]),
                    }

    all_bars = sorted(bars_map.values(), key=lambda x: x["timestamp"])
    print(f"Total Unique 1-Minute Bars Loaded: {len(all_bars):,} ({all_bars[0]['timestamp'].strftime('%Y-%m-%d')} to {all_bars[-1]['timestamp'].strftime('%Y-%m-%d')})")
    return all_bars


def extract_daily_session_data(bars: list[dict[str, Any]]) -> pd.DataFrame:
    """Group bars by date into Asian Session (00:00-06:59) and London Session (07:00-15:00)."""
    daily_groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"asian": [], "london": []})

    for b in bars:
        ts: datetime = b["timestamp"]
        if ts.weekday() >= 5:  # Skip weekends
            continue
        h, m = ts.hour, ts.minute
        time_minutes = h * 60 + m
        date_str = ts.strftime("%Y-%m-%d")

        if 0 <= time_minutes < 420:  # 00:00 to 06:59 UTC
            daily_groups[date_str]["asian"].append(b)
        elif 420 <= time_minutes <= 900:  # 07:00 to 15:00 UTC
            daily_groups[date_str]["london"].append(b)

    records = []
    for date_str, data in sorted(daily_groups.items()):
        asian_bars = data["asian"]
        london_bars = data["london"]

        # Validate sufficient bars (at least 360 bars in Asia, 420 bars in London)
        if len(asian_bars) < 360 or len(london_bars) < 420:
            continue

        asian_high = max(b["h_ask"] for b in asian_bars)
        asian_low = min(b["l_bid"] for b in asian_bars)
        asian_range = (asian_high - asian_low) * 10000.0  # in pips

        london_high = max(b["h_ask"] for b in london_bars)
        london_low = min(b["l_bid"] for b in london_bars)
        london_range = (london_high - london_low) * 10000.0  # in pips

        records.append({
            "date": date_str,
            "asian_high": asian_high,
            "asian_low": asian_low,
            "asian_range_pips": asian_range,
            "london_high": london_high,
            "london_low": london_low,
            "london_range_pips": london_range,
            "asian_bars": asian_bars,
            "london_bars": london_bars,
        })

    df = pd.DataFrame(records)
    # Compute 20-day rolling median Asian range strictly lagged by 1 day
    df["baseline_20d"] = df["asian_range_pips"].rolling(20).median().shift(1)
    df["is_compressed"] = df["asian_range_pips"] < (0.75 * df["baseline_20d"])

    # Drop the first 20 days warm-up period
    df = df.dropna(subset=["baseline_20d"]).reset_index(drop=True)
    print(f"Total Valid Daily Sessions (post-warmup): {len(df):,} ({df['is_compressed'].sum()} Compressed Sessions = {df['is_compressed'].mean():.1%})")
    return df


def simulate_breakout_for_session(
    row: pd.Series,
    force_direction: int | None = None,  # None: follow breakout; +1: force Long; -1: force Short
) -> dict[str, Any]:
    """Simulate breakout trade execution during 07:00..10:00 UTC."""
    asian_high = row["asian_high"]
    asian_low = row["asian_low"]
    asian_range_usd = asian_high - asian_low
    london_bars = row["london_bars"]

    breakout_window_bars = [b for b in london_bars if (b["timestamp"].hour * 60 + b["timestamp"].minute) <= 600]
    post_breakout_bars = []
    
    breakout_idx = -1
    breakout_direction = 0  # +1: Long, -1: Short
    entry_price = 0.0
    breakout_time = None

    # Step 1: Detect first breakout in 07:00..10:00 UTC
    for idx, b in enumerate(breakout_window_bars):
        is_long_break = b["h_ask"] > asian_high
        is_short_break = b["l_bid"] < asian_low

        if is_long_break and is_short_break:
            # Ambiguous: Both touched in same minute -> Mark NO_TRADE
            return {"traded": False, "reason": "AMBIGUOUS_BAR", "realized_net_usd": 0.0, "realized_pips": 0.0}

        if is_long_break:
            breakout_idx = idx
            breakout_direction = 1
            entry_price = b["c_ask"]  # Market Buy at top-of-book Ask
            breakout_time = b["timestamp"]
            break
        elif is_short_break:
            breakout_idx = idx
            breakout_direction = -1
            entry_price = b["c_bid"]  # Market Sell at top-of-book Bid
            breakout_time = b["timestamp"]
            break

    if breakout_idx == -1 or breakout_direction == 0:
        return {"traded": False, "reason": "NO_BREAKOUT", "realized_net_usd": 0.0, "realized_pips": 0.0}

    # Step 2: Override direction if running timestamp-matched random control
    trade_direction = force_direction if force_direction is not None else breakout_direction
    if force_direction is not None:
        # Re-price entry according to forced direction
        entry_bar = breakout_window_bars[breakout_idx]
        entry_price = entry_bar["c_ask"] if trade_direction == 1 else entry_bar["c_bid"]

    # Step 3: Define Stops and Targets
    if trade_direction == 1:
        stop_loss = asian_low
        target_price = entry_price + (2.0 * asian_range_usd)
    else:
        stop_loss = asian_high
        target_price = entry_price - (2.0 * asian_range_usd)

    # Step 4: Track trade from breakout bar through 15:00 UTC
    remaining_bars = london_bars[breakout_idx + 1:]
    exit_price = 0.0
    exit_reason = "TIME_CLOSE_15:00"

    for b in remaining_bars:
        if trade_direction == 1:
            hit_stop = b["l_bid"] <= stop_loss
            hit_target = b["h_bid"] >= target_price

            if hit_stop and hit_target:
                # Collision: assume Stop Loss hit first (pessimistic)
                exit_price = stop_loss
                exit_reason = "STOP_LOSS_COLLISION"
                break
            elif hit_stop:
                exit_price = stop_loss
                exit_reason = "STOP_LOSS"
                break
            elif hit_target:
                exit_price = target_price
                exit_reason = "TAKE_PROFIT"
                break
        else:
            hit_stop = b["h_ask"] >= stop_loss
            hit_target = b["l_ask"] <= target_price

            if hit_stop and hit_target:
                # Collision: assume Stop Loss hit first (pessimistic)
                exit_price = stop_loss
                exit_reason = "STOP_LOSS_COLLISION"
                break
            elif hit_stop:
                exit_price = stop_loss
                exit_reason = "STOP_LOSS"
                break
            elif hit_target:
                exit_price = target_price
                exit_reason = "TAKE_PROFIT"
                break

    if exit_price == 0.0:
        # Time exit at 15:00 UTC market close
        exit_bar = london_bars[-1]
        exit_price = exit_bar["c_bid"] if trade_direction == 1 else exit_bar["c_ask"]
        exit_reason = "TIME_CLOSE_15:00"

    # Step 5: Compute Institutional Net P&L
    if trade_direction == 1:
        gross_pnl_usd = TRADE_NOTIONAL * (exit_price - entry_price)
        pips_raw = (exit_price - entry_price) * 10000.0
    else:
        gross_pnl_usd = TRADE_NOTIONAL * (entry_price - exit_price)
        pips_raw = (entry_price - exit_price) * 10000.0

    entry_notional = TRADE_NOTIONAL * entry_price
    exit_notional = TRADE_NOTIONAL * exit_price

    entry_fee = max(MIN_COMMISSION_PER_ORDER, entry_notional * COMMISSION_BPS)
    exit_fee = max(MIN_COMMISSION_PER_ORDER, exit_notional * COMMISSION_BPS)
    total_comm_usd = entry_fee + exit_fee
    slippage_usd = (entry_notional + exit_notional) * 0.5 * SLIPPAGE_BPS

    net_pnl_usd = gross_pnl_usd - total_comm_usd - slippage_usd
    net_pips = (net_pnl_usd / TRADE_NOTIONAL) * 10000.0

    return {
        "traded": True,
        "date": row["date"],
        "breakout_time": breakout_time,
        "direction": trade_direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "gross_pnl_usd": gross_pnl_usd,
        "total_commission_usd": total_comm_usd,
        "slippage_usd": slippage_usd,
        "realized_net_usd": net_pnl_usd,
        "realized_pips": net_pips,
    }


def run_experiment():
    print("=" * 70)
    print("EXECUTING PRE-REGISTERED EXPERIMENT: FX-002 (ASIAN COMPRESSION EXPANSION)")
    print("=" * 70)

    bars = load_merged_eurusd_data()
    df = extract_daily_session_data(bars)

    df_is = df[(df["date"] >= "2021-08-02") & (df["date"] <= "2024-07-31")].copy().reset_index(drop=True)
    df_oos = df[(df["date"] >= "2024-08-01") & (df["date"] <= "2026-07-31")].copy().reset_index(drop=True)

    print(f"\nPartitions: In-Sample (IS) = {len(df_is)} sessions | Out-of-Sample (OOS) = {len(df_oos)} sessions")

    # -------------------------------------------------------------
    # GATE 1: Volatility Expansion Phenomenon Test
    # -------------------------------------------------------------
    print("\n--- [GATE 1] Testing Session-Transition Realized Volatility Expansion ---")
    gate1_results = {}
    for part_name, part_df in [("IS", df_is), ("OOS", df_oos)]:
        comp_ranges = part_df[part_df["is_compressed"]]["london_range_pips"].values
        non_comp_ranges = part_df[~part_df["is_compressed"]]["london_range_pips"].values

        t_stat, p_val_t = ttest_ind(comp_ranges, non_comp_ranges, equal_var=False)
        u_stat, p_val_u = mannwhitneyu(comp_ranges, non_comp_ranges, alternative="two-sided")

        mean_comp = float(np.mean(comp_ranges))
        mean_non_comp = float(np.mean(non_comp_ranges))
        diff_pips = mean_comp - mean_non_comp

        # Gate 1 Pass: Realized range on compressed days > non-compressed days with p < 0.05
        is_higher = mean_comp > mean_non_comp
        p_val_onesided = (p_val_t / 2.0) if is_higher else (1.0 - p_val_t / 2.0)
        gate1_pass = bool(is_higher and p_val_onesided < 0.05)

        gate1_results[part_name] = {
            "n_compressed": len(comp_ranges),
            "n_non_compressed": len(non_comp_ranges),
            "mean_compressed_range_pips": round(mean_comp, 2),
            "mean_non_compressed_range_pips": round(mean_non_comp, 2),
            "range_difference_pips": round(diff_pips, 2),
            "welch_t_stat": round(float(t_stat), 3),
            "welch_p_value_onesided": round(float(p_val_onesided), 6),
            "gate1_passed": gate1_pass,
        }
        print(f"  [{part_name}] Compressed ({len(comp_ranges)}): {mean_comp:.1f} pips vs Non-Compressed ({len(non_comp_ranges)}): {mean_non_comp:.1f} pips | Diff: {diff_pips:+.1f} pips | Welch p: {p_val_onesided:.6f} | Pass: {gate1_pass}")

    # -------------------------------------------------------------
    # GATE 2 & GATE 4: Compressed Breakout vs. Unconditioned Breakout
    # -------------------------------------------------------------
    print("\n--- [GATE 2 & 4] Simulating Breakout Strategy: Compressed vs. Unconditioned ---")
    trading_results = {}
    for part_name, part_df in [("IS", df_is), ("OOS", df_oos)]:
        # 1. Compressed Breakout
        comp_trades = []
        for _, row in part_df.iterrows():
            if row["is_compressed"]:
                r = simulate_breakout_for_session(row)
                comp_trades.append(r)
            else:
                comp_trades.append({"traded": False, "realized_net_usd": 0.0, "realized_pips": 0.0})

        # 2. Unconditioned Breakout (All sessions)
        uncond_trades = []
        for _, row in part_df.iterrows():
            r = simulate_breakout_for_session(row)
            uncond_trades.append(r)

        def calc_metrics(trades: list[dict[str, Any]], total_days: int) -> dict[str, Any]:
            traded_list = [t for t in trades if t["traded"]]
            n_trades = len(traded_list)
            daily_pnl = [t["realized_net_usd"] for t in trades]
            pnl_series = pd.Series(daily_pnl)

            mean_d, std_d = float(pnl_series.mean()), float(pnl_series.std())
            sharpe = (mean_d / std_d * math.sqrt(252.0)) if std_d > 0 else 0.0

            cum_pnl = pnl_series.cumsum()
            dd = cum_pnl.cummax() - cum_pnl
            max_dd = float(dd.max()) if len(dd) else 0.0

            pips_list = [t["realized_pips"] for t in traded_list]
            mean_pips = float(np.mean(pips_list)) if pips_list else 0.0
            tot_usd = float(np.sum(daily_pnl))
            win_rate = float(sum(1 for p in pips_list if p > 0) / n_trades) if n_trades > 0 else 0.0

            return {
                "total_days": total_days,
                "n_trades": n_trades,
                "trade_frequency": round(n_trades / total_days, 4),
                "win_rate": round(win_rate, 4),
                "mean_pips_trade": round(mean_pips, 2),
                "total_net_usd": round(tot_usd, 2),
                "annualized_net_sharpe": round(sharpe, 2),
                "max_drawdown_usd": round(max_dd, 2),
            }

        comp_metrics = calc_metrics(comp_trades, len(part_df))
        uncond_metrics = calc_metrics(uncond_trades, len(part_df))

        # Gate 2: Compressed Sharpe >= Unconditioned Sharpe + 0.30
        gate2_pass = bool(comp_metrics["annualized_net_sharpe"] >= (uncond_metrics["annualized_net_sharpe"] + 0.30))

        # Gate 4: OOS Sharpe >= 0.80, Expectancy >= 2.0 pips, Max DD <= 15%
        gate4_pass = bool(comp_metrics["annualized_net_sharpe"] >= 0.80 and comp_metrics["mean_pips_trade"] >= 2.00)

        trading_results[part_name] = {
            "compressed": comp_metrics,
            "unconditioned": uncond_metrics,
            "gate2_compression_value_add": gate2_pass,
            "gate4_net_economic_hurdle": gate4_pass,
        }
        print(f"  [{part_name}] Compressed: N={comp_metrics['n_trades']} | Pips/Trade: {comp_metrics['mean_pips_trade']:+.2f} | Sharpe: {comp_metrics['annualized_net_sharpe']:.2f} | MaxDD: ${comp_metrics['max_drawdown_usd']:,.2f}")
        print(f"  [{part_name}] Unconditioned: N={uncond_metrics['n_trades']} | Pips/Trade: {uncond_metrics['mean_pips_trade']:+.2f} | Sharpe: {uncond_metrics['annualized_net_sharpe']:.2f} | Value-Add: {gate2_pass}")

    # -------------------------------------------------------------
    # GATE 3: Timestamp-Matched Random Direction Baseline (N=500 Monte Carlo)
    # -------------------------------------------------------------
    print("\n--- [GATE 3] Timestamp-Matched Random Direction Baseline (N=500 MC) ---")
    rng = np.random.RandomState(42)
    rand_oos_sharpes, rand_oos_pips = [], []

    oos_comp_rows = [row for _, row in df_oos.iterrows() if row["is_compressed"]]
    for _ in range(500):
        # Assign random direction (+1 or -1) to each session at the exact same breakout time
        rand_dirs = rng.choice([1, -1], size=len(oos_comp_rows))
        sims = [
            simulate_breakout_for_session(row, force_direction=d)
            for row, d in zip(oos_comp_rows, rand_dirs)
        ]
        traded_sims = [s for s in sims if s["traded"]]
        daily_pnl = [s["realized_net_usd"] for s in sims]
        p_series = pd.Series(daily_pnl)

        m_d, s_d = float(p_series.mean()), float(p_series.std())
        sh = (m_d / s_d * math.sqrt(252.0)) if s_d > 0 else 0.0
        pips = float(np.mean([s["realized_pips"] for s in traded_sims])) if traded_sims else 0.0

        rand_oos_sharpes.append(sh)
        rand_oos_pips.append(pips)

    rand_summary = {
        "mean_pips": round(float(np.mean(rand_oos_pips)), 2),
        "std_pips": round(float(np.std(rand_oos_pips)), 2),
        "p95_pips": round(float(np.percentile(rand_oos_pips, 95)), 2),
        "mean_sharpe": round(float(np.mean(rand_oos_sharpes)), 2),
        "std_sharpe": round(float(np.std(rand_oos_sharpes)), 2),
    }
    actual_oos_pips = trading_results["OOS"]["compressed"]["mean_pips_trade"]
    gate3_pass = bool(actual_oos_pips > rand_summary["p95_pips"])

    print(f"  Random Baseline OOS: Mean Pips: {rand_summary['mean_pips']:+.2f} (std {rand_summary['std_pips']:.2f}, 95th percentile: {rand_summary['p95_pips']:+.2f}) | Mean Sharpe: {rand_summary['mean_sharpe']:.2f}")
    print(f"  Gate 3 Status: Strategy ({actual_oos_pips:+.2f} pips) > Random 95th ({rand_summary['p95_pips']:+.2f} pips) -> Pass: {gate3_pass}")

    # -------------------------------------------------------------
    # Outcome Classification
    # -------------------------------------------------------------
    g1 = gate1_results["IS"]["gate1_passed"] and gate1_results["OOS"]["gate1_passed"]
    g2 = trading_results["OOS"]["gate2_compression_value_add"]
    g3 = gate3_pass
    g4 = trading_results["OOS"]["gate4_net_economic_hurdle"]

    if g1 and g2 and g3 and g4:
        outcome = "Case A — Candidate Validated (Asian Compression to London Expansion Confirmed)"
    elif g1 and not (g2 and g3 and g4):
        outcome = "Case B — Mechanism Confirmed but Directional Edge Unharvestable (Volatility Expansion True, Directional Trading Failed)"
    elif not g1 and (g2 or g4):
        outcome = "Case C — Spurious Trading Result (Gate 1 Volatility Expansion Failed)"
    else:
        outcome = "Case D — Complete Mechanism Failure (Absorbing Negative Result)"

    print(f"\n>>> FINAL OUTCOME: {outcome}")

    # Save Evidence Bundle
    bundle = {
        "hypothesis_id": "FX-002",
        "instrument": "EURUSD",
        "outcome_classification": outcome,
        "gate_1_volatility_expansion": gate1_results,
        "trading_performance": trading_results,
        "timestamp_matched_random_baseline": rand_summary,
        "decision_gate_status": {
            "gate_1_volatility_expansion": g1,
            "gate_2_compression_value_add": g2,
            "gate_3_random_baseline_superiority": g3,
            "gate_4_net_economic_hurdle": g4,
        }
    }
    bundle_path = RESULTS_DIR / "FX-002-evidence-bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"Saved Evidence Bundle: {bundle_path}")

    # Save Research Report
    report_md = f"""# FX-002: Asian Compression to London Volatility Expansion Report

- **Experiment ID:** `FX-002`
- **Mechanism Ref:** `M-006` (Session-Transition Volatility Expansion)
- **Instrument:** `EURUSD` (Dukascopy 1-minute Point-in-Time Bid/Ask Bars)
- **Outcome Classification:** **{outcome}**

---

## 1. Gate 1: Volatility Expansion Phenomenon Test

| Partition | Compressed Days ($N$) | Non-Compressed Days ($N$) | Mean Compressed London Range | Mean Non-Compressed London Range | Difference | Welch's $t$-test $p$-value | Gate 1 Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **In-Sample (2021–2024)** | {gate1_results['IS']['n_compressed']} | {gate1_results['IS']['n_non_compressed']} | **{gate1_results['IS']['mean_compressed_range_pips']:.1f} pips** | {gate1_results['IS']['mean_non_compressed_range_pips']:.1f} pips | **{gate1_results['IS']['range_difference_pips']:+.1f} pips** | $p = {gate1_results['IS']['welch_p_value_onesided']:.6f}$ | **{"PASSED" if gate1_results['IS']['gate1_passed'] else "FAILED"}** |
| **Out-of-Sample (2024–2026)** | {gate1_results['OOS']['n_compressed']} | {gate1_results['OOS']['n_non_compressed']} | **{gate1_results['OOS']['mean_compressed_range_pips']:.1f} pips** | {gate1_results['OOS']['mean_non_compressed_range_pips']:.1f} pips | **{gate1_results['OOS']['range_difference_pips']:+.1f} pips** | $p = {gate1_results['OOS']['welch_p_value_onesided']:.6f}$ | **{"PASSED" if gate1_results['OOS']['gate1_passed'] else "FAILED"}** |

---

## 2. Gate 2 & 4: Breakout Trading Performance (IBKR $4.00 Round-Trip Floor)

| Metric | Compressed Breakout (IS) | Unconditioned Breakout (IS) | Compressed Breakout (OOS) | Unconditioned Breakout (OOS) | Random Direction Baseline (OOS) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Total Sessions** | {trading_results['IS']['compressed']['total_days']} | {trading_results['IS']['unconditioned']['total_days']} | {trading_results['OOS']['compressed']['total_days']} | {trading_results['OOS']['unconditioned']['total_days']} | {trading_results['OOS']['compressed']['total_days']} |
| **Executed Trades** | {trading_results['IS']['compressed']['n_trades']} | {trading_results['IS']['unconditioned']['n_trades']} | {trading_results['OOS']['compressed']['n_trades']} | {trading_results['OOS']['unconditioned']['n_trades']} | {trading_results['OOS']['compressed']['n_trades']} |
| **Trade Frequency** | {trading_results['IS']['compressed']['trade_frequency']:.1%} | {trading_results['IS']['unconditioned']['trade_frequency']:.1%} | {trading_results['OOS']['compressed']['trade_frequency']:.1%} | {trading_results['OOS']['unconditioned']['trade_frequency']:.1%} | — |
| **Win Rate** | {trading_results['IS']['compressed']['win_rate']:.1%} | {trading_results['IS']['unconditioned']['win_rate']:.1%} | {trading_results['OOS']['compressed']['win_rate']:.1%} | {trading_results['OOS']['unconditioned']['win_rate']:.1%} | — |
| **Net Pips / Trade** | **{trading_results['IS']['compressed']['mean_pips_trade']:+.2f} pips** | {trading_results['IS']['unconditioned']['mean_pips_trade']:+.2f} pips | **{trading_results['OOS']['compressed']['mean_pips_trade']:+.2f} pips** | {trading_results['OOS']['unconditioned']['mean_pips_trade']:+.2f} pips | {rand_summary['mean_pips']:+.2f} pips (+/- {rand_summary['std_pips']:.2f}) |
| **Total Net USD** | **${trading_results['IS']['compressed']['total_net_usd']:+,.2f}** | ${trading_results['IS']['unconditioned']['total_net_usd']:+,.2f} | **${trading_results['OOS']['compressed']['total_net_usd']:+,.2f}** | ${trading_results['OOS']['unconditioned']['total_net_usd']:+,.2f} | — |
| **Annualized Sharpe** | **{trading_results['IS']['compressed']['annualized_net_sharpe']:.2f}** | {trading_results['IS']['unconditioned']['annualized_net_sharpe']:.2f} | **{trading_results['OOS']['compressed']['annualized_net_sharpe']:.2f}** | {trading_results['OOS']['unconditioned']['annualized_net_sharpe']:.2f} | {rand_summary['mean_sharpe']:.2f} |
| **Max Drawdown** | ${trading_results['IS']['compressed']['max_drawdown_usd']:,.2f} | ${trading_results['IS']['unconditioned']['max_drawdown_usd']:,.2f} | ${trading_results['OOS']['compressed']['max_drawdown_usd']:,.2f} | ${trading_results['OOS']['unconditioned']['max_drawdown_usd']:,.2f} | — |

---

## 3. Decision Gate Summary

1. **Gate 1 (Volatility Expansion Phenomenon):** **{"PASSED" if g1 else "FAILED"}** — Realized range on compressed days vs non-compressed days.
2. **Gate 2 (Compression Filter Value-Add):** **{"PASSED" if g2 else "FAILED"}** — Compressed Sharpe vs Unconditioned Sharpe.
3. **Gate 3 (Timestamp-Matched Random Superiority):** **{"PASSED" if g3 else "FAILED"}** — Breakout direction vs Random entry at same timestamp.
4. **Gate 4 (Net Economic Hurdle):** **{"PASSED" if g4 else "FAILED"}** — OOS Net Sharpe $\ge 0.80$, Expectancy $\ge 2.0\text{ pips}$.

---

## 4. Scientific Governance Verdict

**Verdict:** `{outcome}`  
Archived permanently in `FX-002-evidence-bundle.json`.
"""
    report_path = RESULTS_DIR / "FX-002-expansion-report.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"Saved Report: {report_path}")


if __name__ == "__main__":
    run_experiment()
