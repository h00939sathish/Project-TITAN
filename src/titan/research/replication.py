"""Independent Replication Framework — prevents false discoveries through out-of-sample replication."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from titan.research.validators.parameter_stability import OptimizationValidationScorecard


@dataclass(frozen=True)
class ReplicationReport:
    """Independent replication report verifying hypothesis consistency across distinct regimes/datasets."""

    hypothesis_id: str
    primary_experiment_id: str
    replication_experiment_id: str
    primary_sharpe: float
    replication_sharpe: float
    correlation_between_returns: float
    replication_passed: bool
    confidence_level: str  # LOW, MEDIUM, HIGH, INSTITUTIONAL

    def summary(self) -> str:
        lines = [
            f"+-- INDEPENDENT REPLICATION REPORT: {self.hypothesis_id} --------------------+",
            f"|  Primary Exp: {self.primary_experiment_id:12s} (Sharpe: {self.primary_sharpe:5.2f})                           |",
            f"|  Replication Exp: {self.replication_experiment_id:8s} (Sharpe: {self.replication_sharpe:5.2f})                           |",
            f"|  Return Correlation: {self.correlation_between_returns:5.2f}                                         |",
            f"|  Replication Status: {'[PASSED]' if self.replication_passed else '[FAILED]'}                                       |",
            f"|  Confidence Level:   {self.confidence_level:13s}                                  |",
            "+--------------------------------------------------------------------+",
        ]
        return "\n".join(lines)


class ReplicationEngine:
    """Independent replication engine requiring dual-experiment confirmation before WATCHLIST entry."""

    def evaluate_replication(
        self,
        hypothesis_id: str,
        primary_scorecard: OptimizationValidationScorecard,
        replication_scorecard: OptimizationValidationScorecard,
        primary_returns: list[float] | None = None,
        replication_returns: list[float] | None = None,
        primary_exp_id: str = "EXP-PRIMARY",
        replication_exp_id: str = "EXP-REPLICATION",
    ) -> ReplicationReport:
        p_sharpe = float(primary_scorecard.best_params.get("oos_sharpe", 0.0))
        r_sharpe = float(replication_scorecard.best_params.get("oos_sharpe", 0.0))

        # Compute return correlation if return series are provided
        correlation = 0.0
        if primary_returns and replication_returns and len(primary_returns) > 5 and len(primary_returns) == len(replication_returns):
            import statistics
            mean_p = statistics.mean(primary_returns)
            mean_r = statistics.mean(replication_returns)
            cov = sum((p - mean_p) * (r - mean_r) for p, r in zip(primary_returns, replication_returns))
            var_p = sum((p - mean_p) ** 2 for p in primary_returns)
            var_r = sum((r - mean_r) ** 2 for r in replication_returns)
            denom = (var_p * var_r) ** 0.5
            correlation = round(cov / denom, 4) if denom > 0 else 0.0

        # Fail closed: must pass stability checks AND achieve OOS Sharpe >= 1.0 on both primary and replication
        passed = (
            primary_scorecard.passed_all_checks
            and replication_scorecard.passed_all_checks
            and p_sharpe >= 1.0
            and r_sharpe >= 1.0
        )

        if passed and min(p_sharpe, r_sharpe) >= 1.5:
            confidence = "INSTITUTIONAL"
        elif passed:
            confidence = "HIGH"
        elif primary_scorecard.passed_all_checks or replication_scorecard.passed_all_checks:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return ReplicationReport(
            hypothesis_id=hypothesis_id,
            primary_experiment_id=primary_exp_id,
            replication_experiment_id=replication_exp_id,
            primary_sharpe=round(p_sharpe, 4),
            replication_sharpe=round(r_sharpe, 4),
            correlation_between_returns=correlation,
            replication_passed=passed,
            confidence_level=confidence,
        )

