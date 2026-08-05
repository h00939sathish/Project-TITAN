"""Formal Research Experiment EXP-00009: Opening Range Exhaustion & Reversal.

Canonical Research Question: RQ-001
Predecessor: EXP-00008 (REJECTED — reversal finding seeded this hypothesis)

Hypothesis:
    Large opening imbalances in SPY increase the probability of intraday
    reversal rather than continuation. The mechanism is liquidity exhaustion:
    large MOO-driven moves consume available liquidity, and once institutional
    execution completes, contrarian flow mean-reverts the price.

Independent Variables:
    - Opening range magnitude (% and percentile)
    - Opening volume (absolute and percentile)
    - Overnight gap (%)

Dependent Variables:
    - Reversal probability
    - Reversal magnitude
    - Maximum adverse excursion (MAE)

Preregistered Thresholds:
    - Top-quartile OR sessions reverse more than bottom-quartile (Fisher p < 0.05)
    - Spearman(OR magnitude, reversal magnitude) significant at Bonferroni α = 0.0167
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
EVIDENCE_PATH = ROOT_DIR / "research" / "experiments" / "EXP-00009_evidence_bundle.json"

OPEN_HOUR_UTC = 13
OPEN_MINUTE_UTC = 30
CLOSE_HOUR_UTC = 20
OPENING_RANGE_BARS = 2


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
    """Group bars into trading sessions by date."""
    sessions: dict[str, list[dict]] = defaultdict(list)
    for bar in bars:
        ts = bar["timestamp"]
        hour, minute = ts.hour, ts.minute
        if hour < OPEN_HOUR_UTC or (hour == OPEN_HOUR_UTC and minute < OPEN_MINUTE_UTC):
            continue
        if hour >= CLOSE_HOUR_UTC + 1:
            continue
        session_key = ts.strftime("%Y-%m-%d")
        sessions[session_key].append(bar)
    for key in sessions:
        sessions[key].sort(key=lambda b: b["timestamp"])
    return dict(sorted(sessions.items()))


def analyze_session(session_bars: list[dict], prev_close: float | None) -> dict | None:
    """Analyze a single session with multi-variable framework."""
    if len(session_bars) < OPENING_RANGE_BARS + 2:
        return None

    # Opening range
    or_bars = session_bars[:OPENING_RANGE_BARS]
    or_open = or_bars[0]["open"]
    or_close = or_bars[-1]["close"]
    or_high = max(b["high"] for b in or_bars)
    or_low = min(b["low"] for b in or_bars)
    or_range_abs = or_high - or_low
    or_return = or_close - or_open
    or_return_pct = (or_return / or_open) * 100.0 if or_open > 0 else 0.0
    or_range_pct = (or_range_abs / or_open) * 100.0 if or_open > 0 else 0.0
    or_volume = sum(b["volume"] for b in or_bars)
    or_direction = 1 if or_return > 0 else (-1 if or_return < 0 else 0)

    if or_direction == 0:
        return None

    # Overnight gap
    overnight_gap_pct = ((or_open - prev_close) / prev_close * 100.0) if prev_close and prev_close > 0 else 0.0

    # Session return (rest of day)
    rest_bars = session_bars[OPENING_RANGE_BARS:]
    session_close = rest_bars[-1]["close"]
    session_return = session_close - or_close
    session_return_pct = (session_return / or_close) * 100.0 if or_close > 0 else 0.0
    session_direction = 1 if session_return > 0 else (-1 if session_return < 0 else 0)

    reversed = or_direction != session_direction and session_direction != 0
    reversal_magnitude_pct = abs(session_return_pct) if reversed else 0.0

    # Maximum Adverse Excursion (MAE): largest move against OR direction during rest of session
    mae = 0.0
    for bar in rest_bars:
        if or_direction > 0:
            # Long opening — adverse = price going below OR close
            adverse = (or_close - bar["low"]) / or_close * 100.0
        else:
            # Short opening — adverse = price going above OR close
            adverse = (bar["high"] - or_close) / or_close * 100.0
        mae = max(mae, adverse)

    # Maximum Favorable Excursion (MFE): largest move with OR direction
    mfe = 0.0
    for bar in rest_bars:
        if or_direction > 0:
            favorable = (bar["high"] - or_close) / or_close * 100.0
        else:
            favorable = (or_close - bar["low"]) / or_close * 100.0
        mfe = max(mfe, favorable)

    return {
        "date": session_bars[0]["timestamp"].strftime("%Y-%m-%d"),
        "or_return_pct": round(or_return_pct, 4),
        "or_range_pct": round(or_range_pct, 4),
        "or_direction": or_direction,
        "or_volume": or_volume,
        "overnight_gap_pct": round(overnight_gap_pct, 4),
        "session_return_pct": round(session_return_pct, 4),
        "session_direction": session_direction,
        "reversed": reversed,
        "reversal_magnitude_pct": round(reversal_magnitude_pct, 4),
        "mae_pct": round(mae, 4),
        "mfe_pct": round(mfe, 4),
        "session_close": session_close,
        "n_bars": len(session_bars),
    }


def compute_percentile_ranks(values: list[float]) -> list[float]:
    """Compute percentile rank (0-100) for each value in list."""
    n = len(values)
    if n == 0:
        return []
    sorted_vals = sorted(values)
    ranks = []
    for v in values:
        # Count values <= v
        count_le = sum(1 for sv in sorted_vals if sv <= v)
        ranks.append(count_le / n * 100.0)
    return ranks


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Fisher's exact test for 2x2 contingency table.

    Table:
        |  Reversed | Continued |
    Top |     a     |     b     |
    Bot |     c     |     d     |

    Returns one-sided p-value: P(reversal rate in top >= observed | H0).
    Uses hypergeometric distribution.
    """
    n = a + b + c + d
    row1 = a + b
    col1 = a + c

    def log_factorial(x):
        return sum(math.log(i) for i in range(1, x + 1)) if x > 0 else 0.0

    log_denom = log_factorial(n)
    log_numer_const = (log_factorial(row1) + log_factorial(n - row1) +
                       log_factorial(col1) + log_factorial(n - col1))

    # Sum probabilities for all tables at least as extreme as observed
    p_value = 0.0
    for x in range(max(0, row1 + col1 - n), min(row1, col1) + 1):
        y = row1 - x
        z = col1 - x
        w = n - row1 - z
        if y < 0 or z < 0 or w < 0:
            continue
        log_p = (log_numer_const - log_denom -
                 log_factorial(x) - log_factorial(y) -
                 log_factorial(z) - log_factorial(w))
        prob = math.exp(log_p)
        # One-sided: is this table's top-row reversal rate >= observed?
        if x * (c + d) >= a * (c + d):  # x/(x+y) >= a/(a+b) simplified
            if (a + b) > 0 and (x + y) > 0:
                if x / (x + y) >= a / (a + b) - 1e-10:
                    p_value += prob
            elif (x + y) == 0:
                p_value += prob
    return min(p_value, 1.0)


def spearman_correlation(x: list[float], y: list[float]) -> tuple[float, float]:
    """Spearman rank correlation with approximate p-value."""
    n = len(x)
    if n < 3:
        return 0.0, 1.0

    def rank(values):
        sorted_indexed = sorted(enumerate(values), key=lambda p: p[1])
        ranks = [0.0] * n
        for rank_val, (orig_idx, _) in enumerate(sorted_indexed):
            ranks[orig_idx] = rank_val + 1
        return ranks

    rx = rank(x)
    ry = rank(y)

    d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    rho = 1.0 - (6.0 * d_sq) / (n * (n * n - 1))

    # Approximate p-value via t-distribution → normal approximation
    if abs(rho) >= 1.0:
        return rho, 0.0
    t_stat = rho * math.sqrt((n - 2) / (1 - rho * rho))
    p_value = 2.0 * 0.5 * math.erfc(abs(t_stat) / math.sqrt(2))
    return rho, p_value


def run_experiment():
    """Execute EXP-00009."""
    print("=" * 76)
    print("  RESEARCH EXPERIMENT EXP-00009: OPENING RANGE EXHAUSTION & REVERSAL")
    print("  Canonical Research Question: RQ-001")
    print("  Predecessor: EXP-00008 (reversal finding)")
    print("=" * 76)
    print()

    if not DATA_PATH.exists():
        print(f"ERROR: Data file not found: {DATA_PATH}")
        return
    bars = load_bars(str(DATA_PATH))
    print(f"Loaded {len(bars)} bars from {DATA_PATH.name}")

    sessions = group_by_session(bars)
    session_dates = sorted(sessions.keys())
    print(f"Identified {len(session_dates)} trading sessions")
    print()

    # Analyze each session, tracking previous close for overnight gap
    results = []
    prev_close = None
    for date_key in session_dates:
        session_bars = sessions[date_key]
        r = analyze_session(session_bars, prev_close)
        if r is not None:
            results.append(r)
        # Update prev_close to last bar's close for overnight gap
        prev_close = session_bars[-1]["close"]

    print(f"Testable sessions: {len(results)}")
    print()

    if len(results) < 10:
        print("ABORT: Insufficient testable sessions.")
        return

    # --- Train / OOS Split ---
    split_idx = int(len(results) * 0.60)
    train = results[:split_idx]
    oos = results[split_idx:]
    print(f"Train: {len(train)} sessions ({train[0]['date']} to {train[-1]['date']})")
    print(f"OOS:   {len(oos)} sessions ({oos[0]['date']} to {oos[-1]['date']})")
    print()

    # --- Analysis for each split ---
    all_metrics = {}

    for label, data in [("TRAIN", train), ("OUT-OF-SAMPLE", oos)]:
        print(f"{'=' * 76}")
        print(f"  {label} ANALYSIS ({len(data)} sessions)")
        print(f"{'=' * 76}")
        print()

        # Compute percentile ranks within this split
        or_ranges = [r["or_range_pct"] for r in data]
        or_volumes = [r["or_volume"] for r in data]
        range_pctls = compute_percentile_ranks(or_ranges)
        vol_pctls = compute_percentile_ranks(or_volumes)

        for i, r in enumerate(data):
            r["or_range_percentile"] = round(range_pctls[i], 1)
            r["or_volume_percentile"] = round(vol_pctls[i], 1)

        # Quartile split by opening range magnitude
        sorted_by_range = sorted(data, key=lambda r: r["or_range_pct"])
        q_size = len(data) // 4
        if q_size < 1:
            q_size = 1
        bottom_q = sorted_by_range[:q_size]
        top_q = sorted_by_range[-q_size:]

        top_reversals = sum(1 for r in top_q if r["reversed"])
        top_continuations = len(top_q) - top_reversals
        bot_reversals = sum(1 for r in bottom_q if r["reversed"])
        bot_continuations = len(bottom_q) - bot_reversals

        top_rev_rate = top_reversals / len(top_q) * 100 if top_q else 0
        bot_rev_rate = bot_reversals / len(bottom_q) * 100 if bottom_q else 0

        fisher_p = fisher_exact_2x2(top_reversals, top_continuations,
                                     bot_reversals, bot_continuations)

        print(f"  1. QUARTILE ANALYSIS (Opening Range Magnitude)")
        print(f"     Top quartile ({len(top_q)} sessions):")
        print(f"       Reversal rate: {top_rev_rate:.1f}% ({top_reversals}/{len(top_q)})")
        print(f"       Mean OR range: {sum(r['or_range_pct'] for r in top_q)/len(top_q):.4f}%")
        print(f"     Bottom quartile ({len(bottom_q)} sessions):")
        print(f"       Reversal rate: {bot_rev_rate:.1f}% ({bot_reversals}/{len(bottom_q)})")
        print(f"       Mean OR range: {sum(r['or_range_pct'] for r in bottom_q)/len(bottom_q):.4f}%")
        print(f"     Fisher's exact p-value: {fisher_p:.4f}")
        print()

        # Spearman: OR magnitude vs reversal magnitude (for reversed sessions only)
        reversed_sessions = [r for r in data if r["reversed"]]
        if len(reversed_sessions) >= 3:
            sp_rho, sp_p = spearman_correlation(
                [r["or_range_pct"] for r in reversed_sessions],
                [r["reversal_magnitude_pct"] for r in reversed_sessions]
            )
        else:
            sp_rho, sp_p = 0.0, 1.0

        print(f"  2. CORRELATION ANALYSIS")
        print(f"     Reversed sessions: {len(reversed_sessions)}/{len(data)}")
        print(f"     Spearman(OR magnitude, reversal magnitude): rho={sp_rho:.3f}, p={sp_p:.4f}")
        print()

        # Spearman: OR magnitude vs MAE (all sessions)
        mae_rho, mae_p = spearman_correlation(
            [r["or_range_pct"] for r in data],
            [r["mae_pct"] for r in data]
        )
        print(f"     Spearman(OR magnitude, MAE): rho={mae_rho:.3f}, p={mae_p:.4f}")
        print()

        # Volume + Range interaction
        high_vol_high_range = [r for r in data
                               if r["or_volume_percentile"] >= 75
                               and r["or_range_percentile"] >= 75]
        if high_vol_high_range:
            hvhr_rev = sum(1 for r in high_vol_high_range if r["reversed"])
            hvhr_rate = hvhr_rev / len(high_vol_high_range) * 100
        else:
            hvhr_rev, hvhr_rate = 0, 0

        print(f"  3. VOLUME + RANGE INTERACTION")
        print(f"     High-volume + High-range sessions: {len(high_vol_high_range)}")
        print(f"     Reversal rate: {hvhr_rate:.1f}% ({hvhr_rev}/{len(high_vol_high_range)})")
        print()

        # Overnight gap analysis
        gapped = [r for r in data if abs(r["overnight_gap_pct"]) > 0.05]
        if gapped:
            gap_rev = sum(1 for r in gapped if r["reversed"])
            gap_rate = gap_rev / len(gapped) * 100
        else:
            gap_rev, gap_rate = 0, 0
        no_gap = [r for r in data if abs(r["overnight_gap_pct"]) <= 0.05]
        if no_gap:
            ng_rev = sum(1 for r in no_gap if r["reversed"])
            ng_rate = ng_rev / len(no_gap) * 100
        else:
            ng_rev, ng_rate = 0, 0

        print(f"  4. OVERNIGHT GAP ANALYSIS")
        print(f"     Sessions with gap (>5bp): {len(gapped)}, reversal rate: {gap_rate:.1f}%")
        print(f"     Sessions without gap:     {len(no_gap)}, reversal rate: {ng_rate:.1f}%")
        print()

        # Summary statistics
        all_rev_rate = sum(1 for r in data if r["reversed"]) / len(data) * 100
        mean_mae = sum(r["mae_pct"] for r in data) / len(data)
        mean_mfe = sum(r["mfe_pct"] for r in data) / len(data)

        print(f"  5. SUMMARY STATISTICS")
        print(f"     Overall reversal rate:  {all_rev_rate:.1f}%")
        print(f"     Mean MAE:               {mean_mae:.4f}%")
        print(f"     Mean MFE:               {mean_mfe:.4f}%")
        print(f"     MAE/MFE ratio:          {mean_mae/mean_mfe:.2f}" if mean_mfe > 0 else "")
        print()

        # Session detail
        print(f"  {'Date':<12} {'OR%':>7} {'OR Rng%':>8} {'RngPctl':>8} {'Vol':>10} {'VolPctl':>8} {'Gap%':>7} {'Sess%':>8} {'Rev?':>5} {'MAE%':>7} {'MFE%':>7}")
        print(f"  {'-'*12} {'-'*7} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*7} {'-'*8} {'-'*5} {'-'*7} {'-'*7}")
        for r in data:
            rev = "YES" if r["reversed"] else "NO"
            print(f"  {r['date']:<12} {r['or_return_pct']:>7.3f} {r['or_range_pct']:>8.4f} {r['or_range_percentile']:>8.1f} {r['or_volume']:>10.0f} {r['or_volume_percentile']:>8.1f} {r['overnight_gap_pct']:>7.3f} {r['session_return_pct']:>8.4f} {rev:>5} {r['mae_pct']:>7.4f} {r['mfe_pct']:>7.4f}")
        print()

        all_metrics[label] = {
            "sessions": len(data),
            "overall_reversal_rate_pct": round(all_rev_rate, 2),
            "top_quartile_reversal_rate_pct": round(top_rev_rate, 1),
            "bottom_quartile_reversal_rate_pct": round(bot_rev_rate, 1),
            "fisher_p_value": round(fisher_p, 4),
            "spearman_or_vs_rev_rho": round(sp_rho, 3),
            "spearman_or_vs_rev_p": round(sp_p, 4),
            "spearman_or_vs_mae_rho": round(mae_rho, 3),
            "spearman_or_vs_mae_p": round(mae_p, 4),
            "high_vol_high_range_sessions": len(high_vol_high_range),
            "high_vol_high_range_reversal_pct": round(hvhr_rate, 1),
            "gap_sessions": len(gapped),
            "gap_reversal_pct": round(gap_rate, 1),
            "mean_mae_pct": round(mean_mae, 4),
            "mean_mfe_pct": round(mean_mfe, 4),
            "reversed_sessions_count": len(reversed_sessions),
        }

    # --- Governance Gate ---
    oos_m = all_metrics["OUT-OF-SAMPLE"]
    train_m = all_metrics["TRAIN"]

    print("=" * 76)
    print("  GOVERNANCE GATE")
    print("=" * 76)

    checks = {}
    # Primary: top-quartile reversal rate > bottom-quartile
    checks["top_q_reversal_gt_bottom_q"] = oos_m["top_quartile_reversal_rate_pct"] > oos_m["bottom_quartile_reversal_rate_pct"]
    # Primary: Fisher p < 0.05
    checks["fisher_p_below_0.05"] = oos_m["fisher_p_value"] < 0.05
    # Secondary: Spearman OR vs reversal magnitude significant at Bonferroni α
    checks["spearman_or_rev_significant"] = oos_m["spearman_or_vs_rev_p"] < 0.0167
    # Secondary: Spearman OR vs MAE significant
    checks["spearman_or_mae_significant"] = oos_m["spearman_or_vs_mae_p"] < 0.0167
    # Consistency: train and OOS directionally consistent
    train_top_gt_bot = train_m["top_quartile_reversal_rate_pct"] > train_m["bottom_quartile_reversal_rate_pct"]
    oos_top_gt_bot = oos_m["top_quartile_reversal_rate_pct"] > oos_m["bottom_quartile_reversal_rate_pct"]
    checks["train_oos_directionally_consistent"] = train_top_gt_bot == oos_top_gt_bot

    all_primary_passed = checks["top_q_reversal_gt_bottom_q"] and checks["fisher_p_below_0.05"]

    for check_name, passed in checks.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {check_name}: {passed}")
    print()

    decision = "PROMOTED" if all_primary_passed else "REJECTED"
    if not all_primary_passed:
        # Check if we have partial evidence worth refining
        if checks["top_q_reversal_gt_bottom_q"] or oos_m["spearman_or_vs_mae_rho"] > 0.2:
            decision = "REFINED"

    print(f"  DECISION: {decision}")
    print()
    if decision != "PROMOTED":
        failed = [k for k, v in checks.items() if not v]
        if failed:
            print(f"  Issues: {', '.join(failed)}")
        print()

    # --- Build evidence bundle ---
    evidence = {
        "experiment_id": "EXP-00009",
        "predecessor": "EXP-00008",
        "canonical_research_question": "RQ-001",
        "hypothesis": "Large opening imbalances increase intraday reversal probability via liquidity exhaustion",
        "economic_mechanism": "MOO flow exhaustion -> institutional completion -> liquidity provider mean-reversion",
        "instrument": "SPY",
        "timeframe": "15m",
        "data_source": str(DATA_PATH.name),
        "total_sessions": len(results),
        "train_period": {"start": train[0]["date"], "end": train[-1]["date"], "sessions": len(train)},
        "oos_period": {"start": oos[0]["date"], "end": oos[-1]["date"], "sessions": len(oos)},
        "train_metrics": all_metrics["TRAIN"],
        "oos_metrics": all_metrics["OUT-OF-SAMPLE"],
        "governance_checks": checks,
        "decision": decision,
        "preregistered_thresholds": {
            "fisher_alpha": 0.05,
            "bonferroni_alpha": 0.0167,
            "min_quartile_sessions": 3,
        },
        "session_results": results,
        "execution_timestamp": datetime.now().isoformat(),
    }

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(f"Evidence bundle saved: {EVIDENCE_PATH}")
    print()
    print("=" * 76)
    print("  EXP-00009 COMPLETE")
    print("=" * 76)

    return evidence


if __name__ == "__main__":
    run_experiment()
