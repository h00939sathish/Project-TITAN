"""Unit tests for the paper-session engine admission sequence.

These tests import configuration only; they never create a TWS connection or a
Nautilus trading node.
"""

from scripts import ibkr_paper_session as paper_session


class _FakeEngine:
    def __init__(self):
        self.registered: list[tuple[object, str]] = []
        self.start_calls: list[bool] = []

    def register_instrument(self, instrument, instrument_id: str) -> None:
        self.registered.append((instrument, instrument_id))

    def start(self, *, sync_from_broker: bool = False) -> None:
        self.start_calls.append(sync_from_broker)


def test_registered_equity_matches_ingress_instrument_id():
    instruments = paper_session._paper_instruments()

    assert set(instruments) == set(paper_session.INSTRUMENT_CONFIG)
    assert instruments["SPY=STK.ARCA"].instrument_id.symbol == "SPY"


def test_engine_registers_instruments_before_broker_sync():
    engine = _FakeEngine()

    paper_session._start_paper_engine(engine)

    expected_ids = ["SPY=STK.ARCA", "QQQ=STK.NASDAQ", "EUR.USD=CASH.IDEALPRO", "GBP.USD=CASH.IDEALPRO"]
    assert [instrument_id for _, instrument_id in engine.registered] == expected_ids
    assert engine.start_calls == [True]
