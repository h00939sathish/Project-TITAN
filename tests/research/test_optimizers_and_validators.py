"""Unit tests for research optimizers, plateau detector, and OptimizationRiskValidator."""

import pytest
from titan.research.optimizers.parameter_surface import ParameterSurface, SurfaceNode
from titan.research.optimizers.plateau_detector import PlateauDetector
from titan.research.validators.parameter_stability import OptimizationRiskValidator
from titan.research.evidence_bundle import create_evidence_bundle


def test_parameter_surface_plateau_coverage():
    surface = ParameterSurface("dual-ma", "15m", "SPY")
    node1 = SurfaceNode({"fast": 10, "slow": 50}, 1.6, 1.8, 1.5, 5.0, 10.0, 20)
    node2 = SurfaceNode({"fast": 20, "slow": 50}, 1.2, 1.0, 0.9, 15.0, -2.0, 15)
    surface.add_node(node1)
    surface.add_node(node2)

    coverage = surface.compute_plateau_coverage(sharpe_threshold=1.5, pf_threshold=1.3)
    assert coverage == 0.5  # 1 out of 2 qualifies


def test_parameter_surface_neighborhood_stability():
    surface = ParameterSurface("dual-ma", "15m", "SPY")
    n0 = SurfaceNode({"fast": 20, "slow": 50}, 1.5, 1.5, 1.4, 5.0, 10.0, 20)
    n1 = SurfaceNode({"fast": 10, "slow": 50}, 1.5, 1.6, 1.4, 4.0, 11.0, 22)
    n2 = SurfaceNode({"fast": 30, "slow": 50}, 1.5, 1.4, 1.3, 6.0, 9.0, 18)

    surface.add_node(n0)
    surface.add_node(n1)
    surface.add_node(n2)

    stability = surface.compute_neighborhood_stability({"fast": 20, "slow": 50})
    assert stability > 0.80  # Smooth plateau, high stability


def test_optimization_risk_validator_rejection_on_spike():
    validator = OptimizationRiskValidator(min_stability=0.70, min_coverage=0.80)
    surface = ParameterSurface("dual-ma", "15m", "SPY")
    # Isolated spike node surrounded by failing nodes
    n0 = SurfaceNode({"fast": 20, "slow": 50}, 2.5, 2.5, 2.0, 3.0, 20.0, 10)
    n1 = SurfaceNode({"fast": 10, "slow": 50}, 0.1, 0.1, 0.5, 25.0, -10.0, 5)

    surface.add_node(n0)
    surface.add_node(n1)

    scorecard = validator.validate("dual-ma", "15m", {"SPY": surface})
    assert not scorecard.passed_all_checks
    assert "REJECTED" in scorecard.summary()
