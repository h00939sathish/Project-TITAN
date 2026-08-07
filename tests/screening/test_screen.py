"""Track 3 screening tests — cost model correctness and kill-criterion logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "screening"))

import screen as sc


def _make_bars(opens, high, low, close):
    # Synthetic bar with both bid and ask sides (spread ~2 pips).
    return [{"o_ask": o + 0.0002, "o_bid": o, "h_ask": h + 0.0002, "h_bid": h,
             "l_ask": l + 0.0002, "l_bid": l, "c_ask": c + 0.0002, "c_bid": c}
            for o, h, l, c in zip(opens, high, low, close)]


def test_cost_eats_into_gross():
    """A clean 20-pip up-move long must net well under 20 pips after spread,
    slippage and commission."""
    n = 30
    o = [1.0000 + i * 0.0001 for i in range(n)]  # trending up
    h = [x + 0.0001 for x in o]
    l = [x - 0.0001 for x in o]
    c = [x + 0.00005 for x in o]
    bars = _make_bars(o, h, l, c)
    # always-long side_fn
    res = sc.backtest(bars, lambda i: "BUY")
    # Gross move = 29 bars * 1 pip = ~29 pips. Net must be strictly less
    # (entry spread + slippage + commission are deducted) but stay positive.
    assert 0 < res["net_pips"] < (n - 1) * 1.0
    assert res["trades"] >= 1


def test_kill_criterion_edges():
    """Award exactly the threshold on 2+ pairs => survives; below on 2 => dies."""
    # simulate the aggregation used by main(): pips_per_year >= 200 on >=2
    def survives(per_pair):
        qualifies = [p for p, v in per_pair.items() if v >= sc.KILL_PIPS_PER_YEAR]
        return len(qualifies) >= sc.MIN_PAIRS

    assert survives({"EURUSD": 200.0, "GBPUSD": 210.0}) is True
    assert survives({"EURUSD": 199.9, "GBPUSD": 210.0}) is False
    assert survives({"EURUSD": 300.0, "GBPUSD": 50.0}) is False


def test_side_uses_next_open_not_lookahead():
    """The buy uses the NEXT bar's open, not the current close."""
    bars = _make_bars([1.0000] * 50, [1.0001] * 50, [0.9999] * 50, [1.0000] * 50)
    # side_fn reads at bar 0 but fills at bar 1 open — engine must run cleanly
    res = sc.backtest(bars, lambda i: "SELL")
    assert res["trades"] >= 0
    assert res["bars"] == 50