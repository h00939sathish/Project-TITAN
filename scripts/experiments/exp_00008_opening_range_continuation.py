"""Formal Research Experiment EXP-00008: Opening Range Continuation.

Canonical Research Question: RQ-001
    How does opening auction imbalance affect first-hour returns?

Hypothesis:
    In equity index ETFs (SPY), the direction of the first 30 minutes
    (two 15m bars after 9:30 AM ET / 13:30 UTC) predicts the sign of
    the remaining session return with probability > 52%.

Economic Mechanism:
    Institutional MOO/LOO order flow creates directional pressure that
    is not fully absorbed within the opening range.

Data:
    SPY 15-minute bars from TWS (research/intraday_backtests/2026-07-30/spy_15m.csv)

Preregistered Thresholds:
    - Continuation rate > 52% (binomial test, p < 0.05)
    - Effect survives 2 bps round-trip execution costs
    - Minimum 15 testable sessions in OOS
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

DATA_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "spy_15m.csv"
JOURNAL_PATH = ROOT_DIR / "research" / "journal" / "EXP-00008_journal.md"
EVIDENCE_PATH = ROOT_DIR / "research" / "experiments" / "EXP-00008_evidence_bundle.json"

# --- Constants ---
OPEN_HOUR_UTC = 13   # 9:30 AM ET = 13:30 UTC
OPEN_MINUTE_UTC = 30
CLOSE_HOUR_UTC = 20  # 4:00 PM ET = 20:00 UTC
OPENING_RANGE_BARS = 2  # First two 15m bars = 30 minutes
COST_BPS_RT = 2.0  # Round-trip execution cost in basis points


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


def group_by_session(bars: list[dict]) -> dict[str, list[dict]]:
    """Group bars into trading sessions by date.

    A session starts at 13:30 UTC and ends before 20:15 UTC.
    """
    sessions: dict[str, list[dict]] = defaultdict(list)
    for bar in bars:
        ts = bar["timestamp"]
        hour, minute = ts.hour, ts.minute
        # Bars from 13:30 UTC to ~20:00 UTC belong to the same session date
        if hour < OPEN_HOUR_UTC or (hour == OPEN_HOUR_UTC and minute < OPEN_MINUTE_UTC):
            continue
        if hour >= CLOSE_HOUR_UTC + 1:
            continue
        session_key = ts.strftime("%Y-%m-%d")
        sessions[session_key].append(bar)

    # Sort bars within each session
    for key in sessions:
        sessions[key].sort(key=lambda b: b["timestamp"])
    return dict(sorted(sessions.items()))


def analyze_session(session_bars: list[dict]) -> dict | None:
    """Analyze a single session for opening range continuation.

    Returns None if the session doesn't have enough bars.
    """
    if len(session_bars) < OPENING_RANGE_BARS + 2:
        return None

    # Opening range: first two 15m bars
    or_bars = session_bars[:OPENING_RANGE_BARS]
    or_open = or_bars[0]["open"]
    or_close = or_bars[-1]["close"]
    or_return = or_close - or_open
    or_return_pct = (or_return / or_open) * 100.0 if or_open > 0 else 0.0

    # Opening range volume
    or_volume = sum(b["volume"] for b in or_bars)

    # Session return: from end of opening range to session close
    rest_bars = session_bars[OPENING_RANGE_BARS:]
    session_close = rest_bars[-1]["close"]
    session_return = session_close - or_close
    session_return_pct = (session_return / or_close) * 100.0 if or_close > 0 else 0.0

    # Direction
    or_direction = 1 if or_return > 0 else (-1 if or_return < 0 else 0)
    session_direction = 1 if session_return > 0 else (-1 if session_return < 0 else 0)

    if or_direction == 0:
        return None  # Flat opening range — not testable

    continued = or_direction == session_direction

    # Cost-adjusted: deduct round-trip cost from session return
    cost = (or_close * COST_BPS_RT / 10000.0)
    session_return_after_costs = abs(session_return) - cost
    survived_costs = session_return_after_costs > 0 if continued else True

    return {
        "date": session_bars[0]["timestamp"].strftime("%Y-%m-%d"),
        "or_return_pct": or_return_pct,
        "or_direction": or_direction,
        "or_volume": or_volume,
        "session_return_pct": session_return_pct,
        "session_direction": session_direction,
        "continued": continued,
        "survived_costs": survived_costs,
        "n_bars": len(session_bars),
    }


def binomial_p_value(successes: int, trials: int, null_p: float = 0.5) -> float:
    """One-sided binomial test: P(X >= successes | p = null_p).

    Uses normal approximation for simplicity and reproducibility.
    """
    if trials == 0:
        return 1.0
    mean = trials * null_p
    std = math.sqrt(trials * null_p * (1 - null_p))
    if std == 0:
        return 1.0
    z = (successes - 0.5 - mean) / std  # Continuity correction
    # Standard normal CDF approximation (Abramowitz & Stegun)
    p_value = 0.5 * math.erfc(z / math.sqrt(2))
    return p_value


def welch_t_test(group_a: list[float], group_b: list[float]) -> tuple[float, float]:
    """Welch's t-test for unequal variances. Returns (t_stat, p_value)."""
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return 0.0, 1.0
    mean_a = sum(group_a) / n_a
    mean_b = sum(group_b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in group_a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in group_b) / (n_b - 1)
    se = math.sqrt(var_a / n_a + var_b / n_b) if (var_a / n_a + var_b / n_b) > 0 else 1e-10
    t_stat = (mean_a - mean_b) / se
    # Approximate p-value using normal distribution (conservative for small samples)
    p_value = 0.5 * math.erfc(abs(t_stat) / math.sqrt(2))
    return t_stat, p_value


def run_experiment():
    """Execute EXP-00008."""
    print("=" * 76)
    print("  RESEARCH EXPERIMENT EXP-00008: OPENING RANGE CONTINUATION")
    print("  Canonical Research Question: RQ-001")
    print("=" * 76)
    print()

    # --- Load and structure data ---
    if not DATA_PATH.exists():
        print(f"ERROR: Data file not found: {DATA_PATH}")
        return
    bars = load_bars(str(DATA_PATH))
    print(f"Loaded {len(bars)} bars from {DATA_PATH.name}")

    sessions = group_by_session(bars)
    print(f"Identified {len(sessions)} trading sessions")
    print()

    # --- Analyze each session ---
    results = []
    for date_key, session_bars in sessions.items():
        r = analyze_session(session_bars)
        if r is not None:
            results.append(r)
    print(f"Testable sessions: {len(results)}")
    print()

    if len(results) < 10:
        print("ABORT: Insufficient testable sessions (< 10). Cannot proceed.")
        return

    # --- Train / Validation Split (60% / 40% chronological) ---
    split_idx = int(len(results) * 0.60)
    train = results[:split_idx]
    oos = results[split_idx:]
    print(f"Train sessions: {len(train)} | OOS sessions: {len(oos)}")
    print(f"Train period: {train[0]['date']} to {train[-1]['date']}")
    print(f"OOS period:   {oos[0]['date']} to {oos[-1]['date']}")
    print()

    # --- Compute metrics for both splits ---
    for label, data in [("TRAIN", train), ("OUT-OF-SAMPLE", oos)]:
        print(f"--- {label} ({len(data)} sessions) ---")

        continuations = sum(1 for r in data if r["continued"])
        cont_rate = continuations / len(data) * 100 if data else 0
        p_val = binomial_p_value(continuations, len(data), 0.5)

        cont_returns = [abs(r["session_return_pct"]) for r in data if r["continued"]]
        rev_returns = [abs(r["session_return_pct"]) for r in data if not r["continued"]]

        mean_cont_ret = sum(cont_returns) / len(cont_returns) if cont_returns else 0
        mean_rev_ret = sum(rev_returns) / len(rev_returns) if rev_returns else 0

        t_stat, t_pval = welch_t_test(cont_returns, rev_returns)

        # Volume quartile analysis
        volumes = sorted([r["or_volume"] for r in data])
        if len(volumes) >= 4:
            q75_vol = volumes[int(len(volumes) * 0.75)]
            q25_vol = volumes[int(len(volumes) * 0.25)]
            high_vol = [r for r in data if r["or_volume"] >= q75_vol]
            low_vol = [r for r in data if r["or_volume"] <= q25_vol]
            hv_cont = sum(1 for r in high_vol if r["continued"]) / len(high_vol) * 100 if high_vol else 0
            lv_cont = sum(1 for r in low_vol if r["continued"]) / len(low_vol) * 100 if low_vol else 0
        else:
            hv_cont, lv_cont = 0, 0

        # Cost survival
        cost_survivors = sum(1 for r in data if r["continued"] and r["survived_costs"])
        cost_rate = cost_survivors / continuations * 100 if continuations > 0 else 0

        print(f"  Continuation Rate:        {cont_rate:.1f}% ({continuations}/{len(data)})")
        print(f"  p-value (binomial):       {p_val:.4f}")
        print(f"  Mean Continuation Return: {mean_cont_ret:.4f}%")
        print(f"  Mean Reversal Return:     {mean_rev_ret:.4f}%")
        print(f"  Welch t-stat:             {t_stat:.3f} (p={t_pval:.4f})")
        print(f"  High-Vol Cont. Rate:      {hv_cont:.1f}%")
        print(f"  Low-Vol Cont. Rate:       {lv_cont:.1f}%")
        print(f"  Cost Survival Rate:       {cost_rate:.1f}%")
        print()

        if label == "TRAIN":
            train_metrics = {
                "sessions": len(data),
                "continuation_rate_pct": round(cont_rate, 2),
                "p_value_binomial": round(p_val, 4),
                "mean_continuation_return_pct": round(mean_cont_ret, 4),
                "mean_reversal_return_pct": round(mean_rev_ret, 4),
                "welch_t_stat": round(t_stat, 3),
                "welch_p_value": round(t_pval, 4),
                "high_vol_continuation_pct": round(hv_cont, 1),
                "low_vol_continuation_pct": round(lv_cont, 1),
                "cost_survival_pct": round(cost_rate, 1),
            }
        else:
            oos_metrics = {
                "sessions": len(data),
                "continuation_rate_pct": round(cont_rate, 2),
                "p_value_binomial": round(p_val, 4),
                "mean_continuation_return_pct": round(mean_cont_ret, 4),
                "mean_reversal_return_pct": round(mean_rev_ret, 4),
                "welch_t_stat": round(t_stat, 3),
                "welch_p_value": round(t_pval, 4),
                "high_vol_continuation_pct": round(hv_cont, 1),
                "low_vol_continuation_pct": round(lv_cont, 1),
                "cost_survival_pct": round(cost_rate, 1),
            }

    # --- Governance Decision ---
    print("=" * 76)
    print("  GOVERNANCE GATE")
    print("=" * 76)

    checks = {}
    # Check 1: OOS continuation rate > 52%
    checks["oos_continuation_rate_above_52pct"] = oos_metrics["continuation_rate_pct"] > 52.0
    # Check 2: OOS p-value < 0.05
    checks["oos_p_value_below_0.05"] = oos_metrics["p_value_binomial"] < 0.05
    # Check 3: OOS sessions >= 15
    checks["oos_min_sessions_15"] = oos_metrics["sessions"] >= 15
    # Check 4: Effect survives costs
    checks["effect_survives_costs"] = oos_metrics["cost_survival_pct"] > 50.0
    # Check 5: Consistent across train and OOS
    train_oos_consistent = abs(train_metrics["continuation_rate_pct"] - oos_metrics["continuation_rate_pct"]) < 15.0
    checks["train_oos_consistency"] = train_oos_consistent

    all_passed = all(checks.values())

    for check_name, passed in checks.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {check_name}: {passed}")

    print()
    decision = "PROMOTED" if all_passed else "REJECTED"
    print(f"  DECISION: {decision}")
    print()

    if not all_passed:
        failed = [k for k, v in checks.items() if not v]
        print(f"  Rejection reasons: {', '.join(failed)}")
        print()

    # --- Per-session detail table ---
    print("=" * 76)
    print("  SESSION DETAIL")
    print("=" * 76)
    print(f"  {'Date':<12} {'OR Dir':>7} {'OR Ret%':>8} {'Sess Ret%':>10} {'Cont?':>6} {'Vol':>10}")
    print(f"  {'-'*12} {'-'*7} {'-'*8} {'-'*10} {'-'*6} {'-'*10}")
    for r in results:
        d = "UP" if r["or_direction"] > 0 else "DOWN"
        c = "YES" if r["continued"] else "NO"
        print(f"  {r['date']:<12} {d:>7} {r['or_return_pct']:>8.4f} {r['session_return_pct']:>10.4f} {c:>6} {r['or_volume']:>10.0f}")
    print()

    # --- Build evidence bundle ---
    evidence = {
        "experiment_id": "EXP-00008",
        "canonical_research_question": "RQ-001",
        "hypothesis": "Opening range direction predicts session drift direction with probability > 52%",
        "economic_mechanism": "Institutional MOO/LOO order flow creates persistent directional pressure",
        "instrument": "SPY",
        "timeframe": "15m",
        "data_source": str(DATA_PATH.name),
        "total_sessions": len(results),
        "train_period": {"start": train[0]["date"], "end": train[-1]["date"], "sessions": len(train)},
        "oos_period": {"start": oos[0]["date"], "end": oos[-1]["date"], "sessions": len(oos)},
        "train_metrics": train_metrics,
        "oos_metrics": oos_metrics,
        "governance_checks": checks,
        "decision": decision,
        "preregistered_thresholds": {
            "continuation_rate_min": 52.0,
            "p_value_max": 0.05,
            "min_oos_sessions": 15,
            "cost_bps_rt": COST_BPS_RT,
            "bonferroni_alpha": 0.0167,
        },
        "session_results": results,
        "execution_timestamp": datetime.utcnow().isoformat(),
    }

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(f"Evidence bundle saved: {EVIDENCE_PATH}")
    print()
    print("=" * 76)
    print("  EXP-00008 COMPLETE")
    print("=" * 76)

    return evidence


if __name__ == "__main__":
    run_experiment()
