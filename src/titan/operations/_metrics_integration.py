"""Metric definitions and wiring helpers for TITAN subsystems."""

from titan.operations.metrics import MetricsRegistry


# Global instance — codebase convention uses module-level registry
_REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _REGISTRY


# Risk gate metrics
intents_evaluated = _REGISTRY.counter("intents_evaluated")
intents_rejected = _REGISTRY.counter("intents_rejected")
kill_switch_triggered = _REGISTRY.counter("kill_switch_triggered")
trading_state_changed = _REGISTRY.counter("trading_state_changed")

# Portfolio metrics
positions_open = _REGISTRY.gauge("positions_open")
gross_exposure = _REGISTRY.gauge("gross_exposure")
cash_balance = _REGISTRY.gauge("cash_balance")

# Execution metrics
orders_submitted = _REGISTRY.counter("orders_submitted")
orders_filled = _REGISTRY.counter("orders_filled")
orders_rejected = _REGISTRY.counter("orders_rejected")
orders_cancelled = _REGISTRY.counter("orders_cancelled")
orders_unknown = _REGISTRY.counter("orders_unknown")

# Reconciliation metrics
drift_count_warning = _REGISTRY.gauge("drift_count_warning")
drift_count_critical = _REGISTRY.gauge("drift_count_critical")
last_reconciliation_age_seconds = _REGISTRY.gauge("last_reconciliation_age_seconds")

# System state
system_state = _REGISTRY.gauge("system_state")
