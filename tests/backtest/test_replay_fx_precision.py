"""ReplayEngine must keep FX price precision and run its circuit breaker on bar time."""

from datetime import datetime, timedelta, timezone

import pytest

from titan.backtest.engine import ReplayEngine
from titan.backtest.fills import BarConservativeFillModel
from titan.risk.circuit_breaker import BreakerStage, CircuitBreaker


class Alternator:
    """Signals on every bar, alternating BUY/SELL so positions stay flat-ish."""

    strategy_id = "alternator"

    def __init__(self):
        self.n = 0

    def update(self, price):
        self.n += 1
        return "BUY" if self.n % 2 else "SELL"


def fx_bars(n=60, start=1.08345, step=0.00007, instrument="EURUSD"):
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(n):
        px = round(start + i * step, 5)
        bars.append({"instrument_id": instrument,
                     "timestamp": (t0 + timedelta(hours=4 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "open": px, "high": px, "low": px, "close": px, "volume": 1})
    return bars


def test_fx_fill_prices_keep_five_decimals():
    bars = fx_bars()
    result = ReplayEngine(Alternator(), bars, tick_size="0.00001").run()
    assert result.rejected_intents == 0
    fills = {float(r.fill_price) for r in result.bar_results if r.accepted}
    closes = {b["close"] for b in bars}
    assert fills and fills <= closes  # no fill was rounded away from its 5dp close


def test_fast_replay_is_not_rate_limited_on_wall_clock():
    result = ReplayEngine(Alternator(), fx_bars(n=200), tick_size="0.00001").run()
    assert result.rejected_intents == 0
    assert result.trades == 200


def test_default_tick_is_still_two_decimals():
    engine = ReplayEngine(Alternator(), fx_bars(n=2))
    assert engine._price_str(1.08345) == "1.08"
    assert BarConservativeFillModel().price_decimals == 2


def test_invalid_tick_is_refused():
    with pytest.raises(ValueError):
        ReplayEngine(Alternator(), fx_bars(n=2), tick_size="0")


def test_injected_clock_still_enforces_per_second_limit():
    now = [1000.0]
    breaker = CircuitBreaker(clock=lambda: now[0])
    allowed = [breaker.record_intent()[0] for _ in range(11)]
    assert allowed == [True] * 10 + [False]
    assert breaker.stage == BreakerStage.THROTTLED
    now[0] += 2.0
    assert breaker.record_intent()[0] is True


def test_same_timestamp_burst_is_still_throttled_in_replay():
    bars = fx_bars(n=1) * 12  # twelve intents at one simulated instant
    result = ReplayEngine(Alternator(), bars, tick_size="0.00001").run()
    assert result.rejected_intents == 2
