"""Decoupled multi-instrument grid search optimizer with strict train/validation separation."""
from __future__ import annotations

import itertools
from typing import Any
from titan.research.harness import run_backtest_result, make_ma_signal_fn, make_dual_ma_signal_fn, make_rsi_signal_fn, make_bollinger_signal_fn, make_orb_signal_fn, make_vwap_signal_fn
from titan.research.optimizers.parameter_surface import ParameterSurface, SurfaceNode


STRATEGY_FACTORY_MAP = {
    "ma-crossover": make_ma_signal_fn,
    "dual-ma": make_dual_ma_signal_fn,
    "rsi": make_rsi_signal_fn,
    "bollinger": make_bollinger_signal_fn,
    "orb": make_orb_signal_fn,
    "vwap-reversion": make_vwap_signal_fn,
}


class GridSearchOptimizer:
    """Decoupled grid search optimizer.

    Strictly separates Training Window (Optimization) from Validation Window
    (Out-of-Sample Evaluation) across a shared multi-instrument universe.
    """

    def __init__(self, slippage_bps: float = 1.0, commission_bps: float = 1.0):
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps

    def optimize_strategy(
        self,
        strategy_id: str,
        timeframe: str,
        bars: list[dict],
        instrument_id: str,
        param_grid: dict[str, list[Any]],
        train_ratio: float = 0.60,
    ) -> ParameterSurface:
        """Run grid search over train window and evaluate nodes on validation window."""
        surface = ParameterSurface(
            strategy_id=strategy_id,
            timeframe=timeframe,
            instrument_id=instrument_id,
        )

        if len(bars) < 60:
            return surface

        split_idx = int(len(bars) * train_ratio)
        train_bars = bars[:split_idx]
        val_bars = bars[split_idx:]

        factory = STRATEGY_FACTORY_MAP.get(strategy_id, make_ma_signal_fn)

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for comb in itertools.product(*param_values):
            params = dict(zip(param_names, comb))

            # Train window backtest
            is_res = run_backtest_result(
                train_bars,
                params,
                signal_factory=factory,
                slippage_bps=self.slippage_bps,
                commission_bps=self.commission_bps,
            )
            # Validation window backtest (optimizer NEVER sees validation data!)
            oos_res = run_backtest_result(
                val_bars,
                params,
                signal_factory=factory,
                slippage_bps=self.slippage_bps,
                commission_bps=self.commission_bps,
            )

            node = SurfaceNode(
                params=params,
                is_sharpe=float(is_res.sharpe_ratio),
                oos_sharpe=float(oos_res.sharpe_ratio),
                profit_factor=float(oos_res.profit_factor),
                max_drawdown_pct=float(oos_res.max_drawdown_pct),
                total_return_pct=float(oos_res.total_return_pct),
                trades_count=int(oos_res.total_trades),
            )
            surface.add_node(node)

        return surface
