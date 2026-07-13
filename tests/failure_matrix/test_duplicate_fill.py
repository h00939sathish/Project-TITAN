"""Duplicate fill — portfolio adds on second apply (dedup at EventStore level)."""
from titan._core import PortfolioEngine, Money


class TestDuplicateFill:
    def test_fill_applied_twice_adds_position(self):
        """PortfolioEngine is additive — no built-in dedup."""
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        portfolio.apply_fill("AAPL", "BUY", 100, Money("150", "USD"))
        pos1 = portfolio.get_position("AAPL")
        assert pos1.quantity == 100
        # Apply same fill again (simulates adapter sending duplicate before event store dedup)
        portfolio.apply_fill("AAPL", "BUY", 100, Money("150", "USD"))
        pos2 = portfolio.get_position("AAPL")
        assert pos2.quantity == 200

    def test_event_store_rejects_duplicate_message_id(self):
        """EventStore deduplicates by message_id — this is the actual dedup mechanism."""
        from titan._core import EventStore, EventEnvelope
        store = EventStore(":memory:")
        env1 = EventEnvelope("Fill", "Order", "ord-1", "adapter", '{"qty":100}')
        env1_json = env1.to_json()
        store.append(env1)
        env2 = EventEnvelope.from_json(env1_json)
        # Duplicate message_id should be rejected
        import pytest
        with pytest.raises(Exception, match="Duplicate"):
            store.append(env2)
