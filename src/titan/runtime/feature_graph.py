from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from titan.runtime.events import MarketEvent
from titan.strategies.timeframes import Timeframe


@dataclass
class BarSnapshot:
    open: float
    high: float
    low: float
    close: float
    timestamp: datetime
    volume: int = 0


class SourceConsistencyError(Exception):
    pass


_PREDECESSOR = {
    Timeframe.FIVE_MINUTES: Timeframe.ONE_MINUTE,
    Timeframe.FIFTEEN_MINUTES: Timeframe.FIVE_MINUTES,
    Timeframe.ONE_HOUR: Timeframe.FIFTEEN_MINUTES,
    Timeframe.ONE_DAY: Timeframe.ONE_HOUR,
}

_AGGREGATION_N = {
    Timeframe.FIVE_MINUTES: 5,
    Timeframe.FIFTEEN_MINUTES: 3,
    Timeframe.ONE_HOUR: 4,
    Timeframe.ONE_DAY: 7,
}


class FeatureGraph:
    def __init__(self):
        self._bars: dict[str, dict[Timeframe, list[BarSnapshot]]] = defaultdict(lambda: defaultdict(list))
        self._source_is_tick: dict[str, bool] = {}
        self._current_minute: dict[str, dict | None] = defaultdict(lambda: None)

    def on_market_event(self, event: MarketEvent) -> None:
        inst = event.instrument_id

        if event.event_type == "Tick":
            if inst in self._source_is_tick and not self._source_is_tick[inst]:
                raise SourceConsistencyError(
                    f"Cannot mix Bar and Tick sources for {inst}"
                )
            self._source_is_tick.setdefault(inst, True)
            price = event.payload["price"]
            ts = event.occurred_at
            self._accumulate_tick(inst, ts, price)

        elif event.event_type == "BarClosed":
            if inst in self._source_is_tick and self._source_is_tick[inst]:
                raise SourceConsistencyError(
                    f"Cannot mix Tick and Bar sources for {inst}"
                )
            self._source_is_tick.setdefault(inst, False)
            tf = event.payload["timeframe"]
            if isinstance(tf, str):
                tf = Timeframe(tf)
            bar = BarSnapshot(
                open=event.payload.get("open", event.payload["close"]),
                high=event.payload.get("high", event.payload["close"]),
                low=event.payload.get("low", event.payload["close"]),
                close=event.payload["close"],
                timestamp=event.occurred_at,
                volume=event.payload.get("volume", 0),
            )
            self._bars[inst][tf].append(bar)

    def _accumulate_tick(self, inst: str, ts: datetime, price: float) -> None:
        minute_key = ts.replace(second=0, microsecond=0)
        current = self._current_minute[inst]

        if current is None or current["minute"] != minute_key:
            if current is not None:
                self._close_minute(inst)
            self._current_minute[inst] = {
                "minute": minute_key,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "count": 1,
            }
        else:
            current["high"] = max(current["high"], price)
            current["low"] = min(current["low"], price)
            current["close"] = price
            current["count"] += 1

    def _close_minute(self, inst: str) -> None:
        current = self._current_minute[inst]
        if current is None:
            return
        bar = BarSnapshot(
            open=current["open"],
            high=current["high"],
            low=current["low"],
            close=current["close"],
            timestamp=current["minute"],
            volume=current["count"],
        )
        self._bars[inst][Timeframe.ONE_MINUTE].append(bar)
        self._current_minute[inst] = None

    def bar(self, instrument_id: str, timeframe: Timeframe, index: int) -> BarSnapshot | None:
        self._close_minute(instrument_id)
        self._ensure_derived(instrument_id, timeframe)
        bars = self._bars[instrument_id].get(timeframe, [])
        if not bars:
            return None
        if index >= 0:
            idx = len(bars) - 1 - index
        else:
            idx = -index - 1
        if 0 <= idx < len(bars):
            return bars[idx]
        return None

    def _ensure_derived(self, inst: str, tf: Timeframe) -> None:
        if tf == Timeframe.ONE_MINUTE:
            return
        if tf not in _PREDECESSOR:
            return

        lower_tf = _PREDECESSOR[tf]
        n = _AGGREGATION_N[tf]

        self._ensure_derived(inst, lower_tf)
        lower_bars = self._bars[inst].get(lower_tf, [])

        n_complete = len(lower_bars) // n
        existing = len(self._bars[inst].get(tf, []))
        if n_complete == existing:
            return
        if n_complete == 0:
            return

        bars = []
        for i in range(n_complete):
            chunk = lower_bars[i * n : (i + 1) * n]
            bars.append(BarSnapshot(
                open=chunk[0].open,
                high=max(b.high for b in chunk),
                low=min(b.low for b in chunk),
                close=chunk[-1].close,
                timestamp=chunk[-1].timestamp,
                volume=sum(b.volume for b in chunk),
            ))

        self._bars[inst][tf] = bars

    def _flush_pending_minute(self, instrument_id: str) -> None:
        self._close_minute(instrument_id)
