"""Tests for EQ-Micro-001 Intraday ETF Lead-Lag Research Screen."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.backtest.factor_simulator import FactorCostModel, FactorSimulationResult
from titan.data.equities_intraday import (
    EquitiesIntradayDataError,
    EquitiesIntradayManifest,
    build_intraday_universe,
)
from titan.research.equities_micro_screen_001 import (
    FactorPreRegistration,
    calculate_etf_intraday_lead_lag_signals,
    compute_lead_lag_rank_ic,
    evaluate_micro_001_gates,
    load_factor_preregistration,
    run_micro_screen_001,
    simulate_intraday_lead_lag_portfolio,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_sp50_liquid_intraday_v1.json"
PREREG_PATH = ROOT / "research" / "equities" / "hypotheses" / "EQ-Micro-001-prereg.json"
SCREEN_PY = ROOT / "src" / "titan" / "research" / "equities_micro_screen_001.py"


def _make_mock_intraday_universe(n_days: int = 5, seed: int = 42):
    manifest = EquitiesIntradayManifest.load(MANIFEST_PATH)
    all_syms = list(manifest.etf_anchors) + list(manifest.universe)
    dates = []
    for day in range(n_days):
        day_str = f"2023-01-{day+3:02d}"
        d_range = pd.date_range(f"{day_str} 09:30:00", f"{day_str} 16:00:00", freq="5min")
        dates.extend(d_range)

    np.random.seed(seed)
    series_map = {}
    # Create an ETF anchor with an intraday impulse
    spy_rets = np.random.normal(0.0001, 0.002, size=len(dates))
    spy_rets[10] = 0.015  # Upward impulse at bar 10
    spy_rets[50] = -0.015  # Downward impulse at bar 50
    spy_p = 100.0 * np.exp(np.cumsum(spy_rets))
    series_map["SPY"] = pd.Series(spy_p, index=dates)

    for sym in all_syms:
        if sym == "SPY":
            continue
        # Constituents drift with beta to SPY + noise
        noise = np.random.normal(0.0, 0.002, size=len(dates))
        stock_rets = 0.8 * spy_rets + noise
        stock_p = 50.0 * np.exp(np.cumsum(stock_rets))
        series_map[sym] = pd.Series(stock_p, index=dates)

    univ = build_intraday_universe(series_map, manifest)
    return univ, manifest


class TestPreRegistrationValidation:
    def test_load_preregistration_succeeds(self):
        prereg = load_factor_preregistration(PREREG_PATH)
        assert prereg.hypothesis_id == "EQ-Micro-001"
        assert prereg.factor_name == "etf_constituent_intraday_lead_lag"
        assert len(prereg.etf_anchors) == 4
        assert prereg.parameters["holding_horizon_bars"] == 6
        assert prereg.pass_criteria["min_oos_net_sharpe"] == 1.20

    def test_missing_fields_rejected(self):
        with pytest.raises(EquitiesIntradayDataError):
            run_micro_screen_001(None, {"hypothesis_id": "EQ-Micro-001"})


class TestSignalGenerationAndFlatAtClose:
    def test_impulse_generates_active_scores_and_flat_at_close(self):
        univ, manifest = _make_mock_intraday_universe(n_days=2)
        prereg = load_factor_preregistration(PREREG_PATH)
        scores = calculate_etf_intraday_lead_lag_signals(univ, prereg.parameters)

        assert scores.shape == (len(univ.prices), 50)
        # Verify active non-zero signals were triggered during impulse bars
        non_zeros = (scores != 0.0).sum().sum()
        assert non_zeros > 0

        # Verify flat at close: final bar (15:55 / 16:00) must have zero signal
        for idx in scores.index:
            if "15:55" in str(idx) or "16:00" in str(idx):
                assert (scores.loc[idx] == 0.0).all()


class TestPortfolioSimulationAndFriction:
    def test_portfolio_simulation_calculates_friction_and_deadbands(self):
        univ, manifest = _make_mock_intraday_universe(n_days=3)
        prereg = load_factor_preregistration(PREREG_PATH)
        scores = calculate_etf_intraday_lead_lag_signals(univ, prereg.parameters)
        cost = FactorCostModel.baseline_ibkr_pro_fixed()

        res = simulate_intraday_lead_lag_portfolio(univ, scores, cost, prereg.parameters)
        assert res.annualized_net_sharpe is not None
        assert res.annualized_net_return is not None
        assert "friction_drag_ratio" in res.costs
        assert res.costs["friction_drag_ratio"] >= 0.0


class TestRankICComputation:
    def test_compute_rank_ic_returns_valid_metrics(self):
        univ, manifest = _make_mock_intraday_universe(n_days=3)
        prereg = load_factor_preregistration(PREREG_PATH)
        scores = calculate_etf_intraday_lead_lag_signals(univ, prereg.parameters)
        mean_ic, pos_frac = compute_lead_lag_rank_ic(univ, scores, forward_bars=6)

        assert -1.0 <= mean_ic <= 1.0
        assert 0.0 <= pos_frac <= 1.0


class TestGateEvaluation:
    def test_failed_gates_emit_rule_8_failure_mode(self):
        prereg = load_factor_preregistration(PREREG_PATH)
        # Create mock failing simulation result
        mock_oos = FactorSimulationResult(
            hypothesis_id="EQ-Micro-001",
            partition="OOS",
            net_returns=pd.Series([0.0005, -0.0025]),
            gross_returns=pd.Series([0.001, -0.002]),
            long_returns=pd.Series([0.001]),
            short_returns=pd.Series([-0.002]),
            turnover_series=pd.Series([0.5, 0.5]),
            rank_ic_series=pd.Series([0.01]),
            costs={"friction_drag_ratio": 0.65},
            annualized_net_sharpe=0.40,  # Fails Gate 1 (< 1.20)
            annualized_net_return=0.025,
            max_drawdown=0.045,
            monthly_turnover=1.5,
            mean_rank_ic=0.01,
            ic_positive_fraction=0.45,
            quantile_returns={"long": 0.01, "short": -0.02, "monotonic": False},
        )
        mock_adverse = FactorSimulationResult(
            hypothesis_id="EQ-Micro-001",
            partition="OOS_ADVERSE",
            net_returns=pd.Series([-0.001]),
            gross_returns=pd.Series([0.0]),
            long_returns=pd.Series([0.0]),
            short_returns=pd.Series([0.0]),
            turnover_series=pd.Series([0.5]),
            rank_ic_series=pd.Series([0.01]),
            costs={"friction_drag_ratio": 1.0},
            annualized_net_sharpe=-0.50,
            annualized_net_return=-0.02,
            max_drawdown=0.05,
            monthly_turnover=1.5,
            mean_rank_ic=0.01,
            ic_positive_fraction=0.45,
            quantile_returns={},
        )

        eval_res = evaluate_micro_001_gates(mock_oos, mock_adverse, prereg)
        assert eval_res["verdict"] == "negative_result"
        assert eval_res["failure_mode"] == "mechanism_failure"
        assert eval_res["failure_mode_confidence"] == "high"


class TestEndToEndScreenAndTmpPathOutput:
    def test_run_micro_screen_001_writes_bundle_to_tmp_path(self, tmp_path):
        univ, manifest = _make_mock_intraday_universe(n_days=10)
        prereg = load_factor_preregistration(PREREG_PATH)

        # Update partition dates in prereg for mock fixture
        custom_prereg = FactorPreRegistration(
            hypothesis_id="EQ-Micro-001",
            factor_name="etf_constituent_intraday_lead_lag",
            etf_anchors=prereg.etf_anchors,
            parameters=prereg.parameters,
            cost_label=prereg.cost_label,
            is_partition={"from": "2023-01-03", "to": "2023-01-07"},
            oos_partition={"from": "2023-01-08", "to": "2023-01-12"},
            pass_criteria=prereg.pass_criteria,
            universe_label="us_sp50_liquid_intraday_v1",
        )

        tmp_out = tmp_path / "test_micro_bundle.json"
        bundle = run_micro_screen_001(univ, custom_prereg, output_path=tmp_out)

        assert bundle["hypothesis_id"] == "EQ-Micro-001"
        assert "is" in bundle
        assert "oos" in bundle
        assert "gates" in bundle
        assert tmp_out.exists()


class TestExecutionImportBan:
    def test_screen_cannot_import_execution(self):
        banned = (
            "from titan.execution",
            "import titan.execution",
            "from titan.runtime",
            "from titan.portfolio",
        )
        text = SCREEN_PY.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"Banned import {token!r} in {SCREEN_PY}"
        assert "import TradeIntent" not in text
        assert "import PaperSession" not in text
        assert "import BrokerAdapter" not in text
