"""Strategy runtime — loads packages and manages lifecycle."""

from hashlib import sha256
from titan._core import TradeIntent
from titan.strategies.manifest import StrategyManifest


class StrategyRejection(Exception):
    """Raised when a strategy's intent is rejected before emission."""
    pass


class StrategyRuntime:
    """Manages strategy lifecycle and intent emission."""

    def __init__(self):
        self._strategies: dict[str, object] = {}
        self._manifests: dict[str, StrategyManifest] = {}
        self._current_time: str | None = None

    def register(self, strategy_id: str, strategy: object, manifest: StrategyManifest) -> None:
        """Register a strategy with its manifest."""
        if not manifest.verify():
            raise ValueError(f"Manifest digest mismatch for {strategy_id}")
        if strategy_id in self._strategies:
            raise ValueError(f"Strategy {strategy_id} already registered")
        self._strategies[strategy_id] = strategy
        self._manifests[strategy_id] = manifest

    def set_current_time(self, timestamp: str) -> None:
        self._current_time = timestamp

    def emit_intent(self, strategy_id: str, instrument_id: str, side: str,
                    quantity: str, order_type: str = "LIMIT",
                    time_in_force: str = "DAY", price: str | None = None,
                    stop_price: str | None = None) -> TradeIntent:
        """Emit a TradeIntent with strategy provenance attached."""
        manifest = self._manifests.get(strategy_id)
        if not manifest:
            raise StrategyRejection(f"Unknown strategy: {strategy_id}")

        if not manifest.verify():
            raise StrategyRejection(f"Manifest digest mismatch for {strategy_id}")

        if instrument_id not in manifest.universe and manifest.universe:
            raise StrategyRejection(f"Instrument {instrument_id} not in strategy universe")

        return TradeIntent(
            strategy_id=strategy_id,
            strategy_package_digest=manifest.package_digest,
            account_id="paper-1",
            instrument_id=instrument_id,
            side=side,
            quantity=str(quantity),
            order_type=order_type,
            time_in_force=time_in_force,
            risk_profile_version=manifest.risk_profile_version,
            price=price,
            stop_price=stop_price,
        )
