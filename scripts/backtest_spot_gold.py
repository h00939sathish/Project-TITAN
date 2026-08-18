"""Spot gold backtest smoke test — runs a trivial strategy on XAUUSD fixture data.

Implementation lives in scripts/backtest_smoke.py.

Usage:
    python scripts/backtest_spot_gold.py
    python scripts/backtest_spot_gold.py --live-data
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_smoke import (
    run_cli,
    run_spot_gold_backtest,
)
from scripts.backtest_smoke import (
    run_live_gold_backtest as run_live_backtest,
)

__all__ = ["run_spot_gold_backtest", "run_live_backtest"]

if __name__ == "__main__":
    run_cli(default_instrument="XAUUSD")
