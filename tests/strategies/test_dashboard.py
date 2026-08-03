"""Smoke tests for the TITAN Dashboard server."""

from fastapi.testclient import TestClient
from dashboard.server import create_app


app = create_app()
client = TestClient(app)


def test_snapshot_endpoint():
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    data = r.json()
    assert "portfolio" in data
    assert "engine" in data
    assert "strategies" in data
    assert "manifests" in data
    assert "lifecycle" in data
    assert "research" in data
    assert "recent_logs" in data


def test_portfolio_fields():
    r = client.get("/api/snapshot")
    p = r.json()["portfolio"]
    assert "cash" in p
    assert "positions_count" in p
    assert "positions" in p


def test_engine_fields():
    r = client.get("/api/snapshot")
    e = r.json()["engine"]
    assert "intents" in e
    assert "fills" in e
    assert "rejected" in e
    assert "uptime_seconds" in e
    assert "kill_switch" in e


def test_strategies_is_list():
    r = client.get("/api/snapshot")
    assert isinstance(r.json()["strategies"], list)


def test_strategy_has_pnl():
    r = client.get("/api/snapshot")
    for s in r.json()["strategies"]:
        assert "pnl" in s


def test_manifests_fields():
    r = client.get("/api/snapshot")
    m = r.json()["manifests"]
    assert "total" in m
    assert "recent" in m
    assert "by_strategy" in m
    assert "by_side" in m
    assert "by_regime" in m


def test_lifecycle_is_dict():
    r = client.get("/api/snapshot")
    assert isinstance(r.json()["lifecycle"], dict)


def test_research_fields():
    r = client.get("/api/snapshot")
    rs = r.json()["research"]
    assert "qualified" in rs
    assert "watchlist" in rs
    assert "failed" in rs
    assert "top_sharpe" in rs
    assert "top_sharpe_strategy" in rs
    assert "last_qualification" in rs


def test_logs_is_list():
    r = client.get("/api/snapshot")
    assert isinstance(r.json()["recent_logs"], list)
