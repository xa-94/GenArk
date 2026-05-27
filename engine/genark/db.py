"""数据库连接管理 — 模块级连接池"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    agent_id    TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    source_path TEXT,
    content_hash TEXT NOT NULL,
    prev_hash   TEXT,
    payload     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_agent_time ON events(agent_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_hash ON events(content_hash);

CREATE TABLE IF NOT EXISTS collector_cursor (
    agent_id    TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    byte_offset INTEGER NOT NULL DEFAULT 0,
    file_mtime  REAL,
    last_hash   TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS file_snapshots (
    agent_id    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    captured_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (agent_id, file_path)
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    report_date TEXT NOT NULL,
    stats_json  TEXT NOT NULL,
    narrative   TEXT NOT NULL,
    event_refs  TEXT,
    llm_model   TEXT,
    llm_tokens  INTEGER,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

_conn: sqlite3.Connection | None = None


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    """上下文管理器，自动提交/关闭"""
    conn = _open_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """初始化数据库表"""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
