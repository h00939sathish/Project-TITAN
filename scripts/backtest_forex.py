"""Forex backtest smoke test — runs a trivial strategy on EUR/USD fixture data.

Implementation lives in scripts/backtest_smoke.py.

Usage:
    python scripts/backtest_forex.py
    python scripts/backtest_forex.py --live-data
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_smoke import (
    run_cli,
    run_forex_backtest,
    run_live_backtest,
)

__all__ = ["run_forex_backtest", "run_live_backtest"]

if __name__ == "__main__":
    run_cli(default_instrument="EURUSD")
