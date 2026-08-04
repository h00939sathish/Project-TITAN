"""FeedHealthSnapshot fail-closed predicates (ADR-019)."""

from titan.data.feed_health import FeedHealthSnapshot


class FakeFeed:
    """Implements the TWSRealtimeFeed health contract we depend on."""

    def __init__(self, healthy=True, recovering=False, advancing=True, latest=None):
        self._healthy = healthy
        self._recovering = recovering
        self._advancing = advancing
        self._latest = latest or {}

    def is_healthy(self, stale_after_s):
        return self._healthy

    def needs_recovery(self):
        return self._recovering

    def bars_advancing(self, since_ts=None):
        return self._advancing

    def latest_completed(self, instr):
        return self._latest.get(instr)


def _snap(feed, instruments=("AAPL", "MSFT")):
    return FeedHealthSnapshot(feed, list(instruments), 30.0)


class TestFeedHealthSnapshot:
    def test_absent_feed_fails_closed(self):
        v = _snap(None).evaluate()
        assert v.healthy is False
        assert v.reason == "feed_health_absent"

    def test_recovering_fails_closed(self):
        v = _snap(FakeFeed(recovering=True)).evaluate()
        assert v.healthy is False
        assert v.reason == "feed_recovering"

    def test_stale_fails_closed(self):
        v = _snap(FakeFeed(healthy=False)).evaluate()
        assert v.healthy is False
        assert v.reason == "feed_stale"

    def test_not_advancing_fails_closed(self):
        v = _snap(FakeFeed(advancing=False)).evaluate()
        assert v.healthy is False
        assert v.reason == "bar_not_advancing"

    def test_all_instruments_uncovered(self):
        v = _snap(FakeFeed(latest={})).evaluate()
        assert v.healthy is False
        assert v.reason == "instrument_uncovered"

    def test_partial_coverage_fails(self):
        feed = FakeFeed(latest={"AAPL": ("2026-01-01T05:00:00Z", 100.0)})
        v = _snap(feed).evaluate()  # MSFT missing
        assert v.healthy is False
        assert v.reason == "instrument_uncovered"
        assert v.watermarks["MSFT"] is None

    def test_healthy_pass_reports_watermarks(self):
        feed = FakeFeed(latest={
            "AAPL": ("2026-01-01T05:00:00Z", 100.0),
            "MSFT": ("2026-01-01T05:00:00Z", 300.0),
        })
        v = _snap(feed).evaluate()
        assert v.healthy is True
        assert v.reason == ""
        assert v.watermarks["AAPL"] == "2026-01-01T05:00:00Z"
        assert v.watermarks["MSFT"] == "2026-01-01T05:00:00Z"

    def test_missing_contract_fails_closed(self):
        class NoContract:
            pass

        v = _snap(NoContract()).evaluate()
        assert v.healthy is False  # must not pass vacuously