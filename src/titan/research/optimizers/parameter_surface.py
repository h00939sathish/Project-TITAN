"""Parameter surface and neighborhood stability analysis."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SurfaceNode:
    """Single point on a multi-dimensional parameter surface."""
    params: dict[str, Any]
    is_sharpe: float
    oos_sharpe: float
    profit_factor: float
    max_drawdown_pct: float
    total_return_pct: float
    trades_count: int

    @property
    def param_key(self) -> str:
        return json.dumps(self.params, sort_keys=True)


@dataclass
class ParameterSurface:
    """Multi-dimensional parameter surface representation."""
    strategy_id: str
    timeframe: str
    instrument_id: str
    nodes: dict[str, SurfaceNode] = field(default_factory=dict)

    def add_node(self, node: SurfaceNode) -> None:
        self.nodes[node.param_key] = node

    def compute_plateau_coverage(self, sharpe_threshold: float = 1.5, pf_threshold: float = 1.3) -> float:
        """Percentage of total parameter grid satisfying Sharpe >= 1.5 and PF >= 1.3."""
        if not self.nodes:
            return 0.0
        qualifying = sum(
            1 for n in self.nodes.values()
            if n.oos_sharpe >= sharpe_threshold and n.profit_factor >= pf_threshold
        )
        return qualifying / len(self.nodes)

    def get_neighbors(self, target_params: dict[str, Any]) -> list[SurfaceNode]:
        """Find immediate Euclidean neighbors in parameter space."""
        neighbors = []
        for key, node in self.nodes.items():
            if node.params == target_params:
                continue
            # Check if exactly one numeric parameter differs by one step
            diff_count = 0
            is_neighbor = True
            for pk, pv in target_params.items():
                nv = node.params.get(pk)
                if isinstance(pv, (int, float)) and isinstance(nv, (int, float)):
                    if pv != nv:
                        diff_count += 1
                elif pv != nv:
                    is_neighbor = False
                    break
            if is_neighbor and diff_count == 1:
                neighbors.append(node)
        return neighbors

    def compute_neighborhood_stability(self, target_params: dict[str, Any]) -> float:
        """Calculate stability score = 1 - (std_dev / mean) across parameter neighbors."""
        neighbors = self.get_neighbors(target_params)
        if not neighbors:
            return 0.0
        sharpes = [n.oos_sharpe for n in neighbors]
        mean = sum(sharpes) / len(sharpes)
        if mean <= 0:
            return 0.0
        variance = sum((s - mean) ** 2 for s in sharpes) / len(sharpes)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean
        return max(0.0, 1.0 - cv)
