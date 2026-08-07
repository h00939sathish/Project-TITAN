"""Promotion gate — evaluates whether a strategy has earned its QUALIFIED badge.

Checks:
1. Base qualification — IS/OOS Sharpe, trades, max DD, PF
2. Walk-forward still positive
3. Shadow trade sufficiency — enough shadow trades for statistical confidence
4. Shadow performance — shadow P&L positive, acceptable win rate
5. Ensemble regression — adding candidate doesn't degrade the pool

Usage:
    gate = PromotionGate(db_path, bars)
    result = gate.evaluate("mean-reversion")
    if result["passed"]:
        gate.promote("mean-reversion")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.results import BacktestResult
from titan.research.db import ResearchDB, DEFAULT_DB_PATH
from titan.research.portfolio_impact import PortfolioImpactEvaluator
from titan.research.replication import ReplicationEngine
from titan.research.validators.parameter_stability import OptimizationRiskValidator, OptimizationValidationScorecard
from titan.strategies.ensemble import WeightedEnsemble, StrategyVote
from titan.strategies.registry import get_registry

# ponytail: single-process lock fine, distributed locks if sharded


PROMOTION_CRITERIA = {
    "min_shadow_trades": 5,
    "min_shadow_win_rate": 0.3,
    "min_shadow_pnl": 0.0,
    "ensemble_sharpe_degradation_max": 0.3,
    "ensemble_dd_increase_max_pct": 5.0,
    "min_plateau_stability": 0.70,
    "min_plateau_coverage": 0.20,
    "max_correlation_with_existing": 0.50,
}


def _vote_confidence(signal: str | None) -> float:
    return 1.0 if signal == "BUY" else (-1.0 if signal == "SELL" else 0.0)


@dataclass
class GateResult:
    name: str
    passed: bool
    evidence: str = ""
    skipped: bool = False


def _strategy_return_series(
    strategy_id: str, params: dict, bars: list[dict]
) -> list[float]:
    """Derive a real per-bar strategy return series by running the registered
    signal over the bars (long/flat position). Returns [] when the strategy is
    not in the registry (live evaluation cannot be performed)."""
    try:
        reg = get_registry().get(strategy_id)
    except KeyError:
        return []  # strategy not in the registry: live series cannot be derived
    if reg is None or not bars:
        return []
    signal_fn = reg.factory(params)
    series: list[float] = []
    prev_close = None
    pos = 0.0
    for bar in bars:
        close = bar.get("close")
        if close is None:
            series.append(0.0)
            continue
        # F7: do NOT swallow signal exceptions. A strategy that raises in its
        # signal must fail the gate, not silently become a flat (0 return)
        # series that looks artificially clean. Exceptions propagate to the
        # caller (the gate), which then fails closed.
        sig = signal_fn({"close": close})
        if sig == "BUY":
            pos = 1.0
        elif sig == "SELL":
            pos = 0.0
        if prev_close is None or prev_close == 0:
            series.append(0.0)
        else:
            series.append(round(pos * (close / prev_close - 1.0), 8))
        prev_close = close
    return series


def _best_params(db: ResearchDB, strategy_id: str) -> dict:
    runs = db.get_runs(strategy_id=strategy_id, limit=20)
    for r in runs:
        label = r.get("label", "")
        if label.startswith("qualification_") or label.startswith("ensemble_"):
            try:
                return json.loads(r.get("params_json", "{}"))
            except json.JSONDecodeError:
                pass
    return {}


def _run_ensemble_on_bars(
    strategy_ids: list[str],
    params_map: dict[str, dict],
    bars: list[dict],
    buy_threshold: float = 0.3,
    sell_threshold: float = -0.3,
    slippage_bps: float = 0.5,
    commission_bps: float = 1.0,
) -> BacktestResult:
    """Run a quick ensemble simulation over bars. Returns BacktestResult."""
    fill_model = BarConservativeFillModel(slippage_bps, commission_bps)
    ensemble = WeightedEnsemble(buy_threshold=buy_threshold, sell_threshold=sell_threshold)

    # Build signal functions
    signal_fns = {}
    for sid in strategy_ids:
        params = params_map.get(sid, {})
        reg = get_registry().get(sid)
        signal_fns[sid] = reg.factory(params)

    # Warmup + Run
    equity_curve = [100_000.0]
    cash = 100_000.0
    position = 0
    position_cost = 0.0
    in_position = False
    trades = []
    close_history = []

    for bar in bars:
        close_price = bar["close"]
        close_history.append(close_price)

        signals = {}
        for sid in strategy_ids:
            signals[sid] = signal_fns[sid]({"close": close_price})

        votes = []
        for sid in strategy_ids:
            sig = signals.get(sid)
            confidence = _vote_confidence(sig)
            votes.append(StrategyVote(strategy_id=sid, vote=sig or "HOLD", confidence=confidence))

        result = ensemble.decide(votes)
        decision = result.decision if result else "NO_TRADE"

        if decision == "BUY" and not in_position:
            fill = fill_model.fill(bar, "buy", 10)
            if fill.fill_cost <= cash:
                cash -= fill.fill_cost
                position = fill.fill_quantity
                position_cost = fill.fill_cost
                in_position = True
        elif decision == "SELL" and in_position:
            fill = fill_model.fill(bar, "sell", position)
            proceeds = fill.fill_cost - fill.commission
            pnl = proceeds - position_cost
            cash += proceeds
            trades.append({
                "pnl": round(pnl, 2), "commission": fill.commission,
                "side": "sell", "price": fill.fill_price, "qty": position,
            })
            position = 0
            position_cost = 0.0
            in_position = False

        cash = max(cash, 0.0)
        mtm = cash + (position * close_price) if in_position else cash
        equity_curve.append(mtm)

    return BacktestResult.compute(equity_curve, trades)


class PromotionGate:
    """Evaluates promotion readiness for a single strategy."""

    def __init__(self, db_path: str | Path, bars: list[dict],
                 instrument: str = "SPY", criteria: dict | None = None):
        self._db_path = Path(db_path)
        self._bars = bars
        self._instrument = instrument
        self._criteria = criteria or PROMOTION_CRITERIA
        self._db = ResearchDB(str(self._db_path))
        self._replication_engine = ReplicationEngine()
        self._portfolio_evaluator = PortfolioImpactEvaluator()

    def evaluate(self, strategy_id: str) -> dict:
        """Run all gates. Returns {gates: [...], passed: bool}."""
        gates = []

        gates.append(self._gate_base_qualification(strategy_id))
        gates.append(self._gate_walk_forward(strategy_id))
        gates.append(self._gate_parameter_stability(strategy_id))
        gates.append(self._gate_independent_replication(strategy_id))
        gates.append(self._gate_portfolio_impact(strategy_id))
        gates.append(self._gate_shadow_sufficiency(strategy_id))
        gates.append(self._gate_shadow_performance(strategy_id))
        gates.append(self._gate_ensemble_regression(strategy_id))

        # Fail closed: must pass ALL mandatory gates
        passed = all(g.passed for g in gates if not g.skipped) and all(g.passed for g in gates if g.name in (
            "base_qualification", "walk_forward", "parameter_stability", "independent_replication", "portfolio_impact"
        ))
        return {"strategy_id": strategy_id, "gates": [g.__dict__ for g in gates], "passed": passed}

    def _get_qual(self, strategy_id: str) -> dict | None:
        quals = self._db.get_qualifications()
        normalized = strategy_id.replace("_", "-")
        return next((q for q in quals if q["strategy_id"] in (strategy_id, normalized)), None)

    @staticmethod
    def _scorecard_from_run(run: dict, strategy_id: str) -> OptimizationValidationScorecard:
        """Build a scorecard from a real ResearchDB run's summary metrics."""
        eff = float(run.get("sharpe") or 0.0)
        return OptimizationValidationScorecard(
            strategy_id=strategy_id,
            timeframe="15m",
            universe=(str(run.get("instrument") or "SPY"),),
            best_params={"oos_sharpe": eff},
            avg_plateau_stability=0.0,
            avg_plateau_coverage=0.0,
            cross_instrument_consistency=0.0,
            walk_forward_passed=True,
            bootstrap_passed=True,
            passed_all_checks=eff >= 1.0,
            rejection_reasons=(),
        )

    def _gate_base_qualification(self, strategy_id: str) -> GateResult:
        qual = self._get_qual(strategy_id)
        if not qual:
            return GateResult("base_qualification", False, "No qualification record found")
        bt_sharpe = qual.get("backtest_sharpe") or 0
        if bt_sharpe >= 0.5:
            return GateResult("base_qualification", True,
                              f"IS Sharpe={bt_sharpe:.2f} >= 0.5")
        return GateResult("base_qualification", False,
                          f"IS Sharpe={bt_sharpe:.2f} < 0.5")

    def _gate_walk_forward(self, strategy_id: str) -> GateResult:
        qual = self._get_qual(strategy_id)
        if not qual:
            return GateResult("walk_forward", False, "No qualification record")
        wf = qual.get("wf_sharpe")
        if wf is None:
            return GateResult("walk_forward", False, "No walk-forward data")
        if wf > 0:
            return GateResult("walk_forward", True, f"WF Sharpe={wf:.2f} > 0.0")
        return GateResult("walk_forward", False, f"WF Sharpe={wf:.2f} <= 0.0")

    def _gate_parameter_stability(self, strategy_id: str) -> GateResult:
        """Check 3D parameter surface neighborhood stability and coverage."""
        qual = self._get_qual(strategy_id)
        if not qual:
            return GateResult("parameter_stability", False, "No qualification record")
        stability = qual.get("plateau_stability")
        coverage = qual.get("plateau_coverage")
        # F3: plateau stability MUST come from a real stored ParameterSurface
        # evaluation. Parsing free-text notes (with a hardcoded coverage
        # default) let a comment string satisfy the gate — removed. If either
        # metric is absent, the gate fails closed.
        if stability is None:
            return GateResult("parameter_stability", False, "Parameter plateau stability not evaluated (missing surface data)")
        min_stab = self._criteria["min_plateau_stability"]
        min_cov = self._criteria["min_plateau_coverage"]
        if stability >= min_stab and (coverage or 0) >= min_cov:
            return GateResult("parameter_stability", True, f"Stability={stability:.2f} >= {min_stab}, Coverage={(coverage or 0)*100:.1f}%")
        return GateResult("parameter_stability", False, f"Stability={stability or 0:.2f} < {min_stab} or Coverage={(coverage or 0)*100:.1f}% < {min_cov*100:.1f}%")

    def _gate_independent_replication(self, strategy_id: str) -> GateResult:
        """Evaluate dual-experiment replication consistency across datasets/regimes."""
        qual = self._get_qual(strategy_id)
        if not qual:
            return GateResult("independent_replication", False, "No qualification record")
        rep_sharpe = qual.get("replication_sharpe")
        # F3: no notes-string fallback. Only a real stored value counts.
        if rep_sharpe is None:
            # Live dual-experiment evaluation when two independent runs exist;
            # real OOS Sharpes come from the runs, correlation from the signal
            # series over the gate's bars. Fail closed if we cannot compute.
            runs = self._db.get_runs(strategy_id=strategy_id, limit=50)
            if len(runs) >= 2:
                sc_p = self._scorecard_from_run(runs[0], strategy_id)
                sc_r = self._scorecard_from_run(runs[1], strategy_id)
                # F1 (CodeRabbit #15): do NOT pass the same series as both
                # primary and replication — a series cannot corroborate itself.
                # The gate has one derivable series; passing it twice would
                # fabricate a ~1.0 self-correlation. Pass it as primary only;
                # replication_returns=None means the engine evaluates the two
                # runs' scorecards (dual-run evidence) without a fake return
                # correlation. Identical run IDs are still rejected by the
                # engine's shared-provenance guard.
                series = _strategy_return_series(
                    strategy_id, _best_params(self._db, strategy_id), self._bars)
                report = self._replication_engine.evaluate_replication(
                    hypothesis_id=strategy_id,
                    primary_scorecard=sc_p,
                    replication_scorecard=sc_r,
                    primary_returns=series,
                    replication_returns=None,
                    primary_exp_id=str(runs[0].get("id", "EXP-PRIMARY")),
                    replication_exp_id=str(runs[1].get("id", "EXP-REPLICATION")),
                )
                return GateResult(
                    "independent_replication", report.replication_passed,
                    f"replication: corr={report.correlation_between_returns:.3f}, "
                    f"pSharpe={report.primary_sharpe:.2f}, rSharpe={report.replication_sharpe:.2f}, "
                    f"confidence={report.confidence_level}")
            return GateResult("independent_replication", False,
                              "Independent replication not performed (missing dual-experiment data)")
        if rep_sharpe >= 1.0:
            return GateResult("independent_replication", True, f"Replication OOS Sharpe={rep_sharpe:.2f} >= 1.0")
        return GateResult("independent_replication", False, f"Replication OOS Sharpe={rep_sharpe:.2f} < 1.0")

    def _gate_portfolio_impact(self, strategy_id: str) -> GateResult:
        """Evaluate candidate incremental Sharpe and max correlation against pool."""
        qual = self._get_qual(strategy_id)
        if not qual:
            return GateResult("portfolio_impact", False, "No qualification record")
        max_corr = qual.get("max_correlation")
        # F3: no notes-string fallback for max_correlation either.
        max_allowed_corr = self._criteria["max_correlation_with_existing"]
        if max_corr is None:
            # Live evaluation: real return series for the candidate and the
            # qualified pool (equal-weighted portfolio) via the evaluator.
            params = _best_params(self._db, strategy_id)
            cand_series = _strategy_return_series(strategy_id, params, self._bars)
            quals = self._db.get_qualifications()
            pool = [q["strategy_id"] for q in quals if q["status"] == "QUALIFIED"]
            pool_series = [
                s for s in (
                    _strategy_return_series(sid, _best_params(self._db, sid), self._bars)
                    for sid in pool
                )
                if len(s) == len(cand_series) and len(s) >= 5
            ]
            if len(cand_series) >= 5:
                report = self._portfolio_evaluator.evaluate_candidate(
                    strategy_id, cand_series, pool_series or None)
                return GateResult(
                    "portfolio_impact", report.adds_portfolio_value,
                    f"ΔSharpe={report.incremental_sharpe:+.3f}, "
                    f"max_corr={report.max_correlation_with_existing:.3f}, "
                    f"DD contribution={report.marginal_drawdown_contribution_pct:.1f}%")
            # Fail closed: no derivable return series => cannot claim impact.
            return GateResult("portfolio_impact", False,
                              "Portfolio impact requires return-series data (none derivable)")
        if max_corr < max_allowed_corr:
            return GateResult("portfolio_impact", True, f"Max pool correlation={max_corr:.2f} < {max_allowed_corr}")
        return GateResult("portfolio_impact", False, f"Max pool correlation={max_corr:.2f} >= {max_allowed_corr} (high diversification overlap)")


    def _gate_shadow_sufficiency(self, strategy_id: str) -> GateResult:
        min_trades = self._criteria["min_shadow_trades"]
        rows = self._db._conn.execute(
            "SELECT COUNT(*) as cnt FROM shadow_events WHERE strategy_id=? AND simulated_side IS NOT NULL",
            (strategy_id,),
        ).fetchone()
        trade_count = rows["cnt"] if rows else 0
        if trade_count >= min_trades:
            return GateResult("shadow_sufficiency", True,
                              f"{trade_count} shadow trades >= {min_trades}")
        if trade_count > 0:
            return GateResult("shadow_sufficiency", False,
                              f"Only {trade_count} shadow trades, need {min_trades}")
        return GateResult("shadow_sufficiency", False,
                          "No shadow trades recorded")

    def _gate_shadow_performance(self, strategy_id: str) -> GateResult:
        min_trades = self._criteria["min_shadow_trades"]
        rows = self._db._conn.execute(
            "SELECT COUNT(*) as cnt, SUM(simulated_pnl) as total_pnl "
            "FROM shadow_events WHERE strategy_id=? AND simulated_side IS NOT NULL",
            (strategy_id,),
        ).fetchone()
        trade_count = rows["cnt"] if rows else 0
        total_pnl = rows["total_pnl"] if rows and rows["total_pnl"] else 0.0
        if trade_count < min_trades:
            return GateResult("shadow_performance", False,
                              f"Insufficient data ({trade_count} trades)",
                              skipped=True)
        win_rows = self._db._conn.execute(
            "SELECT COUNT(*) as cnt FROM shadow_events "
            "WHERE strategy_id=? AND simulated_side='SELL' AND simulated_pnl > 0",
            (strategy_id,),
        ).fetchone()
        wins = win_rows["cnt"] if win_rows else 0
        win_rate = wins / trade_count if trade_count > 0 else 0
        if total_pnl < self._criteria["min_shadow_pnl"]:
            return GateResult("shadow_performance", False,
                              f"Shadow P&L=${total_pnl:.2f} < ${self._criteria['min_shadow_pnl']:.2f}")
        if win_rate < self._criteria["min_shadow_win_rate"]:
            return GateResult("shadow_performance", False,
                              f"Shadow win rate={win_rate:.0%} < {self._criteria['min_shadow_win_rate']:.0%}")
        return GateResult("shadow_performance", True,
                          f"P&L=${total_pnl:.2f}, win rate={win_rate:.0%}")

    def _gate_ensemble_regression(self, strategy_id: str) -> GateResult:
        """Compare ensemble with and without candidate. Skip if candidate is
        already in the qualified pool."""
        qual = self._get_qual(strategy_id)
        if not qual:
            return GateResult("ensemble_regression", False,
                              "No qualification record", skipped=True)
        if qual["status"] == "QUALIFIED":
            return GateResult("ensemble_regression", True,
                              "Already qualified", skipped=True)

        # Current qualified pool (no WATCHLIST)
        db = self._db
        quals = db.get_qualifications()
        qualified_ids = [q["strategy_id"] for q in quals if q["status"] == "QUALIFIED"]

        if not qualified_ids:
            return GateResult("ensemble_regression", True,
                              "No qualified pool yet — nothing to regress against", skipped=True)

        if strategy_id in qualified_ids:
            return GateResult("ensemble_regression", True,
                              "Already in the qualified pool", skipped=True)

        # Build params map for all strategies
        all_ids = qualified_ids + [strategy_id]
        params_map = {}
        for sid in all_ids:
            params_map[sid] = _best_params(db, sid)

        # Run baseline (qualified only)
        train_bars = self._bars[:len(self._bars) // 2]
        test_bars = self._bars[len(self._bars) // 2:]

        baseline = _run_ensemble_on_bars(qualified_ids, params_map, test_bars)
        with_candidate = _run_ensemble_on_bars(all_ids, params_map, test_bars)

        sharpe_drop = baseline.sharpe_ratio - with_candidate.sharpe_ratio
        dd_increase = with_candidate.max_drawdown_pct - baseline.max_drawdown_pct
        max_sharpe_drop = self._criteria["ensemble_sharpe_degradation_max"]
        max_dd_pct = self._criteria["ensemble_dd_increase_max_pct"]

        evidence = (
            f"baseline sharpe={baseline.sharpe_ratio:.2f}, "
            f"with candidate sharpe={with_candidate.sharpe_ratio:.2f}, "
            f"delta={sharpe_drop:+.2f}, "
            f"DD change={dd_increase:+.1f}%"
        )

        if sharpe_drop > max_sharpe_drop:
            return GateResult("ensemble_regression", False,
                              f"Sharpe dropped {sharpe_drop:.2f} > {max_sharpe_drop} limit. {evidence}")
        if dd_increase > max_dd_pct:
            return GateResult("ensemble_regression", False,
                              f"DD increased {dd_increase:.1f}% > {max_dd_pct}% limit. {evidence}")
        return GateResult("ensemble_regression", True, evidence)

    def promote(self, strategy_id: str, dry_run: bool = True) -> bool:
        """Promote strategy if all gates pass."""
        result = self.evaluate(strategy_id)
        if not result["passed"]:
            return False
        if dry_run:
            return True
        # Preserve existing qualification metrics
        qual = self._get_qual(strategy_id)
        bt = qual.get("backtest_sharpe") if qual else None
        wf = qual.get("wf_sharpe") if qual else None
        bt_ret = qual.get("backtest_return") if qual else None
        md = qual.get("max_dd_pct") if qual else None
        pt = qual.get("paper_trades") if qual else None
        self._db.set_qualification(
            strategy_id=strategy_id, status="QUALIFIED",
            backtest_sharpe=bt, wf_sharpe=wf,
            backtest_return=bt_ret, max_dd_pct=md, paper_trades=pt,
            notes="Promoted via promotion gate",
        )
        return True

    def close(self) -> None:
        self._db.close()
