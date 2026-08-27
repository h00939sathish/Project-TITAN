"""Execute the pre-registered FX-001 Passive MAE Excursion Reversal experiment.

Primary Instrument: EURUSD (1-minute Point-in-Time Bid/Ask bars from Dukascopy)
IS: 2021-08-02 to 2024-07-31 (36 months)
OOS: 2024-08-01 to 2026-07-31 (24 months)
Mechanism: M-003 (Structural Excursion Asymmetry)
Session: London Opening Session (07:00 to 15:00 UTC)
Opening Range: 07:00 to 07:30 UTC (30m)
Boundary Formula: Open_07:00 -/+ 1.0 * OR_Range (Post-Only Limit, evaluated at 07:30 UTC)
Trade Sizing: 100,000 base units ($1.0 standard lot)
Cost Model: IBKR IDEALPRO ($2.00 entry + $2.00 exit min fee floor, 0.20 bps linear above, quote-sided fills)
Control: Exposure-matched random boundary in [0.5 * OR, 1.5 * OR] (N=500 Monte Carlo)
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
from scipy.stats import spearmanr, ttest_1samp

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

DATA_PRIOR = ROOT_DIR / "research" / "dukascopy_1m_ba_prior" / "EURUSD.json"
DATA_CURRENT = ROOT_DIR / "research" / "dukascopy_1m_ba" / "EURUSD.json"
RESULTS_DIR = ROOT_DIR / "research" / "forex_research" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TRADE_NOTIONAL = 100000.0  # 1.0 standard lot = 100,000 EUR
COMMISSION_BPS = 0.000020  # 0.20 bps = 0.000020
MIN_COMMISSION_PER_ORDER = 2.00  # $2.00 minimum ticket fee per order
SLIPPAGE_BPS = 0.000010  # 0.10 bps slippage on market exit


def wilcoxon_signed_rank(diffs: list[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test for paired data (H0: median(diffs) <= 0 vs H1: median(diffs) > 0)."""
    nonzero = [(abs(d), d) for d in diffs if abs(d) > 1e-8]
    n = len(nonzero)
    if n < 10:
        return 0.0, 1.0

    nonzero.sort(key=lambda x: x[0])
    w_plus = 0.0
    for rank, (abs_val, orig_val) in enumerate(nonzero, start=1):
        if orig_val > 0:
            w_plus += rank

    mean_w = n * (n + 1) / 4.0
    std_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    z = (w_plus - mean_w) / std_w
    # One-sided p-value for W+ > mean_w
    p_val = 0.5 * math.erfc(z / math.sqrt(2))
    return float(w_plus), float(p_val)


def load_merged_eurusd_data() -> list[dict[str, Any]]:
    print("Loading Dukascopy 1-minute Bid/Ask datasets...")
    bars_map: dict[str, dict[str, Any]] = {}

    for path in [DATA_PRIOR, DATA_CURRENT]:
        if not path.exists():
            print(f"Warning: {path} does not exist.")
            continue
        print(f"  Reading {path.name}...")
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
            for r in records:
                ts = r["timestamp"]
                # Deduplicate and standardize
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
                        "o_mid": (float(r["o_ask"]) + float(r["o_bid"])) / 2.0,
                        "h_mid": (float(r["h_ask"]) + float(r["h_bid"])) / 2.0,
                        "l_mid": (float(r["l_ask"]) + float(r["l_bid"])) / 2.0,
                        "c_mid": (float(r["c_ask"]) + float(r["c_bid"])) / 2.0,
                    }

    all_bars = sorted(bars_map.values(), key=lambda x: x["timestamp"])
    print(f"Total Unique 1-Minute Bars Loaded: {len(all_bars):,} ({all_bars[0]['timestamp'].strftime('%Y-%m-%d')} to {all_bars[-1]['timestamp'].strftime('%Y-%m-%d')})")
    return all_bars


def group_london_sessions(bars: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Group bars by date into Opening Range (07:00-07:30) and Post-OR (07:31-15:00)."""
    sessions: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"or_bars": [], "post_or_bars": []})

    for b in bars:
        ts: datetime = b["timestamp"]
        # Filter Monday through Friday
        if ts.weekday() >= 5:
            continue
        h, m = ts.hour, ts.minute
        time_minutes = h * 60 + m
        date_str = ts.strftime("%Y-%m-%d")

        # London Open: 07:00 (420 min) to 15:00 (900 min) UTC
        if 420 <= time_minutes <= 450:
            sessions[date_str]["or_bars"].append(b)
        elif 451 <= time_minutes <= 900:
            sessions[date_str]["post_or_bars"].append(b)

    # Filter complete sessions (at least 25 bars in OR and at least 400 bars post-OR)
    valid_sessions = {
        k: v for k, v in sessions.items()
        if len(v["or_bars"]) >= 25 and len(v["post_or_bars"]) >= 400
    }
    print(f"Total Valid London Opening Sessions: {len(valid_sessions):,}")
    return valid_sessions


def evaluate_session_q1_mae_mfe(session: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    """Compute exact Q1 MAE/MFE relative to Close_07:30 UTC."""
    or_bars = session["or_bars"]
    post_bars = session["post_or_bars"]

    or_open = or_bars[0]["o_mid"]
    or_close = or_bars[-1]["c_mid"]
    or_return = or_close - or_open
    or_direction = 1 if or_return > 0 else (-1 if or_return < 0 else 0)

    if or_direction == 0:
        return None

    # Calculate post-OR MAE and MFE relative to Close_07:30
    if or_direction > 0:
        # Long breakout: adverse is downward movement in Bid; favorable is upward movement in Ask
        min_bid = min(b["l_bid"] for b in post_bars)
        max_ask = max(b["h_ask"] for b in post_bars)
        mae = max(0.0, or_close - min_bid)
        mfe = max(0.0, max_ask - or_close)
    else:
        # Short breakout: adverse is upward movement in Ask; favorable is downward movement in Bid
        max_ask = max(b["h_ask"] for b in post_bars)
        min_bid = min(b["l_bid"] for b in post_bars)
        mae = max(0.0, max_ask - or_close)
        mfe = max(0.0, or_close - min_bid)

    mae_pips = mae * 10000.0
    mfe_pips = mfe * 10000.0

    return {
        "direction": or_direction,
        "mae_pips": mae_pips,
        "mfe_pips": mfe_pips,
        "diff_pips": mae_pips - mfe_pips,
        "ratio": (mae_pips / mfe_pips) if mfe_pips > 0.1 else 1.0,
    }


def simulate_passive_limit_execution(
    session: dict[str, list[dict[str, Any]]],
    boundary_multiplier: float = 1.0,
) -> dict[str, Any] | None:
    """Simulate post-only limit execution at Open_07:00 -/+ multiplier * OR_Range."""
    or_bars = session["or_bars"]
    post_bars = session["post_or_bars"]

    or_open = or_bars[0]["o_mid"]
    or_close = or_bars[-1]["c_mid"]
    or_high = max(b["h_ask"] for b in or_bars)
    or_low = min(b["l_bid"] for b in or_bars)
    or_range = or_high - or_low

    or_return = or_close - or_open
    direction = 1 if or_return > 0 else (-1 if or_return < 0 else 0)
    if direction == 0 or or_range <= 0.0001:
        return None

    # Determine Limit Price at 07:30 UTC
    if direction > 0:
        # Initial Long breakout -> Place Passive Buy Limit below 07:00 open
        limit_price = or_open - boundary_multiplier * or_range
        is_long = True
    else:
        # Initial Short breakout -> Place Passive Sell Limit above 07:00 open
        limit_price = or_open + boundary_multiplier * or_range
        is_long = False

    # Evaluate bar-by-bar fills from 07:31 to 14:59 UTC
    fill_bar_idx = -1
    for idx, bar in enumerate(post_bars[:-1]):
        if is_long:
            # Buy Limit fills if Ask drops to or below limit_price
            if bar["l_ask"] <= limit_price:
                fill_bar_idx = idx
                break
        else:
            # Sell Limit fills if Bid rises to or above limit_price
            if bar["h_bid"] >= limit_price:
                fill_bar_idx = idx
                break

    session_exit_bar = post_bars[-1]
    exit_bid = session_exit_bar["c_bid"]
    exit_ask = session_exit_bar["c_ask"]

    # Market Taker Opportunity baseline (if entered at 07:30 close)
    if is_long:
        opp_exit = exit_bid
        opp_entry = or_close
        opp_pnl = TRADE_NOTIONAL * (opp_exit - opp_entry)
    else:
        opp_exit = exit_ask
        opp_entry = or_close
        opp_pnl = TRADE_NOTIONAL * (opp_entry - opp_exit)

    if fill_bar_idx == -1:
        # Unfilled: order canceled at 15:00 UTC
        return {
            "filled": False,
            "realized_net_pnl_usd": 0.0,
            "realized_pips": 0.0,
            "opportunity_pnl_usd": opp_pnl,
            "time_to_fill_min": None,
            "post_fill_mae_pips": 0.0,
            "post_fill_mfe_pips": 0.0,
            "adverse_runaway": False,
        }

    # Order Filled!
    fill_bar = post_bars[fill_bar_idx]
    fill_time_min = fill_bar_idx + 1  # minutes elapsed since 07:30
    remaining_bars = post_bars[fill_bar_idx:]

    # Post-fill MAE and MFE
    if is_long:
        post_min_bid = min(b["l_bid"] for b in remaining_bars)
        post_max_ask = max(b["h_ask"] for b in remaining_bars)
        post_mae = max(0.0, limit_price - post_min_bid)
        post_mfe = max(0.0, post_max_ask - limit_price)
        gross_pnl_usd = TRADE_NOTIONAL * (exit_bid - limit_price)
        pips_raw = (exit_bid - limit_price) * 10000.0
    else:
        post_max_ask = max(b["h_ask"] for b in remaining_bars)
        post_min_bid = min(b["l_bid"] for b in remaining_bars)
        post_mae = max(0.0, post_max_ask - limit_price)
        post_mfe = max(0.0, limit_price - post_min_bid)
        gross_pnl_usd = TRADE_NOTIONAL * (limit_price - exit_ask)
        pips_raw = (limit_price - exit_ask) * 10000.0

    # Institutional IBKR Cost Accounting
    entry_notional_usd = TRADE_NOTIONAL * limit_price
    exit_price = exit_bid if is_long else exit_ask
    exit_notional_usd = TRADE_NOTIONAL * exit_price

    entry_fee = max(MIN_COMMISSION_PER_ORDER, entry_notional_usd * COMMISSION_BPS)
    exit_fee = max(MIN_COMMISSION_PER_ORDER, exit_notional_usd * COMMISSION_BPS)
    total_commission_usd = entry_fee + exit_fee
    slippage_usd = exit_notional_usd * SLIPPAGE_BPS

    net_pnl_usd = gross_pnl_usd - total_commission_usd - slippage_usd
    net_pips = (net_pnl_usd / TRADE_NOTIONAL) * 10000.0

    post_mae_pips = post_mae * 10000.0
    post_mfe_pips = post_mfe * 10000.0
    or_range_pips = or_range * 10000.0
    adverse_runaway = post_mae_pips > (2.0 * or_range_pips)

    return {
        "filled": True,
        "realized_net_pnl_usd": net_pnl_usd,
        "realized_pips": net_pips,
        "gross_pnl_usd": gross_pnl_usd,
        "commission_usd": total_commission_usd,
        "slippage_usd": slippage_usd,
        "opportunity_pnl_usd": opp_pnl,
        "time_to_fill_min": fill_time_min,
        "post_fill_mae_pips": post_mae_pips,
        "post_fill_mfe_pips": post_mfe_pips,
        "adverse_runaway": adverse_runaway,
    }


def run_experiment():
    print("=" * 70)
    print("EXECUTING PRE-REGISTERED EXPERIMENT: FX-001 (PASSIVE MAE REVERSAL)")
    print("=" * 70)

    bars = load_merged_eurusd_data()
    sessions = group_london_sessions(bars)

    is_sessions = {k: v for k, v in sessions.items() if "2021-08-02" <= k <= "2024-07-31"}
    oos_sessions = {k: v for k, v in sessions.items() if "2024-08-01" <= k <= "2026-07-31"}

    print(f"\nPartitions: In-Sample (IS) = {len(is_sessions)} sessions, Out-of-Sample (OOS) = {len(oos_sessions)} sessions")

    # -------------------------------------------------------------
    # Q1: Descriptive Replication (MAE > MFE Analysis)
    # -------------------------------------------------------------
    print("\n--- [Q1] Descriptive Replication: Testing MAE > MFE Structural Asymmetry ---")
    q1_results: dict[str, Any] = {}
    for part_name, part_sess in [("IS", is_sessions), ("OOS", oos_sessions)]:
        mae_list, mfe_list, diff_list = [], [], []
        for s in part_sess.values():
            res = evaluate_session_q1_mae_mfe(s)
            if res:
                mae_list.append(res["mae_pips"])
                mfe_list.append(res["mfe_pips"])
                diff_list.append(res["diff_pips"])

        w_stat, p_val = wilcoxon_signed_rank(diff_list)
        mean_mae = float(np.mean(mae_list))
        mean_mfe = float(np.mean(mfe_list))
        ratio = mean_mae / mean_mfe if mean_mfe > 0 else 0.0
        frac_gt = float(sum(1 for d in diff_list if d > 0) / len(diff_list))

        q1_results[part_name] = {
            "n_sessions": len(diff_list),
            "mean_mae_pips": round(mean_mae, 2),
            "mean_mfe_pips": round(mean_mfe, 2),
            "mae_mfe_ratio": round(ratio, 2),
            "fraction_mae_gt_mfe": round(frac_gt, 4),
            "wilcoxon_w": round(w_stat, 2),
            "wilcoxon_p_value": round(p_val, 6),
            "q1_passed": bool(p_val < 0.05 and ratio >= 1.20),
        }
        print(f"  [{part_name}] N={len(diff_list)} | Mean MAE: {mean_mae:.2f} pips vs MFE: {mean_mfe:.2f} pips | Ratio: {ratio:.2f}x | Wilcoxon p-value: {p_val:.6f} | Pass: {q1_results[part_name]['q1_passed']}")

    # -------------------------------------------------------------
    # Q2 / Q3 / Q4: Simulated Limit Order Execution (1.0x OR)
    # -------------------------------------------------------------
    print("\n--- [Q2-Q4] Passive Post-Only Limit Execution at Fixed 1.0x OR Boundary ---")
    exec_results: dict[str, Any] = {}
    for part_name, part_sess in [("IS", is_sessions), ("OOS", oos_sessions)]:
        sim_records = []
        for s in part_sess.values():
            r = simulate_passive_limit_execution(s, boundary_multiplier=1.0)
            if r is not None:
                sim_records.append(r)

        n_total = len(sim_records)
        filled_records = [r for r in sim_records if r["filled"]]
        n_filled = len(filled_records)
        fill_rate = n_filled / n_total if n_total > 0 else 0.0

        daily_net_pnl = [r["realized_net_pnl_usd"] for r in sim_records]
        filled_net_pnl = [r["realized_net_pnl_usd"] for r in filled_records]
        filled_pips = [r["realized_pips"] for r in filled_records]
        fill_times = [r["time_to_fill_min"] for r in filled_records if r["time_to_fill_min"] is not None]
        post_maes = [r["post_fill_mae_pips"] for r in filled_records]
        post_mfes = [r["post_fill_mfe_pips"] for r in filled_records]
        runaways = [r for r in filled_records if r["adverse_runaway"]]
        runaway_rate = len(runaways) / n_filled if n_filled > 0 else 0.0

        # Performance metrics
        mean_net_trade = float(np.mean(filled_net_pnl)) if filled_net_pnl else 0.0
        mean_pips_trade = float(np.mean(filled_pips)) if filled_pips else 0.0
        tot_net_usd = float(np.sum(daily_net_pnl))
        tot_opp_usd = float(np.sum([r["opportunity_pnl_usd"] for r in sim_records]))

        # Daily series for Sharpe & Drawdown
        pnl_series = pd.Series(daily_net_pnl)
        mean_d = float(pnl_series.mean())
        std_d = float(pnl_series.std())
        ann_sharpe = (mean_d / std_d * math.sqrt(252.0)) if std_d > 0 else 0.0
        cum_pnl = pnl_series.cumsum()
        peak = cum_pnl.cummax()
        dd = peak - cum_pnl
        max_dd_usd = float(dd.max()) if len(dd) else 0.0

        exec_results[part_name] = {
            "n_sessions": n_total,
            "n_filled": n_filled,
            "fill_rate": round(fill_rate, 4),
            "median_time_to_fill_min": float(np.median(fill_times)) if fill_times else 0.0,
            "mean_post_fill_mae_pips": round(float(np.mean(post_maes)), 2) if post_maes else 0.0,
            "mean_post_fill_mfe_pips": round(float(np.mean(post_mfes)), 2) if post_mfes else 0.0,
            "adverse_runaway_rate": round(runaway_rate, 4),
            "mean_net_expectancy_pips": round(mean_pips_trade, 2),
            "mean_net_expectancy_usd": round(mean_net_trade, 2),
            "total_realized_net_usd": round(tot_net_usd, 2),
            "total_opportunity_usd": round(tot_opp_usd, 2),
            "annualized_net_sharpe": round(ann_sharpe, 2),
            "max_drawdown_usd": round(max_dd_usd, 2),
        }
        print(f"  [{part_name}] Fill Rate: {fill_rate:.1%} ({n_filled}/{n_total}) | Expectancy: {mean_pips_trade:+.2f} pips (${mean_net_trade:+.2f}/trade) | Sharpe: {ann_sharpe:.2f} | Runaway Rate: {runaway_rate:.1%}")

    # -------------------------------------------------------------
    # Control Baseline: Exposure-Matched Random Boundary Baseline (N=500)
    # -------------------------------------------------------------
    print("\n--- Running Random Boundary Baseline (N=500 Monte Carlo across [0.5*OR, 1.5*OR]) ---")
    rng = np.random.RandomState(42)
    rand_oos_sharpes, rand_oos_expectancies, rand_oos_fill_rates = [], [], []

    oos_session_list = list(oos_sessions.values())
    for _ in range(500):
        # Pick a random boundary multiplier uniformly in [0.5, 1.5] for each session
        rand_mults = rng.uniform(0.5, 1.5, size=len(oos_session_list))
        rand_sims = [
            simulate_passive_limit_execution(sess, boundary_multiplier=m)
            for sess, m in zip(oos_session_list, rand_mults)
        ]
        r_filled = [r for r in rand_sims if r is not None and r["filled"]]
        r_all = [r for r in rand_sims if r is not None]

        f_rate = len(r_filled) / len(r_all) if r_all else 0.0
        pnl_d = [r["realized_net_pnl_usd"] for r in r_all]
        p_series = pd.Series(pnl_d)
        m_d, s_d = float(p_series.mean()), float(p_series.std())
        sh = (m_d / s_d * math.sqrt(252.0)) if s_d > 0 else 0.0
        exp_pips = float(np.mean([r["realized_pips"] for r in r_filled])) if r_filled else 0.0

        rand_oos_sharpes.append(sh)
        rand_oos_expectancies.append(exp_pips)
        rand_oos_fill_rates.append(f_rate)

    rand_ctrl_summary = {
        "mean_fill_rate": round(float(np.mean(rand_oos_fill_rates)), 4),
        "mean_expectancy_pips": round(float(np.mean(rand_oos_expectancies)), 2),
        "std_expectancy_pips": round(float(np.std(rand_oos_expectancies)), 2),
        "p90_expectancy_pips": round(float(np.percentile(rand_oos_expectancies, 90)), 2),
        "mean_sharpe": round(float(np.mean(rand_oos_sharpes)), 2),
        "std_sharpe": round(float(np.std(rand_oos_sharpes)), 2),
    }
    print(f"  Random Control OOS Expectancy: {rand_ctrl_summary['mean_expectancy_pips']:+.2f} pips (std {rand_ctrl_summary['std_expectancy_pips']:.2f}, 90th percentile: {rand_ctrl_summary['p90_expectancy_pips']:+.2f} pips) | Sharpe: {rand_ctrl_summary['mean_sharpe']:.2f}")

    # -------------------------------------------------------------
    # Outcome Categorization & Decision Gates
    # -------------------------------------------------------------
    q1_passed = q1_results["IS"]["q1_passed"] and q1_results["OOS"]["q1_passed"]
    q3_passed = exec_results["OOS"]["fill_rate"] >= 0.40 and exec_results["OOS"]["adverse_runaway_rate"] < 0.25
    q2b_passed = (exec_results["OOS"]["mean_net_expectancy_pips"] > rand_ctrl_summary["p90_expectancy_pips"])
    q4_passed = (exec_results["OOS"]["mean_net_expectancy_pips"] >= 1.50 and exec_results["OOS"]["annualized_net_sharpe"] >= 0.80)

    if q1_passed and q2b_passed and q3_passed and q4_passed:
        outcome = "Case A — Candidate Validated (M-003 Execution Alpha Confirmed)"
    elif q1_passed and not q3_passed:
        outcome = "Case B — Execution Inaccessible (P(Fill) < 40% or High Runaway Rate)"
    elif q1_passed and q3_passed and not q4_passed:
        outcome = "Case C — Descriptive Phenomenon Only (MAE > MFE Confirmed, but Net Expectancy Sub-Hurdle after Costs)"
    elif not q1_passed:
        outcome = "Case D — Mechanism Failure (MAE > MFE Failed to Replicate OOS)"
    else:
        outcome = "Absorbing Negative Result"

    print(f"\n>>> FINAL OUTCOME: {outcome}")

    # Save Evidence Bundle
    bundle = {
        "hypothesis_id": "FX-001",
        "instrument": "EURUSD",
        "outcome_classification": outcome,
        "q1_descriptive_asymmetry": q1_results,
        "q2_q3_q4_execution_results": exec_results,
        "random_boundary_control": rand_ctrl_summary,
        "decision_gate_status": {
            "q1_descriptive_replication": q1_passed,
            "q2b_predictability_vs_random": q2b_passed,
            "q3_fill_accessibility": q3_passed,
            "q4_net_economic_expectancy": q4_passed,
        }
    }
    bundle_path = RESULTS_DIR / "FX-001-evidence-bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"Saved Evidence Bundle: {bundle_path}")

    # Save Research Report
    report_md = f"""# FX-001: Passive MAE Excursion Reversal Research Report

- **Experiment ID:** `FX-001`
- **Mechanism Ref:** [`M-003` (Structural Excursion Asymmetry)](file:///D:/projects/Project%20TITAN/docs/MECHANISM_REGISTRY.md#L87-L110)
- **Instrument:** `EURUSD` (London Opening Session: 07:00–15:00 UTC)
- **Outcome Classification:** **{outcome}**

---

## 1. Q1: Descriptive Replication Matrix (MAE > MFE Asymmetry)

| Partition | Sessions ($N$) | Mean MAE | Mean MFE | MAE/MFE Ratio | Fraction MAE > MFE | Wilcoxon $p$-value | Gate Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **In-Sample (2021–2024)** | {q1_results['IS']['n_sessions']} | {q1_results['IS']['mean_mae_pips']:.1f} pips | {q1_results['IS']['mean_mfe_pips']:.1f} pips | **{q1_results['IS']['mae_mfe_ratio']:.2f}x** | {q1_results['IS']['fraction_mae_gt_mfe']:.1%} | $p = {q1_results['IS']['wilcoxon_p_value']:.6f}$ | **{"PASSED" if q1_results['IS']['q1_passed'] else "FAILED"}** |
| **Out-of-Sample (2024–2026)** | {q1_results['OOS']['n_sessions']} | {q1_results['OOS']['mean_mae_pips']:.1f} pips | {q1_results['OOS']['mean_mfe_pips']:.1f} pips | **{q1_results['OOS']['mae_mfe_ratio']:.2f}x** | {q1_results['OOS']['fraction_mae_gt_mfe']:.1%} | $p = {q1_results['OOS']['wilcoxon_p_value']:.6f}$ | **{"PASSED" if q1_results['OOS']['q1_passed'] else "FAILED"}** |

---

## 2. Q2–Q4: Passive Limit Order Execution Telemetry (1.0x OR Boundary)

| Metric | In-Sample (2021–2024) | Out-of-Sample (2024–2026) | Random Boundary Control (OOS N=500) |
| :--- | :--- | :--- | :--- |
| **Total Eligible Sessions** | {exec_results['IS']['n_sessions']} | {exec_results['OOS']['n_sessions']} | {exec_results['OOS']['n_sessions']} |
| **Filled Sessions** | {exec_results['IS']['n_filled']} | {exec_results['OOS']['n_filled']} | — |
| **Fill Rate P(Fill)** | **{exec_results['IS']['fill_rate']:.1%}** | **{exec_results['OOS']['fill_rate']:.1%}** | {rand_ctrl_summary['mean_fill_rate']:.1%} |
| **Median Time-to-Fill** | {exec_results['IS']['median_time_to_fill_min']:.0f} min | {exec_results['OOS']['median_time_to_fill_min']:.0f} min | — |
| **Post-Fill Mean MAE** | {exec_results['IS']['mean_post_fill_mae_pips']:.1f} pips | {exec_results['OOS']['mean_post_fill_mae_pips']:.1f} pips | — |
| **Post-Fill Mean MFE** | {exec_results['IS']['mean_post_fill_mfe_pips']:.1f} pips | {exec_results['OOS']['mean_post_fill_mfe_pips']:.1f} pips | — |
| **Adverse Runaway Rate (>2.0x OR)** | {exec_results['IS']['adverse_runaway_rate']:.1%} | {exec_results['OOS']['adverse_runaway_rate']:.1%} | — |
| **Mean Net Expectancy / Trade** | **{exec_results['IS']['mean_net_expectancy_pips']:+.2f} pips** | **{exec_results['OOS']['mean_net_expectancy_pips']:+.2f} pips** | {rand_ctrl_summary['mean_expectancy_pips']:+.2f} pips (+/- {rand_ctrl_summary['std_expectancy_pips']:.2f}) |
| **Mean Net USD / Trade** | **${exec_results['IS']['mean_net_expectancy_usd']:+.2f}** | **${exec_results['OOS']['mean_net_expectancy_usd']:+.2f}** | — |
| **Total Realized Net P&L** | **${exec_results['IS']['total_realized_net_usd']:+,.2f}** | **${exec_results['OOS']['total_realized_net_usd']:+,.2f}** | — |
| **Unfilled Opportunity P&L** | ${exec_results['IS']['total_opportunity_usd']:+,.2f} | ${exec_results['OOS']['total_opportunity_usd']:+,.2f} | — |
| **Annualized Net Sharpe** | **{exec_results['IS']['annualized_net_sharpe']:.2f}** | **{exec_results['OOS']['annualized_net_sharpe']:.2f}** | {rand_ctrl_summary['mean_sharpe']:.2f} |
| **Max Drawdown** | ${exec_results['IS']['max_drawdown_usd']:,.2f} | ${exec_results['OOS']['max_drawdown_usd']:,.2f} | — |

---

## 3. Decision Gate Summary

1. **Q1 (Descriptive Asymmetry):** **{"PASSED" if q1_passed else "FAILED"}** — Tested MAE vs MFE across all sessions.
2. **Q2b (Predictability vs. Random Baseline):** **{"PASSED" if q2b_passed else "FAILED"}** — Fixed 1.0x OR boundary comparison against Monte Carlo baseline.
3. **Q3 (Passive Fill Accessibility):** **{"PASSED" if q3_passed else "FAILED"}** — Fill rate is **{exec_results['OOS']['fill_rate']:.1%}** with **{exec_results['OOS']['adverse_runaway_rate']:.1%}** adverse runaway rate.
4. **Q4 (Net Economic Expectancy after Costs):** **{"PASSED" if q4_passed else "FAILED"}** — Net expectancy is **{exec_results['OOS']['mean_net_expectancy_pips']:+.2f} pips** (Sharpe **{exec_results['OOS']['annualized_net_sharpe']:.2f}**).

---

## 4. Scientific Governance Verdict

**Verdict:** `{outcome}`  
Recorded permanently in `FX-001-evidence-bundle.json`.
"""
    report_path = RESULTS_DIR / "FX-001-reversal-report.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"Saved Report: {report_path}")


if __name__ == "__main__":
    run_experiment()
