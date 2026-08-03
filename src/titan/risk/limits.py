"""Loads risk configuration from dict/JSON into Rust RiskConfig objects."""

from titan._core import Money, RiskConfig

DEFAULT_CFG = {
    "instrument_eligibility": [],
    "max_order_notional": ("1000000", "USD"),
    "max_order_quantity": 10000,
    "max_position_size": 50000,
    "max_gross_exposure": ("10000000", "USD"),
    "max_drawdown_fraction": 0.10,
    "max_daily_loss": ("50000", "USD"),
    "data_freshness_threshold_ms": 5000,
    "clock_skew_tolerance_ms": 100,
    "max_correlated_exposure": 0.70,
}


def load_config(data: dict | None = None) -> RiskConfig:
    """Load risk config from a dict, falling back to defaults for missing keys."""
    cfg = {**DEFAULT_CFG, **(data or {})}
    rc = RiskConfig(
        cfg["instrument_eligibility"],
        Money(*cfg["max_order_notional"]),
        cfg["max_order_quantity"],
        cfg["max_position_size"],
        Money(*cfg["max_gross_exposure"]),
        cfg["max_drawdown_fraction"],
        Money(*cfg["max_daily_loss"]),
        cfg["data_freshness_threshold_ms"],
        cfg["clock_skew_tolerance_ms"],
    )
    rc.max_correlated_exposure = cfg["max_correlated_exposure"]
    return rc
