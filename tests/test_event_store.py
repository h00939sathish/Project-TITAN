"""Tests for the SQLite-backed event store."""

import os
import tempfile

from titan._core import EventEnvelope, EventStore


class TestEventStore:
    def setup_method(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = self.tmp.name
        self.tmp.close()
        self.store = EventStore(self.path)

    def teardown_method(self) -> None:
        self.store.close()
        os.unlink(self.path)

    def test_append_and_count(self) -> None:
        env = EventEnvelope("test.event", "test", "id-1", "svc", '{"n": 1}')
        self.store.append(env)
        assert self.store.count() == 1

    def test_append_multiple(self) -> None:
        for i in range(5):
            env = EventEnvelope(
                "test.event", "test", f"id-{i}", "svc", f'{{"n": {i}}}'
            )
            self.store.append(env)
        assert self.store.count() == 5

    def test_replay_aggregate(self) -> None:
        e1 = EventEnvelope("order.submitted", "order", "ORD-001", "exec", '{"s": "new"}')
        e2 = EventEnvelope("order.acknowledged", "order", "ORD-001", "exec", '{"s": "ack"}')
        e3 = EventEnvelope("order.filled", "order", "ORD-001", "exec", '{"s": "filled"}')
        e4 = EventEnvelope("order.submitted", "order", "ORD-002", "exec", '{"s": "other"}')
        for e in [e1, e2, e3, e4]:
            self.store.append(e)

        events = self.store.replay_aggregate("order", "ORD-001")
        assert len(events) == 3
        assert events[0].message_type == "order.submitted"
        assert events[2].message_type == "order.filled"

    def test_replay_by_type(self) -> None:
        e1 = EventEnvelope("order.submitted", "order", "ORD-001", "exec", '{}')
        e2 = EventEnvelope("risk.decision", "risk", "INT-001", "risk", '{}')
        e3 = EventEnvelope("order.filled", "order", "ORD-001", "exec", '{}')
        for e in [e1, e2, e3]:
            self.store.append(e)

        events = self.store.replay_by_type("order.submitted")
        assert len(events) == 1
        assert events[0].message_type == "order.submitted"

    def test_replay_all(self) -> None:
        events = [
            EventEnvelope("e1", "t1", "a1", "s1", "{}"),
            EventEnvelope("e2", "t2", "a2", "s2", "{}"),
            EventEnvelope("e3", "t3", "a3", "s3", "{}"),
        ]
        for e in events:
            self.store.append(e)

        replayed = self.store.replay_all()
        assert len(replayed) == 3

    def test_duplicate_message_id_rejected(self) -> None:
        env = EventEnvelope("test.event", "test", "id-1", "svc", '{"n": 1}')
        self.store.append(env)
        try:
            self.store.append(env)
            assert False, "Should have rejected duplicate"
        except ValueError:
            pass
        assert self.store.count() == 1

    def test_store_persistence_across_instances(self) -> None:
        env = EventEnvelope("test.event", "test", "id-1", "svc", '{"n": 1}')
        self.store.append(env)
        self.store.close()

        store2 = EventStore(self.path)
        assert store2.count() == 1
        events = store2.replay_all()
        assert len(events) == 1
        assert events[0].message_type == "test.event"
        store2.close()
