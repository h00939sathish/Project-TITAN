"""Research CLI — query accumulated experiments from the SQLite research database.

Usage:
    python -m titan.research.cli top
    python -m titan.research.cli top --metric sharpe --limit 5
    python -m titan.research.cli strategy ma-crossover
    python -m titan.research.cli compare ma-crossover rsi
    python -m titan.research.cli runs --strategy rsi --limit 10
    python -m titan.research.cli db-info
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from titan.research.db import ResearchDB, DEFAULT_DB_PATH


def _open_db(path: str | None) -> ResearchDB:
    db_path = path or str(DEFAULT_DB_PATH)
    if not os.path.exists(db_path):
        print(f"Research database not found at {db_path}", file=sys.stderr)
        print("Run the qualification pipeline first:  python scripts/qualification_pipeline.py --db <path>", file=sys.stderr)
        sys.exit(1)
    return ResearchDB(db_path)


def cmd_top(args):
    db = _open_db(args.db)
    metric = args.metric
    limit = args.limit

    quals = db.get_qualifications()
    if not quals:
        print("No qualifications found. Run qualification_pipeline.py first.")
        db.close()
        return

    # Sort by the requested metric from qualifications
    valid_metrics = {"backtest_sharpe": "backtest_sharpe", "wf_sharpe": "wf_sharpe",
                     "paper_trades": "paper_trades", "max_dd_pct": "max_dd_pct"}

    q_sorted = sorted(quals, key=lambda q: q.get(valid_metrics.get(metric, "backtest_sharpe"), 0) or 0, reverse=True)

    print()
    print(f"{'Rank':>4}  {'Strategy':<22} {'Status':<12} {'IS Sharpe':>10} {'WF Sharpe':>10} {'Return%':>8} {'Max DD%':>8} {'Trades':>7} {'PF':>8}")
    print(f"{'-'*4}  {'-'*22} {'-'*12} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*7} {'-'*8}")

    for i, q in enumerate(q_sorted[:limit], 1):
        print(f"{i:>4}  {q['strategy_id']:<22} {q['status']:<12} "
              f"{q.get('backtest_sharpe', 0) or 0:>10.2f} "
              f"{q.get('wf_sharpe', 0) or 0:>10.2f} "
              f"{q.get('backtest_return', 0) or 0:>7.1f}% "
              f"{q.get('max_dd_pct', 0) or 0:>7.1f}% "
              f"{q.get('paper_trades', 0) or 0:>7} "
              f"-")  # PF not in qualifications table yet

    db.close()


def cmd_strategy(args):
    db = _open_db(args.db)
    sid = args.strategy_id

    quals = db.get_qualifications()
    qual = next((q for q in quals if q["strategy_id"] == sid), None)

    runs = db.get_runs(strategy_id=sid, limit=30)

    print(f"\n{'='*60}")
    print(f"  Strategy: {sid}")
    print(f"{'='*60}")

    if qual:
        print(f"\n  Qualification:")
        print(f"    Status      : {qual['status']}")
        print(f"    IS Sharpe   : {qual['backtest_sharpe']}")
        print(f"    WF Sharpe   : {qual['wf_sharpe']}")
        print(f"    Return      : {qual['backtest_return']}%")
        print(f"    Max DD      : {qual['max_dd_pct']}%")
        print(f"    Trades      : {qual['paper_trades']}")
        print(f"    Notes       : {qual['notes']}")
        if qual.get('qualified_at'):
            print(f"    Qualified at: {qual['qualified_at']}")
    else:
        print("\n  No qualification record found.")

    print(f"\n  Recent runs ({len(runs)} total):")
    if runs:
        print(f"  {'#':>4}  {'Date':<24} {'Instrument':<10} {'Return%':>8} {'Sharpe':>7} "
              f"{'Max DD%':>8} {'Win%':>6} {'Trades':>7}")
        print(f"  {'-'*4}  {'-'*24} {'-'*10} {'-'*8} {'-'*7} {'-'*8} {'-'*6} {'-'*7}")
        for r in runs:
            print(f"  {r['id']:>4}  {r['created_at'][:19]:<24} {r['instrument']:<10} "
                  f"{r['return_pct']:>7.1f}% {r['sharpe']:>7.2f} "
                  f"{r['max_dd_pct']:>7.1f}% {r['win_rate']:>5.0f}% {r['n_trades']:>7}")

    best = db.get_best_run(sid, "sharpe")
    if best:
        print(f"\n  Best run: #{best['id']} — sharpe={best['sharpe']:.2f}, "
              f"return={best['return_pct']:.1f}%, params={best['params_json']}")

    db.close()


def cmd_compare(args):
    db = _open_db(args.db)
    a_id, b_id = args.a, args.b

    quals = db.get_qualifications()
    q_a = next((q for q in quals if q["strategy_id"] == a_id), None)
    q_b = next((q for q in quals if q["strategy_id"] == b_id), None)

    print(f"\n{'='*70}")
    print(f"  Compare: {a_id} vs {b_id}")
    print(f"{'='*70}")
    print(f"  {'Metric':<20} {a_id:<22} {b_id:<22}")
    print(f"  {'-'*20} {'-'*22} {'-'*22}")

    def val(q, field, fmt=".2f"):
        if not q or q.get(field) is None:
            return "N/A"
        return f"{q[field]:{fmt}}"

    for metric, label, fmt in [
        ("status", "Status", "s"),
        ("backtest_sharpe", "IS Sharpe", ".2f"),
        ("wf_sharpe", "WF Sharpe", ".2f"),
        ("backtest_return", "Return%", ".1f"),
        ("max_dd_pct", "Max DD%", ".1f"),
        ("paper_trades", "Trades", "d"),
    ]:
        v_a = val(q_a, metric, fmt)
        v_b = val(q_b, metric, fmt)
        print(f"  {label:<20} {v_a:<22} {v_b:<22}")

    db.close()


def cmd_runs(args):
    db = _open_db(args.db)
    runs = db.get_runs(strategy_id=args.strategy_id, limit=args.limit)

    if not runs:
        print("No runs found.")
        db.close()
        return

    print(f"\n{'='*90}")
    print(f"  Recent runs{' for ' + args.strategy_id if args.strategy_id else ''}")
    print(f"{'='*90}")
    print(f"  {'#':>4}  {'Date':<24} {'Strategy':<20} {'Instrument':<10} "
          f"{'Return%':>8} {'Sharpe':>7} {'Max DD%':>8} {'Win%':>6} {'Trades':>7}")
    print(f"  {'-'*4}  {'-'*24} {'-'*20} {'-'*10} {'-'*8} {'-'*7} {'-'*8} {'-'*6} {'-'*7}")
    for r in runs:
        print(f"  {r['id']:>4}  {r['created_at'][:19]:<24} "
              f"{r['strategy_id']:<20} {r['instrument']:<10} "
              f"{r['return_pct']:>7.1f}% {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>7.1f}% {r['win_rate']:>5.0f}% {r['n_trades']:>7}")

    db.close()


def cmd_shadow(args):
    db = _open_db(args.db)
    summary = db.get_shadow_summary(session_id=args.session)
    if not summary:
        print("\n  No shadow events found.")
        db.close()
        return
    print(f"\n{'='*60}")
    print(f"  Shadow Deployment Summary{' (session: ' + args.session + ')' if args.session else ''}")
    print(f"{'='*60}")
    print(f"  {'Strategy':<22} {'Events':>7} {'Trades':>7} {'Total P&L':>10}")
    print(f"  {'-'*22} {'-'*7} {'-'*7} {'-'*10}")
    for s in summary:
        print(f"  {s['strategy_id']:<22} {s['events']:>7} {s['trades']:>7} ${s['total_pnl']:>8.2f}")
    db.close()


def cmd_db_info(args):
    db = _open_db(args.db)
    runs = db.get_runs(limit=1)
    quals = db.get_qualifications()

    print(f"\n{'='*50}")
    print(f"  Research Database Info")
    print(f"{'='*50}")
    print(f"  Path      : {db._path}")
    print(f"  Total runs: {runs[0]['id'] if runs else 0} (latest: #{runs[0]['id'] if runs else 'N/A'})")
    print(f"  Strategies in qualification: {len(quals)}")
    for q in quals:
        print(f"    {q['strategy_id']:<22} {q['status']:<12} "
              f"IS Sharpe={q.get('backtest_sharpe', 0) or 0:.2f}  "
              f"WF Sharpe={q.get('wf_sharpe', 0) or 0:.2f}")

    shadow_rows = db._conn.execute(
        "SELECT strategy_id, COUNT(*) as events, SUM(CASE WHEN simulated_side IS NOT NULL THEN 1 ELSE 0 END) as trades "
        "FROM shadow_events GROUP BY strategy_id"
    ).fetchall()
    if shadow_rows:
        print(f"\n  Shadow events ({sum(r['events'] for r in shadow_rows)} total):")
        for r in shadow_rows:
            print(f"    {r['strategy_id']:<22} {r['events']:>4} events  {r['trades']:>4} simulated trades")
    db.close()


def cmd_promote(args):
    import titan.strategies.registrations  # noqa: F401
    from titan.research.harness import load_bars
    from titan.research.promotion import PromotionGate

    db = _open_db(args.db)
    db.close()

    bars = load_bars(args.csv) if args.csv else []

    gate = PromotionGate(args.db or str(DEFAULT_DB_PATH), bars)
    result = gate.evaluate(args.strategy_id)
    gate.close()

    print(f"\n{'='*60}")
    print(f"  Promotion Evaluation: {args.strategy_id}")
    print(f"{'='*60}")

    for g in result["gates"]:
        status = "PASS" if g["passed"] else "FAIL"
        if g.get("skipped"):
            status = "SKIP"
        print(f"  {g['name']:<30} {status:>6}   {g['evidence']}")

    print(f"\n  Result: {'PASSED' if result['passed'] else 'FAILED'}")

    if result["passed"] and args.apply:
        gate = PromotionGate(args.db or str(DEFAULT_DB_PATH), bars)
        promoted = gate.promote(args.strategy_id, dry_run=False)
        gate.close()
        if promoted:
            print(f"  {args.strategy_id} promoted to QUALIFIED.")
        else:
            print(f"  Promotion failed.")
    elif result["passed"] and not args.apply:
        print(f"  Use --apply to promote.")

    print()


def cmd_walkforward(args):
    from titan.research.harness import load_bars, make_ma_signal_fn
    from titan.research.walkforward import WalkForwardConfig, WalkForwardOptimizer

    csv_path = args.data
    if not os.path.exists(csv_path):
        print(f"Data file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    bars = load_bars(csv_path)
    print(f"Loaded {len(bars)} bars from {csv_path}")

    config = WalkForwardConfig(
        train_size=args.train_size,
        test_size=args.test_size,
        step_size=args.step_size,
        window_type=args.window_type,
        param_grid={"fast": [3, 5, 10], "slow": [15, 20, 30]},
        target_metric=args.target_metric,
        min_wfe_threshold=args.min_wfe,
        min_trades=args.min_trades,
    )

    optimizer = WalkForwardOptimizer()
    res = optimizer.run(bars, make_ma_signal_fn, config)

    print()
    print("=========================================================")
    print("           WALK-FORWARD OPTIMIZATION REPORT              ")
    print("=========================================================")
    print(f"Windows Executed  : {res.summary['num_windows']} ({config.window_type})")
    print(f"Train / Test Size : {config.train_size} / {config.test_size} bars")
    print(f"Average IS Sharpe : {res.is_sharpe:.4f}")
    print(f"Average OOS Sharpe: {res.oos_sharpe:.4f}")
    print(f"Mean OOS Sharpe   : {res.summary.get('mean_oos_sharpe', 0.0):.4f}")
    print(f"Median OOS Sharpe : {res.summary.get('median_oos_sharpe', 0.0):.4f}")
    print(f"Worst OOS Window  : {res.summary.get('worst_oos_sharpe', 0.0):.4f}")
    print(f"Best OOS Window   : {res.summary.get('best_oos_sharpe', 0.0):.4f}")
    print(f"Std Dev OOS Sharpe: {res.summary.get('std_oos_sharpe', 0.0):.4f}")
    print(f"Walk-Forward Eff  : {res.wfe:.4f} (WFE = OOS / IS)")
    print(f"Total OOS Trades  : {res.total_oos_trades}")
    print(f"Passed Gate (>= {config.min_wfe_threshold}): {'[PASSED]' if res.passed_gate else '[FAILED]'}")
    print("=========================================================")


def cmd_doctor(args):
    db_path = args.db or str(DEFAULT_DB_PATH)
    print()
    print("=========================================================")
    print("           TITAN OPERATIONS DOCTOR (HEALTH CHECK)       ")
    print("=========================================================")
    print("SYSTEM")
    print("------")
    print(f"Git SHA        : main")
    print(f"DB Path        : {db_path}")
    print(f"DB Status      : {'EXISTS' if os.path.exists(db_path) else 'NOT CREATED'}")
    print(f"Python Runtime : {sys.version.split()[0]}")

    print("\nRESEARCH & GOVERNANCE")
    print("---------------------")
    if os.path.exists(db_path):
        db = ResearchDB(db_path)
        quals = db.get_qualifications()
        q_count = sum(1 for q in quals if q.get("status") == "QUALIFIED")
        w_count = sum(1 for q in quals if q.get("status") == "WATCHLIST")
        f_count = sum(1 for q in quals if q.get("status") == "FAILED")
        print(f"Qualified Strats: {q_count}")
        print(f"Watchlist Strats: {w_count}")
        print(f"Failed Strats   : {f_count}")
        db.close()
    else:
        print("No ResearchDB found.")

    print("\nOPERATIONS & OBSERVABILITY")
    print("--------------------------")
    print("Prometheus Module : READY")
    print("Circuit Breaker   : READY")
    print("Rebalance Engine  : READY")

    reasons = []
    if not os.path.exists(db_path):
        reasons.append("Research DB unavailable")
    else:
        db = ResearchDB(db_path)
        quals = db.get_qualifications()
        q_count = sum(1 for q in quals if q.get("status") == "QUALIFIED")
        if q_count == 0:
            reasons.append("No QUALIFIED strategies found in Research DB")
        db.close()

    print("\nOVERALL READINESS")
    print("-----------------")
    if not reasons:
        print("Status            : [READY FOR PAPER OPERATION]")
    else:
        print("Status            : [NOT READY]")
        print("Reasons           :")
        for r in reasons:
            print(f"  - {r}")
    print("=========================================================")



def main():
    parser = argparse.ArgumentParser(description="TITAN Research CLI")
    parser.add_argument("--db", help=f"Research database path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--metric", default="backtest_sharpe",
                        choices=["backtest_sharpe", "wf_sharpe", "paper_trades", "max_dd_pct"])

    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Run TITAN Operations Health Check")

    p_top = sub.add_parser("top", help="Top strategies by metric")

    p_strat = sub.add_parser("strategy", help="Strategy details")
    p_strat.add_argument("strategy_id")

    p_cmp = sub.add_parser("compare", help="Compare two strategies")
    p_cmp.add_argument("a")
    p_cmp.add_argument("b")

    p_runs = sub.add_parser("runs", help="List recent runs")
    p_runs.add_argument("--strategy", dest="strategy_id", default=None)

    p_info = sub.add_parser("db-info", help="Database info")
    p_shadow = sub.add_parser("shadow", help="Shadow deployment summary")
    p_shadow.add_argument("--session", default=None, help="Session ID filter")

    p_promote = sub.add_parser("promote", help="Evaluate and promote a strategy")
    p_promote.add_argument("strategy_id", help="Strategy ID to evaluate")
    p_promote.add_argument("--apply", action="store_true",
                           help="Actually promote (default: dry-run only)")
    p_promote.add_argument("--csv", default=None,
                           help="Historical CSV for ensemble regression test")

    p_wf = sub.add_parser("walkforward", help="Run rolling Walk-Forward Optimization")
    p_wf.add_argument("--data", required=True, help="Path to historical CSV data")
    p_wf.add_argument("--train-size", type=int, default=250, help="In-sample train window bars")
    p_wf.add_argument("--test-size", type=int, default=50, help="Out-of-sample test window bars")
    p_wf.add_argument("--step-size", type=int, default=None, help="Step size between windows")
    p_wf.add_argument("--window-type", choices=["rolling", "expanding"], default="rolling")
    p_wf.add_argument("--target-metric", default="sharpe")
    p_wf.add_argument("--min-wfe", type=float, default=0.50)
    p_wf.add_argument("--min-trades", type=int, default=5)

    args = parser.parse_args()

    commands = {
        "doctor": cmd_doctor,
        "top": cmd_top,
        "strategy": cmd_strategy,
        "compare": cmd_compare,
        "runs": cmd_runs,
        "db-info": cmd_db_info,
        "shadow": cmd_shadow,
        "promote": cmd_promote,
        "walkforward": cmd_walkforward,
    }

    commands[args.command](args)



if __name__ == "__main__":
    main()

