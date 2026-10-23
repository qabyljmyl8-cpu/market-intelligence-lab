"""SQLite database setup with a small, forward-compatible schema version."""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

SCHEMA_VERSION = 1

class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("MIL_DATABASE_PATH", "market_intelligence_lab.sqlite3")).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=8.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=8000")
        return conn

    @contextmanager
    def connection(self):
        """Read/general-purpose connection that always closes deterministically."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"Database schema version {version} is newer than this application supports ({SCHEMA_VERSION}).")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    evidence_score INTEGER NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_history(created_at DESC);
                CREATE TABLE IF NOT EXISTS agent_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL REFERENCES analysis_history(id) ON DELETE CASCADE,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS paper_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    side TEXT,
                    quantity REAL NOT NULL DEFAULT 0,
                    price REAL NOT NULL DEFAULT 0,
                    fee REAL NOT NULL DEFAULT 0,
                    cash_delta REAL NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_paper_created ON paper_events(created_at, id);
            """)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
