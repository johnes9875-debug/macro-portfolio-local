from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd


def operations_db(project_root: Path) -> Path:
    p = Path(project_root) / "data" / "operations.sqlite3"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect(project_root: Path):
    con = sqlite3.connect(operations_db(project_root), timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS local_pipeline_runs (
            run_id TEXT PRIMARY KEY,
            market_session TEXT,
            started_at TEXT,
            completed_at TEXT,
            status TEXT,
            error_message TEXT,
            model_version TEXT,
            code_version TEXT
        )
    """)
    con.commit()
    return con


def start_run(project_root: Path, run_id: str, market_session, model_version: str, code_version: str) -> None:
    con = _connect(project_root)
    try:
        con.execute(
            "INSERT OR REPLACE INTO local_pipeline_runs VALUES (?, ?, ?, NULL, 'RUNNING', NULL, ?, ?)",
            [run_id, str(market_session), datetime.now().isoformat(), model_version, code_version],
        )
        con.commit()
    finally:
        con.close()


def finish_run(project_root: Path, run_id: str, status: str, error_message: str | None = None) -> None:
    con = _connect(project_root)
    try:
        con.execute(
            "UPDATE local_pipeline_runs SET completed_at=?, status=?, error_message=? WHERE run_id=?",
            [datetime.now().isoformat(), status, error_message, run_id],
        )
        con.commit()
    finally:
        con.close()


def session_already_succeeded(project_root: Path, market_session) -> bool:
    con = _connect(project_root)
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM local_pipeline_runs WHERE market_session=? AND status='SUCCESS'",
            [str(market_session)],
        ).fetchone()[0]
        return bool(n)
    finally:
        con.close()


def run_history(project_root: Path, limit: int = 100) -> pd.DataFrame:
    con = _connect(project_root)
    try:
        return pd.read_sql_query(
            "SELECT * FROM local_pipeline_runs ORDER BY started_at DESC LIMIT ?", con, params=[limit]
        )
    finally:
        con.close()
