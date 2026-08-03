"""Formal Research Experiment EXP-00013: Execution Microstructure Alpha.

Canonical Research Question: RQ-003
    How much execution alpha exists through intelligent order placement
    (midpoint limit orders, TWAP/VWAP execution, dark pool routing)
    versus naive market order execution?

Hypothesis:
    Placing midpoint limit orders during high-volatility / high-spread sessions
    captures >= 35% of the bid-ask spread with fill rates > 80%, outperforming
    naive market order execution after accounting for transaction costs.
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

SPY_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "spy_15m.csv"
EURUSD_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "eurusd_15m.csv"
EVIDENCE_PATH = ROOT_DIR / "research" / "experiments" / "EXP-0013_evidence_bundle.json"


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


def evaluate_execution_alpha(bars: list[dict], inst_name: str, spread_bps: float = 1.5) -> dict:
    total_orders = len(bars) - 1
    filled_limit_orders = 0
    total_market_cost_bps = 0.0
    total_limit_cost_bps = 0.0

    for i in range(len(bars) - 1):
        close_price = bars[i]["close"]
        next_bar = bars[i + 1]
        
        # Naive market order execution pays half-spread + 0.5 bps slippage
        market_cost = (spread_bps / 2.0) + 0.5
        total_market_cost_bps += market_cost

        # Midpoint limit order placed at close_price
        # Filled if next bar trades through close_price
        midpoint_target = close_price
        if next_bar["low"] <= midpoint_target <= next_bar["high"]:
            filled_limit_orders += 1
            # Midpoint fill saves half-spread
            limit_cost = 0.5  # 0.5 bps friction only
        else:
            # Unfilled limit order falls back to market order with 1 bar delay friction
            limit_cost = market_cost + 0.5

        total_limit_cost_bps += limit_cost

    fill_rate = (filled_limit_orders / total_orders) if total_orders > 0 else 0.0
    avg_market_cost = total_market_cost_bps / max(total_orders, 1)
    avg_limit_cost = total_limit_cost_bps / max(total_orders, 1)
    spread_capture = ((avg_market_cost - avg_limit_cost) / avg_market_cost) if avg_market_cost > 0 else 0.0

    return {
        "instrument": inst_name,
        "total_orders": total_orders,
        "fill_rate": round(fill_rate, 4),
        "avg_market_cost_bps": round(avg_market_cost, 2),
        "avg_limit_cost_bps": round(avg_limit_cost, 2),
        "spread_capture": round(spread_capture, 4),
    }


def main() -> int:
    print("============================================================================")
    print("  RESEARCH EXPERIMENT EXP-00013: EXECUTION MICROSTRUCTURE ALPHA (RQ-003)")
    print("============================================================================")

    spy_bars = load_bars(SPY_PATH)
    eurusd_bars = load_bars(EURUSD_PATH)

    spy_res = evaluate_execution_alpha(spy_bars, "SPY", spread_bps=1.0)
    eurusd_res = evaluate_execution_alpha(eurusd_bars, "EURUSD", spread_bps=1.5)

    print(f"\n  SPY Fill Rate: {spy_res['fill_rate'] * 100:.1f}%, Spread Capture: {spy_res['spread_capture'] * 100:.1f}%")
    print(f"  EURUSD Fill Rate: {eurusd_res['fill_rate'] * 100:.1f}%, Spread Capture: {eurusd_res['spread_capture'] * 100:.1f}%")

    # Preregistered evaluation criteria: >35% spread capture and >80% fill rate
    passed_spy = spy_res["spread_capture"] >= 0.35 and spy_res["fill_rate"] >= 0.80
    passed_eurusd = eurusd_res["spread_capture"] >= 0.35 and eurusd_res["fill_rate"] >= 0.80

    decision = "REFINED" if (passed_spy or passed_eurusd) else "REJECTED"

    evidence_bundle = {
        "experiment_id": "EXP-00013",
        "canonical_rq": "RQ-003",
        "title": "Execution Microstructure Alpha & Limit Order Timing",
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
