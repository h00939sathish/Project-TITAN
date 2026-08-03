"""Import-time registration of all strategies into the global registry."""

import json

from titan.strategies.registry import ParameterDef, StrategyRegistration, get_registry
from titan.research.harness import (make_ma_signal_fn, make_momentum_signal_fn,
                                    make_mr_signal_fn, make_vol_regime_signal_fn,
                                    make_dual_ma_signal_fn, make_rsi_signal_fn,
                                    make_bollinger_signal_fn)
from titan.strategies.timeframes import Timeframe

_reg = get_registry()

_reg.register(StrategyRegistration(
    strategy_id="ma-crossover",
    version="1.0.0",
    description="Simple moving average crossover — BUY when fast MA crosses above slow MA, SELL on cross below.",
    parameter_schema=(
        ParameterDef("fast", "int", 5, "Fast moving average period"),
        ParameterDef("slow", "int", 20, "Slow moving average period"),
    ),
    factory=make_ma_signal_fn,
    qualified_variants=frozenset({
        (Timeframe.ONE_DAY, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
        (Timeframe.FIVE_MINUTES, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
    }),
))

_reg.register(StrategyRegistration(
    strategy_id="mean-reversion",
    version="1.0.0",
    description="Z-score mean reversion — BUY when price drops below entry_z std devs of rolling mean, "
                "SELL when it recovers above exit_z.",
    parameter_schema=(
        ParameterDef("window", "int", 20, "Rolling window for mean and std dev"),
        ParameterDef("entry_z", "float", -2.0, "Z-score threshold to enter (BUY signal)"),
        ParameterDef("exit_z", "float", -0.5, "Z-score threshold to exit (SELL signal)"),
    ),
    factory=make_mr_signal_fn,
    qualified_variants=frozenset({(Timeframe.ONE_DAY, json.dumps({"window": 20, "entry_z": -2.0, "exit_z": -0.5}, sort_keys=True))}),
))

_reg.register(StrategyRegistration(
    strategy_id="volatility-regime",
    version="1.0.0",
    description="Volatility-regime timing — BUY when rolling vol is below its longer-term median "
                "(low-vol regime), SELL when vol exceeds the median (high-vol regime).",
    parameter_schema=(
        ParameterDef("vol_window", "int", 20, "Rolling window for vol computation (bars)"),
        ParameterDef("median_window", "int", 60, "Rolling window for vol median (bars)"),
        ParameterDef("vol_multiple", "float", 1.0, "Vol threshold = median_vol * vol_multiple"),
    ),
    factory=make_vol_regime_signal_fn,
    qualified_variants=frozenset({(Timeframe.ONE_DAY, json.dumps({"vol_window": 20, "median_window": 60, "vol_multiple": 1.0}, sort_keys=True))}),
))

_reg.register(StrategyRegistration(
    strategy_id="time-series-momentum",
    version="1.0.0",
    description="Go long/short based on N-day return sign",
    parameter_schema=(
        ParameterDef("lookback", "int", 20, "Return calculation window"),
    ),
    factory=make_momentum_signal_fn,
    qualified_variants=frozenset({(Timeframe.ONE_DAY, json.dumps({"lookback": 20}, sort_keys=True))}),
))

_reg.register(StrategyRegistration(
    strategy_id="dual-ma",
    version="1.0.0",
    description="Dual moving average — long when fast MA > slow MA, short when fast MA < slow MA. Always in the market.",
    parameter_schema=(
        ParameterDef("fast", "int", 5, "Fast moving average period"),
        ParameterDef("slow", "int", 20, "Slow moving average period"),
    ),
    factory=make_dual_ma_signal_fn,
    qualified_variants=frozenset({
        (Timeframe.ONE_DAY, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
        (Timeframe.FIVE_MINUTES, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
    }),
))

_reg.register(StrategyRegistration(
    strategy_id="rsi",
    version="1.0.0",
    description="Relative Strength Index mean-reversion — BUY when RSI climbs back above the oversold threshold, SELL when it falls below overbought.",
    parameter_schema=(
        ParameterDef("window", "int", 14, "RSI lookback window"),
        ParameterDef("oversold", "float", 30.0, "RSI buy threshold"),
        ParameterDef("overbought", "float", 70.0, "RSI sell threshold"),
    ),
    factory=make_rsi_signal_fn,
    qualified_variants=frozenset({(Timeframe.ONE_DAY, json.dumps({"window": 14, "oversold": 30.0, "overbought": 70.0}, sort_keys=True))}),
))

from titan.research.harness import (make_ma_signal_fn, make_momentum_signal_fn,
                                    make_mr_signal_fn, make_vol_regime_signal_fn,
                                    make_dual_ma_signal_fn, make_rsi_signal_fn,
                                    make_bollinger_signal_fn, make_orb_signal_fn,
                                    make_vwap_signal_fn)

_reg.register(StrategyRegistration(
    strategy_id="bollinger",
    version="1.0.0",
    description="Bollinger Band mean-reversion — BUY when price closes at or below the lower band, SELL when price reverts to the middle band.",
    parameter_schema=(
        ParameterDef("window", "int", 20, "Rolling window for middle and band computation"),
        ParameterDef("std_dev_multiplier", "float", 2.0, "Standard deviation multiplier for the band width"),
    ),
    factory=make_bollinger_signal_fn,
    qualified_variants=frozenset({(Timeframe.ONE_DAY, json.dumps({"window": 20, "std_dev_multiplier": 2.0}, sort_keys=True))}),
))

_reg.register(StrategyRegistration(
    strategy_id="orb",
    version="1.0.0",
    description="Opening Range Breakout — BUY on upside breakout above opening range with ATR and volume expansion filters.",
    parameter_schema=(
        ParameterDef("atr_period", "int", 14, "ATR lookback for volatility context"),
        ParameterDef("min_volume_ratio", "float", 1.2, "Minimum volume expansion ratio"),
        ParameterDef("breakout_mult", "float", 1.0, "Breakout distance multiplier"),
    ),
    factory=make_orb_signal_fn,
    qualified_variants=frozenset(),
))

_reg.register(StrategyRegistration(
    strategy_id="vwap-reversion",
    version="1.0.0",
    description="VWAP Mean Reversion — BUY on oversold price extension below lower VWAP std dev band.",
    parameter_schema=(
        ParameterDef("window", "int", 30, "Rolling window for VWAP calculation"),
        ParameterDef("std_dev", "float", 2.0, "Standard deviation band multiplier"),
    ),
    factory=make_vwap_signal_fn,
    qualified_variants=frozenset(),
))
