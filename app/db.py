"""Database connection and initialization."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def get_db_path() -> Path:
    """Resolve SQLite file path from DATABASE_URL."""
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        return Path(path)
    return Path("./logs.db")


@contextmanager
def get_connection():
    """Yield a DB connection. Creates DB file and table if needed."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    """Create logs table and indexes if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            service TEXT NOT NULL DEFAULT 'unknown',
            correlation_id TEXT,
            metadata TEXT,
            raw TEXT,
            fingerprint TEXT,
            group_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
        CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service);
        CREATE INDEX IF NOT EXISTS idx_logs_correlation_id ON logs(correlation_id);
        CREATE INDEX IF NOT EXISTS idx_logs_group_id ON logs(group_id);
        CREATE INDEX IF NOT EXISTS idx_logs_fingerprint ON logs(fingerprint);
        CREATE TABLE IF NOT EXISTS ingest_totals (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_rejected INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO ingest_totals (id, total_rejected) VALUES (1, 0);
    """)
    conn.commit()


def add_rejected_count(count: int) -> None:
    """Increment total rejected (all time) by count."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE ingest_totals SET total_rejected = total_rejected + ? WHERE id = 1",
            (count,),
        )
        conn.commit()


def get_stats() -> dict:
    """Return total_logs, total_groups, total_rejected (all time) for dashboard."""
    with get_connection() as conn:
        total_logs = conn.execute("SELECT COUNT(*) AS n FROM logs").fetchone()["n"]
        total_groups = conn.execute("SELECT COUNT(DISTINCT group_id) AS n FROM logs").fetchone()["n"]
        row = conn.execute("SELECT total_rejected AS n FROM ingest_totals WHERE id = 1").fetchone()
        total_rejected = row["n"] if row else 0
        return {"total_logs": total_logs, "total_groups": total_groups, "total_rejected": total_rejected}


def get_recent_logs(limit: int = 10) -> list:
    """Return last N logs (id, timestamp, level, message, service) for drill-down."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, timestamp, level, message, service, correlation_id FROM logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
