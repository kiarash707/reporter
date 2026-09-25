"""Repository layer: every SQL statement lives here, handlers only see dicts."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from bot.storage.database import Database
from bot.utils.time import ensure_aware, now, parse_datetime

logger = logging.getLogger("bot.storage.repository")

TICKET_OPEN = "open"
TICKET_ANSWERED = "answered"
TICKET_CLOSED = "closed"
TICKET_STATUSES = (TICKET_OPEN, TICKET_ANSWERED, TICKET_CLOSED)

GROUP_TOGGLE_FIELDS = {"anti_spam", "welcome"}


class Repository:
    """High-level, timezone-aware data access."""

    def __init__(self, db: Database, *, timezone: str = "UTC") -> None:
        self.db = db
        self.timezone = timezone

    # --- internal helpers ----------------------------------------------------
    def _now(self) -> datetime:
        return now(self.timezone)

    def _stamp(self) -> str:
        return self._now().isoformat(timespec="seconds")

    @staticmethod
    def _row_to_dict(
        row: Any, *, datetime_fields: tuple[str, ...] = (), bool_fields: tuple[str, ...] = ()
    ) -> dict[str, Any]:
        data = dict(row) if row is not None else {}
        for field in datetime_fields:
            if field in data:
                data[field] = parse_datetime(data[field])
        for field in bool_fields:
            if field in data:
                data[field] = bool(data[field])
        return data

    # --- users ---------------------------------------------------------------
    def upsert_user(
        self,
        user_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        language: str | None = None,
    ) -> None:
        stamp = self._stamp()
        self.db.execute(
            """
            INSERT INTO users (user_id, username, first_name, language, created_at, last_seen_at)
            VALUES (?, ?, ?, COALESCE(?, 'fa'), ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username     = COALESCE(excluded.username, users.username),
                first_name   = COALESCE(excluded.first_name, users.first_name),
                language     = COALESCE(?, users.language),
                last_seen_at = excluded.last_seen_at
            """,
            (int(user_id), username, first_name, language, stamp, stamp, language),
        )

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM users WHERE user_id = ?", (int(user_id),))
        if row is None:
            return None
        return self._row_to_dict(
            row, datetime_fields=("created_at", "last_seen_at"), bool_fields=("is_blocked", "accepted_rules")
        )

    def get_language(self, user_id: int, default: str = "fa") -> str:
        value = self.db.scalar("SELECT language FROM users WHERE user_id = ?", (int(user_id),), default=None)
        return str(value) if value else default

    def set_language(self, user_id: int, language: str) -> None:
        self.db.execute(
            """
            INSERT INTO users (user_id, language, created_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language = excluded.language, last_seen_at = excluded.last_seen_at
            """,
            (int(user_id), language, self._stamp(), self._stamp()),
        )

    def set_accepted_rules(self, user_id: int, accepted: bool = True) -> None:
        self.db.execute("UPDATE users SET accepted_rules = ? WHERE user_id = ?", (int(accepted), int(user_id)))

    def is_blocked(self, user_id: int) -> bool:
        return bool(self.db.scalar("SELECT is_blocked FROM users WHERE user_id = ?", (int(user_id),), default=0))

    def set_blocked(self, user_id: int, blocked: bool = True, *, reason: str | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO users (user_id, is_blocked, blocked_reason, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_blocked = excluded.is_blocked, blocked_reason = excluded.blocked_reason
            """,
            (int(user_id), int(blocked), reason, self._stamp(), self._stamp()),
        )

    def broadcast_targets(self) -> list[dict[str, Any]]:
        """Reachable users: never blocked, seen at least once."""
        rows = self.db.fetch_all(
            "SELECT user_id, language, first_name FROM users WHERE is_blocked = 0 ORDER BY last_seen_at DESC"
        )
        return [dict(row) for row in rows]

    def user_stats(self, *, active_days: int = 7) -> dict[str, int]:
        cutoff = (self._now() - timedelta(days=active_days)).isoformat(timespec="seconds")
        return {
            "total": int(self.db.scalar("SELECT COUNT(*) FROM users", default=0)),
            "blocked": int(self.db.scalar("SELECT COUNT(*) FROM users WHERE is_blocked = 1", default=0)),
            "active": int(self.db.scalar("SELECT COUNT(*) FROM users WHERE last_seen_at >= ?", (cutoff,), default=0)),
        }

    # --- groups --------------------------------------------------------------
    def upsert_group(self, chat_id: int, title: str | None = None) -> None:
        stamp = self._stamp()
        self.db.execute(
            """
            INSERT INTO groups (chat_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = COALESCE(excluded.title, groups.title),
                updated_at = excluded.updated_at
            """,
            (int(chat_id), title, stamp, stamp),
        )

    def get_group(self, chat_id: int) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM groups WHERE chat_id = ?", (int(chat_id),))
        if row is None:
            return None
        return self._row_to_dict(
            row, datetime_fields=("created_at", "updated_at"), bool_fields=("anti_spam", "welcome")
        )

    def group_feature_enabled(self, chat_id: int, feature: str, default: bool = True) -> bool:
        """Whether a group-level toggle (anti_spam / welcome) is on."""
        if feature not in GROUP_TOGGLE_FIELDS:
            raise ValueError(f"Unknown group feature: {feature}")
        value = self.db.scalar(f"SELECT {feature} FROM groups WHERE chat_id = ?", (int(chat_id),), default=None)
        return default if value is None else bool(value)

    def set_group_feature(self, chat_id: int, feature: str, enabled: bool) -> bool:
        if feature not in GROUP_TOGGLE_FIELDS:
            raise ValueError(f"Unknown group feature: {feature}")
        self.upsert_group(chat_id)
        self.db.execute(
            f"UPDATE groups SET {feature} = ?, updated_at = ? WHERE chat_id = ?",
            (int(enabled), self._stamp(), int(chat_id)),
        )
        return enabled

    def set_group_rules(self, chat_id: int, text: str) -> None:
        self.upsert_group(chat_id)
        self.db.execute(
            "UPDATE groups SET rules = ?, updated_at = ? WHERE chat_id = ?", (text, self._stamp(), int(chat_id))
        )

    def get_group_rules(self, chat_id: int) -> str | None:
        value = self.db.scalar("SELECT rules FROM groups WHERE chat_id = ?", (int(chat_id),), default=None)
        return str(value) if value else None

    def list_groups(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT chat_id, title, anti_spam, welcome FROM groups ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in rows]

    # --- warnings ------------------------------------------------------------
    def add_warning(self, chat_id: int, user_id: int, moderator_id: int, reason: str | None = None) -> int:
        self.db.execute(
            "INSERT INTO warnings (chat_id, user_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(chat_id), int(user_id), int(moderator_id), reason, self._stamp()),
        )
        return self.warning_count(chat_id, user_id)

    def warning_count(self, chat_id: int, user_id: int) -> int:
        return int(
            self.db.scalar(
                "SELECT COUNT(*) FROM warnings WHERE chat_id = ? AND user_id = ?",
                (int(chat_id), int(user_id)),
                default=0,
            )
        )

    def clear_warnings(self, chat_id: int, user_id: int) -> int:
        removed = self.warning_count(chat_id, user_id)
        self.db.execute("DELETE FROM warnings WHERE chat_id = ? AND user_id = ?", (int(chat_id), int(user_id)))
        return removed

    def recent_warnings(self, chat_id: int, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT * FROM warnings WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (int(chat_id), limit)
        )
        return [self._row_to_dict(row, datetime_fields=("created_at",)) for row in rows]

    # --- tickets -------------------------------------------------------------
    def create_ticket(self, user_id: int, subject: str, body: str) -> int:
        stamp = self._stamp()
        cursor = self.db.execute(
            "INSERT INTO tickets (user_id, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (int(user_id), subject, TICKET_OPEN, stamp, stamp),
        )
        ticket_id = int(cursor.lastrowid or 0)
        self.db.execute(
            "INSERT INTO ticket_messages (ticket_id, author_id, from_staff, body, created_at) VALUES (?, ?, 0, ?, ?)",
            (ticket_id, int(user_id), body, stamp),
        )
        return ticket_id

    def get_ticket(self, ticket_id: int) -> dict[str, Any] | None:
        row = self.db.fetch_one("SELECT * FROM tickets WHERE id = ?", (int(ticket_id),))
        if row is None:
            return None
        return self._row_to_dict(row, datetime_fields=("created_at", "updated_at"))

    def ticket_messages(self, ticket_id: int) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY id", (int(ticket_id),))
        return [self._row_to_dict(row, datetime_fields=("created_at",), bool_fields=("from_staff",)) for row in rows]

    def add_ticket_message(self, ticket_id: int, author_id: int, body: str, *, from_staff: bool = False) -> None:
        stamp = self._stamp()
        self.db.execute(
            "INSERT INTO ticket_messages (ticket_id, author_id, from_staff, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(ticket_id), int(author_id), int(from_staff), body, stamp),
        )
        self.db.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (stamp, int(ticket_id)))

    def set_ticket_status(
        self, ticket_id: int, status: str, *, admin_id: int | None = None, reply: str | None = None
    ) -> None:
        if status not in TICKET_STATUSES:
            raise ValueError(f"Unknown ticket status: {status}")
        self.db.execute(
            "UPDATE tickets SET status = ?, admin_id = COALESCE(?, admin_id), reply = COALESCE(?, reply), updated_at = ? WHERE id = ?",
            (status, admin_id, reply, self._stamp(), int(ticket_id)),
        )

    def list_tickets(
        self, *, status: str | None = None, user_id: int | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(int(user_id))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self.db.fetch_all(f"SELECT * FROM tickets {where} ORDER BY id DESC LIMIT ?", params)
        return [self._row_to_dict(row, datetime_fields=("created_at", "updated_at")) for row in rows]

    def count_open_tickets(self, user_id: int | None = None) -> int:
        if user_id is None:
            return int(self.db.scalar("SELECT COUNT(*) FROM tickets WHERE status != ?", (TICKET_CLOSED,), default=0))
        return int(
            self.db.scalar(
                "SELECT COUNT(*) FROM tickets WHERE user_id = ? AND status != ?",
                (int(user_id), TICKET_CLOSED),
                default=0,
            )
        )

    def last_ticket_time(self, user_id: int) -> datetime | None:
        value = self.db.scalar("SELECT MAX(created_at) FROM tickets WHERE user_id = ?", (int(user_id),), default=None)
        return parse_datetime(value, self.timezone) if value else None

    # --- key/value settings & counters ---------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        value = self.db.scalar("SELECT value FROM settings WHERE key = ?", (key,), default=None)
        return default if value is None else str(value)

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, str(value), self._stamp()),
        )

    def get_flag(self, key: str, default: bool = True) -> bool:
        value = self.get_setting(key)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "on", "yes"}

    def set_flag(self, key: str, enabled: bool) -> bool:
        self.set_setting(key, "on" if enabled else "off")
        return enabled

    def increment_counter(self, name: str, amount: int = 1) -> int:
        self.db.execute(
            """
            INSERT INTO stats_counters (name, value) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = value + ?
            """,
            (name, int(amount), int(amount)),
        )
        return int(self.db.scalar("SELECT value FROM stats_counters WHERE name = ?", (name,), default=0))

    def get_counter(self, name: str) -> int:
        return int(self.db.scalar("SELECT value FROM stats_counters WHERE name = ?", (name,), default=0))

    def all_counters(self) -> dict[str, int]:
        return {
            str(row["name"]): int(row["value"]) for row in self.db.fetch_all("SELECT name, value FROM stats_counters")
        }

    # --- staff (extra moderators granted by the owner) -----------------------
    def staff_ids(self) -> set[int]:
        """User ids explicitly granted staff rights by an owner."""
        raw = self.get_setting("staff_ids", "[]") or "[]"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return set()
        if not isinstance(payload, list):
            return set()
        result: set[int] = set()
        for item in payload:
            try:
                result.add(int(item))
            except (TypeError, ValueError):
                continue
        return result

    def _save_staff(self, ids: set[int]) -> None:
        self.set_setting("staff_ids", json.dumps(sorted(ids)))

    def add_staff(self, user_id: int, *, actor_id: int | None = None) -> bool:
        ids = self.staff_ids()
        if int(user_id) in ids:
            return False
        ids.add(int(user_id))
        self._save_staff(ids)
        self.audit(actor_id, "staff_add", target=str(user_id))
        return True

    def remove_staff(self, user_id: int, *, actor_id: int | None = None) -> bool:
        ids = self.staff_ids()
        if int(user_id) not in ids:
            return False
        ids.discard(int(user_id))
        self._save_staff(ids)
        self.audit(actor_id, "staff_remove", target=str(user_id))
        return True

    # --- audit ---------------------------------------------------------------
    def audit(self, actor_id: int | None, action: str, *, target: str | None = None, details: Any = None) -> None:
        payload = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else details
        self.db.execute(
            "INSERT INTO audit_log (actor_id, action, target, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(actor_id) if actor_id is not None else None, action, target, payload, self._stamp()),
        )

    def recent_audit(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        return [self._row_to_dict(row, datetime_fields=("created_at",)) for row in rows]

    # --- rate limiting -------------------------------------------------------
    def check_rate_limit(self, scope: str, key: Any, limit: int, window_seconds: float) -> tuple[bool, float]:
        """Fixed-window rate limiter backed by SQLite.

        Returns ``(allowed, retry_after)``; ``retry_after`` is seconds until the
        window resets when the caller is over the limit (0 otherwise).
        """
        identifier = f"{scope}:{key}"
        moment = time.time()
        with self.db._lock:  # single statement pair, atomically applied
            row = self.db.fetch_one("SELECT window_start, hits FROM rate_limits WHERE key = ?", (identifier,))
            if row is None or moment - float(row["window_start"]) >= window_seconds:
                self.db.execute(
                    """
                    INSERT INTO rate_limits (key, window_start, hits) VALUES (?, ?, 1)
                    ON CONFLICT(key) DO UPDATE SET window_start = excluded.window_start, hits = 1
                    """,
                    (identifier, moment),
                )
                return True, 0.0
            hits = int(row["hits"]) + 1
            if hits > limit:
                retry_after = max(0.0, window_seconds - (moment - float(row["window_start"])))
                return False, round(retry_after, 1)
            self.db.execute("UPDATE rate_limits SET hits = ? WHERE key = ?", (hits, identifier))
            return True, 0.0

    def cooldown_remaining(self, scope: str, key: Any, seconds: float) -> float:
        """Seconds left on a cooldown, registered once via ``start_cooldown``."""
        value = self.db.scalar("SELECT value FROM settings WHERE key = ?", (f"cooldown:{scope}:{key}",), default=None)
        if not value:
            return 0.0
        started = ensure_aware(datetime.fromisoformat(str(value)), self.timezone)
        remaining = (started + timedelta(seconds=seconds) - self._now()).total_seconds()
        return round(remaining, 1) if remaining > 0 else 0.0

    def start_cooldown(self, scope: str, key: Any) -> None:
        self.db.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (f"cooldown:{scope}:{key}", self._stamp(), self._stamp()),
        )

    # --- maintenance ---------------------------------------------------------
    def prune_rate_limits(self) -> int:
        """Drop stale rate-limit rows so the table stays tiny."""
        cursor = self.db.execute("DELETE FROM rate_limits WHERE window_start < ?", (time.time() - 3600,))
        return int(cursor.rowcount or 0)

    def backup(self, destination: Path) -> Path:
        """Consistent copy of the database (SQLite online backup API)."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.db.connect()
        with self.db._lock:
            target = __import__("sqlite3").connect(str(destination))
            try:
                source.backup(target)
            finally:
                target.close()
        return destination

    # --- legacy import -------------------------------------------------------
    def import_legacy_json(self, path: Path) -> dict[str, int]:
        """Import user records from the JSON file used by the previous version.

        Only neutral account data is carried over (language, blocked state and
        support tickets); nothing operational.
        """
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Legacy file is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Legacy file must contain a JSON object")

        imported = {"users": 0, "blocked": 0, "languages": 0, "tickets": 0}

        for raw_id in payload.get("users", []) or []:
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            self.upsert_user(user_id)
            imported["users"] += 1

        for raw_id, meta in (payload.get("user_lang", {}) or {}).items():
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            language = meta if isinstance(meta, str) else (meta or {}).get("lang", "fa")
            if language in {"fa", "en"}:
                self.set_language(user_id, language)
                imported["languages"] += 1

        for raw_id in payload.get("blocked", []) or []:
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            self.set_blocked(user_id, True, reason="imported from legacy data file")
            imported["blocked"] += 1

        for raw_id, ticket in (payload.get("support_tickets", {}) or {}).items():
            if not isinstance(ticket, dict):
                continue
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            subject = str(ticket.get("subject") or ticket.get("title") or "Legacy ticket")
            body = str(ticket.get("message") or ticket.get("text") or "-")
            ticket_id = self.create_ticket(user_id, subject[:200], body)
            status = str(ticket.get("status", TICKET_OPEN))
            self.set_ticket_status(ticket_id, status if status in TICKET_STATUSES else TICKET_OPEN)
            imported["tickets"] += 1

        total_reports = payload.get("total_reports")
        if isinstance(total_reports, int) and total_reports > 0:
            self.set_setting("legacy_total_reports", str(total_reports))

        logger.info("Legacy import finished: %s", imported)
        return imported
