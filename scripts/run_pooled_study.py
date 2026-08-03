#!/usr/bin/env python3
"""Pooled multi-instrument study — SPY+QQQ volatility-regime (Stream C)."""

import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

from titan.research.harness import make_vol_regime_signal_fn
from titan.research.hypothesis import Hypothesis
from titan.research.multi_harness import InstrumentSpec, MultiInstrumentHarness

EXPERIMENTS_DIR = Path("knowledge/research/experiments")


def compute_data_digest(paths: list[str]) -> str:
    sha = hashlib.sha256()
    for p in sorted(paths):
        sha.update(Path(p).read_bytes())
    return sha.hexdigest()


def compute_code_digest() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def compute_config_digest(h: Hypothesis) -> str:
    sha = hashlib.sha256()
    sha.update(f"{h.strategy_id}:{sorted(h.strategy_params.items())}".encode())
    return sha.hexdigest()


def print_report(report):
    h = report.hypothesis
    print("=" * 70)
    print("TITAN Pooled Multi-Instrument Study")
    print(f"Hypothesis: {h.title} ({h.id})")
    print("=" * 70)

    print(f"\n  Strategy: {h.strategy_id}")
    print(f"  Parameters: {h.strategy_params}")
    print(f"  Universe: {h.universe}")
    print(f"  Test period: {h.test_period}")

    print(f"\n  {'-'*68}")
    print(f"  {'Instrument':<12} {'Trades':>8} {'Return%':>10} {'Sharpe':>10} "
          f"{'MaxDD%':>10} {'WinRate%':>10}")
    print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for spec in report.instruments:
        r = spec.result
        if r:
            print(f"  {spec.instrument_id:<12} {r.total_trades:>8} "
                  f"{r.total_return_pct:>10.2f} {r.sharpe_ratio:>10.4f} "
                  f"{r.max_drawdown_pct:>10.2f} {r.win_rate:>10.1f}")

    p = report.pooled_result
    print(f"\n  {'-'*68}")
    print(f"  {'Metric':<30} {'Pooled':>15}")
    print(f"  {'-'*30} {'-'*15}")
    if p:
        print(f"  {'Total Return %':<30} {p.total_return_pct:>15.2f}")
        print(f"  {'Sharpe (pooled eq)':<30} {p.sharpe_ratio:>15.4f}")
        print(f"  {'Max Drawdown %':<30} {p.max_drawdown_pct:>15.2f}")

    print(f"\n  Pairwise Correlations:")
    for c in report.correlations:
        print(f"    {c.instrument_a} vs {c.instrument_b}: r={c.pearson_r:.4f} "
              f"(n={c.observation_count} days)")

    print(f"\n  Trade Accounting:")
    print(f"    Raw total trades (sum): {report.total_pooled_trades}")
    print(f"    Avg pairwise correlation: {report.avg_pairwise_corr:.4f}")
    print(f"    Effective trades (discounted): {report.effective_trades:.1f}")
    for spec in report.instruments:
        print(f"    {spec.instrument_id}: {len(spec.trades)} trades "
              f"({len(spec.trades)/max(report.total_pooled_trades,1)*100:.1f}%)")

    if report.per_instrument_violations:
        print(f"    *** Per-instrument minimum violations:")
        for v in report.per_instrument_violations:
            print(f"      - {v}")

    g = report.gate_result
    print(f"\n  Gate:")
    print(f"    Minimum required: {g.minimum_required}")
    print(f"    Effective trades: {g.trade_count}")
    print(f"    Passed: {'YES' if g.passed else 'NO'}")
    if g.reason:
        print(f"    Reason: {g.reason}")

    print(f"\n  Overall Success: {'YES' if report.success else 'NO'}")

    print(f"\n  {'-'*68}\n")


def write_experiment(report, digest):
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    exp_file = EXPERIMENTS_DIR / f"{report.hypothesis.id}.md"

    h = report.hypothesis
    p = report.pooled_result
    bh = report.bh_result
    g = report.gate_result

    per_inst_lines = []
    for spec in report.instruments:
        r = spec.result
        per_inst_lines.append(
            f"- {spec.instrument_id}: {r.total_trades} trades, "
            f"return {r.total_return_pct:.2f}%, "
            f"Sharpe {r.sharpe_ratio:.4f}, "
            f"max DD {r.max_drawdown_pct:.2f}%, "
            f"win rate {r.win_rate:.1f}%"
        )

    corr_lines = [
        f"- {c.instrument_a} vs {c.instrument_b}: r={c.pearson_r:.4f} "
        f"(n={c.observation_count})"
        for c in report.correlations
    ]

    notes = (
        f"Gate: {'PASSED' if report.success else 'FAILED'}. "
        f"Effective OOS trades: {g.trade_count}. "
        f"Raw trades: {report.total_pooled_trades}. "
        f"Avg pairwise corr: {report.avg_pairwise_corr:.4f}. "
        f"Pooled Sharpe: {p.sharpe_ratio if p else 0:.4f}. "
        f"Pooled return: {p.total_return_pct if p else 0:.2f}%."
    )

    with open(exp_file, "w") as f:
        f.write(f"""# Experiment: {report.hypothesis.id}

**id:** {report.hypothesis.id}
**title:** {report.hypothesis.title}
**economic_rationale:** {report.hypothesis.economic_rationale}
**strategy_id:** {h.strategy_id}
**strategy_params:** {h.strategy_params}
**data_digest:** {digest['data_digest']}
**code_digest:** {digest['code_digest']}
**config_digest:** {digest['config_digest']}
**seed:** {digest['seed']}
**frozen_at:** {digest['frozen_at']}
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

### Per-Instrument (OOS)

{chr(10).join(per_inst_lines)}

### Pooled Equity Metrics (OOS)

- Total Return: {p.total_return_pct if p else 0:.2f}%
- Sharpe Ratio: {p.sharpe_ratio if p else 0:.4f}
- Max Drawdown: {p.max_drawdown_pct if p else 0:.2f}%
- Buy-and-Hold (pooled) Return: {bh.total_return_pct if bh else 0:.2f}%

### Pairwise Correlations

{chr(10).join(corr_lines)}

### Trade Accounting

- Raw total trades: {report.total_pooled_trades}
- Average pairwise correlation: {report.avg_pairwise_corr:.4f}
- Effective trades (discounted): {report.effective_trades:.1f}
- Per-instrument distribution: {', '.join(f'{s.instrument_id}={len(s.trades)}' for s in report.instruments)}

### Gate

- Min trades: {g.minimum_required}
- Effective trades: {g.trade_count}
- Passed: {'YES' if g.passed else 'NO'}
- Reason: {g.reason}

**notes:** {notes}
""")


def main():
    hypothesis = Hypothesis(
        id="2026-07-13-volatility-regime-pooled-spy-qqq",
        title="Pooled volatility-regime timing on SPY+QQQ",
        economic_rationale=(
            "Pooled test of volatility-regime timing across two highly "
            "correlated US equity indices. Uses the pooled-trade-count policy "
            "to discount effective trades for cross-instrument correlation."
        ),
        strategy_id="volatility-regime",
        strategy_params={"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
        instrument="SPY+QQQ",
        universe="SPY, QQQ",
        calendar="2020-01-02 to 2024-12-31",
        train_period="2020-01-02",
        test_period="2023-01-01",
        expected_trade_frequency="~30-60 transitions/year (combined)",
        sample_adequacy_policy="Path A",
        success_criteria=[
            "Sharpe > 0.3 OOS",
            "Max drawdown < SPY benchmark max drawdown OOS",
        ],
        failure_criteria=["Sharpe < 0 OOS"],
        costs="1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()",
        notes=(
            "Pooled study using MultiInstrumentHarness with SPY+QQQ. "
            "Effective trades computed via pooled-trade-count policy."
        ),
    )

    instruments = [
        InstrumentSpec(
            instrument_id="SPY",
            data_path="tests/fixtures/market/spy_2020_2024.csv",
        ),
        InstrumentSpec(
            instrument_id="QQQ",
            data_path="tests/fixtures/market/qqq_2020_2024.csv",
        ),
    ]

    harness = MultiInstrumentHarness(
        hypothesis=hypothesis,
        instruments=instruments,
        signal_factory=make_vol_regime_signal_fn,
    )
    report = harness.run()

    digest = {
        "data_digest": compute_data_digest([s.data_path for s in instruments]),
        "code_digest": compute_code_digest(),
        "config_digest": compute_config_digest(hypothesis),
        "seed": 42,
        "frozen_at": date.today().isoformat(),
    }

    print_report(report)
    write_experiment(report, digest)

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
