"""Replay the registered traderdev-ema9-vwap candidate through the engine's
paper/replay cycle on real FX 4h data (EXP-00025 evidence). Paper only.
"""
import json, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/d/projects/Project TITAN")

import titan.strategies.registrations as regs
from titan.backtest.engine import ReplayEngine

ROOT = Path("D:/projects/Project TITAN")


def resample(raw, minutes):
    out, cur = [], None
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        key = int(dt.timestamp() // (minutes * 60))
        if cur is None or cur[0] != key:
            if cur:
                out.append(cur[1])
            cur = [key, {"timestamp": b["timestamp"],
                         "o_ask": b["o_ask"], "o_bid": b["o_bid"],
                         "h_ask": b["h_ask"], "h_bid": b["h_bid"],
                         "l_ask": b["l_ask"], "l_bid": b["l_bid"],
                         "c_ask": b["c_ask"], "c_bid": b["c_bid"], "n": b["n"]}]
        else:
            d = cur[1]
            d["h_ask"] = max(d["h_ask"], b["h_ask"]); d["h_bid"] = max(d["h_bid"], b["h_bid"])
            d["l_ask"] = min(d["l_ask"], b["l_ask"]); d["l_bid"] = min(d["l_bid"], b["l_bid"])
            d["c_ask"] = b["c_ask"]; d["c_bid"] = b["c_bid"]; d["n"] += b["n"]
    if cur:
        out.append(cur[1])
    return out


def run(pair, frame_mins, label):
    raw = json.loads((ROOT / "research/dukascopy_1m_ba" / f"{pair}.json")
                     .read_text(encoding="utf-8"))
    rows = resample(raw, frame_mins)
    bars = [{"instrument_id": pair, "timestamp": b["timestamp"],
             "open": (b["o_ask"] + b["o_bid"]) / 2,
             "high": max(b["h_ask"], b["h_bid"]), "low": min(b["l_ask"], b["l_bid"]),
             "close": (b["c_ask"] + b["c_bid"]) / 2, "volume": b["n"]}
            for b in rows]
    fn = regs.make_traderdev_ema9vwap_signal_fn(
        {"ema_period": 9, "vwap_period": 240, "atr_period": 14, "trail_mult": 3.0})
    # ReplayEngine calls strategy.update(close); the factory stashes the strat
    # object on .strat for exactly this.
    strat = fn.strat
    eng = ReplayEngine(strat, bars, slippage_bps=0.5, commission_bps=0.2, intent_qty=5000)
    res = eng.run()
    pips = float(res.total_pnl) / (5000 * 0.0001)
    print(f"{label:<18} trades={res.trades:>4}  pnl=${float(res.total_pnl):+10.2f}  "
          f"{pips:+8.1f} pips  rejected={res.rejected_intents}")
    return res


if __name__ == "__main__":
    print("registered ids contain traderdev-ema9-vwap:",
          "traderdev-ema9-vwap" in regs.get_registry().list_ids())
    for pair in ("EURUSD", "GBPUSD"):
        run(pair, 240, f"{pair} 4h")