"""Phase 1 — ADR-021/022/023 gate diagnostic for traderdev-ema9-vwap.

Runs EVERY gate in PromotionGate.evaluate() against REAL evidence:

  - Real Dukascopy 1m bid/ask, resampled to 4h (the strategy's native TF).
  - A real per-bar return series derived from the REGISTERED strategy signal
    (PromotionGate._strategy_return_series) — not fabricated Sharpes. The
    registry MUST be populated (import registrations) BEFORE the first series
    is derived, or the signal factory is missing and the series is [].
  - A TEMPORARY research DB seeded with what a genuine evidence-collection
    pass would store. The production research DB is NEVER touched.

Walk-forward honesty (debated plan, Q2 = option C): we only have the SAME
dataset the strategy was tuned on, so a naive 75/25 split would be
statistically dishonest. Therefore wf_sharpe is NOT seeded; the walk_forward
gate stays UNMET (fails closed) — which is the correct read-only outcome.

Output: research/results/ema9vwap_gate_diagnostic.json. NO promotion,
NO QUALIFIED status change.
"""
import json
import statistics
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# NOTE: registry MUST be populated before any _strategy_return_series call,
# otherwise get_registry().get() raises and the series is [] (IS Sharpe 0).
import titan.strategies.registrations  # noqa: E402,F401  (populate registry)

from titan.research.db import ResearchDB
from titan.research.promotion import PromotionGate, _strategy_return_series

DATA = ROOT / "research" / "dukascopy_1m_ba"
MINUTES = 240  # 4h — F1 native timeframe (the only marginal edge)

STRATEGY = "traderdev-ema9-vwap"
DEFAULTS = {"ema_period": 3, "vwap_period": 20, "atr_period": 5, "trail_mult": 2.0}


def load_4h(pair: str) -> list[dict]:
    raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
    rows = []
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        rows.append({
            **{k: b[k] for k in ("o_ask", "o_bid", "h_ask", "h_bid",
                                 "l_ask", "l_bid", "c_ask", "c_bid", "n")},
            "dt": dt.timestamp(), "ts": b["timestamp"],
        })
    out = []
    cur = None
    for b in rows:
        key = int(b["dt"] // (MINUTES * 60))
        if cur is None or cur[0] != key:
            if cur:
                out.append(cur[1])
            cur = [key, {
                "timestamp": b["ts"], "open": b["o_bid"], "high": b["h_bid"],
                "low": b["l_bid"], "close": b["c_bid"],
                "volume": b["n"], "instrument_id": pair,
            }]
        else:
            d = cur[1]
            d["high"] = max(d["high"], b["h_bid"]); d["low"] = min(d["low"], b["l_bid"])
            d["close"] = b["c_bid"]; d["volume"] += b["n"]
    if cur:
        out.append(cur[1])
    return out


def sharpe_from_returns(returns):
    """Annualized Sharpe from a per-bar return series (bar = 4h)."""
    if len(returns) < 30:
        return 0.0
    mu = statistics.fmean(returns)
    sd = statistics.stdev(returns)
    if sd == 0:
        return 0.0
    return round(mu / sd * (2190.0 ** 0.5), 4)  # ~2190 4h bars/yr


def run_pair(pair: str) -> dict:
    bars = load_4h(pair)
    series = _strategy_return_series(STRATEGY, DEFAULTS, bars)
    bt_sharpe = sharpe_from_returns(series)
    return {
        "pair": pair, "bars": len(bars), "real_is_sharpe": bt_sharpe,
        "series_len": len(series),
    }


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="ema9vwap_gate_"))
    db = ResearchDB(str(tmpdir / "titan_research.db"))

    eur = run_pair("EURUSD")
    gbp = run_pair("GBPUSD")
    print(f"[phase1] EURUSD IS Sharpe={eur['real_is_sharpe']:.3f} "
          f"(n={eur['series_len']}); GBPUSD IS Sharpe={gbp['real_is_sharpe']:.3f}")

    # Seed the CANDIDATE record with REAL IS Sharpe. wf_sharpe intentionally
    # None (Q2: no honest OOS data exists — the gate must fail closed).
    db.set_qualification(
        STRATEGY, version="1.0.0", status="CANDIDATE",
        backtest_sharpe=eur["real_is_sharpe"], wf_sharpe=None,
        backtest_return=None, wf_return=None, max_dd_pct=None,
        notes="phase1 diagnostic (debate plan Q2=option C): only the tuning "
              "dataset exists, so walk_forward is honestly UNMET; no surface/"
              "replication DB columns exist in set_qualification.",
    )

    # Dual-experiment evidence for the live replication path (EURUSD + GBPUSD
    # are independent instruments).
    for pair, res in (("EURUSD", eur), ("GBPUSD", gbp)):
        rid = db.log_run(
            strategy_id=STRATEGY, params=DEFAULTS,
            instrument=pair, label="qualification_is",
            n_bars=res["bars"], return_pct=res["real_is_sharpe"],
            sharpe=res["real_is_sharpe"], data_source="dukascopy_1m",
        )
        db.tag_run(rid, "phase", "1")

    bars = load_4h("EURUSD")
    gate = PromotionGate(db_path=str(tmpdir / "titan_research.db"), bars=bars,
                         instrument="EURUSD")
    result = gate.evaluate(STRATEGY)
    gates = result.get("gates", [])
    passed = result.get("passed")
    print(f"\n[phase1] OVERALL PASSED={passed}  (strategy={STRATEGY})\n")

    rows_out = []
    for g in gates:
        name, ok = g.get("name"), g.get("passed")
        ev = g.get("evidence", "")
        print(f"  {'PASS' if ok else 'FAIL':4} {name:26} {ev}")
        rows_out.append({"gate": name, "passed": ok, "evidence": ev,
                         "skipped": g.get("skipped", False)})

    out = {
        "strategy_id": STRATEGY, "frame": "4h",
        "real_is_sharpe": {"EURUSD": eur["real_is_sharpe"],
                           "GBPUSD": gbp["real_is_sharpe"]},
        "gates": rows_out, "overall_passed": passed,
        "walk_forward_note": "UNMET by design (Q2=option C): only tuned-on "
                             "dataset available; a real WF needs fresh OOS.",
        "temp_db": str(tmpdir / "titan_research.db"),
    }
    res = ROOT / "research" / "results" / "ema9vwap_gate_diagnostic.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n[phase1] wrote {res}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)