"""Formal Research Experiment EXP-00010: Structural MAE > MFE Analysis.

Canonical Research Question: RQ-001
Predecessors: EXP-00008 (REJECTED), EXP-00009 (REFINED)

Hypothesis:
    Intraday sessions structurally mean-revert from the opening range:
    Maximum Adverse Excursion (MAE) exceeds Maximum Favorable Excursion (MFE)
    as a durable, unconditional property across sessions.

    This is a weaker but more testable claim than EXP-00009's magnitude-
    conditioned reversal hypothesis. It tests the most stable empirical
    observation from the first two experiments.

Sub-questions (exploratory):
    - Is MAE > MFE unique to SPY or does it appear in EURUSD?
    - Is the effect time-of-day specific (morning vs afternoon)?
    - Does the overnight gap amplify or suppress the effect?
    - Does opening range magnitude change the MAE/MFE ratio?

Preregistered Thresholds:
    - Mean MAE > Mean MFE with paired Wilcoxon signed-rank test p < 0.05
    - Effect must hold in both train (60%) and OOS (40%)
    - MAE/MFE ratio > 1.0 in OOS
"""

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

SPY_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "spy_15m.csv"
EURUSD_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "eurusd_15m.csv"
EVIDENCE_PATH = ROOT_DIR / "research" / "experiments" / "EXP-00010_evidence_bundle.json"

OPENING_RANGE_BARS = 2


# --- Session definitions ---
# SPY: 13:30-20:00 UTC (9:30 AM - 4:00 PM ET)
# EURUSD: London open 07:00-15:00 UTC (anchor to real liquidity)

INSTRUMENTS = {
    "SPY": {
        "path": SPY_PATH,
        "open_hour": 13, "open_minute": 30,
        "close_hour": 20, "close_minute": 0,
        "label": "SPY (NYSE 9:30-16:00 ET)",
    },
    "EURUSD": {
        "path": EURUSD_PATH,
        "open_hour": 7, "open_minute": 0,
        "close_hour": 15, "close_minute": 0,
        "label": "EURUSD (London 07:00-15:00 UTC)",
    },
}


def load_bars(path: str) -> list[dict]:
    """Load 15m bars from CSV."""
    bars = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("timestamp", "").strip()
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            try:
                bar = {
                    "timestamp": ts,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                }
                bars.append(bar)
            except (ValueError, KeyError):
                continue
    return bars


def group_by_session(bars: list[dict], open_hour: int, open_minute: int,
                     close_hour: int, close_minute: int) -> dict[str, list[dict]]:
    """Group bars into trading sessions."""
    sessions: dict[str, list[dict]] = defaultdict(list)
    for bar in bars:
        ts = bar["timestamp"]
        h, m = ts.hour, ts.minute
        time_minutes = h * 60 + m
        open_minutes = open_hour * 60 + open_minute
        close_minutes = close_hour * 60 + close_minute
        if time_minutes < open_minutes or time_minutes >= close_minutes:
            continue
        session_key = ts.strftime("%Y-%m-%d")
        sessions[session_key].append(bar)
    for key in sessions:
        sessions[key].sort(key=lambda b: b["timestamp"])
    return dict(sorted(sessions.items()))


def analyze_session(session_bars: list[dict], prev_close: float | None) -> dict | None:
    """Compute MAE, MFE, and session structure for a single session."""
    if len(session_bars) < OPENING_RANGE_BARS + 2:
        return None

    or_bars = session_bars[:OPENING_RANGE_BARS]
    or_open = or_bars[0]["open"]
    or_close = or_bars[-1]["close"]
    or_high = max(b["high"] for b in or_bars)
    or_low = min(b["low"] for b in or_bars)
    or_range_pct = ((or_high - or_low) / or_open * 100) if or_open > 0 else 0
    or_return = or_close - or_open
    or_direction = 1 if or_return > 0 else (-1 if or_return < 0 else 0)

    if or_direction == 0:
        return None

    overnight_gap_pct = ((or_open - prev_close) / prev_close * 100) if prev_close and prev_close > 0 else 0

    rest_bars = session_bars[OPENING_RANGE_BARS:]
    session_close = rest_bars[-1]["close"]

    # MAE and MFE
    mae = 0.0
    mfe = 0.0
    for bar in rest_bars:
        if or_direction > 0:
            adverse = (or_close - bar["low"]) / or_close * 100
            favorable = (bar["high"] - or_close) / or_close * 100
        else:
            adverse = (bar["high"] - or_close) / or_close * 100
            favorable = (or_close - bar["low"]) / or_close * 100
        mae = max(mae, adverse)
        mfe = max(mfe, favorable)

    # Time-of-day analysis: split rest_bars into first half (morning) and second half (afternoon)
    mid = len(rest_bars) // 2
    morning_bars = rest_bars[:mid]
    afternoon_bars = rest_bars[mid:]

    def compute_half_mae_mfe(half_bars):
        h_mae, h_mfe = 0.0, 0.0
        for bar in half_bars:
            if or_direction > 0:
                adv = (or_close - bar["low"]) / or_close * 100
                fav = (bar["high"] - or_close) / or_close * 100
            else:
                adv = (bar["high"] - or_close) / or_close * 100
                fav = (or_close - bar["low"]) / or_close * 100
            h_mae = max(h_mae, adv)
            h_mfe = max(h_mfe, fav)
        return h_mae, h_mfe

    morning_mae, morning_mfe = compute_half_mae_mfe(morning_bars)
    afternoon_mae, afternoon_mfe = compute_half_mae_mfe(afternoon_bars)

    mae_gt_mfe = mae > mfe

    return {
        "date": session_bars[0]["timestamp"].strftime("%Y-%m-%d"),
        "or_direction": or_direction,
        "or_range_pct": round(or_range_pct, 4),
        "overnight_gap_pct": round(overnight_gap_pct, 4),
        "mae_pct": round(mae, 4),
        "mfe_pct": round(mfe, 4),
        "mae_gt_mfe": mae_gt_mfe,
        "mae_minus_mfe": round(mae - mfe, 4),
        "mae_mfe_ratio": round(mae / mfe, 4) if mfe > 0 else float("inf"),
        "morning_mae": round(morning_mae, 4),
        "morning_mfe": round(morning_mfe, 4),
        "afternoon_mae": round(afternoon_mae, 4),
        "afternoon_mfe": round(afternoon_mfe, 4),
        "session_close": session_close,
    }


def wilcoxon_signed_rank(diffs: list[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test for paired data.

    Tests H0: median(diffs) = 0 vs H1: median(diffs) > 0 (one-sided).
    Returns (W_plus statistic, p-value via normal approximation).
    """
    # Remove zeros
    nonzero = [(abs(d), d) for d in diffs if d != 0]
    n = len(nonzero)
    if n < 5:
        return 0.0, 1.0

    # Rank by absolute value
    nonzero.sort(key=lambda x: x[0])
    w_plus = 0.0
    w_minus = 0.0
    for rank, (abs_val, orig_val) in enumerate(nonzero, 1):
        if orig_val > 0:
            w_plus += rank
        else:
            w_minus += rank

    # Normal approximation
    expected = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24
    z = (w_plus - expected) / math.sqrt(var) if var > 0 else 0
    p_value = 0.5 * math.erfc(z / math.sqrt(2))  # One-sided
    return w_plus, p_value


def sign_test(values: list[bool]) -> tuple[int, int, float]:
    """Simple sign test: count positives vs negatives, binomial p-value."""
    positives = sum(1 for v in values if v)
    n = len(values)
    if n == 0:
        return 0, 0, 1.0
    # Normal approximation to binomial
    mean = n * 0.5
    std = math.sqrt(n * 0.25)
    if std == 0:
        return positives, n, 1.0
    z = (positives - 0.5 - mean) / std
    p_value = 0.5 * math.erfc(z / math.sqrt(2))
    return positives, n, p_value


def run_instrument(instrument_id: str, config: dict) -> dict | None:
    """Run MAE/MFE analysis for a single instrument."""
    path = config["path"]
    if not path.exists():
        print(f"  SKIP: {path} not found")
        return None

    bars = load_bars(str(path))
    if not bars:
        print(f"  SKIP: No bars loaded from {path.name}")
        return None

    sessions = group_by_session(bars, config["open_hour"], config["open_minute"],
                                config["close_hour"], config["close_minute"])

    results = []
    prev_close = None
    for date_key in sorted(sessions.keys()):
        session_bars = sessions[date_key]
        r = analyze_session(session_bars, prev_close)
        if r is not None:
            results.append(r)
        prev_close = session_bars[-1]["close"]

    if len(results) < 6:
        print(f"  SKIP: Only {len(results)} testable sessions (need >= 6)")
        return None

    print(f"\n{'=' * 76}")
    print(f"  {instrument_id}: {config['label']}")
    print(f"  Testable sessions: {len(results)}")
    print(f"{'=' * 76}\n")

    # Train / OOS split
    split_idx = int(len(results) * 0.60)
    train = results[:split_idx]
    oos = results[split_idx:]

    all_metrics = {}

    for label, data in [("TRAIN", train), ("OUT-OF-SAMPLE", oos)]:
        print(f"  --- {label} ({len(data)} sessions) ---")

        # Primary: MAE vs MFE
        mae_vals = [r["mae_pct"] for r in data]
        mfe_vals = [r["mfe_pct"] for r in data]
        diffs = [r["mae_pct"] - r["mfe_pct"] for r in data]
        mean_mae = sum(mae_vals) / len(mae_vals)
        mean_mfe = sum(mfe_vals) / len(mfe_vals)
        ratio = mean_mae / mean_mfe if mean_mfe > 0 else float("inf")

        w_plus, wilcoxon_p = wilcoxon_signed_rank(diffs)
        mae_gt_count, n_sessions, sign_p = sign_test([r["mae_gt_mfe"] for r in data])

        print(f"    Mean MAE:           {mean_mae:.4f}%")
        print(f"    Mean MFE:           {mean_mfe:.4f}%")
        print(f"    MAE/MFE ratio:      {ratio:.3f}")
        print(f"    MAE > MFE sessions: {mae_gt_count}/{n_sessions} ({mae_gt_count/n_sessions*100:.1f}%)")
        print(f"    Wilcoxon p-value:   {wilcoxon_p:.4f}")
        print(f"    Sign test p-value:  {sign_p:.4f}")
        print()

        # Time-of-day: morning vs afternoon
        morning_mae_gt = sum(1 for r in data if r["morning_mae"] > r["morning_mfe"])
        afternoon_mae_gt = sum(1 for r in data if r["afternoon_mae"] > r["afternoon_mfe"])
        morning_diffs = [r["morning_mae"] - r["morning_mfe"] for r in data]
        afternoon_diffs = [r["afternoon_mae"] - r["afternoon_mfe"] for r in data]
        _, morning_p = wilcoxon_signed_rank(morning_diffs)
        _, afternoon_p = wilcoxon_signed_rank(afternoon_diffs)

        print(f"    Time-of-day breakdown:")
        print(f"      Morning  MAE > MFE: {morning_mae_gt}/{len(data)} (Wilcoxon p={morning_p:.4f})")
        print(f"      Afternoon MAE > MFE: {afternoon_mae_gt}/{len(data)} (Wilcoxon p={afternoon_p:.4f})")
        print()

        # Overnight gap conditioning
        gapped = [r for r in data if abs(r["overnight_gap_pct"]) > 0.05]
        no_gap = [r for r in data if abs(r["overnight_gap_pct"]) <= 0.05]
        gap_ratio = (sum(r["mae_pct"] for r in gapped) / len(gapped)) / (sum(r["mfe_pct"] for r in gapped) / len(gapped)) if gapped and sum(r["mfe_pct"] for r in gapped) > 0 else 0
        nogap_ratio = (sum(r["mae_pct"] for r in no_gap) / len(no_gap)) / (sum(r["mfe_pct"] for r in no_gap) / len(no_gap)) if no_gap and sum(r["mfe_pct"] for r in no_gap) > 0 else 0

        print(f"    Overnight gap conditioning:")
        print(f"      With gap (>5bp):    {len(gapped)} sessions, MAE/MFE={gap_ratio:.3f}")
        print(f"      Without gap:        {len(no_gap)} sessions, MAE/MFE={nogap_ratio:.3f}")
        print()

        # OR magnitude quartile conditioning
        sorted_by_or = sorted(data, key=lambda r: r["or_range_pct"])
        q_size = max(len(data) // 4, 1)
        small_or = sorted_by_or[:q_size]
        large_or = sorted_by_or[-q_size:]
        small_ratio = (sum(r["mae_pct"] for r in small_or) / len(small_or)) / (sum(r["mfe_pct"] for r in small_or) / len(small_or)) if small_or and sum(r["mfe_pct"] for r in small_or) > 0 else 0
        large_ratio = (sum(r["mae_pct"] for r in large_or) / len(large_or)) / (sum(r["mfe_pct"] for r in large_or) / len(large_or)) if large_or and sum(r["mfe_pct"] for r in large_or) > 0 else 0

        print(f"    OR magnitude conditioning:")
        print(f"      Small OR (bottom Q): {len(small_or)} sessions, MAE/MFE={small_ratio:.3f}")
        print(f"      Large OR (top Q):    {len(large_or)} sessions, MAE/MFE={large_ratio:.3f}")
        print()

        # Session detail
        print(f"    {'Date':<12} {'MAE%':>7} {'MFE%':>7} {'MAE>MFE':>8} {'Diff':>7} {'Ratio':>7} {'OR Rng%':>8} {'Gap%':>7}")
        print(f"    {'-'*12} {'-'*7} {'-'*7} {'-'*8} {'-'*7} {'-'*7} {'-'*8} {'-'*7}")
        for r in data:
            gt = "YES" if r["mae_gt_mfe"] else "NO"
            print(f"    {r['date']:<12} {r['mae_pct']:>7.4f} {r['mfe_pct']:>7.4f} {gt:>8} {r['mae_minus_mfe']:>7.4f} {r['mae_mfe_ratio']:>7.3f} {r['or_range_pct']:>8.4f} {r['overnight_gap_pct']:>7.3f}")
        print()

        all_metrics[label] = {
            "sessions": len(data),
            "mean_mae_pct": round(mean_mae, 4),
            "mean_mfe_pct": round(mean_mfe, 4),
            "mae_mfe_ratio": round(ratio, 4),
            "mae_gt_mfe_count": mae_gt_count,
            "mae_gt_mfe_pct": round(mae_gt_count / n_sessions * 100, 1),
            "wilcoxon_p": round(wilcoxon_p, 4),
            "sign_test_p": round(sign_p, 4),
            "morning_mae_gt_count": morning_mae_gt,
            "morning_wilcoxon_p": round(morning_p, 4),
            "afternoon_mae_gt_count": afternoon_mae_gt,
            "afternoon_wilcoxon_p": round(afternoon_p, 4),
            "gap_sessions": len(gapped),
            "gap_mae_mfe_ratio": round(gap_ratio, 4),
            "nogap_sessions": len(no_gap),
            "nogap_mae_mfe_ratio": round(nogap_ratio, 4),
            "small_or_mae_mfe_ratio": round(small_ratio, 4),
            "large_or_mae_mfe_ratio": round(large_ratio, 4),
        }

    return {
        "instrument": instrument_id,
        "label": config["label"],
        "total_sessions": len(results),
        "train_period": {"start": train[0]["date"], "end": train[-1]["date"]},
        "oos_period": {"start": oos[0]["date"], "end": oos[-1]["date"]},
        "train_metrics": all_metrics["TRAIN"],
        "oos_metrics": all_metrics["OUT-OF-SAMPLE"],
        "session_results": results,
    }


def run_experiment():
    """Execute EXP-00010."""
    print("=" * 76)
    print("  RESEARCH EXPERIMENT EXP-00010: STRUCTURAL MAE > MFE ANALYSIS")
    print("  Canonical Research Question: RQ-001")
    print("  Predecessors: EXP-00008 (REJECTED), EXP-00009 (REFINED)")
    print("=" * 76)

    instrument_results = {}
    for inst_id, config in INSTRUMENTS.items():
        result = run_instrument(inst_id, config)
        if result:
            instrument_results[inst_id] = result

    # --- Cross-instrument governance ---
    print("=" * 76)
    print("  GOVERNANCE GATE")
    print("=" * 76)

    checks = {}
    for inst_id, result in instrument_results.items():
        oos = result["oos_metrics"]
        train = result["train_metrics"]
        # Primary: MAE/MFE > 1.0 in OOS
        checks[f"{inst_id}_oos_mae_mfe_gt_1"] = oos["mae_mfe_ratio"] > 1.0
        # Primary: Wilcoxon p < 0.05 in OOS
        checks[f"{inst_id}_oos_wilcoxon_p_lt_0.05"] = oos["wilcoxon_p"] < 0.05
        # Consistency: same direction train and OOS
        checks[f"{inst_id}_train_oos_consistent"] = (train["mae_mfe_ratio"] > 1.0) == (oos["mae_mfe_ratio"] > 1.0)
        # MAE > MFE in majority of OOS sessions
        checks[f"{inst_id}_oos_majority_mae_gt_mfe"] = oos["mae_gt_mfe_pct"] > 50.0

    # Cross-instrument: if both instruments available, check consistency
    if len(instrument_results) >= 2:
        ratios = [r["oos_metrics"]["mae_mfe_ratio"] for r in instrument_results.values()]
        checks["cross_instrument_consistent"] = all(r > 1.0 for r in ratios)

    for check_name, passed in checks.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {check_name}: {passed}")
    print()

    # Decision logic
    primary_checks = [k for k in checks if "wilcoxon" in k or "mae_mfe_gt_1" in k]
    primary_passed = all(checks[k] for k in primary_checks)

    if primary_passed and len(instrument_results) >= 2 and checks.get("cross_instrument_consistent", False):
        decision = "PROMOTED"
    elif primary_passed:
        decision = "REFINED"  # Passed for some instruments but not cross-validated
    else:
        # Check if directionally consistent even if not significant
        directional = [k for k in checks if "consistent" in k]
        if all(checks.get(k, False) for k in directional):
            decision = "REFINED"
        else:
            decision = "REJECTED"

    print(f"  DECISION: {decision}")
    if decision != "PROMOTED":
        failed = [k for k, v in checks.items() if not v]
        if failed:
            print(f"  Issues: {', '.join(failed)}")
    print()

    # Build evidence bundle
    evidence = {
        "experiment_id": "EXP-00010",
        "predecessors": ["EXP-00008", "EXP-00009"],
        "canonical_research_question": "RQ-001",
        "hypothesis": "MAE > MFE is a durable unconditional structural property of intraday sessions",
        "economic_mechanism": "Opening auction creates directional displacement; session mean-reverts as liquidity providers absorb the imbalance",
        "instruments": list(instrument_results.keys()),
        "timeframe": "15m",
        "governance_checks": checks,
        "decision": decision,
        "instrument_results": {k: {
            "total_sessions": v["total_sessions"],
            "train_period": v["train_period"],
            "oos_period": v["oos_period"],
            "train_metrics": v["train_metrics"],
            "oos_metrics": v["oos_metrics"],
        } for k, v in instrument_results.items()},
        "preregistered_thresholds": {
            "wilcoxon_alpha": 0.05,
            "mae_mfe_ratio_min": 1.0,
            "majority_threshold": 50.0,
        },
        "execution_timestamp": datetime.now().isoformat(),
    }

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(f"Evidence bundle saved: {EVIDENCE_PATH}")
    print()
    print("=" * 76)
    print("  EXP-00010 COMPLETE")
    print("=" * 76)

    return evidence


if __name__ == "__main__":
    run_experiment()
