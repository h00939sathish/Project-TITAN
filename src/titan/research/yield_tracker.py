"""Research Health Scorecard & Research Value Added (RVA) Telemetry."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class ResearchHealthScorecard:
    """Expanded Research Health Scorecard measuring quality, throughput, and Value Added."""

    experiments_run: int = 0
    rejected: int = 0
    refined: int = 0     # WATCHLIST entry
    promoted: int = 0    # QUALIFIED entry
    sample_sizes: list[int] = field(default_factory=list)
    oos_sharpes: list[float] = field(default_factory=list)

    @property
    def research_yield_pct(self) -> float:
        if self.experiments_run == 0:
            return 0.0
        return round((self.promoted / self.experiments_run) * 100.0, 2)

    @property
    def research_value_added(self) -> int:
        """Calculate Research Value Added (RVA):
        Promote = +5
        Refine  = +3
        Reject  = +2 (Knowledge gained from disciplined rejection)
        """
        return (self.promoted * 5) + (self.refined * 3) + (self.rejected * 2)

    @property
    def median_sample_size(self) -> int:
        if not self.sample_sizes:
            return 0
        return int(statistics.median(self.sample_sizes))

    @property
    def median_oos_sharpe(self) -> float:
        if not self.oos_sharpes:
            return 0.0
        return round(float(statistics.median(self.oos_sharpes)), 2)

    def summary(self) -> str:
        lines = [
            "+-- RESEARCH HEALTH SCORECARD ---------------------------------------+",
            f"|  Experiments Run:   {self.experiments_run:4d}                                            |",
            f"|  Rejected:          {self.rejected:4d}  (Governance Gate Enforcement)             |",
            f"|  Refined:           {self.refined:4d}  (Advanced to WATCHLIST)                  |",
            f"|  Promoted:          {self.promoted:4d}  (Advanced to QUALIFIED)                  |",
            "|--------------------------------------------------------------------+",
            f"|  Research Yield:    {self.research_yield_pct:5.1f}%                                          |",
            f"|  Research Value:    +{self.research_value_added:3d} RVA (Knowledge Score)                   |",
            f"|  Median Sample:     {self.median_sample_size:6d} bars                                       |",
            f"|  Median OOS Sharpe: {self.median_oos_sharpe:5.2f}                                           |",
            "+--------------------------------------------------------------------+",
        ]
        return "\n".join(lines)
