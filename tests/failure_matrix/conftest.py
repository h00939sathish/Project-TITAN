"""Shared fixtures for FAILURE_MATRIX tests."""
import pytest
from titan._core import (
    Money, RiskConfig, RiskGate, PortfolioEngine, ReconciliationEngine,
    ReconciliationConfig,
)
from titan.execution.simulated_adapter import SimulatedAdapter


@pytest.fixture
def default_config() -> RiskConfig:
    return RiskConfig(
        ["AAPL", "MSFT"],
        Money("50000", "USD"), 1000, 5000,
        Money("100000", "USD"), 0.10, Money("5000", "USD"), 5000,
    )


@pytest.fixture
def gate(default_config) -> RiskGate:
    return RiskGate(default_config)


@pytest.fixture
def portfolio() -> PortfolioEngine:
    return PortfolioEngine("USD", Money("100000", "USD"))


@pytest.fixture
def adapter() -> SimulatedAdapter:
    return SimulatedAdapter()
