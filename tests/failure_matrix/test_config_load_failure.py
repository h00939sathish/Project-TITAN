"""Configuration load failure — bad config produces descriptive error."""
import pytest
from titan._core import RiskConfig
from titan.risk.limits import load_config


class TestConfigLoadFailure:
    def test_bad_config_values_fail(self):
        """Negative values overflow unsigned fields — documents current behavior."""
        with pytest.raises(OverflowError):
            load_config({"max_order_quantity": -1})

    def test_empty_config_returns_defaults(self):
        config = load_config({})
        assert config is not None
        assert config.max_order_quantity == 10000

    def test_partial_config_merges_with_defaults(self):
        config = load_config({"max_order_quantity": 500})
        assert config.max_order_quantity == 500
        assert config.max_position_size == 50000  # from defaults
        assert config.max_drawdown_fraction == 0.10  # from defaults
