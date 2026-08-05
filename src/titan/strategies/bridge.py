"""Bridge: registered strategy → TradeIntent + TradeManifest."""

from datetime import datetime, timezone

import titan.strategies.registrations  # noqa: F401 — triggers registration
from titan._core import TradeIntent
from titan.strategies.manifest import TradeManifest, make_manifest
from titan.strategies.regime.base import RegimeDetector
from titan.strategies.registry import get_registry


class StrategyBridge:
    """Wraps a registered strategy signal function with position management.

    Creates one signal function per instrument (each has its own indicator state).
    Long-only: ignores SELL when no position, ignores BUY when in position.

    Optionally accepts a RegimeDetector.  When the current regime is in
    ``suppress_regimes`` the bridge returns None instead of a TradeIntent.
    """

    def __init__(
        self,
        strategy_id: str,
        strategy_params: dict | None = None,
        account_id: str = "paper-1",
        order_size: int = 1,
        risk_profile_version: str = "1.0",
        regime_detector: RegimeDetector | None = None,
        suppress_regimes: tuple[str, ...] = ("HIGH_VOL",),
        lot_sizes: dict[str, int] | None = None,
        order_type: str = "MARKET",
        limit_offset: float = 0.0,
    ):
        self._reg = get_registry().get(strategy_id)
        self._params = dict(strategy_params or {})
        self._strategy_id = strategy_id
        self._account_id = account_id
        self._order_size = order_size
        self._lot_sizes = lot_sizes or {}
        self._order_type = "LIMIT" if str(order_type).upper() == "LIMIT" else "MARKET"
        self._limit_offset = float(limit_offset)
        self._risk_profile_version = risk_profile_version
        self._has_position: dict[str, bool] = {}
        self._package_digest = self._reg.version
        self._signals: dict[str, object] = {}
        self._warmup_signals: dict[str, str] = {}
        self._warmup_bar_count: dict[str, int] = {}
        self._last_bar_dates: dict[str, str] = {}
        self._last_intent_sides: dict[str, str] = {}
        self._warmed_up: set[str] = set()
        self._max_warmup_age_bars = 5
        self._regime_detector = regime_detector
        self._suppress_regimes = suppress_regimes
        self._current_regime = None
        self._last_manifest: TradeManifest | None = None

    def _signal_fn(self, instrument: str):
        """Get or create a per-instrument signal function."""
        if instrument not in self._signals:
            self._signals[instrument] = self._reg.factory(self._params)
        return self._signals[instrument]

    def warmup(self, instrument: str, prices: list[float]) -> None:
        """Feed historical prices for indicator and regime state; no intents."""
        if instrument in self._warmed_up:
            return
        fn = self._signal_fn(instrument)
        for price in prices:
            signal = fn({"close": price})
            if signal in {"BUY", "SELL"}:
                self._warmup_signals[instrument] = signal
            if self._regime_detector:
                self._current_regime = self._regime_detector.update(price)
        self._warmed_up.add(instrument)

    def on_price(
        self, instrument: str, price: float, bar_date: str | None = None
    ) -> TradeIntent | None:
        """Feed a new price and return a TradeIntent if a genuine new-bar signal fires.

        With a *bar_date* the same bar is never processed twice (prevents
        duplicate intents on restart).  Without one the caller is responsible
        for idempotency (live replay, simulation).

        If a RegimeDetector is configured and the current regime is in
        ``suppress_regimes`` the signal is suppressed (None returned).
        """
        if bar_date and self._last_bar_dates.get(instrument) == bar_date:
            return None
        if bar_date:
            self._last_bar_dates[instrument] = bar_date

        fn = self._signal_fn(instrument)
        self._warmup_bar_count[instrument] = self._warmup_bar_count.get(instrument, 0) + 1
        signal = fn({"close": price})
        if signal in {"BUY", "SELL"}:
            self._warmup_signals[instrument] = signal
            self._warmup_bar_count[instrument] = 0
        if signal is None:
            bar_count = self._warmup_bar_count.get(instrument, 0)
            if bar_count <= self._max_warmup_age_bars and instrument in self._warmup_signals:
                signal = self._warmup_signals[instrument]
            else:
                self._warmup_signals.pop(instrument, None)
        if signal is None:
            return None

        if self._regime_detector:
            self._current_regime = self._regime_detector.update(price)
            if self._current_regime and self._current_regime.regime in self._suppress_regimes:
                return None

        in_pos = self._has_position.get(instrument, False)
        if signal == "BUY" and in_pos:
            return None
        if signal == "SELL" and not in_pos:
            return None

        last_side = self._last_intent_sides.get(instrument)
        if last_side == signal:
            return None

        regime_dict = None
        if self._current_regime:
            regime_dict = {
                "regime": self._current_regime.regime,
                "confidence": self._current_regime.confidence,
                "volatility": self._current_regime.volatility,
            }

        # Limit orders are priced aggressively (last ± offset) so they are
        # marketable — fills like MKT but with a controlled worst-case price.
        order_price = float(price)
        if self._order_type == "LIMIT":
            order_price = order_price + self._limit_offset if signal == "BUY" else order_price - self._limit_offset

        intent = TradeIntent(
            strategy_id=self._strategy_id,
            strategy_package_digest=self._package_digest,
            account_id=self._account_id,
            instrument_id=instrument,
            side=signal,
            quantity=str(self._quantity(instrument)),
            order_type=self._order_type,
            time_in_force="DAY",
            risk_profile_version=self._risk_profile_version,
            market_data_timestamp=bar_date or datetime.now(timezone.utc).isoformat(),
            price=str(order_price),
        )
        self._last_manifest = make_manifest(
            strategy_id=self._strategy_id,
            strategy_version=self._package_digest,
            strategy_params=self._params,
            instrument_id=instrument,
            side=signal,
            quantity=str(self._quantity(instrument)),
            price=str(order_price),
            regime=regime_dict,
        )
        return intent

    def admitted(self, instrument: str, side: str) -> None:
        """Record that an intent for *instrument*/*side* was ADMITTED by the
        engine (passed the risk gate and was dispatched to the broker).

        Only admitted intents update position/side state so a later risk/broker
        rejection cannot suppress the next valid same-direction signal."""
        self._has_position[instrument] = side == "BUY"
        self._last_intent_sides[instrument] = side

    def _quantity(self, instrument: str) -> int:
        """Order quantity in instrument units: order_size × lot size.

        Lot size is 1 for equities (1 share per unit) and the instrument step
        size for forex (e.g. 1000 = one micro-lot of base currency), so a
        single ``order_size`` works across asset classes.
        """
        return self._order_size * self._lot_sizes.get(instrument, 1)

    @property
    def last_manifest(self) -> TradeManifest | None:
        return self._last_manifest

    def get_confidence(self, instrument: str) -> float:
        """Get confidence for the current signal [-1.0, 1.0]."""
        fn = self._signals.get(instrument)
        if fn is None:
            return 0.6
        strat = getattr(fn, "strat", None)
        if strat and hasattr(strat, "confidence"):
            conf = getattr(strat, "confidence")
            if isinstance(conf, (int, float)):
                return float(conf)
        last_side = self._last_intent_sides.get(instrument, "BUY")
        return 0.6 if last_side == "BUY" else -0.6


    def set_position(self, instrument: str, has_position: bool) -> None:
        """Sync position state (e.g., from portfolio after startup)."""
        self._has_position[instrument] = has_position

    def mark_processed(self, instrument: str, bar_date: str) -> None:
        """Mark a bar as already processed so it never fires an intent.

        Used at intraday session start: the backfilled bars are warmed into the
        signal function, and the last (stale) one is marked processed so the
        first intent comes from a bar that completes during the live session.
        """
        self._last_bar_dates[instrument] = bar_date

    def save_state(self) -> dict:
        return {
            "last_bar_dates": dict(self._last_bar_dates),
            "last_intent_sides": dict(self._last_intent_sides),
        }

    def restore_state(self, state: dict) -> None:
        self._last_bar_dates = state.get("last_bar_dates", {})
        self._last_intent_sides = state.get("last_intent_sides", {})
