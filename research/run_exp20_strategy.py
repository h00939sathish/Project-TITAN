#!/usr/bin/env python3
"""EXP-00020 — strategy-level test: EURUSD short-rally reversal through the REAL engine.

Strategy (from EXP-00019 economics): when the reversal signal (negative of the
trailing 12h mid return) is in the top quintile and the bar is inside 12-16 UTC,
SHORT EURUSD (1000 units); cover exactly 60 bars (1h) later. Slippage = real
spread (~0.5 bps), commission 0.2 bps.

Threshold note: the top-quintile cutoff is calibrated in-sample on the same
2-month window (lookahead). A live variant needs rolling calibration; flagged as
a limitation, not a promotion.

Run:  python research/run_exp20_strategy.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from titan.backtest.engine import ReplayEngine

DATA = Path(__file__).resolve().parents[1] / "research" / "dukascopy_1m_ba"
LOOKBACK, HOLD = 720, 60  # 12h / 1h at 1-min


def mid(b: dict) -> float:
    return (b["c_ask"] + b["c_bid"]) / 2


class ShortRallyReversal:
    """Emits SELL at entry bars, BUY (cover) exactly HOLD bars later.

    threshold: scalar (in-sample) or list (rolling per-bar threshold).
    """

    def __init__(self, signal_series: list[float | None], threshold, rolling: bool = False):
        self._sig = signal_series
        self._thr = threshold
        self._rolling = rolling
        self._exit_at = None

    def _thr_at(self, i: int) -> float:
        return self._thr[i] if self._rolling else float(self._thr)

    def update(self, close: float) -> str | None:
        i = self._i = getattr(self, "_i", -1) + 1
        # exit the open short first (must happen before a new entry)
        if self._exit_at is not None:
            if i >= self._exit_at:
                self._exit_at = None
                return "BUY"
            return None
        s = self._sig[i] if i < len(self._sig) else None
        if s is not None and s >= self._thr_at(i):
            self._exit_at = i + HOLD
            return "SELL"
        return None


def main():
    bars = json.loads((DATA / "EURUSD.json").read_text(encoding="utf-8"))
    n = len(bars)
    print(f"EURUSD: {n} 1-min bars ({bars[0]['timestamp'][:10]} -> {bars[-1]['timestamp'][:10]})")

    mids = [mid(b) for b in bars]
    sig: list[float | None] = [None] * n
    for i in range(LOOKBACK, n):
        h = int(bars[i]["timestamp"][11:13])
        if 12 <= h <= 15:  # London/NY overlap
            sig[i] = -(mids[i] / mids[i - LOOKBACK] - 1.0)

    # ROLLING threshold: 80th percentile of the trailing 30 days of signals,
    # recomputed every 5 trading days (~6,000 bars). No lookahead.
    recalc_every = 6000
    window = 30 * 1200  # ~30 trading days of overlap bars
    threshold: list[float] = [0.0] * n
    cache: list[float] = []
    for i in range(n):
        if i % recalc_every == 0:
            lo = max(0, i - window)
            cache = sorted(s for s in sig[lo:i] if s is not None)
        if cache:
            threshold[i] = cache[int(len(cache) * 0.80)]
        else:
            threshold[i] = 0.0
    n_entries = sum(1 for i in range(n) if sig[i] is not None and sig[i] >= threshold[i])
    print(f"rolling 30d/5d top-quintile threshold (no lookahead): {n_entries} entry bars")

    engine_bars = [
        {"instrument_id": "EURUSD", "timestamp": b["timestamp"], "open": mid(b),
         "high": max(b["h_ask"], b["h_bid"]), "low": min(b["l_ask"], b["l_bid"]),
         "close": mid(b), "volume": b["n"]}
        for b in bars
    ]
    engine = ReplayEngine(
        ShortRallyReversal(sig, threshold, rolling=True),
        engine_bars,
        slippage_bps=0.5,
        commission_bps=0.2,
        intent_qty=1000,
    )
    result = engine.run()
    pnl = float(result.total_pnl)
    trades = int(result.trades)
    rej = int(result.rejected_intents)
    print(f"\ntrades={trades} | rejected={rej} | "
          f"total_pnl=${pnl:.2f} on 1000-unit lots (=$0.10/pip)")
    per_trade = pnl / max(trades, 1) * 10  # $ -> pips at micro-lot
    print(f"avg {per_trade:.2f} pips/trade net (in-sample version: +6.25)")
    print("\nCaveat: 12 months, rolling 30d threshold recalibrated every 5d, no lookahead;")
    print("no rollover (1h holds inside 12-16 UTC never cross 21:00 UTC).")


if __name__ == "__main__":
    main()
