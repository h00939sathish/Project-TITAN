"""Formal Research Experiment EXP-00015: Regime-Dependent Momentum Breakdown.

Canonical Research Question: RQ-005
    Which specific macroeconomic and volatility market regimes (VIX level,
    yield curve slope, sideways noise) invalidate time-series momentum
    and trend-following strategies?

Hypothesis:
    Time-series momentum strategies suffer statistically significant Sharpe
    degradation (Delta Sharpe > 0.8) during low-volatility / range-bound market
    regimes compared to high-trend regimes.
"""

import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

SPY_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "spy_15m.csv"
EURUSD_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "eurusd_15m.csv"
EVIDENCE_PATH = ROOT_DIR / "research" / "experiments" / "EXP-0015_evidence_bundle.json"


def load_bars(path: Path) -> list[dict]:
    bars = []
    if not path.exists():
        return bars
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("timestamp", "").strip()
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            try:
                bars.append({
                    "timestamp": ts,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
    return bars


def compute_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean_r = sum(returns) / len(returns)
    var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(var_r)
    return (mean_r / std_r * math.sqrt(252 * 26)) if std_r > 0 else 0.0


def evaluate_regime_momentum_breakdown(bars: list[dict], inst_name: str) -> dict:
    if len(bars) < 100:
        return {
            "instrument": inst_name,
            "trending_sharpe": 0.0,
            "rangebound_sharpe": 0.0,
            "sharpe_delta": 0.0,
        }

    trending_returns = []
    rangebound_returns = []

    for i in range(50, len(bars) - 1):
        # 50-bar rolling volatility / trend strength indicator
        closes = [b["close"] for b in bars[i - 50:i]]
        abs_range = max(closes) - min(closes)
        net_change = abs(closes[-1] - closes[0])
        efficiency_ratio = (net_change / abs_range) if abs_range > 0 else 0.0

        # Simple momentum return (1-bar forward)
        mom_dir = 1.0 if closes[-1] > closes[-2] else -1.0
        fwd_ret = (bars[i + 1]["close"] - bars[i]["close"]) / bars[i]["close"]
        strat_ret = mom_dir * fwd_ret

        if efficiency_ratio > 0.4:
            trending_returns.append(strat_ret)
        else:
            rangebound_returns.append(strat_ret)

    trending_sharpe = compute_sharpe(trending_returns)
    rangebound_sharpe = compute_sharpe(rangebound_returns)
    sharpe_delta = trending_sharpe - rangebound_sharpe

    return {
        "instrument": inst_name,
        "trending_sharpe": round(trending_sharpe, 2),
        "rangebound_sharpe": round(rangebound_sharpe, 2),
        "sharpe_delta": round(sharpe_delta, 2),
        "trending_bars": len(trending_returns),
        "rangebound_bars": len(rangebound_returns),
    }


def main() -> int:
    print("============================================================================")
    print("  RESEARCH EXPERIMENT EXP-00015: REGIME MOMENTUM BREAKDOWN (RQ-005)")
    print("============================================================================")

    spy_bars = load_bars(SPY_PATH)
    eurusd_bars = load_bars(EURUSD_PATH)

    spy_res = evaluate_regime_momentum_breakdown(spy_bars, "SPY")
    eurusd_res = evaluate_regime_momentum_breakdown(eurusd_bars, "EURUSD")

    print(f"\n  SPY Trending Sharpe: {spy_res['trending_sharpe']}, Rangebound: {spy_res['rangebound_sharpe']} (Delta: {spy_res['sharpe_delta']})")
    print(f"  EURUSD Trending Sharpe: {eurusd_res['trending_sharpe']}, Rangebound: {eurusd_res['rangebound_sharpe']} (Delta: {eurusd_res['sharpe_delta']})")

    # Preregistered evaluation criteria: Delta Sharpe > 0.8
    passed_spy = spy_res["sharpe_delta"] >= 0.8
    passed_eurusd = eurusd_res["sharpe_delta"] >= 0.8

    decision = "REFINED" if (passed_spy or passed_eurusd) else "REJECTED"

    evidence_bundle = {
        "experiment_id": "EXP-00015",
        "canonical_rq": "RQ-005",
        "title": "Regime-Dependent Momentum Breakdown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "results": {
            "SPY": spy_res,
            "EURUSD": eurusd_res,
        },
    }

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_PATH, "w") as f:
        json.dump(evidence_bundle, f, indent=2)

    print(f"\n  DECISION: {decision}")
    print(f"  Saved evidence bundle: {EVIDENCE_PATH}")
    print("============================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
