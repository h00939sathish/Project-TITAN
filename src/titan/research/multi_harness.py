"""Multi-instrument validation harness — runs a hypothesis across multiple instruments."""

from dataclasses import dataclass, field

from titan.backtest.results import BacktestResult
from titan.research.gate import check_min_trades
from titan.research.harness import (
    INITIAL_CAPITAL,
    StrategyRunner,
    _exposure_curve,
    buy_and_hold_result,
    evaluate_success_criteria,
    load_bars,
    make_ma_signal_fn,
    split_bars,
)
from titan.research.hypothesis import Hypothesis
from titan.research.metrics import (
    InstrumentDailyCorrelation,
    compute_effective_trades,
    compute_pairwise_correlations,
)


@dataclass
class InstrumentSpec:
    instrument_id: str
    data_path: str
    bars: list[dict] = field(default_factory=list)
    train_bars: list[dict] = field(default_factory=list)
    test_bars: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    result: BacktestResult | None = None


@dataclass
class MultiInstrumentReport:
    hypothesis: Hypothesis
    instruments: list[InstrumentSpec]
    pooled_equity_curve: list[float] = field(default_factory=list)
    pooled_result: BacktestResult | None = None
    bh_result: BacktestResult | None = None
    cash_result: BacktestResult | None = None
    ma_control_result: BacktestResult | None = None
    total_pooled_trades: int = 0
    effective_trades: float = 0.0
    avg_pairwise_corr: float = 0.0
    correlations: list[InstrumentDailyCorrelation] = field(default_factory=list)
    gate_result: None = None
    success: bool = False
    per_instrument_violations: list[str] = field(default_factory=list)


def _compute_pooled_equity(instruments: list[InstrumentSpec]) -> list[float]:
    min_len = min(len(s.equity_curve) for s in instruments)
    return [sum(s.equity_curve[i] for s in instruments) for i in range(min_len)]


def _buy_and_hold_pooled(instruments: list[InstrumentSpec]) -> BacktestResult:
    eq_curves = []
    for spec in instruments:
        bh = buy_and_hold_result(spec.test_bars)
        curve = [INITIAL_CAPITAL]
        initial_close = spec.test_bars[0]["close"] if spec.test_bars else 1.0
        for bar in spec.test_bars:
            curve.append(INITIAL_CAPITAL * bar["close"] / initial_close)
        eq_curves.append(curve)
    if not eq_curves:
        return BacktestResult()
    min_len = min(len(e) for e in eq_curves)
    pooled = [sum(eq[i] for eq in eq_curves) for i in range(min_len)]
    return BacktestResult.compute(pooled, [])


class MultiInstrumentHarness:
    def __init__(
        self,
        hypothesis: Hypothesis,
        instruments: list[InstrumentSpec],
        signal_factory=make_ma_signal_fn,
        control_params: dict | None = None,
        control_factory=make_ma_signal_fn,
        control_label: str = "MA(5,20)",
    ):
        self.hypothesis = hypothesis
        self.instruments = instruments
        self.signal_factory = signal_factory
        self.control_params = control_params or {"fast": 5, "slow": 20}
        self.control_factory = control_factory
        self.control_label = control_label

    def run(self) -> MultiInstrumentReport:
        report = MultiInstrumentReport(self.hypothesis, self.instruments)
        test_start = self.hypothesis.test_period

        for spec in self.instruments:
            bars_all = load_bars(spec.data_path)
            spec.bars = bars_all
            train_bars, test_bars = split_bars(bars_all, test_start)
            spec.train_bars = train_bars
            spec.test_bars = test_bars

            strategy_params = dict(self.hypothesis.strategy_params)
            sig_fn = self.signal_factory(strategy_params)
            runner = StrategyRunner(sig_fn)
            eq, trades = runner.run(test_bars)
            spec.equity_curve = eq
            spec.trades = trades

            exposure_curve = _exposure_curve(eq, trades, test_bars)
            spec.result = BacktestResult.compute(eq, trades, exposure_curve)

        report.pooled_equity_curve = _compute_pooled_equity(self.instruments)
        report.pooled_result = BacktestResult.compute(report.pooled_equity_curve, [])

        n_capital = INITIAL_CAPITAL * len(self.instruments)
        n_bars = len(report.pooled_equity_curve) - 1
        cash_eq = [n_capital] * (n_bars + 1)
        report.cash_result = BacktestResult.compute(cash_eq, [])

        report.bh_result = _buy_and_hold_pooled(self.instruments)

        control_eq_curves = []
        for spec in self.instruments:
            control_runner = StrategyRunner(
                self.control_factory(self.control_params), 10)
            eq, _ = control_runner.run(spec.test_bars)
            control_eq_curves.append(eq)
        min_len = min(len(e) for e in control_eq_curves)
        pooled_control = [sum(eq[i] for eq in control_eq_curves) for i in range(min_len)]
        report.ma_control_result = BacktestResult.compute(pooled_control, [])

        report.total_pooled_trades = sum(
            len(spec.trades) for spec in self.instruments
        )

        instrument_data = [
            (spec.instrument_id, spec.test_bars) for spec in self.instruments
        ]
        report.correlations = compute_pairwise_correlations(instrument_data)

        if report.correlations:
            report.avg_pairwise_corr = sum(
                c.pearson_r for c in report.correlations
            ) / len(report.correlations)
        else:
            report.avg_pairwise_corr = 0.0

        report.effective_trades = compute_effective_trades(
            report.total_pooled_trades,
            len(self.instruments),
            report.avg_pairwise_corr,
        )

        trade_counts = [len(spec.trades) for spec in self.instruments]
        total = sum(trade_counts)
        min_trade_floor = max(int(total * 0.20), 1) if total > 0 else 1
        violations = []
        for i, spec in enumerate(self.instruments):
            if total > 0 and trade_counts[i] < total * 0.20:
                violations.append(
                    f"{spec.instrument_id}: {trade_counts[i]}/{total} "
                    f"({trade_counts[i]/total*100:.1f}%) below 20% minimum"
                )
        report.per_instrument_violations = violations

        effective_trades_int = int(round(report.effective_trades))
        override_doc = ""
        if self.hypothesis.sample_adequacy_policy == "Path B":
            override_doc = self.hypothesis.path_b_evidence_standard
        report.gate_result = check_min_trades(
            effective_trades_int,
            override_doc=override_doc,
        )

        report.success = evaluate_success_criteria(
            self.hypothesis,
            report.pooled_result,
            report.bh_result,
            report.gate_result,
        )

        return report
