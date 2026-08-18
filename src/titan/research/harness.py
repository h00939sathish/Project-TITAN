"""Validation harness — runs a hypothesis through the full validation pipeline."""

import re
import statistics
from typing import Any, Callable

from titan.backtest.corporate_actions import common_adjustments
from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.fx_costs import FxCostModel
from titan.backtest.results import BacktestResult
from titan.data.ingest import read_csv
from titan.data.manifest import DataManifest
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from titan.research.gate import check_min_trades
from titan.research.hypothesis import Hypothesis
from titan.research.metrics import (
    block_bootstrap,
    compute_cagr,
    compute_exposure,
    compute_turnover,
    daily_return_bootstrap,
    exposure_adjusted_benchmark,
    regime_results,
)
from titan.strategies.bollinger import BollingerBands
from titan.strategies.dual_ma import DualMovingAverage
from titan.strategies.mean_reversion import MeanReversion
from titan.strategies.momentum import TimeSeriesMomentum
from titan.strategies.moving_average import MovingAverageCrossover
from titan.strategies.rsi import RelativeStrengthIndex
from titan.strategies.sizing import Sizer
from titan.strategies.volatility_regime import VolatilityRegime

INITIAL_CAPITAL = 100_000.0


def load_bars(csv_path: str) -> list[dict]:
    """Load, normalize, quarantine, and adjust bars."""
    raw = read_csv(csv_path)
    if not raw:
        raise ValueError(f"No data loaded from {csv_path}")
    report, good = validate_and_quarantine(raw, normalize_row)
    ca_db = common_adjustments()
    return ca_db.adjust_bars(good)


def split_bars(bars: list[dict], split_date: str) -> tuple[list[dict], list[dict]]:
    train, test = [], []
    for bar in bars:
        ts = bar.get("timestamp", bar.get("date", ""))
        if ts < split_date:
            train.append(bar)
        else:
            test.append(bar)
    return train, test


class StrategyRunner:
    """Runs a buy/sell-signal strategy over bars with next-event execution and cost model support.

    Takes a function `signal_fn(bar) -> str | None` that returns
    "BUY", "SELL", or None for each bar.
    """

    def __init__(
        self,
        signal_fn,
        *,
        notional_allocation_pct: float = 10.0,
        step_size: int = 1,
        min_quantity: int = 1,
        slippage_bps: float = 0.5,
        commission_bps: float = 1.0,
        cost_model: FxCostModel | None = None,
    ):
        self.signal_fn = signal_fn
        self.notional_allocation_pct = notional_allocation_pct
        self.step_size = step_size
        self.min_quantity = min_quantity
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
        self.cost_model = cost_model

    def run(self, bars: list[dict]) -> tuple[list[float], list[dict]]:
        model = BarConservativeFillModel(
            slippage_bps=self.slippage_bps, commission_bps=self.commission_bps
        )
        equity_curve = [INITIAL_CAPITAL]
        trades: list[dict] = []
        cash = INITIAL_CAPITAL
        position = 0.0
        position_cost = 0.0
        in_position = False
        pending_signal = None

        for bar in bars:
            # 1. Execute pending signal from previous bar against current bar
            if pending_signal == "BUY" and not in_position:
                price = bar.get("ask", bar.get("open", bar.get("close", 0.0)))
                sz_res = Sizer.size(
                    equity=cash + (position * float(price) if position else 0.0),
                    notional_allocation_pct=self.notional_allocation_pct,
                    price=float(price),
                    conversion_rate=1.0,  # Assumed base currency for harness
                    conversion_timestamp=None,
                    step_size=self.step_size,
                    minimum_quantity=self.min_quantity,
                )
                if sz_res.is_tradable:
                    fill = model.fill(bar, "buy", sz_res.quantity, cost_model=self.cost_model)
                    cost = float(fill.fill_cost) + float(fill.commission)
                    if cost <= cash:
                        cash -= cost
                        position = float(fill.fill_quantity)
                        position_cost = float(fill.fill_cost)
                        in_position = True
                        trades.append({
                            "pnl": 0.0,
                            "commission": float(fill.commission),
                            "spread_cost": float(fill.spread_cost),
                            "slippage_cost": float(fill.slippage_cost),
                            "side": "buy",
                            "price": float(fill.fill_price),
                            "qty": int(fill.fill_quantity),
                            "timestamp": bar.get("timestamp", ""),
                            "fidelity": fill.fidelity,
                        })
                pending_signal = None
            elif pending_signal == "SELL" and in_position:
                fill = model.fill(bar, "sell", int(position), cost_model=self.cost_model)
                proceeds = float(fill.fill_cost) - float(fill.commission)
                pnl = proceeds - position_cost
                cash += proceeds
                trades[-1]["pnl"] = pnl
                trades[-1]["exit_timestamp"] = bar.get("timestamp", "")
                trades.append({
                    "pnl": pnl,
                    "commission": float(fill.commission),
                    "spread_cost": float(fill.spread_cost),
                    "slippage_cost": float(fill.slippage_cost),
                    "side": "sell",
                    "price": float(fill.fill_price),
                    "qty": int(fill.fill_quantity),
                    "timestamp": bar.get("timestamp", ""),
                    "fidelity": fill.fidelity,
                })
                position = 0.0
                position_cost = 0.0
                in_position = False
                pending_signal = None

            # 2. Evaluate signal on current bar for execution on next bar
            sig = self.signal_fn(bar)
            if sig in ("BUY", "SELL"):
                pending_signal = sig

            # 3. Mark to market
            close_price = float(bar.get("close", bar.get("open", 0.0)))
            mtm = cash + (position * close_price) if in_position else cash
            equity_curve.append(mtm)

        if in_position and bars:
            last_bar = bars[-1]
            fill = model.fill(last_bar, "sell", int(position), cost_model=self.cost_model)
            net_proceeds = float(fill.fill_cost) - float(fill.commission)
            equity_curve[-1] = cash + net_proceeds

        return equity_curve, trades




def make_strategy_signal_fn(
    strategy_cls: type,
    field_specs: dict[str, tuple[str, Any]],
) -> Callable[[dict], Callable[[dict], str | None]]:
    """Generic signal-fn factory: instantiate strategy_cls from params via field_specs
    (param key -> (constructor kwarg, default)) and return a bar-updating signal_fn
    with the strategy attached as .strat."""
    def factory(params: dict):
        strat = strategy_cls(**{
            ctor_kwarg: params.get(param, default)
            for param, (ctor_kwarg, default) in field_specs.items()
        })

        def signal_fn(bar):
            return strat.update(bar["close"])
        signal_fn.strat = strat
        return signal_fn
    return factory


make_ma_signal_fn = make_strategy_signal_fn(
    MovingAverageCrossover,
    {"fast": ("fast_period", 5), "slow": ("slow_period", 20)},
)
make_mr_signal_fn = make_strategy_signal_fn(
    MeanReversion,
    {"window": ("window", 20), "entry_z": ("entry_z", -2.0), "exit_z": ("exit_z", -0.5)},
)
make_vol_regime_signal_fn = make_strategy_signal_fn(
    VolatilityRegime,
    {
        "vol_window": ("vol_window", 20),
        "median_window": ("median_window", 60),
        "vol_multiple": ("vol_multiple", 1.0),
    },
)
make_momentum_signal_fn = make_strategy_signal_fn(
    TimeSeriesMomentum,
    {"lookback": ("lookback", 20)},
)
make_dual_ma_signal_fn = make_strategy_signal_fn(
    DualMovingAverage,
    {"fast": ("fast_period", 5), "slow": ("slow_period", 20)},
)
make_rsi_signal_fn = make_strategy_signal_fn(
    RelativeStrengthIndex,
    {"window": ("window", 14), "oversold": ("oversold", 30.0), "overbought": ("overbought", 70.0)},
)
make_bollinger_signal_fn = make_strategy_signal_fn(
    BollingerBands,
    {"window": ("window", 20), "std_dev_multiplier": ("std_dev_multiplier", 2.5)},
)


def make_orb_signal_fn(params: dict):
    """Factory: returns a signal_fn for Opening Range Breakout (ORB)."""
    from titan.strategies.orb import make_orb_signal_fn as _make_orb
    evaluator = _make_orb(params)
    history: list[dict] = []

    def signal_fn(bar):
        history.append(bar)
        return evaluator(history)
    return signal_fn


def make_vwap_signal_fn(params: dict):
    """Factory: returns a signal_fn for VWAP Mean Reversion."""
    from titan.strategies.vwap_reversion import make_vwap_signal_fn as _make_vwap
    evaluator = _make_vwap(params)
    history: list[dict] = []

    def signal_fn(bar):
        history.append(bar)
        return evaluator(history)
    return signal_fn


def make_traderdev_ema9vwap_signal_fn(params: dict):
    """Factory: returns a signal_fn for the TraderDev EMA9×VWAP trailing candidate."""
    from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP
    strat = TraderDevEMA9VWAP(
        ema_period=int(params.get("ema_period", 9)),
        vwap_period=int(params.get("vwap_period", 120)),
        atr_period=int(params.get("atr_period", 14)),
        trail_mult=float(params.get("trail_mult", 3.0)),
    )

    def signal_fn(bar):
        return strat(bar)
    signal_fn.strat = strat
    return signal_fn



def run_backtest_result(
    bars: list[dict],
    strategy_params: dict,
    signal_factory=make_ma_signal_fn,
    *,
    notional_allocation_pct: float = 10.0,
    step_size: int = 1,
    min_quantity: int = 1,
    slippage_bps: float = 0.5,
    commission_bps: float = 1.0,
    cost_model: FxCostModel | None = None,
) -> BacktestResult:
    """Run a parameterized strategy + compute BacktestResult."""
    runner = StrategyRunner(
        signal_factory(strategy_params),
        notional_allocation_pct=notional_allocation_pct,
        step_size=step_size,
        min_quantity=min_quantity,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
        cost_model=cost_model,
    )
    eq, trades = runner.run(bars)
    exposure_curve = _exposure_curve(eq, trades, bars)
    res = BacktestResult.compute(eq, trades, exposure_curve)
    if cost_model is not None:
        res.cost_model_digest = cost_model.digest()
        total_spread = sum(t.get("spread_cost", 0.0) for t in trades)
        total_slippage = sum(t.get("slippage_cost", 0.0) for t in trades)
        total_commission = sum(t.get("commission", 0.0) for t in trades)
        gross_pnl = sum(t.get("pnl", 0.0) for t in trades) + total_commission
        net_pnl = sum(t.get("pnl", 0.0) for t in trades)
        fidelity = trades[0]["fidelity"] if trades else ("quote" if cost_model.fill_mode == "QUOTE_NEXT_EVENT" else "lower")
        res.evidence_artifact = {
            "cost_model_digest": cost_model.digest(),
            "fill_model": cost_model.fill_mode,
            "fidelity": fidelity,
            "total_trades": len(trades),
            "total_commission": round(total_commission, 4),
            "total_spread_cost": round(total_spread, 4),
            "total_slippage_cost": round(total_slippage, 4),
            "gross_pnl": round(gross_pnl, 4),
            "net_pnl": round(net_pnl, 4),
            "sharpe_ratio": res.sharpe_ratio,
            "max_drawdown_pct": res.max_drawdown_pct,
        }
    return res



def _exposure_curve(eq: list[float], trades: list[dict],
                    bars: list[dict]) -> list[float]:
    """Build exposure curve (position value / total equity per bar)."""
    in_pos = False
    curve = []
    buy_ts = {t.get("timestamp", "") for t in trades if t.get("side") == "buy"}
    sell_ts = {t.get("timestamp", "") for t in trades if t.get("side") == "sell"}
    for i, bar in enumerate(bars):
        ts = bar.get("timestamp", "")
        if ts in buy_ts:
            in_pos = True
        elif ts in sell_ts:
            in_pos = False
        eq_val = eq[i + 1] if i + 1 < len(eq) else eq[-1]
        pos_val = abs(eq_val - INITIAL_CAPITAL) if in_pos else 0.0
        curve.append(pos_val / max(eq_val, 1.0) if eq_val > 0 else 0.0)
    return curve


def buy_and_hold_result(bars: list[dict]) -> BacktestResult:
    if not bars:
        return BacktestResult()
    shares = INITIAL_CAPITAL / bars[0]["close"]
    eq = [INITIAL_CAPITAL]
    for bar in bars:
        eq.append(shares * bar["close"])
    return BacktestResult.compute(eq, [])


def cash_result(bars: list[dict]) -> BacktestResult:
    eq = [INITIAL_CAPITAL] * (len(bars) + 1)
    return BacktestResult.compute(eq, [])


def run_parameter_sweep(
    bars: list[dict],
    param_grid: list[dict],
    signal_factory=make_ma_signal_fn,
    label_fn=str,
    *,
    notional_allocation_pct: float = 10.0,
    step_size: int = 1,
    min_quantity: int = 1,
    slippage_bps: float = 0.5,
    commission_bps: float = 1.0,
    cost_model: FxCostModel | None = None,
) -> dict:
    results = {}
    for params in param_grid:
        r = run_backtest_result(
            bars,
            params,
            signal_factory,
            notional_allocation_pct=notional_allocation_pct,
            step_size=step_size,
            min_quantity=min_quantity,
            slippage_bps=slippage_bps,
            commission_bps=commission_bps,
            cost_model=cost_model,
        )
        results[label_fn(params)] = r
    return results


def walk_forward(
    bars: list[dict],
    strategy_params: dict,
    signal_factory=make_ma_signal_fn,
    train_size: int = 252,
    step: int = 63,
    *,
    notional_allocation_pct: float = 10.0,
    step_size: int = 1,
    min_quantity: int = 1,
    slippage_bps: float = 0.5,
    commission_bps: float = 1.0,
    cost_model: FxCostModel | None = None,
) -> list[BacktestResult]:
    results = []
    for start in range(0, len(bars) - train_size - step + 1, step):
        window = bars[start:start + train_size + step]
        r = run_backtest_result(
            window,
            strategy_params,
            signal_factory,
            notional_allocation_pct=notional_allocation_pct,
            step_size=step_size,
            min_quantity=min_quantity,
            slippage_bps=slippage_bps,
            commission_bps=commission_bps,
            cost_model=cost_model,
        )
        results.append(r)
    return results



def evaluate_success_criteria(
    hypothesis: Hypothesis,
    candidate: BacktestResult | None,
    benchmark: BacktestResult | None,
    gate_result,
) -> bool:
    """Evaluate preregistered criteria independently of the trade-count gate."""
    criteria_met = 0
    for criterion in hypothesis.success_criteria:
        normalized = criterion.lower()
        if "sharpe" in normalized and ("> 0" in criterion or ">0" in criterion):
            threshold = 0.5
            if ">" in criterion:
                try:
                    threshold = float(criterion.split(">", 1)[1].strip().split()[0])
                except (ValueError, IndexError):
                    threshold = 0.5
            if candidate and candidate.sharpe_ratio > threshold:
                criteria_met += 1
        elif "drawdown" in normalized and benchmark:
            if candidate and candidate.max_drawdown_pct < benchmark.max_drawdown_pct:
                criteria_met += 1
        elif "win rate" in normalized:
            threshold = 40.0
            for value in (40, 35, 30):
                if f"> {value}" in criterion:
                    threshold = float(value)
                    break
            if candidate and candidate.win_rate > threshold:
                criteria_met += 1
        elif "trades" in normalized:
            numbers = re.findall(r"\d+", criterion)
            minimum = int(numbers[0]) if numbers else 30
            if candidate and candidate.total_trades >= minimum:
                criteria_met += 1

    failure_triggered = 0
    for criterion in hypothesis.failure_criteria:
        normalized = criterion.lower()
        if "sharpe < 0" in normalized and candidate and candidate.sharpe_ratio < 0:
            failure_triggered += 1
        elif "return < 0" in normalized and candidate and candidate.total_return_pct < 0:
            failure_triggered += 1

    return (
        criteria_met == len(hypothesis.success_criteria)
        and failure_triggered == 0
        and gate_result.passed
    )


class ValidationReport:
    """Container for a full validation run."""

    def __init__(self, hypothesis: Hypothesis):
        self.hypothesis = hypothesis
        self.bars_all: list[dict] = []
        self.train_bars: list[dict] = []
        self.test_bars: list[dict] = []
        self.manifest: DataManifest | None = None

        self.candidate_result: BacktestResult | None = None
        self.bh_result: BacktestResult | None = None
        self.cash_result: BacktestResult | None = None
        self.ma_control_result: BacktestResult | None = None

        self.trades: list[dict] = []
        self.equity_curve: list[float] = []

        self.regime_perf: dict = {}
        self.turnover: dict = {}
        self.exposure: dict = {}
        self.daily_ci: dict = {}
        self.cagr: dict[str, float] = {}
        self.exposure_adj_bh: dict = {}
        self.exposure_adj_control: dict = {}
        self.block_bootstrap: dict = {}
        self.parameter_sweep: dict = {}
        self.walk_forward_results: list[BacktestResult] = []
        self.gate_result = None
        self.success = False

    def to_dict(self) -> dict:
        b = self.candidate_result
        bh = self.bh_result
        cash_r = self.cash_result
        control = self.ma_control_result
        return {
            "hypothesis_id": self.hypothesis.id,
            "hypothesis_title": self.hypothesis.title,
            "strategy_params": dict(self.hypothesis.strategy_params),
            "bars_total": len(self.bars_all),
            "bars_train": len(self.train_bars),
            "bars_test": len(self.test_bars),
            "candidate": {
                "total_return_pct": b.total_return_pct if b else None,
                "sharpe_ratio": b.sharpe_ratio if b else None,
                "max_drawdown_pct": b.max_drawdown_pct if b else None,
                "win_rate": b.win_rate if b else None,
                "total_trades": b.total_trades if b else None,
                "volatility_annual_pct": b.volatility_annual_pct if b else None,
                "profit_factor": b.profit_factor if b else None,
                "calmar_ratio": b.calmar_ratio if b else None,
            },
            "confidence_intervals": {
                "annual_return_ci": self.daily_ci.get("annual_return_ci", (0, 0)),
                "sharpe_ci": self.daily_ci.get("sharpe_ci", (0, 0)),
            },
            "cagr_pct": self.cagr,
            "benchmarks": {
                "buy_and_hold": {
                    "total_return_pct": bh.total_return_pct if bh else None,
                    "max_drawdown_pct": bh.max_drawdown_pct if bh else None,
                    "sharpe_ratio": bh.sharpe_ratio if bh else None,
                },
                "cash": {
                    "total_return_pct": cash_r.total_return_pct if cash_r else None,
                    "max_drawdown_pct": cash_r.max_drawdown_pct if cash_r else None,
                },
                "ma_control_5_20": {
                    "total_return_pct": control.total_return_pct if control else None,
                    "sharpe_ratio": control.sharpe_ratio if control else None,
                    "max_drawdown_pct": control.max_drawdown_pct if control else None,
                    "total_trades": control.total_trades if control else None,
                },
                "exposure_adjusted": {
                    "bh": self.exposure_adj_bh,
                    "ma_control": self.exposure_adj_control,
                },
            },
            "turnover": self.turnover,
            "exposure": self.exposure,
            "block_bootstrap": self.block_bootstrap,
            "regime_results": self.regime_perf,
            "walk_forward": {
                "n_windows": len(self.walk_forward_results),
                "mean_sharpe": statistics.mean(
                    [r.sharpe_ratio for r in self.walk_forward_results]
                ) if self.walk_forward_results else None,
            },
            "gate": self.gate_result.to_dict() if self.gate_result else None,
            "success": self.success,
            "success_criteria_met": self.hypothesis.success_criteria if self.success else [],
            "failure_criteria_triggered": self.hypothesis.failure_criteria if not self.success else [],
        }


class ValidationHarness:
    """Orchestrates validation: loads data, runs candidate + benchmarks, gates."""

    def __init__(self, hypothesis: Hypothesis, data_path: str,
                 signal_factory=make_ma_signal_fn,
                 control_params: dict | None = None,
                 control_factory=make_ma_signal_fn,
                 control_label: str = "MA(5,20)"):
        self.hypothesis = hypothesis
        self.data_path = data_path
        self.signal_factory = signal_factory
        self.control_params = control_params or {"fast": 5, "slow": 20}
        self.control_factory = control_factory
        self.control_label = control_label

    def _build_param_grid(self, params: dict) -> list[dict]:
        """Default param grid: vary each known param +/- small amount."""
        grid = []
        for k, v in params.items():
            if isinstance(v, (int, float)) and k not in ("entry_z", "exit_z"):
                for delta in [-2, -1, 1, 2]:
                    if k == "slow" and delta < 0 and v + delta < 5:
                        continue
                    if k in ("window", "fast", "slow") and k != "fast" and v + delta > 1:
                        candidate = dict(params)
                        candidate[k] = int(v + delta)
                        if candidate not in grid:
                            grid.append(candidate)
            elif k in ("entry_z", "exit_z"):
                for delta in [-0.3, -0.1, 0.1, 0.3]:
                    candidate = dict(params)
                    candidate[k] = round(v + delta, 2)
                    if candidate not in grid:
                        grid.append(candidate)
        if not grid:
            grid = [dict(params)]
        return grid

    @staticmethod
    def _param_label(params: dict) -> str:
        """Human label for a parameter set."""
        parts = []
        for k, v in params.items():
            parts.append(f"{k}={v}")
        return ",".join(parts)

    def run(self) -> ValidationReport:
        report = ValidationReport(self.hypothesis)

        bars_all = load_bars(self.data_path)
        report.bars_all = bars_all
        test_start = self.hypothesis.test_period
        train_bars, test_bars = split_bars(bars_all, test_start)
        report.train_bars = train_bars
        report.test_bars = test_bars

        strategy_params = dict(self.hypothesis.strategy_params)

        sig_fn = self.signal_factory(strategy_params)
        runner = StrategyRunner(sig_fn)
        eq, trades = runner.run(test_bars)
        report.trades = trades
        report.equity_curve = eq

        exposure_curve = _exposure_curve(eq, trades, test_bars)
        report.candidate_result = BacktestResult.compute(eq, trades, exposure_curve)
        report.bh_result = buy_and_hold_result(test_bars)
        report.cash_result = cash_result(test_bars)
        report.ma_control_result = run_backtest_result(
            test_bars, self.control_params, self.control_factory)

        # Extended metrics
        report.turnover = compute_turnover(trades, INITIAL_CAPITAL)
        report.exposure = compute_exposure(test_bars, trades)
        report.daily_ci = daily_return_bootstrap(eq)
        report.exposure_adj_bh = exposure_adjusted_benchmark(
            report.bh_result, report.exposure.get("time_in_market_pct", 100), "BH")
        report.exposure_adj_control = exposure_adjusted_benchmark(
            report.ma_control_result, report.exposure.get("time_in_market_pct", 100),
            self.control_label)
        bh_equity = [INITIAL_CAPITAL]
        if test_bars:
            initial_close = test_bars[0]["close"]
            bh_equity.extend(
                INITIAL_CAPITAL * bar["close"] / initial_close for bar in test_bars
            )
        control_equity, _ = StrategyRunner(
            self.control_factory(self.control_params), notional_allocation_pct=10.0
        ).run(test_bars)
        report.cagr = {
            "candidate": compute_cagr(eq),
            "buy_and_hold": compute_cagr(bh_equity),
            "cash": compute_cagr([INITIAL_CAPITAL] * (len(test_bars) + 1)),
            "ma_control_5_20": compute_cagr(control_equity),
        }
        report.block_bootstrap = block_bootstrap(trades)
        report.regime_perf = regime_results(test_bars, trades, eq)

        # Walk-forward + parameter sweep
        report.walk_forward_results = walk_forward(
            bars_all, strategy_params, self.signal_factory)
        param_grid = self._build_param_grid(strategy_params)
        report.parameter_sweep = run_parameter_sweep(
            test_bars, param_grid, self.signal_factory, self._param_label)

        # Gate — respects sample-adequacy policy
        override_doc = ""
        if self.hypothesis.sample_adequacy_policy == "Path B":
            override_doc = self.hypothesis.path_b_evidence_standard
        report.gate_result = check_min_trades(
            report.candidate_result.total_trades,
            override_doc=override_doc)

        report.success = evaluate_success_criteria(
            self.hypothesis,
            report.candidate_result,
            report.bh_result,
            report.gate_result,
        )

        return report
