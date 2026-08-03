import logging
from datetime import datetime

from titan.runtime.events import MarketEvent, TradeProposal, StrategyDefinition
from titan.strategies.registry import get_registry
from titan.strategies.timeframes import Timeframe

log = logging.getLogger("titan.runtime")


class MultiTimeframeRuntime:
    DEFAULT_EQUITY = 100_000

    def __init__(self, definitions: list[StrategyDefinition] | None = None, risk_pct: float = 10.0,
                 watchlist_ids: set[str] | None = None):
        self._reg = get_registry()
        self._definitions: list[StrategyDefinition] = []
        self._signal_fns: dict[tuple[str, str, Timeframe], object] = {}
        self._warmup_signals: dict[tuple[str, str, Timeframe], str | None] = {}
        self._positions: dict[tuple[str, str, Timeframe], bool] = {}
        self._last_sides: dict[tuple[str, str, Timeframe], str | None] = {}
        self._last_timestamps: dict[tuple[str, str, Timeframe], datetime | None] = {}
        self._staleness_threshold_seconds: float = 86400
        self._risk_pct = risk_pct
        self._watchlist_ids: set[str] = watchlist_ids or set()

        if definitions:
            for d in definitions:
                self.register(d)

    def register(self, definition: StrategyDefinition) -> None:
        self._definitions.append(definition)

    def warmup(self, instrument_id: str, timeframe: Timeframe, prices: list[float]) -> None:
        for d in self._definitions:
            if d.trigger.event_type == "BarClosed" and d.trigger.timeframe == timeframe:
                key = (d.strategy_id, instrument_id, timeframe)
                fn = self._signal_fn(key, d)
                self._warmup_signals[key] = None
                for price in prices:
                    signal = fn({"close": price})
                    if signal is not None:
                        self._warmup_signals[key] = signal

    def on_market_event(self, event: MarketEvent) -> list[TradeProposal]:
        if event.event_type != "BarClosed":
            return []
        tf = self._extract_timeframe(event)
        if tf is None:
            return []
        close = event.payload.get("close")
        if close is None:
            return []
        close_ts = event.occurred_at

        if (event.received_at - close_ts).total_seconds() > self._staleness_threshold_seconds:
            return []

        proposals = []
        for d in self._definitions:
            key = (d.strategy_id, event.instrument_id, tf)
            if not (d.trigger.event_type == "BarClosed" and d.trigger.timeframe == tf):
                continue

            registration = self._reg.get(d.strategy_id)
            is_qualified = registration.is_qualified_for(tf, d.params)
            if not is_qualified and d.strategy_id not in self._watchlist_ids:
                log.info(
                    f"[gate] SKIP: {d.strategy_id} ({tf}) — not qualified"
                )
                continue
            producer_kind = "shadow" if d.strategy_id in self._watchlist_ids else "strategy"
            if producer_kind == "shadow":
                log.info(
                    f"[gate] SHADOW: {d.strategy_id} ({tf}) — watchlist, routing to shadow deployer"
                )

            if self._last_timestamps.get(key) == close_ts:
                continue

            fn = self._signal_fn(key, d)
            signal = fn({"close": close})
            if signal is None:
                signal = self._warmup_signals.get(key)
            if signal is None:
                continue

            if signal == "BUY" and self._positions.get(key, False):
                continue
            if signal == "SELL" and not self._positions.get(key, False):
                continue
            if self._last_sides.get(key) == signal:
                continue

            shares = max(1, int(self.DEFAULT_EQUITY * self._risk_pct / 100.0 / close))
            proposal = TradeProposal(
                proposal_id=f"prop-{event.message_id}-{d.strategy_id}",
                strategy_id=d.strategy_id,
                producer_kind=producer_kind,
                instrument_id=event.instrument_id,
                side=signal,
                quantity=float(shares),
                price=close,
                timeframe=tf,
                close_timestamp=close_ts,
                rationale_digest="",
                sources=[],
            )
            proposals.append(proposal)

            self._positions[key] = signal == "BUY"
            self._last_sides[key] = signal
            self._last_timestamps[key] = close_ts
            self._warmup_signals[key] = signal

        return proposals

    def _signal_fn(self, key: tuple, definition: StrategyDefinition) -> object:
        if key not in self._signal_fns:
            reg = self._reg.get(definition.strategy_id)
            self._signal_fns[key] = reg.factory(definition.params)
        return self._signal_fns[key]

    @staticmethod
    def _extract_timeframe(event: MarketEvent) -> Timeframe | None:
        tf_raw = event.payload.get("timeframe")
        if tf_raw is None:
            return None
        if isinstance(tf_raw, Timeframe):
            return tf_raw
        for tf in Timeframe:
            if tf_raw == tf.value:
                return tf
        return None
