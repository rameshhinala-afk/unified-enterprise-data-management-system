"""SQLite storage: the single unified store for all enterprise entities."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    role     TEXT NOT NULL,
    api_key  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS employees (
    emp_id     TEXT PRIMARY KEY,
    full_name  TEXT,
    email      TEXT,
    department TEXT,
    salary     REAL,
    hire_date  TEXT
);

-- "Golden record" per real-world customer, merged from CRM + ERP
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT,
    email       TEXT,
    phone       TEXT,
    city        TEXT,
    updated_at  TEXT
);

-- Cross reference: which source records make up each golden record
CREATE TABLE IF NOT EXISTS customer_xref (
    source_system TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    PRIMARY KEY (source_system, source_id)
);

CREATE TABLE IF NOT EXISTS dq_issues (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ts  TEXT NOT NULL,
    entity  TEXT NOT NULL,
    ref     TEXT NOT NULL,
    rule    TEXT NOT NULL,
    detail  TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    username  TEXT NOT NULL,
    action    TEXT NOT NULL,
    entity    TEXT,
    entity_id TEXT,
    detail    TEXT
);
"""


@contextmanager
def session(path: Path) -> Iterator[sqlite3.Connection]:
    """Open a connection; commit on success, roll back on error."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path) -> None:
    with session(path) as conn:
        conn.executescript(SCHEMA)
