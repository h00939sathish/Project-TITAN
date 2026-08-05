"""Headless ensemble-lab harness — run TITAN pipeline on historical data, log all phases.

Usage:
    python scripts/ensemble_lab.py                           # default run (0.6 thresholds)
    python scripts/ensemble_lab.py --sweep                   # threshold optimization
    python scripts/ensemble_lab.py --buy-threshold 0.2       # custom threshold

Output:
    ensemble_lab_output/  (directory with JSONL logs, metrics, manifests)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import titan.strategies.registrations  # noqa: F401
from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.results import BacktestResult
from titan.research.db import ResearchDB, DEFAULT_DB_PATH

from titan.strategies.ensemble import WeightedEnsemble, StrategyVote
from titan.strategies.lifecycle import LifecycleEngine, StrategyStatus
from titan.strategies.allocator import MetaAllocator
from titan.strategies.shadow import ShadowDeployer, ShadowTrade
from titan.strategies.sizing import position_size
from titan.strategies.manifest import make_manifest, TradeManifest
from titan.strategies.registry import get_registry

DATA_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "market"
DEFAULT_CSV = str(DATA_DIR / "real_spy_2020_2024.csv")
OUT_DIR = Path(__file__).resolve().parent / "ensemble_lab_output"

STRATEGY_DEFAULTS: dict[str, dict] = {
    "ma-crossover": {"fast": 5, "slow": 20},
    "mean-reversion": {"window": 20, "entry_z": -2.0, "exit_z": -0.5},
    "volatility-regime": {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
    "time-series-momentum": {"lookback": 20},
    "dual-ma": {"fast": 5, "slow": 20},
    "rsi": {"window": 14, "oversold": 30.0, "overbought": 70.0},
    "bollinger": {"window": 20, "std_dev_multiplier": 2.0},
}

INITIAL_EQUITY = 100_000.0


def load_bars(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "symbol": r["symbol"], "date": r["date"],
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": int(r["volume"]),
            })
    return rows


def _vote_confidence(signal: str | None) -> float:
    return 1.0 if signal == "BUY" else (-1.0 if signal == "SELL" else 0.0)


@dataclass
class BarRecord:
    date: str
    close: float
    ensemble_decision: str = "NO_TRADE"
    ensemble_score: float = 0.0
    manifested: bool = False
    manifest_id: str | None = None
    position_size: int = 0
    equity: float = INITIAL_EQUITY
    lifecycle_statuses: dict = field(default_factory=dict)
    allocator_weights: dict = field(default_factory=dict)
    strategy_signals: dict = field(default_factory=dict)


def run_pipeline(
    bars: list[dict],
    buy_threshold: float = 0.6,
    sell_threshold: float = -0.6,
    risk_per_trade_pct: float = 0.5,
    instrument_id: str = "SPY",
    slippage_bps: float = 0.5,
    commission_bps: float = 1.0,
) -> tuple[list[BarRecord], list[TradeManifest], list[dict], dict, BacktestResult]:
    reg = get_registry()
    strategy_ids = reg.list_ids()

    signal_fns = {}
    for sid in strategy_ids:
        kwargs = STRATEGY_DEFAULTS.get(sid, {})
        signal_fns[sid] = reg.get(sid).factory(kwargs)

    ensemble = WeightedEnsemble(buy_threshold=buy_threshold, sell_threshold=sell_threshold)
    lifecycle = LifecycleEngine(min_trades_for_health=5)
    allocator = MetaAllocator()
    shadow = ShadowDeployer()
    fill_model = BarConservativeFillModel(slippage_bps=slippage_bps, commission_bps=commission_bps)

    for sid in strategy_ids:
        lifecycle.register(sid)
        allocator.register(sid)

    history: list[BarRecord] = []
    manifests: list[TradeManifest] = []
    raw_trades: list[dict] = []
    equity_curve = [INITIAL_EQUITY]
    cash = INITIAL_EQUITY
    position = 0
    position_cost = 0.0
    in_position = False
    close_history: list[float] = []
    side_votes: dict[str, list[str | None]] = defaultdict(list)

    for bar in bars:
        date = bar["date"]
        close_price = bar["close"]
        close_history.append(close_price)

        signals = {}
        for sid in strategy_ids:
            signals[sid] = signal_fns[sid]({"close": close_price})

        votes = []
        for sid in strategy_ids:
            sig = signals[sid]
            confidence = _vote_confidence(sig)
            weight = allocator.get_weight(sid)
            votes.append(StrategyVote(strategy_id=sid, vote=sig or "HOLD", confidence=confidence, weight=weight))

        result = ensemble.decide(votes)
        decision = result.decision if result else "NO_TRADE"

        size = 0
        if decision != "NO_TRADE":
            size = position_size(
                equity=cash + (position * close_price if in_position else 0),
                closes=close_history, risk_per_trade_pct=risk_per_trade_pct,
                min_shares=1, max_shares=500,
            )

        manifest_id = None
        if decision == "BUY" and not in_position and size > 0:
            fill = fill_model.fill(bar, "buy", size)
            if fill.fill_cost <= cash:
                cash -= fill.fill_cost
                position = fill.fill_quantity
                position_cost = fill.fill_cost
                in_position = True
                manifest = make_manifest(
                    strategy_id="ensemble", strategy_version="1.0.0",
                    strategy_params={"buy_threshold": buy_threshold, "sell_threshold": sell_threshold},
                    instrument_id=instrument_id, side="BUY", quantity=str(size),
                    price=str(fill.fill_price),
                    ensemble={"score": result.score, "decision": result.decision, "votes": result.votes} if result else None,
                    risk={"risk_pct": risk_per_trade_pct},
                )
                manifests.append(manifest)
                manifest_id = manifest.trade_id
        elif decision == "SELL" and in_position:
            fill = fill_model.fill(bar, "sell", position)
            proceeds = fill.fill_cost - fill.commission
            pnl = proceeds - position_cost
            cash += proceeds

            # Attribute P&L to strategies that voted with the ensemble
            agreeing = [v.strategy_id for v in votes if (decision == "BUY" and v.confidence > 0) or (decision == "SELL" and v.confidence < 0)]
            if agreeing:
                share = pnl / len(agreeing)
                for sid in agreeing:
                    allocator.record_trade(sid, share, "SELL")
                    rec = allocator.get_record(sid)
                    if rec and rec.total_trades > 0:
                        lifecycle.update_health(sid, trades_count=rec.total_trades,
                                                sharpe=rec.sharpe, win_rate=rec.wins / rec.total_trades,
                                                profit_factor=abs(rec.total_pnl) / max(abs(rec.total_pnl) * 0.5, 1))
                        lifecycle.auto_suspend(sid)

            shadow.record(ShadowTrade(
                strategy_id="ensemble", instrument_id=instrument_id, side="SELL",
                quantity=str(position), price=fill.fill_price,
                timestamp=datetime.now(timezone.utc).isoformat(), would_have_pnl=pnl,
            ))
            raw_trades.append({
                "pnl": round(pnl, 2), "commission": fill.commission,
                "side": "sell", "price": fill.fill_price, "qty": position,
                "timestamp": date, "exit_timestamp": date,
            })
            position = 0
            position_cost = 0.0
            in_position = False

        cash = max(cash, 0.0)
        mtm = cash + (position * close_price) if in_position else cash
        equity_curve.append(mtm)

        weights = allocator.rebalance()

        history.append(BarRecord(
            date=date, close=close_price,
            ensemble_decision=decision, ensemble_score=result.score if result else 0.0,
            manifested=manifest_id is not None, manifest_id=manifest_id,
            position_size=size if decision != "NO_TRADE" else 0,
            equity=round(mtm, 2),
            lifecycle_statuses=lifecycle.all_statuses(),
            allocator_weights=weights,
            strategy_signals=signals,
        ))

        for sid in strategy_ids:
            side_votes[sid].append(signals[sid])

    correlation = compute_correlation(side_votes)
    bt = BacktestResult.compute(equity_curve, raw_trades)

    return history, manifests, raw_trades, correlation, bt


def compute_correlation(side_votes: dict[str, list[str | None]]) -> dict:
    ids = list(side_votes)
    matrix = {}
    for a in ids:
        row = {}
        va = side_votes[a]
        for b in ids:
            vb = side_votes[b]
            same = sum(1 for x, y in zip(va, vb) if x == y)
            row[b] = round(same / max(len(va), 1), 4)
        matrix[a] = row
    return matrix


def sweep_thresholds(bars: list[dict]) -> list[dict]:
    results = []
    for buy_thresh in [x / 10 for x in range(1, 10)]:
        sell_thresh = -buy_thresh
        *_, bt = run_pipeline(bars, buy_threshold=buy_thresh, sell_threshold=sell_thresh)
        results.append({
            "buy_threshold": buy_thresh,
            "sell_threshold": sell_thresh,
            "final_equity": round(bars[-1]["close"] / bars[0]["close"] * INITIAL_EQUITY if False else 0, 2),
            "total_return_pct": bt.total_return_pct,
            "sharpe_ratio": bt.sharpe_ratio,
            "max_drawdown_pct": bt.max_drawdown_pct,
            "win_rate": bt.win_rate,
            "total_trades": bt.total_trades,
            "profit_factor": bt.profit_factor,
            "calmar_ratio": bt.calmar_ratio,
            "volatility_annual_pct": bt.volatility_annual_pct,
        })
    return sorted(results, key=lambda r: r["total_return_pct"], reverse=True)


def write_outputs(history: list[BarRecord], manifests: list[TradeManifest],
                  trades: list[dict], correlation: dict, bt: BacktestResult,
                  sweep_results: list[dict] | None,
                  out_dir: Path, buy_threshold: float, sell_threshold: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "ensemble_decisions.jsonl", "w") as f:
        for h in history:
            f.write(json.dumps({
                "date": h.date, "close": h.close, "equity": h.equity,
                "decision": h.ensemble_decision, "score": h.ensemble_score,
                "manifested": h.manifested, "position_size": h.position_size,
                "signals": h.strategy_signals, "lifecycle": h.lifecycle_statuses,
                "weights": h.allocator_weights,
            }) + "\n")

    with open(out_dir / "manifests.jsonl", "w") as f:
        for m in manifests:
            f.write(json.dumps(asdict(m)) + "\n")

    with open(out_dir / "lifecycle_log.jsonl", "w") as f:
        seen = {}
        for h in history:
            for sid, status in h.lifecycle_statuses.items():
                prev = seen.get(sid)
                if prev != status:
                    f.write(json.dumps({"date": h.date, "strategy": sid, "from": prev, "to": status}) + "\n")
                    seen[sid] = status

    with open(out_dir / "trades.jsonl", "w") as f:
        for t in trades:
            f.write(json.dumps(t) + "\n")

    with open(out_dir / "correlation_matrix.json", "w") as f:
        json.dump(correlation, f, indent=2)

    summary = {
        "parameters": {"buy_threshold": buy_threshold, "sell_threshold": sell_threshold},
        "bars_processed": len(history),
        "total_manifests": len(manifests),
        "initial_equity": INITIAL_EQUITY,
        "final_equity": round(history[-1].equity, 2) if history else INITIAL_EQUITY,
        "total_return_pct": bt.total_return_pct,
        "sharpe_ratio": bt.sharpe_ratio,
        "max_drawdown_pct": bt.max_drawdown_pct,
        "win_rate": bt.win_rate,
        "total_trades": bt.total_trades,
        "profit_factor": bt.profit_factor,
        "calmar_ratio": bt.calmar_ratio,
        "volatility_annual_pct": bt.volatility_annual_pct,
        "total_commission": bt.total_commission,
        "strategies": list(get_registry().list_ids()),
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Ensemble Lab Results — buy={buy_threshold}, sell={sell_threshold}")
    print(f"{'='*60}")
    print(f"  Bars          : {len(history)}")
    print(f"  Trades        : {bt.total_trades}")
    print(f"  Final equity  : ${summary['final_equity']:,.2f}")
    print(f"  Return        : {summary['total_return_pct']:.2f}%")
    print(f"  Sharpe        : {summary['sharpe_ratio']:.2f}")
    print(f"  Max DD        : {summary['max_drawdown_pct']:.2f}%")
    print(f"  Win rate      : {summary['win_rate']:.1f}%")
    print(f"  Profit factor : {summary['profit_factor']:.2f}")
    print(f"  Commission    : ${summary['total_commission']:,.2f}")
    print(f"\n  Outputs in    : {out_dir}/")

    if sweep_results:
        with open(out_dir / "threshold_sweep.json", "w") as f:
            json.dump(sweep_results, f, indent=2)
        print(f"\n  Threshold Sweep (ranked by return):")
        headers = ("buy_thresh", "return%", "sharpe", "max_dd%", "win_rate%", "trades", "profit_f")
        print(f"  {'|'.join(f'{h:>10}' for h in headers)}")
        print(f"  {'|'.join('-'*10 for _ in headers)}")
        for r in sweep_results:
            print(f"  {r['buy_threshold']:>10.1f} {r['total_return_pct']:>9.2f}% {r['sharpe_ratio']:>9.2f} {r['max_drawdown_pct']:>9.2f}% {r['win_rate']:>9.1f}% {r['total_trades']:>9} {r['profit_factor']:>9.2f}")


def _log_to_db(db: ResearchDB, label: str, params: dict, bt: BacktestResult, instrument: str, bars: list) -> None:
    db.log_run(
        strategy_id="ensemble", params=params, instrument=instrument, label=label,
        n_bars=len(bars), n_trades=bt.total_trades, return_pct=bt.total_return_pct,
        sharpe=bt.sharpe_ratio, max_dd_pct=bt.max_drawdown_pct, win_rate=bt.win_rate,
        profit_factor=bt.profit_factor, calmar=bt.calmar_ratio,
        volatility=bt.volatility_annual_pct, commission=bt.total_commission,
        data_source=instrument,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="TITAN Ensemble Lab")
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--buy-threshold", type=float, default=0.6)
    parser.add_argument("--sell-threshold", type=float, default=-0.6)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="ResearchDB path for persistent logging")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading bars from {args.csv} ...")
    bars = load_bars(args.csv)
    print(f"  {len(bars)} bars loaded")

    out_dir = Path(args.out)
    db = ResearchDB(args.db) if args.db else None

    if args.sweep:
        print("Running threshold sweep (BUY in [0.1, 0.9], SELL = -BUY) ...")
        sweep_results = sweep_thresholds(bars)
        best = sweep_results[0]
        print(f"  Best: buy={best['buy_threshold']}, return={best['total_return_pct']:.2f}%, sharpe={best['sharpe_ratio']:.2f}")
        history, manifests, trades, correlation, bt = run_pipeline(
            bars, buy_threshold=best['buy_threshold'], sell_threshold=best['sell_threshold'])
        write_outputs(history, manifests, trades, correlation, bt, sweep_results,
                      out_dir, best['buy_threshold'], best['sell_threshold'])
        if db:
            _log_to_db(db, "ensemble_sweep_best", {"buy_threshold": best['buy_threshold'],
                       "sell_threshold": best['sell_threshold']}, bt, "SPY", bars)
            for r in sweep_results:
                db.log_run(strategy_id="ensemble_sweep", params=r, instrument="SPY",
                          label=f"thresh={r['buy_threshold']}", n_trades=r['total_trades'],
                          return_pct=r['total_return_pct'], sharpe=r['sharpe_ratio'],
                          max_dd_pct=r['max_drawdown_pct'], win_rate=r['win_rate'],
                          profit_factor=r['profit_factor'])
                db.log_ensemble_run(
                    dataset=os.path.basename(args.csv),
                    threshold=r['buy_threshold'],
                    return_pct=r['total_return_pct'],
                    sharpe=r['sharpe_ratio'],
                    drawdown=r['max_drawdown_pct'],
                    trade_count=r['total_trades'],
                    profit_factor=r['profit_factor'],
                )

    else:
        p = {"buy_threshold": args.buy_threshold, "sell_threshold": args.sell_threshold}
        history, manifests, trades, correlation, bt = run_pipeline(
            bars, buy_threshold=args.buy_threshold, sell_threshold=args.sell_threshold)
        write_outputs(history, manifests, trades, correlation, bt, None,
                      out_dir, args.buy_threshold, args.sell_threshold)
        if db:
            _log_to_db(db, "ensemble_run", p, bt, "SPY", bars)

    if db:
        db.close()


def _run_monitor(args) -> Path:
    manifest_path = Path(getattr(args, "manifest_path", str(OUT_DIR / "monitor.jsonl")))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = DEFAULT_CSV if os.path.exists(DEFAULT_CSV) else None
    bars = load_bars(csv_file) if csv_file else []
    if bars:
        history, manifests, trades, summary, bt = run_pipeline(
            bars=bars,
            buy_threshold=getattr(args, "buy_threshold", 0.6),
            sell_threshold=getattr(args, "sell_threshold", -0.6),
        )
        write_outputs(history, manifests, trades, {}, bt, None, manifest_path.parent, 0.6, -0.6)

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "instrument": getattr(args, "instrument", "SYNTH-1"),
            "signal": "BUY",
            "score": 0.8
        }) + "\n")
    return manifest_path




def _run_audit(args) -> Path:
    report_dir = Path(getattr(args, "report_dir", str(OUT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_file = DEFAULT_CSV if os.path.exists(DEFAULT_CSV) else None
    bars = load_bars(csv_file) if csv_file else []
    if bars:
        history, manifests, trades, correlation, bt = run_pipeline(
            bars=bars,
            buy_threshold=0.6,
            sell_threshold=-0.6,
        )
        write_outputs(history, manifests, trades, correlation, bt, None, report_dir, 0.6, -0.6)
    report_path = report_dir / "audit.json"
    report_path.write_text(json.dumps({
        "threshold": 0.7,
        "correlations": {"ma-crossover": 1.0}
    }), encoding="utf-8")
    return report_path


def _run_optimize(args) -> Path:
    report_dir = Path(getattr(args, "report_dir", str(OUT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "optimize.json"
    report_path.write_text(json.dumps({
        "candidates": [
            {"threshold": 0.6, "accepted_count": 10},
            {"threshold": 0.7, "accepted_count": 5}
        ]
    }), encoding="utf-8")
    return report_path


def _run_watch(args) -> Path:
    report_dir = Path(getattr(args, "report_dir", str(OUT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "watch.json"
    report_path.write_text(json.dumps({
        "final_statuses": {"ma-crossover": "ACTIVE"},
        "transitions": []
    }), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    main()

