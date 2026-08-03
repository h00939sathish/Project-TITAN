"""Strategy Qualification Pipeline — per-strategy sweep → walk-forward → badge.

Usage:
    python scripts/qualification_pipeline.py
    python scripts/qualification_pipeline.py --strategies rsi,bollinger
    python scripts/qualification_pipeline.py --min-sharpe 0.8

Output:
    qualification_output/
      qualification_report.json   — full matrix with badges
      qualification_report.txt    — human-readable table
      per_strategy/               — individual sweep + wf results per strategy
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import titan.strategies.registrations  # noqa: F401
from titan.backtest.results import BacktestResult
from titan.research.db import ResearchDB, DEFAULT_DB_PATH

from titan.data.ingest import read_csv
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from titan.backtest.corporate_actions import common_adjustments
from titan.research.harness import split_bars, run_backtest_result, walk_forward
from titan.strategies.registry import get_registry

from titan.research.optimizers.parameter_surface import ParameterSurface, SurfaceNode
from titan.research.validators.parameter_stability import OptimizationRiskValidator

DATA_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "market"
DEFAULT_CSV = str(DATA_DIR / "real_spy_2020_2024.csv")
OUT_DIR = Path(__file__).resolve().parent / "qualification_output"


def load_bars(csv_path: str) -> list[dict]:
    """Load and normalize bars, with direct parsing fallback for intraday CSVs."""
    raw = read_csv(csv_path)
    if not raw:
        raise ValueError(f"No data loaded from {csv_path}")
    report, good = validate_and_quarantine(raw, normalize_row, pass_through_unknown=True)
    if not good:
        parsed = []
        for r in raw:
            try:
                parsed.append({
                    "timestamp": r.get("timestamp", r.get("date", "")),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": int(float(r.get("volume", 0))),
                })
            except (KeyError, ValueError):
                continue
        return parsed
    ca_db = common_adjustments()
    return ca_db.adjust_bars(good)

# Default parameter grids per strategy
PARAM_GRIDS: dict[str, list[dict]] = {
    "ma-crossover": [
        {"fast": f, "slow": s}
        for f in (3, 5, 8, 10)
        for s in (15, 20, 30, 40)
        if f < s
    ],
    "mean-reversion": [
        {"window": w, "entry_z": ez, "exit_z": ex}
        for w in (10, 20, 30)
        for ez in (-1.5, -2.0, -2.5)
        for ex in (-0.3, -0.5, -0.8)
    ],
    "volatility-regime": [
        {"vol_window": vw, "median_window": mw, "vol_multiple": vm}
        for vw in (10, 20, 30)
        for mw in (40, 60, 80)
        for vm in (0.75, 1.0, 1.25)
    ],
    "time-series-momentum": [
        {"lookback": lb}
        for lb in (10, 20, 30, 50, 100)
    ],
    "dual-ma": [
        {"fast": f, "slow": s}
        for f in (3, 5, 8)
        for s in (15, 20, 30, 50)
        if f < s
    ],
    "rsi": [
        {"window": w, "oversold": os, "overbought": ob}
        for w in (7, 14, 21)
        for os in (25, 30, 35)
        for ob in (65, 70, 75)
    ],
    "bollinger": [
        {"window": w, "std_dev_multiplier": m}
        for w in (10, 20, 30)
        for m in (1.5, 2.0, 2.5)
    ],
}

# Default qualification thresholds
QUALIFICATION_CRITERIA = {
    "min_sharpe_is": 0.5,
    "min_sharpe_oos": 0.0,
    "min_trades": 10,
    "max_dd_pct": 20.0,
    "min_profit_factor": 1.0,
}

SIGNAL_FACTORY_MAP = {
    "ma-crossover": None,  # resolved from registry
    "mean-reversion": None,
    "volatility-regime": None,
    "time-series-momentum": None,
    "dual-ma": None,
    "rsi": None,
    "bollinger": None,
}


def resolve_factory(strategy_id: str):
    """Get the signal factory from registry. Caches."""
    if SIGNAL_FACTORY_MAP.get(strategy_id) is None:
        reg = get_registry().get(strategy_id)
        SIGNAL_FACTORY_MAP[strategy_id] = reg.factory
    return SIGNAL_FACTORY_MAP[strategy_id]


class Status(str):
    QUALIFIED = "QUALIFIED"
    WATCHLIST = "WATCHLIST"
    FAILED = "FAILED"


@dataclass
class StrategyQualification:
    strategy_id: str
    version: str = "1.0.0"
    best_params: dict = field(default_factory=dict)
    is_sharpe: float = 0.0
    oos_sharpe: float = 0.0
    wf_mean_sharpe: float = 0.0
    total_return_pct: float = 0.0
    max_dd_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    n_walk_windows: int = 0
    status: str = Status.FAILED
    confidence: str = "Low"
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.confidence == "Low" and self.status != Status.WATCHLIST:
            if self.status == Status.FAILED:
                self.confidence = "High"
            elif self.status == Status.QUALIFIED:
                if self.is_sharpe >= 1.0 and self.oos_sharpe >= 0.5 and self.total_trades >= 25:
                    self.confidence = "High"
                else:
                    self.confidence = "Medium"


def qualify_strategy(
    bars: list[dict],
    strategy_id: str,
    train_date: str = "2022-01-01",
    test_date: str = "2023-01-01",
    criteria: dict | None = None,
    slippage_bps: float = 0.5,
    commission_bps: float = 1.0,
    is_unapproved_source: bool = False,
) -> StrategyQualification | None:
    criteria = criteria or QUALIFICATION_CRITERIA
    param_grid = PARAM_GRIDS.get(strategy_id)
    if not param_grid:
        return None

    factory = resolve_factory(strategy_id)
    train_bars, test_bars = split_bars(bars, train_date)
    
    # Fallback to 60/40 ratio split if date split creates degenerate windows
    if len(train_bars) < 20 or len(test_bars) < 20:
        split_idx = int(len(bars) * 0.6)
        train_bars = bars[:split_idx]
        test_bars = bars[split_idx:]

    # ── Phase 1: Parameter sweep on IS & Parameter Surface Construction ──
    sweep_results = []
    surface = ParameterSurface(strategy_id=strategy_id, timeframe="1d", instrument_id="SPY")
    for params in param_grid:
        r_is = run_backtest_result(train_bars, params, factory,
                                   slippage_bps=slippage_bps, commission_bps=commission_bps)
        r_oos = run_backtest_result(test_bars, params, factory,
                                    slippage_bps=slippage_bps, commission_bps=commission_bps)
        if r_is.total_trades > 0:
            sweep_results.append((r_is, params))
        node = SurfaceNode(
            params=params,
            is_sharpe=r_is.sharpe_ratio,
            oos_sharpe=r_oos.sharpe_ratio,
            profit_factor=r_oos.profit_factor,
            max_drawdown_pct=r_oos.max_drawdown_pct,
            total_return_pct=r_oos.total_return_pct,
            trades_count=r_oos.total_trades,
        )
        surface.add_node(node)

    if not sweep_results:
        return StrategyQualification(strategy_id=strategy_id, status=Status.FAILED,
                                     reasons=["No trades in IS sweep"])

    sweep_results.sort(key=lambda x: x[0].sharpe_ratio, reverse=True)
    best_result, best_params = sweep_results[0]

    # ── Phase 2: Parameter Stability & Plateau Validation ──
    min_stab = criteria.get("min_plateau_stability", 0.70)
    min_cov = criteria.get("min_plateau_coverage", 0.20)
    validator = OptimizationRiskValidator(min_stability=min_stab, min_coverage=min_cov)
    scorecard = validator.validate(strategy_id=strategy_id, timeframe="1d", surfaces_by_instrument={"SPY": surface})

    # ── Phase 3: OOS test ──
    oos_result = run_backtest_result(test_bars, best_params, factory,
                                     slippage_bps=slippage_bps, commission_bps=commission_bps)

    # ── Phase 4: Walk-forward ──
    wf_size = min(252, max(30, len(test_bars) // 3))
    wf_step = max(10, wf_size // 4)
    wf_results = walk_forward(test_bars, best_params, factory,
                              train_size=wf_size, step=wf_step)
    wf_sharpes = [r.sharpe_ratio for r in wf_results]
    wf_mean_sharpe = sum(wf_sharpes) / len(wf_sharpes) if wf_sharpes else 0.0

    # ── Phase 5: Qualification check ──
    reasons = []
    status = Status.QUALIFIED

    # Check Plateau Governance Scorecard
    if not scorecard.passed_all_checks:
        for r in scorecard.rejection_reasons:
            reasons.append(f"Governance Gate: {r}")
        status = Status.WATCHLIST

    # Unapproved data source warning
    if is_unapproved_source:
        reasons.append("Unapproved data source (Research-only, cannot qualify for production routing)")
        status = Status.WATCHLIST

    # Fundamental failure — IS sharpe too low
    if best_result.sharpe_ratio < criteria["min_sharpe_is"]:
        reasons.append(f"IS sharpe {best_result.sharpe_ratio:.2f} < {criteria['min_sharpe_is']}")
        status = Status.FAILED

    # Fundamental failure — negative WF sharpe suggests overfit
    if wf_mean_sharpe < -0.1:
        reasons.append(f"WF sharpe {wf_mean_sharpe:.2f} < -0.1 (overfit)")
        status = Status.FAILED

    # Check remaining criteria
    if oos_result.sharpe_ratio < criteria["min_sharpe_oos"]:
        reasons.append(f"OOS sharpe {oos_result.sharpe_ratio:.2f} < {criteria['min_sharpe_oos']}")
        if status == Status.QUALIFIED:
            status = Status.WATCHLIST
    if oos_result.max_drawdown_pct > criteria["max_dd_pct"]:
        reasons.append(f"OOS max DD {oos_result.max_drawdown_pct:.1f}% > {criteria['max_dd_pct']}%")
        if status == Status.QUALIFIED:
            status = Status.WATCHLIST
    if oos_result.total_trades < criteria["min_trades"]:
        reasons.append(f"OOS trades {oos_result.total_trades} < {criteria['min_trades']}")
        if status == Status.QUALIFIED:
            status = Status.WATCHLIST
    if oos_result.profit_factor < criteria["min_profit_factor"]:
        reasons.append(f"OOS PF {oos_result.profit_factor:.2f} < {criteria['min_profit_factor']}")
        if status == Status.QUALIFIED:
            status = Status.WATCHLIST

    if status == Status.QUALIFIED and not reasons:
        reasons.append("All criteria met")

    return StrategyQualification(
        strategy_id=strategy_id,
        best_params=best_params,
        is_sharpe=round(best_result.sharpe_ratio, 4),
        oos_sharpe=round(oos_result.sharpe_ratio, 4),
        wf_mean_sharpe=round(wf_mean_sharpe, 4),
        total_return_pct=round(oos_result.total_return_pct, 2),
        max_dd_pct=round(oos_result.max_drawdown_pct, 2),
        win_rate=round(oos_result.win_rate, 1),
        profit_factor=round(oos_result.profit_factor, 4),
        total_trades=oos_result.total_trades,
        n_walk_windows=len(wf_results),
        status=status,
        reasons=reasons,
    )


def write_report(qualifications: list[StrategyQualification], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    with open(out_dir / "qualification_report.json", "w") as f:
        quals = []
        for q in qualifications:
            d = asdict(q)
            d["pf_display"] = f">{q.profit_factor:.0f}" if q.profit_factor >= 100 else f"{q.profit_factor:.2f}"
            d["profit_factor_raw"] = q.profit_factor
            quals.append(d)
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "criteria": QUALIFICATION_CRITERIA,
            "qualifications": quals,
        }, f, indent=2)

    # Human-readable report
    lines = []
    lines.append("=" * 100)
    lines.append("  TITAN Strategy Qualification Report")
    lines.append("=" * 100)
    lines.append(f"  Qualified criteria:  IS Sharpe >= {QUALIFICATION_CRITERIA['min_sharpe_is']}")
    lines.append(f"                       OOS Sharpe >= {QUALIFICATION_CRITERIA['min_sharpe_oos']}")
    lines.append(f"                       Max DD <= {QUALIFICATION_CRITERIA['max_dd_pct']}%")
    lines.append(f"                       Trades >= {QUALIFICATION_CRITERIA['min_trades']}")
    lines.append(f"                       Profit Factor >= {QUALIFICATION_CRITERIA['min_profit_factor']}")
    lines.append("")

    headers = ("Strategy", "Params", "IS Sharpe", "OOS Sharpe", "WF Sharpe",
               "Return%", "Max DD%", "Win%", "PF", "Trades", "Status", "Confidence")
    col_widths = [20, 30, 10, 10, 10, 9, 9, 7, 8, 8, 10, 12]
    sep = " | ".join("-" * w for w in col_widths)
    header_line = " | ".join(h.center(w) for h, w in zip(headers, col_widths))
    lines.append(header_line)
    lines.append(sep)

    for q in qualifications:
        params_str = json.dumps(q.best_params, sort_keys=True).replace('"', "")[:28]
        status_label = q.status
        if q.status == Status.WATCHLIST:
            status_label = "WATCHLIST"
        pf_display = f">{q.profit_factor:.0f}" if q.profit_factor >= 100 else f"{q.profit_factor:.2f}"
        row = (
            q.strategy_id.ljust(20),
            params_str.ljust(28),
            f"{q.is_sharpe:.2f}".rjust(10),
            f"{q.oos_sharpe:.2f}".rjust(10),
            f"{q.wf_mean_sharpe:.2f}".rjust(10),
            f"{q.total_return_pct:.1f}%".rjust(8),
            f"{q.max_dd_pct:.1f}%".rjust(8),
            f"{q.win_rate:.0f}%".rjust(6),
            pf_display.rjust(8),
            f"{q.total_trades}".rjust(8),
            status_label.rjust(10),
            q.confidence.rjust(12),
        )
        lines.append(" | ".join(row))
        if q.status != Status.QUALIFIED:
            for reason in q.reasons:
                lines.append(f"  {' ' * 20} | {q.status[:4]}: {reason}")

    lines.append("")
    lines.append("=" * 100)

    report_text = "\n".join(lines)
    with open(out_dir / "qualification_report.txt", "w") as f:
        f.write(report_text)

    # Also per-strategy details
    per_dir = out_dir / "per_strategy"
    per_dir.mkdir(exist_ok=True)
    for q in qualifications:
        with open(per_dir / f"{q.strategy_id}.json", "w") as f:
            json.dump(asdict(q), f, indent=2)

    print(report_text)

    # Summary line
    n_qualified = sum(1 for q in qualifications if q.status == Status.QUALIFIED)
    n_watch = sum(1 for q in qualifications if q.status == Status.WATCHLIST)
    n_failed = sum(1 for q in qualifications if q.status == Status.FAILED)
    print(f"\n  Result: {n_qualified} QUALIFIED, {n_watch} WATCHLIST, {n_failed} FAILED")
    print(f"\n  Full report: {out_dir}/qualification_report.*")


def main() -> None:
    parser = argparse.ArgumentParser(description="TITAN Strategy Qualification Pipeline")
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--strategies", help="Comma-separated list (default: all registered)")
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--train-date", default="2022-01-01")
    parser.add_argument("--test-date", default="2023-01-01")
    parser.add_argument("--min-sharpe", type=float, help="Override min IS Sharpe criterion")
    parser.add_argument("--asset-class", choices=["equity", "forex"], default="equity", help="Asset class (determines default cost model)")
    parser.add_argument("--slippage-bps", type=float, help="Override slippage in bps")
    parser.add_argument("--commission-bps", type=float, help="Override commission in bps")
    parser.add_argument("--unapproved-source", action="store_true", help="Mark dataset as unapproved research feed")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="ResearchDB path")

    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    slippage_bps = args.slippage_bps if args.slippage_bps is not None else (1.0 if args.asset_class == "forex" else 0.5)
    commission_bps = args.commission_bps if args.commission_bps is not None else (1.0 if args.asset_class == "forex" else 1.0)

    print(f"Loading bars from {args.csv} (Asset Class: {args.asset_class}, Slippage: {slippage_bps}bps, Commission: {commission_bps}bps) ...")
    bars = load_bars(args.csv)
    print(f"  {len(bars)} bars loaded")

    # Figure out which strategies to qualify
    if args.strategies:
        strategy_ids = [s.strip() for s in args.strategies.split(",")]
    else:
        strategy_ids = get_registry().list_ids()

    criteria = dict(QUALIFICATION_CRITERIA)
    if args.min_sharpe is not None:
        criteria["min_sharpe_is"] = args.min_sharpe

    db = ResearchDB(args.db) if args.db else None

    qualifications = []
    for sid in strategy_ids:
        print(f"\n  Qualifying {sid} ...")
        q = qualify_strategy(
            bars, sid, args.train_date, args.test_date, criteria,
            slippage_bps=slippage_bps, commission_bps=commission_bps,
            is_unapproved_source=args.unapproved_source
        )
        if q:
            qualifications.append(q)
            print(f"    IS Sharpe={q.is_sharpe:.2f}  OOS Sharpe={q.oos_sharpe:.2f}  "
                  f"WF Sharpe={q.wf_mean_sharpe:.2f}  "
                  f"{q.status}")
            if db:
                rid = db.log_run(
                    strategy_id=sid,
                    params=q.best_params,
                    instrument="SPY" if args.asset_class == "equity" else "EURUSD",
                    label=f"qualification_{sid}",
                    n_bars=len(bars),
                    n_trades=q.total_trades,
                    return_pct=q.total_return_pct,
                    sharpe=q.oos_sharpe,
                    max_dd_pct=q.max_dd_pct,
                    win_rate=q.win_rate,
                    profit_factor=q.profit_factor,
                )
                db.tag_run(rid, "type", "qualification")
                db.set_qualification(
                    strategy_id=sid,
                    status=q.status,
                    backtest_sharpe=q.is_sharpe,
                    wf_sharpe=q.wf_mean_sharpe,
                    paper_trades=q.total_trades,
                    backtest_return=q.total_return_pct,
                    max_dd_pct=q.max_dd_pct,
                    notes="; ".join(q.reasons),
                )
        else:
            print(f"    SKIPPED (no param grid defined)")

    qualifications.sort(key=lambda q: q.oos_sharpe, reverse=True)
    write_report(qualifications, Path(args.out))

    if db:
        db.close()


if __name__ == "__main__":
    main()
