import pytest
from pathlib import Path
from titan.research.db import ResearchDB
from titan.research.promotion import PromotionGate

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_research.db"
    db = ResearchDB(str(db_path))
    yield db_path
    db.close()


def test_promotion_gate_fails_closed_when_data_missing(temp_db):
    db = ResearchDB(str(temp_db))
    # Insert incomplete qualification record missing plateau stability & replication data
    db.set_qualification(
        strategy_id="test-strategy",
        status="WATCHLIST",
        backtest_sharpe=1.8,
        wf_sharpe=1.2,
    )
    db.close()

    gate = PromotionGate(db_path=temp_db, bars=[{"close": 100.0 + i} for i in range(20)])
    result = gate.evaluate("test-strategy")

    assert result["passed"] is False, "Gate must fail closed when mandatory parameter stability or replication data is missing"
    gates_by_name = {g["name"]: g for g in result["gates"]}
    assert gates_by_name["parameter_stability"]["passed"] is False
    assert gates_by_name["independent_replication"]["passed"] is False


def test_promotion_gate_passes_when_all_mandatory_gates_satisfied(temp_db):
    db = ResearchDB(str(temp_db))
    # Insert complete qualification record with plateau stability & replication data
    db.set_qualification(
        strategy_id="test-strategy-qualified",
        status="WATCHLIST",
        backtest_sharpe=1.8,
        wf_sharpe=1.2,
        notes="plateau_stability=0.85 replication_sharpe=1.40 max_correlation=0.10",
    )
    # Insert shadow events to satisfy shadow sufficiency & performance
    db._conn.execute(
        "INSERT INTO shadow_events (strategy_id, simulated_side, simulated_pnl, price, created_at) VALUES (?, 'BUY', 10.0, 100.0, '2026-01-01')"
        , ("test-strategy-qualified",)
    )
    for _ in range(5):
        db._conn.execute(
            "INSERT INTO shadow_events (strategy_id, simulated_side, simulated_pnl, price, created_at) VALUES (?, 'SELL', 10.0, 100.0, '2026-01-01')"
            , ("test-strategy-qualified",)
        )
    db._conn.commit()
    db.close()

    gate = PromotionGate(db_path=temp_db, bars=[{"close": 100.0 + i} for i in range(20)])
    result = gate.evaluate("test-strategy-qualified")

    assert result["passed"] is True
    gates_by_name = {g["name"]: g for g in result["gates"]}
    assert gates_by_name["base_qualification"]["passed"] is True
    assert gates_by_name["walk_forward"]["passed"] is True
    assert gates_by_name["parameter_stability"]["passed"] is True
    assert gates_by_name["independent_replication"]["passed"] is True
    assert gates_by_name["portfolio_impact"]["passed"] is True

def test_portfolio_impact_fails_closed_without_return_series(temp_db):
    """Portfolio impact must NOT pass by default when no correlation metric and
    no derivable return series exist (regression: old code returned True here)."""
    db = ResearchDB(str(temp_db))
    db.set_qualification(
        strategy_id="no-signal-strategy",
        status="WATCHLIST",
        backtest_sharpe=1.5,
        wf_sharpe=1.1,
        notes="plateau_stability=0.85 replication_sharpe=1.20",  # no max_correlation
    )
    db.close()

    gate = PromotionGate(db_path=temp_db, bars=[{"close": 100.0 + i} for i in range(20)])
    result = gate.evaluate("no-signal-strategy")
    gates_by_name = {g["name"]: g for g in result["gates"]}
    # Strategy is not in the registry -> no return series derivable -> fail closed
    assert gates_by_name["portfolio_impact"]["passed"] is False
    assert result["passed"] is False
