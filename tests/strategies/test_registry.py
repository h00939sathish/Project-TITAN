"""Tests for strategy registry."""

import pytest
import titan.strategies.registrations  # noqa: F401 — triggers registration
from titan.strategies.registry import (
    ParameterDef,
    StrategyRegistration,
    StrategyRegistry,
    get_registry,
)


class TestStrategyRegistry:
    def test_register_and_get(self):
        reg = StrategyRegistry()
        reg.register(StrategyRegistration(
            strategy_id="test-strat",
            version="1.0",
            description="A test strategy",
            parameter_schema=(
                ParameterDef("x", "int", 10, "X param"),
            ),
            factory=lambda params: lambda bar: None,
        ))
        retrieved = reg.get("test-strat")
        assert retrieved.strategy_id == "test-strat"
        assert retrieved.version == "1.0"

    def test_duplicate_registration_raises(self):
        reg = StrategyRegistry()
        reg.register(StrategyRegistration(
            strategy_id="dup", version="1", description="", parameter_schema=(),
            factory=lambda params: lambda bar: None,
        ))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(StrategyRegistration(
                strategy_id="dup", version="2", description="", parameter_schema=(),
                factory=lambda params: lambda bar: None,
            ))

    def test_get_unknown_raises(self):
        reg = StrategyRegistry()
        with pytest.raises(KeyError, match="Unknown strategy"):
            reg.get("nonexistent")

    def test_list_ids(self):
        reg = StrategyRegistry()
        reg.register(StrategyRegistration(
            strategy_id="b", version="1", description="", parameter_schema=(),
            factory=lambda params: lambda bar: None,
        ))
        reg.register(StrategyRegistration(
            strategy_id="a", version="1", description="", parameter_schema=(),
            factory=lambda params: lambda bar: None,
        ))
        assert reg.list_ids() == ["a", "b"]

    
def test_global_registry_is_singleton():
    a = get_registry()
    b = get_registry()
    assert a is b


def test_global_registry_has_registered_strategies():
    reg = get_registry()
    ids = reg.list_ids()
    assert "ma-crossover" in ids
    assert "mean-reversion" in ids
    assert "volatility-regime" in ids
