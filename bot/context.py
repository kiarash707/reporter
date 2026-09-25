"""The application context: one object that carries every collaborator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from telethon import TelegramClient

from bot.config import Settings
from bot.errors import NotConfigured
from bot.i18n import Translator
from bot.services.states import StateStore
from bot.storage.database import Database
from bot.storage.repository import Repository
from bot.utils.text import split_message, truncate
from bot.utils.time import humanize_delta, now

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bot.services.antispam import AntispamService
    from bot.services.ratelimit import RateLimiter
    from bot.services.roles import Roles

logger = logging.getLogger("bot.context")


@dataclass(slots=True)
class AppContext:
    """Everything a handler needs, injected explicitly (no global state)."""

    settings: Settings
    db: Database
    repo: Repository
    i18n: Translator
    roles: Roles
    ratelimit: RateLimiter
    client: TelegramClient | None = None
    antispam: AntispamService | None = None
    states: StateStore = field(default_factory=StateStore)
    # small TTL cache for admin lookups on the anti-spam hot path (chat,user) -> monotonic ts
    admin_cache: dict[tuple[int, int], float] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: now("UTC"))
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("bot"))

    # --- telegram access -----------------------------------------------------
    def require_client(self) -> TelegramClient:
        """Return the connected client.

        Handlers run only after startup, so a missing client is a programming
        error - it is reported as a domain error instead of an ``AttributeError``.
        """
        if self.client is None:
            raise NotConfigured("The Telegram client is not connected yet")
        return self.client

    # --- translations --------------------------------------------------------
    def tr(self, key: str, language: str | None = None, **params: object) -> str:
        """Translate a key using the user's language."""
        return self.i18n.t(key, language or self.settings.default_language, **params)

    def language_of(self, user_id: int) -> str:
        return self.repo.get_language(user_id, self.settings.default_language)

    @property
    def uptime(self) -> str:
        return humanize_delta(now("UTC") - self.started_at)

    @property
    def uptime_seconds(self) -> float:
        return (now("UTC") - self.started_at).total_seconds()

    # --- helpers -------------------------------------------------------------
    def is_owner(self, user_id: int | None) -> bool:
        return user_id is not None and int(user_id) in set(self.settings.owner_ids)

    def is_staff(self, user_id: int | None) -> bool:
        if user_id is None:
            return False
        return self.is_owner(user_id) or int(user_id) in self.repo.staff_ids()

    def backups_dir(self) -> Path:
        path = self.settings.data_path / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def notify_owner(self, text: str, *, category: str = "info") -> None:
        """Send a short notice to every owner (never raises)."""
        if self.client is None:
            return
        message = f"[{category}] {truncate(text, 3500)}"
        for owner_id in self.settings.owner_ids:
            try:
                await self.client.send_message(owner_id, message)
            except Exception as exc:  # pragma: no cover - depends on Telegram state
                logger.debug("Cannot notify owner %s: %s", owner_id, exc)

    async def log_to_chat(self, title: str, body: str = "") -> None:
        """Append an entry to the configured log chat, if any."""
        if self.client is None or not self.settings.log_chat_id:
            return
        text = f"<b>{title}</b>\n{body}".strip()
        for chunk in split_message(text):
            try:
                await self.client.send_message(self.settings.log_chat_id, chunk, parse_mode="html")
            except Exception as exc:  # pragma: no cover - depends on Telegram state
                logger.warning("Cannot write to log chat %s: %s", self.settings.log_chat_id, exc)
                break
