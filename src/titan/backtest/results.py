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
    volatility_annual_pct: float = 0.0
    hit_rate_pct: float = 0.0
    tail_loss_pct: float = 0.0
    avg_exposure_pct: float = 0.0
    capacity_proxy: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    cost_model_digest: str = ""
    evidence_artifact: dict | None = None

    @staticmethod
    def compute(equity_curve: list[float], trades: list[dict],
                exposure_curve: list[float] | None = None) -> "BacktestResult":
        return _compute_backtest(equity_curve, trades, exposure_curve)



def _compute_backtest(equity_curve: list[float], trades: list[dict],
                      exposure_curve: list[float] | None = None) -> BacktestResult:
    if not equity_curve or len(equity_curve) < 2:
        return BacktestResult()

    start_equity = equity_curve[0]
    end_equity = equity_curve[-1]
    total_return = (end_equity - start_equity) / start_equity * 100

    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        max_dd = max(max_dd, dd)

    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            daily_returns.append((equity_curve[i] - prev) / prev)

    sharpe = _compute_sharpe(daily_returns)
    vol = _compute_volatility(daily_returns)
    tail_loss = _compute_tail_loss(daily_returns)

    gross_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    total_commission = sum(t.get("commission", 0) for t in trades)
    hit_rate = len(wins) / max(len(trades), 1) * 100
    profit_factor = 100.0 if gross_loss < 0.01 else min(gross_profit / gross_loss, 100.0)

    avg_exposure = 0.0
    if exposure_curve and len(exposure_curve) > 0:
        avg_exposure = sum(exposure_curve) / len(exposure_curve)

    avg_equity = sum(equity_curve) / len(equity_curve) if equity_curve else 1.0
    avg_trade_value = (
        sum(abs(t.get("pnl", 0)) for t in trades) / max(len(trades), 1)
        if trades else 0.0
    )
    capacity = avg_trade_value / max(avg_equity, 1.0) * 100 if avg_equity > 0 else 0.0

    calmar = (total_return / 100) / (max_dd / 100) if max_dd > 0 else 0.0

    return BacktestResult(
        total_return_pct=round(total_return, 4),
        max_drawdown_pct=round(max_dd, 4),
        sharpe_ratio=round(sharpe, 4),
        total_trades=len(trades),
        win_rate=round(hit_rate, 2),
        total_commission=round(total_commission, 2),
        volatility_annual_pct=round(vol, 4),
        hit_rate_pct=round(hit_rate, 2),
        tail_loss_pct=round(tail_loss, 4),
        avg_exposure_pct=round(avg_exposure, 2),
        capacity_proxy=round(capacity, 4),
        calmar_ratio=round(calmar, 4),
        profit_factor=round(profit_factor, 4),
    )


def _compute_sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    avg = sum(daily_returns) / len(daily_returns)
    variance = sum((r - avg) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std = sqrt(variance) if variance > 0 else 1e-10
    return (avg / std) * sqrt(252) if std > 0 else 0.0


def _compute_volatility(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    avg = sum(daily_returns) / len(daily_returns)
    var = sum((r - avg) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    return sqrt(var) * sqrt(252) * 100 if var > 0 else 0.0


def _compute_tail_loss(daily_returns: list[float]) -> float:
    if not daily_returns:
        return 0.0
    sorted_returns = sorted(daily_returns)
    tail_idx = max(0, int(len(sorted_returns) * 0.05) - 1)
    return sorted_returns[tail_idx] * 100 if sorted_returns else 0.0
