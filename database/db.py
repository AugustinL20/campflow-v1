from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from collections.abc import Iterator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"
BACKUPS_DIR = BASE_DIR / "backups"
DB_PATH = DATA_DIR / "campflow.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_ESTABLISHMENT_ID = 1
DEFAULT_ESTABLISHMENT_NAME = "Camping La Peyrugue"
DEFAULT_ESTABLISHMENT_SLUG = "la-peyrugue"


def ensure_runtime_dirs() -> None:
    for directory in (DATA_DIR, EXPORTS_DIR, LOGS_DIR, BACKUPS_DIR):
        directory.mkdir(exist_ok=True)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    ensure_runtime_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    ensure_runtime_dirs()
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _ensure_default_establishment(conn)
        _migrate_users_columns(conn)
        _migrate_audit_columns(conn)
        _migrate_establishment_columns(conn)
        _migrate_employees_weekly_target(conn)
        _migrate_services_qr_token(conn)


def _ensure_default_establishment(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO establishments (id, name, slug, active)
        VALUES (?, ?, ?, 1)
        """,
        (DEFAULT_ESTABLISHMENT_ID, DEFAULT_ESTABLISHMENT_NAME, DEFAULT_ESTABLISHMENT_SLUG),
    )


def _migrate_users_columns(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "users", "establishment_id", "INTEGER")
    _add_column_if_missing(conn, "users", "must_change_password", "INTEGER DEFAULT 0")


def _migrate_audit_columns(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "validation_logs", "actor_user_id", "INTEGER")


def _migrate_establishment_columns(conn: sqlite3.Connection) -> None:
    table_defaults = {
        "employees": "id",
        "services": "id",
        "punches": "id",
        "work_sessions": "id",
        "manual_time_requests": "id",
        "validation_logs": "id",
    }
    for table in table_defaults:
        _add_column_if_missing(conn, table, "establishment_id", "INTEGER")
        conn.execute(
            f"UPDATE {table} SET establishment_id = ? WHERE establishment_id IS NULL",
            (DEFAULT_ESTABLISHMENT_ID,),
        )


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_employees_weekly_target(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(employees)").fetchall()}
    if "weekly_target_hours" not in columns:
        conn.execute("ALTER TABLE employees ADD COLUMN weekly_target_hours REAL DEFAULT 35")


def _migrate_services_qr_token(conn: sqlite3.Connection) -> None:
    from utils.qr_token import generate_qr_token, verify_qr_token
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(services)").fetchall()}
    if "qr_token" not in columns:
        conn.execute("ALTER TABLE services ADD COLUMN qr_token TEXT")
    rows = conn.execute("SELECT id, qr_token FROM services").fetchall()
    for row in rows:
        if not row["qr_token"] or not verify_qr_token(row["qr_token"]):
            conn.execute("UPDATE services SET qr_token = ? WHERE id = ?", (generate_qr_token(row["id"]), row["id"]))
