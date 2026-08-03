"""Formal Research Experiment EXP-00007: Intraday Parameter Plateaus & Neighborhood Stability.

Research Question:
  Does a longer moving-average / indicator horizon reduce microstructure noise and reveal
  cross-instrument parameter plateaus on 15m and 1h intraday data?

Universe:
  SPY, QQQ, EURUSD, GBPUSD

Governance Gate:
  Requires Plateau Stability >= 0.70, Plateau Coverage >= 20%, and Cross-Instrument Consistency >= 75%
  before any candidate enters WATCHLIST.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from titan.research.optimizers.grid_search import GridSearchOptimizer
from titan.research.validators.parameter_stability import OptimizationRiskValidator
from titan.research.evidence_bundle import create_evidence_bundle
from titan.research.harness import load_bars, make_ma_signal_fn, make_dual_ma_signal_fn, make_rsi_signal_fn, make_bollinger_signal_fn, make_orb_signal_fn, make_vwap_signal_fn

DATA_DIR = ROOT_DIR / "research" / "intraday_backtests" / "tws_approved"
OUT_DIR = ROOT_DIR / "research" / "experiments"


PARAM_GRIDS = {
    "dual-ma": {
        "fast": [10, 20, 30, 50],
        "slow": [50, 100, 150, 200],
    },
    "ma-crossover": {
        "fast": [10, 20, 30, 50],
        "slow": [50, 100, 150, 200],
    },
    "rsi": {
        "window": [14, 21, 30, 50],
        "oversold": [30.0, 35.0],
        "overbought": [65.0, 70.0],
    },
    "bollinger": {
        "window": [20, 30, 50],
        "std_dev_multiplier": [1.5, 2.0, 2.5],
    },
    "orb": {
        "atr_period": [10, 14, 20],
        "min_volume_ratio": [1.0, 1.2, 1.5],
        "breakout_mult": [1.0, 1.1, 1.2],
    },
    "vwap-reversion": {
        "window": [20, 30, 50],
        "std_dev": [1.5, 2.0, 2.5],
    },
}

DATASETS = [
    {"symbol": "EURUSD", "tf": "15m", "file": "eurusd_15m_tws.csv"},
    {"symbol": "EURUSD", "tf": "1h", "file": "eurusd_1h_tws.csv"},
    {"symbol": "SPY", "tf": "1h", "file": "spy_1h_tws.csv"},
]


def load_tws_bars(csv_path: str) -> list[dict]:
    """Parse official TWS intraday CSV bar records into normalized dicts."""
    import csv
    bars = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                b = {
                    "timestamp": row.get("timestamp", "").strip(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                }
                bars.append(b)
            except (ValueError, KeyError):
                continue
    return bars


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("==========================================================================")
    print("  RESEARCH EXPERIMENT EXP-00007: INTRADAY PARAMETER PLATEAU VALIDATION")
    print("==========================================================================")
    print("Question: Does a longer horizon reduce microstructure noise and reveal robust plateaus?")
    print("Universe: EURUSD, SPY (15m, 1h)")
    print("Governance: Plateau Stability >= 0.70 | Coverage >= 20% | Cross-Consistency >= 75%\n")

    optimizer = GridSearchOptimizer(slippage_bps=1.0, commission_bps=1.0)
    validator = OptimizationRiskValidator(min_stability=0.70, min_coverage=0.20, min_cross_consistency=0.75)

    evidence_bundles = []

    for strategy_id, grid in PARAM_GRIDS.items():
        for tf in ["15m", "1h"]:
            surfaces = {}
            for ds in DATASETS:
                if ds["tf"] != tf:
                    continue
                path = DATA_DIR / ds["file"]
                if not path.exists():
                    continue
                bars = load_tws_bars(str(path))
                if len(bars) < 60:
                    continue

                surface = optimizer.optimize_strategy(
                    strategy_id=strategy_id,
                    timeframe=tf,
                    bars=bars,
                    instrument_id=ds["symbol"],
                    param_grid=grid,
                    train_ratio=0.60,  # 60% Train, 40% Validation Window
                )
                surfaces[ds["symbol"]] = surface

            if not surfaces:
                continue

            # Governance Validation Scorecard
            scorecard = validator.validate(strategy_id, tf, surfaces)
            print(scorecard.summary())
            print("")

            bundle = create_evidence_bundle(
                experiment_id="EXP-00007",
                question="Does a longer horizon reduce microstructure noise and reveal robust parameter plateaus on 15m and 1h data?",
                scorecard=scorecard,
                train_ratio=0.60,
            )
            evidence_bundles.append(bundle.to_dict())

    report_path = OUT_DIR / "EXP-00007_evidence_bundle.json"
    report_path.write_text(json.dumps(evidence_bundles, indent=2), encoding="utf-8")
    print("==========================================================================")
    print(f"  Saved Reproducible Evidence Bundle to {report_path}")
    print("==========================================================================")


if __name__ == "__main__":
    main()
