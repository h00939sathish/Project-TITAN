"""Live integration tests against the real Alpaca paper API.

These tests require valid API credentials in .env and are skipped when
credentials are absent or the API is unreachable.
"""
import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

pytestmark = [pytest.mark.live, pytest.mark.timeout(15)]


def _has_creds() -> bool:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    return bool(key and secret and not key.startswith("YOUR_") and key != "YOUR_ALPACA_KEY_ID")


def _creds():
    return os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"]


class TestAlpacaLiveIntegration:
    def test_heartbeat_with_real_credentials(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        from titan.execution.alpaca_adapter import AlpacaAdapter
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        health = adapter.heartbeat()
        assert health.connected is True

    def test_authenticate_with_real_api(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        from titan.execution.alpaca_adapter import AlpacaAdapter
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        session = adapter.authenticate()
        assert session is not None
        assert "CONNECTED" in session.state.__str__()

    def test_holdings_with_real_api(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        from titan.execution.alpaca_adapter import AlpacaAdapter
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        adapter.authenticate()
        snapshot = adapter.holdings("default")
        assert snapshot is not None
        assert snapshot.currency == "USD"
        assert float(snapshot.cash.amount) >= 0

    def test_positions_with_real_api(self):
        if not _has_creds():
            pytest.skip("Alpaca API credentials not configured in .env")
        from titan.execution.alpaca_adapter import AlpacaAdapter
        api_key, secret_key = _creds()
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key)
        adapter.authenticate()
        snapshot = adapter.positions("default")
        assert snapshot is not None
        assert snapshot.account_id == "default"
