"""Event store corruption — fails closed on unreadable data."""
import pytest
import tempfile, os
from titan._core import EventStore


class TestEventStoreCorruption:
    def test_corrupt_store_detected_on_read(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
            f.write(b"this is not a valid SQLite file")
        try:
            with pytest.raises(Exception, match="Failed to open|not a database|corrupt"):
                EventStore(path)
        finally:
            os.unlink(path)

    def test_nonexistent_path_creates_new_store(self):
        """Current behavior: EventStore creates file if it doesn't exist."""
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), "test_nonexistent_store.db")
        try:
            store = EventStore(path)
            count = store.count()
            assert count == 0
        finally:
            store.close()
            if os.path.exists(path):
                os.unlink(path)
