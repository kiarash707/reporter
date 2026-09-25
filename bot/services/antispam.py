"""Anti-spam engine: flood, banned words and link protection.

The service is intentionally conservative: it only acts when the bot has the
required rights, it never touches administrators and every decision is logged so
moderators can audit it.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from telethon import TelegramClient, errors

from bot.config import Settings
from bot.errors import NotConfigured
from bot.services.moderation import ModerationService
from bot.storage.repository import Repository
from bot.utils.telegram import looks_like_link
from bot.utils.time import humanize_delta, parse_datetime, utcnow

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bot.context import AppContext

logger = logging.getLogger("bot.services.antispam")

ACTION_DELETE = "delete"
ACTION_WARN = "warn"
ACTION_MUTE = "mute"

_URL_RE = re.compile(r"(?:https?://|www\.)([^\s/]+)", re.I)
_BARE_DOMAIN_RE = re.compile(r"\b((?:[\w-]+\.)+(?:com|net|org|io|ir|co|ru|xyz|info|me|dev|app))\b", re.I)


@dataclass(slots=True)
class Verdict:
    """Outcome of the anti-spam checks for a single message."""

    reason_key: str
    action: str
    detail: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.reason_key)


class AntispamService:
    """Stateless checks + in-memory flood counters."""

    def __init__(self, settings: Settings, repo: Repository) -> None:
        self.settings = settings
        self.repo = repo
        self.moderation = ModerationService(repo)
        self._history: dict[tuple[int, int], deque[float]] = {}
        self._banned_patterns: list[re.Pattern[str]] = []
        self._compile_banned_words()

    # --- setup ---------------------------------------------------------------
    def _compile_banned_words(self) -> None:
        self._banned_patterns.clear()
        for entry in self.settings.antispam_banned_words:
            try:
                self._banned_patterns.append(re.compile(entry, re.I))
            except re.error:
                # Plain text fallback keeps a typo in the config harmless.
                self._banned_patterns.append(re.compile(re.escape(entry), re.I))
        if self._banned_patterns:
            logger.debug("Loaded %s banned-word pattern(s)", len(self._banned_patterns))

    @property
    def enabled(self) -> bool:
        return self.settings.feature_antispam

    # --- checks --------------------------------------------------------------
    def check(self, *, chat_id: int, user_id: int, text: str, is_new_member: bool = False) -> Verdict:
        """Run every configured check and return the first violation."""
        if not self.enabled:
            return Verdict("", "")

        flood = self._check_flood(chat_id, user_id)
        if flood.blocked:
            return flood

        words = self._check_banned_words(text)
        if words.blocked:
            return words

        link = self._check_links(text, is_new_member=is_new_member)
        if link.blocked:
            return link
        return Verdict("", "")

    def _check_flood(self, chat_id: int, user_id: int) -> Verdict:
        window = float(self.settings.antispam_flood_window)
        limit = self.settings.antispam_flood_messages
        key = (int(chat_id), int(user_id))
        bucket = self._history.setdefault(key, deque(maxlen=limit * 4))
        moment = time.monotonic()
        while bucket and moment - bucket[0] > window:
            bucket.popleft()
        bucket.append(moment)
        if len(bucket) > limit:
            return Verdict("antispam.flood", self.settings.antispam_action, f"{len(bucket)}/{limit}")
        return Verdict("", "")

    def _check_banned_words(self, text: str) -> Verdict:
        if not text or not self._banned_patterns:
            return Verdict("", "")
        for pattern in self._banned_patterns:
            match = pattern.search(text)
            if match:
                return Verdict("antispam.banned_word", self.settings.antispam_action, match.group(0)[:40])
        return Verdict("", "")

    def _check_links(self, text: str, *, is_new_member: bool) -> Verdict:
        if not text:
            return Verdict("", "")
        if self.settings.antispam_new_user_seconds and is_new_member and looks_like_link(text):
            return Verdict("antispam.new_user_link", ACTION_DELETE)
        if not self.settings.antispam_block_links:
            return Verdict("", "")
        for domain in self._domains_in(text):
            if not self._domain_allowed(domain):
                return Verdict("antispam.link", self.settings.antispam_action, domain)
        return Verdict("", "")

    @staticmethod
    def _domains_in(text: str) -> list[str]:
        domains = [match.group(1) for match in _URL_RE.finditer(text)]
        domains += [match.group(1) for match in _BARE_DOMAIN_RE.finditer(text)]
        return [domain.strip(".").lower() for domain in domains if domain]

    def _domain_allowed(self, domain: str) -> bool:
        allowed = [entry.lower().lstrip("@") for entry in self.settings.antispam_allowed_domains]
        for entry in allowed:
            host = urlparse(entry if "://" in entry else f"http://{entry}").hostname or entry
            host = host.lower()
            if domain == host or domain.endswith("." + host):
                return True
        return False

    # --- enforcement ---------------------------------------------------------
    async def enforce(self, ctx: AppContext, event: Any, verdict: Verdict) -> None:
        """Delete the message and apply the configured sanction."""
        client: TelegramClient = ctx.client
        chat_id = int(event.chat_id)
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)

        try:
            await event.delete()
        except errors.MessageDeleteForbiddenError:
            logger.info("Cannot delete message in %s (missing rights)", chat_id)
        except errors.RPCError as exc:
            logger.debug("Delete failed in %s: %s", chat_id, exc)

        reason = ctx.tr(verdict.reason_key, language)
        if verdict.action == ACTION_DELETE:
            self.repo.increment_counter("antispam_deleted")
            return

        if verdict.action == ACTION_MUTE:
            minutes = self.settings.antispam_mute_minutes
            result = await self.moderation.mute(client, chat_id, user_id, minutes)
            self.repo.increment_counter("antispam_muted")
            if not result.ok:
                logger.warning("Auto-mute failed in %s: %s", chat_id, result.reason)
            await self._notify(
                event,
                ctx.tr(
                    "mod.muted",
                    language,
                    target=await self._name(client, user_id),
                    duration=humanize_delta(timedelta(minutes=minutes), language=language),
                    reason=reason,
                ),
            )
            return

        # default: warn, then escalate when the limit is reached
        count = self.repo.add_warning(
            chat_id, user_id, ctx.settings.owner_ids[0] if ctx.settings.owner_ids else 0, reason
        )
        self.repo.increment_counter("antispam_warned")
        limit = self.settings.antispam_warn_limit
        if count >= self.settings.antispam_ban_limit:
            await self.moderation.ban(client, chat_id, user_id)
            self.repo.increment_counter("antispam_banned")
            await self._notify(
                event, ctx.tr("mod.ban_limit_reached", language, target=await self._name(client, user_id))
            )
        elif count >= limit:
            await self.moderation.mute(client, chat_id, user_id, self.settings.antispam_mute_minutes)
            self.repo.increment_counter("antispam_muted")
            await self._notify(
                event, ctx.tr("mod.warn_limit_reached", language, target=await self._name(client, user_id))
            )
        else:
            await self._notify(event, ctx.tr("antispam.warned", language, count=count, limit=limit, reason=reason))

    @staticmethod
    async def _name(client: TelegramClient, user_id: int) -> str:
        try:
            entity = await client.get_entity(user_id)
            from bot.utils.telegram import display_name

            return display_name(entity)
        except Exception:
            return str(user_id)

    @staticmethod
    async def _notify(event: Any, text: str) -> None:
        """Post a short notice in the chat (deleted after a moment if possible)."""
        try:
            notice = await event.respond(text)
        except errors.RPCError:
            return
        try:
            import asyncio

            await asyncio.sleep(12)
            await notice.delete()
        except Exception:  # pragma: no cover - best effort cleanup
            pass

    # --- housekeeping --------------------------------------------------------
    def is_new_member(self, user_id: int, *, seconds: int | None = None) -> bool:
        """Whether the user joined more recently than the configured grace period."""
        window = self.settings.antispam_new_user_seconds if seconds is None else seconds
        if not window:
            return False
        user = self.repo.get_user(user_id)
        if not user or not user.get("created_at"):
            return False
        joined = parse_datetime(user["created_at"])
        if joined is None:
            return False
        return (utcnow() - joined).total_seconds() < window

    def prune_history(self, *, keep_seconds: float | None = None) -> int:
        """Drop stale flood buckets to keep memory flat."""
        window = keep_seconds if keep_seconds is not None else float(self.settings.antispam_flood_window) * 4
        moment = time.monotonic()
        removed = 0
        for key in list(self._history):
            bucket = self._history[key]
            while bucket and moment - bucket[0] > window:
                bucket.popleft()
            if not bucket:
                del self._history[key]
                removed += 1
        return removed

    @property
    def tracked_conversations(self) -> int:
        return len(self._history)

    def ensure_available(self) -> None:
        if not self.enabled:
            raise NotConfigured("Anti-spam is disabled")
