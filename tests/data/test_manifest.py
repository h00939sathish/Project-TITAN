"""Tests for DataManifest."""

from pathlib import Path

from titan.data.ingest import checksum
from titan.data.manifest import DataManifest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "market"


class TestDataManifest:
    def test_create_from_bars(self):
        bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000000},
            {"instrument_id": "AAPL", "timestamp": "2026-01-03T00:00:00", "open": 151.0, "high": 153.0, "low": 150.0, "close": 152.0, "volume": 1100000},
        ]
        manifest = DataManifest.create_from_bars(bars, source_path=str(FIXTURES / "sample_ohlcv.csv"))
        assert manifest.instrument_id == "AAPL"
        assert manifest.date_from == "2026-01-02T00:00:00"
        assert manifest.date_to == "2026-01-03T00:00:00"
        assert manifest.record_count == 2
        assert manifest.source_checksum == checksum(FIXTURES / "sample_ohlcv.csv")
        assert manifest.source_path.endswith("sample_ohlcv.csv")
        assert manifest.applied_adjustments == []
        assert manifest.schema_version == "1.0"
        assert manifest.created_at != ""

    def test_compute_digest(self):
        bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000000},
        ]
        manifest = DataManifest.create_from_bars(bars, source_path=str(FIXTURES / "sample_ohlcv.csv"))
        digest = manifest.compute_digest()
        assert isinstance(digest, str)
        assert len(digest) == 64
        assert manifest.compute_digest() == digest

    def test_different_bars_different_digest(self):
        bars1 = [
            {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000000},
        ]
        bars2 = [
            {"instrument_id": "MSFT", "timestamp": "2026-01-02T00:00:00", "open": 400.0, "high": 405.0, "low": 398.0, "close": 402.0, "volume": 2000000},
        ]
        m1 = DataManifest.create_from_bars(bars1, source_path=str(FIXTURES / "sample_ohlcv.csv"))
        m2 = DataManifest.create_from_bars(bars2, source_path=str(FIXTURES / "sample_ohlcv.csv"))
        assert m1.compute_digest() != m2.compute_digest()

    def test_to_json_round_trip(self):
        bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000000},
        ]
        manifest = DataManifest.create_from_bars(bars, source_path=str(FIXTURES / "sample_ohlcv.csv"))
        json_str = manifest.to_json()
        restored = DataManifest.from_json(json_str)
        assert restored.source_path == manifest.source_path
        assert restored.source_checksum == manifest.source_checksum
        assert restored.instrument_id == manifest.instrument_id
        assert restored.date_from == manifest.date_from
        assert restored.date_to == manifest.date_to
        assert restored.record_count == manifest.record_count
        assert restored.applied_adjustments == manifest.applied_adjustments
        assert restored.schema_version == manifest.schema_version
        assert restored.created_at == manifest.created_at

    def test_digest_length(self):
        bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000000},
        ]
        manifest = DataManifest.create_from_bars(bars, source_path=str(FIXTURES / "sample_ohlcv.csv"))
        digest = manifest.compute_digest()
        assert len(digest) == 64

    def test_applied_adjustments(self):
        adjustments = ["dividend", "split"]
        bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-01-02T00:00:00", "open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000000},
        ]
        manifest = DataManifest.create_from_bars(bars, source_path=str(FIXTURES / "sample_ohlcv.csv"), adjustments=adjustments)
        assert manifest.applied_adjustments == adjustments
        json_str = manifest.to_json()
        restored = DataManifest.from_json(json_str)
        assert restored.applied_adjustments == adjustments
