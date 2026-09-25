"""SQLite database access with WAL mode, explicit transactions and migrations."""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from bot.errors import StorageError

logger = logging.getLogger("bot.storage.database")

SCHEMA_VERSION = 1

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            language      TEXT    NOT NULL DEFAULT 'fa',
            is_blocked    INTEGER NOT NULL DEFAULT 0,
            blocked_reason TEXT,
            accepted_rules INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT    NOT NULL,
            last_seen_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS groups (
            chat_id       INTEGER PRIMARY KEY,
            title         TEXT,
            anti_spam     INTEGER NOT NULL DEFAULT 1,
            welcome       INTEGER NOT NULL DEFAULT 1,
            rules         TEXT,
            created_at    TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id       INTEGER NOT NULL,
            user_id       INTEGER NOT NULL,
            moderator_id  INTEGER NOT NULL,
            reason        TEXT,
            created_at    TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_warnings_lookup ON warnings(chat_id, user_id);

        CREATE TABLE IF NOT EXISTS tickets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            subject       TEXT    NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'open',
            created_at    TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL,
            admin_id      INTEGER,
            reply         TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id, status);

        CREATE TABLE IF NOT EXISTS ticket_messages (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id     INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
            author_id     INTEGER NOT NULL,
            from_staff    INTEGER NOT NULL DEFAULT 0,
            body          TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ticket_messages ON ticket_messages(ticket_id);

        CREATE TABLE IF NOT EXISTS settings (
            key           TEXT PRIMARY KEY,
            value         TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS stats_counters (
            name          TEXT PRIMARY KEY,
            value         INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id      INTEGER,
            action        TEXT NOT NULL,
            target        TEXT,
            details       TEXT,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rate_limits (
            key           TEXT PRIMARY KEY,
            window_start  REAL NOT NULL,
            hits          INTEGER NOT NULL DEFAULT 0
        );
        """,
    ),
)


class Database:
    """Small, thread-safe SQLite wrapper.

    The bot is single-process; ``check_same_thread=False`` plus a lock lets the
    few synchronous call-sites (scheduled jobs, tests) share one connection.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None

    # --- lifecycle -----------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        """Open (once) and return the connection with sane pragmas."""
        if self._connection is not None:
            return self._connection
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
            self._connection = connection
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot open database at {self.path}: {exc}") from exc
        logger.debug("SQLite ready: %s", self.path)
        return self._connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                finally:
                    self._connection = None

    def migrate(self) -> int:
        """Apply pending migrations and return the resulting schema version."""
        with self._lock:
            connection = self.connect()
            connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            current = int(row["version"]) if row else 0
            for version, script in MIGRATIONS:
                if version <= current:
                    continue
                logger.info("Applying database migration v%s", version)
                connection.executescript(script)
                if row is None and version == MIGRATIONS[0][0]:
                    connection.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))
                    row = True
                else:
                    connection.execute("UPDATE schema_version SET version = ?", (version,))
                current = version
            connection.commit()
            return current

    # --- queries -------------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            connection = self.connect()
            try:
                cursor = connection.execute(sql, params)
                connection.commit()
                return cursor
            except sqlite3.Error as exc:
                connection.rollback()
                raise StorageError(f"Query failed: {exc}\nSQL: {sql}") from exc

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self._lock:
            connection = self.connect()
            try:
                connection.executemany(sql, rows)
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise StorageError(f"Batch query failed: {exc}\nSQL: {sql}") from exc

    def fetch_one(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.connect().execute(sql, params).fetchone()

    def fetch_all(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.connect().execute(sql, params).fetchall())

    def scalar(self, sql: str, params: Sequence[Any] | dict[str, Any] = (), default: Any = 0) -> Any:
        row = self.fetch_one(sql, params)
        if row is None or row[0] is None:
            return default
        return row[0]

    def table_names(self) -> list[str]:
        rows = self.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        return [str(row["name"]) for row in rows]

    def health(self) -> dict[str, Any]:
        """Small diagnostics payload used by ``bot check``."""
        try:
            version = int(self.scalar("SELECT version FROM schema_version LIMIT 1", default=0))
            return {
                "ok": True,
                "path": str(self.path),
                "schema_version": version,
                "tables": len(self.table_names()),
                "size_bytes": self.path.stat().st_size if self.path.exists() else 0,
            }
        except StorageError as exc:
            return {"ok": False, "path": str(self.path), "error": str(exc)}

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
