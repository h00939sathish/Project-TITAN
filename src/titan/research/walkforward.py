"""Continuous Rolling / Expanding Walk-Forward Optimization (WFO) Engine."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Callable, Any

from titan.backtest.results import BacktestResult
from titan.research.harness import StrategyRunner, INITIAL_CAPITAL


@dataclass
class WalkForwardWindow:
    """Represents a single in-sample / out-of-sample window split."""

    window_id: int
    train_bars: list[dict]
    test_bars: list[dict]
    train_start: str = ""
    train_end: str = ""
    test_start: str = ""
    test_end: str = ""


@dataclass
class WalkForwardConfig:
    """Configuration for Walk-Forward Optimization."""

    train_size: int  # Number of bars in in-sample training window
    test_size: int  # Number of bars in out-of-sample test window
    step_size: int | None = None  # Step size for sliding (defaults to test_size)
    window_type: str = "rolling"  # "rolling" or "expanding"
    param_grid: dict[str, list[Any]] = field(default_factory=dict)
    target_metric: str = "sharpe"  # "sharpe", "return_mdd", "cagr", "total_return"
    min_wfe_threshold: float = 0.50  # WFE = OOS Sharpe / IS Sharpe
    min_trades: int = 5


@dataclass
class WalkForwardStepResult:
    """Out-of-sample and in-sample optimization result for one window."""

    window_id: int
    best_params: dict[str, Any]
    is_result: BacktestResult
    oos_result: BacktestResult
    is_metric_score: float
    oos_metric_score: float


@dataclass
class WalkForwardResult:
    """Overall Walk-Forward Optimization result across all windows."""

    step_results: list[WalkForwardStepResult]
    is_sharpe: float
    oos_sharpe: float
    wfe: float
    stitched_oos_equity: list[float]
    total_oos_trades: int
    passed_gate: bool
    summary: dict[str, Any] = field(default_factory=dict)


def generate_windows(bars: list[dict], config: WalkForwardConfig) -> list[WalkForwardWindow]:
    """Generates rolling or expanding in-sample and out-of-sample window splits."""
    if len(bars) < config.train_size + config.test_size:
        raise ValueError(
            f"Insufficient bars ({len(bars)}) for train_size ({config.train_size}) + test_size ({config.test_size})"
        )

    step = config.step_size or config.test_size
    windows: list[WalkForwardWindow] = []
    window_id = 0

    idx = 0
    while idx + config.train_size + config.test_size <= len(bars):
        if config.window_type == "expanding":
            train_start_idx = 0
        else:
            train_start_idx = idx

        train_end_idx = idx + config.train_size
        test_start_idx = train_end_idx
        test_end_idx = test_start_idx + config.test_size

        train_bars = bars[train_start_idx:train_end_idx]
        test_bars = bars[test_start_idx:test_end_idx]

        train_start = train_bars[0].get("timestamp", train_bars[0].get("date", ""))
        train_end = train_bars[-1].get("timestamp", train_bars[-1].get("date", ""))
        test_start = test_bars[0].get("timestamp", test_bars[0].get("date", ""))
        test_end = test_bars[-1].get("timestamp", test_bars[-1].get("date", ""))

        windows.append(
            WalkForwardWindow(
                window_id=window_id,
                train_bars=train_bars,
                test_bars=test_bars,
                train_start=str(train_start),
                train_end=str(train_end),
                test_start=str(test_start),
                test_end=str(test_end),
            )
        )

        window_id += 1
        idx += step

    return windows


def _evaluate_metric(result: BacktestResult, metric_name: str) -> float:
    if metric_name == "sharpe":
        return result.sharpe_ratio
    elif metric_name == "cagr":
        return result.cagr
    elif metric_name == "return_mdd":
        mdd = abs(result.max_drawdown)
        return result.total_return_pct / (mdd + 1e-6)
    elif metric_name == "total_return":
        return result.total_return_pct
    else:
        return result.sharpe_ratio


class WalkForwardOptimizer:
    """Executes rolling Walk-Forward Optimization across strategy parameter combinations."""

    def __init__(self, buy_qty: int = 10, slippage_bps: float = 0.5, commission_bps: float = 1.0):
        self.buy_qty = buy_qty
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps

    def optimize_window(
        self,
        train_bars: list[dict],
        strategy_factory: Callable[[dict], Any],
        param_grid: dict[str, list[Any]],
        target_metric: str,
    ) -> tuple[dict[str, Any], BacktestResult, float]:
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combinations = [dict(zip(keys, v)) for v in itertools.product(*value_lists)] if keys else [{}]

        best_params = combinations[0] if combinations else {}
        best_score = -float("inf")
        best_result = None

        n_trials = len(combinations)
        n_bars = len(train_bars)
        # Multiple testing penalty: delta_S = sqrt(2 * ln(M) / N)
        mt_penalty = math.sqrt(2.0 * math.log(max(1, n_trials)) / max(1, n_bars)) if n_trials > 1 and n_bars > 0 else 0.0

        for params in combinations:
            signal_fn = strategy_factory(params)
            runner = StrategyRunner(
                signal_fn,
                buy_qty=self.buy_qty,
                slippage_bps=self.slippage_bps,
                commission_bps=self.commission_bps,
            )
            eq, trades = runner.run(train_bars)
            result = BacktestResult(eq, trades)
            raw_score = _evaluate_metric(result, target_metric)
            score = raw_score - mt_penalty

            if score > best_score or best_result is None:
                best_score = score
                best_params = params
                best_result = result

        return best_params, best_result, best_score


    def run(
        self,
        bars: list[dict],
        strategy_factory: Callable[[dict], Any],
        config: WalkForwardConfig,
    ) -> WalkForwardResult:
        windows = generate_windows(bars, config)
        step_results: list[WalkForwardStepResult] = []

        stitched_equity = [INITIAL_CAPITAL]
        current_capital = INITIAL_CAPITAL
        total_oos_trades = 0

        is_sharpes: list[float] = []
        oos_sharpes: list[float] = []

        for w in windows:
            best_params, is_result, is_score = self.optimize_window(
                w.train_bars, strategy_factory, config.param_grid, config.target_metric
            )

            # Evaluate best parameters out-of-sample
            signal_fn = strategy_factory(best_params)
            runner = StrategyRunner(
                signal_fn,
                buy_qty=self.buy_qty,
                slippage_bps=self.slippage_bps,
                commission_bps=self.commission_bps,
            )
            oos_eq, oos_trades = runner.run(w.test_bars)
            oos_result = BacktestResult(oos_eq, oos_trades)
            oos_score = _evaluate_metric(oos_result, config.target_metric)

            step_results.append(
                WalkForwardStepResult(
                    window_id=w.window_id,
                    best_params=best_params,
                    is_result=is_result,
                    oos_result=oos_result,
                    is_metric_score=is_score,
                    oos_metric_score=oos_score,
                )
            )

            is_sharpes.append(is_result.sharpe_ratio)
            oos_sharpes.append(oos_result.sharpe_ratio)
            total_oos_trades += len(oos_trades)

            # Stitch out-of-sample equity curve
            if len(oos_eq) > 1:
                ret_factors = [oos_eq[i] / oos_eq[i - 1] for i in range(1, len(oos_eq))]
                for f in ret_factors:
                    current_capital *= f
                    stitched_equity.append(current_capital)

        avg_is_sharpe = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0.0
        avg_oos_sharpe = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0.0

        import statistics
        mean_oos_sharpe = statistics.mean(oos_sharpes) if oos_sharpes else 0.0
        median_oos_sharpe = statistics.median(oos_sharpes) if oos_sharpes else 0.0
        worst_oos_sharpe = min(oos_sharpes) if oos_sharpes else 0.0
        best_oos_sharpe = max(oos_sharpes) if oos_sharpes else 0.0
        std_oos_sharpe = statistics.stdev(oos_sharpes) if len(oos_sharpes) > 1 else 0.0


        wfe = avg_oos_sharpe / avg_is_sharpe if abs(avg_is_sharpe) > 1e-6 else 0.0
        passed_gate = (wfe >= config.min_wfe_threshold) and (total_oos_trades >= config.min_trades)

        summary = {
            "num_windows": len(windows),
            "window_type": config.window_type,
            "train_size": config.train_size,
            "test_size": config.test_size,
            "target_metric": config.target_metric,
            "avg_is_sharpe": round(avg_is_sharpe, 4),
            "avg_oos_sharpe": round(avg_oos_sharpe, 4),
            "mean_oos_sharpe": round(mean_oos_sharpe, 4),
            "median_oos_sharpe": round(median_oos_sharpe, 4),
            "worst_oos_sharpe": round(worst_oos_sharpe, 4),
            "best_oos_sharpe": round(best_oos_sharpe, 4),
            "std_oos_sharpe": round(std_oos_sharpe, 4),
            "wfe": round(wfe, 4),
            "total_oos_trades": total_oos_trades,
            "passed_gate": passed_gate,
        }

        return WalkForwardResult(
            step_results=step_results,
            is_sharpe=avg_is_sharpe,
            oos_sharpe=avg_oos_sharpe,
            wfe=wfe,
            stitched_oos_equity=stitched_equity,
            total_oos_trades=total_oos_trades,
            passed_gate=passed_gate,
            summary=summary,
        )

