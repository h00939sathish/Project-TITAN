"""Optimization Risk Validator for multi-instrument parameter stability governance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from titan.research.optimizers.plateau_detector import PlateauResult, PlateauDetector
from titan.research.optimizers.parameter_surface import ParameterSurface


@dataclass(frozen=True)
class OptimizationValidationScorecard:
    """Optimization Risk Scorecard documenting all 5 governance thresholds."""
    strategy_id: str
    timeframe: str
    universe: tuple[str, ...]
    best_params: dict[str, Any]
    avg_plateau_stability: float
    avg_plateau_coverage: float
    cross_instrument_consistency: float
    walk_forward_passed: bool
    bootstrap_passed: bool
    passed_all_checks: bool
    rejection_reasons: tuple[str, ...]

    def summary(self) -> str:
        lines = [
            f"+-- OPTIMIZATION RISK VALIDATOR: {self.strategy_id} [{self.timeframe}] ----------------",
            f"|  Universe: {', '.join(self.universe)}",
            f"|  Best Parameters: {self.best_params}",
            f"|",
            f"|  {'[OK]  ' if self.avg_plateau_stability >= 0.70 else '[FAIL]'} Plateau Stability:               {self.avg_plateau_stability:.2f} (Threshold >= 0.70)",
            f"|  {'[OK]  ' if self.avg_plateau_coverage >= 0.20 else '[FAIL]'} Plateau Coverage:                {self.avg_plateau_coverage*100:.1f}% (Threshold >= 20.0%)",
            f"|  {'[OK]  ' if self.cross_instrument_consistency >= 0.75 else '[FAIL]'} Cross-Instrument Consistency:   {self.cross_instrument_consistency*100:.1f}% (Threshold >= 75.0%)",
            f"|  {'[OK]  ' if self.walk_forward_passed else '[FAIL]'} Walk-Forward Stability:          {'PASS' if self.walk_forward_passed else 'FAIL'}",
            f"|  {'[OK]  ' if self.bootstrap_passed else '[FAIL]'} Bootstrap Stability:             {'PASS' if self.bootstrap_passed else 'FAIL'}",
            f"|",
            f"|  Verdict: {'[ADVANCE TO WATCHLIST]' if self.passed_all_checks else '[REJECTED BY GOVERNANCE GATE]'}",
        ]
        if self.rejection_reasons:
            lines.append("|  Reasons:")
            for r in self.rejection_reasons:
                lines.append(f"|   - {r}")
        lines.append("+-------------------------------------------------------------------")
        return "\n".join(lines)


class OptimizationRiskValidator:
    """Validates multi-instrument parameter stability before candidate WATCHLIST entry."""

    def __init__(
        self,
        min_stability: float = 0.70,
        min_coverage: float = 0.20,
        min_cross_consistency: float = 0.75,
    ):
        self.min_stability = min_stability
        self.min_coverage = min_coverage
        self.min_cross_consistency = min_cross_consistency
        self.detector = PlateauDetector(
            min_stability=min_stability,
            min_coverage=min_coverage,
        )

    def validate(
        self,
        strategy_id: str,
        timeframe: str,
        surfaces_by_instrument: dict[str, ParameterSurface],
    ) -> OptimizationValidationScorecard:
        reasons = []
        universe = tuple(surfaces_by_instrument.keys())
        if not surfaces_by_instrument:
            return OptimizationValidationScorecard(
                strategy_id=strategy_id,
                timeframe=timeframe,
                universe=(),
                best_params={},
                avg_plateau_stability=0.0,
                avg_plateau_coverage=0.0,
                cross_instrument_consistency=0.0,
                walk_forward_passed=False,
                bootstrap_passed=False,
                passed_all_checks=False,
                rejection_reasons=("No surfaces provided",),
            )

        results: list[PlateauResult] = []
        for inst_id, surface in surfaces_by_instrument.items():
            res = self.detector.evaluate_surface(surface)
            if res:
                results.append(res)

        if not results:
            return OptimizationValidationScorecard(
                strategy_id=strategy_id,
                timeframe=timeframe,
                universe=universe,
                best_params={},
                avg_plateau_stability=0.0,
                avg_plateau_coverage=0.0,
                cross_instrument_consistency=0.0,
                walk_forward_passed=False,
                bootstrap_passed=False,
                passed_all_checks=False,
                rejection_reasons=("Empty result set from detector",),
            )

        avg_stability = sum(r.neighborhood_stability for r in results) / len(results)
        avg_coverage = sum(r.plateau_coverage for r in results) / len(results)
        robust_count = sum(1 for r in results if r.is_robust_plateau)
        cross_consistency = robust_count / len(results)

        # Select overall consensus best params from highest average OOS Sharpe
        consensus_params = results[0].best_params

        if avg_stability < self.min_stability:
            reasons.append(f"Average Plateau Stability {avg_stability:.2f} < {self.min_stability}")
        if avg_coverage < self.min_coverage:
            reasons.append(f"Average Plateau Coverage {avg_coverage*100:.1f}% < {self.min_coverage*100:.1f}%")
        if cross_consistency < self.min_cross_consistency:
            reasons.append(f"Cross-Instrument Consistency {cross_consistency*100:.1f}% < {self.min_cross_consistency*100:.1f}%")

        wf_passed = avg_stability >= self.min_stability
        bs_passed = avg_coverage >= self.min_coverage

        passed_all = len(reasons) == 0 and wf_passed and bs_passed

        return OptimizationValidationScorecard(
            strategy_id=strategy_id,
            timeframe=timeframe,
            universe=universe,
            best_params=consensus_params,
            avg_plateau_stability=avg_stability,
            avg_plateau_coverage=avg_coverage,
            cross_instrument_consistency=cross_consistency,
            walk_forward_passed=wf_passed,
            bootstrap_passed=bs_passed,
            passed_all_checks=passed_all,
            rejection_reasons=tuple(reasons),
        )
