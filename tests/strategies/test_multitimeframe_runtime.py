from datetime import datetime, timezone

from titan.runtime.events import StrategyDefinition, TriggerSpec
from titan.strategies.multitimeframe_runtime import MultiTimeframeRuntime
from titan.strategies.timeframes import Timeframe

_BUY_WARMUP = [100, 100, 100, 100, 101, 102]
_SELL_WARMUP = [100, 100, 100, 100, 99, 98]


def test_same_strategy_has_independent_state_per_timeframe(runtime, event_factory, t0):
    runtime.warmup("SPY", Timeframe.FIVE_MINUTES, _BUY_WARMUP)
    runtime.warmup("SPY", Timeframe.ONE_DAY, _SELL_WARMUP)
    assert runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0)
    )
    assert runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.ONE_DAY, 97, t0)
    ) == []


def test_duplicate_closed_bar_emits_no_second_intent(runtime, event_factory, t0):
    event = event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0)
    runtime.warmup("SPY", Timeframe.FIVE_MINUTES, _BUY_WARMUP)
    runtime.on_market_event(event)
    assert runtime.on_market_event(event) == []


def test_no_signal_on_closed_bar_creates_no_intent(runtime, event_factory, t0):
    assert runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.FIFTEEN_MINUTES, 100, t0)
    ) == []


def test_stale_data_rejected(runtime, event_factory, t0):
    old_ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    event = event_factory.bar_closed(
        "SPY", Timeframe.FIVE_MINUTES, 100, timestamp=old_ts, received_at=t0
    )
    assert runtime.on_market_event(event) == []


def test_unqualified_variant_rejected(runtime, event_factory, t0):
    rt = MultiTimeframeRuntime()
    rt.register(StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES),
        params={"fast": 999, "slow": 2000},
    ))
    rt.warmup("SPY", Timeframe.FIVE_MINUTES, _BUY_WARMUP)
    assert rt.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0)
    ) == []


def test_SELL_while_flat_rejected(runtime, event_factory, t0):
    runtime.warmup("SPY", Timeframe.ONE_DAY, _SELL_WARMUP)
    assert runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.ONE_DAY, 97, t0)
    ) == []


def test_provenance_includes_strategy_id_and_timeframe(runtime, event_factory, t0):
    runtime.warmup("SPY", Timeframe.FIVE_MINUTES, _BUY_WARMUP)
    proposals = runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0)
    )
    assert len(proposals) == 1
    assert proposals[0].strategy_id == "ma-crossover"
    assert proposals[0].timeframe == Timeframe.FIVE_MINUTES
    assert proposals[0].side == "BUY"
    assert proposals[0].instrument_id == "SPY"
    assert proposals[0].close_timestamp == t0


def test_warmup_then_evaluate(runtime, event_factory, t0):
    runtime.warmup("SPY", Timeframe.FIVE_MINUTES, _BUY_WARMUP)
    proposals = runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0)
    )
    assert len(proposals) == 1
    assert proposals[0].side == "BUY"


def test_warmup_persists_across_bars(runtime, event_factory):
    runtime.warmup("SPY", Timeframe.FIVE_MINUTES, _BUY_WARMUP)
    t_a = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    t_b = datetime(2026, 7, 24, 12, 5, 0, tzinfo=timezone.utc)
    t_c = datetime(2026, 7, 24, 12, 10, 0, tzinfo=timezone.utc)

    p1 = runtime.on_market_event(event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t_a))
    assert len(p1) == 1
    assert p1[0].side == "BUY"

    p2 = runtime.on_market_event(event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 104, t_b))
    assert p2 == []

    p3 = runtime.on_market_event(event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 80, t_c))
    assert len(p3) == 1
    assert p3[0].side == "SELL"
