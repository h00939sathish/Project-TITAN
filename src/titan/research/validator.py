"""Validation framework — automatic checks on every experiment.

Now with bootstrap CI, temporal stability, and multi-instrument support.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def compute_ic(feature_values: list[float | None], target_values: list[float | None]) -> float:
    """Spearman rank correlation between feature and forward returns."""
    pairs = [(f, t) for f, t in zip(feature_values, target_values)
             if f is not None and t is not None and not (isinstance(f, float) and math.isnan(f))]
    if len(pairs) < 10:
        return 0.0
    f_vals, t_vals = zip(*pairs)
    f_ranks = _rank(f_vals)
    t_ranks = _rank(t_vals)
    n = len(pairs)
    mean_f = sum(f_ranks) / n
    mean_t = sum(t_ranks) / n
    cov = sum((fr - mean_f) * (tr - mean_t) for fr, tr in zip(f_ranks, t_ranks))
    std_f = math.sqrt(sum((fr - mean_f) ** 2 for fr in f_ranks))
    std_t = math.sqrt(sum((tr - mean_t) ** 2 for tr in t_ranks))
    if std_f == 0 or std_t == 0:
        return 0.0
    return cov / (std_f * std_t)


def bootstrap_ic(
    feature_values: list[float | None],
    target_values: list[float | None],
    n_iterations: int = 1000,
) -> dict:
    """Bootstrap the IC to get distribution, median, and confidence interval."""
    pairs = [(f, t) for f, t in zip(feature_values, target_values)
             if f is not None and t is not None]
    if len(pairs) < 10:
        return {
            "median_ic": 0.0, "mean_ic": 0.0, "ci_lower": 0.0, "ci_upper": 0.0,
            "p_gt_0": 0.0, "p_lt_0": 0.0, "n_iterations": 0,
        }

    ics: list[float] = []
    n = len(pairs)
    for _ in range(n_iterations):
        sample = random.choices(pairs, k=n)
        f_s, t_s = zip(*sample)
        ic = compute_ic(list(f_s), list(t_s))
        ics.append(ic)

    ics.sort()
    median = ics[n_iterations // 2]
    mean_ic = sum(ics) / n_iterations
    lower = ics[int(n_iterations * 0.025)]
    upper = ics[int(n_iterations * 0.975)]
    p_gt_0 = sum(1 for ic in ics if ic > 0) / n_iterations
    p_lt_0 = 1.0 - p_gt_0

    return {
        "median_ic": median,
        "mean_ic": mean_ic,
        "ci_lower": lower,
        "ci_upper": upper,
        "p_gt_0": p_gt_0,
        "p_lt_0": p_lt_0,
        "n_iterations": n_iterations,
    }


def temporal_stability(
    feature_values: list[float | None],
    target_values: list[float | None],
    n_splits: int = 3,
) -> list[dict]:
    """Split the sample into N equal periods and compute IC for each."""
    pairs = [(f, t) for f, t in zip(feature_values, target_values)
             if f is not None and t is not None]
    if len(pairs) < 20:
        return []

    chunk_size = len(pairs) // n_splits
    results = []
    for i in range(n_splits):
        start = i * chunk_size
        end = start + chunk_size if i < n_splits - 1 else len(pairs)
        chunk = pairs[start:end]
        f_chunk, t_chunk = zip(*chunk)
        ic = compute_ic(list(f_chunk), list(t_chunk))
        results.append({
            "period": i,
            "start_idx": start,
            "end_idx": end,
            "n": len(chunk),
            "ic": ic,
        })
    return results


def cross_instrument_ic(
    instrument_results: dict[str, dict],
) -> dict:
    """Aggregate ICs across multiple instruments.

    Reports mean IC, min/max, and consistency (fraction with same sign).
    """
    ics = []
    for inst, result in instrument_results.items():
        if result.get("ic") is not None:
            ics.append((inst, result["ic"]))

    if not ics:
        return {"mean_ic": 0.0, "min_ic": 0.0, "max_ic": 0.0, "sign_consistency": 0.0}

    ic_vals = [ic for _, ic in ics]
    mean_ic = sum(ic_vals) / len(ic_vals)
    positive_count = sum(1 for ic in ic_vals if ic > 0)
    sign_consistency = max(positive_count, len(ic_vals) - positive_count) / len(ic_vals)

    return {
        "mean_ic": mean_ic,
        "min_ic": min(ic_vals),
        "max_ic": max(ic_vals),
        "sign_consistency": sign_consistency,
        "instrument_count": len(ic_vals),
        "per_instrument": dict(ics),
    }


def compute_p_value(ic: float, n: int) -> float:
    """Approximate p-value for the IC."""
    if n < 3 or abs(ic) >= 1.0:
        return 1.0
    t_stat = ic * math.sqrt((n - 2) / (1 - ic * ic))
    z = abs(t_stat)
    p = math.erfc(z / math.sqrt(2))
    return p


def check_sample_size(n: int, min_samples: int = 100) -> tuple[bool, str]:
    if n < 30:
        return False, f"Too few samples ({n})"
    if n < min_samples:
        return False, f"Sample size {n} < min {min_samples}"
    return True, f"Sample size {n} ✓"


def check_ic_significance(ic: float, n: int, threshold: float = 0.03) -> tuple[bool, str]:
    p = compute_p_value(ic, n)
    if abs(ic) < threshold:
        return False, f"IC {ic:.4f} below threshold {threshold}"
    if p > 0.05:
        return False, f"IC {ic:.4f} not significant (p={p:.4f})"
    return True, f"IC {ic:.4f} (p={p:.4f}) ✓"


def check_bootstrap_stability(bootstrap_result: dict) -> tuple[bool, str]:
    ci_lower = bootstrap_result.get("ci_lower", 0)
    ci_upper = bootstrap_result.get("ci_upper", 0)
    if ci_lower < 0 and ci_upper > 0:
        return False, f"CI crosses zero [{ci_lower:.4f}, {ci_upper:.4f}]"
    return True, f"CI [{ci_lower:.4f}, {ci_upper:.4f}] same sign ✓"


def check_temporal_consistency(periods: list[dict]) -> tuple[bool, str]:
    if not periods:
        return False, "No temporal data"
    ics = [p["ic"] for p in periods]
    sign_flips = sum(1 for i in range(1, len(ics)) if (ics[i] > 0) != (ics[i-1] > 0))
    if sign_flips > len(ics) // 2:
        return False, f"Sign flips {sign_flips}/{len(ics)-1} periods"
    return True, f"IC consistent across {len(periods)} periods [{', '.join(f'{ic:.3f}' for ic in ics)}] ✓"


def check_cross_instrument_consistency(
    cross_result: dict, min_consistency: float = 0.66,
) -> tuple[bool, str]:
    if cross_result.get("instrument_count", 0) < 2:
        return False, "Need ≥2 instruments"
    consistency = cross_result["sign_consistency"]
    if consistency < min_consistency:
        return False, f"Sign consistency {consistency:.0%} < {min_consistency:.0%}"
    return True, f"Sign consistency {consistency:.0%} across {cross_result['instrument_count']} instruments ✓"


def check_cost_sensitivity(
    feature_values: list[float | None],
    target_values: list[float | None],
    cost_bps: float = 10.0,
) -> tuple[bool, str]:
    """Adjust forward returns by transaction costs and re-check."""
    cost_decimal = cost_bps / 10000.0
    pairs = [(f, t) for f, t in zip(feature_values, target_values)
             if f is not None and t is not None]
    if len(pairs) < 10:
        return False, "Insufficient data for cost check"

    f_vals = [p[0] for p in pairs]
    median = statistics.median(f_vals)
    above = [p[1] for p in pairs if p[0] >= median]
    below = [p[1] for p in pairs if p[0] < median]

    if not above or not below:
        return False, "No split possible"

    gross_mean_above = sum(above) / len(above)
    gross_mean_below = sum(below) / len(below)
    gross_spread = gross_mean_above - gross_mean_below
    net_spread = gross_spread - 2 * cost_decimal

    if net_spread <= 0:
        return False, f"Net spread {net_spread:.4f} <= 0 after {cost_bps} bps"
    return True, f"Net spread {net_spread:.4f} survives {cost_bps} bps"


@dataclass
class ResearchDecision:
    """Explicit decision recorded for every experiment.

    Status hierarchy:
      Promote — strong evidence, ready for strategy design
      Refine — promising but incomplete (small sample, borderline IC)
      Reject — evidence doesn't support the hypothesis
      Archive — invalid methodology, no longer relevant
    """

    status: str  # "promote", "refine", "reject", "archive"
    confidence: str  # "high", "medium", "low"
    reasons: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summary(self) -> str:
        return f"Decision: {self.status.upper()} (confidence: {self.confidence})\n  Reasons:\n" + \
               "\n".join(f"    - {r}" for r in self.reasons)


def make_decision(
    checks: dict[str, bool | str],
    bootstrap: dict,
    temporal: list[dict],
    cross_instrument: dict | None = None,
    experiment_index: int = 0,
    total_experiments: int = 1,
    expected_sign: int = 0,
) -> ResearchDecision:
    """Automatically generate a research decision from validation results.

    When running batches of experiments, pass experiment_index and
    total_experiments for Bonferroni-adjusted significance thresholds.

    expected_sign: 0 = non-directional hypothesis; +1 = hypothesis predicts a
    POSITIVE IC; -1 = predicts a NEGATIVE IC. A significant IC of the OPPOSITE
    sign falsifies a directional hypothesis (e.g. "momentum" is falsified by a
    strongly negative IC) and yields REJECT with high confidence.
    """
    failures: list[str] = []
    for check, result in checks.items():
        if result is False:
            failures.append(check)
        elif isinstance(result, str) and "❌" in result:
            failures.append(check)

    reasons: list[str] = []

    # Bonferroni adjustment: more experiments → stricter evidence needed
    alpha = 0.05 / max(total_experiments, 1)
    if total_experiments > 1:
        reasons.append(f"Bonferroni-adjusted alpha: {alpha:.4f} ({total_experiments} experiments)")

    if failures:
        reasons.extend(f"Failed check: {f}" for f in failures)

    # Bootstrap
    ci_lower = bootstrap.get("ci_lower", 0)
    ci_upper = bootstrap.get("ci_upper", 0)
    ci_crosses_zero = ci_lower < 0 and ci_upper > 0
    if ci_crosses_zero:
        reasons.append(f"Bootstrap CI crosses zero [{ci_lower:.3f}, {ci_upper:.3f}]")

    # Directional falsification: a significant IC with the OPPOSITE sign to the
    # hypothesis is a REAL effect but NOT the hypothesized one.
    direction_contradicted = False
    if expected_sign > 0 and ci_upper < 0:
        direction_contradicted = True
        reasons.append(
            f"IC is significantly NEGATIVE [{ci_lower:.3f}, {ci_upper:.3f}] while the "
            f"hypothesis expects positive — hypothesis FALSIFIED (evidence supports "
            f"the opposite direction)"
        )
    elif expected_sign < 0 and ci_lower > 0:
        direction_contradicted = True
        reasons.append(
            f"IC is significantly POSITIVE [{ci_lower:.3f}, {ci_upper:.3f}] while the "
            f"hypothesis expects negative — hypothesis FALSIFIED (evidence supports "
            f"the opposite direction)"
        )
    if direction_contradicted:
        return ResearchDecision("reject", "high", reasons)

    # Temporal
    if temporal:
        ics = [p["ic"] for p in temporal]
        sign_flips = sum(1 for i in range(1, len(ics)) if (ics[i] > 0) != (ics[i-1] > 0))
        if sign_flips > 0:
            reasons.append(f"IC sign flipped in {sign_flips}/{len(ics)-1} temporal splits")

    # Cross-instrument
    cross_weak = False
    if cross_instrument and cross_instrument.get("instrument_count", 0) >= 2:
        consistency = cross_instrument.get("sign_consistency", 0)
        if consistency < 1.0:
            cross_weak = True
            reasons.append(f"Not all instruments agree (consistency {consistency:.0%})")

    # Decision logic
    critical_failures = [f for f in failures if f in (
        "IC statistically significant", "Bootstrap CI same sign",
    )]
    sample_ok = all("Sample size" not in f for f in failures)
    costs_ok = all("transaction costs" not in f for f in failures)

    if not failures and not ci_crosses_zero and not cross_weak and sample_ok and costs_ok:
        return ResearchDecision("promote", "high", reasons)
    elif not critical_failures and len(failures) <= 1:
        return ResearchDecision("refine", "medium", reasons)
    elif "IC statistically significant" in str(failures) and not cross_weak:
        return ResearchDecision("refine", "medium", reasons)
    else:
        return ResearchDecision("reject", "low", reasons)


def run_validators(
    feature_values: list[float | None],
    target_values: list[float | None],
    experiment_id: str,
    dataset_id: str,
    cost_bps: float = 10.0,
    n_bootstrap: int = 1000,
) -> tuple[dict, dict, dict, dict]:
    """Run all validators. Returns (evidence_dict, checks, bootstraps, temporals).

    n_bootstrap trades CI precision for runtime — 1000 is default; 300 is ample
    for large samples (bootstrap CI converges with sample size).
    """
    ic = compute_ic(feature_values, target_values)
    n = sum(1 for f, t in zip(feature_values, target_values)
            if f is not None and t is not None)

    checks: dict[str, bool | str] = {}

    # 1. Sample size
    sample_ok, sample_msg = check_sample_size(n)
    checks["Sample size sufficient"] = sample_ok if sample_ok else sample_msg

    # 2. IC significance
    ic_ok, ic_msg = check_ic_significance(ic, n)
    checks["IC statistically significant"] = ic_ok if ic_ok else ic_msg

    # 3. Bootstrap
    bootstrap_result = bootstrap_ic(feature_values, target_values, n_bootstrap)
    boot_ok, boot_msg = check_bootstrap_stability(bootstrap_result)
    checks["Bootstrap CI same sign"] = boot_ok if boot_ok else boot_msg

    # 4. Temporal stability
    temporal_result = temporal_stability(feature_values, target_values, 3)
    temp_ok, temp_msg = check_temporal_consistency(temporal_result)
    checks["Temporal consistency"] = temp_ok if temp_ok else temp_msg

    # 5. Cost sensitivity
    cost_ok, cost_msg = check_cost_sensitivity(feature_values, target_values, cost_bps)
    checks["Survives transaction costs"] = cost_ok if cost_ok else cost_msg

    evidence = {
        "experiment_id": experiment_id,
        "dataset_id": dataset_id,
        "ic": ic,
        "p_value": compute_p_value(ic, n),
        "sample_size": n,
        "survived_costs": cost_ok,
        "bootstrap": bootstrap_result,
        "temporal": temporal_result,
    }

    return evidence, checks, bootstrap_result, temporal_result


def _rank(values):
    """Assign ranks (1-based, ties averaged). O(n log n) — count ties once via
    a Counter instead of sorted_vals.count(v) per value (which is O(n^2) and
    hangs on multi-thousand-row intraday datasets)."""
    from collections import Counter

    sorted_vals = sorted(values)
    counts = Counter(sorted_vals)
    rank_map = {}
    i = 0
    for v in sorted_vals:
        if v not in rank_map:
            tie_count = counts[v]
            rank_map[v] = (i + 1 + i + tie_count) / 2 if tie_count > 1 else i + 1
        i += 1
    return [rank_map[v] for v in values]
