"""Lightweight SQLite research database — persists every run, metric, and qualification."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "research_data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "titan_research.db"


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class ResearchDB:
    """Research experiment database. Auto-creates tables on first connect."""

    def __init__(self, db_path: str | Path | None = None):
        self._path = Path(db_path or DEFAULT_DB_PATH)
        _ensure_dir(self._path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                params_json TEXT NOT NULL DEFAULT '{}',
                instrument  TEXT NOT NULL DEFAULT 'SPY',
                label       TEXT,
                n_bars      INTEGER NOT NULL DEFAULT 0,
                n_trades    INTEGER NOT NULL DEFAULT 0,
                return_pct  REAL NOT NULL DEFAULT 0.0,
                sharpe      REAL NOT NULL DEFAULT 0.0,
                max_dd_pct  REAL NOT NULL DEFAULT 0.0,
                win_rate    REAL NOT NULL DEFAULT 0.0,
                profit_factor REAL NOT NULL DEFAULT 0.0,
                calmar      REAL NOT NULL DEFAULT 0.0,
                volatility  REAL NOT NULL DEFAULT 0.0,
                commission  REAL NOT NULL DEFAULT 0.0,
                data_source TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS qualifications (
                strategy_id     TEXT PRIMARY KEY,
                version         TEXT NOT NULL DEFAULT '1.0.0',
                status          TEXT NOT NULL DEFAULT 'CANDIDATE',
                backtest_sharpe REAL,
                wf_sharpe       REAL,
                paper_trades    INTEGER,
                backtest_return REAL,
                wf_return       REAL,
                max_dd_pct      REAL,
                qualified_at    TEXT,
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS ensemble_runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    TEXT NOT NULL,
                git_sha       TEXT NOT NULL DEFAULT 'unknown',
                dataset       TEXT NOT NULL,
                threshold     REAL NOT NULL,
                return_pct    REAL NOT NULL,
                sharpe        REAL NOT NULL,
                drawdown      REAL NOT NULL,
                trade_count   INTEGER NOT NULL,
                profit_factor REAL NOT NULL DEFAULT 1.0
            );

            CREATE TABLE IF NOT EXISTS run_tags (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id  INTEGER NOT NULL REFERENCES runs(id),
                key     TEXT NOT NULL,
                value   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shadow_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at      TEXT NOT NULL,
                strategy_id     TEXT NOT NULL,
                instrument      TEXT NOT NULL DEFAULT 'SPY',
                bar_date        TEXT,
                price           REAL NOT NULL,
                signal          TEXT,
                simulated_side  TEXT,
                simulated_qty   INTEGER DEFAULT 0,
                simulated_pnl   REAL DEFAULT 0.0,
                session_id      TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    def log_run(
        self,
        strategy_id: str,
        params: dict | None = None,
        instrument: str = "SPY",
        label: str | None = None,
        n_bars: int = 0,
        n_trades: int = 0,
        return_pct: float = 0.0,
        sharpe: float = 0.0,
        max_dd_pct: float = 0.0,
        win_rate: float = 0.0,
        profit_factor: float = 0.0,
        calmar: float = 0.0,
        volatility: float = 0.0,
        commission: float = 0.0,
        data_source: str = "",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """INSERT INTO runs (created_at, strategy_id, params_json, instrument, label,
               n_bars, n_trades, return_pct, sharpe, max_dd_pct, win_rate,
               profit_factor, calmar, volatility, commission, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, strategy_id, json.dumps(params or {}), instrument, label,
             n_bars, n_trades, return_pct, sharpe, max_dd_pct, win_rate,
             profit_factor, calmar, volatility, commission, data_source),
        )
        self._conn.commit()
        return cur.lastrowid

    def tag_run(self, run_id: int, key: str, value: str) -> None:
        self._conn.execute("INSERT INTO run_tags (run_id, key, value) VALUES (?, ?, ?)",
                          (run_id, key, value))
        self._conn.commit()

    def get_runs(
        self, strategy_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        if strategy_id:
            rows = self._conn.execute(
                "SELECT * FROM runs WHERE strategy_id = ? ORDER BY id DESC LIMIT ?",
                (strategy_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_best_run(self, strategy_id: str, metric: str = "sharpe") -> dict | None:
        allowed = {"sharpe", "return_pct", "profit_factor", "calmar"}
        if metric not in allowed:
            raise ValueError(f"metric must be one of {allowed}")
        row = self._conn.execute(
            f"SELECT * FROM runs WHERE strategy_id = ? ORDER BY {metric} DESC LIMIT 1",
            (strategy_id,),
        ).fetchone()
        return dict(row) if row else None

    def set_qualification(
        self,
        strategy_id: str,
        version: str = "1.0.0",
        status: str = "CANDIDATE",
        backtest_sharpe: float | None = None,
        wf_sharpe: float | None = None,
        paper_trades: int | None = None,
        backtest_return: float | None = None,
        wf_return: float | None = None,
        max_dd_pct: float | None = None,
        notes: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat() if status == "QUALIFIED" else None
        self._conn.execute(
            """INSERT OR REPLACE INTO qualifications
               (strategy_id, version, status, backtest_sharpe, wf_sharpe, paper_trades,
                backtest_return, wf_return, max_dd_pct, qualified_at, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (strategy_id, version, status, backtest_sharpe, wf_sharpe, paper_trades,
             backtest_return, wf_return, max_dd_pct, now, notes),
        )
        self._conn.commit()

    def get_qualifications(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM qualifications WHERE status = ?", (status,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM qualifications ORDER BY strategy_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def log_shadow_event(
        self,
        strategy_id: str,
        instrument: str = "SPY",
        bar_date: str | None = None,
        price: float = 0.0,
        signal: str | None = None,
        simulated_side: str | None = None,
        simulated_qty: int = 0,
        simulated_pnl: float = 0.0,
        session_id: str = "",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """INSERT INTO shadow_events
               (created_at, strategy_id, instrument, bar_date, price, signal,
                simulated_side, simulated_qty, simulated_pnl, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, strategy_id, instrument, bar_date, price, signal,
             simulated_side, simulated_qty, simulated_pnl, session_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_shadow_summary(self, session_id: str | None = None) -> list[dict]:
        if session_id:
            rows = self._conn.execute(
                """SELECT strategy_id,
                          COUNT(*) as events,
                          SUM(CASE WHEN simulated_side IS NOT NULL THEN 1 ELSE 0 END) as trades,
                          SUM(simulated_pnl) as total_pnl
                   FROM shadow_events
                   WHERE session_id = ?
                   GROUP BY strategy_id""",
                (session_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT strategy_id,
                          COUNT(*) as events,
                          SUM(CASE WHEN simulated_side IS NOT NULL THEN 1 ELSE 0 END) as trades,
                          SUM(simulated_pnl) as total_pnl
                   FROM shadow_events
                   GROUP BY strategy_id"""
            ).fetchall()
        return [dict(r) for r in rows]

    def log_ensemble_run(
        self,
        dataset: str,
        threshold: float,
        return_pct: float,
        sharpe: float,
        drawdown: float,
        trade_count: int,
        profit_factor: float = 1.0,
        git_sha: str = "main",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """INSERT INTO ensemble_runs
               (created_at, git_sha, dataset, threshold, return_pct, sharpe, drawdown, trade_count, profit_factor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, git_sha, dataset, threshold, return_pct, sharpe, drawdown, trade_count, profit_factor),
        )
        self._conn.commit()
        return cur.lastrowid

    def close(self) -> None:


        self._conn.close()
