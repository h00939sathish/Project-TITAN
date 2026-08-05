"""Run a backtest from a fixture CSV and render the report as HTML."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from titan.data.ingest import read_csv
from titan.backtest.engine import ReplayEngine, BacktestResult
from titan._core import RiskConfig, Money


class _Strategy:
    def __init__(self):
        self._step = 0
    def update(self, price):
        self._step += 1
        if self._step == 1:
            return "BUY"
        if self._step == 5:
            return "SELL"
        return None


def _prepare_bars(csv_path: str) -> list[dict]:
    raw = read_csv(csv_path)
    bars = []
    for r in raw:
        bars.append({
            "instrument_id": r.get("symbol", "UNKNOWN"),
            "timestamp": r.get("date") or r.get("timestamp", ""),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": int(float(r.get("volume", 0))),
        })
    return bars


def run_backtest(fixture_path: str, cash: float = 100_000.0) -> BacktestResult:
    bars = _prepare_bars(fixture_path)
    replay = ReplayEngine(_Strategy(), bars, initial_capital=str(int(cash)))
    return replay.run()


def main():
    parser = argparse.ArgumentParser(description="Run backtest and render HTML report")
    parser.add_argument("--fixture", required=True, help="Path to fixture CSV")
    parser.add_argument("--output", default="report.html", help="Output HTML file path")
    parser.add_argument("--cash", type=float, default=100000.0, help="Starting cash")
    args = parser.parse_args()

    result = run_backtest(args.fixture, args.cash)
    from titan.render.report import render_qualification_report
    html = render_qualification_report(result, title=f"Backtest: {Path(args.fixture).name}")
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
