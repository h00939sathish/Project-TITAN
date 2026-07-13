"""Event store write failure — command is rejected, error is not swallowed."""
import pytest
from titan._core import EventStore, EventEnvelope


class TestEventStoreWriteFailure:
    def test_append_to_readonly_store_fails(self):
        store = EventStore(":memory:")
        store.close()
        env = EventEnvelope("Test", "test", "1", "test", "{}")
        with pytest.raises(Exception, match="closed"):
            store.append(env)

    def test_duplicate_message_id_rejected(self):
        store = EventStore(":memory:")
        env = EventEnvelope("Test", "test", "1", "test", "{}")
        # Force same message_id by constructing with a fixed json and re-parsing
        json_str = env.to_json()
        env2 = EventEnvelope.from_json(json_str)
        store.append(env)
        with pytest.raises(Exception, match="Duplicate"):
            store.append(env2)
