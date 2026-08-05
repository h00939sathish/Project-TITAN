"""Plateau detector for distinguishing robust parameter regions from isolated overfit spikes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from titan.research.optimizers.parameter_surface import ParameterSurface, SurfaceNode


@dataclass(frozen=True)
class PlateauResult:
    """Detected plateau result containing robustness metrics."""
    strategy_id: str
    timeframe: str
    instrument_id: str
    best_params: dict[str, Any]
    oos_sharpe: float
    profit_factor: float
    max_drawdown_pct: float
    plateau_coverage: float
    neighborhood_stability: float
    is_robust_plateau: bool
    rejection_reasons: tuple[str, ...]


class PlateauDetector:
    """Detects parameter plateaus vs overfit spikes across surfaces."""

    def __init__(self, min_stability: float = 0.70, min_coverage: float = 0.20,
                 min_sharpe: float = 1.5, min_pf: float = 1.3, max_dd_pct: float = 10.0):
        self.min_stability = min_stability
        self.min_coverage = min_coverage
        self.min_sharpe = min_sharpe
        self.min_pf = min_pf
        self.max_dd_pct = max_dd_pct

    def evaluate_surface(self, surface: ParameterSurface) -> PlateauResult | None:
        if not surface.nodes:
            return None

        # Find peak OOS Sharpe node
        best_node = max(surface.nodes.values(), key=lambda n: n.oos_sharpe)
        coverage = surface.compute_plateau_coverage(self.min_sharpe, self.min_pf)
        stability = surface.compute_neighborhood_stability(best_node.params)

        reasons = []
        if best_node.oos_sharpe < self.min_sharpe:
            reasons.append(f"OOS Sharpe {best_node.oos_sharpe:.2f} < {self.min_sharpe}")
        if best_node.profit_factor < self.min_pf:
            reasons.append(f"Profit Factor {best_node.profit_factor:.2f} < {self.min_pf}")
        if best_node.max_drawdown_pct > self.max_dd_pct:
            reasons.append(f"Max DD {best_node.max_drawdown_pct:.1f}% > {self.max_dd_pct}%")
        if stability < self.min_stability:
            reasons.append(f"Neighborhood Stability {stability:.2f} < {self.min_stability} (isolated overfit spike)")
        if coverage < self.min_coverage:
            reasons.append(f"Plateau Coverage {coverage*100:.1f}% < {self.min_coverage*100:.1f}%")

        is_robust = len(reasons) == 0

        return PlateauResult(
            strategy_id=surface.strategy_id,
            timeframe=surface.timeframe,
            instrument_id=surface.instrument_id,
            best_params=best_node.params,
            oos_sharpe=best_node.oos_sharpe,
            profit_factor=best_node.profit_factor,
            max_drawdown_pct=best_node.max_drawdown_pct,
            plateau_coverage=coverage,
            neighborhood_stability=stability,
            is_robust_plateau=is_robust,
            rejection_reasons=tuple(reasons),
        )
