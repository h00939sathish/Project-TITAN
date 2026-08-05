#!/usr/bin/env python3
"""TITAN Research Validation Pipeline — hypothesis-driven, multi-benchmark.

Usage:
    python scripts/validate.py [--data path/to/bars.csv] [--hypothesis-id ID]

Pre-register a hypothesis in knowledge/research/hypotheses/ before running.
Outputs results to stdout and the experiment record to knowledge/research/experiments/.
"""

import argparse
import statistics
import sys
from pathlib import Path

import titan.strategies.registrations  # noqa: F401 — triggers strategy registration
from titan.backtest.results import BacktestResult
from titan.data.manifest import DataManifest
from titan.research.gate import check_min_trades
from titan.research.harness import (
    ValidationHarness,
    buy_and_hold_result,
    cash_result,
    load_bars,
    run_backtest_result,
    split_bars,
    walk_forward,
)
from titan.research.hypothesis import Hypothesis
from titan.research.metrics import (
    identify_regimes,
)
from titan.strategies.registry import get_registry

HYPOTHESES_DIR = Path("knowledge/research/hypotheses")
EXPERIMENTS_DIR = Path("knowledge/research/experiments")


def load_hypothesis(hyp_id: str) -> Hypothesis:
    """Load a preregistered hypothesis from its markdown file."""
    path = HYPOTHESES_DIR / f"{hyp_id}.md"
    if not path.exists():
        print(f"ERROR: Hypothesis not found: {path}", file=sys.stderr)
        print(f"  Preregister one at {HYPOTHESES_DIR}/ before running.", file=sys.stderr)
        sys.exit(1)

    lines = path.read_text().splitlines()
    meta = {}
    current_key = None
    current_val: list[str] = []
    for line in lines:
        if line.startswith("**") and ":**" in line:
            if current_key:
                meta[current_key] = "\n".join(current_val).strip()
            colon = line.index(":**")
            current_key = line[2:colon].strip()
            current_val = [line[colon + 3:].strip()]
        elif current_key and line.startswith("- "):
            current_val.append(line[2:].strip())
        elif current_key and line.strip():
            current_val.append(line.strip())

    if current_key:
        meta[current_key] = "\n".join(current_val).strip()

    success_raw = meta.get("success_criteria", "").split("\n")
    failure_raw = meta.get("failure_criteria", "").split("\n")

    success_criteria = [s.strip() for s in success_raw if s.strip() and not s.strip().startswith("**")]
    failure_criteria = [s.strip() for s in failure_raw if s.strip() and not s.strip().startswith("**")]

    params_raw = meta.get("strategy_params", "")
    params = {}
    for part in params_raw.replace(";", ",").split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                params[k.strip()] = int(v.strip())
            except ValueError:
                try:
                    params[k.strip()] = float(v.strip())
                except ValueError:
                    params[k.strip()] = v.strip()

    return Hypothesis(
        id=meta.get("id", hyp_id),
        title=meta.get("title", ""),
        economic_rationale=meta.get("economic_rationale", ""),
        strategy_id=meta.get("strategy_id", ""),
        strategy_params=params,
        instrument=meta.get("instrument", ""),
        universe=meta.get("universe", ""),
        calendar=meta.get("calendar", ""),
        train_period=meta.get("train_period", ""),
        test_period=meta.get("test_period", ""),
        success_criteria=success_criteria,
        failure_criteria=failure_criteria,
        costs=meta.get("costs", ""),
        expected_trade_frequency=meta.get("expected_trade_frequency", ""),
        sample_adequacy_policy=meta.get("sample_adequacy_policy", "Path A"),
        path_b_evidence_standard=meta.get("path_b_evidence_standard", ""),
        notes=meta.get("notes", ""),
        status="running",
    )


def print_report(report):
    """Print formatted validation report."""
    h = report.hypothesis
    b = report.candidate_result
    bh = report.bh_result
    cash_r = report.cash_result
    control = report.ma_control_result

    print("=" * 60)
    print(f"TITAN Validation Report")
    print(f"Hypothesis: {h.title} ({h.id})")
    print("=" * 60)

    print(f"\n  Strategy: {h.strategy_id}")
    print(f"  Parameters: {h.strategy_params}")
    print(f"  Trade frequency (expected): {h.expected_trade_frequency}")
    print(f"  Sample-adequacy policy: {h.sample_adequacy_policy}")
    if h.sample_adequacy_policy == "Path B":
        print(f"  Path B evidence standard: {h.path_b_evidence_standard}")
    print(f"  Test period: {h.test_period}")

    print(f"\n  OOS bars: {len(report.test_bars)}")

    print(f"\n  {'Metric':<25} {'Candidate':>12} {'BH':>12} {'Cash':>12} {'MA(5,20)':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Return %':<25} {b.total_return_pct if b else 0:>12.2f} "
          f"{bh.total_return_pct if bh else 0:>12.2f} "
          f"{cash_r.total_return_pct if cash_r else 0:>12.2f} "
          f"{control.total_return_pct if control else 0:>12.2f}")
    print(f"  {'CAGR %':<25} {report.cagr.get('candidate', 0):>12.2f} "
          f"{report.cagr.get('buy_and_hold', 0):>12.2f} "
          f"{report.cagr.get('cash', 0):>12.2f} "
          f"{report.cagr.get('ma_control_5_20', 0):>12.2f}")
    print(f"  {'Sharpe':<25} {b.sharpe_ratio if b else 0:>12.4f} "
          f"{bh.sharpe_ratio if bh else 0:>12.4f} "
          f"{'N/A':>12} "
          f"{control.sharpe_ratio if control else 0:>12.4f}")
    print(f"  {'Max DD %':<25} {b.max_drawdown_pct if b else 0:>12.2f} "
          f"{bh.max_drawdown_pct if bh else 0:>12.2f} "
          f"{cash_r.max_drawdown_pct if cash_r else 0:>12.2f} "
          f"{control.max_drawdown_pct if control else 0:>12.2f}")
    print(f"  {'Win Rate %':<25} {b.win_rate if b else 0:>12.1f} "
          f"{'N/A':>12} {'N/A':>12} "
          f"{control.win_rate if control else 0:>12.1f}")
    print(f"  {'Total Trades':<25} {b.total_trades if b else 0:>12} "
          f"{'0':>12} {'0':>12} "
          f"{control.total_trades if control else 0:>12}")

    print(f"\n  Turnover (total): {report.turnover.get('total_turnover_pct', 0):.1f}%")
    print(f"  Time in market:   {report.exposure.get('time_in_market_pct', 0):.1f}%")
    print(f"  Longest flat:     {report.exposure.get('longest_flat_period_bars', 0)} bars")
    print(f"  BH exposure-adj:  {report.exposure_adj_bh.get('adjusted_return_pct', 0):.2f}%")

    print(f"\n  Block bootstrap (5th pctl): {report.block_bootstrap.get('p5', 0):.2f}")

    print(f"\n  Walk-Forward windows: {len(report.walk_forward_results)}")
    wf_sharpes = [r.sharpe_ratio for r in report.walk_forward_results]
    if wf_sharpes:
        print(f"  Walk-Forward mean Sharpe: {statistics.mean(wf_sharpes):.4f}")

    print(f"\n  Gate: {'YES' if report.gate_result and report.gate_result.passed else 'NO'}")
    print(f"  Trades: {report.candidate_result.total_trades if report.candidate_result else 0} "
          f"(min {report.gate_result.minimum_required if report.gate_result else 30})")
    print(f"  Success: {'YES' if report.success else 'NO'}")


def write_experiment(report) -> None:
    """Write experiment record to knowledge/research/experiments/."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    exp_file = EXPERIMENTS_DIR / f"{report.hypothesis.id}.md"

    b = report.candidate_result
    bh = report.bh_result
    cash_r = report.cash_result
    control = report.ma_control_result
    g = report.gate_result
    bb = report.block_bootstrap
    h = report.hypothesis

    notes = (
        f"Gate: {'PASSED' if report.success else 'FAILED'}. "
        f"OOS trade count: {b.total_trades if b else 0}. "
        f"Policy: {h.sample_adequacy_policy}. "
        f"Candidate vs BH return: {b.total_return_pct if b else 0:.2f}% vs {bh.total_return_pct if bh else 0:.2f}%. "
        f"Block bootstrap 5th pctl: {bb.get('p5', 0):.2f}."
    )

    with open(exp_file, "w") as f:
        f.write(f"""# Experiment: {report.hypothesis.id}

**id:** {report.hypothesis.id}
**title:** {report.hypothesis.title}
**economic_rationale:** {report.hypothesis.economic_rationale}
**strategy_id:** {h.strategy_id}
**strategy_params:** {h.strategy_params}
**instrument:** {h.instrument}
**universe:** {h.universe}
**calendar:** {h.calendar}
**train_period:** {h.train_period}
**test_period:** {h.test_period}
**success_criteria:** {', '.join(h.success_criteria)}
**failure_criteria:** {', '.join(h.failure_criteria)}
**costs:** {h.costs}
**expected_trade_frequency:** {h.expected_trade_frequency}
**sample_adequacy_policy:** {h.sample_adequacy_policy}
**path_b_evidence_standard:** {h.path_b_evidence_standard}
**status:** completed
**success:** {'YES' if report.success else 'NO'}

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | {b.total_return_pct if b else 0:.2f}% | {bh.total_return_pct if bh else 0:.2f}% | {cash_r.total_return_pct if cash_r else 0:.2f}% | {control.total_return_pct if control else 0:.2f}% |
| CAGR | {report.cagr.get('candidate', 0):.2f}% | {report.cagr.get('buy_and_hold', 0):.2f}% | {report.cagr.get('cash', 0):.2f}% | {report.cagr.get('ma_control_5_20', 0):.2f}% |
| Sharpe Ratio | {b.sharpe_ratio if b else 0:.4f} | {bh.sharpe_ratio if bh else 0:.4f} | N/A | {control.sharpe_ratio if control else 0:.4f} |
| Max Drawdown | {b.max_drawdown_pct if b else 0:.2f}% | {bh.max_drawdown_pct if bh else 0:.2f}% | {cash_r.max_drawdown_pct if cash_r else 0:.2f}% | {control.max_drawdown_pct if control else 0:.2f}% |
| Win Rate | {b.win_rate if b else 0:.1f}% | N/A | N/A | {control.win_rate if control else 0:.1f}% |
| Total Trades | {b.total_trades if b else 0} | 0 | 0 | {control.total_trades if control else 0} |

### Extended Metrics
- Turnover (total): {report.turnover.get('total_turnover_pct', 0):.1f}%
- Time in market: {report.exposure.get('time_in_market_pct', 0):.1f}%
- Longest flat period: {report.exposure.get('longest_flat_period_bars', 0)} bars
- Buy-and-hold exposure-adjusted return: {report.exposure_adj_bh.get('adjusted_return_pct', 0):.2f}%
- Buy-and-hold exposure-adjusted max drawdown: {report.exposure_adj_bh.get('adjusted_max_dd_pct', 0):.2f}%

### Block Bootstrap (OOS)
- Method: {bb.get('method', 'N/A')}
- Mean PnL: {bb.get('mean', 0):.2f}
- Median PnL: {bb.get('median', 0):.2f}
- Std PnL: {bb.get('std', 0):.2f}
- 5th pctl: {bb.get('p5', 0):.2f}
- 95th pctl: {bb.get('p95', 0):.2f}

### Parameter Sensitivity (OOS)
{chr(10).join(f'- {label}: return={r.total_return_pct:.2f}%, sharpe={r.sharpe_ratio:.4f}, dd={r.max_drawdown_pct:.2f}%, trades={r.total_trades}' for label, r in sorted(report.parameter_sweep.items()))}

### Walk-Forward
- Windows: {len(report.walk_forward_results)}
- Mean Sharpe: {statistics.mean([r.sharpe_ratio for r in report.walk_forward_results]):.4f}

### Gate
- Min trades: {g.minimum_required if g else 'N/A'}
- Actual trades: {g.trade_count if g else 'N/A'}
- Passed: {'YES' if g and g.passed else 'NO'}
- Reason: {g.reason if g else 'N/A'}

**notes:** {notes}
""")


def main():
    parser = argparse.ArgumentParser(description="TITAN Research Validation Pipeline")
    parser.add_argument("--data", default="tests/fixtures/market/spy_2020_2024.csv",
                        help="Path to OHLCV CSV")
    parser.add_argument("--hypothesis-id", default="2026-07-13-ma-50-200",
                        help="ID of preregistered hypothesis (file in knowledge/research/hypotheses/)")
    parser.add_argument("--info", action="store_true",
                        help="List available hypotheses and strategies and exit")
    args = parser.parse_args()

    HYPOTHESES_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.info:
        reg = get_registry()
        print("Registered strategies:")
        for sid in reg.list_ids():
            r = reg.get(sid)
            print(f"  {sid}  v{r.version} — {r.description}")
        print("\nAvailable hypotheses:")
        for p in sorted(HYPOTHESES_DIR.glob("*.md")):
            print(f"  {p.stem}")
        return 0

    hypothesis = load_hypothesis(args.hypothesis_id)

    reg = get_registry()
    try:
        registration = reg.get(hypothesis.strategy_id)
    except KeyError:
        print(f"ERROR: Hypothesis '{args.hypothesis_id}' has strategy_id="
              f"'{hypothesis.strategy_id}' which is not registered.",
              file=sys.stderr)
        sys.exit(1)

    errors = reg.validate_params(hypothesis.strategy_id, hypothesis.strategy_params)
    if errors:
        print(f"ERROR: Parameter validation failed for strategy '{hypothesis.strategy_id}':",
              file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    harness = ValidationHarness(hypothesis, args.data,
                                signal_factory=registration.factory)
    report = harness.run()

    print_report(report)
    write_experiment(report)

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
