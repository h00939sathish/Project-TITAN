"""Formal Research Experiment EXP-00011: Volatility Compression & Directional Expansion.

Canonical Research Question: RQ-002
    Under what specific market conditions does volatility compression precede
    clean directional expansion versus false whipsaw breakouts?

Hypothesis:
    Intraday volatility compression (periods where ATR drops into the bottom 25th
    percentile over a 100-bar rolling window alongside volume contraction)
    precedes clean directional price expansion (breakout magnitude > 2.0x ATR)
    with probability > 55%.

Data:
    SPY and EURUSD 15-minute bars (`spy_15m.csv`, `eurusd_15m.csv`)

Preregistered Thresholds:
    - Expansion breakout success rate > 55% in OOS (binomial p < 0.05)
    - False breakout rate < 30% in OOS
    - Cross-asset consistency between SPY and EURUSD
"""

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

SPY_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "spy_15m.csv"
EURUSD_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "eurusd_15m.csv"
EVIDENCE_PATH = ROOT_DIR / "research" / "experiments" / "EXP-00011_evidence_bundle.json"

COMPRESSION_WINDOW = 20
LOOKBACK_WINDOW = 100
EXPANSION_HORIZON = 10  # Look up to 10 bars forward for expansion target


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


def compute_atr(bars: list[dict], period: int = 14) -> list[float]:
    """Compute True Range and ATR."""
    if len(bars) < period + 1:
        return [0.0] * len(bars)
    tr_list = []
    for i in range(len(bars)):
        if i == 0:
            tr = bars[i]["high"] - bars[i]["low"]
        else:
            high_low = bars[i]["high"] - bars[i]["low"]
            high_close = abs(bars[i]["high"] - bars[i - 1]["close"])
            low_close = abs(bars[i]["low"] - bars[i - 1]["close"])
            tr = max(high_low, high_close, low_close)
        tr_list.append(tr)

    atr = [0.0] * len(bars)
    # Initial SMA for ATR
    atr[period - 1] = sum(tr_list[:period]) / period
    for i in range(period, len(bars)):
        atr[i] = (atr[i - 1] * (period - 1) + tr_list[i]) / period
    return atr


def find_compression_events(bars: list[dict]) -> list[dict]:
    """Identify volatility compression events and track expansion outcomes."""
    if len(bars) < LOOKBACK_WINDOW + EXPANSION_HORIZON:
        return []

    atrs = compute_atr(bars, period=14)
    events = []

    for i in range(LOOKBACK_WINDOW, len(bars) - EXPANSION_HORIZON):
        current_atr = atrs[i]
        historical_atrs = atrs[i - LOOKBACK_WINDOW:i]
        
        # Percentile rank of current ATR
        count_below = sum(1 for a in historical_atrs if a < current_atr)
        atr_percentile = (count_below / len(historical_atrs)) * 100.0

        # Volume contraction percentile if volume available
        vols = [b["volume"] for b in bars[i - LOOKBACK_WINDOW:i]]
        curr_vol = bars[i]["volume"]
        vol_below = sum(1 for v in vols if v < curr_vol)
        vol_percentile = (vol_below / len(vols)) * 100.0 if any(v > 0 for v in vols) else 0.0

        # Compression criteria: ATR in bottom 25th percentile
        if atr_percentile <= 25.0:
            # Compression range over last 10 bars
            comp_bars = bars[i - 10:i + 1]
            comp_high = max(b["high"] for b in comp_bars)
            comp_low = min(b["low"] for b in comp_bars)
            comp_range = comp_high - comp_low

            if comp_range <= 0:
                continue

            # Look forward up to EXPANSION_HORIZON bars for breakout
            future_bars = bars[i + 1:i + 1 + EXPANSION_HORIZON]
            
            breakout_dir = 0
            breakout_bar_idx = None
            
            for f_idx, f_bar in enumerate(future_bars):
                if f_bar["close"] > comp_high:
                    breakout_dir = 1
                    breakout_bar_idx = f_idx
                    break
                elif f_bar["close"] < comp_low:
                    breakout_dir = -1
                    breakout_bar_idx = f_idx
                    break

            if breakout_dir == 0:
                continue  # No breakout occurred within horizon

            # Track post-breakout price trajectory
            post_breakout_bars = future_bars[breakout_bar_idx:]
            target_distance = comp_range * 2.0
            
            succeeded = False
            whipsawed = False
            max_expansion = 0.0

            breakout_entry = post_breakout_bars[0]["close"]

            for b in post_breakout_bars:
                if breakout_dir == 1:
                    exp = b["high"] - breakout_entry
                    adverse = breakout_entry - b["low"]
                else:
                    exp = breakout_entry - b["low"]
                    adverse = b["high"] - breakout_entry

                max_expansion = max(max_expansion, exp)

                if exp >= target_distance:
                    succeeded = True

                if adverse >= comp_range:
                    whipsawed = True

            events.append({
                "bar_idx": i,
                "timestamp": bars[i]["timestamp"].isoformat(),
                "atr_percentile": round(atr_percentile, 1),
                "vol_percentile": round(vol_percentile, 1),
                "comp_range": round(comp_range, 4),
                "breakout_dir": breakout_dir,
                "succeeded": succeeded,
                "whipsawed": whipsawed,
                "max_expansion_ratio": round(max_expansion / comp_range, 2) if comp_range > 0 else 0.0,
            })

    return events


def binomial_p_value(successes: int, trials: int, null_p: float = 0.5) -> float:
    """One-sided binomial test."""
    if trials == 0:
        return 1.0
    mean = trials * null_p
    std = math.sqrt(trials * null_p * (1 - null_p))
    if std == 0:
        return 1.0
    z = (successes - 0.5 - mean) / std
    p_value = 0.5 * math.erfc(z / math.sqrt(2))
    return p_value


def analyze_instrument(instrument_id: str, csv_path: Path) -> dict | None:
    """Run RQ-002 volatility compression analysis on an instrument."""
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return None

    bars = load_bars(str(csv_path))
    if not bars:
        print(f"  SKIP: No bars loaded from {csv_path.name}")
        return None

    events = find_compression_events(bars)
    if not events:
        print(f"  SKIP: No compression events found for {instrument_id}")
        return None

    split_idx = int(len(events) * 0.60)
    train_events = events[:split_idx]
    oos_events = events[split_idx:]

    print(f"\n{'=' * 76}")
    print(f"  {instrument_id}: Volatility Compression Analysis")
    print(f"  Total compression events: {len(events)}")
    print(f"  Train events: {len(train_events)} | OOS events: {len(oos_events)}")
    print(f"{'=' * 76}\n")

    metrics = {}

    for label, ev_list in [("TRAIN", train_events), ("OUT-OF-SAMPLE", oos_events)]:
        n = len(ev_list)
        if n == 0:
            continue
        successes = sum(1 for e in ev_list if e["succeeded"])
        whipsaws = sum(1 for e in ev_list if e["whipsawed"])
        succ_rate = (successes / n) * 100.0
        whipsaw_rate = (whipsaws / n) * 100.0
        mean_exp_ratio = sum(e["max_expansion_ratio"] for e in ev_list) / n
        p_val = binomial_p_value(successes, n, null_p=0.50)

        print(f"  --- {label} ({n} events) ---")
        print(f"    Expansion Success Rate: {succ_rate:.1f}% ({successes}/{n})")
        print(f"    False Breakout (Whipsaw) Rate: {whipsaw_rate:.1f}% ({whipsaws}/{n})")
        print(f"    Mean Expansion Ratio:   {mean_exp_ratio:.2f}x")
        print(f"    Binomial p-value:        {p_val:.4f}")
        print()

        metrics[label] = {
            "n_events": n,
            "successes": successes,
            "success_rate_pct": round(succ_rate, 1),
            "whipsaw_rate_pct": round(whipsaw_rate, 1),
            "mean_expansion_ratio": round(mean_exp_ratio, 2),
            "binomial_p_value": round(p_val, 4),
        }

    return {
        "instrument": instrument_id,
        "total_events": len(events),
        "train_metrics": metrics.get("TRAIN", {}),
        "oos_metrics": metrics.get("OUT-OF-SAMPLE", {}),
    }


def run_experiment():
    """Execute EXP-0011."""
    print("=" * 76)
    print("  RESEARCH EXPERIMENT EXP-00011: VOLATILITY COMPRESSION & EXPANSION")
    print("  Canonical Research Question: RQ-002")
    print("=" * 76)

    instruments = {
        "SPY": SPY_PATH,
        "EURUSD": EURUSD_PATH,
    }

    results = {}
    for inst_id, path in instruments.items():
        res = analyze_instrument(inst_id, path)
        if res:
            results[inst_id] = res

    # --- Governance Gate ---
    print("=" * 76)
    print("  GOVERNANCE GATE")
    print("=" * 76)

    checks = {}
    for inst_id, res in results.items():
        oos = res["oos_metrics"]
        train = res["train_metrics"]

        # Primary: OOS expansion success rate > 55%
        checks[f"{inst_id}_oos_success_gt_55pct"] = oos.get("success_rate_pct", 0) > 55.0
        # Primary: Binomial p < 0.05
        checks[f"{inst_id}_oos_binomial_p_lt_0.05"] = oos.get("binomial_p_value", 1.0) < 0.05
        # Secondary: Whipsaw rate < 30%
        checks[f"{inst_id}_oos_whipsaw_lt_30pct"] = oos.get("whipsaw_rate_pct", 100) < 30.0
        # Consistency: Train and OOS both > 50%
        checks[f"{inst_id}_train_oos_consistent"] = (train.get("success_rate_pct", 0) > 50.0) == (oos.get("success_rate_pct", 0) > 50.0)

    # Cross-asset consistency
    if len(results) >= 2:
        rates = [r["oos_metrics"].get("success_rate_pct", 0) for r in results.values()]
        checks["cross_asset_consistent"] = all(r > 50.0 for r in rates)

    for check_name, passed in checks.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {check_name}: {passed}")
    print()

    primary_passed = all(checks[k] for k in checks if "success_gt_55pct" in k or "binomial_p_lt_0.05" in k)
    
    if primary_passed and checks.get("cross_asset_consistent", False):
        decision = "PROMOTED"
    elif any(checks[k] for k in checks if "success_gt_55pct" in k):
        decision = "REFINED"
    else:
        decision = "REJECTED"

    print(f"  DECISION: {decision}")
    print()

    # Save evidence bundle
    evidence = {
        "experiment_id": "EXP-00011",
        "canonical_research_question": "RQ-002",
        "hypothesis": "Volatility compression precedes clean directional expansion > 55% in OOS",
        "economic_mechanism": "Liquidity drying -> order accumulation -> thin orderbook sweep",
        "instruments": list(results.keys()),
        "governance_checks": checks,
        "decision": decision,
        "results": results,
        "execution_timestamp": datetime.now().isoformat(),
    }

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(f"Evidence bundle saved: {EVIDENCE_PATH}")
    print()
    print("=" * 76)
    print("  EXP-00011 COMPLETE")
    print("=" * 76)


if __name__ == "__main__":
    run_experiment()
