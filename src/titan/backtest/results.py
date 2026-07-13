"""Record and compute backtest results."""

from dataclasses import dataclass
from math import sqrt


@dataclass
class BacktestResult:
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    total_commission: float = 0.0

    @staticmethod
    def compute(equity_curve: list[float], trades: list[dict]) -> "BacktestResult":
        if not equity_curve or len(equity_curve) < 2:
            return BacktestResult()

        start_equity = equity_curve[0]
        end_equity = equity_curve[-1]
        total_return = (end_equity - start_equity) / start_equity * 100

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            max_dd = max(max_dd, dd)

        # Sharpe (simplified: uses daily returns from equity curve)
        daily_returns = []
        for i in range(1, len(equity_curve)):
            r = (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            daily_returns.append(r)

        if daily_returns and len(daily_returns) > 1:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - avg_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std = sqrt(variance) if variance > 0 else 1e-10
            sharpe = (avg_return / std) * sqrt(252) if std > 0 else 0.0
        else:
            sharpe = 0.0

        # Trade stats
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        total_commission = sum(t.get("commission", 0) for t in trades)

        return BacktestResult(
            total_return_pct=round(total_return, 4),
            max_drawdown_pct=round(max_dd, 4),
            sharpe_ratio=round(sharpe, 4),
            total_trades=len(trades),
            win_rate=round(len(wins) / max(len(trades), 1) * 100, 2),
            total_commission=round(total_commission, 2),
        )
