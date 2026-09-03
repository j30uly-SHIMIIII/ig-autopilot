"""SQLite schema management for IG-AutoPilot.

Phase 1 defines the `queue` (pending/publishing posts) and `posts`
(publish log) tables. Later phases (plans / insights / comments / logs)
extend this module without changing the Phase 1 schema.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "queue.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pillar_id TEXT,
    caption TEXT NOT NULL DEFAULT '',
    hashtags TEXT NOT NULL DEFAULT '',
    image_paths TEXT NOT NULL DEFAULT '[]',   -- JSON list of PNG paths, carousel order
    media_type TEXT NOT NULL DEFAULT 'carousel',
    scheduled_at TEXT NOT NULL,               -- ISO 8601, local account timezone
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | publishing | published | failed
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    ig_media_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_queue_status_scheduled
    ON queue (status, scheduled_at);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queue (id),
    ig_media_id TEXT NOT NULL,
    permalink TEXT,
    published_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,        -- country|title|event ISO datetime
    title TEXT NOT NULL,
    country TEXT NOT NULL,
    event_at TEXT NOT NULL,                -- ISO 8601, tz-aware
    alerted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_alerts_event_at
    ON calendar_alerts (event_at);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(db_path: Path | str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """Context manager that ensures schema exists and commits/closes on exit."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
