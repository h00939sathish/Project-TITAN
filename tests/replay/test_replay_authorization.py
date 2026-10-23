"""ADR-035: replay authorization is bound to the BacktestAdapter, never to a token."""
from datetime import datetime, timezone

import pytest

from titan._core import Money, RiskConfig, TradeIntent
from titan.backtest.engine import ReplayEngine
from titan.execution.backtest_adapter import BacktestAdapter
from titan.execution.engine import PaperConfig, PaperTradingEngine


def _config():
    risk = RiskConfig(["EURUSD"], Money("50000", "USD"), 1000, 5000, Money("100000", "USD"),
                      0.10, Money("5000", "USD"), 5000, 100)
    return PaperConfig(risk_config=risk, reconciliation_config=None, currency="USD",
                       starting_capital="100000", account_id="paper-1", state_path="")


def _intent(cert=None, strategy_id="s"):
    kwargs = dict(strategy_id=strategy_id, strategy_package_digest="", account_id="paper-1",
                  instrument_id="EURUSD", side="BUY", quantity="10", order_type="MARKET",
                  time_in_force="DAY", risk_profile_version="1.0",
                  market_data_timestamp=datetime.now(timezone.utc).isoformat(), price="1.0500")
    if cert is not None:
        kwargs["certificate_ref"] = cert
    return TradeIntent(**kwargs)


def _bars(n=40):
    bars = []
    for i in range(n):
        px = 100 + (i % 10) - (5 if i % 20 >= 10 else 0)
        bars.append({"instrument_id": "AAA", "timestamp": f"2024-01-{1 + i % 28:02d}T{i % 24:02d}:00:00Z",
                     "open": px, "high": px + 1, "low": px - 1, "close": px, "volume": 1000})
    return bars


class _Flip:
    strategy_id = "flip"

    def __init__(self):
        self.n = 0

    def update(self, price):
        self.n += 1
        return ("BUY", "SELL")[self.n % 2] if self.n % 5 == 0 else None


class _NotABacktest(BacktestAdapter):
    pass


def test_replay_runs_without_any_certificate():
    result = ReplayEngine(_Flip(), _bars()).run()
    assert result.bars_processed > 0
    assert result.trades > 0
    assert result.rejected_intents == 0


@pytest.mark.parametrize("cert", [None, "replay-engine-cert", "backtest-cert", '{"strategy_id": "s"}'])
def test_paper_gate_still_rejects_missing_or_fake_certificates(cert):
    engine = PaperTradingEngine(_config(), object())
    with pytest.raises(ValueError, match="(?i)certificate"):
        engine.submit_intent(_intent(cert))


def test_paper_gate_rejects_forged_signature():
    forged = '{"strategy_id": "s", "expires_at": "2099-01-01T00:00:00Z", "signature": "' + "00" * 64 + '"}'
    engine = PaperTradingEngine(_config(), object())
    with pytest.raises(ValueError, match="(?i)certificate"):
        engine.submit_intent(_intent(forged))


def test_replay_entry_point_refuses_a_non_backtest_adapter():
    engine = PaperTradingEngine(_config(), object())
    with pytest.raises(ValueError, match="(?i)replay authorization refused"):
        engine.submit_replay_intent(_intent())


def test_replay_entry_point_refuses_a_backtest_adapter_subclass():
    engine = PaperTradingEngine(_config(), _NotABacktest([]))
    with pytest.raises(ValueError, match="(?i)replay authorization refused"):
        engine.submit_replay_intent(_intent())


def test_replay_entry_point_still_refuses_shadow_intents():
    engine = PaperTradingEngine(_config(), BacktestAdapter([]))
    with pytest.raises(ValueError, match="(?i)shadow"):
        engine.submit_replay_intent(_intent(strategy_id="shadow-x"))
