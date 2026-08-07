"""ADR-022/023 Track 2a tests — qualifications schema carries plateau /
replication / correlation metrics so parameter_stability can be evaluated.

After this change, set_qualification persists plateau_stability,
plateau_coverage, replication_sharpe, and max_correlation, and
_get_qual returns them so _gate_parameter_stability (promotion.py) reads real
stored values instead of failing closed on "missing surface data".
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from titan.research.db import ResearchDB
from titan.research.promotion import PromotionGate, _strategy_return_series


def _fresh_db():
    """A fresh ResearchDB the new schema owns (columns created on init)."""
    tmp = Path(tempfile.mkdtemp(prefix="track2a_")) / "titan_research.db"
    return ResearchDB(str(tmp))


class TestSchemaMigration:
    def test_columns_exist_after_init(self):
        """Fresh DB has the four metric columns in qualifications."""
        db = _fresh_db()
        cols = [r[1] for r in db._conn.execute(
            "PRAGMA table_info(qualifications)")]
        for c in ("plateau_stability", "plateau_coverage",
                  "replication_sharpe", "max_correlation"):
            assert c in cols, f"missing column {c}"

    def test_existing_db_gets_columns_via_alter(self):
        """A DB created WITHOUT the columns is migrated (idempotent ALTER)."""
        # Build a pre-migration table by hand, then open through ResearchDB
        fd = Path(tempfile.mkdtemp(prefix="titan_mig_")) / "old.db"
        c = sqlite3.connect(str(fd))
        c.executescript("""
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL, strategy_id TEXT NOT NULL,
                params_json TEXT NOT NULL DEFAULT '{}',
                instrument TEXT NOT NULL DEFAULT 'SPY', label TEXT,
                n_bars INTEGER NOT NULL DEFAULT 0,
                n_trades INTEGER NOT NULL DEFAULT 0,
                return_pct REAL NOT NULL DEFAULT 0.0,
                sharpe REAL NOT NULL DEFAULT 0.0,
                max_dd_pct REAL NOT NULL DEFAULT 0.0,
                win_rate REAL NOT NULL DEFAULT 0.0,
                profit_factor REAL NOT NULL DEFAULT 0.0,
                calmar REAL NOT NULL DEFAULT 0.0,
                volatility REAL NOT NULL DEFAULT 0.0,
                commission REAL NOT NULL DEFAULT 0.0,
                data_source TEXT NOT NULL DEFAULT '');
            CREATE TABLE qualifications (
                strategy_id TEXT PRIMARY KEY,
                version TEXT NOT NULL DEFAULT '1.0.0',
                status TEXT NOT NULL DEFAULT 'CANDIDATE',
                backtest_sharpe REAL, wf_sharpe REAL, paper_trades INTEGER,
                backtest_return REAL, wf_return REAL, max_dd_pct REAL,
                qualified_at TEXT, notes TEXT);
            CREATE TABLE ensemble_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL, git_sha TEXT NOT NULL DEFAULT 'unknown',
                dataset TEXT NOT NULL, threshold REAL NOT NULL,
                return_pct REAL NOT NULL, sharpe REAL NOT NULL,
                drawdown REAL NOT NULL, trade_count INTEGER NOT NULL,
                profit_factor REAL NOT NULL DEFAULT 1.0);
            CREATE TABLE run_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT);
            CREATE TABLE shadow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT);
            CREATE TABLE ensemble_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT);
        """)
        c.commit()
        # Reinit: the shadow_events/log_shadow_event reference or FK may need
        # more cols; keep this minimal and only assert the ALTER on
        # qualifications happened.
        db = ResearchDB(str(fd))
        cols = [r[1] for r in db._conn.execute(
            "PRAGMA table_info(qualifications)")]
        assert "plateau_stability" in cols
        assert "plateau_coverage" in cols
        assert "replication_sharpe" in cols
        assert "max_correlation" in cols

    def test_set_qualification_roundtrip(self):
        """Writing surface metrics then reading them back preserves values."""
        db = _fresh_db()
        db.set_qualification(
            "test-strat", status="CANDIDATE", backtest_sharpe=1.1,
            wf_sharpe=0.5, plateau_stability=0.82, plateau_coverage=0.30,
            replication_sharpe=1.3, max_correlation=0.1,
        )
        q = db.get_qualifications(status="CANDIDATE")[0]
        assert q["plateau_stability"] == 0.82
        assert q["plateau_coverage"] == 0.30
        assert q["replication_sharpe"] == 1.3
        assert q["max_correlation"] == 0.1


class TestGateReadsColumns:
    def test_parameter_stability_passes_with_stored_values(self):
        """With real stored plateau metrics, the gate passes instead of
        failing closed on 'missing surface data'."""
        db = _fresh_db()
        db.set_qualification(
            "test-strat", status="CANDIDATE", backtest_sharpe=1.0,
            wf_sharpe=0.4, plateau_stability=0.90, plateau_coverage=0.50,
        )
        gate = PromotionGate(db_path=str(Path(db._path)), bars=[], criteria=None)
        gate._db = db  # same instance the test seeded
        result = gate._gate_parameter_stability("test-strat")
        assert result.passed is True
        assert "0.90" in result.evidence or "Stability=0.90" in result.evidence

    def test_parameter_stability_fails_when_below_threshold(self):
        db = _fresh_db()
        db.set_qualification(
            "test-strat", status="CANDIDATE", backtest_sharpe=1.0,
            wf_sharpe=0.4, plateau_stability=0.30, plateau_coverage=0.10,
        )
        bars = []  # not used by this gate
        gate = PromotionGate(db_path=str(Path(db._path)), bars=bars, criteria=None)
        gate._db = db
        result = gate._gate_parameter_stability("test-strat")
        assert result.passed is False