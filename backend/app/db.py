"""Thin, thread-safe SQLite persistence layer (no ORM).

The agent loop runs in a background thread per session, so writes are
serialized behind a single lock. This is a single-process demo app, not a
high-concurrency service, so a global lock is the simplest correct choice.
"""
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ux_autopsy.db"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    task TEXT NOT NULL,
    persona TEXT NOT NULL,
    custom_persona TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    completed INTEGER,
    actions_count INTEGER NOT NULL DEFAULT 0,
    pages_visited INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    friction_count INTEGER,
    ux_score REAL,
    score_breakdown TEXT,
    provider TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    url TEXT,
    element_id TEXT,
    element_text TEXT,
    action TEXT,
    reason TEXT,
    confidence REAL,
    screenshot_path TEXT,
    duration_ms INTEGER,
    decide_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error TEXT
);

CREATE TABLE IF NOT EXISTS friction_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    evidence TEXT,
    affected_action TEXT,
    confidence REAL,
    recommendation TEXT,
    signal TEXT,
    why_json TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
    session_id TEXT PRIMARY KEY,
    executive_summary TEXT,
    root_causes TEXT,
    provider TEXT,
    fallback INTEGER NOT NULL DEFAULT 0,
    fallback_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_friction_session ON friction_points(session_id);
"""


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


class _CursorResult:
    """Rows fetched while still holding the lock, so callers can safely
    fetchone()/fetchall() after execute() returns without racing another
    thread's use of the shared sqlite3 connection."""

    __slots__ = ("_rows", "_idx")

    def __init__(self, rows):
        self._rows = rows
        self._idx = 0

    def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return None

    def fetchall(self):
        rows = self._rows[self._idx:]
        self._idx = len(self._rows)
        return rows


class _SafeConnection:
    """Serializes execute/fetch/commit across threads behind a single lock.

    A plain sqlite3 connection is not safe for concurrent use across threads
    even with check_same_thread=False — fetching from a cursor on one thread
    while another thread executes on the same connection can raise
    'bad parameter or other API misuse'. Materializing rows before releasing
    the lock closes that race.
    """

    def execute(self, sql, params=()):
        with _lock:
            cur = _connect().execute(sql, params)
            rows = cur.fetchall()
            return _CursorResult(rows)

    def executemany(self, sql, seq_of_params):
        with _lock:
            _connect().executemany(sql, seq_of_params)

    def commit(self):
        with _lock:
            _connect().commit()


_wrapped = _SafeConnection()


def get_db() -> _SafeConnection:
    return _wrapped


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    """CREATE TABLE IF NOT EXISTS only handles brand-new databases — a
    pre-existing local demo database from before a column existed needs it
    added explicitly, or later inserts referencing it fail."""
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def init_db() -> None:
    with _lock:
        conn = _connect()
        conn.executescript(SCHEMA)
        _ensure_column(conn, "friction_points", "why_json", "TEXT")
        _ensure_column(conn, "events", "confidence", "REAL")
        _ensure_column(conn, "events", "decide_ms", "INTEGER")
        _ensure_column(conn, "analyses", "fallback", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "analyses", "fallback_reason", "TEXT")
        conn.commit()


def row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]
