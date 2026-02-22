"""SQLite database engine with migrations."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import sqlite_utils

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS issues (
    id              TEXT PRIMARY KEY,
    repo_owner      TEXT NOT NULL,
    repo_name       TEXT NOT NULL,
    number          INTEGER NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT,
    labels          TEXT,
    url             TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'open',
    has_assignees   INTEGER NOT NULL DEFAULT 0,
    has_linked_prs  INTEGER NOT NULL DEFAULT 0,
    language        TEXT,
    repo_stars      INTEGER,
    created_at      TEXT NOT NULL,
    discovered_at   TEXT NOT NULL,
    UNIQUE(repo_owner, repo_name, number)
);

CREATE TABLE IF NOT EXISTS analyses (
    id              TEXT PRIMARY KEY,
    issue_id        TEXT NOT NULL REFERENCES issues(id),
    rating          TEXT NOT NULL,
    confidence      REAL NOT NULL,
    complexity      TEXT,
    reasoning       TEXT NOT NULL,
    cost_usd        REAL,
    model           TEXT,
    duration_ms     INTEGER,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id              TEXT PRIMARY KEY,
    issue_id        TEXT NOT NULL REFERENCES issues(id),
    status          TEXT NOT NULL DEFAULT 'pending',
    outcome         TEXT,
    cost_usd        REAL,
    duration_ms     INTEGER,
    workspace_path  TEXT,
    pr_url          TEXT,
    pr_number       INTEGER,
    branch_name     TEXT,
    num_turns       INTEGER,
    model           TEXT,
    test_output     TEXT,
    diff_summary    TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_repo ON issues(repo_owner, repo_name);
CREATE INDEX IF NOT EXISTS idx_analyses_issue_id ON analyses(issue_id);
CREATE INDEX IF NOT EXISTS idx_attempts_issue_id ON attempts(issue_id);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status);
CREATE INDEX IF NOT EXISTS idx_attempts_outcome ON attempts(outcome);
"""

MIGRATIONS = [MIGRATION_1]


def get_database(db_path: str) -> sqlite_utils.Database:
    """Initialize and return a database connection with pragmas and migrations.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Configured sqlite_utils.Database instance.
    """
    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db = sqlite_utils.Database(db_path)

    # Configure pragmas for safety and performance
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")

    # Run migrations
    _apply_migrations(db)

    return db


def _get_schema_version(db: sqlite_utils.Database) -> int:
    """Get the current schema version from the database."""
    try:
        rows = list(db.execute("SELECT MAX(version) FROM schema_version").fetchall())
        if rows and rows[0][0] is not None:
            return rows[0][0]
    except sqlite3.OperationalError:
        pass
    return 0


def _apply_migrations(db: sqlite_utils.Database) -> None:
    """Apply pending migrations sequentially."""
    current = _get_schema_version(db)

    for i, migration_sql in enumerate(MIGRATIONS, start=1):
        if i <= current:
            continue
        logger.debug("Applying migration %d", i)
        db.executescript(migration_sql)
        db.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", [i])

    if current < len(MIGRATIONS):
        logger.info("Database migrated from v%d to v%d", current, len(MIGRATIONS))
